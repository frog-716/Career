# Roadmap

本页维护周期范围和推进门槛；当前交付、失败与未验证状态只在[STATUS](execution/STATUS.md)。[authority](00-authority.md)决定模块目标；旧B00–B06和旧“先接真实Provider”的排序不再覆盖本周期。历史批次保留于execution作证据，不重新编号成当前待办。

## Current Cycle — 长期 Career 模型

唯一长期模型正本为[长期 Career 模型](target/long-term-career-model.md)；Opportunity内部流程继续由[四份Opportunity正本](target/opportunity/opportunity-product-model.md)负责。Phase A–I 的结果、依赖和验收边界见[实施计划](execution/WIKI-PROJECT-RESUME-IMPLEMENTATION-PLAN.md)。目标分批落地，不表示当前代码已实现。

| 阶段 | 范围 | 状态 |
| --- | --- | --- |
| A | 长期 Career 模型正本及当前权威文档对齐 | COMPLETE：文档已更新；未改业务代码 |
| B | 一级导航、独立 Project、Employment-Project 关系 | COMPLETE / PASS：代码、自动检查、Runtime Rebaseline、两轮用户 UI 验收及本轮测试数据清理均通过 |
| C | Employment / Person 生命周期和身份确认 | COMPLETE / PASS |
| D1 | Raw + Wiki Semantic Foundation | COMPLETE / PASS：自动验证、Runtime、两段用户 UI 验收、清理及 Git 收口均通过 |
| D2 | Wiki Compiler | COMPLETE / PASS：真实 DeepSeek smoke、逐条编辑后接受、Wiki rewrite/history/source_refs、测试数据清理及 Git 收口均通过 |
| D3 | Project / Employment / Person 工作区接入 Raw + Wiki Compiler | COMPLETE / PASS：两轮用户 UI 验收、D3.5 Fresh-Eyes UX 修复与隔离回归通过 |
| D4 | Wiki Cognition | SYNTHETIC READY；基础实现与 UX-1 形成依赖完整的 Cognition/UX checkpoint；导航兼容测试单行修正已获授权。REAL SMOKE PAUSED / NOT YET PASSED：被 UX Reset 暂停，正式 Cognition 未完成真实验收，不是 COMPLETE |
| UX-1 | AI 进度、对象归属及关闭/切页/刷新恢复 | COMPLETE / PASS：用户 UI、机器核验、TestProvider exactly once 与无重复 dispatch 均通过 |
| UX-2 | Opportunity + Wiki + Shared Visual Foundation | COMPLETE / PASS：四张用户截图与 Shared Visual Foundation 验收通过，自动回归、Git 收口和正式 Runtime Update 均完成；UX-3 READY，不恢复 D4 smoke |
| UX-3 | 项目 / 任职 / 人物工作区 | COMPLETE / PASS；正式加载随 Phase 1 Runtime Update 核验 |
| Resume 入口收口 | 四一级导航，机会打开原简历与返回 | 自动、独立审查和隔离 Fresh-Eyes 通过；Git / Runtime 收口中，不等于整个 F 完成 |
| UX-4 | 简历保存回读、投递、沟通、面试与准备连续路径 | 紧随入口收口执行 |
| Resume AI Privacy Gate | 从空 DTO 构造允许字段，捕获请求做对抗验证 | UX-4 后执行；任何真实 Resume AI outbound 前必须通过 |
| UX-5 | 全新虚构库独立盲审完整核心链 | Privacy Gate 后执行；通过后才可恢复 D4 真实 smoke Preview |
| E | 分类旧数据并退役 T14、ResumeUse 与重复业务对象 | 尚未开始；目标模型优先，分类后可清理明确测试对象 |
| F | 从机会进入简历、创建/复制与版本流程 | 尚未开始 |
| G | Resume AI 最小 DTO 与逐条建议 | 尚未开始 |
| H | 快捷键审计、真实 macOS 行为核对和用户手工验收 | 尚未开始 |
| I | 全链回归、迁移副本演练与文档收口 | 尚未开始 |

Project、Employment、Person不是下一周期才定义的对象。真实资料、测试资料和未知资料须分类处理；测试数据可在确认归属后清理，未知或真实资料不猜测删除。Schema migration 仍需显式、安全、可测试。真实Provider、浏览器与 macOS 结果按实际运行分别验收；Simulation Context Pack继续使用投递时冻结的Resume。

## AI Infrastructure → AI-Config Batch（已由 Enhancement Sprint 实现）

Feedback登记：用户2026-09-17确认。动机是用户需要切换不同提供商/模型、明确当前默认模型，并安全保存密钥；使用场景是在设置页维护配置、测试连接、选择默认后供业务Skill统一使用，没有模型时仍可编辑资料、简历及记录求职业务。

支持多ModelConfig：provider、base_url、model、api_key_ref、enabled；添加、编辑、删除、测试连接和选择唯一global default_model_config_id。API Key由SecretStore持有，不进入普通Career DB、普通backup、Context或Prompt。业务Skill后续仅通过ModelGateway调用；未来可增加SkillModelBinding覆盖全局默认。

已实现：ModelConfig/AISettings 复用 schema v6 的 current namespace；macOS Keychain SecretStore；OpenAI-compatible ModelGateway；设置页维护、测试连接、默认切换与显式删除；Interview Real FinalReview/ResearchPatch、结构化 Resume proposal、Company/Opportunity Research proposal 均通过 Gateway。真实 Provider 语义质量、真实 Key/模型和生产部署仍单独按运行证据核验，不用 TestProvider 代替。

## Later

- Offer Comparison
- Global Inbox
- Advanced Career Intelligence
- Automation

它们是后续方向，不是本期欠缺即阻塞验收的前置条件。自动招聘/发送、连续语音、语义索引或Repository Ingestion等能力须有真实需求与授权边界再拆批；不预建通用Agent平台、云同步或微服务。

## 批次记录与停止条件

每批编码前固定：一个用户结果、输入/Interface、错误/并发/副作用、允许文件、相关验收、依赖与停止条件。需要跨轮次协调才建立execution批次记录并由STATUS链接；不为所有后续阶段预写空票。

验证与风险相称：文档批次检查权威、链接、diff及范围；持久化/迁移/权限/并发使用虚构隔离测试，界面按实际主路径检查。通过后记录真实证据与未验能力，用户明确要求分析或文档后停止时，不自动进入实施。
