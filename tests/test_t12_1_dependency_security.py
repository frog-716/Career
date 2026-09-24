import base64
from pathlib import Path

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def test_malformed_host_cannot_bypass_local_host_guard(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(
        create_app(
            store,
            runtime_dir=tmp_path / "runtime",
        )
    )

    response = client.get(
        "/api/state",
        headers={"Host": "127.0.0.1/anything?path=/"},
    )

    assert response.status_code == 403


def test_range_requests_do_not_reach_starlette_file_response(tmp_path):
    frontend_dir = tmp_path / "dist"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("虚构静态内容", encoding="utf-8")
    store = Store(tmp_path / "data", TestProvider())
    client = TestClient(
        create_app(
            store,
            frontend_dir=Path(frontend_dir),
        )
    )

    response = client.get("/", headers={"Range": "bytes=0-1"})

    assert response.status_code == 416


def test_screenshot_validation_does_not_decode_untrusted_bytes_with_pillow(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "PIL", None)

    from workbench.artifacts import write_screenshot

    artifact = write_screenshot(
        tmp_path,
        "stdlib-image",
        {
            "media_type": "image/png",
            "data_base64": _ONE_PIXEL_PNG,
        },
    )

    assert artifact["media_type"] == "image/png"
    assert base64.b64decode(_ONE_PIXEL_PNG) == (tmp_path / artifact["path"]).read_bytes()
