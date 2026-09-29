"""Both empty-project and employment entry points must use the real browser creation binding."""
from pathlib import Path
import socket
import subprocess
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider
from workbench.secret_store import MemorySecretStore


@pytest.fixture(scope='module')
def ux5_browser_dist(tmp_path_factory):
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    dist = tmp_path_factory.mktemp('ux5-project-build') / 'dist'
    subprocess.run([str(frontend / 'node_modules/.bin/vite'), 'build', '--outDir', str(dist)],
                   cwd=frontend, check=True, capture_output=True)
    return dist


@pytest.mark.parametrize(('route', 'button_name', 'form_selector'), [
    ('projects', '新建项目', '[data-project-form]'), ('work', '新建任职', '#episode-form'),
], ids=['project', 'employment'])
@pytest.mark.parametrize('surface', ['.ux3-empty-project', '.rail-heading'], ids=['central-empty-action', 'rail-plus-action'])
def test_empty_project_action_opens_form_and_cancel_does_not_write(tmp_path, ux5_browser_dist, monkeypatch, surface, route, button_name, form_selector):
    monkeypatch.setenv('CAREER_AI_MODE', 'LOCAL_ONLY')
    monkeypatch.setenv('CAREER_BUILD_ID', 'career-0.7.0-batch-f')
    store = Store(tmp_path / 'data', TestProvider(), MemorySecretStore())
    app = create_app(store, frontend_dir=ux5_browser_dist)
    client = TestClient(app)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        before = client.get('/api/work-domain').json()
        assert before['projects'] == [] and before['employments'] == []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='chrome')
            try:
                page = browser.new_page()
                writes = []
                page.on('request', lambda request: writes.append(request.url)
                        if request.method in {'POST', 'PUT', 'DELETE'} else None)
                page.goto(f'http://127.0.0.1:{port}/#{route}', wait_until='networkidle')
                page.locator(surface).get_by_role('button', name=button_name, exact=True).click()
                form = page.locator('dialog[open] ' + form_selector)
                expect(form).to_be_visible(timeout=3000)
                expect(page.locator('dialog[open]').get_by_role('heading', name=button_name, exact=True)).to_be_visible()
                page.get_by_role('button', name='关闭弹窗', exact=True).click()
                expect(page.locator('dialog[open]')).to_have_count(0)
                assert writes == [], '只打开和取消表单不能发出写请求'
            finally:
                browser.close()
        assert client.get('/api/work-domain').json() == before
    finally:
        server.should_exit = True
        thread.join(10)
