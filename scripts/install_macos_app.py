#!/usr/bin/env python3
"""生成可双击的 Career.app。"""
from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path


DEFAULT_PORT = 8765


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


def launcher_source(port: int = DEFAULT_PORT, ai_mode: str | None = None) -> str:
    if ai_mode not in (None, "LOCAL_ONLY", "AI_ENABLED"):
        raise ValueError("ai_mode 必须是 LOCAL_ONLY、AI_ENABLED 或 None")
    mode_setup = f'    setenv("CAREER_AI_MODE", "{ai_mode}", 1);\n' if ai_mode else ""
    return f'''#include <unistd.h>
#include <libproc.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {{
    char executable[PROC_PIDPATHINFO_MAXSIZE];
    char resolved[PROC_PIDPATHINFO_MAXSIZE];
    char root[PROC_PIDPATHINFO_MAXSIZE];
    char python[PROC_PIDPATHINFO_MAXSIZE];
    char script[PROC_PIDPATHINFO_MAXSIZE];
    if (proc_pidpath(getpid(), executable, sizeof(executable)) <= 0 ||
        realpath(executable, resolved) == NULL) {{
        perror("Career launcher: cannot locate executable");
        return 1;
    }}
    char *last_slash = strrchr(resolved, '/');
    if (last_slash == NULL) {{
        fprintf(stderr, "Career launcher: invalid executable path\\n");
        return 1;
    }}
    *last_slash = '\\0';
    if (snprintf(root, sizeof(root), "%s", resolved) >= (int)sizeof(root)) {{
        fprintf(stderr, "Career launcher: project path is too long\\n");
        return 1;
    }}
    int found = 0;
    for (int depth = 0; depth < 16; depth++) {{
        int written = snprintf(script, sizeof(script), "%s/scripts/macos_app.py", root);
        if (written < 0 || written >= (int)sizeof(script)) {{
            fprintf(stderr, "Career launcher: project path is too long\\n");
            return 1;
        }}
        if (access(script, R_OK) == 0) {{
            found = 1;
            break;
        }}
        char *parent = strrchr(root, '/');
        if (parent == NULL || parent == root) break;
        *parent = '\\0';
    }}
    if (!found) {{
        fprintf(stderr, "Career 项目目录不存在；请将 Career.app 放回项目目录内\\n");
        return 1;
    }}
    int python_written = snprintf(python, sizeof(python), "%s/.venv/bin/python", root);
    if (python_written < 0 || python_written >= (int)sizeof(python)) {{
        fprintf(stderr, "Career launcher: project path is too long\\n");
        return 1;
    }}
    if (access(python, X_OK) != 0) {{
        fprintf(stderr, "Career 虚拟环境不存在：%s\\n", python);
        return 1;
    }}
{mode_setup}
    execl(python, python, script, "start", "--project-root", root, "--port", "{int(port)}", (char *)0);
    perror("Career launcher");
    return 1;
}}
'''


def build(destination: Path, project_root: Path, port: int = DEFAULT_PORT, ai_mode: str | None = None) -> Path:
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
    source = launcher_source(port, ai_mode)
    with tempfile.TemporaryDirectory(prefix="career-launcher-") as temp_dir:
        source_path = Path(temp_dir) / "launcher.c"
        source_path.write_text(source, encoding="utf-8")
        launcher = executable_dir / "Career"
        subprocess.run(
            ["/usr/bin/clang", "-arch", "arm64", "-O2", "-o", str(launcher), str(source_path)],
            check=True,
        )
    subprocess.run(
        ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", "--timestamp=none", str(app)],
        check=True,
    )
    subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
        check=True,
    )
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "macos")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ai-mode", choices=("LOCAL_ONLY", "AI_ENABLED"), default=None,
                        help="将显式运行模式嵌入 App；省略时 Finder 启动会 fail closed")
    args = parser.parse_args()
    app = build(args.destination, args.project_root, args.port, args.ai_mode)
    print(f"已生成：{app}")
    print("双击该 App 会启动或复用本地服务，并打开用户设置的默认首页。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
