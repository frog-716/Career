# Roadmap

本页维护周期范围和推进门槛；当前交付、失败与未验证状态只在[STATUS](execution/STATUS.md)。[authority](00-authority.md)决定模块目标；旧B00–B06和旧“先接真实Provider”的排序不再覆盖本周期。历史批次保留于execution作证据，不重新编号成当前待办。

## Current Cycle — Opportunity Vertical

目标是完成一次具体求职尝试的纵向闭环，遵循四份[Opportunity模块正本](target/opportunity/opportunity-product-model.md)及authority路由。采用增量重构，保护现有数据，复用编辑器、版本/PDF、事务/CAS/幂等和Context边界。

Documentation & Agent Alignment是正式业务重构前的独立文档批次；完成文档不代表下列实现批次已开始。后续依赖与验收输入引用[Gap Analysis §8](audit/OPPORTUNITY-GAP-ANALYSIS.md)，不复制成另一套详细批次规格。

| 推荐顺序 | 用户结果 / 推进门槛 |
| --- | --- |
| A. 可恢复迁移基线 | dry-run与引用/冲突盘点、备份及隔离恢复、运行版本核对、已知测试失败解释；尚不切换生产业务模型 |
| B. 机会正本与管线 | 公司关联、一次尝试的唯一状态、管线与基本Workspace；旧ID和历史可达 |
| C. 每机会简历到一次投递 | 独立工作稿、Greeting、普通/投递版本、可无简历Submission、冻结材料 |
| D. Communication + Timeline 第一阶段 | 已投递后手动记录text/phone/other真实沟通；由Opportunity创建、Submission、typed Communication派生初步Timeline |
| E. 完整 Interview Vertical | 无日期也可明确确认real并首次进入面试；逐轮准备、绑定simulation、历史Final Review多选、Context Pack复制、current Transcript/Review、real-only Research Patch确认与Timeline；simulation永远零Patch |
| F. Offer与结束 | 当前Offer、谈薪沟通、最终result与完整历史回看；无自动Employment |
| G. 领域AI与Context策略 | 各任务显式Context/输出/写入权限、Patch与失效；真实模型质量另行实测 |
| H. 兼容写入口收敛 | 对应替代路径验收后退役旧写入口，保留旧材料和来源；可随各模块批次完成，不等最后大删 |

按实际依赖拆一个可执行纵向批次；普通工程选择自主解决，旧资料归属/历史含义等不可推导问题进入Migration Gate。真实模型未配置不阻塞可独立的手动闭环，也不能把手动版当全部AI验收完成。模拟本期采用用户操作ChatGPT语音与文本回传，不要求内置语音平台。

Batch D已按用户2026-09-18确认收窄为Communication + Timeline第一阶段。RawSource、PatchProposal、公司/机会Research与AI沟通分析不再作为D完成条件，仍需后续单独确定批次和依赖；不因D完成而视为已经交付。

本周期不扩展Employment / Project / People / Growth内部结构；只允许通过稳定Career Context接口使用获准资料。SearchCycle、TargetRole与OrgUnit旧引用兼容保留，不升级为Opportunity必需层；独立JobPosting不是本周期目标。

## Resume Workspace Productization（Feedback登记）

用户2026-09-17确认：一个Resume Workspace UI，多份由不同Opportunity拥有的ResumeDocument。使用场景是从机会进入其专属工作稿，或从左侧唯一“简历工作台”选择最近编辑的文档，再在同一个纸面编辑器继续工作。动机是隔离业务内容但保留统一工具，避免多套工作台、自动选错稿和机会页面重复管理版本。

Batch C落实导航和身份：Opportunity → 正确document_id → 同一Resume Workspace → 返回来源Opportunity；左侧直接进入显示当前文档/最近编辑项，不自动选第一份。autosave不生成版本；主动保存产生普通版本，RecordSubmitted产生标明机会/日期的不可变投递版本。版本管理归Resume Workspace，Opportunity只读实际投递材料。继续复用现有排版、编辑器和PDF能力。

后续Resume Experience独立优化可细化文档侧栏、普通/投递历史分组、来源呈现和视觉布局；本登记不是扩大C领域范围的授权。

## AI Infrastructure → AI-Config Batch（已由 Enhancement Sprint 实现）

Feedback登记：用户2026-09-17确认。动机是用户需要切换不同提供商/模型、明确当前默认模型，并安全保存密钥；使用场景是在设置页维护配置、测试连接、选择默认后供业务Skill统一使用，没有模型时仍可编辑资料、简历及记录求职业务。

支持多ModelConfig：provider、base_url、model、api_key_ref、enabled；添加、编辑、删除、测试连接和选择唯一global default_model_config_id。API Key由SecretStore持有，不进入普通Career DB、普通backup、Context或Prompt。业务Skill后续仅通过ModelGateway调用；未来可增加SkillModelBinding覆盖全局默认。

已实现：ModelConfig/AISettings 复用 schema v6 的 current namespace；macOS Keychain SecretStore；OpenAI-compatible ModelGateway；设置页维护、测试连接、默认切换与显式删除；Interview Real FinalReview/ResearchPatch、结构化 Resume proposal、Company/Opportunity Research proposal 均通过 Gateway。真实 Provider 语义质量、真实 Key/模型和生产部署仍单独按运行证据核验，不用 TestProvider 代替。

## Next Cycle — Employment / Project / People / Growth

这些模块保持当前状态与已有数据。本期不补造完整领域图、不重写内部schema；下一周期基于实际使用问题、现状证据和用户确认，再制定其模块authoritative docs与验收。Opportunity不直接依赖它们未来的数据库设计。

## Later

- Offer Comparison
- Global Inbox
- Advanced Career Intelligence
- Automation

它们是后续方向，不是本期欠缺即阻塞验收的前置条件。自动招聘/发送、连续语音、语义索引或Repository Ingestion等能力须有真实需求与授权边界再拆批；不预建通用Agent平台、云同步或微服务。

## 批次记录与停止条件

每批编码前固定：一个用户结果、输入/Interface、错误/并发/副作用、允许文件、相关验收、依赖与停止条件。需要跨轮次协调才建立execution批次记录并由STATUS链接；不为所有后续阶段预写空票。

验证与风险相称：文档批次检查权威、链接、diff及范围；持久化/迁移/权限/并发使用虚构隔离测试，界面按实际主路径检查。通过后记录真实证据与未验能力，用户明确要求分析或文档后停止时，不自动进入实施。
