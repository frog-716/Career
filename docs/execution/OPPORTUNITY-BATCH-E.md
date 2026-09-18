# Opportunity Batch E — 完整 Interview Vertical

状态：**计划完成，尚未实施**。规划日期：2026-09-18。本轮仅使用 `$workbench-plan` 固定可执行范围、公共 Interface 与验收条件；未调用 `$workbench-implement`，未修改业务代码、schema、数据或 Production。

## 1. 范围、权威与已验证基线

本批只交付一个纵向结果：已投递且仍在推进的 canonical Opportunity，经用户明确确认后进入正式面试流程；每个真实轮次可完成准备、0..N 次绑定模拟、文本 Transcript、当前 Final Review，以及真实轮次的 OpportunityResearch PatchProposal 确认闭环，并由 Timeline 投影回看。

权威顺序为：本轮用户要求 > [authority](../00-authority.md) > 四份 Opportunity 正本（[Product](../target/opportunity/opportunity-product-model.md)、[Domain](../target/opportunity/opportunity-domain-model.md)、[UI Flow](../target/opportunity/opportunity-ui-flow.md)、[Context & Ingestion](../target/opportunity/context-ingestion.md)）> [Context Contract](../02-context-contract.md) > [Architecture](../03-architecture.md) > [Acceptance](../05-acceptance.md) > [Roadmap](../07-roadmap.md)。[Gap Analysis](../audit/OPPORTUNITY-GAP-ANALYSIS.md) 是历史分析与迁移建议，不覆盖本轮新决定。

本轮明确覆盖旧目标的一项语义：**Simulation 永远不能产生 PatchProposal**。旧 Product/Context 文档中“模拟里的用户自述可成为个人 Patch 候选”不适用于 Batch E；模拟中意识到资料遗漏时，用户去对应正式资料入口手动修改。实施不得借旧条款开放个人 Wiki/Profile/Research 回流。

实施基线是 `/Users/frog/Projects/Career-worktrees/batch-d` 的完整 Batch D 工作树，而不是其 Git HEAD。已核对的代码事实：

- 运行身份为 `0.5.0-batch-d` / schema v4；canonical Opportunity、一次 Submission、独立 ResumeDocument、Communication archive 与三源 Timeline 已存在。
- `records.kind='interview'` 只有 legacy typed body：`round`、`occurred_at`、`submission_id`、`raw_note_id` 等；没有 real/simulation、状态、父轮次、Preparation、当前 Raw 或 Final Review。
- `engagement.py` 已拒绝新 Interview/Offer typed 写入，但 `/api/journey/notes/{id}/correct` 仍可为 interview note 保存带历史的 correction，`.../candidate` 仍可由 interview note 生成 Wiki candidate。
- `ContextCompiler` 只接受 job/resume；当前 Provider 输出协议也只支持这两类。不能把现有 compiler 名称当作 Interview Context 已实现。
- `timeline.py` 只投影 Opportunity 创建、明确 canonical Submission、未归档 Communication；没有 Interview adapter 或 Timeline 事实表。
- 当前没有 CompanyResearch / OpportunityResearch 当前正本，也没有通用 PatchProposal；现有 `knowledge_candidate` 只会确认到 Wiki，不能直接冒充本批所需的 Research Patch。

Batch D 记录的 Production 为 `/Users/frog/Library/Application Support/Career Data`、PID 2994、版本 0.2.0、schema v1。它只是 2026-09-18 的既有证据；E 实施开始前必须重新只读核对真实进程、版本、SQLite、附件与 hash。本批继续只允许独立 worktree、临时虚构数据和届时最新 Production 备份的隔离恢复副本，绝不执行 Production Cutover。

## 2. 用户可观察结果与明确非目标

主路径固定为：

```text
submitted + active Opportunity
  → 用户明确 ConfirmRealInterview（日期可未知）
  → Opportunity 首次进入 interview；创建 pending/scheduled real
  → 编辑本轮 Preparation
  → 可选启动 0..N Simulation，选择 0..N 历史 Final Review
  → 复制本次 Context Pack 到新的 ChatGPT/Voice 对话
  → 用户外部完成模拟并粘贴文本 Raw
  → 用户手动编辑或在测试模式生成当前 Final Review
  → 真实面试粘贴文本 Raw、完成当前 Final Review
  → 真实轮次可在明确测试/模型处理下产生 OpportunityResearch PatchProposal
  → 用户编辑后接受并立即 Apply，或拒绝
  → 明确确认下一轮时新建另一个 real；Opportunity 仍只显示“面试”
```

基础闭环不依赖模型：real 创建与排期、改期/待重约/完成/永久取消、Preparation 手动编辑、Simulation 创建、Context Pack 导出复制、Raw 当前文本、Final Review 手动编辑、多轮、Timeline 都必须可用。没有可用模型时，AI 生成 Preparation/Review/Patch 明确显示不可用；不能阻塞手动路径，也不能展示伪 AI 结果。

本批不实现：Offer Domain 或“进入 Offer”动作、Communication AI/Research 全量产品化、CompanyResearch、个人 Career Context Patch、Resume 修改、真实 AI/AI-Config/ModelGateway、内置录音/转写/Voice 自动化、控制 ChatGPT 网页、通用 Raw/Patch 平台、Timeline 表、全局 Interview 工作台重构、Employment / Project 修改、Production Cutover 或 `.codex/config.toml` 处理。

## 3. Domain 不变量

1. Opportunity 只有 `phase=interview`，不增加一面/二面/等待结果等 phase。
2. `ConfirmRealInterview` 是唯一可创建新 real 的动作，也是本批唯一可将 submitted 推到 interview 的动作；Communication 文本、AI、Timeline 和前端组合调用均无此权限。
3. 第一个 submitted→interview 使用服务端一次业务时间写 `phase_changed_on=confirmed_on`；已处于 interview 时新增轮次不写 Opportunity、不增加其 revision、不重置阶段日期。
4. 一次现实轮次始终是同一个 real ID。排期、改期、临时取消待重约、重新约都原位 CAS 更新；只有现实新轮次才新建对象。
5. real 状态仅 `pending | scheduled | completed | cancelled`。`scheduled` 必须有日期；临时取消变 `pending` 并清空 schedule；`cancelled` 只表达永久取消。
6. real 完成或取消绝不改变 Opportunity phase/result；进入 Offer 留给 Batch F 的明确 Domain Action。
7. Simulation 必须且只能绑定同一 Opportunity 的一个 real；不能绑定 simulation、跨机会或脱离 real 存在。
8. Simulation 不改变 Opportunity、real status、Research、Career Context、Resume、Profile、Employment 或 Project；服务端对 Simulation 的 Patch 生成/创建/接受路径一律拒绝。
9. 每个 real 最多一份当前 Preparation；每个 InterviewSession 最多一份当前 Raw 和一份当前 Final Review。三者都不建立内容版本链。Preparation 的五类内容只是推荐结构，允许部分或全部为空；Final Review 的五块结构仍固定存在。
10. Raw 修正覆盖当前正文并提高自身 revision/hash；不把旧正文复制进 revisions、command result、run、proposal、日志或另一个 note。修改 Raw 不自动更新/删除 Final Review。
11. Final Review 只有五块结构且是可编辑当前终版；保存 Review 不直接修改任何正式事实。
12. Real Patch 只来自同一 real 的当前 Raw，且本批唯一允许目标是同一 Opportunity 的 `OpportunityResearch`；用户编辑/接受/拒绝，接受后在一个事务立即 Apply。Final Review 不是 Patch 来源授权。
13. Context Pack 默认读取实际 Submission 快照；有简历时读取 `resume_snapshot`，无简历时明确写缺失。绝不能用当前 ResumeDocument 或最新 ResumeVersion 补位。
14. 用户为 Simulation 多选历史 Review 时，只读取所选当前 Final Review；默认不读取它们的 Raw。选择不改变任何 Career 正本。
15. Timeline 是查询投影；Interview 的创建、状态或内容更新不能另写 Timeline record。
16. Communication 只可作为 `source_communication_id`。后续更正或 archive 不改 Interview；被引用的 archived source 仍可由明确来源读取并显示已归档。
17. 所有新写命令具有 idempotency key；所有当前对象修改具有 expected revision。跨 owner 返回 404，规则/字段错误 422，CAS、幂等异体、状态竞争或 legacy 未核对返回 409。

