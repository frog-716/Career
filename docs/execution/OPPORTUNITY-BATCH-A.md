# Opportunity Batch A — 可恢复迁移基线

状态：规划、实施及独立验收完成；停止在Batch A，Batch B未开始。日期：2026-09-17。

## 目标、输入与范围

依据当前用户指令、[authority](../00-authority.md)路由的四份Opportunity目标、[Context合同](../02-context-contract.md)、[Acceptance](../05-acceptance.md) O19/R01–R04及[Gap Analysis Batch A](../audit/OPPORTUNITY-GAP-ANALYSIS.md)。本批只证明迁移前的数据可盘点、可备份、可恢复、运行版本可识别；不交付Batch B或其他领域目标。

允许修改：新增`src/workbench/migration_baseline.py`、`scripts/migration_baseline.py`、`tests/test_migration_baseline.py`；必要时最小修正现有backup的路径/不覆盖保护并补测试；更新服务README、本记录与STATUS。不修改Opportunity、Resume、Submission、前端、Employment/Project、Provider、已有审计、目标正本或`.codex/config.toml`。两个profile测试先复现与定位，除非成为本批必要前置，否则不修实现或旧测试。

生产路径已由`GET /api/state` diagnostics确认：`/Users/frog/Library/Application Support/Career Data`；SQLite为其`workspace.sqlite3`，附件为`artifacts/`。当前PID 12720、cwd为本项目，运行自报0.1.0，源码APP_VERSION为0.2.0。生产备份写代码与生产目录之外的新备份目录；恢复只写新的系统临时目录，绝不覆盖生产或已有目录。真实资料报告只记录ID/引用/hash/分类，不把正文放入仓库。

## Interface与预先固定的验收

CLI：`inventory DATA_DIR --output NEW_JSON`只读盘点；`verify BACKUP_DIR RESTORED_DIR --output NEW_JSON`只读比较。显式路径必需，拒绝缺DB/未知schema/越界或符号链接附件、拒绝报告覆盖或写进受检数据目录。inventory使用sqlite URI mode=ro、query_only、单一读事务，不实例化Store，不执行DDL。报告记录错误及阻塞项，不将demo兼容问题自动升级为用户Gate，也不自动解决非demo业务歧义。

验收先固定如下：

| ID | 可观察结果 |
| --- | --- |
| A01 | 读实际diagnostics、PID/cwd/启动时间与源码hash；在真实备份/隔离恢复后重启已确认服务，记录新PID/0.2.0/相同数据路径及Provider配置状态；不能凭版本字符串认证旧进程 |
| A02 | inventory可重复，schema/计数/完整ID与逐行hash、canonical候选、公司冲突、多投递/Offer、未知轮次、简历/用途/PDF及Raw/Wiki/Candidate引用齐全；读前后生产逻辑内容与附件不变 |
| A03 | 虚构库覆盖多投递/Offer、公司冲突、未知轮次、错类型/缺失引用及损坏/越界附件；demo问题与未标记资料分开；工具不猜迁移结果 |
| A04 | 使用现有backup函数真实生产备份，备份与恢复目标均为新目录；恢复到隔离目录并通过integrity/FK、schema、全表行数/关键ID/逐行内容hash及文件hash比较，覆盖冻结快照和Raw/Wiki引用 |
| A05 | 验证器对被改写的冻结内容、缺行、坏附件等返回失败；拒绝覆盖已有输出/恢复目标；生产目录不成为备份或恢复目的地 |
| A06 | 原profile测试复现1通过/2失败；隔离HTTP场景证明旧revision被409拒绝、读取新revision可选材且扩展联系方式保留，区分测试假设与实际产品缺陷；不扩大Resume重构 |
| A07 | 记录代码/工具版本、真实备份/恢复路径、inventory与验证manifest及实际命令结果；独立审查阶段核对真实文件/DB与diff，不以实施自报替代；停止在Batch A |

错误分层：读取/格式/路径错误失败；数据完整性问题阻止安全迁移；仅demo/legacy语义缺失列兼容问题；非demo归属/历史语义不可推导列待核对Migration Gate，非demo标记本身不证明真实经历。附件/库在盘点期间变化需报告并重取基线，不隐瞒并发变化。

## 顺序与停止条件

1. 固定本计划、工作树既有改动和保护文件hash；复现旧测试。
2. 先建立隔离测试，再实现只读inventory与恢复比较，运行针对性测试。
3. 核对生产路径后执行inventory、现有backup、新目录restore和verify；报告写代码与生产目录之外。
4. 检查无running分析后受控停止旧服务；先用隔离恢复副本验证当前源码启动影响，再启动同路径生产服务，比较前后逻辑记录/附件。若初始化只改变SQLite物理头，也如实记录，不能称文件字节未变。
5. 使用workbench-review独立审查阶段核对规格/工程两轴及真实恢复证据；更新本记录和STATUS。未满足项明确留下，不自动进入Batch B。

