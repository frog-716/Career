# Career OS 本地服务

安装并启动（项目根目录）：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python scripts/run.py
```

入口 http://127.0.0.1:8765；启动器复用已有服务，默认打开浏览器。单进程运行，不使用多 worker。
生产默认 `~/Library/Application Support/CareerOS`；用 `CAREER_DATA_DIR` 指向代码目录之外可更换位置。代码不含任何用户资料，生产与合成测试数据分开。SQLite schema version 1；当前无旧业务版本需迁移，后续升级必须先备份、显式 migration，程序拒绝未知更高版本。

## 模块职责与接口

- `core.Store`：current 及 revisions 正本写入、Context 白名单、分析审计、提案/版本/投递/反馈事务。页面仅调 HTTP Service。`context/analyze` 每轮读取 profile 当前版本和指定 active JD，不读取历史、反馈、简历或旧结果。首版资料为一个自由文本单元（请维护与当前目标相关的事实、硬约束、反证和未知），不预建图谱和自动选材。全局 epoch 让资料/JD任何修改使既有分析过期，简历草稿另查 revision。
- `providers`：只收实际 payload；Provider 不持有 Store、数据库或文件工具。远端不继承会话。每轮 payload 在本地运行审计保存，可在 UI 查看；语义正确性需人工审阅。
- `artifacts`：PDF / 截图原子写入与 sha256；数据库只存相对路径、metadata和关系。已有投递关联不可变版本/PDF与岗位快照。
- `app`：仅回环 Host、同源 Origin、写入自定义 header、请求大小上限；静态服务仅 frontend/dist，不暴露数据目录。
- `backup`：SQLite 在线一致性快照和关联附件哈希清单，恢复只允许不存在的新目录。

HTTP 与错误/并发字段见 [当前 MVP Interface](../../docs/execution/MVP.md)。expected_revision 冲突返回409；提案原子检查 epoch+draft revision 并保存 applied_result实现幂等。版本按草稿revision幂等、投递按用户动作幂等键。反馈补充只追加；数据不进入AI。

## Provider 配置

默认真实模式，缺配置仍可启动、编辑和导出；调用时返回未配置。

在本地终端配置（不要把密钥发到聊天）：

```sh
export CAREER_AI_PROVIDER=real
export CAREER_AI_BASE_URL=https://api.openai.com/v1
export CAREER_AI_MODEL='填写你的服务已授权的模型名称'
read -s 'CAREER_AI_API_KEY?API Key（隐藏输入）：'
export CAREER_AI_API_KEY
.venv/bin/python scripts/run.py
```

上述隐藏输入语法用于 macOS zsh。更换配置后先停止旧进程再启动。支持遵循 Chat Completions JSON 对象格式的服务；开发模型配置不代表运行时模型授权。官方请求参考：[Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)。远端请求仅在预览后点击发送，包包括当前资料、该岗位 JD 和本轮指令。API Key 仅服务端环境变量，不进入包/日志/UI；不读宿主登录凭据。

显式测试模式只验证流程，不是真实 AI：

```sh
CAREER_AI_PROVIDER=test CAREER_DATA_DIR=/tmp/career-os-synthetic .venv/bin/python scripts/run.py --port 8766
```

不自动种入 fixtures；生产首次为空。

## 验证与恢复

```sh
PYTHONPATH=src .venv/bin/pytest tests -q
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv/bin/python scripts/backup.py backup "$HOME/Library/Application Support/CareerOS" "$HOME/Library/Application Support/CareerOS-backups"
.venv/bin/python scripts/backup.py restore /绝对路径/备份目录 /绝对路径/尚不存在的恢复目录
```

恢复后用 CAREER_DATA_DIR 指向新目录启动；不要将生成备份放进仓库。仅同机备份不能抵御磁盘损坏。
