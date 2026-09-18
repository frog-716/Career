"""User-owned model configuration and default selection.

Only opaque ``api_key_ref`` values are persisted.  DTOs intentionally expose
whether a key exists, never the reference or secret itself.
"""
from .core import Conflict, Invalid, Missing, digest, now, required, uid


def _strict(body, fields):
    if not isinstance(body, dict) or set(body) - set(fields):
        raise Invalid("模型配置包含不允许的字段")


def _text(value, label, limit=1000, optional=False):
    if optional and value in (None, ""):
        return ""
    return required(value, label, limit)


def _config(store, c, config_id):
    return store._get(c, config_id, "ai_model_config")


def _public(config, secret_store):
    ref = config.get("api_key_ref")
    return {
        "id": config["id"], "display_name": config["display_name"],
        "provider": config["provider"], "base_url": config["base_url"],
        "model": config["model"], "enabled": config["enabled"],
        "created_at": config["created_at"], "updated_at": config["updated_at"],
        "revision": config.get("revision", 0),
        "api_key_set": bool(ref), "api_key_masked": "••••••••" if ref else "",
    }


def settings(store, c=None):
    owned = c is None
    if owned:
        ctx = store.connect(False)
        c = ctx.__enter__()
    try:
        configs = [_public(x, store.secret_store) for x in store._current(c, "ai_model_config")]
        row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
        value = __import__("json").loads(row[0]) if row else {"default_model_config_id": None}
        default = value.get("default_model_config_id")
        if default and not any(x["id"] == default and x["enabled"] for x in configs):
            default = None
        return {"configs": configs, "default_model_config_id": default}
    finally:
        if owned:
            ctx.__exit__(None, None, None)


def _save_settings(store, c, default_id):
    row = c.execute("SELECT revision,body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
    old = __import__("json").loads(row[1]) if row else {"id": "ai-settings", "default_model_config_id": None}
    expected = row[0] if row else 0
    store._save(c, "ai_settings", {
        **old, "id": "ai-settings", "default_model_config_id": default_id,
    }, expected)


def create(store, body):
    _strict(body, {"display_name", "provider", "base_url", "model", "api_key", "enabled"})
    display = _text(body.get("display_name"), "显示名称", 200)
    provider = _text(body.get("provider"), "供应商", 100)
    base_url = _text(body.get("base_url"), "Base URL", 2000).rstrip("/")
    model = _text(body.get("model"), "模型名称", 500)
    enabled = body.get("enabled", True)
    if type(enabled) is not bool:
        raise Invalid("enabled 必须是布尔值")
    key = _text(body.get("api_key"), "API Key", 10000)
    with store.connect() as c:
        config = {
            "id": "model-config:" + uid(), "display_name": display,
            "provider": provider, "base_url": base_url, "model": model,
            "api_key_ref": store.secret_store.put(None, key), "enabled": enabled,
            "created_at": now(), "updated_at": now(),
        }
        c.execute("INSERT INTO current VALUES(?,?,?,?)", (config["id"], "ai_model_config", 0, store_dump(config)))
        return _public(config, store.secret_store)


def update(store, config_id, body):
    _strict(body, {"display_name", "provider", "base_url", "model", "api_key", "enabled", "expected_revision"})
    with store.connect() as c:
        current = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        expected = body.get("expected_revision")
        if type(expected) is not int or expected != row[0]:
            raise Conflict("模型配置已更新，请重新载入")
        updated = dict(current)
        for field, label, limit in (("display_name", "显示名称", 200), ("provider", "供应商", 100),
                                    ("base_url", "Base URL", 2000), ("model", "模型名称", 500)):
            if field in body:
                updated[field] = _text(body[field], label, limit).rstrip("/") if field == "base_url" else _text(body[field], label, limit)
        if "enabled" in body:
            if type(body["enabled"]) is not bool: raise Invalid("enabled 必须是布尔值")
            updated["enabled"] = body["enabled"]
        old_ref = current.get("api_key_ref")
        new_key = body.get("api_key")
        if new_key not in (None, ""):
            updated["api_key_ref"] = store.secret_store.put(old_ref, _text(new_key, "API Key", 10000))
        updated["updated_at"] = now()
        saved = store._save(c, "ai_model_config", updated, expected)
        return _public(saved, store.secret_store)


def delete(store, config_id, confirm=False):
    if confirm is not True:
        raise Invalid("删除模型配置需要明确确认")
    with store.connect() as c:
        current = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        settings_row = c.execute("SELECT body FROM current WHERE id='ai-settings' AND kind='ai_settings'").fetchone()
        import json
        setting = json.loads(settings_row[0]) if settings_row else {"default_model_config_id": None}
        if setting.get("default_model_config_id") == config_id:
            _save_settings(store, c, None)
        c.execute("DELETE FROM current WHERE id=?", (config_id,))
        store.secret_store.delete(current.get("api_key_ref", ""))
        return {"deleted": config_id, "default_model_config_id": None if setting.get("default_model_config_id") == config_id else setting.get("default_model_config_id")}


def set_default(store, config_id, body):
    _strict(body, {"expected_revision"})
    with store.connect() as c:
        config = _config(store, c, config_id)
        row = c.execute("SELECT revision FROM current WHERE id=?", (config_id,)).fetchone()
        if body.get("expected_revision") != row[0]: raise Conflict("模型配置已更新，请重新载入")
        if not config.get("enabled"): raise Invalid("只有启用的模型配置可以设为默认")
        _save_settings(store, c, config_id)
        return settings(store, c)


def clear_default(store):
    with store.connect() as c:
        _save_settings(store, c, None)
        return settings(store, c)


def test_ephemeral(store, body):
    """Test an unsaved form without creating a ModelConfig or audit record."""
    _strict(body, {"provider", "base_url", "model", "api_key"})
    config = {
        "provider": _text(body.get("provider"), "供应商", 100),
        "base_url": _text(body.get("base_url"), "Base URL", 2000).rstrip("/"),
        "model": _text(body.get("model"), "模型名称", 500),
    }
    key = _text(body.get("api_key"), "API Key", 10000)
    from .model_gateway import OpenAICompatibleAdapter, GatewayError
    try:
        OpenAICompatibleAdapter(config, key).test()
        return {"status": "success", "code": "success", "model": config["model"]}
    except GatewayError as exc:
        return {"status": "failed", "code": exc.code, "message": str(exc), "model": config["model"]}


def selected(store, c, config_id=None):
    import json
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
    return store.secret_store.get(config["api_key_ref"])


def store_dump(value):
    import json
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