## 4. 最小数据模型：复用 JSON/records，不按对象机械建表

本批不新增一张业务表对应一个名词。继续复用 `records` 的稳定 ID 与 JSON body；只对当前对象采用明确 kind、owner、revision/hash 和唯一索引。`records` 的 upsert 能满足当前稿覆盖，但所有写入只能经过 Interview service，不能继续使用通用 `_record` 作为公开业务接口。

### 4.1 InterviewSession

新形态继续使用 `records.kind='interview'` 和原 typed ID，body 至少包含：

| 字段 | 规则 |
| --- | --- |
| `id` / `interview_format` | 稳定 ID；新形态 format 固定为 2，和 legacy 确定性区分 |
| `opportunity_id` | canonical owner；alias 先解析再保存 |
| `type` | `real` 或 `simulation`，创建后不可改 |
| `name` | real 用户填写；simulation 由目标轮次和同父序号形成稳定展示名，可在同 ID 下保留 |
| `status` | real 为四态；simulation 仅允许 `pending/completed/cancelled`，不使用 scheduled |
| `confirmed_on` | real 必填且创建后不随改期变化；正常新建由服务端业务日产生 |
| `scheduled_on` / `scheduled_at` | real 可空；只知道日期时不伪造午夜时间，知道精确时间时 `scheduled_at` 必须带时区且日期一致 |
| `completed_on` | 完成时由用户确认的实际业务日；未完成为空 |
| `target_real_interview_id` | simulation 必填，real 必须为空；父对象必须是同机会 real |
| `source_communication_id` | real 可空；保存时必须属于同机会，之后 archive 不清空引用 |
| `created_at` / `updated_at` / `revision` | 服务端时间与对象 CAS；状态/排期成功变更 revision +1 |
| legacy provenance | 原 `round/raw_note_id/submission_id/occurred_at` 等字段原样保留，不作为新字段默认值 |

`cancelled` 的动作时间可以记录为 `cancelled_on` 供回看，但 Timeline 的核心业务日期仍按 §11 的确定性规则投影。没有删除 Interview 的普通产品动作；误建或永久不进行使用 `cancelled`，保持 ID 与来源可追溯。

### 4.2 Preparation、Raw、Final Review

继续使用窄职责 record kinds，不新增 SQL 表：

- `interview_preparation`：确定性 owner 为 real ID，可保存面试重点、预计问题、重点项目、风险问题、用户备注；这些是推荐结构，各项允许为空，只保存用户当前真正需要准备的内容。只有 current body、revision/hash，无内容历史。
- `interview_raw`：确定性 owner 为任一 InterviewSession ID，保存用户粘贴的带时间戳文本、revision/hash、updated_at；服务不解析说话人或把时间戳变成事实。
- `interview_final_review`：确定性 owner 为任一 InterviewSession ID，字段固定为 `summary`、`key_qa[]`、`patterns[]`、`discoveries[]`、`next_actions[]`，current-only、CAS 可编辑。

这三个对象的唯一性由 deterministic ID 加 schema v5 partial unique index 双重保护。command 记录只保存对象 ID/revision/hash 等重放元数据，不复制正文。不得调用会把旧正文写入 `revisions` 的通用 `_save`。

### 4.3 最小 OpportunityResearch 与 PatchProposal

Batch D 没有当前 Research 正本，而 real Patch 必须有明确落点。E 只补足满足真实面试回流的最小边界：

- `current.kind='opportunity_research'`：每个 canonical Opportunity 至多一份当前档案，包含按主题组织的 research items、revision 与 source refs；首次接受 Patch 时可懒创建。
- 本批 item category 只覆盖 `company_business | role | team | recruiting_context | process | unknown`。全部仍属于这一次 Opportunity；不自动提升到 CompanyResearch。
- `records.kind='patch_proposal'`：只允许 `origin_type=real_interview_raw`、当前 raw ID/revision/hash、real ID、opportunity ID、目标 research revision、一个或多个 `append/update research item` 建议、状态 `pending/applied/rejected/stale`。
- 用户可以编辑 category/content 后接受。接受动作重新校验 real/type、Raw revision/hash、目标 Research revision 和 proposal revision，在同一事务更新 Research 与 proposal；拒绝只更新 proposal。

E 不建设通用 JSON Patch、任意 target registry、跨 Company/Wiki/Profile 的 Apply 引擎。真实面试中出现个人资料遗漏时仍由用户去正式资料入口修改；Company 级提升留待 Research 专门批次决定。

## 5. 公共 Domain Actions 与 HTTP Interface

路径名可在实施时按现有 router 习惯微调，但动作语义、输入与副作用在编码前固定：

