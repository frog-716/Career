#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from workbench.backup import backup,restore
p=argparse.ArgumentParser(description='仅本地备份；恢复到新目录，不覆盖已有数据')
p.add_argument('action',choices=['backup','restore']);p.add_argument('source');p.add_argument('destination')
a=p.parse_args()
result=backup(a.source,a.destination) if a.action=='backup' else restore(a.source,a.destination)
print(result or a.destination)
