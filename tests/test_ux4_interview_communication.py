"""UX-4 phase transitions preserve communication and interview history."""
import pytest

from test_communication import setup_submitted, create
from test_interview import confirm
from test_offer import record


@pytest.mark.parametrize('phase', ['submitted', 'interview', 'offer'])
def test_general_communication_continues_without_changing_opportunity(tmp_path, phase):
    client, _, opportunity = setup_submitted(tmp_path)
    if phase in {'interview', 'offer'}:
        opportunity = confirm(client, opportunity).json()['opportunity']
    if phase == 'offer':
        opportunity = record(client, opportunity).json()['opportunity']
    prefix = f"/api/opportunities/{opportunity['id']}"
    before = client.get(prefix).json()
    offer_before = client.get(prefix + '/offer').json() if phase == 'offer' else None
    response = create(client, opportunity, key='continued-general', content='虚构后续招聘沟通')
    assert response.status_code == 200, response.text
    event = response.json()
    assert event['purpose'] == 'general'
    assert client.get(prefix).json() == before
    if phase == 'offer':
        assert client.get(prefix + '/offer').json() == offer_before
    assert create(client, opportunity, key='continued-general', content='虚构后续招聘沟通').json()['id'] == event['id']


def test_ended_history_and_corrections_do_not_reopen_the_process(tmp_path):
    client, _, opportunity = setup_submitted(tmp_path)
    event = create(client, opportunity).json()
    created = confirm(client, opportunity).json()
    opportunity, interview = created['opportunity'], created['interview']
    prefix = f"/api/opportunities/{opportunity['id']}"
    ended = client.post(prefix + '/end', json={
        'result': 'withdrawn', 'expected_revision': opportunity['revision'], 'idempotency_key': 'end',
    }).json()
    ip = prefix + f"/interviews/{interview['id']}"
    assert client.get(ip).status_code == 200
    assert client.get(prefix + f"/communications/{event['id']}").status_code == 200
    assert create(client, ended, key='ended-new').status_code == 409
    assert confirm(client, ended, key='ended-interview').status_code == 409
    assert client.post(ip + '/pending', json={
        'expected_revision': interview['revision'], 'idempotency_key': 'ended-status',
    }).status_code == 409
    assert client.post(ip + '/simulations', json={
        'selected_review_ids': [], 'communication_ids': [], 'wiki_ids': [], 'idempotency_key': 'ended-simulation',
    }).status_code == 409
    assert client.put(prefix + f"/communications/{event['id']}", json={
        'type': 'text', 'occurred_on': '2026-09-29', 'content': '虚构历史更正',
        'expected_revision': event['revision'], 'idempotency_key': 'correct-communication',
    }).status_code == 200
    assert client.put(ip + '/raw', json={
        'content': '虚构面试文字稿更正', 'expected_revision': 0, 'idempotency_key': 'correct-raw',
    }).status_code == 200
    assert client.put(ip + '/final-review', json={
        'summary': '虚构终版复盘更正', 'key_qa': [], 'patterns': [], 'discoveries': [], 'next_actions': [],
        'expected_revision': 0, 'idempotency_key': 'correct-review',
    }).status_code == 200
    assert client.get(prefix).json() == ended


def test_ended_interview_browser_keeps_corrections_but_hides_progression(tmp_path):
    """Use the same browser bundle and HTTP routes as a historical Timeline entry."""
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path
    import uvicorn
    from playwright.sync_api import sync_playwright
    from workbench.app import create_app

    client, store, opportunity = setup_submitted(tmp_path / 'data')
    created = confirm(client, opportunity).json()
    opportunity, interview = created['opportunity'], created['interview']
    prefix = f"/api/opportunities/{opportunity['id']}"
    assert client.post(prefix + '/end', json={
        'result': 'withdrawn', 'expected_revision': opportunity['revision'], 'idempotency_key': 'end',
    }).status_code == 200
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    subprocess.run([str(frontend / 'node_modules/.bin/vite'), 'build', '--outDir', str(tmp_path / 'dist')],
                   cwd=frontend, check=True, capture_output=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(store, frontend_dir=tmp_path / 'dist'),
                                          host='127.0.0.1', port=port, log_level='error'))
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
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/#opportunities/{opportunity['id']}", wait_until='networkidle')
                page.locator(f'[data-interview="{interview["id"]}"]').first.click()
                dialog = page.locator('dialog')
                dialog.wait_for()
                assert dialog.locator('[data-prep]').count() == 1, dialog.inner_text()
                assert dialog.locator('[data-raw], [data-review]').count() == 2
                assert dialog.locator('[data-schedule], [data-pending], [data-complete], [data-cancel]').count() == 0
                assert dialog.locator('[data-simulation]').count() == 0
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(10)
