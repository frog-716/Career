# Opportunity Batch F — Offer Vertical

状态：**计划完成，尚未实施**。规划日期：2026-09-18。本轮仅使用 `$workbench-plan` 固定可执行范围、公共 Interface 与验收条件；未调用 `$workbench-implement`，未修改业务代码、schema、数据或 Production。

## 1. 范围、权威与当前基线

本批只交付一个纵向结果：仍在推进的 canonical Opportunity，由用户明确记录现实 Offer 后进入 `phase=offer`，维护一份当前 Offer 条件，以现有 Communication 记录谈薪，并由用户明确选择 `accepted / rejected / withdrawn` 结束机会；Offer、谈薪和结果都由现有真实对象投影到 Timeline，接受 Offer 不创建 Employment。

权威顺序为：本轮用户要求 > [authority](../00-authority.md) > 四份 Opportunity 正本（[Product](../target/opportunity/opportunity-product-model.md)、[Domain](../target/opportunity/opportunity-domain-model.md)、[UI Flow](../target/opportunity/opportunity-ui-flow.md)、[Context & Ingestion](../target/opportunity/context-ingestion.md)）> [Context Contract](../02-context-contract.md) > [Architecture](../03-architecture.md) > [Acceptance](../05-acceptance.md) > [Roadmap](../07-roadmap.md)。[Gap Analysis](../audit/OPPORTUNITY-GAP-ANALYSIS.md) 只提供历史映射与迁移建议，不覆盖本轮新决定。

实施基线是 `/Users/frog/Projects/Career-worktrees/batch-e` 的**完整 Batch E 工作树**，不是其 Git HEAD。已核对的代码与数据事实：

- E 隔离运行身份为 `0.6.0-batch-e` / schema v5；Opportunity、Submission、Communication、Interview 和 Timeline 已形成 B–E 人工闭环。
- `records.kind='offer'` 仍是 legacy typed 形态：`opportunity_id / occurred_at / terms / status / raw_note_id`，没有 format discriminator、受控更新、CAS、幂等或专属 HTTP/UI。
- `/api/opportunity-activity/offer` 与 Job scope `journey_note.kind=offer` 的新建均已返回 `lifecycle_action_pending`；当前没有 Offer 更新入口。旧记录只能经 activity/legacy 页面读取。
- `Opportunity.end` 已拥有唯一 `result` 写入规则，`accepted` 要求 `phase=offer`、同机会唯一 Offer、`confirmed_offer_id` 和明确 `offer_id`；它不创建 Employment。F 应深化这个边界，而不是增加第二套决定状态。
- Communication 当前格式为 2，只含 `type / occurred_on / content`；新建只允许 submitted 阶段，尚无 `purpose`，更新/归档不改变 Opportunity。
- Timeline 当前只投影 Opportunity 创建、Submission、未归档 Communication、Interview；没有 Offer/Result adapter，也没有 Timeline 事实表。
- 最新已记录 Production 基线为 `/Users/frog/Library/Application Support/Career Data`、PID 2994、runtime 0.2.0、schema v1。A 盘点有 1 条 demo/legacy typed Offer、0 个多 Offer 分组；其 terms/status/日期不因此获得新模型语义。

实施开始时必须重新只读核对 Production 进程、版本、数据目录、SQLite/附件 hash 与最新备份；本计划中的历史数值不能替代届时事实。

## 2. 用户可观察闭环与非目标

主路径固定为：

```text
submitted 或 interview + active Opportunity
  → 用户明确 RecordOffer
  → 原子创建唯一 Offer，phase=offer，phase_changed_on=动作业务日
  → Offer Workspace 查看/编辑一份当前条件
  → 0..N 次“记录谈薪沟通”产生 purpose=negotiation 的 CommunicationEvent
  → 用户在现实条件改变后明确 UpdateOffer；沟通本身不改 Offer
  → 用户明确 AcceptOffer / 招聘方结束 / 主动退出
  → Opportunity.result=accepted / rejected / withdrawn
  → result!=active 进入已结束 View，phase 仍为 offer
  → Submission、Interview、Offer、谈薪和结果历史继续可回看
```

Offer 基础闭环完全手工可用，不依赖模型、AI-Config、Research、RawSource、附件或 Offer Comparison。UI 可以说明“AI 分析/Offer 对比后续提供”，但不得渲染成可执行或已完成能力。

本批不实现：OfferVersion、Negotiation/SalaryNegotiation 新对象、Compensation Engine、税务或合同判断、Offer Comparison/评分/推荐、Offer AI Skill、ModelGateway、AI-Config、真实 AI、通用 Raw/Patch/附件平台、自动从 Communication 提炼条款、自动 Employment、Employment/Project 重构、Production Cutover 或 `.codex/config.toml` 修改。

## 3. Domain 不变量

1. 每个 canonical Opportunity 最多一份 canonical current Offer；Offer 的 owner 创建后不可变，alias 与 canonical URL 必须解析到同一对象集合。
2. `RecordOffer` 是唯一能创建 canonical Offer、把 active Opportunity 推进到 `phase=offer` 并写 `phase_changed_on` 的动作。Interview completed、Communication 文本、AI、Timeline、legacy status 和前端组合请求均无此权限。
3. `RecordOffer` 只允许 `phase ∈ {submitted, interview}` 且 `result=active`；`resume`、已经 offer、ended 或 legacy read-only Opportunity 均拒绝。现实中的独立新 Offer/岗位使用新的 Opportunity。
4. `phase_changed_on` 使用 RecordOffer 的服务端 Asia/Shanghai 业务日，不使用用户补录的 `received_on` 冒充动作时间；`received_on` 是 Offer 自己的现实日期。
5. Offer 当前条件可 CAS 原位更新，不创建 OfferVersion，不把每次 Update 写入 Timeline，也不在 command/revision/log 中暗存旧 terms 正文。
6. Offer 的最终决定只存在于 `Opportunity.result`；Offer 不持久化第二套 `status/decision`。DTO 可从 Opportunity 投影当前决定。
7. `AcceptOffer` 只允许 canonical Offer 阶段、active Opportunity，并同时校验 Opportunity revision、Offer revision 和 owner；它只写 `result=accepted/result_changed_at`，不创建或修改 Employment/Project。
8. `rejected` 与 `withdrawn` 继续复用唯一 Opportunity 结束动作。三种最终结果都保留 `phase=offer`，只由 `result != active` 进入已结束 View。
9. ended Opportunity 不能 UpdateOffer、RecordOffer 或新增谈薪 Communication；既有 Communication 是否允许更正/归档延续 Batch D 的历史修正规则，不反向改变 Offer/result。
10. Communication `purpose=negotiation` 只表达现实谈薪沟通。Create/Update/Archive Communication 永远没有 Offer 或 Opportunity 生命周期写权限；UpdateOffer 也不创建 Communication。
11. Timeline 永远是查询投影。Offer、Communication 和 Opportunity result 是唯一事实源；不得新增 OfferTimelineEvent、DecisionEvent、ResultEvent 或 timeline 表。
12. legacy Offer 默认 Unknown/只读；不得从旧 `status`、Application status、文本中的 “Offer”、JourneyPlan 或记录存在推断 phase/result/current terms。
13. 所有新写动作必须处于一个 `BEGIN IMMEDIATE` 短事务，拥有幂等 key；修改当前对象必须带 expected revision。跨 owner 返回 404，字段错误 422，状态/CAS/幂等异体/legacy 未核对冲突返回 409。

