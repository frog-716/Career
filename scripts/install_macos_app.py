#!/usr/bin/env python3
"""生成可双击的 Career.app。"""
from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path


def build_icon(project_root: Path, resources_dir: Path) -> None:
    source = project_root / "macos" / "career-icon.png"
    if not source.exists():
        raise SystemExit(f"找不到 App 图标源文件：{source}")
    resources_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="career-icon-") as temp_dir:
        iconset = Path(temp_dir) / "Career.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512, 1024):
            output = iconset / f"icon_{size}x{size}.png"
            subprocess.run(["/usr/bin/sips", "-z", str(size), str(size), str(source), "--out", str(output)], check=True, stdout=subprocess.DEVNULL)
            if size <= 512:
                doubled = iconset / f"icon_{size}x{size}@2x.png"
                subprocess.run(["/usr/bin/sips", "-z", str(size * 2), str(size * 2), str(source), "--out", str(doubled)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(resources_dir / "Career.icns")], check=True)


def build(destination: Path, project_root: Path) -> Path:
    app = destination / "Career.app"
    legacy_app = destination / "Career OS.app"
    if legacy_app.exists():
        shutil.rmtree(legacy_app)
    contents = app / "Contents"
    executable_dir = contents / "MacOS"
    executable_dir.mkdir(parents=True, exist_ok=True)
    resources_dir = contents / "Resources"
    build_icon(project_root, resources_dir)
    plist = {
        "CFBundleDisplayName": "Career",
        "CFBundleExecutable": "Career",
        "CFBundleIdentifier": "local.career-os.desktop",
        "CFBundleName": "Career",
        "CFBundlePackageType": "APPL",
        "CFBundleIconFile": "Career.icns",
        "CFBundleIconName": "Career",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
    root = str(project_root.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    source = f'''#include <unistd.h>
#include <stdio.h>

int main(void) {{
    const char *root = "{root}";
    char python[4096];
    char script[4096];
    snprintf(python, sizeof(python), "%s/.venv/bin/python", root);
    snprintf(script, sizeof(script), "%s/scripts/macos_app.py", root);
    execl(python, python, script, "start", "--project-root", root, (char *)0);
    perror("Career launcher");
    return 1;
}}
'''
    with tempfile.TemporaryDirectory(prefix="career-launcher-") as temp_dir:
        source_path = Path(temp_dir) / "launcher.c"
        source_path.write_text(source, encoding="utf-8")
        launcher = executable_dir / "Career"
        subprocess.run(
            ["/usr/bin/clang", "-arch", "arm64", "-O2", "-o", str(launcher), str(source_path)],
            check=True,
        )
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "macos")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    app = build(args.destination, args.project_root)
    print(f"已生成：{app}")
    print("双击该 App 会启动或复用本地服务，并打开用户设置的默认首页。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
