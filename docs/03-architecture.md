# 工程起点与扩展方式

这是Astra可调整的工程方案；产品不变量以 [上下文契约](02-context-contract.md) 为准。

## 技术路线

单体本地后端（优先Python，复用SQLite经验）、TypeScript任务前端、SQLite、附件目录。前端可采用React等成熟方式，主控在首批固定工具链与版本。语音/本地模型可作为独立受控进程。暂不引入微服务、图数据库、向量库优先架构。

建议 `workspace.sqlite3` 存当前资料、来源、事件、任务与已确认结果；`analysis.sqlite3` 存运行审计与提案。分析只收ContextPacket。跨库应用时，把修改及appliedProposalId写在workspace同一事务，analysis状态可对账重建，防止重复更新。

关键数据关系结构化；可变分析内容使用带schemaVersion的JSON。不为每个UI页造表，也不把所有约束藏进万能JSON。

## 数据对象

| 对象 | 职责 |
| --- | --- |
| ContextEntry / Revision / SourceArtifact | 当前资料、修订、不可变原件与来源 |
| CareerEpisode / WorkItem | 独立工作期、目标、事项与行动 |
| Opportunity | 目标岗位/JD；不是已投递 |
| ResumeDocument | 可编辑、自动保存工作稿；不是事实正本 |
| ResumeVersion | 显式保存的不可变快照；可无岗位或关联一个岗位；parentVersionId可空 |
| Application | 显式记录的实际投递；关联岗位、已有版本、时间和状态；同岗位/版本可多次使用 |
| EvidenceRef | 经历到来源的引用；旧简历只能作定位线索，不能自证 |
| WorkbenchRecoveryPoint | 草稿/导入/恢复备份；不混入正式版本历史 |
| Communication / InterviewSession / Offer | 对应实际沟通、面试、条款事件 |
| Review / Practice / LearningAction | 派生复盘、练习与后续行动 |
| CollaborationRecord / StageDocument | 工作范围内的协作观察和阶段记录 |
| AnalysisRun / Proposal | 输入清单、策略/模型版本、结果状态、待确认差异 |

稳定经历ID仅承诺同工作稿lineage派生中保留；重新导入不同文件不自动判断同一经历。没有claim graph或全局识别要求。

## 深模块

Module是通过小Interface提供丰富行为的封装；Interface包含调用、前提、错误、并发及副作用，不只是函数签名。Seam放在真实可变处；Adapter实现供应方差异。以下Interface是设计示例，非必须逐字实现。

| Module | Interface | 隐藏的复杂性 |
| --- | --- | --- |
| Context | readCurrent / applyChange / getTaskSources | revision、来源、冲突、范围、摘要失效 |
| Artifacts | ingest / read / export / backup | 格式解析、文件哈希、原件、附件一致性 |
| Journey | getCurrentTask / executeAction | 允许跳步和回退的流程、引用、事务、幂等 |
| Analysis | run / cancel / propose | 选材、模型、校验、过期判定 |
| Resume | openDraft / applyProposal / saveVersion / export | 编辑、稳定ID、PDF、版本与恢复 |
| Conversation | start / submitTurn / finish | 文本/语音、轮次、追问、转写、复盘 |
| Integrations | searchJobs / researchCompany / importSource | 平台差异、错误、限流、采集时间 |

工作记录先作为Journey/Context中的场景；有独立复杂性后再拆。删除某模块后若复杂性会回到多个调用者，说明它有价值；若只是转发包装可合并。不要机械按表建立Controller/Service/Repository三层。

## 目录建议（在实施时创建，不是包内已有应用）

```text
frontend/                    任务页面、资料编辑、简历、对话
src/workbench/               深模块实现
tests/                       Interface测试、HTTP/SQLite与浏览器验收
docs/                        本包规范，模块文档及execution状态
.agents/skills/              按任务读取的开发技能
用户选择的数据目录/          workspace.sqlite3、analysis.sqlite3、artifacts、backups
```

代码与用户数据分离；数据不在静态根目录、不进Git。手动资料编辑经页面落库；若支持外部Markdown，使用导入差异协议，避免两个正本。

## 本地运行与可靠性

- 启动器检测服务/端口并打开HTTP地址；已有服务则复用。浏览器file地址不是应用入口。
- 自动保存草稿，后台任务持久化为queued/running/succeeded/failed/cancelled/stale；进程重启可恢复。模型调用不持有长事务。
- 请求有幂等键；远端模型重试可能再次计费，不承诺外部exactly-once。
- 文件先临时写、哈希、原子改名，再登记引用；失败不显示“已完整保存”。无引用残留可延迟回收。
- 数据库一致性备份+不可变附件清单，实际恢复验证；单盘备份不能抵御整盘损坏。
- 锁定依赖、字体本地化、版本化migration，升级前备份；回滚匹配代码和数据版本。
- 本地监听回环地址，限制Origin/会话和可读文件范围；密钥只在服务端配置。远端发送范围遵循上下文契约。
- 开发Agent使用隔离数据；有终端权限的Agent不能仅靠提示词与真实文件隔离，需要环境权限保证。

## 扩展

新能力沿“任务输入→选材策略→提案→用户动作→持久化结果”加入。模型/语音/外部数据接入是合理Seam；没有第二种实际需求的普通功能不预造Adapter平台。未来同步不影响现在的稳定ID设计，但当前不写同步实现。

## MVP 已固定实现

Python 3.9+ / FastAPI，TypeScript + Vite，单进程模块化单体。SQLite 单文件以 current/revisions/records/applications 隔离用途，Context 入口仅读 current 白名单；选择单库使提案应用和幂等状态同事务，避免双库对账。schema 使用 PRAGMA user_version=1，后续迁移需先备份、显式版本迁移，拒绝打开更高版本。资料当前按一份自由文本保存，连同目标 JD 形成最小 Context，用户自行维护相关事实、硬约束和反证；不预建经历检索系统。

生产默认 `~/Library/Application Support/CareerOS`，可用 CAREER_DATA_DIR 指定代码外位置。服务入口 `scripts/run.py`；接口与运行命令见 `src/workbench/README.md` 与 `frontend/README.md`。远端接口为无会话 Chat Completions Provider，实际 JSON payload 本地审计；测试模式必须显式配置。运行时密钥仅环境变量。