## 4. Offer Domain 模型与存储判断

本批不为名称整齐新增业务表。继续使用 `records.kind='offer'` 的稳定 ID，并以 `offer_format=2` 确定性区分 canonical current Offer 与 legacy typed Offer。理由：

- 现有 typed ID、`raw_note_id` 和 legacy provenance 可以保留；
- `records` 已被 Communication/Interview 用作受 Domain service 控制的 current typed 对象；
- Offer 不需要数据库级版本链，原位 body 更新符合 current-only 语义；
- SQLite `BEGIN IMMEDIATE` 加同 owner 扫描足以在本地单进程中串行保证 0..1；不为一个可由 service 完整保护的 JSON owner 机械新增表或索引。

canonical body 至少包含：

| 字段 | 规则 |
| --- | --- |
| `id` / `offer_format` | 稳定 ID；新格式固定为 2 |
| `opportunity_id` | canonical owner，创建后不可改 |
| `received_on` | `YYYY-MM-DD`；RecordOffer 可由 UI 默认今天，服务端仍校验并保存用户确认值 |
| `terms` | §5 的完整当前条件对象；允许部分为空 |
| `raw_note_id?` | 只保留已有 legacy 原件稳定引用；F 不新增上传/粘贴 Raw 接口 |
| `created_at / updated_at` | 创建时间不可改，更新时刷新 `updated_at` |
| `revision` | 从 0 开始，每次成功 Update 加一；RecordOffer 后 Opportunity revision 也因 phase 改变而增加 |
| `legacy_provenance?` | 仅显式升级时保存原 typed body/hash与已有来源引用，不作为 OfferVersion 展示 |

`decision/status`、`result_changed_at` 不保存在 Offer；读取 DTO 从 owner Opportunity 投影 `result/result_changed_at`。`confirmed_offer_id` 继续由 Opportunity 保存为当前唯一 Offer 指针，service 每次核对它与 Offer owner/数量一致。

## 5. current terms 与 compensation 最小设计

`terms` 使用固定外壳、可选文本内容，保存用户确认后的当前条件：

```text
terms
├── offered_role_title: string
├── location: string
├── start_date: YYYY-MM-DD | null
├── employment_type: string
├── probation: string
├── benefits: string
├── compensation
│   ├── guaranteed_cash: string
│   ├── variable_cash: string
│   ├── equity: string
│   ├── one_time: string
│   └── notes: string
└── other_terms: string
```

`offered_role_title` 只记录 Offer 中用户明确确认的正式岗位名称，尤其用于它与 Opportunity 岗位名称存在现实差异的情况；它不是 Opportunity title 的副本。地点、入职日、用工类型、试用期和福利同样只保存用户明确确认属于 Offer 条件的内容。薪酬只按“保证现金 / 浮动现金 / 权益 / 一次性项目 / 补充说明”分栏，足以避免把条件收入和现金混为一谈。所有薪酬字段仍是用户原样文本，例如 `25k/月 × 14，税前，CNY`；本批不解析数字、不计算年包、不统一币种、不推断税前税后、不设计薪级或归属期模型。

空字符串表示尚未确认，不表示现实条件为零。RecordOffer 可只确认收到日期并稍后补齐条件；不得从 Opportunity、JD、Research 或 Communication 自动填入 `offered_role_title`、location 或其它 Offer 条件。UI 可以把 Opportunity 岗位名称作为只读上下文提示，但不得把它作为表单默认值或未经用户确认写入 Offer。

`other_terms` 承载保密、有效期、工作时间、特殊约束等尚不值得稳定结构化的内容。真实使用若证明需要数值比较，再从这些保留原文中显式迁移；F 不提前实现 Comparison schema。

## 6. 公共 Domain / HTTP Interface

所有写接口只接受列明字段；不得提供通用 `PATCH /offer/status` 或 `PATCH /opportunity/phase`。

### 6.1 RecordOffer

```text
POST /api/opportunities/{opportunity_id}/offer
{
  received_on,
  terms,
  expected_opportunity_revision,
  idempotency_key
}
```

同一事务：解析 alias/canonical owner → 幂等检查 → 校验 active 与 phase → 扫描 canonical/legacy 冲突 → 创建 `offer_format=2` → 更新 Opportunity `phase=offer`、`phase_changed_on=动作业务日`、`phase_source=RecordOffer`、`confirmed_offer_id` → bump epoch。任何一步失败全部回滚。

同 key 同 body 重放同一成功，不新增对象；同 key 异体 409。另一 key 再次 RecordOffer 明确 409，不把它当 UpdateOffer。RecordOffer 与 EndOpportunity 并发由 Opportunity expected revision 和写事务保证只有合法序列成功。

### 6.2 GetOffer

```text
GET /api/opportunities/{opportunity_id}/offer
GET /api/opportunities/{opportunity_id}/offer/{offer_id}
```

singular GET 返回 canonical current Offer、明确 legacy DTO，或 `null/404`；列表需求不形成第二个接口。跨机会 `offer_id` 按 404 处理。DTO 额外投影 owner 的 `phase/result/result_changed_at`，但这些字段不可经 Offer 更新。

### 6.3 UpdateOffer

```text
PUT /api/opportunities/{opportunity_id}/offer/{offer_id}
{
  received_on,
  terms,
  expected_revision,
  idempotency_key
}
```

采用完整当前值替换，避免前端自己组合局部 patch。只允许 active、phase=offer、同 owner、`offer_format=2`；成功只更新 Offer 的 `received_on/terms/updated_at/revision`，不改 Opportunity phase/result/revision，不创建 Communication/Timeline/Employment。

幂等 command 只保存 action、owner/id、request hash、resulting revision/hash，不保存旧 terms 或完整返回正文；重放不再次写入。后续已有更新时，旧 key 只报告已应用并要求刷新当前值，不把历史快照伪装成当前 Offer。

### 6.4 AcceptOffer 与其它结束动作

```text
POST /api/opportunities/{opportunity_id}/offer/{offer_id}/accept
{
  expected_opportunity_revision,
  expected_offer_revision,
  idempotency_key
}
```

`AcceptOffer` 校验当前 Offer 条件 revision 后调用同一个内部 Opportunity result transition，只写 `accepted/result_changed_at`。现有 `POST /api/opportunities/{id}/end` 保留 `rejected/withdrawn`；旧客户端向 `/end` 发送 accepted 时必须成为 `AcceptOffer` 的兼容 adapter，执行同一套 owner/Offer 校验，不能形成第二份写实现。

用户文案固定：`accepted=接受 Offer`、`rejected=招聘方结束机会`、`withdrawn=主动退出`。Domain enum 不改。Accept 双击同 key幂等；Accept 与 Withdraw/Reject 使用同一 Opportunity revision，竞争时只有一个结果成功，失败方 409 并保留输入。

### 6.5 UpgradeLegacyOffer

```text
POST /api/opportunities/{opportunity_id}/offer/{offer_id}/upgrade
{
  received_on,
  terms,
  expected_opportunity_revision,
  expected_legacy_hash,
  idempotency_key,
  confirmed: true
}
```