| Domain Action | 建议 HTTP | 输入 / 结果 |
| --- | --- | --- |
| `ConfirmRealInterview` | `POST /api/opportunities/{oid}/interviews/real` | name、可选 schedule、可选 source_communication_id、Opportunity expected_revision、idempotency；原子创建 real，并在首次时推进 phase |
| `List/GetInterview` | `GET .../interviews[/{iid}]` | canonical scope 内新形态与明确 legacy DTO；跨 owner 404 |
| `ScheduleRealInterview` | `POST .../{iid}/schedule` | scheduled_on、可选 scheduled_at、expected_revision、idempotency；pending/scheduled 原位排期/改期 |
| `SetRealInterviewPending` | `POST .../{iid}/pending` | expected_revision、idempotency；清空 schedule，表达暂时取消待重约 |
| `CompleteRealInterview` | `POST .../{iid}/complete` | completed_on、expected_revision、idempotency；只改 real，不改 Opportunity |
| `CancelRealInterview` | `POST .../{iid}/cancel` | cancelled_on、expected_revision、idempotency；永久取消，只改 real |
| `SavePreparation` | `PUT .../{real_id}/preparation` | 五块当前内容、expected_revision、idempotency；只允许 real owner |
| `PrepareInterviewContextPack` | `POST .../{real_id}/context-pack` | 明确 communication/wiki 选择与用途；返回可检查、可复制 pack 和 snapshot ID，不写业务事实 |
| `StartSimulation` | `POST .../{real_id}/simulations` | 0..N selected_review_ids、可选 communication/wiki 选择、idempotency；原子创建 simulation + context snapshot，返回 pack |
| `Complete/CancelSimulation` | scoped action | expected_revision、业务日、idempotency；不触碰父 real/Opportunity |
| `SaveInterviewRaw` | `PUT .../{iid}/raw` | current text、expected_revision、idempotency；覆盖当前 Raw，使依赖旧 Raw 的 pending proposal stale |
| `SaveFinalReview` | `PUT .../{iid}/final-review` | 五块完整结构、expected_revision、idempotency；人工路径始终可用 |
| `GenerateFinalReview` | `POST .../{iid}/generate-final-review` | real/simulation 均可；输入当前 Raw + 当前允许 Context，输出严格五块 Final Review 建议；不得产生 PatchProposal，用户编辑后另行保存 current Review |
| `GenerateResearchPatch` | `POST .../{iid}/generate-research-patch` | 只允许 real；输入当前 real Raw + 当前允许 Context，输出 OpportunityResearch PatchProposal；用户编辑/接受/拒绝后才 Apply |
| `Edit/ResolvePatchProposal` | proposal scoped endpoint | expected proposal/target/source revisions、idempotency；simulation 请求服务端硬拒绝 |

不得暴露通用 `ProcessInterview`、通用 `PATCH interview.status` 或前端“先建 Interview，再改 Opportunity”组合。`GenerateFinalReview` 与 `GenerateResearchPatch` 在 Domain/HTTP/UI、权限和输出 schema 上保持分离；底层可共用同一个窄职责 processor/provider adapter。每个动作在单个 `BEGIN IMMEDIATE` 中完成 owner、状态、CAS、幂等和允许副作用检查；模型调用在事务外，返回后重新检查 source/target revision，变更则将结果标 stale，不覆盖当前值。

## 6. 状态、日期与并发规则

`ConfirmRealInterview` 只接受 `result=active` 且 phase 为 submitted 或 interview：

- submitted：同一事务创建 real，保存 `confirmed_on=business_day(now)`，Opportunity phase→interview、phase_changed_on=confirmed_on、phase_source 指向该 real，Opportunity revision +1。
- interview：只创建 real；提交的 Opportunity expected_revision 只用于确认用户看到当前 active/interview 状态，不保存 Opportunity。
- resume/offer/ended/legacy read-only：409。E 的正常入口不补造未投递历史；旧目标中的“未投递先确认”不在本批已投递主链内宣称完成。

排期规则：pending 可以 schedule；scheduled 可以原位 reschedule；scheduled→pending 清空 `scheduled_on/scheduled_at`；pending/scheduled→completed 要求 `completed_on`；pending/scheduled→cancelled 表示永久取消。completed/cancelled 不能通过普通动作回到其它状态；若未来需要历史纠错，另设明确 correction action，不开放任意状态写入。

`CompleteRealInterview`、`CancelRealInterview`、Preparation/Raw/Review 保存均不改 Opportunity revision。Confirm 与 EndOpportunity 竞争时，由同一 SQLite 写锁中的前置检查决定只可能有一个符合前置的结果；不得出现 ended Opportunity 新建 real 或 real 已建但 phase 未提交的半成功。

新建 simulation 要求父 real 所属 Opportunity 仍 active/interview。重复点击复用同一 idempotency key；不同 key 表达不同模拟。ended Opportunity 保留已有 Interview、Raw、Review、Patch 的读取和当前内容更正，但不允许创建新 real/simulation或推进状态。

## 7. Interview Context Pack 与 ContextSnapshot

不把当前 `ContextCompiler.compile(job/resume)` 直接扩大成递归扫描。新增窄职责 Interview policy，通过同一受控读取接口准备 `task_type=interview_preparation | interview_simulation | interview_review | interview_patch`，每项声明 required/optional/forbidden、输出和预算。

默认来源与限制：

| 来源 | 规则 |
| --- | --- |
| 当前 Opportunity / JD | required；只读 canonical 当前值和 revision |
| OpportunityResearch | optional；没有则标 Unknown，不用目录 description/Wiki 代替 |
| Submission | required；读取同机会唯一 Submission。`resume_snapshot` 存在则使用当时结构/引用，不存在明确“本次无简历” |
| 当前 ResumeDocument / 其它 ResumeVersion | forbidden，除非未来另有用户明确任务；E 默认永不读取 |
| 目标 real | required；simulation pack 的 target 永远是父 real |
| Preparation | optional current；只读父 real 的当前值 |
| Communication | 只读用户明确选择且同机会的 IDs；source communication 可默认勾选但仍在预览中可见。archive 后仍可作为明确来源读取并标 archived |
| 前序 Interview | Preparation 可选同机会此前 real 的当前 Final Review；Simulation 只读用户多选的任意既有 real/simulation Final Review |
| 历史 Raw | forbidden by default；选择 Final Review 不带入对应 Raw |
| Career Context | 只读用户明确选择的当前 personal Wiki 条目及合同允许的 goal/constraint；不读 episode 私聊、其它机会材料或 Feedback |

一次读取事务内校验所有 owner、revision/hash，建立 source list、Unknown、omissions 和预算。Context Pack UI 必须允许用户先检查来源，再复制文本。`ContextSnapshot` 保存任务、target、source ID/revision/hash/用途、选中的 Review IDs、skill/policy version、生成时间、packet hash及实际 pack；不保存任何 Interview Raw，因为 pack 默认不含历史 Raw。StartSimulation 的同键重放返回首次 snapshot/pack，不因来源后来变化生成不同内容。

历史 Review 候选只包括创建 Simulation 前已存在、属于同一 Opportunity 且当前可读的 Final Review；去重且最多 30 个。跨机会、重复、已不存在或 revision 变化在生成前拒绝；生成后 source 变化只使 snapshot 标 stale，不反向修改 simulation 或 Career 正本。

## 8. Raw、Final Review 与处理降级

Raw 入口只接受文本，最多沿用本地 100k 限制；时间戳是正文的一部分，不声称自动识别说话人、置信度或音频。用户修正后覆盖当前 raw body，revision/hash 增加，旧正文不进入 revisions 或命令结果；旧库 JourneyNote/correction 历史完整保留但不继续写入新 Raw。

保存 Raw 后：

- Final Review 原样保留，界面提示“Raw 已更新，复盘未自动重算”；
- 依赖旧 Raw 的 pending PatchProposal 变 stale，已 applied/rejected 历史状态不回滚；
- 已保存 ContextSnapshot 只标 stale，不重写；
- 不自动调用 Provider、不自动生成 Review、不自动 Apply Research。

