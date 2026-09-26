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

## Domain Objects

### Project

Project 是独立的长期对象，可以代表公司项目、个人项目、黑客松、开源、学习或其他项目；这些例子不是固定类型。最小核心字段为 `name`、`description`、自由 `tags`、`status`、`status_note` 和可选 `employment_id`。

`status` 只允许 `active`、`paused`、`completed`、`canceled`。不加 `stopped`，也不建 `merged_into`、`replaced_by`、`fork`、`predecessor`、`successor` 等关系图。取消、合并或替代说明放 `status_note`。标签只是分类，不能代替 Employment 等真实关系。

Project 不属于 Employment。非任职 Project 默认用户是唯一负责人，不强制维护 Participant。任职中的 Project 可选关联对应 Employment；任职页可以显示相关 Project，但打开和修改的始终是同一个 Project 正本。任职公司的协作者按需引用该 Employment 中已确认的 Person。

用户认为项目仍是同一个项目时，改名或转方向只更新同一 Project 的当前名称、描述和 Wiki 认知，不新建 pivot 或替代项目实体。

### Employment

Employment 表示一段真实任职环境，拥有公司/职位/时间、当前目标、长期协作人物、关联 Project、工作 Raw 和该任职范围的 Wiki 知识。它与 Project 是可选关联，不是父子容器。

Employment 结束后成为历史工作环境。其 People 知识、当时目标、承诺和组织环境保留为历史语义，不再冒充当前状态。关于用户自身、可跨环境复用的方法或规律，经 Wiki Patch 审批后可进入 Cognition。

### Opportunity

Opportunity 是一次具体求职尝试，并拥有自己的 JD、阶段与结果、招聘沟通、研究、面试过程、ResumeDocument 和 Submission。机会流程细则、Company 共享边界及真实投递行为以 Opportunity 四份正本为准。

### Person

Person 不是全局 CRM。Person 主要属于某一段 Employment；同一姓名在不同工作期不自动视为同一身份。Person 本体保持轻，协作含义与来源放在 Wiki。

Raw 中出现姓名或代称，不创建长期 Person。身份映射、长期 Person 创建，以及重要人物知识写入必须由用户确认；重复出现也不改变这条规则。未经确认的名字只能作为临时 mention 留在当前材料中。

人物知识使用 Fact、Observation、Hypothesis，并带 Raw `source_refs` 与适用范围；不做性格分类、心理诊断或信任度/权力指数。对已经由用户确认身份的 Person，Compiler 从 Raw 提出的明确要求、承诺等可以直接作为普通 Wiki Patch 逐条交给用户审批，无须再做一次同义的身份确认。用户逐条接受、编辑后接受或拒绝；不得批量接受。

## Wiki Semantic Layer 与 Cognition

Wiki 是 Raw 与 Domain Objects 之上的持续语义知识层，保存当前有效的含义、范围、标签、时间状态和 Raw `source_refs`。它可以描述项目知识、任职协作、人物、决策、当前目标/状态、风险、结果、未解决问题及 Cognition。

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
