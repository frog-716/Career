# 长期 Career 模型

状态：已确认的目标规格；不表示已经实现。最后整理：2026-09-25。

本文是 Career 跨模块长期模型的唯一规则正本。Opportunity 的阶段、招聘流程、轮次、投递和谈薪细节仍由 [Opportunity 四份目标规格](opportunity/opportunity-product-model.md)负责；两者冲突时，本文负责全局导航、长期对象边界、Wiki/Raw/Person、Resume AI 隐私及 Resume 入口，Opportunity 正本负责机会内领域动作。工程现状见 [Architecture](../03-architecture.md)，不能覆盖本文目标。`docs/audit/` 与 `docs/archive/` 仅保留历史原貌。

## 产品边界

一级导航固定为：**Wiki / 机会 / 项目 / 任职**。简历不是一级工作区。完整 Resume Editor 继续存在，从某个机会的“编辑简历”进入，并明确显示当前编辑的是哪个 Opportunity 的简历。

Career 是 local-first 的个人长期职业工作台，仓库保持 Private，不公开发布。本模型不要求云部署、多端同步或通用 Agent 平台。

## 对象总图

```text
外部材料 / 用户输入
          ↓
         Raw
          ↓ 关联
Domain Objects：Project / Employment / Opportunity / Person
          ↓ 当前语义与来源引用
    Wiki Semantic Layer
       ├── Cognition（跨经历的个人认知）
       └── Wiki Compiler 提议并由用户逐条审批 Patch

Opportunity ──拥有──> ResumeDocument ──有版本──> ResumeVersion
      └────────────> Submission（冻结实际投递材料）
```

Raw 记“当时原始材料是什么”；Domain Object 记当前业务身份、状态与关系；Wiki 记从材料中整理出的当前含义；Cognition 是 Wiki 中可以跨项目、任职和机会复用的个人认知。它们不是重复的事实库。

## Raw

Raw 是原始依据，保留来源内容或受控更正后的当前文本，以及来源、时间和对象引用。它可以是粘贴文字、聊天、会议/面试转写、文档或项目资料。第一版继续从明确业务入口接收材料，不建立万能导入平台。

Raw 回答“原来到底发生了什么”，不负责解释全部业务含义，也不自动创建长期人物。普通名字 mention 只在本次 Raw/分析范围内使用，不因此成为 Person。

### D1 Raw 与来源引用合同

D1 手工新增的 Raw 保存标题、正文、来源类型、所属范围、创建时间、用户 provenance、revision 与内容摘要，并有稳定 ID；写入后不提供普通编辑或删除入口。Raw 是原始依据，不是 Wiki 的第二份正文库。Wiki 只保存语义和来源指针；任何 Wiki 新建、改写、退役或恢复都不能反写或改变 Raw。将来需要更正时由明确业务入口定义更正规则。

已有原始记录按原 ID 引用，不复制正文来制造统一副本。`source_ref` 是稳定类型化指针：`kind + id + revision + hash`。读取时检查版本与摘要；如果旧记录只保留当前正文且已经变化，系统拒绝把新正文冒充为旧版本。现有事件、证据、面试转写、任职/机会原话、沟通和资料原件可作为 Raw 来源；AI 复盘、Research 派生结论、Achievement 与 Wiki 不属于 Raw。

Raw 的范围由 Career 正式对象拥有。Person 范围只能指向已确认人物；机会材料只在同一 Opportunity 内可见，通用 Wiki / Cognition 读取不得预装机会私有知识。Cognition 可以引用个人、Project、Employment 与已确认 Person 的资料，但本期不自动提炼 Cognition。

## Domain Objects

### Project

Project 是独立的长期对象，可以代表公司项目、个人项目、黑客松、开源、学习或其他项目；这些例子不是固定类型。最小核心字段为 `name`、`description`、自由 `tags`、`status`、`status_note` 和可选 `employment_id`。

`status` 只允许 `active`、`paused`、`completed`、`canceled`。不加 `stopped`，也不建 `merged_into`、`replaced_by`、`fork`、`predecessor`、`successor` 等关系图。取消、合并或替代说明放 `status_note`。标签只是分类，不能代替 Employment 等真实关系。

Project 不属于 Employment。非任职 Project 默认用户是唯一负责人，不强制维护 Participant。任职中的 Project 可选关联对应 Employment；任职页可以显示相关 Project，但打开和修改的始终是同一个 Project 正本。任职公司的协作者按需引用该 Employment 中已确认的 Person。每个 Project 与 Person 的协作关系有自己的 `project_role`，由用户自由填写，不设固定枚举；它与 Person 在 Employment 中的 `role` 完全独立。同一个人在不同 Project 可以分别担任 Reviewer、Sponsor 等角色；修改其中一项不会修改另一项。