只接受一个真实 typed legacy Offer、明确 canonical owner、active 且允许 RecordOffer 的 phase，并要求当前机会没有其它 canonical/legacy Offer 冲突。动作复用同一 typed ID，保留 `raw_note_id/created_at` 和 immutable `legacy_provenance`，原子写 `offer_format=2` 并执行与 RecordOffer 相同的 phase transition。note-only 继续只读，不生成虚构 typed ID。ended、owner/date/当前 terms 未确认或多个 Offer 时保持 Unknown/Gate，不自动升级。

## 7. negotiation Communication

现有 CommunicationEvent 最小增加 `purpose ∈ {general, negotiation}`：

- 新建兼容请求未传 purpose 时只允许按既有 submitted 路径保存 `general`；已有 format 2 记录读取时确定性投影 `general`，无需批量重写。
- `purpose=negotiation` 只允许 active、phase=offer、已有同 owner canonical Offer 时创建；仍使用现有 `type=text|phone|other`、日期、正文、CAS/幂等与 archive。
- purpose 创建后不可改。Update 不接收 purpose，只修正 type/date/content 并保留原 purpose；legacy Communication 不因含薪酬/Offer文字猜成 negotiation。
- 结束后不能新增沟通；既有沟通的更正/归档延续 Batch D 规则。archive 后从默认列表和 Timeline 消失，稳定 ID 仍保留。
- Offer Workspace 的 `[记录谈薪沟通]` 调用同一个 Communication Domain Action；不得创建 Negotiation service/table，也不得在 Communication 保存/更新时调用 Offer service。

## 8. Offer Workspace 与历史回看

Opportunity `phase=offer && result=active` 时，阶段区显示：收到日期、当前 terms、编辑 Offer、记录谈薪沟通、接受 Offer、主动退出；“招聘方结束机会”放入结束动作/次级菜单。AI 分析和 Offer 对比只显示清晰的后续边界，不放可点击假入口。

Offer Detail 属于当前 Opportunity Workspace，可通过稳定 Offer anchor/ID打开，展示当前条件、收到日期、可用的 legacy source link、`purpose=negotiation` 沟通和当前 result。它不是一级导航或全局工作台。

机会 ended 后，Workspace 仍能查看 Submission、Interview、Offer、Communication 和 Timeline；Offer 编辑与新增谈薪按钮禁用/不存在。accepted 后不显示“已创建 Employment”，Employment 数量和内容必须保持不变。

## 9. Timeline 投影

在现有查询投影增加：

1. canonical Offer：`occurred_on=received_on`，标题“收到 Offer”，摘要明确为“当前条件”而非伪造收到当天的历史条款，目标跳回 Offer Detail。
2. negotiation Communication：沿用 Communication 对象，标题“谈薪沟通”；archive 后不投影。
3. Opportunity result：`occurred_on=business_day(result_changed_at)`，标题分别为“接受 Offer / 招聘方结束机会 / 主动退出”，目标跳回 Opportunity ended Workspace。

Offer 每次 Update 只更新同一 Offer 投影摘要，不新增事件。排序沿用稳定日期、timestamp、source rank、ID；Unknown 日期进入待核对区，不赋今天。schema/inventory 测试断言没有 `timeline_event`、OfferTimelineEvent、DecisionEvent 或 ResultEvent 持久对象。

## 10. Legacy Offer 与现有数据

`offer_format != 2` 的 typed Offer 和 note-only Offer 都是 legacy：

- typed 保留真实 ID、owner、raw_note_id、旧 terms/status/occurred_at 与 source 状态；UI 标“历史 Offer · 待核对”。
- `status=pending/accepted/...` 不映射 Opportunity.result；`occurred_at` 不自动认作 received_on；旧 terms 不自动成为 current terms。
- note-only 保留 legacy projection，不进入 canonical 0..1 计数和正式 Offer/Result Timeline。
- 一个 owner 有多个 typed/canonical Offer、owner 不可解析、raw_note/source 缺失、`confirmed_offer_id` 冲突或已有 ended/accepted 语义不一致时进入 Migration Gate；不删、不合并、不挑“最新”。
- 当前已知 1 条 demo/legacy typed Offer只标 `demo_legacy_defer`，不替用户升级，也不阻塞新的虚构闭环。实施 inventory 若发现新的真实资料，再按届时事实判断。

## 11. schema v5 决策与兼容期

**规划结论：优先保持 schema v5，不创建 v6 migration。** 这不是因为字段少，而是当前兼容性证据表明 E/v5 runtime：

- 已阻止两个旧 Offer 新建入口；
- 没有 typed Offer 更新接口；
- 不会删除 JSON 中不认识的 Offer 字段；
- 对 accepted 已要求唯一同 owner Offer 与 `confirmed_offer_id`，行为与 F 的结果正本一致；
- Communication update 原位保留未知 `purpose` 字段，旧 runtime 也不能在 offer 阶段新增一般沟通。

F 只新增 `offer_format=2` body、service 路由和 Communication purpose，不新增 table/index/SQLite constraint。实施必须用冻结 E runtime 打开含 F 写入的 v5 副本，实际证明：可启动、不会制造第二个 Offer、旧 Offer/JourneyNote 写入口仍拒绝、现有合法 result 约束不被绕过、未知字段不丢失。

如果测试发现 E/v5 runtime 能创建/覆盖 canonical Offer、清除 purpose/terms、绕过 0..1 或让 legacy 写入成为第二正本，立即停止并把“schema v6 fence + 最小 migration”作为工程 Gate 更新本计划；不得在相同 v5 下掩盖不兼容。仅运行版本变为 `0.7.0-batch-f` 不构成升 schema 的理由。

## 12. 修改范围与实施顺序

实施必须从完整 `/Users/frog/Projects/Career-worktrees/batch-e` 创建新的独立 `batch-f` worktree/`codex/opportunity-f`，不在 Production 项目目录实现业务代码。

| 顺序 | 预计文件/模块 | 完成边界 |
| --- | --- | --- |
| F1 固定测试与基线 | 新 `tests/test_offer.py`，局部 timeline/communication/compat tests；本文/STATUS | 固定动作矩阵、Production只读基线、E工作树hash |
| F2 Offer 深模块 | 新 `src/workbench/offer.py`；`app.py` | DTO、owner、Record/Get/Update/Accept/Upgrade、CAS/幂等、current-only留存 |
| F3 生命周期整合 | `opportunity.py` | 共享唯一 result transition；旧 accepted route只作adapter；无通用phase/status patch |
| F4 谈薪 | `communication.py` | purpose最小扩展、offer阶段创建门禁、原CRUD/archive语义保持 |
| F5 Timeline | `timeline.py` | Offer、negotiation、result纯投影；无事实表 |
| F6 Legacy门禁 | `engagement.py`、必要时`journey.py` | legacy读取/显式升级；旧写入口继续拒绝，不影响Interview/Employment note |
| F7 UI | `frontend/src/opportunity-ui.ts`，复杂时新增 `offer-ui.ts`，局部样式/main state | RecordOffer、Offer Workspace、terms编辑、谈薪、决定、历史回看；无全局Offer导航 |
| F8 版本/文档 | `core.py`仅APP_VERSION，后端/前端README、本文实施记录、STATUS | schema仍5并记录兼容证据；不改目标原文/审计 |

