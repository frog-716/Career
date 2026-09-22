"""T11 page loading, scope and lazy-list contracts."""

import re

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


HEADERS = {"X-Career-Request": "1"}


def client_for(tmp_path):
    return TestClient(create_app(Store(tmp_path / "data", TestProvider())))


def post(client, path, body):
    return client.post(path, json=body, headers=HEADERS)


def test_summary_state_does_not_download_history_payloads(tmp_path):
    client = client_for(tmp_path)
    assert post(client, "/api/jobs", {
        "company": "摘要测试公司",
        "title": "摘要测试岗位",
        "jd": "虚构 JD",
        "idempotency_key": "summary-job",
    }).status_code == 200
    full = client.get("/api/state")
    summary = client.get("/api/state?view=summary")
    assert full.status_code == 200 and summary.status_code == 200
    payload = summary.json()
    assert payload["jobs"]
    assert payload["opportunities"]
    assert payload["runs"] == []
    assert payload["applications"] == []
    assert payload["versions"] == []
    assert payload["artifacts"] == []
    assert payload["feedback"] == []
    assert payload["profile"]["content"] == ""
    assert payload["diagnostics"]["data_dir"] is None if "data_dir" in payload["diagnostics"] else True


def test_opportunity_cursor_is_stable_and_bound_to_view(tmp_path):
    client = client_for(tmp_path)
    for index in range(5):
        response = post(client, "/api/opportunities", {
            "company_name": f"分页公司 {index}",
            "title": f"分页岗位 {index}",
            "jd": "虚构 JD",
            "idempotency_key": f"page-opportunity-{index}",
        })
        assert response.status_code == 200, response.text
    first = client.get("/api/opportunities?view=all&limit=2")
    assert first.status_code == 200
    page = first.json()
    assert len(page["items"]) == 2
    assert page["next_cursor"]
    second = client.get("/api/opportunities?view=all&limit=2&cursor=" + page["next_cursor"])
    assert second.status_code == 200
    page2 = second.json()
    assert not {item["id"] for item in page["items"]} & {item["id"] for item in page2["items"]}
    assert client.get("/api/opportunities?view=ended&limit=2&cursor=" + page["next_cursor"]).status_code == 409


def test_knowledge_cursor_is_stable_and_bound_to_scope(tmp_path):
    client = client_for(tmp_path)
    for index in range(4):
        response = post(client, "/api/knowledge/sources", {
            "title": f"分页资料 {index}",
            "content": f"虚构资料 {index}",
            "source_type": "text",
            "scope_type": "personal",
            "scope_id": "",
            "idempotency_key": f"page-source-{index}",
        })
        assert response.status_code == 200, response.text
    first = client.get("/api/knowledge?scope=personal&tab=sources&limit=2")
    assert first.status_code == 200
    page = first.json()
    assert len(page["items"]) == 2
    assert page["next_cursor"]
    second = client.get("/api/knowledge?scope=personal&tab=sources&limit=2&cursor=" + page["next_cursor"])
    assert second.status_code == 200
    assert not {item["id"] for item in page["items"]} & {item["id"] for item in second.json()["items"]}
    assert client.get("/api/knowledge?scope=all&tab=sources&limit=2&cursor=" + page["next_cursor"]).status_code == 409


def test_t11_frontend_does_not_fake_work_domain_failure_or_hide_interview_entries():
    main = open("frontend/src/main.ts", encoding="utf-8").read()
    interview = open("frontend/src/interview-ui.ts", encoding="utf-8").read()
    assert "api(\"/work-domain\").catch(() => ({" not in main
    assert "pageRequestSequence" in main
    assert "resumes: state.resumes" in main
    assert "生成复盘建议" in interview
    assert "提议研究补丁" in interview
    assert "simulation" in interview


def test_profile_wiki_tab_does_not_query_invalid_knowledge_tab():
    main = open("frontend/src/main.ts", encoding="utf-8").read()
    wiki_branch = main.split('} else if (targetPage === "wiki") {', 1)[1].split(
        '} else if (targetPage === "directory") {', 1
    )[0]
    assert 'if (knowledgeUI.tab === "profile") {' in wiki_branch
    profile_branch = wiki_branch.split('if (knowledgeUI.tab === "profile") {', 1)[1].split(
        '} else {', 1
    )[0]
    assert 'api("/knowledge?" + params.toString())' not in profile_branch