用户认为项目仍是同一个项目时，改名或转方向只更新同一 Project 的当前名称、描述和 Wiki 认知，不新建 pivot 或替代项目实体。

### Employment

Employment 表示一段真实任职环境，拥有公司/职位/时间、当前目标、长期协作人物、关联 Project、工作 Raw 和该任职范围的 Wiki 知识。它与 Project 是可选关联，不是父子容器。

Employment 结束后成为历史工作环境。其 Person、人物关系和任职角色继续保留并可读；当时目标、承诺和组织环境也保留为历史语义，不再冒充当前状态。关于用户自身、可跨环境复用的方法或规律，经 Wiki Patch 审批后可进入 Cognition。

### Opportunity

Opportunity 是一次具体求职尝试，并拥有自己的 JD、阶段与结果、招聘沟通、研究、面试过程、ResumeDocument 和 Submission。机会流程细则、Company 共享边界及真实投递行为以 Opportunity 四份正本为准。

### Person

Person 不是全局 CRM。Person 主要属于某一段 Employment；同一姓名在不同工作期不自动视为同一身份。Person 本体保持轻，只记录这个人在该 Employment 中的身份资料（姓名、任职角色等），协作含义与来源放在 Wiki。

Raw 中出现姓名或代称，不创建长期 Person。身份映射、长期 Person 创建，以及重要人物知识写入必须由用户确认；用户手工创建 Person 本身就是身份确认，不再要求第二次确认；重复出现也不改变这条规则。未经确认的名字只能作为临时 mention 留在当前材料中，待解决身份由未来的 Raw / Wiki Compiler 链处理。本阶段正常人物卡片不显示 `identity confirmed` 等技术状态。

人物的明确要求、承诺、Fact、Observation、Hypothesis 都属于 Wiki Semantic Layer，按范围和来源记录，不扩成 Person 本体字段。人物知识带 Raw `source_refs` 与适用范围；不做性格分类、心理诊断或信任度/权力指数。对已经由用户确认身份的 Person，Compiler 从 Raw 提出的明确要求、承诺等可以直接作为普通 Wiki Patch 逐条交给用户审批，无须再做一次同义的身份确认。用户逐条接受、编辑后接受或拒绝；不得批量接受。

## Wiki Semantic Layer 与 Cognition

Wiki 是 Raw 与 Domain Objects 之上的持续语义知识层，保存当前有效的含义、范围、标签、时间状态和 Raw `source_refs`。它可以描述项目知识、任职协作、人物、决策、当前目标/状态、风险、结果、未解决问题及 Cognition。

### D1 Wiki Knowledge 合同

第一版语义类型只用 `Fact`、`Observation`、`Hypothesis`：Fact 是用户当前确认、由原始材料支持的事实；Observation 是从材料中观察到、尚未升格为绝对事实的模式；Hypothesis 是仍待验证的推断。类型不带 AI confidence 分数。用户可以直接写 Wiki；这种记录的 provenance 明确标记为 `user`，来源列表为空，不伪造 Raw 引用，也不建立第二套来源账本。

每条 Wiki Knowledge 属于一个明确的 Project、Employment、Opportunity、已确认 Person、Personal 或 Cognition 范围，可带自由 Tags 和 0..N 个稳定 `source_refs`。Person 范围必须引用已存在且身份已确认的 Person；Wiki 写入不创建 Person。一份 Raw 可以支持多条知识，一条知识也可引用多份 Raw。写入和改动只保存引用，不复制原文。Opportunity A 的知识只能在 A 的显式范围中显示；“全部长期范围”视图不读取 Opportunity 私有知识。Cognition 只保留手工记录能力，不在 D1 自动归纳。

Wiki Knowledge 的状态为 `current` 或 `retired`。新建、编辑、退役与恢复都使用同一对象 ID，沿用 Career 的 `current` / `revisions` 版本机制与 CAS；改写以新修订更新当前语义，默认读取当前知识，历史视图保留旧版本。退役只让知识退出默认当前视图，不物理删除内容、修订或来源引用。来源与版本历史沿用这套现有机制，不另建第二套 provenance、archive 或 history 系统。D1 没有 Compiler：所有写入均由用户手工创建或编辑，不调用 Provider。

Wiki 不创建第二套 Project、Employment、Opportunity 或 Person 正本。对象的身份、主字段、状态及真实关系由 Domain Object 拥有；Wiki 保存需要跨材料理解的语义。业务含义优先使用 `scope` 与自由 `tags` 表达，不为 Decision、Commitment、Risk、Achievement 等词各造一套实体表。知识语义优先收敛到 `Fact`、`Observation`、`Hypothesis`。

