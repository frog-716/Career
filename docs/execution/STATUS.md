# 当前状态

最后整理：2026-09-16。本文只维护当前交付范围、现役入口、外部 Gate 与技术债；历史批次的过程和证据留在各自文档。

## 当前交付

[Career OS 结构优化与产品化重构](STRUCTURE-REFACTOR.md) B1—B5 已交付。当前应用以 Opportunity 与 Employment 为两条任务主干：

- Opportunity → Wiki 选材 / Context → 正式简历与 PDF → Submission → 研究、沟通、面试、Offer。
- Employment → Stage → Project → 参与者 / 事件 → Achievement → Evidence → 可确认的 Wiki 候选。

结构化编辑器是唯一可写简历链，旧文字简历只读兼容；状态驱动页面、基础资料、全局反馈和设置页案例装载/删除入口已接入。虚构案例 `career-os-b5-demo-v1` 已保留供用户熟悉，删除仅由用户主动触发。

基础资料支持姓名、邮箱、电话、微信、GitHub 与个人网页，并可同步到当前简历。人工事实闭环已经覆盖原件、候选、确认、修订、撤回、显式选材、预览、正式版本/PDF、投递冻结、原话更正和回流候选。真实 AI 语义质量仍受下述外部 Gate 限制。

## 现役入口与证据

- 启动、配置和模块说明：[服务 README](../../src/workbench/README.md)
- 当前架构和边界：[03-architecture](../03-architecture.md)
- 当前证据索引：[EVIDENCE](EVIDENCE.md)
- 当前最新交付批次：[STRUCTURE-REFACTOR](STRUCTURE-REFACTOR.md)
- 人工事实闭环：[FACT-LOOP](FACT-LOOP.md)

生产入口为 `http://127.0.0.1:8765`；默认数据目录为 `~/Library/Application Support/Career Data`。代码、测试资料和生产数据必须隔离。早期纯文本 MVP 契约已经撤回并归档，不再作为当前 Interface。

## 外部条件 Gate

当前没有已验证的真实 Provider 配置。缺少 `CAREER_AI_API_KEY` / `OPENAI_API_KEY` / `CAREER_AI_MODEL` 时，本地编辑、记录、版本与导出仍可使用，但岗位分析和简历适配的语义质量不能验收。TestProvider 或模拟 HTTP 成功不能代替真实模型调用。

模型、语音、招聘来源和其他外部能力均须逐项使用真实配置与隔离资料验证；不要把密钥发送到聊天，也不因外部能力缺失阻塞独立的本地闭环。

## 当前简化与技术债

- 文件解析、AI 候选提取、自动相关性排序、结构化简历内容 patch 和多 ResumeDocument 尚未完成。
- 细粒度研究快照、独立 JobPosting、EvidenceLink 页/行定位与 Repository Ingestion 仍待后续批次。
- 全局 epoch 采用保守失效；失败或中断的远端任务不自动收费重试。
- 数据量较小时 state 一次读取全部本地记录；有性能证据后再分页或引入索引。
- 备份仍以本地命令行为主，同盘备份不能防整盘损坏；schema 迁移必须先备份并显式按版本执行。
- 数据库登记前后的极端崩溃可能遗留无引用附件；不会形成假成功，但尚无自动孤儿回收。

## 历史交付

按时间保留：[任务工作台首试](TASK-WORKSPACE.md)、[单窗口工作区](FOCUSED-WORKSPACE.md)、[既有工作台本地接入](RESUME-WORKBENCH.md)、[职业 Wiki 与业务对象整合](WIKI-DOMAIN.md)、[冷启动整改](COLD-START-REPAIR.md)、[事实闭环整改](FACT-LOOP.md)。完整早期证据和已撤回的 MVP 契约位于 [archive](../archive/README.md)，仅用于追溯。

仓库记录过的本地提交基线为后端 `71776ce`、前端与验收 `9db7692`；这只说明历史基线，不代表当前工作树已提交、push、deploy 或 publish。
