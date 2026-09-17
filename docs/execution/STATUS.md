# 当前状态

最后整理：2026-09-17（Opportunity Batch C仅规划）。本文只维护当前交付范围、现役入口、外部 Gate 与技术债；历史批次的过程和证据留在各自文档。

## Opportunity Batch C — 计划完成，尚未实施，2026-09-17

已按 `$workbench-plan` 读取当前authority、四份Opportunity正本、B最终记录/实际工作树、editor/Profile/applications/PDF代码及B私有inventory；正式计划见 [OPPORTUNITY-BATCH-C](OPPORTUNITY-BATCH-C.md)。

- 目标是每机会懒创建独立工作稿、显式普通版本、Greeting、当前稿/旧版/无简历的一次投递；单事务冻结材料并更新canonical phase。复用纸面编辑器，保留applications，拟显式升级schema3；不迁移editor-main所有权或ResumeUse。
- 计划固定了所有全局稿入口、Profile显式刷新、旧PDF字节复制、特殊版本删除保护、文件操作崩溃恢复，以及自动测试/浏览器/migration/rollback/forward recovery条件。这些均为待实施条件，不是已交付能力。
- 继续以B独立工作树为基线；生产v1状态依据B既有证据，本轮未重测在线状态。后续仅在虚构目录与最新生产备份的隔离恢复副本实施，Production Cutover仍需后续明确授权。
- 本轮仅新增C计划和更新本状态，并同步这两个规划文件到B工作树；未改业务代码、旧审计/目标/A/B记录，未运行测试/浏览器/备份/迁移，未调用workbench-implement。完成计划后停止。

## Opportunity Batch B — 隔离验收通过，2026-09-17

已按用户补充的Company匹配与禁止Production Cutover约束完成 workbench-implement → workbench-review。完整实现、测试、浏览器、迁移与恢复证据见[本批记录](OPPORTUNITY-BATCH-B.md) §11。

- 业务源码交付在 `/Users/frog/Projects/Career-worktrees/batch-b`（`codex/opportunity-b`）；原生产源码目录仅同步B记录和本状态，不回拷新业务代码/dist。现有未提交文档对齐/A改动不计为B。
- canonical Opportunity/Company、元数据与结束动作/CAS/幂等、六View与基础Workspace已实现；旧Job/plan.stage/context.company及旧投递/面试/Offer旁路受控。NFKC+trim+casefold身份匹配保留展示名，不猜别名、不合并主体。
- 最终兼容回归77通过；最后迁移安全/记录候选定向复验21通过（有重叠），typecheck/build通过。原profile基线仍1通过2失败，仅补测试创建Job所需幂等键，未改原revision断言或产品行为。
- 最新生产备份 `Career Data-backups/batch-b-20260917T133523Z` 已真实创建/隔离恢复。v2演练全部旧199行/PDF保全；新增1迁移manifest，2旧机会defer，0条被猜测迁入canonical。v1实际rollback恢复、旧程序拒绝v2、开写后v2 forward recovery和原v1活动/投递回放均已验证。
- 生产PID2994、0.2.0、schema1、数据库物理/逻辑hash、附件及源码/dist保持；无生产业务POST、重启或迁移。生产保留现有投递/面试/Offer能力。
- 本批停止；C具备隔离开发前置，实施尚未开始，当前规划见上节。Production Cutover为后续显式部署授权，不能把隔离B当作完整生产替换。真实AI、无损逆迁移、异机灾备与完整C–G仍未验证/未实现。

## Opportunity Batch A — 2026-09-17

状态：可恢复迁移基线已完成，已按workbench-plan → workbench-implement → workbench-review规划、实施及独立验收；该轮结束时Batch B实施未开始，当前B状态见上节。完整范围、复现命令、manifest与恢复证据见[本批记录](OPPORTUNITY-BATCH-A.md)。

