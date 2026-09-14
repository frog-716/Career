---
name: workbench-plan
description: 在职场中台项目启动、拆分下一批或调整跨模块Interface时，将当前需求转成可执行批次与Astra/Luna分工。
---

读取项目根目录AGENTS.md、docs/00-authority.md、docs/03-architecture.md、docs/07-roadmap.md；涉及资料或分析时再完整读取docs/02-context-contract.md。

1. 从STATUS与实际代码确认当前行为，区分用户需求、工程建议和未知；首次没有STATUS则创建初始记录。
2. 选择一个纵向用户结果，明确输入、Interface（含错误/并发）、相关验收和依赖。
3. 分配Luna有限执行工作，划定互不重叠文件；公共Interface由Astra先固定。独立只读核查可并行。
4. 写当前批次任务到docs/execution/，STATUS只链接当前任务；设计结论修改唯一所属文档。

完成条件：当前批次能直接执行，允许修改文件与验收可判断。随后进入实施，不为后续所有批次预写大量空票。Gate与模型调度遵循docs/06-agent-workflow.md。
