"""Consistent local backup and restore without overwriting user data."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import uuid

from .artifacts import ArtifactError
from .attachment_lock import attachment_lifecycle_lock
from .core import Invalid, ROOT


MANIFEST_SCHEMA = 1
STATUS_FILE = ".career-weekly-status.json"
_SUPPORTED_SCHEMA = {1, 2, 3, 4, 5, 6}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _outside(path):
    p = Path(path).expanduser().resolve()
    if p == ROOT or ROOT in p.parents:
        raise Invalid("备份与数据目录必须在代码目录外")
    return p


def _fsync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_dir(path.parent)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def read_backup_status(backup_dir):
    path = _outside(backup_dir) / STATUS_FILE
    if not path.is_file():
        return {
            "last_success_at": None,
            "last_restore_verified_at": None,
            "last_error": None,
            "recovery_point_age": None,
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "last_success_at": None,
            "last_restore_verified_at": None,
            "last_error": f"status_read_error: {exc}",
            "recovery_point_age": None,
        }
    return {
        "last_success_at": value.get("last_success_at"),
        "last_restore_verified_at": value.get("last_restore_verified_at"),
        "last_error": value.get("last_error"),
        "recovery_point_age": value.get("recovery_point_age"),
    }


def update_backup_status(backup_dir, **changes):
    root = _outside(backup_dir)
    current = read_backup_status(root)
    current.update({key: changes[key] for key in changes if key in current})
    _write_json(root / STATUS_FILE, current)
    return current


def _artifact_records(connection):
    """Return artifact path/hash pairs, rejecting ambiguous metadata."""
    records = {}
    for (body,) in connection.execute("SELECT body FROM records WHERE kind='artifact'"):
        try:
            artifact = json.loads(body)
            path, digest = artifact["path"], artifact["sha256"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise Invalid("附件记录缺少路径或哈希，备份未完成") from exc
        if not isinstance(path, str) or not isinstance(digest, str):
            raise Invalid("附件记录缺少路径或哈希，备份未完成")
        if path in records and records[path] != digest:
            raise Invalid("多个附件记录使用同一路径但哈希不同，备份未完成")
        records[path] = digest
    return records


def _listed_artifact_files(root):
    directory = Path(root) / "artifacts"
    if not directory.exists():
        return set()
    if directory.is_symlink() or not directory.is_dir():
        raise Invalid("附件目录无效")
    files = set()
    for path in directory.rglob("*"):
        if path.is_symlink() or not path.is_file():
            raise Invalid("附件目录包含无效文件")
        files.add(str(path.relative_to(root)))
    return files


def _artifact_path(root, relative):
    if not isinstance(relative, str) or not relative.startswith("artifacts/"):
        raise ArtifactError("附件路径无效")
    candidate = (Path(root) / relative).resolve()
    artifacts = (Path(root) / "artifacts").resolve()
    try:
        unsafe = candidate.is_symlink() or not candidate.is_file()
    except OSError as exc:
        raise ArtifactError("附件路径无效") from exc
    if artifacts not in candidate.parents or unsafe:
        raise ArtifactError("附件路径无效")
    return candidate


def _manifest_needs(manifest):
    value = manifest.get("needs_attention", [])
    return value if isinstance(value, list) else []


def _validate_manifest_against_db(root, manifest, artifact_records):
    """Validate published files against the DB snapshot.

    An incomplete recovery point may intentionally omit unreadable registered
    attachments, but every omission must be explicitly recorded in the
    manifest. It is never treated as a healthy backup.
    """
    files = manifest.get("files")
    if not isinstance(files, dict) or "workspace.sqlite3" not in files:
        raise Invalid("备份清单版本不支持")
    listed = {path: digest for path, digest in files.items() if path != "workspace.sqlite3"}
    expected = set(artifact_records)
    omitted = expected - set(listed)
    attention_paths = {item.get("path") for item in _manifest_needs(manifest) if isinstance(item, dict)}
    if omitted - attention_paths or (omitted and manifest.get("status") != "incomplete"):
        raise Invalid("清单遗漏附件：" + ", ".join(sorted(omitted)))
    extra = set(listed) - expected
    if extra:
        raise Invalid("清单包含未引用附件：" + ", ".join(sorted(extra)))

    on_disk = _listed_artifact_files(root)
    expected_on_disk = set(listed)
    if on_disk != expected_on_disk:
        missing = sorted(expected_on_disk - on_disk)
        extra = sorted(on_disk - expected_on_disk)
        detail = []
        if missing:
            detail.append("备份缺少附件文件：" + ", ".join(missing))
        if extra:
            detail.append("发现未列入清单的孤儿附件：" + ", ".join(extra))
        raise Invalid("；".join(detail) or "附件文件与清单不一致")
    for path, digest in artifact_records.items():
        if path in omitted:
            continue
        if listed[path] != digest:
            raise Invalid("附件清单哈希与数据库记录不一致：" + path)
        if hashlib.sha256((Path(root) / path).read_bytes()).hexdigest() != digest:
            raise Invalid("附件文件哈希校验失败：" + path)


def _validate_quarantine(root, manifest):
    errors = []
    quarantine = manifest.get("quarantine", [])
    if not isinstance(quarantine, list):
        return ["quarantine 格式无效"]
    for item in quarantine:
        if not isinstance(item, dict):
            errors.append("quarantine 条目无效")
            continue
        relative, digest = item.get("backup_path"), item.get("sha256")
        if not isinstance(relative, str) or not relative.startswith("quarantine/") or not isinstance(digest, str):
            errors.append("quarantine 路径或哈希无效")
            continue
        path = (Path(root) / relative).resolve()
        quarantine_root = (Path(root) / "quarantine").resolve()
        if quarantine_root not in path.parents or path.is_symlink() or not path.is_file():
            errors.append("quarantine 文件缺失：" + relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append("quarantine 哈希失败：" + relative)
    return errors


def verify_backup(backup_dir):
    """Verify one published recovery point without initializing Store."""
    root = _outside(backup_dir)
    result = {
        "path": str(root),
        "valid": False,
        "healthy": False,
        "recoverable": False,
        "partial_recovery": False,
        "status": "invalid",
        "created_at": None,
        "needs_attention": [],
        "quarantine": [],
        "differences": [],
    }
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        result["status"] = manifest.get("status", "legacy")
        result["created_at"] = manifest.get("created_at")
        result["needs_attention"] = _manifest_needs(manifest)
        result["quarantine"] = manifest.get("quarantine", [])
        if manifest.get("schemaVersion") != MANIFEST_SCHEMA:
            raise Invalid("备份清单版本不支持")
        files = manifest.get("files")
        database = root / "workspace.sqlite3"
        if not isinstance(files, dict) or "workspace.sqlite3" not in files:
            raise Invalid("备份清单版本不支持")
        if not database.is_file() or hashlib.sha256(database.read_bytes()).hexdigest() != files["workspace.sqlite3"]:
            raise Invalid("备份数据库哈希校验失败")
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in _SUPPORTED_SCHEMA:
                raise Invalid("备份 schema 不受支持")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise Invalid("备份数据库损坏")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise Invalid("备份存在外键损坏")
            records = _artifact_records(connection)
        _validate_manifest_against_db(root, manifest, records)
        result["differences"] = _validate_quarantine(root, manifest)
        result["valid"] = not result["differences"]
        result["healthy"] = result["valid"] and result["status"] in {"complete", "complete_with_quarantine"}
        result["recoverable"] = result["healthy"]
        result["partial_recovery"] = result["valid"] and result["status"] == "incomplete"
    except (OSError, ValueError, TypeError, json.JSONDecodeError, Invalid, sqlite3.Error) as exc:
        result["differences"].append(str(exc))
    return result


def _copy_bytes(data, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _safe_quarantine_name(path):
    base = Path(path).name.replace("/", "_").replace("\\", "_")[:160] or "orphan"
    return f"{uuid.uuid4().hex}-{base}"


def _partial_error(staging, exc):
    try:
        _write_json(Path(staging) / ".partial-status.json", {"status": "interrupted", "error": str(exc), "at": _now()})
    except Exception:
        pass


def backup(data_dir, output_dir, backup_name=None):
    """Publish a complete, warned, or incomplete recovery point atomically."""
    source = _outside(data_dir)
    output = _outside(output_dir)
    if not (source / "workspace.sqlite3").is_file():
        raise Invalid("源数据库不存在")
    if output == source or source in output.parents:
        raise Invalid("备份目录不能位于源数据目录内")
    if backup_name is not None:
        if not isinstance(backup_name, str) or not backup_name or Path(backup_name).name != backup_name:
            raise Invalid("备份名称不合法")
        final = output / backup_name
    else:
        final = output / ("career-backup-" + str(uuid.uuid4()))
    if final.exists() or final.is_symlink():
        raise Invalid("备份目标已存在，不会覆盖")
    if final == source or final in source.parents:
        raise Invalid("备份目标不能覆盖源数据目录")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    staging = Path(tempfile.mkdtemp(prefix=".partial-", dir=str(output)))
    os.chmod(staging, 0o700)
    try:
        with attachment_lifecycle_lock(source):
            with sqlite3.connect(str(source / "workspace.sqlite3"), timeout=15) as locker:
                locker.execute("BEGIN IMMEDIATE")
                # The read connection is separate because SQLite's backup API
                # must not run on a connection holding this write reservation.
                with sqlite3.connect(str(source / "workspace.sqlite3")) as src, sqlite3.connect(str(staging / "workspace.sqlite3")) as dest:
                    src.backup(dest)
                with sqlite3.connect(str(staging / "workspace.sqlite3")) as snapshot:
                    if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise Invalid("源数据库快照损坏")
                    if snapshot.execute("PRAGMA foreign_key_check").fetchone() is not None:
                        raise Invalid("源数据库快照存在外键损坏")
                    artifact_records = _artifact_records(snapshot)
                manifest = {
                    "schemaVersion": MANIFEST_SCHEMA,
                    "status": "complete",
                    "created_at": _now(),
                    "files": {},
                    "quarantine": [],
                    "needs_attention": [],
                }
                for path, digest in artifact_records.items():
                    try:
                        original = _artifact_path(source, path)
                        data = original.read_bytes()
                        actual = hashlib.sha256(data).hexdigest()
                        if actual != digest:
                            raise ArtifactError("登记附件哈希不匹配")
                    except (ArtifactError, Invalid) as exc:
                        manifest["needs_attention"].append({"path": path, "expected_sha256": digest, "reason": str(exc)})
                        continue
                    target = staging / path
                    _copy_bytes(data, target)
                    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                        raise OSError("附件复制后哈希校验失败：" + path)
                    manifest["files"][path] = digest

                referenced = set(artifact_records)
                for orphan in sorted(_listed_artifact_files(source) - referenced):
                    original = _artifact_path(source, orphan)
                    data = original.read_bytes()
                    quarantine_name = "quarantine/" + _safe_quarantine_name(orphan)
                    target = staging / quarantine_name
                    _copy_bytes(data, target)
                    digest = hashlib.sha256(data).hexdigest()
                    manifest["quarantine"].append({
                        "backup_path": quarantine_name,
                        "original_path": orphan,
                        "sha256": digest,
                    })

                manifest["files"]["workspace.sqlite3"] = hashlib.sha256((staging / "workspace.sqlite3").read_bytes()).hexdigest()
                if manifest["needs_attention"]:
                    manifest["status"] = "incomplete"
                elif manifest["quarantine"]:
                    manifest["status"] = "complete_with_quarantine"
                locker.commit()
        _write_json(staging / "manifest.json", manifest)
        _fsync_dir(staging)
        os.replace(staging, final)
        _fsync_dir(output)
        return final
    except Exception as exc:
        # A partial directory is evidence of an interrupted/unpublished run;
        # keep it recognizable for diagnosis instead of deleting it.
        if staging.exists():
            _partial_error(staging, exc)
        raise


def restore(backup_dir, destination):
    """Restore a verified recovery point into a new directory only."""
    source = _outside(backup_dir)
    dest = _outside(destination)
    if dest.exists():
        raise Invalid("恢复目标必须是不存在的新目录，不会覆盖已有数据")
    if source in dest.parents:
        raise Invalid("恢复目录不能位于备份目录内")
    checked = verify_backup(source)
    if not checked["valid"]:
        raise Invalid("备份不可恢复：" + "; ".join(checked["differences"]))
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".career-restore-", dir=str(dest.parent)))
    try:
        for relative, digest in manifest["files"].items():
            p = (source / relative).resolve()
            if source not in p.parents or (relative != "workspace.sqlite3" and not relative.startswith("artifacts/")):
                raise Invalid("备份路径越界")
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise Invalid("备份哈希校验失败")
            _copy_bytes(data, stage / relative)
        for item in manifest.get("quarantine", []):
            relative, digest = item["backup_path"], item["sha256"]
            p = (source / relative).resolve()
            if source not in p.parents or not relative.startswith("quarantine/"):
                raise Invalid("隔离附件路径越界")
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise Invalid("隔离附件哈希校验失败")
            _copy_bytes(data, stage / relative)
        with sqlite3.connect((stage / "workspace.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise Invalid("备份数据库损坏")
            artifact_records = _artifact_records(connection)
        _validate_manifest_against_db(stage, manifest, artifact_records)
        _fsync_dir(stage)
        os.replace(stage, dest)
        _fsync_dir(dest.parent)
        verified_at = _now()
        update_backup_status(source.parent, last_restore_verified_at=verified_at, last_error=None)
        return {
            "destination": str(dest),
            "status": manifest.get("status"),
            "verified_at": verified_at,
            "needs_attention": manifest.get("needs_attention", []),
            "quarantine": manifest.get("quarantine", []),
        }
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