默认不改 schema DDL、migration chain、Resume/Submission/Interview/Research/Provider/Employment/Project、附件系统、四份目标正本或 `.codex/config.toml`。只有测试证明 v5 不安全时才先停下调整 schema 计划，不能静默扩范围。

## 13. 自动测试：编码前固定断言

以下测试在计划阶段均为**待运行**，不得提前标通过：

| ID | 固定断言 |
| --- | --- |
| T01 RecordOffer | submitted/interview+active 成功；Offer+phase+phase date+confirmed ID同事务；phase date取动作业务日，received_on独立；resume/offer/ended/legacy拒绝 |
| T02 0..1/幂等 | 双击同 key 只一条；同 key 异体拒绝；新 key 第二份拒绝；alias/canonical看到同一 ID |
| T03 RecordOffer竞争 | RecordOffer 与 rejected/withdrawn 并发只有合法一方成功；失败无半条 Offer、无半个 phase |
| T04 terms | 全部字段可部分为空；`offered_role_title`、location等不从Opportunity/JD/Research/Communication复制；长度/日期/shape严格校验；薪酬文本原样保存，不计算/归一化/猜币种 |
| T05 UpdateOffer | 同 owner CAS、幂等、重启可读；stale/跨owner/legacy/ended拒绝；只改当前 body，不产生 OfferVersion/revision旧terms/Timeline事件 |
| T06 Communication | negotiation只允许 active offer+canonical Offer；general旧路径保持；purpose不可改；两次沟通不改Offer/Opportunity；archive从列表/Timeline消失 |
| T07 AcceptOffer | 校验Opportunity+Offer双revision；同key幂等；只改result/result_changed_at；phase/Offer terms/Interview/Submission不变 |
| T08 最终竞争 | Accept vs Withdraw/Reject只有一个结果；结果一旦结束不能换；accepted只在offer+唯一canonical Offer成立 |
| T09 Employment边界 | accepted前后所有Employment/Project行、ID/body hash不变，不调用对应service，不新增origin_offer_id |
| T10 ended View | accepted/rejected/withdrawn均进入ended，保留offer phase与phase_changed_on；历史对象仍可读，Offer不可再更新/新增谈薪 |
| T11 Timeline | Offer一条、每条未归档谈薪一条、result一条；Offer Update不增项；稳定排序/target可达；无Timeline事实kind/table |
| T12 Legacy | typed/note-only/缺source/未知owner/date/status/多Offer分类；不映射status/application/文本；显式upgrade同ID且保留legacy provenance |
| T13 旧旁路 | activity Offer、JourneyNote Offer、万能Opportunity/Job phase/status、Application status均不能创建Offer或推进phase；旧accepted adapter走唯一Accept实现 |
| T14 v5兼容 | 冻结E runtime打开F v5写入后不丢字段、不生成第二正本；所有旧Offer写入口仍拒绝；若失败则触发v6 Gate |
| T15 current-only留存 | DB全库扫描证明旧terms没有被command/revision/run/proposal/log暗存；legacy provenance只存在显式upgrade的一次原始快照 |
| T16 两机会隔离 | Offer/terms/谈薪/result/Timeline不串；跨owner均404；相同幂等key在不同owner有独立作用域 |
| T17 B–E回归 | Company/Opportunity、Resume/Greeting/Submission/PDF、Communication archive、Interview/Simulation/Research Patch、Timeline全部通过 |
| T18 非本期 | 无Provider网络调用；AI/Comparison按钮不可执行；Employment/Project、Raw/Wiki/Profile/Research hash不变 |
| T19 backup/recovery | 含F新写入v5备份恢复后Offer/terms/revision/purpose/result/历史ID和附件hash一致；E/F runtime兼容结果可重复 |

先跑 Offer/Communication/Timeline 定向测试；整合后因 router、Opportunity lifecycle 和主 Workspace 受影响，运行一次完整 pytest、一次 TypeScript/Vite build。证据充分后停止，不重复全量测试凑数量。

## 14. 浏览器验收

全部使用临时虚构 schema v5、非生产端口和一个受控浏览器 tab；结束立即关闭 Agent 创建的 tab并停止临时服务。

| ID | 可观察结果 |
| --- | --- |
| U01 | submitted Opportunity 明确 RecordOffer，显示唯一 Offer Workspace、收到日期、当前条件；phase变Offer，阶段日期为动作日；Opportunity岗位只作提示，空的offered_role_title/location保持未确认 |
| U02 | interview Opportunity 可直接RecordOffer，不要求终面/所有轮次completed；Interview completed本身不自动推进 |
| U03 | 编辑当前条件后刷新/重启仍是一份Offer；双窗口旧revision保存409且保留输入，没有Offer v2/v3历史 |
| U04 | 连续记录两次谈薪Communication并显示在Offer区/Timeline；沟通文字含28k也不自动改terms，用户Update后当前值才变化 |
| U05 | Offer Update不改变result、不新增Timeline项；Offer item只更新当前摘要，两个谈薪事件仍独立存在 |
| U06 | AcceptOffer后进入已结束View，phase仍Offer；Offer、Interview、Submission、PDF和谈薪仍可查看，Offer编辑/新增谈薪不可用 |
| U07 | 独立机会分别验证withdrawn与rejected，展示文案区分用户退出和招聘方结束；两者都不改phase |
| U08 | 两窗口Accept/Withdraw竞争只产生一个最终result；Accept旧Offer revision被拒绝并要求刷新条件 |
| U09 | 两Opportunity各自Offer、谈薪和结果完全隔离；旧Job alias与canonical URL进入同一Workspace/Offer |
| U10 | legacy typed Offer显示Unknown/待核对，旧status/terms不自动接管；显式完整核对后同ID升级；note-only继续legacy |
| U11 | 页面无Offer Comparison、评分、自动推荐、AI假结果或Employment自动创建；Employment列表前后完全一致 |
| U12 | 最新Production备份的隔离v5副本能读legacy Offer；synthetic分支完成Record→Update→谈薪→Accept后，备份恢复副本通过F浏览器回读 |

浏览器主链优先用 submitted Opportunity；另单独覆盖 interview 直达 Offer。不得在 Production 副本的真实用户对象上写 synthetic 数据，必须先复制出明确可丢弃分支。

## 15. Production备份、rehearsal、rollback与forward recovery

实施时按顺序执行，所有写入只发生在新的隔离目录：

1. 重新只读确认 Production PID/runtime、`/api/state` data_dir、schema/integrity、表计数、SQLite逻辑/物理hash和附件hash；不POST、不重启。
2. 使用现有 backup 能力创建届时最新真实备份，恢复到全新临时目录并先验证 v1 全表/关键ID/Submission/PDF/Raw/Wiki/附件一致。
3. 在恢复副本重新执行已验收 v1→v2→v3→v4→v5 链；每段重新生成 hash-bound plan，不复用旧报告，不替 legacy 选择语义。
4. 在 v5 副本只读盘点所有 Offer：format、owner、数量、confirmed pointer、旧status/terms、raw_note/source、Opportunity phase/result和Application status；不执行UpgradeLegacyOffer。
5. 若 §11 兼容证据成立，F runtime 直接接受 v5，不执行 schema migration。冻结E runtime也打开同一F数据副本验证安全兼容；两次启动前后逻辑hash差异必须只来自已知初始化/命令，不允许业务字段丢失。
6. **开写前 rollback**：恢复 pre-F v5 备份到另一个全新目录，用E runtime实际启动，读回全部B–E数据；不靠手改schema。
7. 在恢复副本的独立 synthetic 分支走两个Opportunity：RecordOffer、两次negotiation、Update、Accept以及另一条Withdraw/Reject；同时保留legacy Offer不升级。
8. **开写后 forward recovery**：用F代码备份含新写入的v5数据，再恢复到新的空目录；核对Offer ID/body/revision、Communication purpose、Opportunity phase/result、Timeline投影、Submission/Interview/PDF及所有附件hash，并用F浏览器读回。
9. 证明代码回退到E时不会破坏F数据：E可启动/读取v5，旧Offer写入口仍拒绝且未知F字段不被更新动作删除；功能降级必须明确，不把E读到的canonical Offer宣称为完整F Workspace。
10. 最后再次只读核对 Production runtime/schema/hash/计数/附件，证明仍为v1且没有Cutover、重启或业务POST。

