"""T10 weekly backup integrity and recovery contracts over synthetic data."""

import json
import sys
import base64
from io import BytesIO
import threading
import time
from datetime import date
from pathlib import Path

import pytest

from batch_b_helpers import save_job
from workbench import backup as backup_module
from workbench.backup import backup, read_backup_status, restore, verify_backup
from workbench.core import Invalid, Store
from workbench.providers import TestProvider

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from weekly_backup import create_weekly_backup, weekly_target


def _store(tmp_path):
    store = Store(tmp_path / "source", TestProvider())
    job = save_job(store, {"company": "虚构公司", "title": "测试岗位", "jd": "虚构职位描述"})
    resume = store.open_resume(job["id"])
    resume = store.save_resume(resume["id"], "虚构简历正文", 0)
    version = store.save_version(resume["id"], resume["revision"])
    artifact = store.export_pdf(version["id"])
    return store, artifact


def test_same_week_corruption_is_repaired_without_overwriting_original(tmp_path):
    store, artifact = _store(tmp_path)
    day = date(2026, 9, 21)
    target = weekly_target(tmp_path / "backups", day)
    created = create_weekly_backup(store.data_dir, target.parent, day=day)
    assert created == target
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["files"][artifact["path"]] = "tampered"
    (target / "manifest.json").write_text(json.dumps(manifest))

    repaired = create_weekly_backup(store.data_dir, target.parent, day=day)

    assert repaired != target
    assert repaired.exists()
    assert target.exists()
    assert repaired.name.startswith(target.name + ".repair-")


def test_orphan_is_quarantined_and_source_is_preserved(tmp_path):
    store, _ = _store(tmp_path)
    orphan = store.data_dir / "artifacts" / "orphan.bin"
    orphan.write_bytes(b"synthetic orphan")

    bundle = backup(store.data_dir, tmp_path / "backups", "orphan-case")
    manifest = json.loads((bundle / "manifest.json").read_text())

    assert manifest["status"] == "complete_with_quarantine"
    assert manifest["quarantine"]
    quarantined = bundle / manifest["quarantine"][0]["backup_path"]
    assert quarantined.read_bytes() == b"synthetic orphan"
    assert orphan.read_bytes() == b"synthetic orphan"


def test_missing_registered_artifact_publishes_incomplete_recovery_point(tmp_path):
    store, artifact = _store(tmp_path)
    (store.data_dir / artifact["path"]).unlink()

    bundle = backup(store.data_dir, tmp_path / "backups", "missing-case")
    manifest = json.loads((bundle / "manifest.json").read_text())

    assert manifest["status"] == "incomplete"
    assert manifest["needs_attention"]
    assert manifest["needs_attention"][0]["path"] == artifact["path"]
    assert bundle.exists()


def test_interrupted_copy_keeps_recognizable_partial_directory(tmp_path, monkeypatch):
    store, _ = _store(tmp_path)

    def fail_copy(*_args, **_kwargs):
        raise OSError("synthetic copy interruption")

    monkeypatch.setattr(backup_module, "_artifact_path", fail_copy)

    with pytest.raises(OSError, match="synthetic copy interruption"):
        backup(store.data_dir, tmp_path / "backups", "interrupted-case")

    partials = list((tmp_path / "backups").glob(".partial-*"))
    assert len(partials) == 1
    assert (partials[0] / "workspace.sqlite3").exists()
    assert not (tmp_path / "backups" / "interrupted-case").exists()


def test_verified_recovery_point_restores_to_new_dir_and_records_status(tmp_path):
    store, _ = _store(tmp_path)
    backup_dir = tmp_path / "backups"
    bundle = create_weekly_backup(store.data_dir, backup_dir, day=date(2026, 9, 21))

    checked = verify_backup(bundle)
    restored = restore(bundle, tmp_path / "restored")
    status = read_backup_status(backup_dir)

    assert checked["healthy"]
    assert restored["status"] == "complete"
    assert status["last_restore_verified_at"]
    assert (tmp_path / "restored" / "workspace.sqlite3").is_file()


def test_incomplete_recovery_point_is_explicitly_not_healthy(tmp_path):
    store, artifact = _store(tmp_path)
    (store.data_dir / artifact["path"]).unlink()
    bundle = backup(store.data_dir, tmp_path / "backups", "incomplete-case")

    checked = verify_backup(bundle)
    restored = restore(bundle, tmp_path / "restored-incomplete")

    assert not checked["healthy"]
    assert checked["status"] == "incomplete"
    assert restored["status"] == "incomplete"
    assert restored["needs_attention"]


@pytest.mark.parametrize("bad_path", ["artifacts/../outside.pdf", "artifacts/" + "x" * 300 + ".pdf"])
def test_dangerous_or_oversized_registered_path_is_never_followed(tmp_path, bad_path):
    store, artifact = _store(tmp_path)
    with store.connect() as connection:
        row = connection.execute("SELECT body FROM records WHERE id=?", (artifact["id"],)).fetchone()
        body = json.loads(row[0])
        body["path"] = bad_path
        connection.execute("UPDATE records SET body=? WHERE id=?", (json.dumps(body), artifact["id"]))

    bundle = backup(store.data_dir, tmp_path / "backups", "unsafe-path")
    manifest = json.loads((bundle / "manifest.json").read_text())

    assert manifest["status"] == "incomplete"
    assert any(item["path"] == bad_path for item in manifest["needs_attention"])


def _tiny_png():
    from PIL import Image

    image = Image.new("RGB", (1, 1), (12, 34, 56))
    stream = BytesIO()
    image.save(stream, format="PNG")
    return {
        "media_type": "image/png",
        "data_base64": base64.b64encode(stream.getvalue()).decode("ascii"),
    }


def _parallel_feedback(store, total, workers, barrier):
    timings = []
    errors = []
    timings_lock = threading.Lock()

    def save(start):
        try:
            barrier.wait()
            for index in range(start, total, workers):
                started = time.perf_counter()
                store.feedback({"text": f"虚构并发附件 {index}", "screenshot": _tiny_png()})
                elapsed = time.perf_counter() - started
                with timings_lock:
                    timings.append(elapsed)
        except Exception as exc:  # pragma: no cover - reported by the assertion below.
            with timings_lock:
                errors.append(exc)

    threads = [threading.Thread(target=save, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    assert len(timings) == total
    return sorted(timings)


def test_one_thousand_concurrent_attachment_saves_have_measured_backup_budget(tmp_path):
    workers = 4
    total = 1000
    baseline = Store(tmp_path / "baseline", TestProvider())
    baseline_times = _parallel_feedback(baseline, total, workers, threading.Barrier(workers))

    store = Store(tmp_path / "with-backup", TestProvider())
    barrier = threading.Barrier(workers + 1)
    backup_result = {}

    def run_backup():
        barrier.wait()
        backup_result["path"] = backup(store.data_dir, tmp_path / "with-backup-points", "pressure")

    backup_thread = threading.Thread(target=run_backup)
    backup_thread.start()
    with_backup_times = _parallel_feedback(store, total, workers, barrier)
    backup_thread.join()

    checked = verify_backup(backup_result["path"])
    assert checked["healthy"]
    assert len(store.state()["artifacts"]) == total
    baseline_p95 = baseline_times[int(total * 0.95) - 1]
    with_backup_p95 = with_backup_times[int(total * 0.95) - 1]
    print(f"attachment_save_p95 baseline={baseline_p95:.4f}s with_backup={with_backup_p95:.4f}s delta={with_backup_p95 - baseline_p95:.4f}s")
