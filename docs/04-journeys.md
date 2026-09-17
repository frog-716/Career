# 用户场景与状态变化

按[authority](00-authority.md)区分模块。本页Opportunity场景是**target journey，尚未整体实现/验收**；动作细则以[UI Flow](target/opportunity/opportunity-ui-flow.md)、[Product Model](target/opportunity/opportunity-product-model.md)、[Domain Model](target/opportunity/opportunity-domain-model.md)和[Context & Ingestion](target/opportunity/context-ingestion.md)为准。现状证据见[AS-IS](audit/AS-IS-system-map.md)，实施状态见[STATUS](execution/STATUS.md)。

## Opportunity主链 — Target

创建Opportunity → 投递准备 → 记录已投递 → 招聘沟通 → 确认真实面试 → 每轮准备 / 模拟 / 真实 / 复盘 → Offer / 谈薪 → accepted / rejected / withdrawn。

这是正常主路径，不强制逐步完成。可以无简历投递、先聊后投或直接确认面试；同一岗位重新尝试创建新的Opportunity。长尾补录/更正不自动伪造一次现实活动或随意重置阶段。

| 步骤 | 输入 | 用户动作 | 产出 | 状态变化 |
| --- | --- | --- | --- | --- |
| 创建Opportunity | 公司、岗位、JD、可选外部链接 | 添加机会；公司主体有歧义时明确选择 | 复用/创建Company，新增一次求职尝试，管线新增一行 | phase=写简历，result=active；阶段日期为创建日 |
| 投递准备：简历 | 选定/导入的简历来源及当前资料 | 首次打开并选择来源，编辑内容/排版；按需请求AI；主动保存版本 | 每机会最多一份独立ResumeDocument；普通编辑保存当前值，主动保存才建普通版本 | phase不因改稿、保存或AI分析变化；简历可跳过 |
| 投递准备：Greeting | 当前机会及用户表达 | 手动编辑或采用AI建议 | 当前可编辑Greeting | 不新增阶段 |
| 记录已投递 | 现实已发送；选择当前稿/已存版本/本次无简历，当前Greeting | 点击记录已投递 | 唯一Submission，自动记录今天；冻结Greeting和实际简历；有简历时无论是否已存普通版都生成特殊投递版 | phase→已投递；不要求再次填日期、渠道或备注；失败不能半成功 |
| 招聘沟通 | 线上聊天、电话文字或转写 | 添加线上沟通 / 记录电话沟通 | CommunicationEvent＋Raw；Skill可提出Research/安排等目标分组Patch | 沟通不自动切阶段；接受有效面试安排才进入确认动作 |
| 确认真实面试 | 已确认安排、轮次名称、实际面试日期 | 创建real InterviewSession | 属于当前机会的真实轮次及确认时间 | 确认当天phase→面试，不等面试完成；面试日期与确认日分开 |
| 每轮准备 | JD、实际投递简历、Research、HR沟通、此前真实轮次当前复盘 | 准备这一轮 | 该real轮次的Preparation / Context Pack；缺材料明确说明 | 不新增phase；无投递简历不得替换成最新工作稿 |
| 模拟 | 已存在的同机会目标real轮次及Pack | 开始模拟；复制到全新ChatGPT对话语音练习；自行录音/转写后上传文本 | simulation Session绑定target_real_interview_id；Transcript及后处理 | phase仍为面试；模拟AI面试官虚构信息不能成为现实事实 |
| 真实面试与复盘 | 本轮带时间戳Transcript；不要求长期保存audio | 上传/更正文字稿；运行复盘、编辑终版、审阅信息Patch | 当前Raw＋五项FinalReview＋目标分组Patch；用户确认后正式对象更新 | 不把创建轮次当已完成；Raw修正覆盖当前正文、无旧Raw历史；无长期AI原版复盘副本 |
| 下一轮 | 新的已确认轮次名称/日期 | 添加real轮次，重复准备/模拟/复盘 | 同机会多轮，各有准备、Raw和FinalReview | Opportunity仍是面试，不新增一面/二面phase；工作区显示最新待进行real |
| Offer | 现实收到的条款与原材料 | 记录/更新Offer；按需分析 | 唯一当前Offer；条件可更新，原始材料不改 | 首次收到phase→Offer |
| 谈薪 | 当前Offer、个人底线、实际条件沟通 | 添加谈薪沟通、更新当前条件 | CommunicationEvent，purpose=negotiation；关联Raw/提案 | 仍为Offer，不单建Negotiation系统 |
| 结束 | 招聘方终止 / 用户退出 / 接受Offer的明确决定 | rejected / withdrawn / accepted | 当前result与结束活动，可回看冻结材料 | rejected/withdrawn可在任意阶段；accepted仅Offer；result!=active进入已结束View，保留最后phase，不自动创建Employment |

FinalReview固定关注本轮结论、关键问答、跨问题模式、新信息发现、下一轮建议。用户可以编辑终版，AI输出不是自动确认的个人或公司事实。模拟用户明确补充的个人信息可形成Career Patch；真实面试官透露的岗位/团队信息可形成OpportunityResearch Patch，均须确认。

## 岗位情报、资料确认与历史回看 — Target

| 输入 | 用户动作 | 产出 | 状态变化 |
| --- | --- | --- | --- |
| JD、指定Web材料、HR沟通、电话、真实面试、Offer或手动内容 | 在业务页面添加材料 / 编辑情报 / 接受目标Patch | CompanyResearch与OpportunityResearch当前档案；前端统一“岗位情报”，保留来源和owner | 情报本身不改变phase/result；不能把机会信息未经确认提升为公司共享结论 |
| AI从Raw发现的信息 | 按目标分组编辑/接受/拒绝 | 接受即Apply到正式对象；拒绝不写；手动正式编辑直接保存 | revision/CAS/stale按Context合同执行，不增加第二个“应用”按钮 |
| Opportunity与其Submission/沟通/面试/Offer/result | 查看Timeline，点条目回到源对象 | 聚合、摘要、时间排序与跳转 | 不建立第二套事实，不记录字号/普通保存/AI重跑/Patch接受 |
| 已投递材料 | 查看当时简历/Greeting/日期、下载原PDF | 冻结历史；完整简历版本列表在Resume Workspace | 当前稿、JD、Research、事实修改均不覆盖历史投递 |

AI按具体任务出现，手动闭环可独立验收，mock不能证明真实模型质量。没有网络/解析器/模型时明确能力边界，不能把指针登记、手动原话或固定模板标为已完成自动研究/复盘。

## 非本期场景

自动搜岗、平台采集、全局Inbox、内置连续语音及多Offer比较不作为本期主链前置要求，见[Roadmap](07-roadmap.md)。下面保留既有任职场景，不代表本批实现，也不触发Employment/Project/People重构。

## 入职、协作与阶段总结

每份工作一张独立卡片：角色与时间、阶段、正在做的事、协作人、成果。任职、兼职、个人项目允许时间重叠，也可在职求职。

记事可只写一句或导入聊天/交接，AI整理目标、约束、动作、结果与问题。以真实事项推动“提出假设→行动实验→观察结果→阶段总结”，不强制每天写日报。

协作档案保存职责、决策权、明确目标、承诺、沟通偏好和具体互动。解释必须列支持、反证和未知；不把感受或一次冲突变成对人格/真实动机的确定判断。

阶段文档按项目结束/角色变化/交接形成，可人工修改当前版并留历史；新增经历确认后才成为下次简历素材。任职事实与离职后重建项目区分。受限公司材料按授权范围脱敏/引用，不默认发送远端。