- 新增只读inventory/verify工具，补现有backup/restore目的地保护；schema仍为1，无领域迁移、前端改动或数据清理。两份审计与四份目标文档保持原文。
- 已从实际服务确认生产目录`~/Library/Application Support/Career Data`。真实备份已创建并恢复到新的系统临时目录；SQLite integrity、199条全表记录/ID/hash、冻结快照、版本、Raw/Wiki与1个PDF均一致。
- 旧服务自2026-09-15运行，启动器复用健康进程导致未加载更新源码。已先验证隔离副本启动，再受控重启生产为0.2.0；数据路径与Provider状态不变，逻辑内容和附件不变。现有初始化改变SQLite物理字节，未改业务记录或schema。
- 当前inventory无真实用户决策Gate；G1公司文字冲突、G2面试类型/业务日期未知均关联demo，保留为legacy兼容问题，不自动选值。未带demo标记的ResumeUse引用案例版本/PDF，必须保留；未标记本身不证明真实业务事实。
- 针对性测试9通过；原profile测试再次复现1通过、2失败。保存profile会同步当前全局草稿并提高revision；旧测试仍传0/旧revision而遇到409，第二项把错误JSON当document产生KeyError。读取最新revision的隔离HTTP场景通过；本批未修改profile/editor或旧测试，不宣称全套测试已通过。
- 具备规划并在隔离数据上启动Batch B的安全前置；生产迁移前仍须按届时数据重新盘点、备份和处理真实歧义。当前未验证真实AI、浏览器全流程、迁移/回滚代码或异机灾备。

## Documentation & Agent Alignment — 2026-09-17

当时状态：文档对齐完成；Gap Analysis增量路线已确认，实现Batch A/B及后续批次尚未开始。以下为该轮历史证据，Batch A现状见上节。

- 已对齐authority模块权威、AGENTS/README读取路由及三个Workbench Skill的文档加载方式；产品、Context、Architecture、Journey、Acceptance、Roadmap分别承接目标与验证范围。四份人工确认目标保持原文，AS-IS与Gap Analysis保持历史快照。
- 已区分Current Architecture / Stable Contracts / Target Direction，以及target acceptance与实际测试证据。独立机会稿、唯一Submission/Greeting冻结、real/simulation、当前Research、统一Raw/Patch、领域AI及Timeline等仍是TO-BE，不因文档修改变为已交付。
- 下一批建议：[Gap Analysis §8](../audit/OPPORTUNITY-GAP-ANALYSIS.md)的**A：建立可恢复迁移基线**；先细化允许范围、dry-run/备份恢复验收与冲突处理，不直接进入业务模型切换。
- 已知失败未修复：AS-IS运行71项中69通过、2失败，均在`tests/test_profile_ownership.py`的profile保存后旧revision选材路径；typecheck当时通过。本批未重跑业务测试，也未调整断言或实现。
- 运行身份问题未解决：AS-IS观察runtime自报0.1.0、source为0.2.0，准确加载组合未知。本批未查询生产服务、重启、构建或更改Provider配置；未接真实AI、未操作数据库或用户数据。默认生产备份目录当时为空，恢复能力仍需Batch A核验。
- 文档自审完成：13个允许的Markdown文件、95个本地链接及代码围栏检查通过，`git diff --check`通过；AGENTS为15行，三个Skill各仅修改读取段落，README仅修改文档地图。两份审计、四份目标及业务文件共74个文件hash无变化；任职Journey、产品中的任职/协作/反馈/案例说明和Architecture非本期对象行均保留。未新增业务实现或测试。
- 剩余文档边界：本次范围内未发现未消解的Opportunity目标冲突。未修改的模块README、旧execution记录及两份审计仍保留历史说法；其适用性由authority限定，不覆盖当前目标。Domain §5与UI §6的投递版本读取口径、Offer原件与通用Raw更正边界已在authority说明，目标原文未改。