Final Review 手动表单始终可用。TestProvider 分别提供两个明确意图：`GenerateFinalReview` 只返回五块 Review 建议且存储零 Patch；`GenerateResearchPatch` 只对 real 返回 Research Proposal。两者分别验证输出 schema、来源白名单、stale 与权限，页面和响应必须标“测试模式”。RealProvider 未配置或 E 尚未接入正式 Interview Skill 时返回明确 capability unavailable，不把模板文字包装成 AI 结论。真实 AI 质量不属于 E 通过证据。

## 9. Real-only Patch 闭环

`GenerateFinalReview` 对 real/simulation 都只生成 Review 建议，绝不创建或更新 PatchProposal。`GenerateResearchPatch` 在 service、storage、HTTP、UI 四层只对 real 暴露有效能力；simulation 请求在构造 proposal 前即拒绝。服务层和存储层都断言 `proposal.origin_interview.type == real`，并在 schema/verify inventory 中检查 simulation proposal 数为 0。

real 的测试/未来模型输出先经固定 schema 校验：每条建议必须引用当前 Raw ID，区分可核对信息、推断、建议与 Unknown，只能生成本批允许的 OpportunityResearch item 操作。用户在 Patch 面板可编辑 category/content、逐条接受或拒绝；批量接受仍按同一 target 分组并原子 Apply。来源或 Research revision 变化时 409/stale，保留用户编辑内容供比较，不 last-write-wins。

Patch 接受不改变 Interview status、Opportunity phase/result、Final Review、CompanyResearch、Wiki/Profile、Resume、Employment/Project。Timeline 不展示“接受 Patch”事件。

## 10. Legacy Interview 兼容与旧写入口

v5 dry-run 把现有资料分类为：format 2 real/simulation、legacy typed+有效 note、legacy typed 缺 note、note-only、多个 typed 指向同 note、owner/alias 冲突、type/date/status Unknown、跨机会 submission/source 冲突。

- legacy typed ID 保留并可读；`round` 只作原字段展示，不自动成为新 name，`occurred_at` 不自动成为 confirmed/scheduled/completed 日期。
- 不根据“一面/模拟”等名称猜 type，不根据 JourneyPlan/Application/Offer 猜 status、phase 或 result。
- note-only 留在 Legacy 资料区，不进入 Interview Timeline，也不自动创建 Session。
- 迁移不改任何 legacy body，不创建 real/simulation、Preparation、Raw、Review、Research 或 Patch。
- 允许后续在同 ID 上执行显式 `UpgradeLegacyInterview`，但必须由用户选择 type、name、真实日期/状态；simulation 还要明确父 real。只有 canonical owner 无歧义且字段完整时才写 format 2。此动作不属于自动 migration。
- 被新 format 2 Interview 引用的 legacy note，其 correction/candidate 旧入口统一返回 `interview_action_required`。既有历史、来源与 candidate 可读；Employment scope note 不受影响。
- 旧 `/api/opportunity-activity/interview` POST 继续停写并指向 scoped action；GET 兼容读。旧 Job URL 解析到同一 canonical collection，不能另建一套 Interview。

若显式升级 legacy real 需要把 submitted 推到 interview，用户必须明确提供历史 `confirmed_on` 并通过专门动作；不能使用升级当天伪造历史日期。已结束或 owner/type 不可确定的记录保持只读 Unknown。

## 11. Opportunity / Interview Workspace 与 Timeline

submitted/active 当前阶段增加两个明确入口：

- Workspace 的“确认进入正式面试”；
- 未归档 Communication Detail 的“从本次沟通确认面试安排”，只多带 `source_communication_id`，仍由同一个 Confirm action 完成。

phase=interview 时，Opportunity 当前阶段区域只显示当前/下一场 real：优先最近未来 scheduled，其次 pending；completed/cancelled 进入此前轮次。主动作是准备、开始模拟、上传真实面试文字稿/打开本轮。所有轮次列表可进入 `#opportunities/{oid}/interviews/{iid}` 或等价同应用路由。

Interview Workspace 展示稳定轮次顶部、排期/状态动作、Preparation、该 real 的 Simulation 列表、真实 Raw、真实 Final Review、real-only Patch 区。Simulation Detail 显示其 Context Pack 来源、复制按钮、Raw 与 Review；不显示 Patch 或正式资料修改入口。页面不堆出 CompanyResearch、Offer、Resume 版本管理或通用 AI 聊天。

Timeline 新增一个 Interview adapter，不新增表或 record：

| source type | 显示日期 | 摘要与目标 |
| --- | --- | --- |
| real pending | `confirmed_on` | 轮次名 · 时间待定，进入 real workspace |
| real scheduled | `scheduled_on` | 轮次名 · 待进行，进入 real workspace |
| real completed | `completed_on` | 轮次名 · 已完成 / 已复盘，进入 real workspace |
| real cancelled | `cancelled_on`，缺失则 `confirmed_on` | 轮次名 · 已永久取消 |
| simulation | `completed_on`，未完成则创建业务日 | 父轮次模拟 #N · 待回传/已完成/已复盘，进入 simulation detail |

同一 Session 始终只有一条投影，排期/状态/Review 变化使该项即时更新。稳定排序延续 Batch D；同日排序不冒充真实先后。legacy Unknown 进入独立待核对区，不赋今天。点击来源 Communication 时，即使已 archive，也能从 Interview 来源区读取只读正文并显示“来源已归档”。

Offer 只显示边界文案“收到现实 Offer 后将由后续动作记录”，不放置可写空按钮，不实现 phase=offer。

## 12. schema v5 的必要性

E 需要 schema v5，但原因不是批次编号：冻结的 Batch D/v4 程序会接受同一 v4 数据库，并仍允许对 interview JourneyNote 写 correction/history 和生成 Wiki candidate；它不知道 current-only Raw、simulation 零 Patch、real parent、Review/Patch/Research revision 约束。让 v4 程序打开 E 已写入的数据库会重新形成 Raw/Patch 旁路，破坏数据保留和权限不变量。

v4→v5 最小 DDL/manifest：

1. dry-run 只读分类 §10 的 legacy 形态、Interview/Note/Submission/Communication owner 与引用、现有 candidate/source、Timeline 候选；不初始化 Store、不补默认值。
2. apply 在 `BEGIN IMMEDIATE` 校验 source snapshot hash，建立 Preparation/Raw/FinalReview/OpportunityResearch owner 的必要 partial unique index，登记 `interview_migration` manifest，最后设置 `PRAGMA user_version=5`。
3. 不批量重写任何 Interview、JourneyNote、Communication、Submission、Resume、Raw/Wiki/Candidate、Employment/Project 或附件；不产生 Timeline、ContextSnapshot 或 PatchProposal。
4. v5 runtime 只接受 v5；冻结 D/v4 runtime 必须在任何初始化/写入前拒绝 v5，E runtime 也拒绝 v1–v4并提示显式迁移。
5. verify 比较全部既有 current/records/revisions/applications 行 ID/body hash和附件 hash；允许新增仅 migration manifest/index/schema version。