如果实施改判需要v6，则必须先把步骤改为显式 v5→v6 dry-run/apply/verify、v5 runtime拒绝v6、pre-F rollback和v6 forward recovery，再编码；不得沿用本节“同schema兼容”结论。

## 16. Gates 与 Unknown

计划阶段没有新的已确认用户产品 Gate。仅以下真实数据或兼容性事实可在实施时升级为 Gate：

- 同一 canonical owner 存在多个 typed/canonical Offer，无法由用户确认哪一个是当前 Offer；
- legacy Offer owner、raw source、received_on、current terms 或既有 result 无法保留且真实用户要求升级；
- `confirmed_offer_id` 指向缺失/跨owner Offer，或 accepted Opportunity 没有唯一可核对 Offer；
- 冻结E/v5 runtime 能写坏/覆盖F Offer、清除purpose、恢复旧Offer双写或绕过0..1；
- 迁移链/备份恢复出现SQLite integrity、外键/应用引用或附件hash差异；
- Production 在备份期间发生写入导致source snapshot变化。

demo/legacy 的单条案例 Offer、旧 `status=pending`、JourneyPlan=offer 或 Application status 只标 `demo_legacy_defer`，不升级成用户产品Gate，不自动迁移。普通字段命名、UI排版、模块文件拆分、deterministic command ID等由实施自主解决。

尚待实施验证：最新Production事实与Offer计数、v5双向运行兼容、legacy显式upgrade的实际UI、全部测试/浏览器/恢复。真实AI、Offer附件/Raw上传、Offer Comparison、数值薪酬比较、税务合同判断、Production Cutover、异机灾备和无损F数据降级到旧产品体验均不属于F验收。

## 17. 反向审查

| 攻击问题 | 计划控制 |
| --- | --- |
| Interview completed偷偷创建Offer | Interview action没有Offer依赖；只有RecordOffer同时写Offer+phase，T01/T13核对 |
| Communication含“Offer”自动推进 | Communication无生命周期写权限；字符串不参与phase，T06 |
| 一个Opportunity创建两个Offer | BEGIN IMMEDIATE内owner扫描、confirmed pointer与第二key拒绝，T02/T03 |
| 谈薪变化创建OfferVersion | Update原位覆盖current body；全库旧terms扫描，T05/T15 |
| UpdateOffer偷偷accepted | Update不调用result transition，前后Opportunity hash断言，T05 |
| accepted自动创建Employment | Accept只调用Opportunity transition；Employment/Project全表hash，T09/U11 |
| accepted/rejected/withdrawn变phase | 三种只写result；phase仍offer，T07/T10 |
| 条件变成HR系统 | 七类稳定文本＋other_terms，无组织/审批/合同/薪级模型 |
| Compensation过度设计 | 只分保证/浮动/权益/一次性/说明文本，不解析或计算 |
| Communication获得Offer写权限 | 两个service单向独立；T06比较Offer hash |
| Timeline复制事实 | 只读projector、无事件kind/table，T11 |
| Offer Update制造Timeline噪声 | 一个Offer投影原位更新摘要，不追加变更事件 |
| Application/legacy status猜accepted | 只接受显式AcceptOffer；legacy status保留Unknown，T12/T13 |
| Offer Comparison侵入 | 无API/UI/评分/排序；只保留可读current terms |
| AI成为基础依赖 | F无Provider调用；手动全链断网可用，T18 |
| 两机会Offer串联 | 所有接口完整owner scope与404，T16/U09 |
| old Job alias形成第二Offer | alias先canonicalize，同集合扫描，T02/U09 |
| ended后偷改Offer | Update/Create negotiation先校验active，T05/T10 |
| Employment/Project被联动 | 允许文件不含两模块，hash与浏览器回归，T09/T18 |
| schema按编号升级 | 默认保持v5；只有旧runtime可破坏写契约才触发v6 Gate |

额外反查：把 decision 同时存入 Offer 会与 `Opportunity.result` 形成双正本，因此计划明确只在 DTO 投影；把每次幂等返回全文写进 command 会暗中形成 terms 历史，因此 command 只存hash/ID/revision；把 `received_on` 当 `phase_changed_on` 会伪造用户动作日期，因此两者保持独立。

## 18. review checklist

`$workbench-review` 必须分别检查：

**规格轴**：现实Offer仅由RecordOffer进入；0..1 current；terms最小且可编辑；谈薪复用Communication；三个result语义与ended View；Accept无Employment；Offer/Result Timeline纯投影；legacy不猜；AI/Comparison/Raw上传未侵入。

**规范轴**：owner scope、CAS/幂等/并发、current-only留存、旧写入口、alias收敛、v5兼容证据、备份恢复、Production不变、Employment/Project hash、无网络调用和单浏览器tab收口。review发现的问题必须修复并重新跑直接受影响的验收；不得以扩大产品目标让测试变绿。

## 19. 明确停止点

本轮在本文与STATUS登记完成后停止。没有执行代码、schema、测试、浏览器、备份、迁移或Production动作；上文全部测试与运行结果仍是待实施验收条件。

未来用户明确调用 `$workbench-implement` 后，F 实施才从完整 E worktree 创建独立 F worktree，并在实现、自动测试、浏览器、最新Production备份隔离rehearsal和 `$workbench-review` 全部通过后停止。不得自动进入 Batch G、Offer Comparison、AI-Config、ModelGateway、真实AI、Employment/Project重构或Production Cutover。

## 20. 实施证据与 review 结论（2026-09-18）

### 20.1 实际实现候选

实施位于独立 worktree `/Users/frog/Projects/Career-worktrees/batch-f`、分支 `codex/opportunity-f`，来源是完整 Batch E 工作树。候选运行身份为 `0.7.0-batch-f`，当前仍接受 schema v5；它没有进入 Production，也不是已通过 cutover 的交付。

本批候选新增 `src/workbench/offer.py`：在既有 `records.kind='offer'` 身份上以 `offer_format=2` 表达唯一 current Offer，提供 Record/Get/Update/Accept/legacy upgrade。RecordOffer 在一个 SQLite 写事务内创建 Offer、推进 phase、写服务端业务日和 `confirmed_offer_id`；UpdateOffer 原位 CAS；AcceptOffer 调用 Opportunity 唯一 result transition，零 Employment/Project 副作用。`terms` 只接受固定文本结构；`offered_role_title`、location 和其它条件全部来自本次用户提交，空值保持未确认，不从 Opportunity/JD/Research/Communication 补值。

