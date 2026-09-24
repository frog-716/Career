#!/usr/bin/env python3
"""Start or reuse this local application; no external services are launched."""
import argparse
import fcntl
import json
import os
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from workbench.local_runtime import (
    process_started_at,
    write_process_metadata,
)
from workbench.runtime_mode import RuntimeModeError, startup_mode


def runtime_dir(project_root: Path) -> Path:
    path = Path(os.environ.get('CAREER_RUNTIME_DIR') or project_root / '.career-runtime').expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def acquire_runtime_lock(path: Path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    lock_path = path / 'career.lock'
    handle = lock_path.open('a+')
    lock_path.chmod(0o600)
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('Career 已有另一个启动器持有单实例锁')
    return handle

def main():
    try:
        startup_mode()
    except RuntimeModeError as exc:
        print(str(exc), file=sys.stderr)
        return 78
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    url='http://127.0.0.1:'+str(args.port)
    try:
        with urllib.request.urlopen(url+'/healthz',timeout=1) as r:data=json.load(r)
        if data.get('status') == 'ok':
            print('Career 已运行：'+url)
            if not args.no_browser:webbrowser.open(url)
            return 0
    except Exception:pass

    runtime = runtime_dir(Path(__file__).resolve().parents[1])
    try:
        lock = acquire_runtime_lock(runtime)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 75

    import uvicorn
    from workbench.app import create_app
    app=create_app(
        runtime_dir=runtime,
    )
    started_at = process_started_at(os.getpid()) or time.time()
    write_process_metadata(
        app.state.local_runtime.process_metadata_path,
        pid=os.getpid(),
        started_at=started_at,
        instance_id=app.state.local_runtime.startup_instance_id,
        data_instance_id=app.state.local_runtime.data_instance_id,
    )
    print('Career：'+url+'\n个人本机模式已启用；不需要浏览器配对，服务只监听 127.0.0.1。')
    if not args.no_browser:
        import threading
        threading.Timer(1,lambda:webbrowser.open(url)).start()
    try:
        uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)
    finally:
        try:
            app.state.local_runtime.process_metadata_path.unlink(missing_ok=True)
        finally:
            lock.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
