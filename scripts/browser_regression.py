#!/usr/bin/env python3
"""Run an isolated, fake-data browser smoke; never defaults to a production URL."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
FIXTURE = ROOT / "tests" / "fixtures" / "t12_browser_fixture.json"
HEADERS = {"X-Career-Request": "1"}


def loopback(url: str) -> bool:
    return urlparse(url).hostname in {"127.0.0.1", "localhost", "::1"}


def wait_for_server(url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen(url + "/healthz", timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("隔离浏览器服务未在限定时间内启动")


def run_existing(base_url: str) -> int:
    if not loopback(base_url):
        raise SystemExit("只允许 loopback base URL；脚本不会连接生产环境")
    with sync_playwright() as playwright:
        browser = None
        page = None
        requests: list[str] = []
        try:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("request", lambda request: requests.append(request.url))
            page.goto(base_url + "/", wait_until="networkidle")
            page.wait_for_selector("#app")
            page.get_by_text("机会", exact=True).first.click()
            page.wait_for_selector("#op-create, .op-page")
            body = page.locator("body").inner_text()
            assert "虚构浏览器回归公司" in body, "隔离 fixture 未显示"
            print(f"browser regression: requests={len(requests)} api_requests={sum('/api/' in url for url in requests)}")
            return 0
        except Exception:
            failure_dir = Path(tempfile.mkdtemp(prefix="career-t12-browser-failure-"))
            if page is not None:
                page.screenshot(path=str(failure_dir / "failure.png"), full_page=True)
                url = page.url
            else:
                url = base_url + "/"
            (failure_dir / "short-log.txt").write_text("url=" + url + "\n" + "requests=" + str(len(requests)) + "\n", encoding="utf-8")
            print(f"browser regression failed; redacted evidence kept at {failure_dir}")
            return 1
        finally:
            if browser is not None:
                browser.close()


def run_isolated() -> int:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data_dir = Path(tempfile.mkdtemp(prefix="career-t12-browser-data-"))
    dist = ROOT / "frontend" / "dist"
    if not dist.exists():
        raise SystemExit("frontend/dist 不存在，请先执行 npm --prefix frontend run build")
    os.environ["CAREER_TEST_MODE"] = "1"
    os.environ["CAREER_AI_MODE"] = "LOCAL_ONLY"
    store = Store(data_dir, TestProvider())
    app = create_app(store, frontend_dir=dist, require_local_session=False)
    client = TestClient(app)
    for index, opportunity in enumerate(fixture["opportunities"]):
        response = client.post(
            "/api/opportunities",
            json={**opportunity, "idempotency_key": f"t12-browser-{index}"},
            headers=HEADERS,
        )
        response.raise_for_status()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{port}"
        wait_for_server(base_url)
        return run_existing(base_url)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        shutil.rmtree(data_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="仅可指定 loopback 的已有隔离服务")
    args = parser.parse_args()
    return run_existing(args.base_url.rstrip("/")) if args.base_url else run_isolated()


if __name__ == "__main__":
    raise SystemExit(main())
