# Career 本地服务

当前 Production 已部署通过最终 review 的 **Batch F Opportunity MVP**，运行版本 `0.7.0-batch-f`、schema v6。正式代码位于 `/Users/frog/Projects/Career`，数据仍位于外部 `/Users/frog/Library/Application Support/Career Data`；v1→v6 migration、备份、恢复、完整性与浏览器 smoke 证据见 [Batch F §23](../../docs/execution/OPPORTUNITY-BATCH-F.md#23-opportunity-mvp-production-cutover2026-09-18)。

安装并启动（项目根目录）：

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python scripts/macos_app.py start --no-browser
```

入口 http://127.0.0.1:8765；启动器复用已有服务。`scripts/run.py` 跟随系统默认浏览器，`macos/Career.app` 则显式使用 Google Chrome，不修改 macOS 全局设置。单进程运行，不使用多 worker。
生产默认 `~/Library/Application Support/Career Data`；用 `CAREER_DATA_DIR` 指向代码目录之外可更换位置。代码不含任何用户资料，生产与合成测试数据分开。本代码新空库为 SQLite user_version=6，已有库只接受 v6，v1–v5 启动前只读检查并拒绝，不隐式迁移。备份 manifest.schemaVersion=1 是包格式，不是数据库版本。

## 模块职责与接口

- `core.Store`：current 及 revisions 正本写入、Context 白名单、分析审计、提案/版本/投递/反馈事务。页面仅调 HTTP Service。`context/analyze` 每轮同事务读取基础资料、指定 active JD 和显式选择的当前 Wiki；个人目标/约束必选，其余每轮重选。不读取原件、候选、历史、反馈、简历或旧结果。profile 在用户显式整理后仅维护身份字段；旧混合资料归档及候选确认不会形成重复当前正本。全局 epoch 让资料/JD任何修改使既有分析过期，简历草稿另查 revision。
- `knowledge`：不可变来源、候选整理/确认、Wiki 当前修订/撤回与历史；来源同 scope 校验；个人/机会/任职隔离。仅个人或当前机会有效条目能进入求职 packet。
- `domain`：公司/组织树、求职周期/方向、机会关系、固定简历版本用途。用途不创建实际投递；当前实际投递只能走 Opportunity scoped `RecordSubmitted`。接口见 [Wiki 与业务对象整合](../../docs/execution/WIKI-DOMAIN.md)。
- `opportunity`：current JSON 中唯一 canonical Opportunity，Company 由 company_id 实时读取；Create/Update/End 同事务 CAS/幂等。旧 Job/plan.stage/context.company_id 冻结，legacy 未决对象只读。历史 Submission 快照保持原文，新投递由 `submission` 模块冻结材料并推进阶段。
- `employment` / `work`：公开的 Employment 主身份和旧 `journey_episode` 兼容映射；EmploymentStage、Project、Person、WorkEvent、Achievement、Evidence 及其多对多关系。工作成果不会自动写入个人 Wiki。
- `communication`：Opportunity scoped Communication 的唯一新写入口；Create/Update/Archive 使用幂等命令与记录级 CAS。旧 typed Communication 原 ID 只读投影并可由用户显式核对升级；不复制 `journey_note`，不改变 Opportunity 生命周期。
- `interview`：Opportunity scoped Real/Simulation、柔性 Preparation、current-only Raw/Final Review、Context Pack 与 real-only Research Patch。`GenerateFinalReview` 和 `GenerateResearchPatch` 是两个独立动作；Simulation 在 service/storage/HTTP/UI 均无 Patch 能力。
- `offer`：Opportunity scoped 唯一 current Offer。RecordOffer 原子创建 `offer_format=2` 并推进 phase；UpdateOffer 原位 CAS 更新明确确认的当前条件；AcceptOffer 只结束 Opportunity。legacy typed Offer 默认只读，必须完整核对后同 ID 升级。
- `timeline`：按请求从 Opportunity、Submission、未归档 Communication 和 Interview 生成只读投影；不写 Timeline 事实表。
- `engagement`：ResearchSnapshot、Interview、Offer 及旧 typed Communication 的兼容读取；旧 Communication 新建入口停写。
- `context`：唯一 Context Compiler，输出 schema v2 的来源 revision/hash、用途、未知/冲突/遗漏、策略版本和预算；读取当前 canonical JD/Company 身份，移除旧目录 description 的隐式正文；资料和身份修改使预览/结果过期。
- `providers`：只收实际 payload；Provider 不持有 Store、数据库或文件工具。远端不继承会话。每轮 payload 在本地运行审计保存，可在 UI 查看；语义正确性需人工审阅。
- `artifacts`：PDF / 截图原子写入与 sha256；数据库只存相对路径、metadata和关系。已有投递关联不可变版本/PDF与岗位快照。
- `app`：仅回环 Host、同源 Origin、写入自定义 header、请求大小上限；静态服务仅 frontend/dist，不暴露数据目录。
- `backup`：在 SQLite 稳定写入窗口内生成在线一致性快照和关联附件哈希清单；备份、恢复都会逐条核对数据库 artifact 引用、清单、文件与 sha256，并拒绝缺失、哈希不符、清单遗漏或孤儿附件。恢复只允许不存在的新目录，现有 schemaVersion 1 清单仍可读取。
- `demo`：幂等装载或删除带固定 dataset id 的虚构全链路案例；不会覆盖 profile、现有机会、简历或附件，删除前逐项核对归属。
- `journey`：机会辅助计划仅保存下一行动/提醒日期，独立 CAS；stage 只读。旧 note/typed interview/offer 新记入口停写，新业务动作由 `communication` / `interview` / `offer` 接管；已有记录更正/候选/历史继续可用，任职分支不变。

HTTP 路由、错误与并发语义以当前模块实现和对应测试为准，跨模块边界见 [结构优化与产品化重构](../../docs/execution/STRUCTURE-REFACTOR.md)。expected_revision 冲突返回409；提案原子检查 epoch+draft revision 并保存 applied_result实现幂等。版本按草稿revision幂等、投递按用户动作幂等键。反馈补充只追加；数据不进入AI。

## AI 模型配置

默认真实模式，缺配置仍可启动、编辑和导出；AI 操作会明确提示尚未配置模型。当前正式入口是 Career 的“设置 → AI 模型”：可维护多个 OpenAI-compatible 配置、测试连接、选择唯一默认模型并删除配置。模型配置只在数据库保存 `api_key_ref`，真实 API Key 由 macOS Keychain 持有；API response、普通业务备份、Context、Prompt、日志和前端 localStorage 都不会返回或保存完整 Key。

编辑配置时 API Key 留空表示保留旧 Key，填写新 Key 才替换。删除当前默认模型必须明确确认，删除后不自动切换其它模型。没有默认模型时人工资料、简历、投递、面试和记录功能继续可用。

旧环境变量 Provider 仅为测试和诊断兼容保留，不再作为业务 LLM 的配置或调用入口；旧 `/api/analysis` 也统一经 `ModelGateway`。生产配置请在“设置 → AI 模型”中保存到 macOS Keychain。支持遵循 Chat Completions JSON 对象格式的服务；开发模型配置不代表运行时模型授权。官方请求参考：[Chat Completions](https://platform.openai.com/docs/api-reference/chat/create)。远端请求仅在预览后点击发送，包包括当前基础资料、显式选择的当前 Wiki、该岗位 JD 和本轮指令。API Key 不进入业务包、日志、UI 或浏览器存储；不读宿主登录凭据。

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

迁移前使用只读盘点与恢复比较（schema v1–v6；必须显式传入已核对的路径）：

```sh
.venv/bin/python scripts/migration_baseline.py inventory /绝对路径/现有数据目录 --output /绝对路径/独立证据目录/new-inventory.json
.venv/bin/python scripts/migration_baseline.py verify /绝对路径/备份目录 /绝对路径/隔离恢复目录 --output /绝对路径/独立证据目录/new-verification.json
```

证据目录需预先存在，报告以0600新建，拒绝覆盖或写入受检目录。inventory不初始化Store，不执行DDL；输出schema/全表计数、ID与逐行hash、Opportunity映射候选、公司/多投递/多Offer/面试语义歧义、简历和资料引用及附件hash。历史revisions逐行保全，但不声称已验证每条历史引用的业务语义。退出码0仅说明本次完整性检查通过，**不是迁移许可**；仍需检查`migration_gates`和`demo_legacy_findings`，不能自动决定归属、合并或删除。

backup拒绝把备份写入源数据目录或覆盖已存在备份；restore只接受新目录，并拒绝恢复到备份内部。verify比较全部表行/冻结内容、schema及附件与原备份manifest；恢复副本先保持未启动状态完成此比较，再另建副本做启动演练。现有Store启动初始化可能改变SQLite物理hash；逻辑hash与物理hash分开记录。

针对性测试：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest tests/test_migration_baseline.py tests/test_backup.py -q -p no:cacheprovider`。真实生产备份、恢复与运行版本核验见[Opportunity Batch A](../../docs/execution/OPPORTUNITY-BATCH-A.md)。本机启动脚本会复用健康服务，源码更新后需停止旧进程再启动；仅看到源码版本不能证明长驻服务已经加载。

## Batch B 保留接口与前置 v1→v2 迁移

- `GET /api/opportunities?view=all|resume|submitted|interview|offer|ended`，`GET /api/opportunities/{id}`：唯一当前 DTO 或明确 legacy 只读 DTO。canonical ID 和旧 alias 均可读。
- `POST /api/opportunities`：company_id/company_name 二选一、title、jd、可选 action_url、idempotency_key。Company 按 trim/NFKC/casefold 匹配；多主体歧义 409，展示名不归一化。新建默认 resume/active。
- `POST /api/opportunities/{id}`：元数据、expected_revision、idempotency_key；不接受 phase/result/日期。旧 `/jobs` 元数据适配进入同一动作，没有第二份 Job 写入。
- `POST /api/opportunities/{id}/end`：result、expected_revision、idempotency_key；accepted 还需要同机会唯一且已明确确认的 offer_id。保留 phase/阶段日，不创建 Employment。
- 新 `/applications` 返回 409 `submission_action_pending`，已有请求仍重放冻结 JSON。`applications/{id}/status` 停写；typed 与 job note 的 interview/offer 新建返回 `lifecycle_action_pending`，原件/更正/候选和幂等读取保留。旧整包 demo load/remove 在副作用前拒绝。
- 旧简历正文及 editor-main 只读；C 写入仅接受明确所属机会的 ResumeDocument，见下文。

先把最新完整生产备份恢复到 **系统临时目录下的不存在目录**；以下路径全部是隔离副本。不要把正式 Career Data 或指向它的链接传给 apply。报告目录预先建立，报告拒绝覆盖，apply 在修改前预留报告文件。

```sh
.venv/bin/python -B scripts/migrate_opportunity.py dry-run /系统临时目录/隔离副本 --output /独立证据目录/plan.json
.venv/bin/python -B scripts/migrate_opportunity.py apply /系统临时目录/隔离副本 --plan /独立证据目录/plan.json --output /独立证据目录/apply.json
.venv/bin/python -B scripts/migrate_opportunity.py verify /系统临时目录/隔离副本 --output /独立证据目录/verify.json
```

dry-run 默认逐 Job `defer_legacy`，不根据记录存在或 demo 猜 phase/result。明确迁入需给出 confirmed/reason/company/phase/result 及可核对日期；未知日期保持 null。source_snapshot_sha256 绑定全部原行/schema/附件；同迁移输入重跑只回放，不覆盖 v2 新写入。迁移事务保存 before-image，旧实体/投递/版本/附件/历史逐行校验，user_version 显式升 2；不新增业务表。apply 仅接受系统临时目录的独立普通数据库文件，拒绝符号/硬链接。

开写前 rollback 是备份恢复到另一个新目录并使用匹配 v1 代码；开写后应备份 v2 并 forward recover，不能把 user_version 改回 1 或用旧备份抹掉新增数据。本批不提供无损逆迁移，也不执行生产部署。实际证据及测试命令见[Batch B](../../docs/execution/OPPORTUNITY-BATCH-B.md)。

## 事实回流接口

- `profile.py`：`POST /api/profile/basics`（basics:name/email/phone/wechat/github/links, expected_revision）；旧非空文本先调用 `/api/profile/organize`（basics, entries, confirmed:true, expected_revision, idempotency_key），同事务归档原文、生成pending候选、更新唯一profile。
- `journey.py`：`POST /api/journey/notes/{id}/correct`（title/content/expected_revision/idempotency_key）；`GET .../history` 保留原件及全部更正；`POST .../candidate`（title/content/entry_type/scope_type/scope_id/promote_to_personal/expected_revision/idempotency_key）。原note可带同job的submission_id；候选固定继承该引用。任职导出在同一读事务输出原文及全部更正正文。
- `resume_documents.py`：`GET /api/resume-documents/{did}/materials` 只列个人/当前机会有效Wiki及profile；`POST /api/resume-documents/{did}/select-facts` 在保存草稿后以CAS和幂等key选择 `{id,revision,section_type}`，可显式include_profile/profile_revision；`GET /api/resume-documents/{did}/sources` 返回引用版本和current/updated/withdrawn/removed状态。普通PUT不得伪造来源refs；历史恢复采用冻结版本来源。

错误遵循404不存在、422输入/范围不合法、409版本或幂等冲突。现役 runtime 使用 schema v6，无启动时批量迁移；本节接口最初在 schema v3 批次建立。测试：`tests/test_fact_resume.py`、`tests/test_profile_ownership.py`、`tests/test_record_candidates.py`；字段与完整批次验收见 [事实闭环](../../docs/execution/FACT-LOOP.md)。

联系方式扩展：basics必需name/phone/email，可选wechat/github/links；链接必须HTTP(S)，links至多10条。旧三字段请求保留已存在扩展字段。resume-documents/{did}/select-facts明确include_profile时同步所有填写的联系方式，允许再次主动更新基础信息；历史版本不变。

## Batch C：独立工作稿与一次投递

Batch C runtime 只接受v3空库或经显式迁移的隔离副本；不会启动时迁移v1/v2。当前 Production 已完成后续完整迁移链并使用 schema v6；B迁移CLI只产生v2，完成其verify后再执行C迁移。

- `GET /api/resume-documents`：按最近编辑排序的目录（did、opportunity_id、公司/岗位和saved_at），不自动选择/创建文档。
- `GET /api/opportunities/{oid}/resume`：返回所属稿或document:null；`POST .../resume/start`：expected_opportunity_revision/idempotency_key/source，来源仅blank、version（source_version_id/source_document_hash）、legacy_draft（source_revision/source_hash）。来源复制不迁移所有权，外部JSON导入不支持。
- `GET/PUT /api/resume-documents/{did}`：独立当前结构与CAS，PUT为document/expected_revision；current-only，不创建ResumeVersion或全量autosave历史。
- `GET .../materials`、`GET .../sources`、`POST .../select-facts`：owner推导资料范围，Profile/Wiki必须显式选入；Profile保存不再同步任何工作稿。
- `GET/POST .../versions`：仅显式保存普通版；POST需document/expected_revision/name/pdf_base64/idempotency_key。`GET/DELETE .../versions/{vid}`、`POST .../restore`（version_id/expected_revision/idempotency_key）只操作本稿版本；恢复只更新当前稿。共享引用阻止删除；特殊投递版永久不可改/删。
- `POST /api/opportunities/{oid}/greeting`：content（可null/空串）、expected_revision、idempotency_key；当前值投递后仍可修改。
- `POST /api/opportunities/{oid}/submitted`：expected_revision/idempotency_key/resume。resume.mode=none、draft（did/CAS/结构/PDF）或version（source_version_id/document hash/artifact hash）。同事务冻结Submission及Greeting、创建独立特殊版/PDF（none不制造材料）、推进phase/date；同键重放，异键不能第二次。后期/已结束不借补录回退阶段。
- 全局`/api/editor`和`/api/editor/versions`只读兼容来源；所有旧写入口409，`job_id`不能选中全局可写稿。旧ResumeUse及其PDF保持原引用。

`resume_artifacts.py`使用SQLite写锁、私有staging、fsync、atomic rename、hash检查。DB引用是唯一提交判据；启动/备份检查完整性，未提交C文件移动到resume-quarantine，既有legacy文件不删除。无通用Artifact WAL/operation journal；所有移动在数据库写锁内，不与另一个提交抢文件。已提交PDF缺失/hash错误时fail closed，不能给出有效备份或投递读取。

```sh
.venv/bin/python scripts/migrate_resume.py dry-run /系统临时目录/隔离v2副本 --output /独立证据目录/c-plan.json
.venv/bin/python scripts/migrate_resume.py apply /系统临时目录/隔离v2副本 --plan /独立证据目录/c-plan.json --output /独立证据目录/c-apply.json
.venv/bin/python scripts/migrate_resume.py verify /系统临时目录/隔离v3副本 --output /独立证据目录/c-verify.json
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```

C迁移保留旧applications六列原值/JSON原字节，只追加明确canonical槽位；无法关联的legacy保留null且新写入不能借null绕过唯一性。真实多投递/关联冲突停止迁移；不批量建稿。开写前恢复pre-C v2备份到新目录，开写后备份v3做forward recovery；不降schema、不逆向覆盖生产。实际证据见[Batch C](../../docs/execution/OPPORTUNITY-BATCH-C.md)。

## Batch D：Communication 与 Timeline 第一阶段

- `POST /api/opportunities/{oid}/communications`：仅 active + submitted canonical Opportunity 可新建；必填 type（text/phone/other）、occurred_on、content、idempotency_key。不会推进或结束 Opportunity。
- `GET /api/opportunities/{oid}/communications[/{cid}]`：默认不返回 archived；legacy typed Communication 保留原 ID、未知 type 不猜测，关联 JourneyNote 时读取当前更正正文。
- `PUT /api/opportunities/{oid}/communications/{cid}`：按 expected_revision CAS 更新。已结束 Opportunity 仍允许更正历史；legacy 只读 Opportunity 只读不可改。
- `POST /api/opportunities/{oid}/communications/{cid}/delete`：产品表现为删除，底层只设置最小 `archived/archived_at`。不提供回收站、恢复 UI、通用软删除或生命周期联动。
- `GET /api/opportunities/{oid}/timeline`：即时投影 Opportunity 创建、明确 canonical Submission 和可见 Communication；未知日期单列，不猜时间。没有 `timeline_event` 表或第二份事实。
- 旧 `/api/opportunity-activity/communication` 和 Job scope `journey_note.kind=communication` 新建返回 `communication_action_required`；旧记录继续读取，已被 typed Communication 引用的 JourneyNote 不再接受单独更正。Employment scope 不受影响。

迁移只在 v3 隔离副本执行；它盘点 legacy typed / note-only / 重复原文引用、owner 可解析性与 Submission 投影候选，不重写旧 Communication，只写迁移 manifest 并把 user_version 升至 4：

```sh
.venv/bin/python -B scripts/migrate_communication.py dry-run /系统临时目录/隔离v3副本 --output /独立证据目录/d-plan.json
.venv/bin/python -B scripts/migrate_communication.py apply /系统临时目录/隔离v3副本 --plan /独立证据目录/d-plan.json --output /独立证据目录/d-apply.json
.venv/bin/python -B scripts/migrate_communication.py verify /系统临时目录/隔离v4副本 --output /独立证据目录/d-verify.json
```

开写前 rollback 是恢复 pre-D v3 备份并使用匹配 v3 运行时；v4 开写后只允许备份并 forward recover 到新的 v4 目录，不降 schema。实际证据、删除策略判断与浏览器验收见[Batch D](../../docs/execution/OPPORTUNITY-BATCH-D.md)。

## Batch E：完整 Interview Vertical

- `POST /api/opportunities/{oid}/interviews/real` 明确确认真实面试；无日期为 pending，有日期为 scheduled。只有首轮从 submitted 原子推进 Opportunity 到 interview，并以服务端确认日写 `phase_changed_on`。
- 同一 Interview ID 通过 `schedule`、`pending`、`complete`、`cancel` 改状态；完成、改期和取消不改变 Opportunity phase/result。Simulation 只能由同机会 real 的 `/simulations` 创建。
- Real 独占一份柔性 current Preparation；Real/Simulation 各自拥有 current-only Raw 和固定五块 Final Review，全部使用 CAS/幂等，不保存 AI 历史版本。
- `generate-final-review` 支持 real/simulation，只返回待编辑五块建议且不产生 Patch；`generate-research-patch` 只支持 real，只创建 pending Proposal。用户明确 edit/accept/reject 后，accept 才原子写入当前 OpportunityResearch。
- Interview Context 只读取实际唯一 Submission 的冻结简历或明确“本次无简历”，以及显式选择的 Communication/Wiki/历史 Final Review；不读取当前 ResumeDocument、未选择 Raw、Feedback 或任职私密备注。
- legacy typed Interview 保持 Unknown/只读；专门 `upgrade` 动作要求用户明确 type/name/status/日期及 simulation parent，保留同 ID 与 provenance，不按名称或旧日期猜测。
- Timeline 仅投影各 Session；archived Communication 仍可作为 Interview 稳定来源读取。旧 Interview JourneyNote 新建、被引用 Note 的 correction/candidate 均被 Domain Action 门禁拦截。

v4→v5 migration 只增加四个 owner 唯一索引、hash-bound manifest 和 schema fence，不重写旧 Interview 或其它业务对象：

```sh
.venv/bin/python -B scripts/migrate_interview.py dry-run /系统临时目录/隔离v4副本 --output /独立证据目录/e-plan.json
.venv/bin/python -B scripts/migrate_interview.py apply /系统临时目录/隔离v4副本 --plan /独立证据目录/e-plan.json --output /独立证据目录/e-apply.json
.venv/bin/python -B scripts/migrate_interview.py verify /系统临时目录/隔离v5副本 --output /独立证据目录/e-verify.json
```

开写前 rollback 恢复 pre-E v4 备份并使用匹配 v4 runtime；v5 开写后只允许备份并 forward recover 到新的 v5 目录。Production Cutover、真实 AI、Offer、通用 Raw/Patch 平台和 Employment/Project 变更不属于本批。实际证据见[Batch E](../../docs/execution/OPPORTUNITY-BATCH-E.md)。

## Batch F：Offer Vertical

- `POST /api/opportunities/{oid}/offer`：仅 active 的 submitted/interview Opportunity 可记录现实 Offer；同事务创建唯一 `offer_format=2` 记录、推进 phase、写阶段日和 `confirmed_offer_id`。`offered_role_title`、location 等条件只保存用户提交值，不从 Opportunity/JD/Research/Communication 补值。
- `GET /api/opportunities/{oid}/offer` 与 `PUT .../offer/{offer_id}`：读取或 CAS 更新一份 current Offer。terms 是文本事实，薪酬只分保证现金、浮动现金、权益、一次性项目和说明，不计算总包、不猜币种、不生成 OfferVersion。
- `POST .../offer/{offer_id}/accept`：校验 Opportunity 与 Offer 双 revision，只写 `Opportunity.result=accepted`；不创建或修改 Employment/Project。旧 `/end accepted` 仅委托同一实现，legacy Offer 未显式升级时拒绝。
- `CommunicationEvent.purpose=negotiation` 复用 Batch D 对象、归档与 CAS；仅 active offer + canonical Offer 可新建。沟通不会修改 Offer 条件、phase 或 result。
- legacy typed Offer 及 note-only 继续 Unknown/只读；typed 仅能用明确 received_on、完整 current terms、hash 与确认标记同 ID 升级并保存一次 provenance。
- Timeline 即时投影 current Offer、未归档谈薪和 Opportunity result，不写 Timeline 事实。ended Workspace 保留 Submission、Interview、Offer 与 Communication 历史。

F runtime 只接受 schema v6。v5→v6 迁移只写一条 hash-bound migration manifest 并更新 `PRAGMA user_version`，不改业务对象、Offer terms 或 SQLite schema objects。冻结 E runtime 只接受 v5，因此不能打开 v6 执行旧 `/end accepted`。

```sh
.venv/bin/python -B scripts/migrate_offer.py dry-run /系统临时目录/隔离v5副本 --output /独立证据目录/f-plan.json
.venv/bin/python -B scripts/migrate_offer.py apply /系统临时目录/隔离v5副本 --plan /独立证据目录/f-plan.json --output /独立证据目录/f-apply.json
.venv/bin/python -B scripts/migrate_offer.py verify /系统临时目录/隔离v6副本 --output /独立证据目录/f-verify.json
```

开写前 rollback 是恢复 pre-F v5 备份并使用冻结 E runtime；v6 开写后只允许备份并 forward recover 到新 v6 目录。Batch F 隔离验收当时仍需单独授权 Production Cutover；该 cutover 现已完成，见 [Batch F §23](../../docs/execution/OPPORTUNITY-BATCH-F.md#23-opportunity-mvp-production-cutover2026-09-18)。Offer Comparison、真实 AI/AI-Config、Employment/Project 和 Compensation Engine 不属于本批。