如果实施发现上述唯一索引无法在现有 JSON shape 上安全建立，可缩为 deterministic ID + verifier，但 schema fence 仍必需；实施记录必须说明具体兼容性证据，不能为了“少一个版本号”让旧程序继续写。

## 13. 迁移 rehearsal、rollback 与 forward recovery

实施时按以下顺序，只在隔离目录：

1. 重新确认 Production 服务 PID/版本、真实数据目录、SQLite/schema、附件目录、源码/dist 与只读逻辑/物理 hash；不发业务 POST、不重启。
2. 用现有 backup 创建届时最新真实备份，恢复到新的系统临时目录；先验证 v1 integrity、对象计数、关键 ID、Submission/ResumeVersion/PDF/hash、Raw/Wiki/Candidate 与附件引用。
3. 在恢复副本重新执行已验收 v1→v2→v3→v4 链，每段重新生成 hash-bound plan，不复用过期报告，不替 demo/legacy 选择语义。
4. 对 v4 副本执行 E dry-run；真实用户 owner/type/date/status 或引用无法安全解释时报告 Gate，demo/legacy 标 defer。建立 pre-E v4 backup，再 apply/verify v5。
5. 冻结 D/v4 runtime 打开 v5 必须拒绝且 hash 不变；E/v5 runtime 打开 pre-E v4 也拒绝。不得靠手改 `user_version` 模拟 rollback。
6. 开写前 rollback：从 pre-E backup 恢复到另一个新目录，用匹配 D/v4 runtime 实际启动和读回原数据；不覆盖 v5 副本。
7. 在迁移后 Production 副本的再次可丢弃分支加入明确 synthetic canonical submitted Opportunity，走 real→排期/改期→pending→重约→simulation→Raw/Review→real Patch Apply，随后创建 v5 backup 并恢复到新目录。
8. forward recovery 核对所有新 Interview/Preparation/Raw/Review/ContextSnapshot/Patch/Research、Opportunity phase date、Submission frozen snapshot/PDF、Communication archived source和幂等/CAS；用 E runtime 和浏览器读回。不得恢复 pre-E 快照丢弃新写入。
9. 最终再次只读核对 Production v1 的 PID/version/schema/hash/计数/附件，证明没有 Cutover 或用户数据变化。

manifest 至少记录代码/worktree hash、输入备份与隔离路径、前后 schema/hash、legacy 分类/Gates、全部旧 ID/body/hash、Interview/Note/Communication/Submission 引用、附件 hash、迁移/拒绝/rollback/forward 结果及 Production 前后核对。私人正文只留 0600 私有证据目录，不写仓库文档。

## 14. 修改文件/模块范围与实施顺序

实施必须从 Batch D 完整工作树创建新的独立 worktree/`codex/opportunity-e` 分支；不从未包含 B–D 实现的 HEAD 重建。

| 顺序 | 预计文件/模块 | 完成边界 |
| --- | --- | --- |
| E1 基线与固定测试 | 本文、STATUS；新增 E tests/fixtures | 记录 D 工作树 hash、Production 只读基线；固定动作/错误/状态矩阵 |
| E2 Interview Domain | 新 `src/workbench/interview.py`，局部 `opportunity.py`、`app.py` | real/simulation、状态、CAS/幂等、source communication、首轮原子 phase；无 AI 依赖 |
| E3 Preparation/Raw/Review | 可在 `interview.py` 内形成深模块，复杂时新增窄职责 `interview_materials.py` | current-only 保存、hash/stale、不写 revisions/旧正文；不建通用 Raw 平台 |
| E4 Context/processing | `context.py` 的公共 source 工具或新 `interview_context.py`；`providers.py` 仅增加受限测试协议 | pack/snapshot、实际 Submission、Review 多选、预算；GenerateFinalReview / GenerateResearchPatch 两个意图分离，TestProvider 明示，真实 AI 不宣称 |
| E5 Research/Patch | 新窄职责 `interview_patch.py` 或 Interview 模块内部；`knowledge.py` 只做旧旁路门禁 | real-only Proposal→编辑/接受/拒绝→OpportunityResearch；不建通用 target registry |
| E6 Timeline/legacy | `timeline.py`、`engagement.py`、`journey.py` | Interview adapter、legacy read/显式升级、旧 correction/candidate/POST 旁路停写；Employment notes 不变 |
| E7 schema/迁移/恢复 | `core.py`、`backup.py` 必要兼容；新 migration module/CLI；migration baseline | v4→v5 fence、dry-run/apply/verify、真实备份 rehearsal；不改旧业务行 |
| E8 UI | `frontend/src/opportunity-ui.ts`、`main.ts` 数据加载/路由、现有 CSS；复杂时新增 `interview-ui.ts` | Confirm、real/simulation workspace、pack copy、Raw/Review/Patch、Timeline；不重写全局前端 |
| E9 文档与 review | `src/workbench/README.md`、frontend README、本文实施记录、STATUS | 只记录真实证据、两轴 review 后停止 |

默认不改 ResumeDocument/Submission/Artifact 写逻辑、Company 匹配、Communication CRUD、Offer、Employment、Project、AI-Config 或四份目标原文。只有 E 的 frozen Submission 读取、archived Communication 来源解析或 migration verify 直接需要时才作局部调用，不改变它们的拥有权。

## 15. 编码前固定的自动测试

以下验收在计划阶段尚未运行，不能标通过。全部使用 tmp/虚构数据和 TestProvider/Spy；不接真实 AI：

