#!/usr/bin/env python3
"""Seal and zip this kit; writes only MANIFEST and a chosen new zip artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from verify_bundle import ROOT, check, payload_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / (ROOT.name + ".zip"))
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists() or target.is_symlink():
        parser.error("Output already exists; choose a new explicit filename")
    if ROOT == target or ROOT in target.parents:
        parser.error("Zip output must be outside the kit")
    files = payload_files(ROOT)
    entries = [{"path": f.relative_to(ROOT).as_posix(), "bytes": f.stat().st_size,
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]
    manifest = {"formatVersion": 1, "kit": ROOT.name, "date": "2026-09-14",
                "scope": "clean design kit, not an implemented application",
                "manifestExcludesItself": True, "files": entries}
    errors, count = check(ROOT, strict=True, manifest=manifest)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    # Keep the prior manifest intact if validation fails; publish atomically.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ROOT,
                                     prefix=".manifest-", delete=False) as temporary:
        temporary.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        manifest_temp = Path(temporary.name)
    try:
        manifest_temp.replace(ROOT / "MANIFEST.json")
    finally:
        manifest_temp.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files + [ROOT / "MANIFEST.json"]:
            info = zipfile.ZipInfo(ROOT.name + "/" + file.relative_to(ROOT).as_posix(),
                                   date_time=(2026, 9, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, file.read_bytes())
    print(f"Created {target.name}: {count + 1} files, {target.stat().st_size} bytes")
    print("SHA-256", hashlib.sha256(target.read_bytes()).hexdigest())
