#!/usr/bin/env python3
"""Start or reuse this local application; no external services are launched."""
import argparse
import sys
import urllib.request
import json
import webbrowser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    url='http://127.0.0.1:'+str(args.port)
    try:
        with urllib.request.urlopen(url+'/api/state',timeout=1) as r:data=json.load(r)
        if data.get('diagnostics',{}).get('app_version'):
            print('Career OS 已运行：'+url)
            if not args.no_browser:webbrowser.open(url)
            return
    except Exception:pass
    import uvicorn
    from workbench.app import create_app
    app=create_app()
    print('Career OS：'+url+'\n数据目录：'+str(app.state.store.data_dir))
    if not args.no_browser:
        import threading
        threading.Timer(1,lambda:webbrowser.open(url)).start()
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)
if __name__=='__main__':main()
