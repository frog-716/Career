"""A failed opportunity read must never display another opportunity's details."""
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import unquote

import uvicorn
from playwright.sync_api import sync_playwright

from workbench.app import create_app
from test_communication import setup_submitted, create
from test_interview import confirm
from test_record_submitted import opportunity, start, submit


def test_failed_opportunity_read_does_not_reuse_another_owners_details(tmp_path):
    client, store, own = setup_submitted(tmp_path / "data")
    marker = "UX4_SCOPE_A_ONLY_COMMUNICATION"
    event = create(client, own, content=marker)
    assert event.status_code == 200, event.text
    start(client, own)
    confirmed = confirm(client, own)
    assert confirmed.status_code == 200, confirmed.text
    interview = confirmed.json()["interview"]
    other = opportunity(client, "UX4_SCOPE_B_WITHOUT_RESUME")
    assert submit(client, other, {"mode": "none"}).status_code == 200

    frontend = Path(__file__).resolve().parents[1] / "frontend"
    subprocess.run(
        [str(frontend / "node_modules/.bin/vite"), "build", "--outDir", str(tmp_path / "dist")],
        cwd=frontend, check=True, capture_output=True,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        create_app(store, frontend_dir=tmp_path / "dist"),
        host="127.0.0.1", port=port, log_level="error",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="chrome")
            try:
                page = browser.new_page()
                page.goto(
                    f"http://127.0.0.1:{port}/#opportunities/{own['id']}",
                    wait_until="networkidle",
                )
                assert page.get_by_text(marker, exact=True).count() > 0
                assert page.get_by_text("已保存的工作稿", exact=True).count() == 1
                assert page.locator(f'[data-interview="{interview["id"]}"]').count() > 0

                error_message = "UX4 forced selected opportunity resume read failure"

                def fail_other_resume(route):
                    if unquote(route.request.url).endswith(f"/opportunities/{other['id']}/resume"):
                        route.fulfill(
                            status=500, content_type="application/json",
                            body='{"detail":"' + error_message + '"}',
                        )
                    else:
                        route.continue_()

                page.route("**/resume", fail_other_resume)
                page.evaluate(
                    '(id) => location.hash = "opportunities/" + encodeURIComponent(id)',
                    other["id"],
                )
                page.get_by_text(error_message, exact=True).first.wait_for()
                assert page.locator(".op-workspace-heading h2").inner_text() == other["title"]
                leaked = {
                    "communication": page.get_by_text(marker, exact=True).count(),
                    "saved_resume": page.get_by_text("已保存的工作稿", exact=True).count(),
                    "interview": page.locator(f'[data-interview="{interview["id"]}"]').count(),
                }
                assert leaked == {"communication": 0, "saved_resume": 0, "interview": 0}
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(10)