| 编号 | 固定断言 |
| --- | --- |
| T01 Confirm | submitted/active 无日期创建 pending real；带日期创建 scheduled；confirmed_on/phase_changed_on 同一天；phase+real 同事务；resume/offer/ended/legacy 拒绝 |
| T02 多轮 | interview phase 新建第二/第三 real 只增加 Session，不改 phase_changed_on/Opportunity revision；无预设轮数 |
| T03 schedule | 同 ID pending→scheduled→reschedule→pending(clear)→scheduled；不新增对象；永久 cancel 与临时待重约严格区分 |
| T04 status isolation | complete/cancel real 不改 Opportunity phase/result/revision，不创建 Offer/Employment；EndOpportunity 竞争无半成功 |
| T05 source communication | 同机会可引用；跨机会/不存在拒绝；后续 update/archive 不改 Interview；明确读取 archived source 状态/正文 |
| T06 simulation parent | 同机会 real 0..N；跨机会、simulation parent、legacy unknown parent、无 parent 拒绝；任何 simulation 操作不改父/Opportunity |
| T07 Preparation | 仅 real 0..1 current；五类推荐内容允许任意部分为空；CAS/幂等；simulation 拒绝；旧正文不进 revisions/command；重启可读 |
| T08 Context Pack | 只含 canonical Opportunity/JD、Research、实际 Submission snapshot、target real、Preparation、明确 Communication/Review/Wiki；无当前 ResumeDocument、其它机会、Feedback、episode 私聊或历史 Raw |
| T09 Review 多选 | 0/1/N、real+simulation、跨轮次可选；重复/跨机会/不存在/变更拒绝；所选 Review 不带 Raw；同键重放同一 snapshot/pack |
| T10 Raw | real/simulation 各自0..1 current；修正覆盖且 revision/hash变；DB全库扫描证明旧正文未藏在 revisions/request/run/proposal；Review保持；依赖 proposal/snapshot stale |
| T11 Final Review | 五块结构校验、current-only、CAS/幂等、人工编辑；不改 Research/Opportunity；Raw变更不自动重算 |
| T12 GenerateFinalReview | real/simulation 分别以当前 Raw + 允许 Context 生成严格五块建议；不直接保存 current Review、不产生任何 Patch；用户编辑后 SaveFinalReview；stale source 拒绝 |
| T13 Simulation zero Patch | GenerateResearchPatch HTTP 不对 simulation 形成有效能力，service/storage 直接拒绝，UI 无入口；DB断言零 simulation-origin proposal；个人 Wiki/Profile/Research/Resume/Employment/Project hash不变 |
| T14 Real Research Patch | GenerateResearchPatch 只接受 current real Raw→结构化 proposal；非法 target/source拒绝；编辑、拒绝、接受立即 Apply；source/target/proposal stale拒绝；接受只改同机会 OpportunityResearch |
| T15 Provider degradation | 无模型时所有手动动作可用，两个AI动作明确 unavailable；TestProvider 分别验证两个意图且响应/页面标测试；Spy 捕获 payload/输出分离；无真实网络调用 |
| T16 Timeline | 每个 real/simulation 一条、状态/日期/Review摘要即时投影、稳定排序/Unknown；无 timeline kind/table；点击回真实 workspace |
| T17 legacy | typed+note/read-only、缺 note、note-only、多 typed、owner冲突、type/date/status unknown；不猜名称/Offer/plan；显式升级同 ID 且完整校验；旧新建/correction/candidate 旁路拒绝 |
| T18 scope/concurrency | 两 Opportunity 完全隔离；alias/canonical 共用集合；Confirm 双击同 key 一条、异体冲突；并发 status/Raw/Review/Patch CAS保留输入 |
| T19 migration | v4 空库/全 legacy/歧义/已有合法 fixture dry-run；source hash变化、重复 apply、事务故障；只增 index/manifest/version，旧行/body/hash/附件不变 |
| T20 version/recovery | v4拒绝v5、v5拒绝v4且源不变；pre-E rollback、含E写入的v5 forward recovery；ContextSnapshot/Patch/Research/archived source完整 |
| T21 非本期回归 | B Opportunity、C Resume/Greeting/Submission/PDF、D Communication/archive/Timeline、Context隔离、Employment/Project 通过；Offer写门禁和 Production v1 保持 |

测试承载预计新增 `tests/test_interview.py`、`tests/test_interview_context.py`、`tests/test_interview_patch.py`、`tests/test_interview_migration.py`，局部更新 `test_timeline.py`、`test_communication.py`、`test_journey.py`、`test_engagement.py`、`test_context.py`、`test_backup.py`。先跑 E 定向测试；整合后因 Store/schema/router/主 Workspace 受影响，运行一次完整 pytest 和一次 frontend build/tsc。只有新失败才定向复验，不重复全量凑证据。

## 16. 浏览器验收条件

使用临时 schema v5 虚构数据、TestProvider 和非生产端口；Agent 只保留一个受控浏览器 tab，验收结束立即关闭 Agent 创建的 tab 并停止临时服务：

| 编号 | 可观察结果 |
| --- | --- |
| U01 | submitted Opportunity 可从 Workspace 或 Communication 明确确认“业务一面”；不填日期得到 pending，phase 当天进入面试 |
| U02 | 为同一 real 排期、改期、临时待重约、重新排期始终同一 URL/ID；永久取消明确区分，Opportunity 不结束 |
| U03 | 完成业务一面后 Opportunity 仍 interview+active；确认业务二面后 phase_changed_on 不变，轮次数不受限制 |
| U04 | Interview Workspace 能编辑当前 Preparation；刷新/重启保留，历史中不出现多个版本 |
| U05 | 开始 simulation 时可 0/1/N 多选跨轮 real/simulation Final Review；pack 预览使用实际投递简历且不含当前稿/所选 Review 的 Raw；复制按钮可用 |
| U06 | simulation 回传 Raw、修正 Raw、手动五块 Review；页面没有 Patch/资料回流入口，相关正式对象保持 |
| U07 | real/simulation 分别调用 GenerateFinalReview；都只得到五块建议、明确标“测试模式”，用户编辑并保存后才成为 current Review，且零 Patch |
| U08 | real 单独调用 GenerateResearchPatch 后 Proposal 可编辑、拒绝或接受；接受后 OpportunityResearch 即时显示，二次应用不重复；simulation UI 无此入口且直接请求被拒绝 |
| U09 | Timeline 包含 D 的创建/投递/沟通与 E 的多轮/simulation，状态日期正确、每对象一条并能打开详情；无第二事实库 |
| U10 | source Communication archive 后 Interview 仍在，来源显示“已归档”且可只读查看；修改 Communication 不改轮次 |
| U11 | legacy typed Interview 显示 Unknown/待核对，不因“一面/模拟”字样猜 type；note-only 不进入 Timeline；显式核对后同 ID 升级 |
| U12 | 无模型配置时 real/simulation/Raw/Review/Timeline 全可完成，AI操作明确不可用；没有真实网络请求或假结果 |
| U13 | 两 Opportunity 的 real/simulation/Review/Patch 完全隔离；旧 Job 深链和 canonical URL 读同一对象，不重复 |
| U14 | v5 forward 恢复副本经浏览器读回完整闭环；Resume Workspace、冻结投递材料、Communication、一个 Employment/Project 路径冒烟通过，Offer 仍为后续边界 |

最新 Production 备份副本只用于迁移保全、legacy 读取与 runtime 兼容；真实副本若没有可写 canonical submitted Opportunity，不注入假用户数据。所有 U01–U14 写入在纯虚构数据或备份的明确 synthetic 分支完成。

## 17. Gates 与 Unknown

规划时没有新增已确认的用户产品 Gate。以下仅在实施 inventory 发现真实用户数据且无法安全保留/解释时升级：

- 一个 legacy Interview 同时有冲突 canonical owner/submission/opportunity 引用；
- 多个 typed Interview 指向同一 note，无法判断一轮还是重复登记；
- 真实 legacy 记录必须进入新模型，但用户无法确认 real/simulation、父 real、confirmed/scheduled/completed 日期或状态；
- 新形态 simulation 已存在跨机会/非 real parent，或 real/simulation Patch 约束已被违反；
- Submission frozen snapshot/PDF、Communication source、Raw/Wiki/Candidate 或附件引用在迁移前后不一致；
- source snapshot hash 在 apply 前变化或 SQLite integrity/foreign key 检查失败。