## 实施与验收证据

### 修改范围与验收结论

新增只读模块、CLI及7个隔离测试；`backup.py`只补目的地不能嵌入源/备份、不能覆盖已有备份及先验证再建临时目录的保护。更新服务README、本记录及STATUS。未修改业务模型、schema、前端、profile/editor、旧失败测试、Provider、两份审计、四份目标或`.codex/config.toml`。开工时已有的文档对齐改动和配置删除保持原状，不归入本批。

| 验收 | 实际证据与结论 |
| --- | --- |
| A01 | 实际HTTP diagnostics、PID/启动命令、源码hash、隔离启动和生产重启均已核验；新PID 2994，0.2.0，同一生产目录与Provider状态 |
| A02/A03 | 新CLI只读检查schema v1、199行与全部ID/hash、关系及歧义；虚构数据覆盖多投递/Offer、公司冲突、面试Unknown、错类型/缺失引用和越界附件；不执行映射 |
| A04 | 现有backup真实执行；新目录restore真实执行；备份manifest、完整SQL内容及附件比较通过；两端integrity=ok、FK/引用异常0 |
| A05 | 隔离负例分别篡改冻结JSON、删除Submission行、损坏PDF，verify均拒绝；覆盖/重叠路径被拒绝。正向恢复未用Store初始化 |
| A06 | 原文件复现1通过/2失败；最新revision选材、再次刷新及保留旧客户端未传的扩展联系方式通过。没有为了变绿改变产品目标 |
| A07 | 命令输出、源码hash、私有manifest、恢复报告与本记录已保存；独立审查阶段重新运行真实verify和针对性测试，核对本批diff及保护文件 |

### 生产身份、数据与备份

- 生产目录由实际`GET http://127.0.0.1:8765/api/state`确认：`/Users/frog/Library/Application Support/Career Data`；数据库`workspace.sqlite3`、附件`artifacts/`。未更换生产路径。
- 旧PID 12720始于2026-09-15 16:12:16，命令来自本项目`scripts/run.py`。源码随后更新为0.2.0，启动器对任何健康版本直接复用，没有reload；因此旧进程保持0.1.0。旧进程完整内存代码/历史Git组合无法追溯，未用版本字符串猜测。当前进程于2026-09-17 19:50:11启动为0.2.0，证据另记录实际源码SHA256与启动命令；Git HEAD为`368af740fd2b17e5718ce31675bf526df4591347`，工作树有既有未提交改动。
- 已先确认没有running分析，Provider为real但未配置，隔离启动诊断与原服务一致；全程无真实模型请求。仅受控停止/启动服务，运行PID/log发生变化。
- **生产逻辑记录、schema与附件未修改；SQLite物理文件字节已改变。** 新进程既有Store初始化会执行`PRAGMA user_version=1`等启动SQL；隔离副本先验证了此行为，生产前后全表/epoch/历史/附件的逻辑快照相同。不能将“业务数据不变”写成“数据库文件未写入”。

真实产物（均在仓库和生产目录之外）：

| 产物 | 实际位置 |
| --- | --- |
| 备份 | `/Users/frog/Library/Application Support/Career Data-backups/batch-a-20260917T114422Z` |
| 未启动的恢复副本 | `/private/var/folders/cl/wtl8p1w508g43s7b4wqsr5gh0000gn/T/career-batch-a-restore-w8ljjchg/restored` |
| 独立启动演练副本 | `/private/var/folders/cl/wtl8p1w508g43s7b4wqsr5gh0000gn/T/career-batch-a-boot-0lthfu81/probe` |
| 私有证据目录 | `/Users/frog/Library/Application Support/Career Migration Audits/batch-a-20260917T114422Z` |

证据目录中的`batch-a-manifest.json`为索引；`production-before.json`、`production-pre-restart.json`、`production-after-restart.json`记录生产变化；`backup-final.json`/`restored-final.json`为最终inventory；`restore-review.json`为独立验收比较；`preserved-materials.json`列关键材料ID与冻结字段hash；`runtime-before.json`/`runtime-after.json`及`startup-probe.json`记录运行身份；`test-results.json`保留实际测试输出。报告不复制正文，目录0700、JSON报告0600。首次44引用检查后补齐旧resume/job和note/submission等边，最终检查49条；两次报告保留，不覆盖旧证据。

### 恢复结果与dry-run

