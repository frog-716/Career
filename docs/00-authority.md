# 权威顺序与读取路由

## 正本顺序与模块范围

1. 用户最新明确指令。
2. 当前任务所属模块的已确认目标规范。跨模块长期对象、Raw/Wiki/Person 语义、一级导航、Resume 入口与 Resume AI Profile 隐私以[长期 Career 模型](target/long-term-career-model.md)为唯一正本。Opportunity 的阶段、招聘流程、轮次、投递与谈薪细节由下列四份文件共同负责：

   | 正本 | 负责的问题 |
   | --- | --- |
   | [opportunity-product-model.md](target/opportunity/opportunity-product-model.md) | 产品定义、阶段与结果、用户工作区 |
   | [opportunity-domain-model.md](target/opportunity/opportunity-domain-model.md) | 对象职责、关系、可变与冻结规则 |
   | [opportunity-ui-flow.md](target/opportunity/opportunity-ui-flow.md) | 用户动作、Domain Action及页面变化 |
   | [context-ingestion.md](target/opportunity/context-ingestion.md) | 资料入口、Patch确认、Context读取边界 |

3. 项目总览与跨模块合同：[产品](01-product.md)、[Context](02-context-contract.md)、[Journey](04-journeys.md)。它们承接模块正本，不另定义一套Opportunity模型。
4. 工程合同与实施建议：[Architecture](03-architecture.md)、[Roadmap](07-roadmap.md)。可作最小合理工程调整，不能改变模块产品语义或扩大周期范围。
5. [Acceptance](05-acceptance.md)把当前模块规范转成可观察验收；新增验收不代表实现或测试已通过。

旧product、architecture、journey、execution批次和模块README中与两类目标正本冲突的描述不再覆盖它们。独立JobPosting、多次Submission等旧方向不继续作为当前待办。Project、Employment、Person 已纳入长期模型；不再引用“下周期设计”或旧模块边界作为目标。旧表和代码可以作为现状证据，不能削弱新模型或要求复杂兼容。

四份目标按职责交叉阅读，而非按编号让一份全部覆盖另一份。具体已有规则的读取口径：Domain §5规定每次有简历投递都生成特殊版本，UI §6的“未手动保存时自动生成”不能解读为其他情况不生成；Domain §18的Offer原始材料不可改，是通用Raw更正规则的特定边界。遇到无法按职责消解的真实冲突，指出具体条款再确认，不自行扩写产品设计。

## Agent读取顺序

AGENTS → 本文 → 判断任务模块 → 模块authoritative docs → 按任务读取architecture / context / journey / acceptance / roadmap → STATUS、模块README及必要代码/测试。Opportunity任务先读以上四份目标；资料/AI任务完整读Context合同。跨模块任务分别确认拥有者，只加载依赖边界，不借关联展开全部模块重构。

AGENTS是入口，Skills负责拆批、实施和审查方法；业务规则维护于项目文档。README只提供导航。新的产品决定写回所属正本，总览/验收同步必要摘要与引用，不建立重复字段规格。

## 目标、现状与历史证据

- `docs/target/` 是已确认目标，**不代表已经实现**。总览中的target acceptance同样是待验要求。
- [AS-IS System Map](audit/AS-IS-system-map.md)是2026-09-17的现状证据快照；[Gap Analysis](audit/OPPORTUNITY-GAP-ANALYSIS.md)是差异与迁移建议快照。两者保持历史原文，不随本次文档对齐改写，也不升级为目标规范。
- [STATUS](execution/STATUS.md)记录当前交付、已知问题和批次状态。代码、schema、实际测试与运行观察分别证明对应能力；历史成功不覆盖新失败，源代码能力不证明长驻服务已经加载。
- execution中的旧批次、fixtures与外部参考仅提供可追溯证据或验证材料；[archive](archive/README.md)只用于历史追溯，不进入当前目标链。
- 个人事实只来自运行时资料正本，不从源码、开发聊天或审计中推断。测试用虚构隔离材料。

## 稳定边界

Local-first，代码与用户数据分离，无本期云部署/多端同步要求；GitHub 仓库可以公开，但真实个人资料、运行态、备份和凭据只保留在本机，并由 `.gitignore` 排除。AI经用户选择的Provider处理明确任务；正式事实变更遵守所属模块的确认合同。真实模型、语音、招聘来源、备份恢复逐项核验，安装或demo不能替代成功证据。迁移先区分真实资料与测试资料，明确属于测试的旧业务对象可安全清理；未知或真实记录不可猜测删除。Schema migration 必须显式、安全、可测试。