`communication.py` 增加 `purpose=general|negotiation`；谈薪只允许 active offer + canonical Offer，更新不能改变 purpose，归档规则不变。`timeline.py` 增加 current Offer、谈薪 Communication 与 Opportunity result 的只读投影，没有新增事实表/记录。旧 `/end accepted` 在 F runtime 中只作为 AcceptOffer adapter；legacy Offer 仍须显式完整核对后同 ID 升级。

前端新增 `frontend/src/offer-ui.ts`，在同一 Opportunity Workspace 提供 Record/Edit、两次谈薪、Accept、legacy 核对和 ended 历史回看。表单明确显示 Opportunity 岗位只作上下文。浏览器验收中复现了深链接切换后 scoped Offer/Timeline 沿用前一机会数据的问题；后端 owner 校验返回 404，未发生串写。`main.ts` 已增加目标 ID 重新加载和 load token，修复后在两个 Opportunity 间往返验证 Offer、Timeline 与编辑 owner 均隔离。

变更相对完整 E 基线只涉及：`offer.py`、`app.py`、`core.py`、`opportunity.py`、`communication.py`、`timeline.py`、`offer-ui.ts`、`opportunity-ui.ts`、`main.ts`、局部样式、两份模块 README、`tests/test_offer.py`、一条因 F legacy 门禁而失效的旧迁移断言、本文与 STATUS。Employment、Project、Provider、Context、Research、Resume、Submission、Interview 实现没有作为 F 修改。

### 20.2 自动测试与构建

- 定向 Offer/兼容回归：`12 passed`。
- 完整 Python 回归：`149 passed in 15.79s`。
- `npm run build`：TypeScript 与 Vite build 成功；仅保留既有大 chunk 提示。
- `git diff --check`：通过。
- 自动测试覆盖 RecordOffer 原子性/0..1/竞争、无字段补值、current-only/CAS/幂等、谈薪隔离、三种结果、零 Employment、legacy upgrade/defer、纯投影 Timeline、跨 owner、旧旁路与恢复读取。

完整回归中先发现两条 Batch B 断言：错误 offer_id 的旧 accepted route 返回 404，以及 legacy Offer 可直接 accepted。前者在 F adapter 收敛为既有 422；后者按本批预先固定的 legacy Unknown/显式 upgrade 规则改为 409，并增加 canonical Offer 的旧 accepted adapter 正向测试，没有通过放宽产品门禁让测试变绿。

### 20.3 浏览器验收

使用一个 Agent 创建的隐藏 in-app browser tab、虚构 schema v5 与非生产端口完成：submitted RecordOffer 空 terms、Opportunity title 不自动带入、明确编辑岗位/地点/薪酬、外部并发导致 409 且表单输入保留、两次谈薪、Accept 后 ended 历史回看、独立 rejected/withdrawn、pending Interview 直接 RecordOffer、legacy Unknown 与同 ID 显式 upgrade、两个 Opportunity 往返隔离。恢复副本另行回读 accepted Offer、revision 1、两次谈薪和纯投影 Timeline。控制台 error/warning 为 0；验收 tab 已关闭，两个临时服务均已停止。

### 20.4 最新生产备份、迁移与恢复证据

实施前只读确认 Production：PID 2994、runtime `0.2.0`、数据目录 `/Users/frog/Library/Application Support/Career Data`、schema v1、integrity ok；表计数 `meta=1/current=24/records=27/applications=1/revisions=146`。数据库 sha256 为 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`，唯一附件 sha256 为 `8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。

使用现有 backup 能力真实创建 `/Users/frog/Library/Application Support/Career Data-backups/career-backup-80cb0ef5-a845-454f-89ba-c287b8cabd91`，恢复到新的系统临时目录并通过 v1 全表、ID、引用、Submission/PDF/Raw/Wiki 与附件核对。其独立副本实际执行 v1→v2→v3→v4→v5，最终 `verified=true`、`differences=[]`、`rewritten_interviews=0`。v5 inventory 只有一个 demo legacy typed Offer，canonical 0、真实 Gate 0，保留 `demo_legacy_defer`。

pre-F v5 backup 恢复后由冻结 E runtime 启动，schema/integrity/对象计数可读。F synthetic 写入后的第一次 forward restore 暴露新 Offer 把缺失 `raw_note_id` 序列化为 null，旧 verifier 将其当无效引用；实现改为未提供时省略字段。干净 R2 重新写入、备份、恢复后校验 `checked_rows=235`、`differences=[]`、`reference_issues=[]`、`verified=true`；F runtime 与实际浏览器均成功回读 Offer/terms/revision/purpose/result/ID/附件。证据位于 `/Users/frog/Library/Application Support/Career Migration Audits/batch-f-20260918T062904Z`。

### 20.5 `$workbench-review` 两轴结论

**规格轴：候选功能符合，但批次未通过。** RecordOffer 是唯一 phase 推进动作；0..1 current Offer、用户明确 terms、`offered_role_title` 不复制、谈薪复用 Communication、accepted/rejected/withdrawn、ended View、Accept 零 Employment、legacy 不猜和 Timeline 纯投影均由代码、测试和浏览器实际证明。未进入 Comparison、AI、Raw 上传、Employment/Project 或 Compensation Engine。

**规范轴：发现阻塞 Gate。** 冻结 `0.6.0-batch-e` 能打开含 F 写入的 schema v5。最小复现先由 F 把 Offer 从 revision 0 更新到 revision 1，Opportunity revision 保持 3；随后 E runtime 使用旧 `/end accepted`，请求体没有 `expected_offer_revision`，仍返回 accepted。证据 `v6-gate-frozen-e-stale-accept.json` 为：`offer_revision_in_db=1`、`request_omitted_expected_offer_revision=true`、`status=accepted_without_offer_cas`。

这使旧客户端在不知道当前 Offer 条件 revision 的情况下结束机会，绕过 F 已固定的 Opportunity + Offer 双 revision 写契约。此前 `e-runtime-f-data-compat-r2.json` 中 `accepted_result=accepted` 不能再解释为兼容成功，正是 Gate 的早期信号。仅靠 F runtime adapter 无法约束冻结 E 进程；同 schema v5 继续运行会保留旁路。

按用户明确约束“如果冻结 E runtime 能破坏 F 写契约，停止并升级为 v6 Gate，不得硬做”，review 结论为 **Blocked / 不通过**：需要先制定并实施最小 schema v6 fence/migration，使 E runtime 拒绝 F 数据，再重新验证 v5 rollback、v6 forward recovery、旧程序拒绝、F 浏览器与全量测试。当前 v5 候选不得 Production Cutover，不把本节前半部分的功能证据升级为批次完成。

### 20.6 停止点与未验证项

本轮停止在 schema v6 Gate，不继续修改 schema、创建 migration 或做 Production Cutover。Production 最终仍是 PID 2994、runtime 0.2.0、schema v1；数据库 hash、表计数和附件 hash与实施前一致，没有重启、迁移或业务 POST。

尚未验证：v5→v6 dry-run/apply/verify、冻结 E runtime 对 v6 的明确拒绝、v6 pre-F rollback/forward recovery、最终 F v6 浏览器回归、Production Cutover、真实 AI/AI-Config、Offer 原件上传/分析、Offer Comparison、异机灾备。Opportunity 人工主链的 F 候选功能可运行，但在 v6 fence 完成并重新 review 前不能称为安全闭环，也不具备进入下一实现批次的前置。

