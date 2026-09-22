"""User-owned model configuration and safe secret/destination binding."""

import json
from urllib.parse import urlsplit

from .core import Conflict, Invalid, Missing, digest, now, required, uid
from .secret_store import SecretStoreError
from .runtime_mode import require_ai_enabled, require_secret_maintenance


SECRET_OPERATION_KIND = "ai_secret_operation"
SECRET_STATUSES = {
    "not_checked", "ready", "missing", "denied", "locked",
    "interaction_not_allowed", "timeout", "error",
}
CLEANUP_POLICY_AUTOMATIC = "automatic"
CLEANUP_POLICY_MANUAL = "manual_cleanup_required"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_PORTS = {"https": 443, "http": 80}


def _strict(body, fields):
    if not isinstance(body, dict) or set(body) - set(fields):
        raise Invalid("模型配置包含不允许的字段")


def _text(value, label, limit=1000, optional=False):
    if optional and value in (None, ""):
        return ""
    return required(value, label, limit)


def canonical_model(provider, model):
    """Normalize provider aliases before they reach the remote API."""
    if provider.strip().casefold() == "deepseek" and model.strip().casefold() == "deepseek-v4.1-flash":
        return "deepseek-flash"
    return model


def normalize_destination(provider, base_url):
    """Validate and normalize the one destination identity used everywhere.

    Query strings, fragments and userinfo are never part of an AI destination.
    External HTTP is rejected; loopback HTTP remains available for explicitly
    configured local fake providers.
    """
    provider_value = _text(provider, "供应商", 100)
    url_value = _text(base_url, "Base URL", 2000)
    parsed = urlsplit(url_value)
    scheme = parsed.scheme.casefold()
    if scheme not in ("https", "http") or not parsed.netloc:
        raise Invalid("Base URL 必须是有效的 HTTPS URL 或本地 HTTP URL")
    if parsed.username is not None or parsed.password is not None:
        raise Invalid("Base URL 不允许包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise Invalid("Base URL 不允许包含 query 或 fragment")
    hostname = parsed.hostname
    if not hostname:
        raise Invalid("Base URL 缺少主机名")
    hostname = hostname.casefold()
    if scheme == "http" and hostname not in LOOPBACK_HOSTS:
        raise Invalid("Base URL 仅允许 HTTPS；HTTP 只能用于显式 loopback")
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise Invalid("Base URL 端口无效") from exc
    port = parsed_port or DEFAULT_PORTS[scheme]
    path = parsed.path or ""
    if path != "/":
        path = path.rstrip("/")
    host_for_url = "[" + hostname + "]" if ":" in hostname else hostname
    port_suffix = "" if port == DEFAULT_PORTS[scheme] else ":" + str(port)
    normalized_url = f"{scheme}://{host_for_url}{port_suffix}{path}"
    return {
        "provider": provider_value,
        "provider_key": provider_value.casefold(),
        "scheme": scheme,
        "host": hostname,
        "port": port,
        "base_path": path or "/",
        "normalized_url": normalized_url,
    }


def _config(store, c, config_id):
    return store._get(c, config_id, "ai_model_config")


def _public(config, runtime_status=None):
    ref = config.get("api_key_ref")
    status = runtime_status or config.get("secret_status")
    if status not in SECRET_STATUSES:
        status = "not_checked" if ref else "error"
    return {
        "id": config["id"], "display_name": config["display_name"],
        "provider": config["provider"], "base_url": config["base_url"],
        "model": config["model"], "enabled": config["enabled"],
        "created_at": config["created_at"], "updated_at": config["updated_at"],
        "revision": config.get("revision", 0),
        "configured_ref": bool(ref),
        "secret_status": status,
        # Keep the old display field for existing clients, without returning
        # the opaque reference itself or probing the Keychain during listing.
        "api_key_set": bool(ref), "api_key_masked": "••••••••" if ref else "",
        "cleanup_pending": bool(config.get("secret_cleanup_pending")),
        "cleanup_state": config.get("secret_cleanup_state"),
    }


def settings(store, c=None):
    owned = c is None
    if owned:
        ctx = store.connect(False)
        c = ctx.__enter__()
    try:
        configs = [
            _public(x, store.runtime_secret_status(x["id"]))
            for x in store._current(c, "ai_model_config")
        ]
        row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
        value = json.loads(row[0]) if row else {"default_model_config_id": None}
        default = value.get("default_model_config_id")
        if default and not any(x["id"] == default and x["enabled"] for x in configs):
            default = None
        return {"configs": configs, "default_model_config_id": default}
    finally:
        if owned:
            ctx.__exit__(None, None, None)


def _save_settings(store, c, default_id):
    row = c.execute("SELECT revision,body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
    old = json.loads(row[1]) if row else {"id": "ai-settings", "default_model_config_id": None}
    expected = row[0] if row else 0
    store._save(c, "ai_settings", {
        **old, "id": "ai-settings", "default_model_config_id": default_id,
    }, expected)


def _journal_body(
    operation_id,
    config_id,
    expected_revision,
    old_ref,
    new_ref,
    phase,
    error_code=None,
    cleanup_policy=CLEANUP_POLICY_AUTOMATIC,
):
    timestamp = now()
    return {
        "id": "ai-secret-operation:" + operation_id,
        "operation_id": operation_id,
        "config_id": config_id,
        "expected_revision": expected_revision,
        "old_ref": old_ref,
        "new_ref": new_ref,
        "phase": phase,
        "created_at": timestamp,
        "updated_at": timestamp,
        "error_code": error_code,
        "cleanup_policy": cleanup_policy,
    }


def _journal_update(store, operation_id, **changes):
    with store.connect() as c:
        row = c.execute(
            "SELECT body FROM records WHERE id=? AND kind=?",
            ("ai-secret-operation:" + operation_id, SECRET_OPERATION_KIND),
        ).fetchone()
        if not row:
            return None
        operation = json.loads(row[0])
        operation.update(changes)
        operation["updated_at"] = now()
        store._record(c, SECRET_OPERATION_KIND, operation)
        return operation


def _journal_in(c, store, operation):
    store._record(c, SECRET_OPERATION_KIND, operation)


def _new_ref(store):
    ref = store.secret_store_for_maintenance().allocate_ref()
    if not isinstance(ref, str) or not ref:
        raise Invalid("SecretStore 未返回有效的秘密引用")
    return ref


def _cleanup_ref(store, ref):
    if not ref:
        return None
    try:
        store.secret_store_for_maintenance().delete(ref)
        return None
    except SecretStoreError as exc:
        return exc
    except Exception as exc:
        return SecretStoreError("error", "无法清理模型配置的秘密引用")


def _ref_is_current(store, ref):
    if not ref:
        return False
    with store.connect(False) as c:
        return any(config.get("api_key_ref") == ref for config in store._current(c, "ai_model_config"))


def _mark_cleanup(store, operation_id, error):
    changes = {
        "phase": "cleanup_pending",
        "error_code": getattr(error, "code", "error"),
    }
    if getattr(error, "code", None) == CLEANUP_POLICY_MANUAL:
        changes["cleanup_state"] = CLEANUP_POLICY_MANUAL
    _journal_update(store, operation_id, **changes)


def _operation_holds_ref(store, operation_id, ref):
    with store.connect(False) as c:
        row = c.execute(
            "SELECT body FROM records WHERE id=? AND kind=?",
            ("ai-secret-operation:" + operation_id, SECRET_OPERATION_KIND),
        ).fetchone()
    if not row:
        return False
    operation = json.loads(row[0])
    return (
        operation.get("old_ref") == ref
        and operation.get("cleanup_policy") == CLEANUP_POLICY_MANUAL
    )


def _finish_cleanup(store, operation_id, ref, error_code=None):
    if _operation_holds_ref(store, operation_id, ref):
        held = SecretStoreError(
            CLEANUP_POLICY_MANUAL,
            "该旧 Secret 引用需要人工清理",
        )
        _mark_cleanup(store, operation_id, held)
        return held
    error = _cleanup_ref(store, ref)
    if error:
        _mark_cleanup(store, operation_id, error)
        return error
    _journal_update(store, operation_id, phase="cleaned", error_code=error_code)
    return None


def _write_and_verify_secret(store, operation_id, new_ref, key):
    """Write a new ref, then verify it with the bounded SecretStore read path."""

    maintenance_store = store.secret_store_for_maintenance()
    try:
        maintenance_store.put(new_ref, key)
    except SecretStoreError as exc:
        _journal_update(store, operation_id, phase="write_failed", error_code=exc.code)
        return exc
    except Exception:
        error = SecretStoreError("error", "无法写入模型配置的 API Key")
        _journal_update(store, operation_id, phase="write_failed", error_code=error.code)
        return error
    _journal_update(store, operation_id, phase="secret_written", error_code=None)

    try:
        read_back = maintenance_store.get(new_ref)
    except SecretStoreError as exc:
        _journal_update(store, operation_id, phase="verification_failed", error_code=exc.code)
        return exc
    except Exception:
        error = SecretStoreError("error", "无法验证模型配置的 API Key")
        _journal_update(store, operation_id, phase="verification_failed", error_code=error.code)
        return error
    if read_back != key:
        error = SecretStoreError("error", "新 API Key 的读取验证失败")
        _journal_update(store, operation_id, phase="verification_failed", error_code=error.code)
        return error
    _journal_update(store, operation_id, phase="secret_verified", error_code=None)
    return None


def _validated_input(body, current=None):
    provider = _text(body.get("provider", current.get("provider") if current else None), "供应商", 100)
    destination = normalize_destination(provider, _text(body.get("base_url", current.get("base_url") if current else None), "Base URL", 2000))
    model = canonical_model(provider, _text(body.get("model", current.get("model") if current else None), "模型名称", 500))
    display = _text(body.get("display_name", current.get("display_name") if current else None), "显示名称", 200)
    enabled = body.get("enabled", current.get("enabled") if current else True)
    if type(enabled) is not bool:
        raise Invalid("enabled 必须是布尔值")
    return display, provider, destination, model, enabled


def _save_new_config(store, c, config):
    c.execute("INSERT INTO current VALUES(?,?,?,?)", (config["id"], "ai_model_config", 0, store_dump(config)))


def create(store, body):
    require_secret_maintenance(store.runtime_mode)
    _strict(body, {"display_name", "provider", "base_url", "model", "api_key", "enabled"})
    display, provider, destination, model, enabled = _validated_input(body)
    key = _text(body.get("api_key"), "API Key", 10000)
    config_id = "model-config:" + uid()
    operation_id = uid()
    new_ref = _new_ref(store)
    config = {
        "id": config_id, "display_name": display, "provider": provider,
        "base_url": destination["normalized_url"], "destination_binding": destination,
        "model": model, "api_key_ref": None, "secret_status": "not_checked",
        "enabled": enabled, "created_at": now(), "updated_at": now(),
    }
    operation = _journal_body(operation_id, config_id, 0, None, new_ref, "intent")
    with store.connect() as c:
        _save_new_config(store, c, config)
        _journal_in(c, store, operation)
    secret_error = _write_and_verify_secret(store, operation_id, new_ref, key)
    if secret_error:
        cleanup_error = _finish_cleanup(store, operation_id, new_ref, error_code=secret_error.code)
        with store.connect() as c:
            current = _config(store, c, config_id)
            if cleanup_error:
                current.update(enabled=False, secret_status="error", secret_cleanup_pending=True)
                store._save(c, "ai_model_config", current, c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()[0])
            else:
                c.execute("DELETE FROM current WHERE id=?", (config_id,))
        raise Invalid("无法保存 API Key，请检查秘密存储权限") from secret_error
    try:
        with store.connect() as c:
            current = _config(store, c, config_id)
            row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
            if not row or row[0] != 0:
                raise Conflict("模型配置已更新，请重新载入")
            current["api_key_ref"] = new_ref
            current["secret_status"] = "ready"
            saved = store._save(c, "ai_model_config", current, 0)
            settings_row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
            current_settings = json.loads(settings_row[0]) if settings_row else {"default_model_config_id": None}
            if saved["enabled"] and not current_settings.get("default_model_config_id"):
                _save_settings(store, c, saved["id"])
            _journal_in(c, store, {**operation, "phase": "switched", "updated_at": now()})
    except Exception as exc:
        _journal_update(store, operation_id, phase="switch_failed", error_code=getattr(exc, "code", "error"))
        cleanup_error = _finish_cleanup(store, operation_id, new_ref, error_code=getattr(exc, "code", "error"))
        if cleanup_error:
            with store.connect() as c:
                current = _config(store, c, config_id)
                current.update(enabled=False, secret_status="error", secret_cleanup_pending=True)
                row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
                store._save(c, "ai_model_config", current, row[0])
            raise Invalid("模型配置保存失败，秘密清理待处理") from exc
        with store.connect() as c:
            c.execute("DELETE FROM current WHERE id=?", (config_id,))
        raise Invalid("模型配置保存失败，未切换当前配置") from exc
    _journal_update(store, operation_id, phase="cleaned", error_code=None)
    store.set_runtime_secret_status(saved["id"], "ready")
    return _public(saved, store.runtime_secret_status(saved["id"]))


def _load_update(store, config_id, body):
    with store.connect(False) as c:
        current = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        expected = body.get("expected_revision")
        if type(expected) is not int or not row or expected != row[0]:
            raise Conflict("模型配置已更新，请重新载入")
    return current, expected


def update(store, config_id, body):
    require_secret_maintenance(store.runtime_mode)
    _strict(body, {"display_name", "provider", "base_url", "model", "api_key", "enabled", "expected_revision"})
    current, expected = _load_update(store, config_id, body)
    display, provider, destination, model, enabled = _validated_input(body, current)
    updated = dict(current)
    updated.update({
        "display_name": display, "provider": provider,
        "base_url": destination["normalized_url"], "destination_binding": destination,
        "model": model, "enabled": enabled, "updated_at": now(),
    })
    old_binding = current.get("destination_binding") or normalize_destination(current["provider"], current["base_url"])
    destination_changed = {
        key: old_binding.get(key) for key in ("provider_key", "scheme", "host", "port", "base_path")
    } != {
        key: destination.get(key) for key in ("provider_key", "scheme", "host", "port", "base_path")
    }
    new_key = body.get("api_key")
    has_new_key = new_key not in (None, "")
    if destination_changed and not has_new_key:
        raise Invalid("模型目的地已变化，必须重新录入 API Key；不会复用旧 Key")
    if not has_new_key:
        with store.connect() as c:
            latest = _config(store, c, config_id)
            row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
            if not row or row[0] != expected:
                raise Conflict("模型配置已更新，请重新载入")
            latest.update(updated)
            saved = store._save(c, "ai_model_config", latest, expected)
        return _public(saved, store.runtime_secret_status(saved["id"]))

    key = _text(new_key, "API Key", 10000)
    new_ref = _new_ref(store)
    operation_id = uid()
    cleanup_policy = current.get("secret_cleanup_policy", CLEANUP_POLICY_AUTOMATIC)
    operation = _journal_body(
        operation_id,
        config_id,
        expected,
        current.get("api_key_ref"),
        new_ref,
        "intent",
        cleanup_policy=cleanup_policy,
    )
    with store.connect() as c:
        latest = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        if not row or row[0] != expected:
            raise Conflict("模型配置已更新，请重新载入")
        _journal_in(c, store, operation)
    secret_error = _write_and_verify_secret(store, operation_id, new_ref, key)
    if secret_error:
        _finish_cleanup(store, operation_id, new_ref, error_code=secret_error.code)
        raise Invalid("无法保存 API Key，请检查秘密存储权限") from secret_error
    try:
        with store.connect() as c:
            latest = _config(store, c, config_id)
            row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
            if not row or row[0] != expected:
                raise Conflict("模型配置已更新，请重新载入")
            latest.update(updated)
            latest["api_key_ref"] = new_ref
            latest["secret_status"] = "ready"
            latest.pop("secret_cleanup_policy", None)
            if cleanup_policy == CLEANUP_POLICY_MANUAL:
                latest["secret_cleanup_pending"] = True
                latest["secret_cleanup_state"] = CLEANUP_POLICY_MANUAL
            elif latest.get("secret_cleanup_state") != CLEANUP_POLICY_MANUAL:
                latest.pop("secret_cleanup_pending", None)
            saved = store._save(c, "ai_model_config", latest, expected)
            _journal_in(c, store, {**operation, "phase": "switched", "updated_at": now()})
    except Exception as exc:
        _journal_update(store, operation_id, phase="switch_failed", error_code=getattr(exc, "code", "error"))
        cleanup_error = _finish_cleanup(store, operation_id, new_ref, error_code=getattr(exc, "code", "error"))
        if cleanup_error:
            _mark_cleanup(store, operation_id, cleanup_error)
            raise Invalid("模型配置保存失败，秘密清理待处理") from exc
        if isinstance(exc, Conflict):
            raise
        raise Invalid("模型配置保存失败，未切换当前配置") from exc
    old_ref = current.get("api_key_ref")
    if old_ref and not _ref_is_current(store, old_ref):
        cleanup_error = _finish_cleanup(store, operation_id, old_ref)
        if cleanup_error:
            with store.connect() as c:
                latest = _config(store, c, config_id)
                latest["secret_cleanup_pending"] = True
                row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
                store._save(c, "ai_model_config", latest, row[0])
            store.set_runtime_secret_status(saved["id"], "ready")
            return _public(
                {**saved, "secret_cleanup_pending": True},
                store.runtime_secret_status(saved["id"]),
            )
    else:
        _journal_update(store, operation_id, phase="cleaned", error_code=None)
    store.set_runtime_secret_status(saved["id"], "ready")
    return _public(saved, store.runtime_secret_status(saved["id"]))


def mark_cleanup_hold(store, config_id, body):
    """Mark the current opaque ref as manual-only cleanup without touching it."""

    require_secret_maintenance(store.runtime_mode)
    _strict(body, {"expected_revision"})
    with store.connect() as c:
        current = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        expected = body.get("expected_revision")
        if type(expected) is not int or not row or expected != row[0]:
            raise Conflict("模型配置已更新，请重新载入")
        if not current.get("api_key_ref"):
            raise Invalid("当前模型没有可保留的 Secret 引用")
        current["secret_cleanup_policy"] = CLEANUP_POLICY_MANUAL
        current["secret_cleanup_pending"] = True
        current["secret_cleanup_state"] = CLEANUP_POLICY_MANUAL
        saved = store._save(c, "ai_model_config", current, expected)
    return _public(saved, store.runtime_secret_status(saved["id"]))


def delete(store, config_id, confirm=False):
    require_ai_enabled(store.runtime_mode)
    if confirm is not True:
        raise Invalid("删除模型配置需要明确确认")
    operation_id = uid()
    with store.connect() as c:
        current = _config(store, c, config_id)
        settings_row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
        setting = json.loads(settings_row[0]) if settings_row else {"default_model_config_id": None}
        if setting.get("default_model_config_id") == config_id:
            _save_settings(store, c, None)
        operation = _journal_body(
            operation_id, config_id, c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()[0],
            current.get("api_key_ref"), None, "delete_intent",
            cleanup_policy=current.get("secret_cleanup_policy", CLEANUP_POLICY_AUTOMATIC),
        )
        c.execute("DELETE FROM current WHERE id=?", (config_id,))
        _journal_in(c, store, operation)
    old_ref = current.get("api_key_ref")
    if old_ref and not _ref_is_current(store, old_ref):
        cleanup_error = _finish_cleanup(store, operation_id, old_ref)
        if cleanup_error:
            raise Invalid("模型配置已删除，但秘密清理待处理") from cleanup_error
    else:
        _journal_update(store, operation_id, phase="cleaned", error_code=None)
    return {"deleted": config_id, "default_model_config_id": None if setting.get("default_model_config_id") == config_id else setting.get("default_model_config_id")}


def set_default(store, config_id, body):
    require_ai_enabled(store.runtime_mode)
    _strict(body, {"expected_revision"})
    with store.connect() as c:
        config = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        if body.get("expected_revision") != row[0]:
            raise Conflict("模型配置已更新，请重新载入")
        if not config.get("enabled"):
            raise Invalid("只有启用的模型配置可以设为默认")
        _save_settings(store, c, config_id)
        return settings(store, c)


def clear_default(store):
    require_ai_enabled(store.runtime_mode)
    with store.connect() as c:
        _save_settings(store, c, None)
        return settings(store, c)


def test_ephemeral(store, body):
    """Test an unsaved form without creating a ModelConfig or storing its key."""
    require_ai_enabled(store.runtime_mode)
    _strict(body, {"provider", "base_url", "model", "api_key"})
    provider = _text(body.get("provider"), "供应商", 100)
    destination = normalize_destination(provider, _text(body.get("base_url"), "Base URL", 2000))
    config = {
        "provider": provider,
        "base_url": destination["normalized_url"],
        "destination_binding": destination,
        "model": canonical_model(provider, _text(body.get("model"), "模型名称", 500)),
    }
    key = _text(body.get("api_key"), "API Key", 10000)
    from .model_gateway import OpenAICompatibleAdapter, GatewayError
    from . import outbound_policy
    target = {"kind": "connection_test", "id": "connection-test:" + digest({
        "provider": config["provider"], "base_url": config["base_url"], "model": config["model"],
    })}
    try:
        adapter = OpenAICompatibleAdapter(config, key, store.runtime_mode)
        try:
            outbound_policy.audit(store, task_type="connection_test", target=target,
                                  event="dispatched", payload_hash=digest({
                                      "model": config["model"], "fixed_test": True,
                                  }), details={"provider": config["provider"]})
        except Exception:
            pass
        adapter.test()
        try:
            outbound_policy.audit(store, task_type="connection_test", target=target,
                                  event="response_received", payload_hash=digest({
                                      "model": config["model"], "fixed_test": True,
                                  }), details={"status": "success"})
        except Exception:
            pass
        return {"status": "success", "code": "success", "model": config["model"]}
    except GatewayError as exc:
        try:
            outbound_policy.audit(store, task_type="connection_test", target=target,
                                  event="failed", details={"code": exc.code})
        except Exception:
            pass
        return {"status": "failed", "code": exc.code, "message": str(exc), "model": config["model"]}


def selected(store, c, config_id=None):
    if config_id:
        config = _config(store, c, config_id)
    else:
        row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
        value = json.loads(row[0]) if row else {}
        config = _config(store, c, value.get("default_model_config_id")) if value.get("default_model_config_id") else None
    if config and (not config.get("enabled") or not config.get("api_key_ref")):
        raise Invalid("默认 AI 模型未启用或缺少 API Key")
    return config


def secret(store, config):
    require_ai_enabled(store.runtime_mode)
    try:
        return store.secret_store.get(config["api_key_ref"])
    except SecretStoreError:
        raise
    except Exception as exc:
        raise SecretStoreError("error", "无法读取模型配置的 API Key") from exc


def mark_secret_status(store, config_id, status):
    if status not in {"missing", "denied", "locked", "interaction_not_allowed", "timeout", "error"}:
        status = "error"
    store.set_runtime_secret_status(config_id, status)
    try:
        with store.connect() as c:
            config = _config(store, c, config_id)
            row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
            config["secret_status"] = status
            store._save(c, "ai_model_config", config, row[0])
    except Exception:
        # Status reporting must not hide the original safe secret-store error.
        return


def recover_secret_operations(store):
    """Reconcile only journal-known refs, outside the startup DB transaction."""
    if not (
        store.runtime_mode.ai_enabled
        or (store.runtime_mode.local_only and store.runtime_mode.valid)
    ):
        return
    with store.connect(False) as c:
        operations = store._records(c, SECRET_OPERATION_KIND)
        current = store._current(c, "ai_model_config")
    current_refs = {item.get("api_key_ref") for item in current if item.get("api_key_ref")}
    for operation in operations:
        if operation.get("phase") == "cleaned":
            continue
        new_ref = operation.get("new_ref")
        old_ref = operation.get("old_ref")
        active = any(item.get("id") == operation.get("config_id") and item.get("api_key_ref") == new_ref for item in current)
        if active:
            target = old_ref if old_ref and old_ref not in current_refs else None
        else:
            target = new_ref or old_ref
        if not target:
            _journal_update(store, operation["operation_id"], phase="cleaned", error_code=None)
            continue
        if (
            target == old_ref
            and operation.get("cleanup_policy") == CLEANUP_POLICY_MANUAL
        ):
            _mark_cleanup(
                store,
                operation["operation_id"],
                SecretStoreError(
                    CLEANUP_POLICY_MANUAL,
                    "该旧 Secret 引用需要人工清理",
                ),
            )
            continue
        error = _cleanup_ref(store, target)
        if error:
            _mark_cleanup(store, operation["operation_id"], error)
        else:
            if not active and not old_ref:
                # This is an interrupted create before its first config
                # switch. It is safe to remove only this operation's pending
                # row; an update operation always has an old_ref and keeps
                # the prior config intact.
                with store.connect() as c:
                    row = c.execute("SELECT body FROM current WHERE id=? AND kind='ai_model_config'", (operation["config_id"],)).fetchone()
                    if row and not json.loads(row[0]).get("api_key_ref"):
                        c.execute("DELETE FROM current WHERE id=?", (operation["config_id"],))
            _journal_update(store, operation["operation_id"], phase="cleaned", error_code=None)


def store_dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
