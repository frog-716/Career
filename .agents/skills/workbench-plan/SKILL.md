---
name: workbench-plan
description: 在职场中台项目启动、拆分下一批或调整跨模块Interface时，将当前需求转成可执行批次。
---

读取项目根目录AGENTS.md、docs/00-authority.md、docs/03-architecture.md、docs/07-roadmap.md；涉及资料或分析时再完整读取docs/02-context-contract.md。

1. 从STATUS与实际代码确认当前行为，区分用户需求、工程建议和未知；首次没有STATUS则创建初始记录。
2. 选择一个纵向用户结果，明确输入、Interface（含错误/并发）、相关验收和依赖。
3. 当前主 Agent 先固定公共Interface，再拆分有明确顺序、文件范围和停止条件的实施步骤，并统一完成整合与验收。
4. 只有跨轮次、跨模块或确需持久化协调时才写当前批次到docs/execution/并由STATUS链接；小任务直接维护所属正本，不为单次计划或验证新增文档。

完成条件：当前批次能直接执行，允许修改文件与验收可判断。随后进入实施，不为后续所有批次预写大量空票。
