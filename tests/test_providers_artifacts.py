import base64
import json
from io import BytesIO
from pathlib import Path

import pytest

from workbench.artifacts import ArtifactError, read_artifact, write_pdf, write_screenshot
from workbench.providers import ProviderError, RealProvider, TestProvider, get_provider


FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures/scenarios.json").read_text())
PACKET = {"schemaVersion": 1, "taskKind": "job", "sources": [{"id": "s1", "revision": 2, "purpose": "current_fact", "content": FIXTURE["candidate"]["experience"]["revision2"]}], "instruction": "请分析岗位匹配，不能编造数字。"}


def test_test_provider_is_explicit_and_only_uses_packet_sources(monkeypatch):
    monkeypatch.setenv("CAREER_AI_PROVIDER", "test")
    provider = get_provider()
    assert isinstance(provider, TestProvider)
    assert provider.diagnostics()["mode"] == "test"
    payload = provider.build_payload(PACKET)
    assert json.loads(payload["messages"][1]["content"]) == PACKET
    result = provider.complete(payload)
    assert result["claims"]
    assert result["claims"][0]["source_ids"] == ["s1"]
    assert "旧" not in json.dumps(result, ensure_ascii=False)


def test_default_real_provider_can_start_unconfigured(monkeypatch):
    monkeypatch.delenv("CAREER_AI_PROVIDER", raising=False)
    monkeypatch.delenv("CAREER_AI_MODEL", raising=False)
    monkeypatch.delenv("CAREER_AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = get_provider()
    assert provider.diagnostics()["configured"] is False
    with pytest.raises(ProviderError, match="未配置"):
        provider.complete({})


def test_resume_uses_current_facts_only(monkeypatch):
    monkeypatch.setenv("CAREER_AI_PROVIDER", "test")
    packet = {"taskKind": "resume", "sources": [
        {"id": "current", "purpose": "current_fact", "content": FIXTURE["candidate"]["experience"]["revision2"]},
        {"id": "jd", "purpose": "job", "content": FIXTURE["job"]["jd"]},
    ]}
    result = get_provider().complete(get_provider().build_payload(packet))
    assert result["draft"] == FIXTURE["candidate"]["experience"]["revision2"]
    assert "jd" not in result["claims"][0]["source_ids"]


def test_payload_is_fresh_and_endpoint_validation(monkeypatch):
    monkeypatch.setenv("CAREER_AI_MODEL", "fixture-model")
    monkeypatch.setenv("CAREER_AI_API_KEY", "fixture-key")
    monkeypatch.setenv("CAREER_AI_BASE_URL", "http://example.com/v1")
    with pytest.raises(ProviderError, match="HTTPS"):
        get_provider()


def test_pdf_is_real_chinese_and_safe(tmp_path):
    artifact = write_pdf(tmp_path, "version-1", FIXTURE["candidate"]["experience"]["revision2"] * 300)
    path = tmp_path / artifact["path"]
    assert artifact["media_type"] == "application/pdf"
    assert path.read_bytes().startswith(b"%PDF")
    assert artifact["size"] == path.stat().st_size
    second = write_pdf(tmp_path, "version-2", FIXTURE["candidate"]["experience"]["revision1"])
    assert second["sha256"] != artifact["sha256"]
    with pytest.raises(ArtifactError):
        read_artifact(tmp_path, "../version-1.pdf")


def test_screenshot_validates_media_size_and_path(tmp_path):
    from PIL import Image
    image_data = BytesIO()
    Image.new("RGB", (1, 1), "white").save(image_data, format="PNG")
    png = base64.b64encode(image_data.getvalue()).decode()
    artifact = write_screenshot(tmp_path, "shot-1", {"name": "x.png", "media_type": "image/png", "data_base64": png})
    assert (tmp_path / artifact["path"]).read_bytes().startswith(b"\x89PNG")
    with pytest.raises(ArtifactError):
        write_screenshot(tmp_path, "shot-2", {"media_type": "image/gif", "data_base64": png})


def test_real_provider_posts_exact_payload_and_sanitizes_errors(monkeypatch):
    calls = {}
    class Response:
        content = b'{"choices":[{"message":{"content":"{\\"draft\\":\\"ok\\",\\"claims\\":[]}"}}]}'
        def raise_for_status(self): pass
        def json(self): return json.loads(self.content)
    class Client:
        def __init__(self, **kwargs): calls["options"] = kwargs
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs): calls.update(url=url, kwargs=kwargs); return Response()
    monkeypatch.setattr("workbench.providers.httpx.Client", Client)
    provider = RealProvider("https://example.test/v1", "fixture-model", "secret-key")
    payload = provider.build_payload(PACKET)
    assert provider.complete(payload)["draft"] == "ok"
    assert calls["url"] == "https://example.test/v1/chat/completions"
    assert calls["kwargs"]["json"] == payload
    class Broken(Client):
        def post(self, *args, **kwargs): raise RuntimeError("secret-key upstream body")
    monkeypatch.setattr("workbench.providers.httpx.Client", Broken)
    with pytest.raises(ProviderError) as error:
        provider.complete(payload)
    assert "secret-key" not in str(error.value)


def test_artifact_symlink_root_escape(tmp_path):
    data=tmp_path/'data';outside=tmp_path/'outside';data.mkdir();outside.mkdir()
    (outside/'sample.pdf').write_bytes(b'%PDF')
    (data/'artifacts').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ArtifactError):read_artifact(data,'artifacts/sample.pdf')
