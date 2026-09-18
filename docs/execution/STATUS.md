# 当前状态

最后整理：2026-09-18（Opportunity MVP 已从最终 Batch F worktree 完成 Production Cutover；现役 runtime 为 `0.7.0-batch-f`、schema v6）。本文只维护当前交付范围、现役入口、外部 Gate 与技术债；历史批次的过程和证据留在各自文档。

## Opportunity Enhancement Sprint — 已实现并部署，2026-09-18

Sidebar 拖拽排序、AI-Config/Keychain/ModelGateway、Interview/Resume/Research AI 增强已完成；完整范围和证据见 [Enhancement Sprint](OPPORTUNITY-ENHANCEMENT-SPRINT.md)。Production 已备份并以当前源码重启，真实 AI 仍因没有用户配置而未做语义验收。

## Opportunity MVP Production Cutover — 成功，2026-09-18

完整部署证据见 [Batch F §23](OPPORTUNITY-BATCH-F.md#23-opportunity-mvp-production-cutover2026-09-18)。

- 2026-09-18 18:27（Asia/Shanghai）正式启动 `0.7.0-batch-f` / schema v6；唯一 writer 为 PID `43589`，端口 `127.0.0.1:8765`，数据目录仍是 `/Users/frog/Library/Application Support/Career Data`。
- 部署来源固定为 `/Users/frog/Projects/Career-worktrees/batch-f`、commit `eafacb8427d80b36c5d569813157a55380c1d4bd` 及其已验收工作树；正式源码与 frontend dist 已由该工作树构建和核对，没有从旧 HEAD 重拼。
- 最终回滚点 `PRE_CUTOVER_BACKUP` 为 `/Users/frog/Library/Application Support/Career Data-backups/pre-cutover-20260918T101916Z`；独立恢复验证 `verified=true`、`differences=[]`。旧 v1 数据目录另完整保留于 `/Users/frog/Library/Application Support/Career Data-pre-cutover-v1-20260918T101916Z`，逻辑 snapshot 与切换前一致。
- 在最终备份的系统临时恢复副本严格执行 v1→v2→v3→v4→v5→v6，每段均 dry-run/apply/verify；五次 verify 均 `differences=[]`。无真实 Migration Gate；两个旧 Job 保持 legacy/defer，demo 公司冲突与 Interview 语义未知保持待核对，没有自动猜测。
- v6 切换后 integrity `ok`、外键无异常；原 `current=24/applications=1/records=27/revisions=146` 全部业务行保留，新增仅五条 migration manifest。Submission 六个原列及冻结 Resume/Artifact/Job/Opportunity snapshot 逐字节一致，ResumeVersion、PDF hash、Communication、Interview、Offer、Wiki/Candidate、Employment/Project 均核对通过。
- Production 浏览器只读 smoke 已通过六个 Pipeline View、Opportunity Workspace、统一 Resume Workspace、Timeline、Wiki、Employment/Project 与 390×844；legacy 保持 Unknown，console error/warning 为 0。验收没有业务 POST，数据库 snapshot 前后相同；唯一受控浏览器 tab 已关闭。
- 当前基础业务可以正式使用；真实 AI/AI-Config、Offer Comparison、深度 Research 与异机灾备仍未完成。本次没有用真实用户 Opportunity 重放完整写链，也没有实际触发 rollback。

## Opportunity MVP Finalization — 隔离实施与验收通过，2026-09-18

完整记录见 [Batch F §22](OPPORTUNITY-BATCH-F.md#22-opportunity-mvp-finalization2026-09-18)。

- 产品表面已收敛为唯一 Opportunity 管线、Opportunity Workspace 与一个多文档简历工作台；独立面试/足迹入口从主导航隐藏，旧深链接与历史资料继续兼容读取。“今天”使用 canonical Opportunity 当前状态，不再把 JourneyPlan 作为求职状态入口。
- Workspace 先显示当前动作，再显示岗位情报、冻结投递材料和纯投影 Timeline；面试区聚焦当前/下一轮，用户不需要理解 Raw、Patch、ContextSnapshot、schema 或 revision。没有真实模型也可手工完成准备、模拟资料包外带、记录和复盘。
- 实际浏览器完整走通 Resume/Greeting→Submission→Communication→多轮 Real/Simulation/Raw/Review→Offer/谈薪→accepted，并覆盖无简历、rejected、withdrawn、两 Opportunity 隔离、旧核心数据读取、390×844 和零 console error/warning；唯一 tab 已关闭，临时服务已停止。
- 最终完整 Python 回归 `152 passed`；frontend build/typecheck 和 `git diff --check` 通过。风险 review 未发现双写正本、Timeline 事实、Simulation Patch、Employment 副作用或 schema v6 fence 回归。
- Production 最终仍为 0.2.0/schema v1、integrity ok、数据库 hash 不变；没有 Cutover、重启、迁移、业务 POST 或代码覆盖。Production Cutover 仍需后续显式授权。

## Opportunity Batch F — 隔离实施与验收通过，2026-09-18

已按 `$workbench-implement` 在 `/Users/frog/Projects/Career-worktrees/batch-f`（`codex/opportunity-f`）完成 Offer Vertical，并在原 v5 兼容 Gate 后实施最小 v5→v6 runtime fence；定点 `$workbench-review` 已通过。完整记录见 [Batch F §21](OPPORTUNITY-BATCH-F.md#21-schema-v6-fence实施与定点review2026-09-18)。

- 已实现唯一 current Offer、Record/Update/Accept、明确 `offered_role_title`、谈薪 Communication、三种 result、legacy 显式升级、纯投影 Timeline 与最基础 Offer Workspace；浏览器主链仍使用已通过的 F 功能验收证据。
- F runtime 现只接受 schema v6；v5→v6 migration 只增加一条 hash-bound manifest 并更新 `user_version`，业务行、Offer terms 和 schema objects 零改写。冻结 `0.6.0-batch-e` 在 Store 初始化、任何业务写入前拒绝 v6。
- 最终定向回归 `33 passed`；最终完整 Python 回归 `152 passed`；TypeScript/Vite build 成功，仅有已知大 chunk 提示。stale Offer revision 在 F 旧 adapter 返回 409，缺少 Offer revision 返回 422，冻结 E 则无法打开 v6。
- 最新生产备份的新隔离恢复副本完成 v1→v6；pre-v6 v5 rollback 恢复后 E 可读/F 拒绝，含 F Offer revision 1 的 v6 forward recovery 后 F 可读/E 拒绝。Production 保持 PID 2994、0.2.0/schema v1，DB hash/计数/附件未变。
- 本轮未进入 Offer Comparison、真实 AI/AI-Config、Employment/Project 或 Production Cutover；Batch F 隔离交付最终通过，下一批仍需新指令。

## Opportunity Batch E — 隔离实施与验收通过，2026-09-18

已按 `$workbench-plan` → `$workbench-implement` → `$workbench-review` 完成 [Batch E：完整 Interview Vertical](OPPORTUNITY-BATCH-E.md#20-实施与两轴验收记录2026-09-18)。

- 隔离交付位于 `/Users/frog/Projects/Career-worktrees/batch-e`（`codex/opportunity-e`），运行身份 `0.6.0-batch-e` / schema v5。实现 submitted→明确 ConfirmRealInterview→多轮 real→Preparation→0..N simulation→文本 Raw→当前 Final Review→real-only OpportunityResearch PatchProposal 确认闭环，并扩展纯投影 Timeline。
- 无日期确认创建 pending real；只有首次 submitted→interview 写 phase_changed_on。改期/待重约保持同一 ID；完成/永久取消不改变 Opportunity。Simulation 必须绑定同机会 real，且所有路径永远禁止 Patch。
- Context Pack 固定读取实际 Submission snapshot，不用当前 ResumeDocument；Simulation 可多选同机会历史 real/simulation Final Review，但默认不读对应 Raw。
- 复用现有 JSON/records typed 身份，没有机械新增业务表；schema v5 作为写契约门禁，v4→v5 migration 不重写旧业务行。旧 Interview 新建/关联 Note correction/candidate 旁路已停写；legacy Unknown 保留并只允许完整显式升级。
- 最终全量138通过，TypeScript/Vite build与实际浏览器完整主路径通过。最新真实生产备份已创建，隔离 v1→v5 clean verify、pre-E rollback、旧程序拒绝、含E写入 forward recovery通过；E inventory无真实Migration Gate。
- Production 最终仍为 PID2994、0.2.0/schema1，SQLite hash、表计数与附件hash保持；没有Cutover、重启、业务POST或源码/dist替换。Batch F具备隔离规划前置；Production Cutover、Offer、真实AI/AI-Config、Employment/Project仍不在当前授权内。

## Opportunity Batch D — 隔离实施与验收通过，2026-09-18

已按 `$workbench-plan` → `$workbench-implement` → `$workbench-review` 完成 [Batch D：Communication + Timeline 第一阶段](OPPORTUNITY-BATCH-D.md#20-实施与两轴验收记录2026-09-18)。

- 交付位于 `/Users/frog/Projects/Career-worktrees/batch-d`（`codex/opportunity-d`），运行身份 `0.5.0-batch-d` / schema v4。已投递机会支持 text/phone/other Communication Create/Update/Archive、CAS/幂等、ended 历史更正；Timeline 只投影 Opportunity/Submission/Communication，不建第二事实库。
- 删除采用对象内最小 archive；UI、默认 List/Detail/Timeline 隐藏，底层同 ID 与 legacy provenance 保留。无回收站、恢复 UI 或通用软删除平台。
- 旧 typed/JourneyNote 读取保留，两个旧新建入口及 typed Note correction 停写；Job alias/canonical URL 共用 scoped Domain Action，没有已知 Communication 双写旁路。phase/result 不受任何 Communication 动作影响。
- 完整回归129通过；review后定向18通过；TypeScript/Vite build和实际浏览器 U01–U10 通过。最新生产备份隔离v1→v2→v3→v4、旧程序拒绝、pre-D rollback和含D写入的v4 forward recovery通过；无真实Migration Gate。
- Production 最终仍为 PID2994、0.2.0/schema1，数据库/逻辑快照/附件hash及表计数保持；没有Cutover、重启、POST或源码/dist替换。具备在隔离环境规划 Interview Core 的前置，但未进入下一批。

## Opportunity Batch C — 隔离核心验收通过，2026-09-18

已完成workbench-implement → workbench-review；用户追加的统一Resume Workspace边界已落实，详细证据与未验边界见 [Batch C §17](OPPORTUNITY-BATCH-C.md#17-实施与两轴验收记录2026-09-1718)。

- 交付位于 `/Users/frog/Projects/Career-worktrees/batch-c`（codex/opportunity-c），基于完整B工作树；仅此目录实现schema3/0.4.0-batch-c。每Opportunity独立稿、三种显式来源、普通/特殊投递版本、Greeting当前值与冻结snapshot、一次投递/none、Profile显式刷新已接通；一个工作台UI、明确目录选择与返回来源机会。
- 最终全量120通过、前端build/tsc通过；真实浏览器双稿/冲突/PDF/none/统一导航及进程中断恢复已验证。原两profile失败按已确认产品目标消除隐式sync，未放宽CAS或跳过测试。
- 最新生产备份真实创建，隔离v1→v2→v3、旧程序拒绝、pre-C rollback、开写后v3 forward recovery通过；原199行/附件保全，C未猜测归属。完整PDF恢复分支228行/3个artifact/66个引用验证通过。
- 生产PID2994、0.2.0/schema1、DB物理/逻辑hash、附件、源码/dist保持。没有Production Cutover；生产原投递/面试/Offer写路径仍保留。
- 无新增真实资料Migration Gate，demo/legacy继续defer。具备Batch D隔离开发前置；本轮停止，不进入D。Resume Workspace Productization与AI Infrastructure → AI-Config仅在[Roadmap/Feedback](../07-roadmap.md)登记后续范围，AI-Config未实现。

## Opportunity Batch B — 隔离验收通过，2026-09-17

已按用户补充的Company匹配与禁止Production Cutover约束完成 workbench-implement → workbench-review。完整实现、测试、浏览器、迁移与恢复证据见[本批记录](OPPORTUNITY-BATCH-B.md) §11。

- 业务源码交付在 `/Users/frog/Projects/Career-worktrees/batch-b`（`codex/opportunity-b`）；原生产源码目录仅同步B记录和本状态，不回拷新业务代码/dist。现有未提交文档对齐/A改动不计为B。
- canonical Opportunity/Company、元数据与结束动作/CAS/幂等、六View与基础Workspace已实现；旧Job/plan.stage/context.company及旧投递/面试/Offer旁路受控。NFKC+trim+casefold身份匹配保留展示名，不猜别名、不合并主体。
- 最终兼容回归77通过；最后迁移安全/记录候选定向复验21通过（有重叠），typecheck/build通过。原profile基线仍1通过2失败，仅补测试创建Job所需幂等键，未改原revision断言或产品行为。
- 最新生产备份 `Career Data-backups/batch-b-20260917T133523Z` 已真实创建/隔离恢复。v2演练全部旧199行/PDF保全；新增1迁移manifest，2旧机会defer，0条被猜测迁入canonical。v1实际rollback恢复、旧程序拒绝v2、开写后v2 forward recovery和原v1活动/投递回放均已验证。
- 生产PID2994、0.2.0、schema1、数据库物理/逻辑hash、附件及源码/dist保持；无生产业务POST、重启或迁移。生产保留现有投递/面试/Offer能力。
- B批次结束时C具备隔离开发前置；当前C实施验收状态见上节。Production Cutover为后续显式部署授权，不能把隔离B当作完整生产替换。真实AI、无损逆迁移、异机灾备与完整C–G仍未验证/未实现。

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