## 21. schema v6 fence 实施与定点 review（2026-09-18）

### 21.1 最小实现

在用户确认的 Gate 范围内新增 `offer_migration.py` 与 `scripts/migrate_offer.py`。v5→v6 迁移执行 hash-bound dry-run/apply/verify：写入一条 `migration:offer-v6-fence` manifest，将 `PRAGMA user_version` 从 5 更新为 6。没有新表、索引、trigger 或其它约束，没有改写任何原有 `meta/current/records/applications/revisions` 行，也没有触及 Offer terms 或 legacy 语义。

F `0.7.0-batch-f` 现在对已有数据库只接受 schema v6，新空库也创建为 v6。冻结 E `0.6.0-batch-e` 原有的精确 schema v5 检查使它在 Store 初始化阶段拒绝 v6，早于 HTTP 服务和任何业务写入。此 fence 不支持对未停止的旧进程做热迁移；后续 Production Cutover 仍必须先停止/排空旧 writer，再迁移和启动 F，符合 Architecture 现有升级顺序。

### 21.2 自动验证

- 直接受影响的 schema/migration、Offer Accept/CAS、旧 `/end accepted` adapter 与 backup/recovery：最终 `33 passed in 2.50s`。
- 新的定点回归先将 Offer 从 revision 0 更新为 1，再用 revision 0 调用旧 accepted adapter：HTTP 409；省略 `expected_offer_revision` 返回 422。两次后 Opportunity 均仍为 `active`。
- 最终完整 Python 回归：`152 passed in 8.60s`。
- `npm run build`：TypeScript 与 Vite 成功；只有已知的大 chunk 提示。
- `git diff --check`：通过。v6 不改 UI，本次按用户限定 review 范围没有重复打开浏览器；§20.3 的 Offer Vertical 浏览器验收仍是本批 UI 证据。

### 21.3 最新生产备份的隔离 rehearsal

源备份仍为 `/Users/frog/Library/Application Support/Career Data-backups/career-backup-80cb0ef5-a845-454f-89ba-c287b8cabd91`。它被再次恢复到新系统临时目录，完整执行 v1→v2→v3→v4→v5→v6；本次证据位于 `/Users/frog/Library/Application Support/Career Migration Audits/batch-f-20260918T062904Z/v6-fence`。

v5→v6 前后 `integrity=ok`；`meta/current/applications/revisions` 与除 v6 manifest 外的 `records` 全部行 hash 相同；SQLite schema objects 相同。计数只从 `records=31` 变为 `records=32`，其余为 `meta=1/current=24/applications=1/revisions=146`。`v6-verify.json` 为 `verified=true` 且 `differences=[]`。

版本边界实测：F runtime 对 v5 初始化失败，E runtime 对 v5 正常；迁移后 F runtime 对 v6 正常，冻结 E runtime 对 v6 在 Store 初始化失败，且检查前后逻辑数据不变。在 v6 副本上重放 revision 0→1 后，F 旧 adapter 对 stale revision 返回 409、对缺少 Offer revision 返回 422，冻结 E 则无法启动到业务路由。

rollback 真实恢复 `pre-v6-v5-backup` 到新目录：`verify_restore=true`，E 可读，F 拒绝。forward recovery 将含 Offer revision 1、Opportunity result active 的 v6 数据备份并恢复到新目录：`verify_restore=true`，F 可读，E 拒绝。

### 21.4 定点 `$workbench-review`

**规格轴：通过。** 此修复没有改 Offer 产品对象、terms、phase/result、Timeline、Employment/Project 或 UI。Offer revision CAS 仍是 Accept 的写契约，stale 旧 adapter 已由 409 实测。

**规范轴：通过，原 v6 Gate 关闭。** 迁移只改 schema version 并写 manifest，有源快照 hash 绑定、重放、源变化拒绝、事务故障回滚与独立验证。schema/runtime 互斥、pre-F rollback 和 v6 forward recovery 均有真实恢复证据。review 未发现新的跨版本 Offer/Opportunity 写入口，因此按用户约束没有启动 Subagent。

### 21.5 Production 与停止点

Production 最终仍为 PID 2994、runtime `0.2.0`、schema v1、integrity ok；表计数仍为 `meta=1/current=24/records=27/applications=1/revisions=146`，数据库 sha256 仍为 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`。没有迁移、重启、业务 POST 或 Cutover。

Batch F 隔离交付最终通过。本轮在 F 停止，不进入下一 Batch。Production Cutover、实际部署时的旧 writer 停止/排空、真实 AI/AI-Config、Offer 原件上传/分析、Offer Comparison 与异机灾备仍未执行。

## 22. Opportunity MVP Finalization（2026-09-18）

在完整 Batch F worktree 上完成产品表面收口，没有修改 B–F 领域对象、schema v6、迁移或 Production。主导航只保留“机会”和唯一“简历工作台”作为求职主入口；旧面试/足迹深链接与历史对象继续兼容读取，但不再形成第二条正常用户路线。“今天”改为从 canonical Opportunity 读取当前动作，不再用 JourneyPlan 作为求职状态正本；简历快捷入口先进入文档目录，不自动打开旧全局稿。

Opportunity Workspace 按“现在该做什么 → 岗位情报 → 投递材料 → Timeline”排列。写简历、已投递、面试和 Offer 分别只显示当前阶段主动作。面试首页聚焦当前/下一轮 Real，之前轮次折叠；详情使用“面试准备 / 模拟面试 / 面试记录 / 面试复盘”等用户语言。Simulation 只显示状态与复盘，页面不提供 Raw 或 Patch；Context Pack 不铺开内部 JSON，只能由用户明确复制。没有真实模型时仍可手工完成准备、记录与复盘。Offer 只展示用户明确填写的条件，接受/退出/招聘方结束入口保持各自 Domain Action。

浏览器验收发现并修复两个产品问题：无本机会 ResumeDocument 时，RecordSubmitted 下拉曾展示其它 Opportunity 的版本；现在只展示 owner 等于当前 Opportunity 的版本，跨机会复制仍只能先通过 StartResume 显式创建独立工作稿。ended 回看和旧投递曾显示完整 ISO 时间；现在按 Asia/Shanghai 只显示业务日期。窄视口首次打开默认收起侧栏，390×844 实测主动作和阶段条可完整使用。

### 22.1 自动验证与真实浏览器

- 最终完整 Python 回归：`152 passed in 8.98s`。
- `npm run build` 与 `npm run typecheck` 通过；仅保留既有的大 chunk 提示。`git diff --check` 通过。
- 一个受控 in-app browser tab 在全新 `/tmp` schema v6/TestProvider 数据中完整走通：创建 Opportunity、Greeting、独立 ResumeDocument、普通版本、带 PDF 的冻结投递版本、Communication、无日期 Real、柔性 Preparation、0 份历史复盘创建 Simulation、Simulation 复盘、Real Raw/Final Review、下一轮排期、RecordOffer、谈薪、accepted 与 ended 回看。
- 同一 tab 另行验证无简历投递、rejected、withdrawn、两 Opportunity 工作稿/投递版本隔离、六个管线 View、唯一简历目录不自动选首稿、390×844 响应式。console error/warning 为 0。
- 将最新 v6 rehearsal backup 复制到新的 `/tmp` 目录并启动后，旧 Job、Submission/PDF、typed Communication/Interview/Offer 和历史资料可在新 Workspace 只读访问；未在备份证据目录写入。
- tab 已关闭，两个临时服务均已停止。

### 22.2 风险驱动 `$workbench-review`

**规格轴：通过。** 浏览器主链覆盖从创建机会到 accepted 的人工闭环及无简历、rejected、withdrawn、多轮和隔离分支；页面没有重新暴露 Job/JourneyPlan/ResumeUse/RawSource/PatchProposal/schema 作为正常操作概念。投递材料继续读取冻结 Submission snapshot/PDF；Simulation UI 和既有领域测试均证明零 Patch；Timeline 继续只读投影。

**规范轴：通过。** 本轮业务写入仍只调用既有 scoped Domain Action，没有增加前端组合 phase/result、旧状态双写、Timeline 事实或 Employment 副作用。完整回归继续覆盖 CAS/幂等、owner、投递冻结、Offer accept、legacy adapter 和 schema v6 fence。review 未发现新的高风险写旁路，因此没有启动 Subagent。

### 22.3 Production 与停止点

最终只读核验 Production 仍运行 `0.2.0`，数据目录 `/Users/frog/Library/Application Support/Career Data`，schema v1、integrity ok，SQLite sha256 仍为 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`。没有 Cutover、重启、migration、业务 POST、源码或 dist 覆盖。

