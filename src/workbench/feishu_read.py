"""Narrow Feishu read adapter backed only by the existing lark-cli install."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException

from .core import Conflict, Invalid, Missing, Store, digest, now, uid
from .wiki import api as wiki_api
from .wiki import sources


MAX_SEARCH_RESULTS = 10
MAX_QUERY_CHARS = 30
MAX_RAW_CHARS = 100_000
MAX_STDOUT_BYTES = 4 * 1024 * 1024
MAX_STDERR_BYTES = 32 * 1024
CLI_TIMEOUT_SECONDS = 15.0
CACHE_TTL_SECONDS = 15 * 60
ALLOWED_RESOURCE_TYPES = {"doc": "doc", "docx": "docx"}


class FeishuCliError(Exception):
    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class FeishuResourceRef:
    selection_id: str
    resource_type: str
    resource_id: str
    title: str
    url: str | None
    edited_at: str | None

    def public(self) -> dict[str, object]:
        return {
            "provider": "feishu", "selection_id": self.selection_id,
            "resource_type": self.resource_type,
            "title": self.title, "url": self.url, "edited_at": self.edited_at,
        }


@dataclass(frozen=True)
class FeishuPreview:
    preview_id: str
    resource: FeishuResourceRef
    content: str
    content_hash: str
    revision_id: int | None
    expires_at: float

    def public(self) -> dict[str, object]:
        return {
            "preview_id": self.preview_id,
            "resource": {
                "provider": "feishu", "resource_type": self.resource.resource_type,
                "title": self.resource.title,
                "url": self.resource.url, "edited_at": self.resource.edited_at,
                "revision_id": self.revision_id,
            },
            "content": self.content, "content_hash": self.content_hash,
        }


def _safe_feishu_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or parsed.port is not None or parsed.query and len(parsed.query) > 1024):
            return None
        if not (host == "feishu.cn" or host.endswith(".feishu.cn")
                or host == "larksuite.com" or host.endswith(".larksuite.com")):
            return None
        return value
    except ValueError:
        return None


def _avatar_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port:
            return None
        if not (host == "feishucdn.com" or host.endswith(".feishucdn.com")
                or host == "larksuite.com" or host.endswith(".larksuite.com")):
            return None
        return value
    except ValueError:
        return None


def _value(payload: object, key: str, *, nested: str | None = None):
    if not isinstance(payload, dict):
        return None
    result = payload.get(key)
    if nested and isinstance(result, dict):
        return result.get(nested)
    return result


def _error_category(exit_code: int, stdout: bytes, stderr: bytes) -> str:
    messages: list[str] = []
    for raw in (stdout, stderr):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            payload = None
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            messages.extend(str(error.get(key, "")) for key in ("type", "subtype", "code", "message"))
        else:
            messages.append(text[:4096])
    message = " ".join(messages).casefold()
    if any(term in message for term in ("token", "unauthorized", "unauthorised", "401", "refresh", "auth expired")):
        return "auth"
    if any(term in message for term in ("scope", "permission", "forbidden", "403", "access denied")):
        return "permission"
    if exit_code == 2:
        return "invalid_command"
    return "cli_error"


class FeishuReadAdapter:
    """Allowlisted lark-cli calls plus short-lived, server-side selection state."""

    def __init__(
        self,
        cli_path: str | Path | None = None,
        *,
        timeout: float = CLI_TIMEOUT_SECONDS,
        max_stdout_bytes: int = MAX_STDOUT_BYTES,
        max_stderr_bytes: int = MAX_STDERR_BYTES,
    ):
        self.cli_path = Path(cli_path) if cli_path is not None else None
        self.timeout = timeout
        self.max_stdout_bytes = max_stdout_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self._lock = threading.RLock()
        self._resources: dict[str, tuple[FeishuResourceRef, float]] = {}
        self._cursors: dict[str, tuple[str, str, float]] = {}
        self._previews: dict[str, FeishuPreview] = {}

    def _executable(self) -> str:
        candidates: list[Path] = []
        if self.cli_path is not None:
            candidates.append(self.cli_path)
        else:
            found = shutil.which("lark-cli")
            if found:
                candidates.append(Path(found))
            candidates.extend((
                Path.home() / ".local/bin/lark-cli",
                Path("/opt/homebrew/bin/lark-cli"),
                Path("/usr/local/bin/lark-cli"),
            ))
        for candidate in candidates:
            try:
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
            except OSError:
                continue
        raise FeishuCliError("missing", "没有找到已安装的 lark-cli")

    @staticmethod
    def _child_environment() -> dict[str, str]:
        """Pass only runtime basics needed by lark-cli, never Career content/secrets."""
        parent = os.environ
        path = parent.get("PATH", "")
        path_parts = [part for part in path.split(os.pathsep) if part]
        for part in ("/usr/bin", "/bin", "/opt/homebrew/bin", "/usr/local/bin"):
            if part not in path_parts:
                path_parts.append(part)
        env = {"HOME": str(Path.home()), "PATH": os.pathsep.join(path_parts)}
        for name in ("LANG", "LC_ALL", "LC_CTYPE"):
            value = parent.get(name)
            if isinstance(value, str) and len(value) < 128:
                env[name] = value
        return env

    def _run_json(self, args: list[str]) -> object:
        command = [self._executable(), *args]
        try:
            process = subprocess.Popen(
                command, shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=self._child_environment(), close_fds=True, start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise FeishuCliError("missing", "没有找到已安装的 lark-cli") from exc
        except OSError as exc:
            raise FeishuCliError("unavailable", "无法启动现有 lark-cli") from exc

        output: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        sizes = {"stdout": 0, "stderr": 0}
        limits = {"stdout": self.max_stdout_bytes, "stderr": self.max_stderr_bytes}
        overflow = threading.Event()

        def collect(name: str, pipe):
            try:
                while True:
                    chunk = pipe.read(32 * 1024)
                    if not chunk:
                        return
                    sizes[name] += len(chunk)
                    if sizes[name] > limits[name]:
                        overflow.set()
                        return
                    output[name].append(chunk)
            finally:
                pipe.close()

        readers = [
            threading.Thread(target=collect, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=collect, args=("stderr", process.stderr), daemon=True),
        ]
        for thread in readers:
            thread.start()
        deadline = time.monotonic() + self.timeout
        timed_out = False
        while process.poll() is None:
            if overflow.is_set():
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.01)
        if timed_out or overflow.is_set():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                process.kill()
        try:
            exit_code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait()
        for thread in readers:
            thread.join(timeout=1)
        stdout = b"".join(output["stdout"])
        stderr = b"".join(output["stderr"])
        if timed_out:
            raise FeishuCliError("timeout", "lark-cli 读取超时，请稍后重试")
        if overflow.is_set():
            raise FeishuCliError("output_limit", "lark-cli 返回内容超过安全读取上限")
        if exit_code != 0:
            category = _error_category(exit_code, stdout, stderr)
            messages = {
                "auth": "飞书连接需要恢复，请通过现有 lark-cli 检查登录状态。",
                "permission": "当前 lark-cli 或目标资料没有所需读取权限。请检查现有授权，不要在 Career 中扩大权限。",
                "invalid_command": "当前 lark-cli 不接受这项只读请求。",
                "cli_error": "lark-cli 读取失败，请检查现有连接状态。",
            }
            raise FeishuCliError(category, messages.get(category, "lark-cli 读取失败。"))
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise FeishuCliError("invalid_json", "lark-cli 未返回有效 JSON") from exc
        if isinstance(payload, dict) and payload.get("ok") is False:
            category = _error_category(exit_code, stdout, stderr)
            messages = {
                "auth": "飞书连接需要恢复，请通过现有 lark-cli 检查登录状态。",
                "permission": "当前 lark-cli 或目标资料没有所需读取权限。请检查现有授权，不要在 Career 中扩大权限。",
                "invalid_command": "当前 lark-cli 不接受这项只读请求。",
                "cli_error": "lark-cli 读取失败，请检查现有连接状态。",
            }
            raise FeishuCliError(category, messages.get(category, "lark-cli 读取失败。"))
        return payload

    @staticmethod
    def _data(payload: object) -> dict:
        if not isinstance(payload, dict):
            raise FeishuCliError("invalid_json", "lark-cli 返回结构不符合预期")
        if payload.get("ok") is False:
            raise FeishuCliError("cli_error", "lark-cli 读取失败")
        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    def connection_status(self) -> dict[str, object]:
        payload = self._run_json(["auth", "status", "--json"])
        identities = _value(payload, "identities")
        user_status = identities.get("user") if isinstance(identities, dict) else None
        if not isinstance(user_status, dict) or user_status.get("available") is not True:
            return {"connected": False, "identity": None}
        identity_payload = self._run_json(["contact", "+get-user", "--as", "user", "--json"])
        user = _value(self._data(identity_payload), "user")
        if not isinstance(user, dict):
            raise FeishuCliError("invalid_json", "lark-cli 未返回当前用户身份")
        open_id = user.get("open_id")
        display_name = user.get("name")
        status_open_id = user_status.get("openId")
        if (not isinstance(open_id, str) or not open_id or len(open_id) > 256
                or not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 200
                or (isinstance(status_open_id, str) and status_open_id != open_id)):
            raise FeishuCliError("invalid_json", "lark-cli 当前身份字段不完整或不一致")
        return {
            "connected": True,
            "identity": {
                "provider": "feishu", "user_id": open_id,
                "display_name": display_name, "avatar_url": _avatar_url(user.get("avatar_url")),
            },
        }

    @staticmethod
    def _search_query(query: object, *, allow_blank: bool = False) -> str:
        if not isinstance(query, str) or len(query) > MAX_QUERY_CHARS:
            raise Invalid("搜索词不能超过 30 个字符")
        if any(ord(char) < 32 or ord(char) == 127 for char in query):
            raise Invalid("搜索词包含不支持的字符")
        normalized = query.strip()
        if not normalized and not allow_blank:
            raise Invalid("请输入搜索词")
        return normalized

    def _cursor(self, cursor: str | None, query: str) -> tuple[str, str] | None:
        if cursor is None:
            return None
        if not isinstance(cursor, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", cursor):
            raise Invalid("搜索结果已失效，请重新搜索")
        with self._lock:
            self._prune_locked()
            value = self._cursors.get(cursor)
        if value is None:
            raise Conflict("搜索结果已失效，请重新搜索")
        saved_query, page_token, _ = value
        if query and query != saved_query:
            raise Invalid("翻页搜索词不能更改")
        return saved_query, page_token

    def search(self, query: object = "", cursor: str | None = None) -> dict[str, object]:
        normalized = self._search_query(query, allow_blank=cursor is not None)
        cursor_data = self._cursor(cursor, normalized)
        page_token = None
        if cursor_data is not None:
            normalized, page_token = cursor_data
        args = [
            "drive", "+search", "--as", "user", "--query=" + normalized,
            "--doc-types", "doc,docx", "--page-size", str(MAX_SEARCH_RESULTS),
            "--format", "json",
        ]
        if page_token:
            args.extend(("--page-token", page_token))
        payload = self._run_json(args)
        data = self._data(payload)
        rows = data.get("results")
        has_more = data.get("has_more", False)
        next_page_token = data.get("page_token", "")
        if (not isinstance(rows, list) or len(rows) > MAX_SEARCH_RESULTS
                or type(has_more) is not bool
                or (has_more and (not isinstance(next_page_token, str) or not next_page_token or len(next_page_token) > 2048))):
            raise FeishuCliError("invalid_json", "lark-cli 搜索结果结构不符合预期")
        items = []
        expires = time.monotonic() + CACHE_TTL_SECONDS
        with self._lock:
            self._prune_locked()
            for row in rows:
                if not isinstance(row, dict):
                    raise FeishuCliError("invalid_json", "lark-cli 搜索结果结构不符合预期")
                raw_type = row.get("doc_type", row.get("type"))
                resource_type = ALLOWED_RESOURCE_TYPES.get(str(raw_type).casefold())
                resource_id = row.get("token") or row.get("doc_token") or row.get("obj_token")
                title = row.get("title")
                if resource_type is None:
                    continue
                if (not isinstance(resource_id, str)
                        or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", resource_id)
                        or not isinstance(title, str) or not title.strip() or len(title) > 500):
                    raise FeishuCliError("invalid_json", "lark-cli 文档元数据不符合预期")
                edited_at = row.get("edit_time_iso")
                if not isinstance(edited_at, str) or len(edited_at) > 64:
                    edited_at = None
                selection_id = uid().replace(":", "_") + "_" + uid().replace(":", "_")
                ref = FeishuResourceRef(
                    selection_id=selection_id, resource_type=resource_type,
                    resource_id=resource_id, title=title.strip(),
                    url=_safe_feishu_url(row.get("url")),
                    edited_at=edited_at,
                )
                self._resources[selection_id] = (ref, expires)
                items.append(ref.public())
            next_cursor = None
            if has_more:
                next_cursor = uid().replace(":", "_") + "_" + uid().replace(":", "_")
                self._cursors[next_cursor] = (normalized, next_page_token, expires)
            self._bound_cache_locked()
        return {"items": items, "next_cursor": next_cursor}

    def preview(self, selection_id: str) -> dict[str, object]:
        if not isinstance(selection_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", selection_id):
            raise Missing("飞书搜索结果不存在或已失效")
        with self._lock:
            self._prune_locked()
            selected = self._resources.get(selection_id)
        if selected is None:
            raise Missing("飞书搜索结果不存在或已失效，请重新搜索")
        resource = selected[0]
        payload = self._run_json([
            "docs", "+fetch", "--as", "user", "--doc=" + resource.resource_id,
            "--doc-format", "markdown", "--detail", "simple",
        ])
        document = _value(self._data(payload), "document")
        if not isinstance(document, dict) or document.get("document_id") != resource.resource_id:
            raise FeishuCliError("invalid_json", "lark-cli 返回了与所选文档不匹配的内容")
        content = document.get("content")
        revision_id = document.get("revision_id")
        if (not isinstance(content, str) or len(content) > MAX_RAW_CHARS
                or (revision_id is not None and (type(revision_id) is not int or revision_id < 1))):
            raise Invalid("所选飞书文档为空、过长或版本信息不合法，暂时不能导入")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        preview_id = uid().replace(":", "_") + "_" + uid().replace(":", "_")
        preview = FeishuPreview(
            preview_id=preview_id, resource=resource, content=content,
            content_hash=content_hash, revision_id=revision_id,
            expires_at=time.monotonic() + CACHE_TTL_SECONDS,
        )
        with self._lock:
            self._prune_locked()
            self._previews[preview_id] = preview
            self._bound_cache_locked()
        return preview.public()

    def get_preview(self, preview_id: object) -> FeishuPreview:
        if not isinstance(preview_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", preview_id):
            raise Missing("飞书预览已失效，请重新选择资料")
        with self._lock:
            self._prune_locked()
            preview = self._previews.get(preview_id)
        if preview is None:
            raise Missing("飞书预览已失效，请重新选择资料")
        return preview

    def _prune_locked(self) -> None:
        current = time.monotonic()
        self._resources = {key: value for key, value in self._resources.items() if value[1] > current}
        self._cursors = {key: value for key, value in self._cursors.items() if value[2] > current}
        self._previews = {key: value for key, value in self._previews.items() if value.expires_at > current}

    def _bound_cache_locked(self) -> None:
        for cache, limit in ((self._resources, 200), (self._cursors, 100), (self._previews, 20)):
            while len(cache) > limit:
                cache.pop(next(iter(cache)))


def _http_error(error: FeishuCliError) -> HTTPException:
    status = {
        "missing": 503, "unavailable": 503, "auth": 503,
        "permission": 403, "timeout": 504, "output_limit": 502,
        "invalid_json": 502, "invalid_command": 502, "cli_error": 502,
    }.get(error.category, 502)
    return HTTPException(status_code=status, detail=error.message)


def router(store: Store, *, cli_path: str | Path | None = None) -> APIRouter:
    api = APIRouter()
    adapter = FeishuReadAdapter(cli_path)

    @api.get("/api/feishu/status")
    def status():
        try:
            return adapter.connection_status()
        except FeishuCliError as error:
            raise _http_error(error) from error

    @api.post("/api/feishu/search")
    def search(body: dict):
        if not isinstance(body, dict) or set(body) - {"query", "cursor"}:
            raise Invalid("搜索请求包含不允许的字段")
        if "query" not in body and "cursor" not in body:
            raise Invalid("请输入搜索词或选择下一页")
        if "query" in body and not isinstance(body["query"], str):
            raise Invalid("搜索词格式不合法")
        if "cursor" in body and not isinstance(body["cursor"], str):
            raise Invalid("搜索页标识格式不合法")
        try:
            return adapter.search(body.get("query", ""), body.get("cursor"))
        except FeishuCliError as error:
            raise _http_error(error) from error

    @api.post("/api/feishu/resources/{selection_id}/preview")
    def preview(selection_id: str, body: dict):
        if body:
            raise Invalid("预览请求不接受额外参数")
        try:
            return adapter.preview(selection_id)
        except FeishuCliError as error:
            raise _http_error(error) from error

    @api.post("/api/feishu/import")
    def import_raw(body: dict):
        if not isinstance(body, dict) or set(body) != {
            "preview_id", "scope_type", "scope_id", "idempotency_key",
        }:
            raise Invalid("导入请求字段不合法")
        preview = adapter.get_preview(body.get("preview_id"))
        with store.connect() as connection:
            scope = wiki_api._scope(store, connection, body.get("scope_type"), body.get("scope_id"))
            provenance = {
                "kind": "external_source", "provider": "feishu",
                "resource_type": preview.resource.resource_type,
                "resource_id": preview.resource.resource_id,
                "url": preview.resource.url,
                "revision_id": preview.revision_id,
            }
            payload = {
                "scope_type": scope[0], "scope_id": scope[1],
                "source_kind": "feishu_doc", "title": preview.resource.title,
                "content": preview.content, "provenance": provenance,
            }
            previous, key, fingerprint = wiki_api._request(
                store, connection, "import_feishu_raw", body.get("idempotency_key"), payload,
            )
            if previous is not None:
                value = sources.resolve_source(store, connection, "raw_material", previous["raw_id"])
                return dict(value, source_ref=sources.source_ref(value))
            created_at = now()
            raw = {
                "id": uid(), "kind": "raw_material", **{k: v for k, v in payload.items() if k != "provenance"},
                "revision": 1, "hash": digest(payload), "provenance": provenance,
                "created_at": created_at,
            }
            store._record(connection, "raw_material", raw)
            result = dict(raw, source_ref=sources.source_ref(raw))
            wiki_api._remember(store, connection, key, fingerprint, {"raw_id": raw["id"]})
            return result

    return api
