# Context Contract

本合同按[authority](00-authority.md)解释。长期对象与跨模块语义以[长期 Career 模型](target/long-term-career-model.md)为准；Opportunity内任务以[Context & Ingestion](target/opportunity/context-ingestion.md)及[Domain Model](target/opportunity/opportunity-domain-model.md)为准。下文把目标转成读取、确认和并发合同，不声称目标已经实现。

## Current implementation — 审计基线

以下来自2026-09-17 [AS-IS §8–11](audit/AS-IS-system-map.md)，本次文档对齐没有重新执行业务验收。

| 已实现机制 | 当前限制 / 与目标的差距 |
| --- | --- |
| ContextCompiler在同一Store事务读取当前资料、revision/hash和epoch；Provider只接收构造好的payload | 编译策略只有job与旧resume，现役HTTP仅开放job分析；没有各领域Skill注册合同 |
| 正常分析读profile、当前JD、选定active Wiki及强制个人goal/constraint | 关联Company/OrgUnit/TargetRole/SearchCycle的name/description仍自动进入packet；**不符合下文目标的显式任务读取规则** |
| 普通新请求不读旧聊天、revisions、Raw、旧run和Feedback；无隐式远端Session | 用户粘入当前资料的旧说法仍可能进入包；这不是语义去污染保证 |
| Raw / candidate / Wiki按kind分开；人工候选确认创建Wiki；Wiki修改/CAS/epoch失效 | 现有Raw不可变、note更正保留历史；Candidate尚不能统一更新Research/Interview等领域对象 |
| 分析结果保存为run，旧文字提案有内部兼容方法；现役接口不自动写正式事实 | 结构化简历AI patch、Interview/Research/Offer任务尚未接入 |
| Wiki选材限制30条、正文100k；run保存packet/payload/result | 不是全包预算；新Raw覆盖政策和分析留存策略尚未落地 |
| profile保存会同步唯一editor-main的身份区；Wiki选材保留source_refs | 多机会独立工作稿尚未实现；不能据此对所有未来文档自动覆盖身份表达 |

2026-09-17审计快照中的真实 Provider 未验收、两项 profile/editor 测试失败等结论只描述当日证据，不代表当前。当前测试、运行与验收状态以 [STATUS](execution/STATUS.md) 为准；不能把合同要求当作现有机制的证明。

## Target contract — 资料与正式对象

```text
明确业务入口 → RawSource → Domain Skill → PatchProposal
→ 用户编辑 / 接受 / 拒绝 → 接受后立即Apply → Domain Object
→ ContextCompiler后续读取当前结果
```

原始材料是证据，当前认知由所属正式对象拥有，AI分析是建议。Career Context中的个人Wiki/profile继续承担已允许的个人事实与身份；Research、Interview及其他业务对象不全部复制进Wiki。Candidate与Patch统一为PatchProposal概念和交互，不要求机械合并表或丢弃旧ID。

用户直接手动编辑正式资料，按受控接口保存即可；**AI提出的正式事实变更必须经用户确认**，不能因为指令看似明确或已有对象关联就由Skill直接写库。用户确认与独立材料核验分开；编辑后的内容不能沿用旧核验结论。

资料从沟通、面试、Offer等明确业务页面进入统一Ingestion边界，入口携带目标对象，不新增全局Inbox或万能资料Prompt。来源URL、目录或Git指针不是读取授权，也不意味着系统已经抓取正文。

### Current / Raw / 冻结材料的留存

| 内容 | 目标写入与读取合同 |
| --- | --- |
| 当前个人事实、Research、业务对象 | 经手动编辑或已确认Patch更新；分析读当前有效值。事实撤回/变更使相关依赖失效 |
| 新求职Raw / Transcript | 用户确认修正版覆盖当前正文，不保留旧Raw正文修订历史；仍有revision/hash用于CAS、来源与stale判断 |
| FinalReview | 一份可编辑当前终版；不另长期保留AI原始复盘和用户终版两套正本。它是复盘，不自证为CareerFact |
| Submission、投递ResumeVersion、Greeting Snapshot、原PDF | 保留实际当时材料，当前事实/JD/工作稿/Research修改不得覆盖 |
| Offer原始材料 | 原件本身不可改；当前Offer条件可以更新。不能用通用Raw更正入口改写该原件 |
| 历史库中的Raw、revisions、版本、run与附件 | 迁移保护并保持可追溯；新留存政策不授权清理旧用户数据 |
| Employment / Project记录 | 现行原话与更正历史是实现现状；新目标按长期 Career 模型统一 Raw、Domain Object 与 Wiki 的边界，不把旧schema当目标 |

覆盖当前Raw不等于降低revision。新写路径不得借通用revisions、run、proposal.before、日志或缓存暗中永久保存被替换Raw全文。备份是隔离恢复用途，不得作为正常分析的旧正文库。具体留存实现可参考[Gap Analysis §6–7](audit/OPPORTUNITY-GAP-ANALYSIS.md)，必须在实际写路径验收。

## Target contract — 每个Skill显式声明

这里的Domain Skill是产品内AI任务策略，不是`.agents/skills/`中的开发方法技能。每个任务须先声明下列合同，再接入模型：

