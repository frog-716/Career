# Career OS 本地服务

安装并启动（项目根目录）：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python scripts/run.py
```

入口 http://127.0.0.1:8765；启动器复用已有服务。`scripts/run.py` 跟随系统默认浏览器，`macos/Career.app` 则显式使用 Google Chrome，不修改 macOS 全局设置。单进程运行，不使用多 worker。
生产默认 `~/Library/Application Support/Career Data`；用 `CAREER_DATA_DIR` 指向代码目录之外可更换位置。代码不含任何用户资料，生产与合成测试数据分开。SQLite schema version 1；当前无旧业务版本需迁移，后续升级必须先备份、显式 migration，程序拒绝未知更高版本。

## 模块职责与接口

- `core.Store`：current 及 revisions 正本写入、Context 白名单、分析审计、提案/版本/投递/反馈事务。页面仅调 HTTP Service。`context/analyze` 每轮同事务读取基础资料、指定 active JD 和显式选择的当前 Wiki；个人目标/约束必选，其余每轮重选。不读取原件、候选、历史、反馈、简历或旧结果。profile 在用户显式整理后仅维护身份字段；旧混合资料归档及候选确认不会形成重复当前正本。全局 epoch 让资料/JD任何修改使既有分析过期，简历草稿另查 revision。
- `knowledge`：不可变来源、候选整理/确认、Wiki 当前修订/撤回与历史；来源同 scope 校验；个人/机会/任职隔离。仅个人或当前机会有效条目能进入求职 packet。
- `domain`：公司/组织树、求职周期/方向、机会关系、固定简历版本用途。用途不创建实际投递；机会用途可经共用投递接口引用结构化正式版本。接口见 [Wiki 与业务对象整合](../../docs/execution/WIKI-DOMAIN.md)。
- `opportunity`：公开的 Opportunity 主身份和旧 `job` 兼容映射；Submission 冻结 Opportunity、JobPosting、公司/组织/方向/周期、简历版本和 PDF 哈希，状态变化追加历史。
- `employment` / `work`：公开的 Employment 主身份和旧 `journey_episode` 兼容映射；EmploymentStage、Project、Person、WorkEvent、Achievement、Evidence 及其多对多关系。工作成果不会自动写入个人 Wiki。
- `engagement`：ResearchSnapshot、Communication、Interview、Offer 的独立业务记录；每条记录引用不可变 `journey_note` 原文，旧记录通过只读 projection 兼容。
- `context`：唯一 Context Compiler，输出 schema v2 的来源 revision/hash、用途、未知/冲突/遗漏、策略版本和预算；机会关系变化会使旧预览与结果失效。
- `providers`：只收实际 payload；Provider 不持有 Store、数据库或文件工具。远端不继承会话。每轮 payload 在本地运行审计保存，可在 UI 查看；语义正确性需人工审阅。
- `artifacts`：PDF / 截图原子写入与 sha256；数据库只存相对路径、metadata和关系。已有投递关联不可变版本/PDF与岗位快照。
- `app`：仅回环 Host、同源 Origin、写入自定义 header、请求大小上限；静态服务仅 frontend/dist，不暴露数据目录。
- `backup`：在 SQLite 稳定写入窗口内生成在线一致性快照和关联附件哈希清单；备份、恢复都会逐条核对数据库 artifact 引用、清单、文件与 sha256，并拒绝缺失、哈希不符、清单遗漏或孤儿附件。恢复只允许不存在的新目录，现有 schemaVersion 1 清单仍可读取。
- `demo`：幂等装载或删除带固定 dataset id 的虚构全链路案例；不会覆盖 profile、现有机会、简历或附件，删除前逐项核对归属。
- `journey`：按岗位保存阶段/下一行动/日期，按工作期保存卡片，追加不可变的研究、沟通、面试、Offer、事务、协作和收获记录。计划更新CAS；笔记重试幂等；数据纳入同一备份。手动阶段不创建实际投递，记录不进入当前求职Context。完整HTTP契约见 [任务工作台批次](../../docs/execution/TASK-WORKSPACE.md)。

HTTP 路由、错误与并发语义以当前模块实现和对应测试为准，跨模块边界见 [结构优化与产品化重构](../../docs/execution/STRUCTURE-REFACTOR.md)。expected_revision 冲突返回409；提案原子检查 epoch+draft revision 并保存 applied_result实现幂等。版本按草稿revision幂等、投递按用户动作幂等键。反馈补充只追加；数据不进入AI。

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

上述隐藏输入语法用于 macOS zsh。更换配置后先停止旧进程再启动。支持遵循 Chat Completions JSON 对象格式的服务；开发模型配置不代表运行时模型授权。官方请求参考：[Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)。远端请求仅在预览后点击发送，包包括当前基础资料、显式选择的当前 Wiki、该岗位 JD 和本轮指令。API Key 仅服务端环境变量，不进入包/日志/UI；不读宿主登录凭据。

显式测试模式只验证流程，不是真实 AI：

```sh
CAREER_AI_PROVIDER=test CAREER_DATA_DIR=/tmp/career-os-synthetic .venv/bin/python scripts/run.py --port 8766
```

不自动种入 fixtures；生产首次为空。

## 独立简历工作台

构建前端并启动同一服务后，打开 `/editor.html`。`editor.py` 封装结构化草稿、修订冲突、不可变版本和恢复点；历史版本可通过 `DELETE /api/editor/versions/{version_id}` 删除，同时删除未被引用的 PDF。已经关联岗位/方向或登记投递的版本会返回冲突并保留，避免破坏历史投递记录。接口契约及源码来源见 [工作台接入批次](../../docs/execution/RESUME-WORKBENCH.md)。工作稿不进入默认职业事实 Context，线上妙搭资料不自动导入。实际 PDF 存入同一个本地附件目录，纳入下述备份流程。

## 验证与恢复

```sh
PYTHONPATH=src .venv/bin/pytest tests -q
npm --prefix frontend run typecheck
npm --prefix frontend run build
.venv/bin/python scripts/backup.py backup "$HOME/Library/Application Support/Career Data" "$HOME/Library/Application Support/Career Data-backups"
.venv/bin/python scripts/backup.py restore /绝对路径/备份目录 /绝对路径/尚不存在的恢复目录
```

每周生产备份由 macOS 用户级 LaunchAgent 在周一 00:00 调用 `scripts/weekly_backup.py`，目标目录按周一日期命名为 `Career Data-backups/YYYYMMDD`。安装、检查、卸载分别使用 `.venv/bin/python scripts/install_weekly_backup.py install|status|uninstall`；测试或演练请使用隔离 `--data-dir`，不要指向生产目录。

恢复后用 CAREER_DATA_DIR 指向新目录启动；不要将生成备份放进仓库。仅同机备份不能抵御磁盘损坏。

## 固定版本投递（冷启动整改）

`POST /api/applications` 复用已有 applications 表：`job_id, version_id, artifact_id, applied_at（含时区）, channel, status, idempotency_key`。服务根据记录 kind 接受 `editor_version` 或旧 `version`；结构化版本必须已存在匹配机会/PDF/hash 的 `resume_use`，方向用途不能替代机会用途。新写入的 `version_kind` 标注来源，旧记录缺省为文字版；`channel` 对旧客户端可省略，页面必填。不存在404、关系或PDF损坏422、幂等键不同内容409。

在同一事务中冻结岗位、版本内容与排版、PDF元数据；后续工作稿/资料/JD变化不更新投递。只有显式状态接口可改投递status。新创建请求指纹包含初始status，状态更新后原请求仍可安全重放；旧记录缺少初始请求，沿用身份/材料/时间校验并补渠道校验，不推断原始status。无DDL migration，不补造旧数据字段，不复制新版本到旧文字稿。`tests/test_applications.py` 验证冻结、跨机会用途、损坏PDF、并发幂等、旧格式重放与实际Provider测试请求隔离。

旧 `resume/version` 仅保留历史兼容读取；HTTP 不再允许编辑旧文字稿、生成旧版本或应用旧提案。结构化 `/api/editor` 是唯一简历编辑与版本入口。

## 全链路案例

设置页可调用 `POST /api/demo/load` 装载或补齐案例，调用 `POST /api/demo/remove` 删除案例。案例固定使用 `career-os-b5-demo-v1`，包含 Opportunity、ResearchSnapshot、Communication、Interview、Offer、Submission、Employment、EmploymentStage、Project、Person、WorkEvent、Achievement、Evidence、Wiki 生命周期和一份真实本地 PDF；重复装载不重复创建。删除只接受清单内且仍带同 dataset id 的对象，不自动执行。


## 事实回流接口

- `profile.py`：`POST /api/profile/basics`（basics:name/email/phone/wechat/github/links, expected_revision）；旧非空文本先调用 `/api/profile/organize`（basics, entries, confirmed:true, expected_revision, idempotency_key），同事务归档原文、生成pending候选、更新唯一profile。
- `journey.py`：`POST /api/journey/notes/{id}/correct`（title/content/expected_revision/idempotency_key）；`GET .../history` 保留原件及全部更正；`POST .../candidate`（title/content/entry_type/scope_type/scope_id/promote_to_personal/expected_revision/idempotency_key）。原note可带同job的submission_id；候选固定继承该引用。任职导出在同一读事务输出原文及全部更正正文。
- `editor.py`：`GET /api/editor/materials?job_id=` 只列个人/当前机会有效Wiki及profile；`POST /api/editor/select-facts` 在保存草稿后以CAS和幂等key选择 `{id,revision,section_type}`，可显式include_profile/profile_revision；`GET /api/editor/sources` 返回引用版本和current/updated/withdrawn/removed状态。普通PUT不得伪造来源refs；历史恢复采用冻结版本来源。

错误遵循404不存在、422输入/范围不合法、409版本或幂等冲突。沿用schema v1，无启动时批量迁移。测试：`tests/test_fact_resume.py`、`tests/test_profile_ownership.py`、`tests/test_record_candidates.py`；字段与完整批次验收见 [事实闭环](../../docs/execution/FACT-LOOP.md)。

联系方式扩展：basics必需name/phone/email，可选wechat/github/links；链接必须HTTP(S)，links至多10条。旧三字段请求保留已存在扩展字段。editor/select-facts明确include_profile时同步所有填写的联系方式，允许再次主动更新基础信息；历史版本不变。