尚未完成真实 AI/AI-Config、Offer Comparison、深度 Research、异机灾备和 Production Cutover。现有阻塞不是 Opportunity 人工主链功能，而是上线动作仍需用户显式授权并按既定 v1→v6 停旧 writer、备份、迁移、验证和恢复流程执行。

## 23. Opportunity MVP Production Cutover（2026-09-18）

用户在 Batch F 最终验收通过后单独、显式授权本地 Production Cutover。本节只记录部署与数据证据；没有改变 B–F 产品模型，也没有进入下一批。

### 23.1 部署身份与最终备份

唯一部署来源为 `/Users/frog/Projects/Career-worktrees/batch-f`，分支 `codex/opportunity-f`，HEAD `eafacb8427d80b36c5d569813157a55380c1d4bd`，完整已验收运行源码树 hash 为 `559c13d2135987fff5cc7a468687b4105932ffce691dc66fbddab5d029de9244`。切换前 Production 为 PID `2994`、runtime `0.2.0`、schema v1、数据目录 `/Users/frog/Library/Application Support/Career Data`；`integrity=ok`，计数为 `meta=1/current=24/records=27/applications=1/revisions=146`，SQLite sha256 为 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`，唯一附件 sha256 为 `8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。

最终 `PRE_CUTOVER_BACKUP` 为 `/Users/frog/Library/Application Support/Career Data-backups/pre-cutover-20260918T101916Z`，位于 Production data_dir 外。它实际恢复到独立目录并通过全部 199 行、引用和附件校验：`verified=true`、`differences=[]`、`artifact_count=1`。旧源码另存 `/Users/frog/Library/Application Support/Career Migration Audits/production-cutover-20260918T101916Z/pre-cutover-code.tar.gz`，sha256 为 `d5f73678f7e796e90ab85ecf77e63fc7c658ddf24fa34b08879c9a9c15bd73de`。

### 23.2 迁移与数据切换

旧 writer 停止后确认 PID 退出、8765 端口释放且没有残留 Career writer。迁移 CLI 的既有安全围栏拒绝直接修改正式目录，因此没有放宽或绕过它：从最终备份恢复全新系统临时副本，在其中依次执行 v1→v2→v3→v4→v5→v6；每段均重新 dry-run、核对 source snapshot/Gate、apply、verify。五段 verify 均为 `verified=true`、`differences=[]`：

- v1→v2：0 个旧 Job 自动迁入，2 个保持 `defer_legacy`；
- v2→v3：0 个 Submission 映射，1 个 legacy 保持 null；只新增 nullable canonical 列，六个原列逐字节一致；
- v3→v4：`rewritten_communications=0`；
- v4→v5：`rewritten_interviews=0`；
- v5→v6：`rewritten_business_rows=0`、`added_constraints=[]`。

验证后的 v6 副本先复制到同一文件系统的私有候选目录并逐文件比对，再以目录 rename 切换到原 Production data path。切换前再次确认源 snapshot 未变化。原 v1 目录没有删除，保留于 `/Users/frog/Library/Application Support/Career Data-pre-cutover-v1-20260918T101916Z`，其 snapshot `0850e98b047f8e70b03a5b4ee7dec195956270f26a214fc94dcde109491ceae8` 与切换前完全一致。

### 23.3 完整性与正式运行

正式 v6 snapshot 为 `feb8509c402c390558e920f0711204c8e2a476a82dfa76922e5ee4857a6487d0`；`integrity=ok`、外键无异常。原 24 个 current、1 个 application、27 个 records 和 146 个 revisions 业务行均保留，records 只新增五条 migration manifest。唯一 Submission 的 Resume/Artifact/Job/Opportunity 四组冻结 snapshot hash、version_id、artifact_id、applied_at 均保持；ResumeVersion 存在，PDF 文件与登记 hash 均为 `8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。既有 Communication、Interview、Offer、Wiki、3 个 Candidate、Employment 与 Project 均保留。

2026-09-18 18:27（Asia/Shanghai）用 `--no-browser` 启动正式 runtime。现役 PID `43589`，runtime `0.7.0-batch-f`、schema v6、data_dir 仍为真实 Career Data，8765 只有一个监听 writer。`macos/Career.app` 可执行文件内固定项目根目录为 `/Users/frog/Projects/Career`，且其 sha256 与最终 Batch F worktree 中的 app 可执行文件一致。启动前曾有两次 F runtime 对 v1 的预期只读拒绝，证明 schema fence 生效；正式 v6 进程从启动行起没有 Traceback/ERROR/Exception。

### 23.4 Production browser smoke 与停止点

单一受控 in-app browser tab 实际检查六个 Opportunity View、两个 legacy Opportunity、Opportunity Workspace、冻结 Submission/PDF、Communication、Interview、Offer、纯投影 Timeline、统一 Resume Workspace、Wiki、Employment/Project 与 390×844。legacy phase/date/type/result 保持待核对，没有被自动解释；Resume Workspace 未自动选择文档，历史 PDF 可读；console error/warning 为 0。

本次 browser smoke 全部只读，没有创建测试 Opportunity，也没有业务 POST。smoke 前后 Production snapshot 相同；验收 tab 已关闭，tab 列表为空。没有真实 Migration Gate；只保留两个 demo/legacy 待核对项。当前 Opportunity MVP 已正式可用。

有效 rollback point 是最终 `PRE_CUTOVER_BACKUP`、已验证的 v1 恢复副本、保留的完整 v1 数据目录和旧代码归档。若后续需要 rollback，先停止新 runtime，不在 v6 目录逆迁移；将备份恢复到新的安全目录并用匹配旧 runtime 验证，再决定路径切换。此次没有实际执行 rollback；异机灾备、真实 AI/AI-Config、Offer Comparison、深度 Research 和真实 Production 全写链重放仍未验证。本次到此停止。