demo/case/legacy 歧义只标 `demo_legacy_defer`，不替用户拍板，也不阻塞新虚构闭环。普通工程选择（模块拆分、确定性 ID、索引名称、UI panel）不是用户 Gate。

尚待实施验证：届时 Production PID/version/schema/hash 与最新备份；真实 legacy 分类计数；schema v5 partial index 与现存 JSON 的兼容性；D 完整工作树能否无遗漏进入 E worktree；所有测试、浏览器、v4→v5 rehearsal、rollback/forward recovery。真实 AI、ChatGPT Voice、音频/转写质量、Production cutover、异机灾备、无损 v5→v4 逆迁移、Offer Domain 均未验证且不属于 E 验收。

附件中的用户请求文本在“二十九、输出 Batch E 正式”处结束，后续若原本还有未传入内容属于 Unknown；本计划只依据已收到的 1–28 节和明确的“只规划、停止”要求，不补造额外范围。

## 18. 反向审查结论

| 攻击问题 | 计划控制 |
| --- | --- |
| 1. 只确认进入面试但没日期 | Confirm 创建 pending，schedule 可空；phase 日期取 confirmed_on |
| 2. 改期创建新 Session | schedule/reschedule 原位 CAS；ID/owner不变 |
| 3. 暂时取消变 permanent cancelled | 单独 pending action 清空 schedule；cancel 是明确永久动作 |
| 4. completed 推进 Opportunity | Interview actions 无 Opportunity lifecycle 写权限；T04 比较完整 before/after |
| 5. 预设轮数 | real 是无上限 1:N；name 自由输入，不存 round enum |
| 6. 下一轮重置 phase date | phase 已 interview 时 Confirm 不保存 Opportunity |
| 7. simulation 脱离 real | server owner/type/parent 事务校验 + 唯一 scoped action |
| 8. simulation 产生 Patch | UI 无 GenerateResearchPatch；HTTP/service/storage 四层拒绝 + DB inventory 零断言；GenerateFinalReview 只有 Review schema |
| 9. 多选 Review 自动带 Raw | policy forbidden + Spy payload 检查 raw ID/content sentinel |
| 10. 最新 Resume 替代投递版 | compiler 只读 applications frozen snapshot；当前 document forbidden |
| 11. Raw 修正覆盖 Review | 独立 current records；只标 stale，不写 Review |
| 12. Review 编辑改 Research | SaveFinalReview 无 Research service 依赖；hash回归 |
| 13. Real Patch 自动 Apply | 独立 GenerateResearchPatch 只创建 pending proposal；用户 resolve + source/target CAS，同事务才 Apply |
| 14. Communication 改/archive 破坏 Interview | 只存稳定 source ID；include_archived read；无反向联动 |
| 15. Timeline 复制事实 | 只读 adapter；schema/测试断言无 Timeline 持久对象 |
| 16. legacy 名称猜 type | format 2 判别；round/title只显示，不参与映射 |
| 17. 两 Opportunity 串联 | 路径 owner、parent、review、source、proposal全链 scope 校验 |
| 18. 无模型不可用 | 手动 Domain 全独立；AI capability unavailable 不影响 CRUD |
| 19. 提前实现 Offer | E 无 Offer action/router；仅边界文案，旧门禁保留 |
| 20. 侵入 Employment/Project | forbidden patch target、Context scope及回归 hash保护 |
| 21. Context 再次全库扫描 | task policy + 明确 ID selection + source预算 + 实际 payload 验证 |
| 22. 多选 Review 重复/失效 | 去重、same-opportunity、revision/hash校验；snapshot stale 不改正本 |

额外反查：若不升 schema v5，D/v4 的 interview JourneyNote correction/candidate 仍能写入并绕过 current-only Raw 与 simulation 零 Patch，因此“复用 records、没有新业务表”不能成为继续使用 v4 的理由。若实现重新引入通用 `ProcessInterview`、让 GenerateFinalReview 产出 Patch、让 simulation 获得 GenerateResearchPatch、把通用 KnowledgeCandidate 直接当 Research Patch、复制旧 Raw 到 proposal、自动从 Communication 创建 real，或为 Timeline 写 event，即偏离本计划，应停止并修正边界。

## 19. 实施完成后的 review 与停止点

后续获授权实施时，先使用 `$workbench-implement`；完成后使用 `$workbench-review` 分别检查规格与工程规范。review 必须核对：Confirm 唯一 phase 权限、多轮日期、real/simulation parent、Preparation 柔性空项、GenerateFinalReview 与 GenerateResearchPatch 的意图/权限/输出分离、simulation 零 Patch、Submission frozen context、Review 多选不带 Raw、Raw current-only、real-only Patch确认、archived Communication 来源、Timeline projection、schema fence/recovery、Production 未变和非本期范围。

Batch E 的停止点是：完整 Interview Vertical 在临时虚构数据和最新 Production 备份隔离副本通过预定验收，证据写回本文并由 STATUS 链接。到此停止；不进入 Batch F、Offer、通用 Research/Raw/Patch、真实 AI/AI-Config、Employment / Project 或 Production Cutover。

当前计划不授权实施或部署。Production Career Data 必须保持 v1，直到未来单独、显式的 Production Cutover 授权。

## 20. 实施与两轴验收记录（2026-09-18）

状态：**独立隔离实施与验收通过；Production 未 Cutover；Batch E 到此停止。** 本次按 `$workbench-implement` 完成实现，并按 `$workbench-review` 分别做规格轴和工程规范轴验收。

### 20.1 实际交付

实现位于 `/Users/frog/Projects/Career-worktrees/batch-e`、分支 `codex/opportunity-e`，从完整 Batch D 工作树复制后开发。运行身份为 `0.6.0-batch-e` / schema v5；没有把源码、dist 或数据复制到 Production 项目或数据目录。

- 新增 `interview.py`：Real/Simulation、pending/scheduled/completed/cancelled、无日期 Confirm、同 ID 排期/改期/待重约、柔性 current Preparation、current-only Raw、固定五块 current Final Review、ContextSnapshot、当前 OpportunityResearch 和 real-only PatchProposal。
- `GenerateFinalReview` 与 `GenerateResearchPatch` 在 Domain/HTTP/UI/TestProvider 中分离。前者支持 real/simulation，只返回待编辑 Review 建议；后者只支持 real，只创建 pending Proposal，必须经用户编辑/接受/拒绝，接受后才 Apply。
- Simulation 必须绑定同机会 current real；service/storage/HTTP/UI 均无有效 Research Patch 能力。Migration inventory/verify 交叉核对 proposal 声明与实际来源 Session，不只信任 JSON 声明字段。
- Interview Context 读取 canonical Opportunity/JD、唯一实际 Submission 的冻结简历或明确“本次无简历”、当前 Research/Preparation，以及用户显式选择的 Communication/Wiki/历史 Final Review；不读取当前 ResumeDocument、未选 Raw、Feedback 或 Employment 私密资料。
- `timeline.py` 只增加 Interview adapter；每个 Session 一条即时投影，legacy Unknown 单列，未创建 `timeline_event`。archived Communication 仍能按稳定 ID 作为 Interview 来源只读显示。
- legacy typed Interview 保持 Unknown/只读。显式 `UpgradeLegacyInterview` 要求用户确认 type/name/status/日期和 simulation parent，保留同 ID 与 provenance；不按 `round`、文本或旧时间猜测。
- 新增 `migrate_interview.py` 与 hash-bound v4→v5 migration。迁移只建立 Preparation/Raw/Review/Research owner 唯一索引、manifest 与 schema fence，不重写旧 Interview 或其它业务行。
- 前端 `interview-ui.ts` 复用 Opportunity Workspace：确认真实面试、多轮列表、Preparation、Simulation Context Pack、Raw、Final Review、两个分离的生成动作和 Patch 编辑/接受/拒绝。Simulation 页面没有 Patch 按钮。