SQL共199行：meta 1、current 24、records 27、applications 1、revisions 146。备份与恢复副本均`integrity_check=ok`，FK违规0，49条列明的当前引用异常0。所有行包括原始JSON的hash一致；1份Submission的resume/job/opportunity/artifact冻结快照、1个editor_version、2个ResumeUse、1份PDF、3个knowledge_source、5个journey_note、1个Wiki、3个Candidate以及146条历史revision均保全。Candidate状态保持原值，没有重新确认或回放。历史行全部比较，但未逐一认证历史引用的业务语义。

逻辑快照SHA256：`0850e98b047f8e70b03a5b4ee7dec195956270f26a214fc94dcde109491ceae8`。生产SQLite物理hash从`c6bf614deb82cdc2978ca98f56e878c85b6582d46f9b51a60b841a7b291ec739`变为`8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`；源库与备份SQLite物理hash本来也可因SQLite backup页头重建而不同，恢复副本则在启动前与备份manifest字节一致。

- canonical候选2个：两个旧Job，只有其中1个已有materialized Opportunity；另一项是候选/当前兼容投影，未补写实体。
- 多Submission=0、多Offer=0、完整性异常=0；`migration_gates=[]`是本次盘点的结果，不是对所有历史业务事实的确认，也不授权迁移。
- **G1为demo/legacy兼容问题**：`demo-b5-job`公司文字与`demo-b5-company`名称冲突；保留两值和关联，不合并、不选主体。
- **G2为demo/legacy兼容问题**：`demo-b5-interview-activity`没有real/simulation及可靠的面试/确认日期。旧occurred_at是现有记录字段，未认定为目标业务日期；plan与Offer的历史阶段差异仍保留。不默认real、不推导当前phase/result。
- 未带demo标记的ResumeUse引用案例版本、PDF和方向，报告保留`cross_dataset_reference`；不能据demo标签删掉被其他记录使用的材料。
- 当前全局editor_draft归属仍为Unknown，旧文字稿按原job关联保留；没有将其自动指派给机会。该归属不阻塞本批备份恢复，未来涉及所有权时另按真实数据核对。

### 两项profile/editor失败

复现命令（仅临时虚构资料）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest tests/test_profile_ownership.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest tests/test_migration_baseline.py tests/test_backup.py -q -p no:cacheprovider
```

独立验收阶段实际为原测试`2 failed, 1 passed in 0.26s`；本批/备份测试`9 passed in 0.50s`。

根因链：`profile.py:_save`调用`editor.py:sync_profile_to_draft`同步当前全局稿，`_save_document`提高revision；`select_facts`按expected_revision保护草稿。旧测试在profile保存后仍硬编码expected_revision=0，第40行预期200实际409；第54行未检查HTTP状态，把同一个409错误体当作有document的数据而KeyError。第二个测试后半段还会复用再次保存profile前的草稿revision，同属旧假设。新隔离HTTP测试验证旧revision被拒绝、GET最新草稿后选材成功、再次更新基础资料后用新revision成功、旧三字段客户端保留wechat/github/links。

结论限定为：**这两个断言失效源于旧revision假设，不能据此认定CAS产品行为缺陷。** 多文档目标下profile刷新机制仍待后续批次实现，本批不将当前全局自动同步升级为目标设计，也没有降低CAS或改旧断言。前端源码使用当前revision并先flushSave，未本轮验收多窗口实际交互，不宣称所有编辑器行为已验证。全套测试仍有已知失败。

### 独立审查、局限与停止点

按workbench-review由当前主Agent在独立阶段检查实际diff，两轴均无剩余Batch A阻塞发现，不声称另有独立人员/Agent签字。规格轴核对A01–A07、O19历史保护部分及恢复基础要求；**没有宣称O19全部目标能力或批次B–H已通过**。规范轴核对只读连接、无Store初始化、显式路径、报告不覆盖、backup事务/附件清单、恢复隔离与全行hash，以及旧文档/配置保护。

审查过程中补强了最小证据缺口：旧resume/job与note/submission等引用需列入inventory，已补齐；损坏PDF负例原先叠加在已坏SQL上，现改用另一份完好恢复副本单独损坏，同时验证缺行与错类型引用。均属预先约定A02/A03/A05，没有扩展业务实现。

仍未验证：实际canonical迁移/rollback实现、完整浏览器求职流程、多窗口编辑器竞争、真实AI语义、异机/整盘灾难恢复、外部进程同时改附件或抢占目标路径的极端并发。临时恢复目录可能被系统回收，持久备份与证据已留在Application Support。旧进程完整加载组合及未标记资料的真实业务归属仍不可追溯/Unknown。

**Batch B具备规划和隔离开发的安全前置。** 真正生产迁移前需重取届时inventory/备份，验证已实现的迁移及回滚，遇到真实资料不可推导再报告Gate；本次demo问题不自动升级为用户产品Gate，也没有被自动决策。本轮到此停止，不进入Batch B。
