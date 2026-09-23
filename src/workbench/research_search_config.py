"""Tavily credentials are a separate, Keychain-backed Research setting."""

import json

from .core import Conflict, Invalid, now, uid
from .runtime_mode import require_secret_maintenance
from .secret_store import SecretStoreError


CONFIG_ID = "research-search-provider"
CONFIG_KIND = "research_search_provider"
OPERATION_KIND = "research_search_secret_operation"
SECRET_STATUSES = {
    "not_configured", "not_checked", "ready", "missing", "denied",
    "locked", "interaction_not_allowed", "timeout", "error",
}


def _public(store, c=None):
    if c is None:
        with store.connect(False) as connection:
            return _public(store, connection)
    row = c.execute(
        "SELECT revision,body FROM current WHERE id=? AND kind=?",
        (CONFIG_ID, CONFIG_KIND),
    ).fetchone()
    configured = bool(row and json.loads(row[1]).get("secret_ref"))
    revision = row[0] if row else 0
    status = store.runtime_search_secret_status()
    if not configured and status in {"not_configured", "not_checked", None}:
        status = "not_configured"
    elif status not in SECRET_STATUSES:
        status = "error"
    return {
        "provider": "tavily",
        "configured": configured,
        "secret_status": status,
        "revision": revision,
    }


def settings(store, c=None):
    return _public(store, c)


def configured_ref_for_search(store):
    """Internal dispatch-only ref lookup; public settings never return refs."""
    with store.connect(False) as c:
        config, _ = _read_config(c)
        return config.get("secret_ref")


def _read_config(c):
    row = c.execute(
        "SELECT revision,body FROM current WHERE id=? AND kind=?",
        (CONFIG_ID, CONFIG_KIND),
    ).fetchone()
    return (json.loads(row[1]), row[0]) if row else ({"id": CONFIG_ID, "provider": "tavily", "secret_ref": None}, 0)


def _record_operation(store, operation):
    with store.connect() as c:
        store._record(c, OPERATION_KIND, operation)


def _update_operation(store, operation_id, **changes):
    with store.connect() as c:
        row = c.execute(
            "SELECT body FROM records WHERE id=? AND kind=?",
            ("tavily-secret-operation:" + operation_id, OPERATION_KIND),
        ).fetchone()
        if not row:
            return None
        operation = json.loads(row[0])
        operation.update(changes, updated_at=now())
        store._record(c, OPERATION_KIND, operation)
        return operation


def _is_current(store, ref):
    if not ref:
        return False
    with store.connect(False) as c:
        for kind in (CONFIG_KIND, "ai_model_config"):
            for row in c.execute("SELECT body FROM current WHERE kind=?", (kind,)):
                body = json.loads(row[0])
                if ref in {body.get("secret_ref"), body.get("api_key_ref")}:
                    return True
    return False


def _delete_unreferenced(store, ref):
    if not ref or _is_current(store, ref):
        return None
    try:
        store.secret_store_for_maintenance().delete(ref)
        return None
    except SecretStoreError as exc:
        return exc.code
    except Exception:
        return "error"


def _finish_operation(store, operation_id, ref, *, phase, error_code=None):
    cleanup_error = _delete_unreferenced(store, ref)
    _update_operation(
        store, operation_id,
        phase="cleanup_pending" if cleanup_error else phase,
        cleanup_ref=ref if cleanup_error else None,
        error_code=cleanup_error or error_code,
    )
    return cleanup_error


def _expected_revision(body):
    if not isinstance(body, dict) or set(body) - {"api_key", "expected_revision"}:
        raise Invalid("搜索 Provider 配置包含不允许的字段")
    expected = body.get("expected_revision")
    if type(expected) is not int or expected < 0:
        raise Invalid("搜索 Provider 配置版本不合法")
    return expected