| 声明 | 要求 |
| --- | --- |
| `task_type` / `target_object` / `skill_version` | 固定任务身份、所属对象与策略版本 |
| `required_context` | 必需来源、用途、字段及缺失处理；不能默默用其他对象代替 |
| `optional_context` | 可选来源与触发条件，必要时回到明确指定Raw核验 |
| `forbidden_context` | 排除的范围、对象、历史、来源角色及未确认材料 |
| `output schema` | 结构化输出、来源引用、事实/推断/建议/Unknown区分；声明哪些只是分析、哪些形成Patch |
| `allowed patch targets` | 可修改的对象与字段白名单；只能调用所属Domain Action |
| `confirmation requirement` | 正式事实Patch须用户确认；逐条接受/编辑后接受后立即应用，拒绝不写事实，无第二次Apply或批量接受。Person身份映射、创建及重要人物知识写入须由用户确认；已确认身份后，明确要求/承诺作为普通逐条Patch，不再重复确认身份 |
| `budget` | 最终请求的总预算、来源配额及超限行为；required约束和反证不足时提示/缩小任务，不静默截断 |

Skill统一通过`ContextCompiler.prepare(task_type, target_object, user_request)`或等价受控接口取材料，不持有Store/SQL，也不能按对象关系递归展开全部description/context。Company身份字段仅在任务声明需要时作为背景；目录description不是CompanyResearch。Research必须读取对应当前档案并标明所有者和来源，不再用“相关目录已关联”替代授权。

### 任务选材边界

| 任务 | 允许的相关输入 | 关键限制 |
| --- | --- | --- |
| Resume / Greeting | 当前Opportunity/JD、相关Career Context、Research、目标当前稿/招呼语 | 不读其他机会工作稿或全部旧版本。Resume AI DTO 对Profile只发送“区存在”和字段名，剔除Profile区内容，不发送姓名、电话、微信、邮箱值；未来任务另行定义最小授权字段 |
| Research / Communication ingestion | 本次指定Raw、所属机会、相关当前Research | 不自动把机会材料提升成公司级结论；范围变化需明确目标和确认 |
| Interview准备 / Simulation Pack | 目标real轮次、JD、实际投递简历、Research、HR沟通、此前真实轮次的当前复盘 | 没有投递简历须明确缺失，不能用最新工作稿替代；不全量读取旧面试Raw |
| Interview复盘 | 本轮当前Transcript、real/simulation来源及目标轮次、相关背景 | 模拟AI面试官的虚构信息不具备现实事实资格；用户自述可提个人Patch；真实面试官信息可提机会研究Patch |
| Offer | 当前条件、指定原件、相关个人约束及谈薪沟通 | 不扩展到多Offer Comparison，不自动建Employment |

Opportunity / Resume / Interview经Career Context Interface取得任务允许的职业资料。Employment、Project、Person是当前目标模型的一部分，其内部对象不因此被整库暴露。任职私聊、他人档案不因同一窗口或同一用户而进入求职Context；反馈与Career Wiki、Research、Resume、Interview完全隔离。

## 每次请求、确认与并发

1. 明确任务、目标对象、当前指令与Skill策略；先完成范围/权限过滤，再取当前目标/硬约束、相关事实、当前领域结论及必要证据。
2. 在短事务内回正本读当前revision/hash和epoch，构造带来源用途的packet；模型调用不占用长事务。
3. 用户可检查本次材料及遗漏；远端发送范围须明确。新请求从packet重建，不继承旧助手消息、旧revision、失效摘要、开发Agent聊天、日志或备份。
4. Provider只收到构造好的请求及配置，不能取得Store/SQL、任意文件或事实写入权限。JD/聊天中的指令是输入数据，不授予工具权限。
5. 校验输出schema、允许引用、目标字段及事实/推断边界。合法来源ID只证明可追溯，不证明每句结论受来源支持。
6. 返回与接受Patch前重新检查目标/来源revision；已变化则stale，禁止直接覆盖当前值。CAS冲突保留用户输入并展示差异；幂等重试不重复创建事实或再次应用提案。
7. 用户对同一目标的一组Patch编辑/接受后，由Domain Action验证并原子应用；正式对象更新与提案applied状态同事务。Raw更正也使依赖旧内容的提案失效。

允许先用全局epoch做保守失效；不能宣称运行中的模型已即时换用新资料。“继续讨论”只带仍有效的任务指令或明确标为proposal用途的材料，不复制整段旧答案。缓存与索引只回候选ID，回正本读当前值；没有实现索引时不声称已具备语义检索。

## ContextSnapshot与证据边界

重要分析记录task_type、target_object、使用的对象ID/revision/hash及用途、context_snapshot_id、generated_at、skill_version和Provider标识。留存应服从Raw/FinalReview政策；不能为可追溯而暗存被禁止的旧全文副本。Raw已覆盖后，来源元信息可追溯，但若未保留正文，不能保证重建当时完整输入。

实际请求范围在隔离验收时捕获payload验证，不能只看最终回答有没有提到旧事实。真实Provider质量与mock契约测试分别记录；模型幻觉、相关性和来源语义支持仍需审阅。验收见[05-acceptance](05-acceptance.md)的Context及Opportunity目标条目。

## 简历来源与非本期兼容

`meta.source_refs`记录选材来源及revision/hash，是表达追溯而非第二份CareerFact。Profile 是姓名、联系方式和个人网页的基础资料正本：新工作稿带入最新资料；保存基础资料时，所有当前 ResumeDocument 自动更新受管理的身份/联系方式区及 profile 来源 revision。它不改经历、技能、排版或其他简历表达，并以工作稿 revision/CAS 保护并发编辑。普通 ResumeVersion、投递版本、Submission 快照和 PDF 保持当时内容，不随 Profile 改动。Wiki事实仍按当前目标显式选择，普通编辑不倒写CareerFact。

旧混合profile的历史内容不因新目标而自动拆分或删除。Profile保存后同步当前ResumeDocument身份区是当前用户确认的工作稿行为，和AI发送范围是两件事：Resume AI 默认只能知道Profile区是否存在及字段是否存在，不能读取这些字段值。任职人物身份、Person创建与重要知识写入按长期 Career 模型由用户确认；其它跨模块读取按任务授权与来源范围执行。
