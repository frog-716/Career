# Opportunity Batch D — Communication + Timeline 第一阶段

状态：**隔离实施与两轴验收通过；Production 未 Cutover**。规划与实施日期：2026-09-18。本文先由 `$workbench-plan` 固定验收条件，后按 `$workbench-implement` 实施并以 `$workbench-review` 验收。

## 1. 范围、权威与当前基线

本批只交付一个纵向结果：用户在 canonical Opportunity 已投递后，可以记录已经发生的线上、电话或其他招聘沟通，并在同一 Opportunity Workspace 的 Timeline 中查看 Opportunity 创建、Submission 和 CommunicationEvent。

权威顺序为：本轮用户要求 > [authority](../00-authority.md) > 四份 Opportunity 正本（[Product](../target/opportunity/opportunity-product-model.md)、[Domain](../target/opportunity/opportunity-domain-model.md)、[UI Flow](../target/opportunity/opportunity-ui-flow.md)、[Context & Ingestion](../target/opportunity/context-ingestion.md)）> [Context Contract](../02-context-contract.md) > [Architecture](../03-architecture.md) > [Acceptance](../05-acceptance.md) > [Roadmap](../07-roadmap.md)。[Gap Analysis](../audit/OPPORTUNITY-GAP-ANALYSIS.md) 和 AS-IS 审计提供历史差异与迁移证据，不把旧目标描述成当前能力。

