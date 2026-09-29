"""Mac Chrome shortcuts act on a synthetic opportunity-owned Resume."""
import socket
import subprocess
import threading
import time
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from workbench.app import create_app
from workbench.core import Store
from workbench.opportunity import create_opportunity
from workbench.providers import TestProvider
from workbench.secret_store import MemorySecretStore


def test_resume_mac_shortcuts_and_local_find_replace(tmp_path, monkeypatch):
    monkeypatch.setenv('CAREER_AI_MODE', 'LOCAL_ONLY')
    monkeypatch.setenv('CAREER_BUILD_ID', 'career-0.7.0-batch-f')
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    dist = tmp_path / 'dist'
    subprocess.run([str(frontend / 'node_modules/.bin/vite'), 'build', '--outDir', str(dist)],
                   cwd=frontend, check=True, capture_output=True)
    store = Store(tmp_path / 'data', TestProvider(), MemorySecretStore())
    app = create_app(store, frontend_dir=dist, runtime_dir=tmp_path / 'runtime')
    client = TestClient(app, headers={'X-Career-Request': '1'})
    opportunity = create_opportunity(store, {
        'company_name': '虚构快捷键公司', 'title': '虚构岗位', 'jd': '只测试编辑器',
        'idempotency_key': 'shortcuts-opportunity',
    })
    started = client.post(f"/api/opportunities/{opportunity['id']}/resume/start", json={
        'expected_opportunity_revision': opportunity['revision'],
        'idempotency_key': 'shortcuts-start', 'source': {'kind': 'blank'},
    }).json()
    document_id = started['document_id']
    document = started['document']
    document['sections'][0]['items'].append({
        'id': 'shortcut-skill', 'content': '甲乙丙丁 English words',
    })
    saved = client.put(f'/api/resume-documents/{document_id}', json={
        'document': document, 'expected_revision': started['revision'],
    })
    assert saved.status_code == 200, saved.text
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='chrome')
            try:
                page = browser.new_page(viewport={'width': 1280, 'height': 900})
                page.goto(f'http://127.0.0.1:{port}/#resume?document_id={document_id}',
                          wait_until='networkidle')
                editable = page.locator('[data-edit-id="shortcut-skill"]')
                assert editable.count() == 1
                page.evaluate("""() => document.addEventListener('keydown', event => {
                  if (['s','f'].includes(event.key.toLowerCase()))
                    queueMicrotask(() => window.__shortcut = {key:event.key, prevented:event.defaultPrevented});
                })""")
                editable.focus()
                page.keyboard.press('Meta+s')
                assert page.evaluate('window.__shortcut.prevented')
                name = page.locator('dialog[open] input[maxlength="200"]')
                assert name.count() == 1
                name.fill('虚构快捷键版')
                page.locator('dialog[open] button[type="submit"]').click()
                expect(page.locator('#toast')).to_contain_text('已保存版本', timeout=30000)
                versions = client.get(f'/api/resume-documents/{document_id}/versions').json()['versions']
                assert len(versions) == 1 and versions[0]['name'] == '虚构快捷键版'

                editable.focus()
                page.keyboard.press('Meta+f')
                assert page.evaluate('window.__shortcut.prevented')
                panel = page.locator('.resume-find-panel')
                assert panel.count() == 1
                panel.locator('[data-find]').fill('English')
                page.keyboard.press('Meta+ArrowRight')
                assert editable.evaluate('el => el.style.textAlign') == ''
                before_find_undo = editable.inner_html()
                page.keyboard.press('Meta+z')
                assert editable.inner_html() == before_find_undo
                panel.locator('[data-find]').fill('English')
                panel.locator('[data-next]').click()
                assert page.evaluate('window.getSelection().toString()') == 'English'
                panel.locator('[data-replace]').fill('英文')
                panel.locator('[data-apply]').click()
                assert '英文' in editable.inner_text()
                panel.locator('[data-close]').click()
                page.wait_for_timeout(600)
                current = client.get(f'/api/resume-documents/{document_id}').json()
                assert '英文' in current['document']['sections'][0]['items'][0]['content']

                editable.focus()
                page.keyboard.press('Meta+a')
                assert page.evaluate('window.getSelection().toString()') == editable.inner_text()
                assert '专业技能' not in page.evaluate('window.getSelection().toString()')
                page.keyboard.press('ArrowLeft')
                editable.evaluate("""el => {
                  let node=el.firstChild, range=document.createRange();
                  range.setStart(node,0); range.setEnd(node,2);
                  let selection=window.getSelection();
                  selection.removeAllRanges(); selection.addRange(range);
                }""")
                page.keyboard.press('Meta+b')
                assert editable.locator('b,strong').count() >= 1
                page.keyboard.press('Meta+ArrowRight')
                assert editable.evaluate('el => el.style.textAlign') == 'right'
                page.keyboard.press('Meta+z')
                assert editable.evaluate('el => el.style.textAlign') != 'right'
                page.keyboard.press('Meta+Shift+z')
                assert editable.evaluate('el => el.style.textAlign') == 'right'

                page.context.grant_permissions(['clipboard-read', 'clipboard-write'],
                                               origin=f'http://127.0.0.1:{port}')
                page.evaluate("navigator.clipboard.writeText('虚构剪贴板')")
                editable.evaluate("""el => {
                  el.focus(); let node=el.lastChild, range=document.createRange();
                  range.setStart(node,node.length); range.collapse(true);
                  let selection=window.getSelection();
                  selection.removeAllRanges(); selection.addRange(range);
                }""")
                page.keyboard.press('Meta+v')
                assert '虚构剪贴板' in editable.inner_text()
                editable.evaluate("""el => {
                  let node=[...el.childNodes].find(n=>n.nodeType===Node.TEXT_NODE && n.data.includes('虚构剪贴板'));
                  let start=node.data.indexOf('虚构剪贴板'), range=document.createRange();
                  range.setStart(node,start); range.setEnd(node,start+5);
                  let selection=window.getSelection();
                  selection.removeAllRanges(); selection.addRange(range);
                }""")
                page.keyboard.press('Meta+c')
                assert page.evaluate('navigator.clipboard.readText()') == '虚构剪贴板'
                page.keyboard.press('Meta+x')
                assert '虚构剪贴板' not in editable.inner_text()
                page.keyboard.press('Meta+z')
                assert '虚构剪贴板' in editable.inner_text()

                for shortcut, expected in (
                    ('Meta+Shift+ArrowLeft', '第二行'),
                    ('Meta+Shift+ArrowRight', ' xyz'),
                ):
                    editable.evaluate("""el => {
                      el.innerHTML='第一行 abc<br>第二行 xyz'; el.focus();
                      let node=el.childNodes[2], range=document.createRange();
                      range.setStart(node,3); range.collapse(true);
                      let selection=window.getSelection();
                      selection.removeAllRanges(); selection.addRange(range);
                    }""")
                    page.keyboard.press(shortcut)
                    assert page.evaluate('window.getSelection().toString()') == expected
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(10)