Cognition 是 Wiki 的一部分，表达从多段经历中归纳、未来还可复用的关于用户自身的认知，例如工作方法、能力证据或规律。它可以跨 Employment、Project、Opportunity，并保留来源；不另建独立数据库。

AI 与界面先看相关 Wiki。当前语义不足以回答任务时，再按需查找并读取具体 Raw，避免每次把全部原文塞进上下文。引用 Raw 只表示来源可追溯，不自动证明推论正确。

## Wiki Compiler

Compiler 不是普通摘要器。它比较新 Raw 与相关对象已有的当前 Wiki，回答“这批材料让我们原来的认知发生了什么变化”。

```text
保存 Raw
→ 确定关联对象
→ 读取相关对象的当前 Wiki
→ 比较新旧认知
→ 生成逐条 Wiki Patch（add / rewrite / retire）
→ 用户逐条接受 / 编辑后接受 / 拒绝
→ 更新 Wiki 当前态，保留 Revision 与 Raw source_refs
```

`retire` 让旧认知不再被当作当前结论，但保留历史，不物理删除。索引、来源引用、创建/更新时间和近期活动等低风险整理可以自动完成；影响未来理解的知识内容必须逐条经用户确认，不提供批量接受。

对于尚未确认身份的人物，不把要求或承诺写进长期 Person。确认身份后，这些内容作为常规 Wiki Patch 审批，不增加第二道身份确认。

### D2 首版实现合同

D2 每次只处理用户从页面明确选择的一份新手工 Raw（`raw_material` / `manual_text`），不批量扫描或自动触发。Compiler 只读取该 Raw 的直接范围及明确关系：Project 可带其 Employment 和该 Project 已关联的确认 Person；Employment 可带其确认 Person；Person 可带所属 Employment；Opportunity 只带该机会自身；Personal 只带个人范围。Cognition 不在 D2 范围内。只读取这些范围内当前有效的 Wiki，不读取其它对象、全部 Raw、退役知识、Resume、Feedback 或私人资料；不通过姓名 mention 搜索或匹配 Person。

发给模型的专用 DTO 固定为 `task`、`raw`、`scopes`、`current_knowledge`。Raw 只含 `id`、`source_kind`、`created_at`、`content`；范围只含 `type`、`stable_id`、必要的文字身份字段；当前 Wiki 只含 `knowledge_id`、`type`、`content`、`tags`、`revision` 和目标范围标识。DTO 不包含数据库 metadata、hash、Secret、完整历史 revision、退役知识或其它 Career 资料。模型的每条 `source_refs` 只能标识本轮唯一 Raw 的 kind、id、revision；服务器本地核验后补入 D1 稳定来源指针中的 hash，模型不提供 hash，也不能借此引用其它 Raw。

发送分成准备与确认两步。准备只构造最终请求，不产生 Provider outbound。用户预览必须直接显示本轮 Raw 全文、范围对象的可读名称、每条当前 Wiki 全文及其 Tags；这些展示值只能来自已经清洗的最终 Context DTO，不得再查其它 Career 数据。长正文可以在有界区域内滚动，但必须能查看全文。预览主说明使用“AI 会比较‘新资料’和‘Wiki 里已有的信息’，判断 Wiki 是否需要更新”，并按“新资料 → 所属项目 / 任职 / 人物 → Wiki 里已有的信息 → AI 会判断”的顺序展示；Fact / Observation / Hypothesis 分别翻译为“已确认事实 / 观察 / 待验证判断”，不在每条知识上重复显示范围名称。预览明确说明“仅限上面这些内容，不会读取其他 Career 资料”，模型与条数等技术信息收在默认折叠的次级详情中。用户点击“让 AI 整理”仍走现有单独 confirm，不改变 prepare / preview / confirm 边界。只有用户单独确认后才执行现有 AI operation、dispatch slot、Provider gateway、审计、幂等及错误恢复合同；每个确认 operation 最多一次 outbound，不自动 retry。请求预算遵守共享 50 个来源、200,000 字符和 256 KiB 请求上限；超限在发送前拒绝。

模型输出只允许严格结构化的 `add`、`rewrite`、`retire` Patch，最多 20 条。Fact 必须被所选 Raw 明确支持；Observation 不能把单次材料伪装成重复模式；推断必须保持 Hypothesis；可以合法返回 0 条。服务器拒绝未知字段、非法类型/范围/目标/revision、缺失或跨 Raw 的来源及重复目标，不猜测或修补模型输出。Proposal 与正式 Wiki 分开保存，pending Patch 不出现在 Wiki 当前列表。

