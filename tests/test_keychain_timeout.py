from __future__ import annotations

import platform
import secrets
import sys
import threading
import time
from pathlib import Path

import pytest

from workbench.secret_store import KeychainSecretStore, SecretStoreError
from workbench.secret_store_helper import classify_keychain_exception


HELPER = Path(__file__).with_name("keychain_helper_probe.py")


def _store(timeout=0.4):
    return KeychainSecretStore(
        platform_name="Darwin",
        helper_timeout_seconds=timeout,
        helper_command=[sys.executable, str(HELPER)],
    )


def test_helper_timeout_terminates_helper_and_never_falls_back(monkeypatch):
    fake_secret = secrets.token_urlsafe(24)
    monkeypatch.setenv("CAREER_FAKE_SECRET", fake_secret)
    store = _store(timeout=0.2)
    termination_observations = []
    original_terminate = store._terminate_helper

    def observe_termination(process):
        confirmed = original_terminate(process)
        termination_observations.append((confirmed, process.poll()))
        return confirmed

    store._terminate_helper = observe_termination

    started = time.monotonic()
    with pytest.raises(SecretStoreError) as error:
        store.get("hang")

    assert error.value.code == "timeout"
    assert time.monotonic() - started < 2
    assert termination_observations and all(
        confirmed and returncode is not None
        for confirmed, returncode in termination_observations
    )
    assert not store._active_helpers


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        ("missing", "missing"),
        ("denied", "denied"),
        ("locked", "locked"),
        ("interaction", "interaction_not_allowed"),
    ],
)
def test_helper_error_classification(account, expected):
    with pytest.raises(SecretStoreError) as error:
        _store().get(account)
    assert error.value.code == expected


@pytest.mark.parametrize(
    ("native_status", "expected"),
    [
        (-25300, "missing"),
        (-128, "denied"),
        (-25293, "denied"),
        (-67030, "denied"),
        (-25308, "interaction_not_allowed"),
    ],
)
def test_native_keychain_status_classification(native_status, expected):
    class NativeError(Exception):
        pass

    assert classify_keychain_exception(NativeError(native_status)) == expected


def test_helper_crash_and_malformed_response_fail_closed():
    for account in ("crash", "malformed"):
        with pytest.raises(SecretStoreError) as error:
            _store().get(account)
        assert error.value.code == "error"


def test_put_get_delete_and_ipc_do_not_expose_secret(monkeypatch, capsys):
    fake_secret = secrets.token_urlsafe(24)
    monkeypatch.setenv("CAREER_FAKE_SECRET", fake_secret)
    store = _store()

    assert store.put("inspect", fake_secret) == "inspect"
    value = store.get("inspect")
    assert value == "helper-secret"
    assert store.delete("inspect") is None
    captured = capsys.readouterr()
    assert fake_secret not in captured.out
    assert fake_secret not in captured.err

    # The helper only sees the request over the private socketpair.
    result = store._run_helper("get", "inspect", fake_secret)
    assert result["status"] == "ok"
    assert result["argv_has_secret"] is False
    assert result["environment_has_secret"] is False
    assert fake_secret not in str(store._helper_command)
    assert not store._active_helpers


def test_delete_missing_is_idempotent_and_shutdown_leaves_no_helpers():
    assert _store().delete("missing") is None


def test_concurrent_reads_leave_no_zombie_helpers():
    store = _store(timeout=1.0)
    results = []

    def read():
        results.append(store.get("ok"))

    threads = [threading.Thread(target=read) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert results == ["helper-secret"] * 6
    assert not store._active_helpers


def test_shutdown_terminates_active_helper():
    store = _store(timeout=10.0)
    result = []

    def read():
        try:
            store.get("hang")
        except SecretStoreError as error:
            result.append(error.code)

    thread = threading.Thread(target=read)
    thread.start()
    started = time.monotonic()
    while not store._active_helpers and time.monotonic() - started < 1.0:
        time.sleep(0.01)
    store.shutdown()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result and result[0] == "error"
    assert not store._active_helpers


@pytest.mark.skipif(platform.system() != "Darwin", reason="requires the real macOS Keychain")
def test_real_macos_fake_item_put_get_delete_is_bounded():
    store = KeychainSecretStore(helper_timeout_seconds=2.0)
    ref = store.allocate_ref()
    fake_secret = secrets.token_urlsafe(32)
    timings = {}
    try:
        for operation in ("put", "get"):
            started = time.monotonic()
            if operation == "put":
                assert store.put(ref, fake_secret) == ref
            else:
                assert store.get(ref) == fake_secret
            timings[operation] = time.monotonic() - started
            assert timings[operation] < 2.0
    finally:
        started = time.monotonic()
        store.delete(ref)
        timings["delete"] = time.monotonic() - started
        assert timings["delete"] < 2.0
        with pytest.raises(SecretStoreError) as missing:
            store.get(ref)
        assert missing.value.code == "missing"