实施基线是 `/Users/frog/Projects/Career-worktrees/batch-c` 的完整 Batch C 工作树，而不是只取其 HEAD。Batch C 已记录为 `0.4.0-batch-c` / schema v3，120 项自动测试和隔离浏览器核心验收通过；最新生产备份的 v1→v2→v3、旧程序拒绝、pre-C rollback 和 v3 forward recovery 已在隔离目录验证。上述是 [Batch C §17](OPPORTUNITY-BATCH-C.md#17-实施与两轴验收记录2026-09-1718) 的既有证据，本轮规划没有重新查询在线生产进程。

Batch C 记录的 Production 仍为 `/Users/frog/Library/Application Support/Career Data`、`0.2.0`、schema v1，PID 2994；这些值在 D 实施开始前必须从实际服务、SQLite、附件目录和源码/dist 重新核对，不能直接当作届时在线事实。D 继续只在独立 worktree、临时虚构数据和届时最新生产备份的隔离恢复副本实施及验收，不执行 Production Cutover。

## 2. 用户可观察闭环与明确非目标

主路径固定为：

```text
canonical Opportunity(result=active, phase=submitted)
  → 添加线上沟通 / 记录电话沟通 / 添加其他沟通
  → 用户确认 occurred_on + content
  → CreateCommunication
  → CommunicationEvent
  → Opportunity Timeline 出现同一对象的投影
  → 打开 Communication Detail
  → 更正当前内容或删除误建记录
```

用户可以从旧 Job URL 进入同一个 canonical Opportunity，但所有新沟通先解析为 canonical `opportunity_id` 后再写入；别名不能形成第二份记录空间。

本批完成后只可宣称 **Communication + Timeline 第一阶段**。不实现或暗示已经实现：InterviewSession / ConfirmRealInterview、Offer、Research 重构、RawSource、PatchProposal、AI 提炼、自动面试识别、ModelGateway、AI-Config、完整 Timeline、Employment / Project 改造。文本出现“一面”“Offer”或“拒绝”等词也只保存为沟通文本。

## 3. CommunicationEvent Domain 模型

不新增业务表。继续以现有 `records.kind='communication'` 和原 typed Communication ID 作为对象身份；新写入采用明确的 current body：

| 字段 | 规则 |
| --- | --- |
| `id` | 创建时生成，永久稳定；Timeline 与 Detail 都使用此 ID |
| `communication_format` | 新形态固定为 `2`，用于和 legacy body 确定性区分 |
| `opportunity_id` | canonical Opportunity ID；保存前解析旧 Job/canonical 别名 |
| `type` | 仅 `text`、`phone`、`other` |
| `occurred_on` | 用户确认的 `YYYY-MM-DD` 业务日期；UI 默认本地今天但服务端不替缺值猜今天 |
| `content` | 用户确认的沟通正文；必填、保留换行，限制沿用本地文本上限 |
| `created_at` | 服务端 UTC 创建时间，不随更正变化 |
| `updated_at` | 服务端 UTC 最近更正时间；创建时等于 `created_at` |
| `revision` | 从 0 开始；每次成功 Update/Archive 加 1，作为 CAS |
| `archived` / `archived_at` | 新建为 `false` / `null`；用户“删除”时以 CAS 设为 `true` / 服务端 UTC 时间，默认查询、Detail 与 Timeline 均过滤 |

`channel`、`participants`、`outcome`、`raw_note_id` 等 legacy 字段不机械删除。旧记录仍按原 body 保存和读取；用户显式更正 legacy typed Communication 时，在**同一 ID、同一 record**中补齐 format 2 的 current 字段，同时保留原字段作来源追溯，不更新或删除其 JourneyNote。

CommunicationEvent 只表达一次已发生的现实沟通。它没有 phase/result 写权限，不拥有 Company/role，不承载 AI 分析、Research 事实或未来 Interview 的确认状态。未来对象可以引用 `communication_id`；本批不预建引用表或万能 source 平台。

## 4. typed Communication 复用与 legacy 分类

当前代码已验证存在：

- `engagement.py` 在 `records.kind='communication'` 创建 typed body，并同时创建 `journey_note`；字段包括 `opportunity_id`、`occurred_at`、`channel`、`participants`、`raw_note_id`、`outcome`、`created_at`。
- `/api/opportunity-activity` 合并 typed rows 和没有 typed 对象的 JourneyNote projection。
- `/api/journey/notes` 的 Job/communication 分支会调用 `create_activity`，因此当前至少有两个可触达的 legacy 写入口。
- canonical Opportunity Workspace 当前只读取 JourneyNote，尚未读取 typed Communication，也没有统一 Timeline。

D 的兼容读按以下类别处理：

| 现有数据 | D 读取方式 | 是否进入 Timeline | 写策略 |
| --- | --- | --- | --- |
| format 2 typed Communication | 直接读 current body | 是，按同一 ID 一条 | 新 Domain Actions |
| legacy typed + 有效 `raw_note_id` | 内容读取 JourneyNote 当前更正，原 typed ID 保持 | 是；`type` 无法确定时显示“历史沟通 · 类型待核对” | 用户显式 Update 后同 ID 升为 format 2；不改 Note |
| legacy typed + 缺失/错误 Note | 显示可验证字段并标“原文缺失/待核对” | 有日期则进入；未知日期进入“日期待核对”组，不补今天 | 只有用户补齐 type/date/content 后才能变为 format 2 |
| 只有 JourneyNote、没有 typed Communication | 继续在 legacy 资料/足迹入口只读 | 否 | 不自动转换 |
| 多个 typed rows 指向同一 Note 或关联冲突 | inventory 明确列出，不能自动选主对象 | 暂不进入统一 Timeline 的歧义组 | 真实用户数据按 Gate；demo/legacy 只记录 defer |

`channel` 不自动映射成 `type`；即使旧值看似“电话/邮件”，也不通过字符串猜测。`occurred_at` 仅在能严格解析出日期时投影为 `occurred_on`，否则保持 Unknown。旧 Note 不因 typed Communication 被更正或删除而删除；Timeline 也不会把失去 typed 对象的 Note 重新投影成 CommunicationEvent。

legacy typed DTO 的初始 `revision` 视为 0；第一次显式 Update/Delete 必须提交 `expected_revision=0`。成功 Update 后进入 format 2 并按正常规则递增，不从 JourneyNote 的更正 revision 猜 Communication revision。

## 5. Domain Actions 与 HTTP Interface

公共 Interface 在编码前固定为：

| Domain Action | HTTP | 输入 | 关键前置与结果 |
| --- | --- | --- | --- |
| `CreateCommunication` | `POST /api/opportunities/{opportunity_id}/communications` | `type`, `occurred_on`, `content`, `idempotency_key` | canonical、可写、`result=active`、`phase=submitted`；返回 revision 0 |
| `GetCommunication` | `GET /api/opportunities/{opportunity_id}/communications/{communication_id}` | 路径 ID | 所属机会匹配；返回 current/legacy DTO |
| `ListCommunications` | `GET /api/opportunities/{opportunity_id}/communications` | 无 | canonical scope 内的 typed Communication；不夹入 note-only projection |
| `UpdateCommunication` | `PUT /api/opportunities/{opportunity_id}/communications/{communication_id}` | 完整 `type`, `occurred_on`, `content`, `expected_revision`, `idempotency_key` | 同一 ID 原位更正、revision +1；允许 active 或 ended 的历史修正 |
| `ArchiveCommunication`（UI 显示“删除”） | `POST /api/opportunities/{opportunity_id}/communications/{communication_id}/delete` | `expected_revision`, `idempotency_key` | 原对象设为 archived；默认不可见，不删 Note/Raw/任何其它对象 |
| `GetOpportunityTimeline` | `GET /api/opportunities/{opportunity_id}/timeline` | 无 | 只读派生 projection |

统一错误语义：不存在或跨机会访问为 404；字段/日期/type 不合法为 422；legacy Opportunity 未核对、已结束/非 submitted 时新增、CAS 冲突、幂等键异体复用和歧义 legacy 更正为 409。错误内容应明确用户下一步，不能返回内部 SQL 或路径。

Create 严格使用 `active()` 后再检查 `phase == 'submitted'`。Update/Delete 使用 `writable()` 和对象 owner 校验，不要求 Opportunity 仍 active，因此 ended 历史可修正/删除；它们绝不能调用 `EndOpportunity`、阶段推进或 reactivation。read-only/deferred legacy Opportunity 仍不可写。

## 6. CAS、幂等与事务边界

Create/Update/Archive 都在单个 `BEGIN IMMEDIATE` 事务中完成 owner、phase/result、revision、幂等指纹和对象写入检查。计划复用现有 request-record 思路，但以 action + canonical opportunity ID + communication ID + payload 形成指纹；同键同体返回首次结果，同键异体返回 409。

- 两次 Create 使用同一 idempotency key：只产生一条 CommunicationEvent。
- 两个不同 key 的并发 Create：代表两次明确用户动作，允许各自产生对象；UI 双击必须复用同一个 key。
- Update 必须提交完整 current 字段和 `expected_revision`；旧 revision 失败且保留用户输入，不做 last-write-wins。
- Archive 也要求 current revision。成功后的相同 key 重放返回首次归档结果；不同 key 再删按默认查询返回 404。
- Update 在同一 `records` row 原位替换 current body，不新增 Timeline 项，也不为 MVP 建复杂内容历史。

幂等记录不能把完整沟通正文复制成另一个业务正本。保存的 command result 只保留重放所需的稳定结果/指纹；若现有 `engagement_request` 会复制完整 result，则实现时应收窄为不含正文的 `communication_request` 或等价 metadata，而不是继续复制敏感正文。

## 7. Opportunity 与其它领域的硬边界

Create/Update/Archive 的事务后逐项断言以下对象没有变化：

- Opportunity `phase`、`phase_changed_on`、`result`、`result_changed_at`、`revision`；
- Submission、ResumeDocument、ResumeVersion、Greeting/PDF/hash；
- Interview、Offer、ResearchSnapshot；
- JourneyPlan、Job status；
- Raw/Wiki/Candidate、Profile；
- Employment、Project 及任职 JourneyNote。

“HR 说周五一面”只保存正文。下一批 `ConfirmRealInterview` 才能创建真实 InterviewSession 并将 phase 推进到 interview。本批不分析关键词、不解析安排、不生成 Patch，也不让前端组合多个 API 模拟状态推进。

## 8. 旧写入口收敛

schema v4 运行时内只允许上述 scoped Domain Actions 创建/修改/删除 CommunicationEvent：

- `POST /api/opportunity-activity/communication` 保留明确兼容错误，返回 409 `communication_action_required` 并指向 scoped action；其 GET 继续只读。
- `POST /api/journey/notes` 对 `scope_type=job, kind=communication` 返回同一兼容错误；`scope_type=episode` 的任职记录保持原行为。
- 被 typed Communication 引用的 Job JourneyNote 不再允许通过旧 correction 入口改变“当前沟通正文”；返回 409 并指向 Communication Detail。Note history、原文读取和 Candidate 相关非 D 能力保持现状。
- 旧 Opportunity/Job URL 可导航到 canonical Workspace；新 API 在服务端解析 alias 后写 canonical ID。没有 canonical 映射的 legacy Job 只读，不临时创建 Opportunity。
- 前端移除 canonical Workspace 对旧 `journey.notes` 作为沟通正本的依赖；legacy 资料可在原只读入口查看，但不与 Timeline 混成第二条记录。

Research/interview/offer 的既有暂停和读路径不因本批放开。不得借收敛 Communication 写入口重构整个 `engagement.py` 或 `journey.py`。

## 9. Timeline Projection 设计

不建 `TimelineEvent` 表、不写 timeline records、不引入 Event Bus。Timeline service 在一次只读事务中读取真实源对象并返回可扩展 tagged union：

```json
{
  "items": [
    {
      "source_type": "communication",
      "object_id": "...",
      "occurred_on": "2026-09-18",
      "title": "电话沟通",
      "summary": "确认后续会安排业务面",
      "status": null,
      "target": {"kind": "communication", "id": "..."}
    }
  ],
  "unknown_date_items": []
}
```

第一阶段 source adapter 只有：

| `source_type` | 正本与日期 | 摘要/状态 | 点击目标 |
| --- | --- | --- | --- |
| `opportunity_created` | Opportunity `created_on` | “加入 Career”；无伪状态 | Workspace 顶部 |
| `submission` | canonical Submission `submitted_on` | “完成投递” + 实际材料摘要 | 已有 Submission/投递材料锚点，能查看 frozen version/Greeting/PDF |
| `communication` | typed Communication `occurred_on` | type 标签 + 当前正文的确定性短摘要 | Communication Detail |

摘要在查询时由当前正文折叠空白并截取固定长度，不另存；Update 后同一 Timeline item 自动显示新摘要，Delete 后消失。Submission 只在有明确 canonical association 时进入，不能仅因公司/日期相似而猜关联。legacy typed Communication 使用同一 typed ID；note-only projection 不进入。

排序为 `occurred_on DESC`，同日再按可验证的 source timestamp、固定 source rank、object ID 排序，保证响应稳定。同日只有日期而没有时刻时，UI 不把稳定排序描述成真实先后。无法确定日期的 legacy typed rows 放在独立 `unknown_date_items`，不赋当前日期，也不静默丢失。

后续 Interview/Offer/result 只需增加 source adapter 和新 `source_type`，不改变已有三个对象、排序协议或目标导航；本批不预建通用插件系统。

## 10. Communication Detail 与删除策略

Detail 是 Opportunity Workspace 内的轻量面板/路由状态，显示 type、occurred_on、current content、legacy 待核对提示和 revision。编辑复用同一表单；CAS 409 时保留用户输入，同时展示服务器最新值，由用户明确重试。

实施前删除策略复审决定采用**对象内最小 archive**。理由是现有 Communication 已存于 JSON `records.body`，增加 `archived/archived_at` 与一次 CAS 更新不需要新表、通用框架或级联逻辑；相比物理删除，它保留稳定 ID、当前正文和 legacy provenance，未来 Interview/Research/Patch 可显式引用而不悬空。物理删除虽然少两个字段，但会让未来来源引用必须另做 tombstone 或禁止删除，长期并不更小。

用户界面仍显示“删除”：确认后该对象从列表、Detail 默认读取和 Timeline 消失。底层 typed record 保留；只有明确的内部 `include_archived` 读取边界可供完整性验证或未来来源解析，本批不暴露回收站、恢复 UI、删除审计页或通用软删除 API。archive 不改 JourneyNote、Raw、Research、Interview、Offer 或 Opportunity；legacy typed archive 后原 JourneyNote 仍在 legacy 资料入口只读，Timeline 不会把它重新生成为 CommunicationEvent。

本批现有 schema 没有已验证的 Interview/Patch/Research → Communication 正式引用，因此不预建引用扫描器。未来正式增加引用时，引用方通过稳定 communication ID 显式读取 archived source，并自行决定是否展示“来源已删除”；这就是本批固定的升级边界。

## 11. Opportunity Workspace UI

`phase=submitted && result=active` 的当前阶段区域显示“招聘沟通”：

- `添加线上沟通` 预填 `type=text`；
- `记录电话沟通` 预填 `type=phone`；
- `添加其他沟通` 预填 `type=other`；
- 表单只要求日期和内容，日期默认浏览器本地今天但可改；不要求公司、岗位、渠道、联系人、HR、备注或标签；
- 可轻量显示最近一次 typed Communication，并进入其 Detail。

Workspace 下方始终显示统一 Timeline，包括 active 与 ended Opportunity。ended 页面隐藏新增按钮并说明“机会已结束，历史仍可查看和更正”；Detail 的编辑/删除保留，不出现重新激活入口。

不新建长期“沟通与面试”资料板块。原“已有资料记录”若仍承载 research/note-only 历史，只能明确标为 legacy/历史资料并与 Timeline 分开；Communication 不重复显示。Timeline 的 Submission 点击必须打开实际冻结材料而非空壳详情。

## 12. schema v4 与迁移策略

本批需要 schema v4，原因是**写契约不向后兼容**，不是按批次机械加一：schema v3 的 Batch C 运行时仍可通过 `/api/opportunity-activity/communication` 或 Job JourneyNote 创建 legacy `typed + note` 双写，并且不知道 D 的 Update/Delete CAS、ended 规则和 Timeline 投影。若 v3 程序可以打开 D 已写入的库，rollback 会重新引入两个可写正本，无法满足旧程序拒绝和 forward recovery。

v3→v4 migration 保持最小：

1. 只读 dry-run/inventory 分类 format 2、legacy typed+note、typed 缺 note、note-only、raw-note 多重引用、opportunity owner/alias 冲突、日期/type Unknown、Submission Timeline 关联候选；不创建 Store、不执行 DDL、不回写默认值。
2. apply 绑定 source snapshot hash，在 `BEGIN IMMEDIATE` 内记录 D migration manifest，最后将 `PRAGMA user_version` 从 3 设为 4；**不批量重写任何 Communication/JourneyNote，不生成 Timeline 数据**。
3. schema v4 runtime 只接受 v4；冻结 C/v3 runtime 必须在初始化前拒绝 v4，D runtime 也拒绝 v1/v2/v3 并提示显式迁移。
4. verify 比较迁移前后所有既有 current/records/revisions/applications 行 ID 与 body hash；允许的新增只有 D migration manifest 和 schema version，附件集合/hash与 Raw/Wiki/Candidate、Submission、ResumeDocument、Employment/Project 必须相同。

不为 schema 版本新增业务表或把 legacy 行伪装成已确认数据。迁移工具延续 B/C 的路径保护：只接受系统临时目录中的普通独立数据库，拒绝生产目录、代码目录、符号/硬链接、覆盖和唯一备份。

## 13. 真实备份副本 rehearsal、rollback 与 forward recovery

实施时严格按序：

1. 重新确认实际生产数据目录、SQLite、附件目录、服务 PID/版本/schema、源码与 dist；记录只读基线。
2. 使用现有 backup 创建**届时最新**真实生产备份，恢复到不存在的新隔离目录；先验证 v1 integrity、对象计数、关键 ID、Submission/ResumeVersion/PDF/hash 和资料引用。
3. 在隔离副本重新运行已验收的 v1→v2→v3 链；每段使用当时 source hash，不复用过期 plan，不自动迁 legacy Opportunity/Company/phase/result。
4. 在 v3 副本运行 D dry-run，人工检查分类和 Gates；另建 pre-D v3 backup，再 apply v3→v4 并 verify。真实副本只用于保全与兼容读取，不在其中补造用户沟通。
5. 用冻结 C/v3 runtime 尝试打开 v4，必须在任何初始化/写入前拒绝且 hash 不变；D/v4 runtime 尝试打开 pre-D v3 同样拒绝。
6. **开写前 rollback**：从 pre-D backup 恢复到另一个新目录，用匹配 C/v3 runtime 实际启动和读回；不把 v4 整数直接改回 3。
7. 在真实副本的再次复制分支或纯虚构目录中创建明确标识的 synthetic canonical Opportunity/Submission/Communication，验证 D 行为；不得把 synthetic 行写进原恢复副本或称为生产资料迁入。
8. **开写后 forward recovery**：备份已包含 D Communication 的 v4 数据，恢复到新的隔离目录，用匹配 D/v4 runtime 读回；核对 ID/revision/content、Timeline、Submission frozen material、PDF bytes/hash 和同键重放。不得用 pre-D v3 backup 覆盖这些新增事实。

manifest 至少记录代码/工作树 hash、输入备份与所有隔离路径、前后 schema/snapshot hash、全表计数、Communication 分类和 Unknown、owner/alias/Note 引用、全部旧行与附件保护 hash、迁移重放/故障结果、旧程序拒绝、rollback/forward recovery 及生产前后只读核对。用户正文只留在权限受限的私有证据目录，不复制进仓库文档。

## 14. 计划修改范围与顺序

实施必须新建独立 D worktree/branch，并先保存完整 C 工作树来源与 hash。允许范围预先固定为：

| 顺序 | 允许模块 | 完成界线 |
| --- | --- | --- |
| D1 基线/测试触发 | 本文、STATUS、Roadmap；D 测试 fixture | 重新核对 C 完整基线与生产只读状态，先固定 API/错误/不变量 |
| D2 Communication deep module | 新 `src/workbench/communication.py` 或在实际边界更窄时扩展 `engagement.py`；`app.py` | 复用 `kind=communication` 身份，完成 Create/List/Get/Update/Archive、CAS/幂等/owner；不造新表 |
| D3 legacy 写门禁 | `engagement.py`、`journey.py` 的 Job/communication 局部分支 | 旧读保留，两个旧写入口不能绕过 Domain Action；episode/Employment 不变 |
| D4 Timeline projection | 新 `src/workbench/timeline.py`、`app.py` | 三种源 adapter、稳定排序/Unknown、对象导航；无持久 Timeline |
| D5 schema/迁移 | `core.py` diagnostics/版本；新窄职责 D migration + CLI；`migration_baseline.py`、`backup.py` 仅在直接需要时 | v3→v4 semantic fence、dry-run/apply/verify、旧程序拒绝和恢复；不改旧业务行 |
| D6 canonical UI | `frontend/src/opportunity-ui.ts`、`main.ts` 的数据加载/事件、现有 CSS；必要的类型 | submitted actions、表单、Detail、Timeline、ended 历史；不重写全局 workspace |
| D7 文档与验收 | `src/workbench/README.md`、本文实施记录、STATUS | 只写真实命令/结果和未验证项；两轴 review 后停止 |

默认不改 `opportunity.py`、Submission/ResumeDocument/Artifact、Context Compiler、Provider、Employment/Project、AI 配置；只有实现发现 D 公共接口无法在现有边界成立时，先记录具体原因并限于必要行。四份 target、Gap Analysis、AS-IS、AGENTS 和既有批次记录不因实施验证结果改写。

## 15. 编码前固定的自动测试

以下条件在编码前固定；计划形成时尚未运行，实施结果见 §20。测试仅使用 tmp/虚构数据和 TestProvider：

| 编号 | 固定断言 |
| --- | --- |
| T01 创建 | submitted/active 创建 text/phone/other；服务端 owner 为 canonical ID；日期/content 校验；持久化重启可读 |
| T02 状态隔离 | 正文含“面试/Offer/拒绝”仍不改变 Opportunity 任一 lifecycle 字段，不创建 Interview/Offer/Research/Note |
| T03 scope | 两 Opportunity 通信完全隔离；跨 owner ID 404；旧 Job alias 与 canonical URL 指向同一集合且不重复 |
| T04 phase/result | resume/interview/offer phase 创建拒绝；ended 创建拒绝；ended 历史 Update/Archive 允许且不 reactivation；read-only legacy 拒绝 |
| T05 CAS | stale Update/Archive 409；current revision 成功递增；冲突后原输入可重试；Update 后 Timeline 仍一条同 ID |
| T06 幂等/并发 | Create/Update/Archive 同键同体重放、同键异体冲突；真实并发双击同 key 只一条；Create 与 EndOpportunity 竞争只有符合锁内前置的一种结果 |
| T07 删除 | UI删除后 list/detail/Timeline 默认消失；底层同 ID archived body 可供内部完整性读取；Opportunity 和其它对象不变；legacy Note/Raw 不删除、不自动回投 Timeline；无恢复UI/通用软删除平台 |
| T08 legacy read | typed+note 复用 typed ID/current corrected content；type/date Unknown 不猜；用户显式补齐后同 ID format 2；note-only 不进 Timeline；多 typed/Note 歧义进入 inventory |
| T09 legacy writes | 旧 activity POST、Job communication note POST、typed Note correction 不能绕过；旧 GET/history 可读；episode/Employment note 创建与更正保持 |
| T10 Timeline | Opportunity created + Submission + Communication 聚合、倒序与同日稳定；摘要随当前值变化；无 timeline record；unknown date 独立返回；Submission 导航到冻结材料 |
| T11 migration | v3 normal/空库/all-legacy/歧义 fixture dry-run；source hash 变化、重复 apply/异体、事务故障；只新增 manifest/version，旧行与附件 hash 相同 |
| T12 version/recovery | v3 runtime 拒绝 v4、v4 runtime 拒绝 v3且源 hash 不变；pre-D rollback 和开写后 v4 forward backup/restore；同键重放保全 |
| T13 非本期回归 | Batch C Resume/Greeting/Submission/PDF 核心测试、B Opportunity lifecycle/CAS、现有 engagement read、Employment/Project 与 Context 隔离通过；Interview/Offer 写门禁仍在 |
| T14 安全/HTTP | 跨机会访问、非法日期/type、超长正文、缺 key/revision 的 404/409/422 一致；响应不泄露本地路径/SQL；无真实 Provider 调用 |

测试承载预计新增 `tests/test_communication.py`、`tests/test_timeline.py`、`tests/test_communication_migration.py`，并局部更新 `test_engagement.py`、`test_journey.py`、`test_opportunity.py`、`test_backup.py` 和旧 schema fixture。先跑 D 定向测试；整合后因 Store/schema/router/主 Workspace 均受影响，运行一次完整 `.venv/bin/python -m pytest -q`，再执行一次 `npm --prefix frontend run build`（含 tsc）。有新失败才定向复验，不重复全量凑证据。

## 16. 浏览器验收条件

使用独立虚构数据目录和非生产端口，实际浏览器逐项验证：

| 编号 | 可观察验收 |
| --- | --- |
| U01 | 从已投递 Opportunity 看到三个沟通入口；线上/电话默认 type 正确，日期默认今天且可改，表单不要求渠道/联系人 |
| U02 | 记录“HR 说周五业务一面”，保存后仍为 submitted，页面没有 Interview 对象或“已确认面试”暗示 |
| U03 | Timeline 同时显示加入 Career、完成投递和沟通；排序/摘要正确，Submission 能打开 frozen Resume/Greeting/PDF，Communication 打开真实 Detail |
| U04 | 编辑错字与日期后原 Timeline 项就地更新、无第二条；另一窗口 stale revision 得到可理解冲突并保留输入 |
| U05 | 删除误建 Communication 后 Detail/Timeline 项消失，机会阶段/结果/Submission 不变；legacy Note 若存在仍从历史入口可读 |
| U06 | 两个 Opportunity 分别创建沟通不串联；从旧 Job URL 和 canonical URL 查看同一对象，没有重复 |
| U07 | ended Opportunity 历史与 Timeline 可读、可更正；正常新增按钮不存在且直接请求也拒绝，不出现重新激活 |
| U08 | legacy typed Communication 可查看；未知 type/date 明示待核对，用户显式补齐后仍是同一 ID；note-only 不冒充 Timeline 沟通 |
| U09 | 停止并重启隔离服务后 current content/revision/Timeline 保持；v4 forward 恢复副本走相同页面可读 |
| U10 | Resume Workspace、投递材料和一个虚构 Employment/Project 主路径冒烟通过；页面仍明确 Interview/Offer/Research/AI 未接管 |

最新生产备份恢复副本只验迁移保全、legacy 读取和 runtime 兼容；若没有可写 canonical submitted Opportunity，不用 demo 替代真实用户业务验收。U01–U10 的写入在纯虚构或明确 synthetic 分支完成。

## 17. Gates 与 Unknown

规划时没有新增已确认的用户产品 Gate。下列只有在实施 inventory 发现**真实用户数据**且无法安全保留/投影时才升级为 Gate：

- 多个 typed Communication 指向同一 raw Note，无法判断是一件沟通还是多件；
- typed Communication 的 owner 同时指向互相冲突的 canonical Opportunity/legacy Job；
- 真实 typed Communication 缺失正文且没有任何可读来源，用户又需要它进入 Timeline；
- 同一 Submission 对多个 canonical Opportunity 有冲突关联，导致 Timeline 不能确定归属；
- 数据完整性、附件或迁移 source hash 在 apply 前变化。

demo/case/legacy 歧义只标 `demo_legacy_defer`，不自动替用户做 Migration Gate 决策，也不阻塞新虚构闭环。日期/type 不可推导默认保持 Unknown；用户可以在 Detail 显式核对，而不是迁移时猜测。普通工程选择（module 文件名、摘要长度、UI 面板形式、schema v4 fence）不是用户 Gate。

规划时待验证：实施当时的生产 PID/version/schema/hash 与最新备份；真实数据中上述 legacy 分类计数；C 完整工作树能否无遗漏复制到 D worktree；所有预定自动测试、浏览器路径、v3→v4 rehearsal、rollback/forward recovery。结果见 §20。真实 AI、外部平台送达、异机灾备、无损 v4→v3 逆迁移不属于 D 验收。

## 18. 反向审查结论

| 攻击问题 | 计划控制 |
| --- | --- |
| 1. 创建沟通偷偷改 phase/result | Communication 事务无 lifecycle 写权限；T02/T04 比较完整 before/after body |
| 2. 文本出现面试自动建 Interview | 无解析器/Skill/关键词分支；明确对象计数断言 |
| 3. Timeline 复制第二份事实 | 纯查询 adapter；迁移/测试断言不存在 timeline kind/table |
| 4. Update 后出现两条 | 同 ID 原位 CAS 更新，projection key 为 source_type + object_id |
| 5. Delete 误删 Note/Raw/其它对象 | 只在 typed body 设 archived；行/hash保护测试；note-only 不回投 Timeline |
| 6. 两 Opportunity 串沟通 | API owner 路径 + canonical owner 校验 + 跨 owner 404 |
| 7. Job/canonical ID 生成两份 | 写前统一 resolve canonical ID，并将其纳入指纹 |
| 8. 双击重复 | UI 复用 idempotency key，服务端事务内指纹回放；并发测试 |
| 9. ended 偷偷新增 | Create 在锁内检查 active + submitted；Update/Delete 只更正已有对象 |
| 10. legacy Note 被当 typed | Timeline 只读 `kind=communication`；note-only 留 legacy 入口 |
| 11. 提前建 Raw/Patch/Research | format 2 直接存用户确认文本；范围/文件/测试均禁止相关写入 |
| 12. 侵入 Interview/Offer | 原写门禁保留，Timeline source adapter 本批不含二者 |
| 13. 影响 Employment/Project | Job communication 门禁按 scope 精确判断；episode 路径与回归测试保护 |
| 14. 后续 source 需要推倒 Timeline | tagged union + source adapters；追加类型不改前三种事实或导航协议 |

额外反查：若不设 schema v4 fence，冻结 C/v3 程序能重新开放 legacy 双写，构成回滚后的旁路；因此本计划明确升级。若 migration 实现开始批量补 content/type/date、创建 Timeline row 或改 Note，即偏离计划，应停止而不是以“兼容”名义继续。

## 19. 实施完成后的 review 与停止点

本次已使用 `$workbench-implement`，并使用 `$workbench-review` 分别检查需求符合度与工程规范。review 核对：单一 Communication 写正本、archive 默认不可见且底层可引用、状态隔离、legacy 不猜、无 Timeline 持久化、schema fence/恢复证据、浏览器真实路径、Production 未变和非本期文件范围；结论见 §20.7。

Batch D 的停止点是：Communication + Timeline 第一阶段在临时虚构数据和最新生产备份隔离副本通过上述验收，证据写回本文实施记录并由 STATUS 链接。到此停止；不进入 Interview Core，不实现 Research/Raw/Patch/AI，不执行 Production Cutover，不修改 Employment / Project 或 `.codex/config.toml`。

当前计划不授权部署。Production Career Data 保持 v1，直到未来单独、显式的 Production Cutover 授权。

## 20. 实施与两轴验收记录（2026-09-18）

### 20.1 交付位置与删除策略结论

实现位于独立工作树 `/Users/frog/Projects/Career-worktrees/batch-d`、分支 `codex/opportunity-d`，基于 Batch C 完整工作树复制，而不是从其未包含实现的 Git HEAD 重建。运行身份为 `0.5.0-batch-d` / schema v4；没有复制业务代码或构建产物到 Production 源码目录。

实施前复审后采用**对象内最小 archive**：现有 Communication 已以 JSON 存在 `records.body`，增加 `archived/archived_at` 和一次 CAS 更新即可保留稳定 ID、正文与 legacy provenance，也避免未来 Interview/Research/Patch 显式引用悬空。UI 仍称“删除”；默认 List、Detail 与 Timeline 不返回 archived。没有回收站、恢复 UI、通用软删除框架或删除审计平台。当前没有已验证的正式下游引用，因此本批不建引用扫描器；未来出现正式引用时，引用方必须以稳定 `communication_id` 显式读取 archived source，并自行显示来源已删除状态。

### 20.2 实际实现

- 新增 `communication.py`：复用 `records.kind=communication` 和原 typed ID，完成 scoped Create/List/Get/Update/Archive、canonical owner、CAS、幂等和 ended 历史更正；命令记录只保存 ID/revision/archive metadata，不复制沟通正文。
- 新增 `timeline.py`：只读投影 Opportunity 创建、明确 canonical Submission 与未归档 typed Communication；未知日期单列，摘要查询时生成，不存在 Timeline 表或 record。
- 旧 `/api/opportunity-activity/communication`、Job scope Communication JourneyNote 新建和已被 typed Communication 引用的 Note correction 均返回 `communication_action_required`；旧 GET/history 与 Employment scope 保持。
- schema v4 作为写契约 fence；新增 `migrate_communication.py` 与 migration module，只登记 hash-bound manifest/version，不重写 Communication、JourneyNote、Submission、Resume、Raw/Wiki、Employment/Project 或附件。
- Opportunity Workspace 接入三个沟通入口、当前记录、Detail、CAS 冲突比较、产品“删除”和 Timeline；ended 隐藏新增但保留历史查看/更正。旧 Job 深链和 canonical URL 读取同一 scoped 数据。
- 备份在 schema v4 继续运行 Resume artifact recovery/integrity 检查。服务 README、前端 README、Roadmap 与 STATUS 更新唯一所属信息；四份 Opportunity target、Acceptance、Architecture、Context Contract、Gap/AS-IS 均未改写。

### 20.3 自动验证

编码前 Batch C 基线为 `120 passed`。最终完整回归命令 `./.venv/bin/python -m pytest -q` 为 **129 passed in 69.91s**；review 后调整幂等重放顺序，再运行 D/迁移/legacy/backup 定向集合为 **18 passed in 4.83s**。最终 `npm --prefix frontend run build` 通过 TypeScript 与 Vite 构建；只有既有 editor chunk size 警告。`git diff --check` 通过。

覆盖结果包括：三种 type、非法日期/正文、Opportunity scope、CAS/并发、同键重放、ended、archive、状态零联动、legacy typed+Note、note-only、旧写旁路、Timeline 无事实表、v3→v4 source hash/事务故障/重放、schema fence、Batch C Resume/Submission/PDF、Employment/Project 与 Context 回归。

### 20.4 实际浏览器验收

在 TestProvider、临时 schema v4 数据目录和非生产端口完成 U01–U10：

- 已投递 Opportunity 显示三个入口；记录含“一面”的电话沟通后仍为 submitted，Timeline 同时显示创建、Submission、Communication，未创建 Interview。
- 同一 Communication 编辑后原 Timeline 项就地更新；后台制造第二窗口 revision 后，浏览器显示服务器当前内容并完整保留未提交输入。
- UI 删除后 List/Detail/Timeline 消失，SQLite 同 ID 保留 `archived=true`、`archived_at` 和更正后的正文；Submission 与 phase/result 不变。
- 两个 Opportunity 分别显示自己的沟通；旧 `#jobs/{id}` 深链与 canonical URL 均加载同一 Communication/Timeline。验收中发现首次深链未加载 scoped 数据，已修正启动时路由解析顺序并复验。
- ended Opportunity 不显示新增入口，Timeline 与历史沟通仍可见并可更正，结果仍为 ended，没有 reactivation。
- 最新生产备份迁移副本中的 legacy typed Communication 显示“类型待核对”，日期可核对，Detail 可读；只读 legacy Opportunity 不显示编辑/删除。另在纯虚构 canonical Opportunity 中实际浏览器验证：未知 type/date 不猜，用户明确补齐后仍为原 typed ID、format 2；原 JourneyNote 不变，note-only 只留在 Legacy 区且不进入 Timeline。验收中发现 Detail 曾被后端 writable guard 误拦，已拆分 read/write owner guard 并补回归。
- v4 forward 恢复目录通过浏览器读回 synthetic Opportunity、Submission、Communication 与三源 Timeline。统一 Resume Workspace、冻结投递材料及 demo Employment/Project 页面完成冒烟；界面仍明确真实 Interview/Offer/Research/AI 未接管。

### 20.5 最新生产备份副本 rehearsal

实施开始与结束均只读核对真实服务：PID `2994`，运行版本 `0.2.0`，数据目录 `/Users/frog/Library/Application Support/Career Data`，schema v1。最新真实备份已创建在 `/Users/frog/Library/Application Support/Career Data-backups/batch-d-20260917T193448Z`，并恢复到新的系统临时目录。v1 恢复验证为 integrity `ok`、`current=24`、`records=27`、`applications=1`、`revisions=146`、总检查 199 行、1 个 artifact。

在该隔离恢复副本重新执行 v1→v2→v3 后，D dry-run 发现 1 条 legacy typed Communication：owner 未 materialize 为 canonical，但 legacy Job 可读且属于 demo；其 raw Note 存在、type 未核对。另有 1 个 legacy Submission，因没有明确 canonical association 不进入 Timeline。note-only=0、重复 Note 引用=0、真实 Migration Gate=0。v3→v4 apply/verify 成功，只新增 1 条 `communication_migration` manifest；`current=24`、`records=30`、`applications=1`、`revisions=146`，全部既有行与 artifact hash 不变。

pre-D v3 备份恢复后由 Batch C runtime 实际启动；Batch D runtime 拒绝 v3，Batch C runtime 拒绝 v4，均未靠修改整数回滚。随后从迁移后的生产副本再次复制分支，写入明确 synthetic Opportunity/无简历 Submission/Communication，再创建 v4 备份并恢复到新目录。恢复比较 `verified=true`、integrity `ok`、212 行、53 个引用、`current=26`、`records=34`、`applications=2`、`revisions=149`、差异 0；D runtime 与浏览器均读回 Communication revision 0、submitted/active、三源 Timeline，既有 PDF expected/actual sha256 同为 `8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。

私有证据位于 `/Users/frog/Library/Application Support/Career Migration Audits/batch-d-20260917T193448Z/`，文件权限为 0600；正文不复制进仓库。包含 v1 restore、B/C/D plan/apply/verify、forward write/recovery/runtime 和 Production final read-only 报告。

### 20.6 Production 保全

最终只读核对仍为 PID `2994`、`0.2.0`、schema v1、integrity `ok`；表计数保持 `1/24/27/1/146`，SQLite sha256 保持 `8a93d380a658a939686326abb9f00db126a98a62f003e8a0fedb635cfed291d9`，备份快照 hash 保持 `0850e98b047f8e70b03a5b4ee7dec195956270f26a214fc94dcde109491ceae8`，唯一 artifact hash 不变。没有 Production POST、迁移、进程重启、源码/dist 替换或用户资料清理。

### 20.7 `$workbench-review` 两轴结论

**规格轴：通过。** Communication 新写正本唯一，archive 产品语义与底层保留一致；phase/result/Submission/Resume/Interview/Offer/Research 均无联动；legacy 不猜 type/date，note-only 不进入 Timeline；Timeline 是三源投影。没有进入 Interview Core、Research/Raw/Patch、AI/AI-Config、Employment/Project 修改或 Production Cutover。

**规范轴：通过。** Domain Action 在事务内完成 owner/CAS/幂等检查，schema fence、hash-bound migration、pre-write rollback 和 post-write forward recovery成立；旧公共旁路停写，alias/canonical 共用服务边界。review 发现并修复 schema v4 backup recovery 条件、legacy 只读 Detail、未知创建日期分组、首次深链 scoped load、只读 Detail 写按钮及 archive 后 update 幂等重放。最终没有阻塞发现。

### 20.8 Gates、下一批前置与未验证项

没有新增真实用户 Migration Gate；当前唯一语义未知来自 demo/legacy typed Communication 和 legacy Submission，按规则 defer，不替用户做归属或类型判断。Communication API 没有已知双写旁路；直接修改 SQLite 不属于产品 Interface。

Interview Core 已具备隔离开发前置：canonical Opportunity、一次 Submission、typed Communication、稳定 ID、Timeline projection、旧写门禁和 v4 恢复基线均已成立。Production 仍是 v1，后续批次继续在隔离工作树/副本开发，不能把这一结论解释为已授权 Cutover。

尚未验证：真实 AI/ModelGateway/AI-Config、外部招聘平台送达、异机灾备、无损 v4→v3 逆迁移、Production v1→v4 Cutover，以及 demo 之外未来出现的真实 Communication/Submission 歧义。Batch D 到此停止，不进入 Interview Core。
