#!/usr/bin/env python3
"""Verify an archive produced by this kit in a clean temporary directory.

Runs scripts from the archive: use only your own trusted generated kit.
"""
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile


def run(args, cwd, expected=0):
    result = subprocess.run([sys.executable, "-B", *args], cwd=cwd,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != expected:
        raise RuntimeError(result.stdout)
    return result.stdout.strip()


def check_archive(archive_path):
    with tempfile.TemporaryDirectory(prefix="workbench-kit-check-") as tmp:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            paths = [PurePosixPath(name) for name in names]
            roots = {p.parts[0] for p in paths if p.parts}
            if len(roots) != 1 or len(set(names)) != len(names):
                raise ValueError("Archive needs one root and unique paths")
            if any(p.is_absolute() or ".." in p.parts or "\\" in str(p) for p in paths):
                raise ValueError("Unsafe archive path")
            if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in archive.infolist()):
                raise ValueError("Symlinks are not allowed")
            if archive.testzip() is not None:
                raise ValueError("Corrupt zip entry")
            archive.extractall(tmp)
        root = Path(tmp) / next(iter(roots))
        print(run(["scripts/verify_bundle.py", "--strict"], root))
        print(run(["-m", "unittest", "discover", "-s", "reference_code/tests", "-v"], root))
        readme = root / "README.md"
        original = readme.read_bytes()
        readme.write_bytes(original + b"\nmodified\n")
        output = run(["scripts/verify_bundle.py", "--strict"], root, expected=1)
        if "Hash/size mismatch" not in output:
            raise RuntimeError("Verifier did not identify tampering")
        readme.write_bytes(original)
        print("PASS: checksum tampering detected; original restored")
        print(run(["scripts/verify_bundle.py", "--strict"], root))
        # Verify deterministic rebuilding and refusal to overwrite.
        rebuilt = Path(tmp) / "rebuilt.zip"
        print(run(["scripts/build_bundle.py", "--output", str(rebuilt)], root))
        if rebuilt.read_bytes() != Path(archive_path).read_bytes():
            raise RuntimeError("Rebuilt archive bytes differ")
        run(["scripts/build_bundle.py", "--output", str(rebuilt)], root, expected=2)
        print("PASS: deterministic rebuild and existing-archive protection")
        original_manifest = (root / "MANIFEST.json").read_bytes()
        unexpected = root / "unexpected.pdf"
        unexpected.write_bytes(b"%PDF-1.7\xff\x00")
        output = run(["scripts/build_bundle.py", "--output", str(Path(tmp) / "invalid.zip")], root, expected=1)
        if "Unexpected private/binary artifact" not in output:
            raise RuntimeError("Unwanted binary was not diagnosed")
        if (root / "MANIFEST.json").read_bytes() != original_manifest:
            raise RuntimeError("Failed build changed the original manifest")
        if (Path(tmp) / "invalid.zip").exists():
            raise RuntimeError("Failed validation left an archive")
        unexpected.unlink()
        print("PASS: binary diagnosed; failed build preserves manifest and creates no zip")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 -B scripts/check_archive.py TRUSTED_KIT.zip")
    check_archive(Path(sys.argv[1]).resolve(strict=True))