没有实现 Offer、真实 AI/AI-Config、通用 Raw/Patch 平台或 Employment/Project 修改。

### 20.2 自动测试与构建

最终完整回归：`PYTHONPATH=src .../python -m pytest -q` 为 **138 passed in 16.39s**。`npm run build` 通过 TypeScript 与 Vite 构建；仅保留既有 editor chunk size warning。`git diff --check` 通过。

覆盖包括：无日期/有日期 Confirm、首次 phase 日期、多轮不重写阶段日、排期/改期/pending/completed/cancelled、状态与 Opportunity 隔离、parent/owner、Preparation 空项、0/1/N real+simulation Review 选择、实际冻结 Submission 简历、无简历、Raw current-only 全库扫描、Final Review current-only、两个生成意图、无模型手工降级、Patch edit/accept/reject/stale、Simulation 零 Patch、archived Communication source、Timeline 无事实表、legacy 同 ID 显式升级、schema fence/迁移故障/重放和既有 Batch A–D 回归。

### 20.3 浏览器验收

在 TestProvider、临时 schema v5、非生产端口完成实际浏览器检查：submitted Workspace 无日期确认“业务一面”后立即显示 interview、当天 `phase_changed_on`、pending/尚未排期；Real Workspace 显示状态、柔性 Preparation、Simulation、当前 Raw/Review 和两个独立生成动作；Simulation 只显示 `GenerateFinalReview`，无 Patch 入口；Simulation Raw 保存后生成建议仅填入五块编辑区，未自动保存；Real Patch 实际经历生成 pending → 用户编辑 category/content → 保存 → 拒绝，页面读回 rejected 编辑内容；既有 accepted Patch 与 Research 保持；Timeline 点击同一 Interview 详情且无第二事实库。

验收期间始终只保留一个 Agent 创建的 in-app browser tab；每段验收后均关闭 tab 并停止 8785 临时服务。另清理了早期 Batch B 遗留的两个 `serve-isolated.py` 临时进程；Production PID 未动。

### 20.4 最新生产备份副本 migration rehearsal

实施前后只读核对实际 Production：PID `2994`，运行 `0.2.0`，数据目录 `/Users/frog/Library/Application Support/Career Data`，schema v1、integrity `ok`。SQLite sha256 仍为 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`；表计数仍为 `meta=1/current=24/records=27/applications=1/revisions=146`，唯一 artifact sha256 未变。

使用现有 backup 能力真实创建 `/Users/frog/Library/Application Support/Career Data-backups/batch-e-20260918T034438Z`，恢复到新的系统临时目录后，v1 integrity、全部 199 行、关键 ID、Submission/ResumeVersion/PDF/Raw/Wiki 引用和唯一附件 hash 与备份一致。随后在隔离副本重演 v1→v2→v3→v4→v5；最终 clean rehearsal verify 为 schema 5、`verified=true`、`differences=[]`、`rewritten_interviews=0`。

E dry-run 发现 1 条 legacy typed Interview、0 条 note-only、0 重复 Raw note、0 非法 Patch、0 Migration Gate、0 demo Gate；保持 legacy，不猜 type/status/date，不自动升级。私有 0600 证据位于 `/Users/frog/Library/Application Support/Career Migration Audits/batch-e-20260918T034438Z/`，用户正文未复制进仓库。

### 20.5 rollback / forward recovery

v5 开写前已把 pre-E v4 备份恢复到另一个全新目录，Batch D/v4 runtime 实际读取 schema 4；同一 runtime 对 v5 隔离副本在初始化前明确拒绝。没有通过直接改 `user_version` 伪造 rollback。

在 v5 隔离副本的明确 synthetic 分支写入 Opportunity、无简历 Submission、Real、Simulation、Preparation、Raw、Final Review、ContextSnapshot、pending→applied Patch 与 OpportunityResearch；随后真实 backup/restore 到新的 pristine 目录。启动 runtime 前备份/恢复 snapshot hash 完全一致；启动后 schema 5、Real/Simulation关键 ID、Research revision 和两条 Timeline Interview 投影均读回，`timeline_event=0`。

### 20.6 review 发现与结论

规格轴发现并修复：Final Review 生成幂等结果曾可能持久化 Raw 派生正文；Simulation 重放会被后来结束的 Opportunity 错误拒绝；选择器曾列出没有 Final Review 的 Session；Patch UI 缺少编辑动作。修复后 command 只存 source revision/hash、snapshot ID 和 suggestion hash；重放重算 TestProvider 建议并核对 hash，不保存正文；可选项只来自实际 current Review；Patch UI 支持编辑、接受、拒绝。

工程轴发现并修复：migration verify 曾只检查 `origin_interview_type` 声明，没有交叉核对实际来源 Session。现已按实际 `interview_format=2/type=real` 检查；全量测试和 clean rehearsal 重跑通过。

**规格轴：通过。** Confirm 是唯一阶段推进权限；多轮/Simulation/Preparation/Raw/Review、真实冻结 Submission Context、两个 AI 意图、real-only 用户确认 Patch 与纯投影 Timeline 符合本批范围。Simulation 实际零 Patch，未提前进入 Offer 或真实 AI。

**规范轴：通过。** scoped owner、CAS、幂等、短事务、模型调用后 source/target 复核、current-only 留存、schema fence、hash-bound migration、pre-write rollback、post-write forward recovery与旧入口门禁成立。没有已知可写 Interview 双写旁路；note-only legacy 只读兼容不被伪装成新 Session。

### 20.7 停止点与未验证项

Production 仍为 0.2.0/schema v1，未迁移、未重启、未执行业务 POST、未替换源码/dist。Batch E 到此停止，不进入 Batch F。

未验证：真实 AI/ModelGateway/AI-Config、ChatGPT Voice/音频/转写质量、Production v1→v5 Cutover、异机灾备、无损 v5→v4 逆迁移、Offer 领域与谈薪闭环。真实 Production legacy Interview 的业务 type/status/date 仍 Unknown；本次没有替用户做语义决定。Batch F 的隔离规划前置已满足，正式 Production Cutover 仍需后续显式授权。
