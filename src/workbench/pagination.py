"""Small content-bound cursors for stable read-only list pagination."""

import base64
import json

from .core import Conflict, Invalid, digest


def _token(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _untoken(value):
    try:
        padded = value + "=" * (-len(value) % 4)
        result = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise Invalid("分页游标无效") from None
    if not isinstance(result, dict):
        raise Invalid("分页游标无效")
    return result


def page(items, *, scope, order="created_at,id", limit=None, cursor=None):
    """Return a deterministic page while keeping old list responses compatible."""
    if limit is None and cursor is None:
        return items
    try:
        size = int(limit or 50)
    except (TypeError, ValueError):
        raise Invalid("limit 必须是 1 至 100 的整数") from None
    if size < 1 or size > 100:
        raise Invalid("limit 必须是 1 至 100 的整数")
    ordered = sorted(
        items,
        key=lambda item: (str(item.get("created_at") or item.get("updated_at") or ""), str(item.get("id") or "")),
    )
    start = 0
    if cursor:
        token = _untoken(cursor)
        expected = digest({"scope": scope, "order": order})
        if token.get("scope") != scope or token.get("order") != order or token.get("signature") != expected:
            raise Conflict("分页游标与当前列表范围或排序规则不匹配")
        marker = (str(token.get("created_at") or ""), str(token.get("id") or ""))
        start = next(
            (index + 1 for index, item in enumerate(ordered)
             if (str(item.get("created_at") or item.get("updated_at") or ""), str(item.get("id") or "")) == marker),
            len(ordered),
        )
    selected = ordered[start:start + size]
    next_cursor = None
    if start + size < len(ordered) and selected:
        last = selected[-1]
        next_cursor = _token({
            "scope": scope,
            "order": order,
            "signature": digest({"scope": scope, "order": order}),
            "created_at": last.get("created_at") or last.get("updated_at") or "",
            "id": last.get("id") or "",
        })
    return {"items": selected, "next_cursor": next_cursor, "scope": scope, "order": order}