用户一次只处理一条：接受、编辑后接受或拒绝，没有批量入口。只有接受会通过 D1 Wiki mutation 更新正式 Wiki，并沿用原对象 ID、CAS 与 revision；rewrite 保留原知识类型、标签并追加来源，retire 保留知识与历史只退出当前视图。编辑 add/rewrite 时用户编辑的是 Wiki 正文；编辑 retire 时用户编辑退役原因并保存在审批结果中，Wiki 原文不变。拒绝不改 Wiki。应用前复核 Raw、关联范围/关系、相关当前 Wiki 和目标 revision；任何变化都拒绝旧 Patch，不静默 rebase。Provider `outcome_unknown` 不自动重发，也不创建推定成功的 Proposal。D2 复用 schema v6 的现有 records/current/revisions 与 AI operation 存储，不新增 schema migration。

## Resume / Submission

每个 Opportunity 独立拥有 `0..1 ResumeDocument`；不建立共享当前简历。简历不是一级导航。用户从机会进入编辑器时默认绑定该机会简历；编辑器允许切换到别的 Opportunity 简历或版本，并清楚标出当前主体。

若用户还没有 Resume/Version，首次简历使用 A4 基础模板：Profile 区显示姓名、电话、微信、邮箱；正文包含专业技能、工作经历、项目经历、教育背景；第一版不含 GitHub。若已有 Resume/Version，可选择一个版本，只复制其当前内容，随后立即进入编辑。复制后的文档完全独立，不保存跨简历 copy lineage。ResumeVersion 名称承担备注；不保留 ResumeUse，也不设置“关联已保存版本”的正常流程。

工作稿可靠自动保存；`⌘S` 打开轻量版本命名框并创建 ResumeVersion，不触发浏览器保存网页。普通保存、版本历史和跨简历复制不改变 Raw provenance、Wiki source_refs、Research provenance 或 Submission 历史。

Resume AI 使用专门的最小 DTO，不直接发送数据库 ResumeDocument。默认 DTO 只告知 Profile 区是否存在，以及其中有哪些字段存在；不发送姓名、电话、微信、邮箱等真实字段值，ResumeDocument中Profile区的实际内容也必须从默认请求中剔除。其他任务未来若确需处理 Profile 内容，必须另定该任务的最小发送范围，不能扩大这个默认 DTO。

Resume AI 只看当前 Opportunity、JD、当前 Opportunity Research、当前稿、相关 Wiki/Project Knowledge/Cognition；不读其他 Opportunity，也不一次性塞入全部 Raw。建议只用 `rewrite`、`add`、`delete`，逐条显示并由用户审批；不提供批量接受。表达可以重写，不能编造项目、数字、职责、结果或本人贡献。

Submission 表示用户确认现实中已经发送。它冻结实际发送的 Resume、PDF、Greeting 和日期。之后修改当前简历或 Profile 不得改变历史投递材料。面试 Simulation Context Pack 继续使用实际投递时冻结的 Resume；本周期先回归现有链路，不提前改成复杂 Agent。

编辑器快捷键是硬性目标。特别是 `⌘⇧←` / `⌘⇧→`，Phase H 必须先核对真实浏览器与 macOS 行为，再请用户手工验收预期选择范围，之后才能实现；不得仅凭文字猜测 selection algorithm。

## 旧数据与迁移规则

用户确认历史业务数据基本是测试数据。动数据前仍须识别真实资料和测试资料。明确归属于测试的旧业务对象可安全清理；未知或可能真实的记录不得假定为测试，也不得擅自删除。目标模型优先，不为 T14、ResumeUse、Achievement、Evidence 建复杂兼容迁移层；确认有价值的真实信息时，按 Raw + Wiki source_refs 映射或保留其来源。

数据库 schema migration 必须显式、安全、可测试：先盘点、备份、dry-run，在隔离副本上执行并核对，提供失败恢复办法，再按批次授权边界处理正式数据。清理测试业务行不能替代 schema migration 的迁移测试，也不能在应用启动时暗中改 schema。

## 被替代的当前规则

以下旧描述不再是目标：简历工作台是一级导航；Project/Employment/Person 延后到下个周期或只经抽象 Context 接入；Person 是跨任职全局名录；名字 mention 可自动升级人物；T14 成果复用是冻结架构；ResumeUse 需兼容常规读取或有自己的用途模型；Achievement/Evidence/Event 必须长期作为重复领域正本；Resume AI 默认可以收到 Profile 真实值；已确认人物的每条明确要求/承诺还需另一次身份确认；根据文字自行猜 `⌘⇧←/→` 的选择算法。

这份列表取代旧文档中的相反目标摘要；旧实现只作为审计事实记录，历史 audit/archive 原文不改。