def save(store, body):
    require_secret_maintenance(store.runtime_mode)
    expected = _expected_revision(body)
    api_key = body.get("api_key")
    if not isinstance(api_key, str) or not api_key or len(api_key) > 10000 or api_key.strip() != api_key:
        raise Invalid("Tavily API Key 不能为空或格式不合法")

    with store.connect(False) as c:
        current, revision = _read_config(c)
        if expected != revision:
            raise Conflict("搜索 Provider 配置已更新，请重新载入")
        current_ref = current.get("secret_ref")
        previous_runtime_status = store.runtime_search_secret_status()
        model_refs = {
            json.loads(row[0]).get("api_key_ref")
            for row in c.execute("SELECT body FROM current WHERE kind='ai_model_config'")
        }
    secret_store = store.secret_store_for_maintenance()
    new_ref = secret_store.allocate_ref()
    if not isinstance(new_ref, str) or not new_ref or new_ref == current_ref or new_ref in model_refs:
        raise Invalid("SecretStore 未返回独立的 Tavily Secret 引用")
    operation_id = uid()
    timestamp = now()
    operation = {
        "id": "tavily-secret-operation:" + operation_id,
        "operation_id": operation_id,
        "expected_revision": expected,
        "old_ref": current_ref,
        "new_ref": new_ref,
        "phase": "intent",
        "created_at": timestamp,
        "updated_at": timestamp,
        "error_code": None,
    }
    _record_operation(store, operation)

    try:
        written_ref = secret_store.put(new_ref, api_key)
        if written_ref != new_ref:
            raise SecretStoreError("error", "SecretStore 返回的引用不匹配")
        _update_operation(store, operation_id, phase="secret_written", error_code=None)
        read_back = secret_store.get(new_ref)
        if read_back != api_key:
            raise SecretStoreError("error", "SecretStore 读取验证失败")
        _update_operation(store, operation_id, phase="secret_verified", error_code=None)
    except SecretStoreError as exc:
        _finish_operation(store, operation_id, new_ref, phase="write_failed", error_code=exc.code)
        store.set_runtime_search_secret_status(exc.code if not current_ref else previous_runtime_status)
        raise Invalid("Tavily Secret 无法安全保存或验证") from None
    except Exception:
        _finish_operation(store, operation_id, new_ref, phase="write_failed", error_code="error")
        store.set_runtime_search_secret_status("error" if not current_ref else previous_runtime_status)
        raise Invalid("Tavily Secret 无法安全保存或验证") from None
    finally:
        # Drop the local reference as soon as validation finishes; it is never
        # passed to logs, persistence, subprocess arguments or environment.
        api_key = ""
        read_back = None

    try:
        with store.connect() as c:
            latest, latest_revision = _read_config(c)
            if latest_revision != expected:
                raise Conflict("搜索 Provider 配置已更新，请重新载入")
            saved = store._save(c, CONFIG_KIND, {
                **latest,
                "id": CONFIG_ID,
                "provider": "tavily",
                "secret_ref": new_ref,
            }, expected)
            switched = dict(operation, phase="switched", updated_at=now())
            store._record(c, OPERATION_KIND, switched)
    except Conflict:
        cleanup_error = _finish_operation(store, operation_id, new_ref, phase="cas_conflict", error_code="conflict")
        if not _public(store)["configured"]:
            store.set_runtime_search_secret_status("error" if cleanup_error else "not_configured")
        raise

    old_ref = current.get("secret_ref")
    if old_ref:
        cleanup_error = _finish_operation(store, operation_id, old_ref, phase="cleaned")
        if cleanup_error:
            store.set_runtime_search_secret_status("ready")
    else:
        _update_operation(store, operation_id, phase="cleaned", error_code=None)
    store.set_runtime_search_secret_status("ready")
    return _public(store)


def recover_secret_operations(store):
    """Recover only Tavily refs created by an unfinished local config save."""
    with store.connect(False) as c:
        operations = [
            json.loads(row[0])
            for row in c.execute("SELECT body FROM records WHERE kind=?", (OPERATION_KIND,))
        ]
    for operation in operations:
        if operation.get("phase") in {"cleaned", "cleanup_pending", "cas_conflict", "write_failed"}:
            if operation.get("phase") != "cleanup_pending":
                continue
        phase = operation.get("phase")
        operation_id = operation.get("operation_id")
        if phase in {"intent", "secret_written", "secret_verified"}:
            _finish_operation(
                store, operation_id, operation.get("new_ref"),
                phase="recovered_before_switch", error_code="process_interrupted",
            )
        elif phase in {"switched", "cleanup_pending"}:
            cleanup_ref = operation.get("cleanup_ref") or operation.get("old_ref")
            if cleanup_ref and not _is_current(store, cleanup_ref):
                _finish_operation(store, operation_id, cleanup_ref, phase="cleaned")
