"""T04: text-layer PDF rendering and frozen-material consistency."""
from io import BytesIO
import unicodedata

from fastapi.testclient import TestClient
from pypdf import PdfReader

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1", "Content-Type": "application/json"}


def post(client, path, body):
    response = client.post(path, json=body, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def fake_document(name="林晓岚"):
    long_bullet = "负责将虚构的招聘数据、权限校验和可观测性接入统一平台，完成跨团队交付并通过回归验收。" * 55
    return {
        "schemaVersion": 1,
        "profile": {
            "id": "profile-t04",
            "name": name,
            "contacts": [
                {"id": "contact-phone-t04", "kind": "identity", "content": "电话：13800000000", "href": ""},
                {"id": "contact-email-t04", "kind": "identity", "content": "邮箱：lin@example.test", "href": ""},
                {"id": "contact-github-t04", "kind": "link", "content": "GitHub：lin-xiaolan", "href": "https://github.example.test/lin-xiaolan"},
            ],
        },
        "sections": [
            {"id": "section-skills-t04", "type": "skills", "title": "专业技能", "items": [
                {"id": "skill-t04", "content": "Python、SQLite、接口设计、中文排版"},
            ]},
            {"id": "section-experience-t04", "type": "experience", "title": "工作经历", "items": [
                {"id": "experience-t04-a", "organization": "虚构星河科技", "role": "高级后端工程师", "date": "2024年1月—2025年6月", "bullets": [
                    {"id": "bullet-t04-a1", "content": "<b>平台稳定性：</b>" + long_bullet},
                    {"id": "bullet-t04-a2", "content": "把风险、证据和用户确认动作写入交付流程，项目结果可追溯。"},
                ]},
                {"id": "experience-t04-b", "organization": "虚构云港实验室", "role": "软件工程师", "date": "2022年7月—2023年12月", "bullets": [
                    {"id": "bullet-t04-b1", "content": "构建数据服务和自动化测试，支持多个虚构业务团队。"},
                ]},
            ]},
            {"id": "section-projects-t04", "type": "projects", "title": "项目经历", "items": [
                {"id": "project-t04", "title": "平台重构项目", "responsibility": "技术负责人", "date": "2024年3月—2025年4月", "bullets": [
                    {"id": "bullet-t04-p1", "content": "拆分服务边界，建立发布前检查和失败恢复路径。"},
                ]},
            ]},
        ],
        "formatting": {"font": "CareerResumeCN"},
        "meta": {"title": "T04 虚构中文简历"},
    }


def setup(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(create_app(store), headers=HEADERS)
    opportunity = post(client, "/api/opportunities", {
        "company_name": "虚构星河科技",
        "title": "高级后端工程师",
        "jd": "虚构 JD：负责平台稳定性和项目交付。",
        "idempotency_key": "t04-opportunity",
    })
    document = post(client, f"/api/opportunities/{opportunity['id']}/resume/start", {
        "expected_opportunity_revision": opportunity["revision"],
        "idempotency_key": "t04-start",
        "source": {"kind": "blank"},
    })
    return client, store, opportunity, document


def extracted(response):
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # Chromium's CJK font extraction may insert variation selectors around a
    # glyph; these are not document content and do not affect reading order.
    text = text.replace("\ufe00", "").replace("\ufe01", "")
    return reader, unicodedata.normalize("NFKC", text)


def test_current_export_is_real_text_pdf_with_chinese_pagination_and_order(tmp_path):
    client, _, _, document = setup(tmp_path)
    saved = client.put(
        f"/api/resume-documents/{document['document_id']}",
        json={"document": fake_document(), "expected_revision": document["revision"]},
        headers=HEADERS,
    )
    assert saved.status_code == 200, saved.text
    response = client.post(
        f"/api/resume-documents/{document['document_id']}/pdf",
        json={"expected_revision": saved.json()["revision"]},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    reader, text = extracted(response)
    assert response.content.startswith(b"%PDF-")
    assert len(reader.pages) >= 2
    for value in ("林晓岚", "13800000000", "lin@example.test", "虚构星河科技", "高级后端工程师", "2024年1月", "平台重构项目"):
        assert value in text, value
    order = [text.index(value) for value in ("林晓岚", "虚构星河科技", "高级后端工程师", "平台重构项目")]
    assert order == sorted(order)
    assert response.headers["x-resume-document-hash"]
    assert response.headers["x-resume-renderer-version"].startswith("playwright-1.51.0-chrome-")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "frame-src 'self' blob:" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_submission_pdf_and_material_remain_a_after_current_draft_becomes_b(tmp_path):
    client, store, opportunity, document = setup(tmp_path)
    version_a = fake_document("林晓岚A版")
    saved_a = client.put(
        f"/api/resume-documents/{document['document_id']}",
        json={"document": version_a, "expected_revision": document["revision"]},
        headers=HEADERS,
    ).json()
    created_version = post(client, f"/api/resume-documents/{document['document_id']}/versions", {
        "name": "版本 A",
        "expected_revision": saved_a["revision"],
        "idempotency_key": "t04-version-a",
    })
    submitted = post(client, f"/api/opportunities/{opportunity['id']}/submitted", {
        "expected_revision": opportunity["revision"],
        "idempotency_key": "t04-submit-a",
        "resume": {
            "mode": "draft",
            "document_id": document["document_id"],
            "expected_document_revision": saved_a["revision"],
        },
    })
    frozen_artifact_id = submitted["submission"]["artifact_id"]
    frozen_bytes = client.get(f"/api/artifacts/{frozen_artifact_id}").content
    _, frozen_text = extracted(type("Response", (), {"content": frozen_bytes})())
    assert "林晓岚A版" in frozen_text
    assert submitted["submission"]["resume_snapshot"]["document"]["profile"]["name"] == "林晓岚A版"

    version_b = fake_document("林晓岚B版")
    version_b["sections"][1]["items"][0]["role"] = "平台架构师"
    saved_b = client.put(
        f"/api/resume-documents/{document['document_id']}",
        json={"document": version_b, "expected_revision": saved_a["revision"]},
        headers=HEADERS,
    )
    assert saved_b.status_code == 200, saved_b.text
    current_pdf = client.post(
        f"/api/resume-documents/{document['document_id']}/pdf",
        json={"expected_revision": saved_b.json()["revision"]},
        headers=HEADERS,
    )
    assert current_pdf.status_code == 200, current_pdf.text
    _, current_text = extracted(current_pdf)
    assert "林晓岚B版" in current_text and "平台架构师" in current_text
    assert "林晓岚A版" not in current_text

    assert client.get(f"/api/artifacts/{frozen_artifact_id}").content == frozen_bytes
    assert client.get(f"/api/resume-documents/{document['document_id']}/versions/{submitted['submission_version']['id']}").json()["document"]["profile"]["name"] == "林晓岚A版"
    assert store.state()["applications"][0]["resume_snapshot"]["document"]["profile"]["name"] == "林晓岚A版"
    assert created_version["document"]["profile"]["name"] == "林晓岚A版"