以下保留2026-09-16交付记录供现状追溯，**不能解释为新Opportunity目标已实现**。其中旧“独立JobPosting待后续”不再是本期目标；`Employment→Stage→Project→…→Wiki`是原交付概括，AS-IS已确认不存在完整连续引用/自动回流链。当前范围按[authority](../00-authority.md)和[Roadmap](../07-roadmap.md)，具体已验证能力按[AS-IS](../audit/AS-IS-system-map.md)。


## 当前交付

[Career OS 结构优化与产品化重构](STRUCTURE-REFACTOR.md) B1—B5 已交付。当前应用以 Opportunity 与 Employment 为两条任务主干：

- Opportunity → Wiki 选材 / Context → 正式简历与 PDF → Submission → 研究、沟通、面试、Offer。
- Employment → Stage → Project → 参与者 / 事件 → Achievement → Evidence → 可确认的 Wiki 候选。

结构化编辑器是唯一可写简历链，旧文字简历只读兼容；状态驱动页面、基础资料、全局反馈和设置页案例装载/删除入口已接入。虚构案例 `career-os-b5-demo-v1` 已保留供用户熟悉，删除仅由用户主动触发。

基础资料支持姓名、邮箱、电话、微信、GitHub 与个人网页，并可同步到当前简历。人工事实闭环已经覆盖原件、候选、确认、修订、撤回、显式选材、预览、正式版本/PDF、投递冻结、原话更正和回流候选。真实 AI 语义质量仍受下述外部 Gate 限制。

## 现役入口与证据

- 启动、配置和模块说明：[服务 README](../../src/workbench/README.md)
- 当前架构和边界：[03-architecture](../03-architecture.md)
- 当前证据索引：[EVIDENCE](EVIDENCE.md)
- 当前最新交付批次：[STRUCTURE-REFACTOR](STRUCTURE-REFACTOR.md)
- 人工事实闭环：[FACT-LOOP](FACT-LOOP.md)

生产入口为 `http://127.0.0.1:8765`；默认数据目录为 `~/Library/Application Support/Career Data`。代码、测试资料和生产数据必须隔离。早期纯文本 MVP 契约已经撤回并归档，不再作为当前 Interface。

## 外部条件 Gate

当前没有已验证的真实 Provider 配置。缺少 `CAREER_AI_API_KEY` / `OPENAI_API_KEY` / `CAREER_AI_MODEL` 时，本地编辑、记录、版本与导出仍可使用，但岗位分析和简历适配的语义质量不能验收。TestProvider 或模拟 HTTP 成功不能代替真实模型调用。

模型、语音、招聘来源和其他外部能力均须逐项使用真实配置与隔离资料验证；不要把密钥发送到聊天，也不因外部能力缺失阻塞独立的本地闭环。

## 当前简化与技术债

- 文件解析、AI 候选提取、自动相关性排序、结构化简历内容 patch 和多 ResumeDocument 尚未完成。
- 细粒度研究快照、独立 JobPosting、EvidenceLink 页/行定位与 Repository Ingestion 仍待后续批次。
- 全局 epoch 采用保守失效；失败或中断的远端任务不自动收费重试。
- 数据量较小时 state 一次读取全部本地记录；有性能证据后再分页或引入索引。
- 备份仍以本地命令行为主，同盘备份不能防整盘损坏；schema 迁移必须先备份并显式按版本执行。
- 数据库登记前后的极端崩溃可能遗留无引用附件；不会形成假成功，但尚无自动孤儿回收。

## 历史交付

按时间保留：[任务工作台首试](TASK-WORKSPACE.md)、[单窗口工作区](FOCUSED-WORKSPACE.md)、[既有工作台本地接入](RESUME-WORKBENCH.md)、[职业 Wiki 与业务对象整合](WIKI-DOMAIN.md)、[冷启动整改](COLD-START-REPAIR.md)、[事实闭环整改](FACT-LOOP.md)。完整早期证据和已撤回的 MVP 契约位于 [archive](../archive/README.md)，仅用于追溯。

仓库记录过的本地提交基线为后端 `71776ce`、前端与验收 `9db7692`；这只说明历史基线，不代表当前工作树已提交、push、deploy 或 publish。
