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
| D. 业务资料、岗位情报与沟通 | 当前Raw、Patch底座、公司/机会Research、沟通与初步Timeline；人工操作先可用 |
| E. 真实轮次与模拟闭环 | 确认real、逐轮准备、绑定simulation、Context Pack复制、Transcript与当前复盘 |
| F. Offer与结束 | 当前Offer、谈薪沟通、最终result与完整历史回看；无自动Employment |
| G. 领域AI与Context策略 | 各任务显式Context/输出/写入权限、Patch与失效；真实模型质量另行实测 |
| H. 兼容写入口收敛 | 对应替代路径验收后退役旧写入口，保留旧材料和来源；可随各模块批次完成，不等最后大删 |

按实际依赖拆一个可执行纵向批次；普通工程选择自主解决，旧资料归属/历史含义等不可推导问题进入Migration Gate。真实模型未配置不阻塞可独立的手动闭环，也不能把手动版当全部AI验收完成。模拟本期采用用户操作ChatGPT语音与文本回传，不要求内置语音平台。

本周期不扩展Employment / Project / People / Growth内部结构；只允许通过稳定Career Context接口使用获准资料。SearchCycle、TargetRole与OrgUnit旧引用兼容保留，不升级为Opportunity必需层；独立JobPosting不是本周期目标。

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
