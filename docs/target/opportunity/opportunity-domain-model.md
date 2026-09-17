# Opportunity Domain Model V1

## 0. 这份文档解决什么问题

这份文档把产品语言翻译成后端对象关系。

它重点回答：

- 哪些是真正的业务对象
- 谁拥有谁
- 谁是一对一 / 一对多
- 哪些只是前端展示，不要额外建第二份数据
- 哪些内容可以修改
- 哪些历史内容必须冻结

当前不要求数据库表名必须与本文完全一致。

Codex 审计现有项目时，应优先判断“业务语义是否一致”，而不是机械重命名。

---

# 1. Company

表示现实中的公司。

核心关系：

```text
Company 1:N Opportunity
```

用户输入公司名时：

```text
查找已有 Company
├── 找到 → 关联
└── 没找到 → 创建
```

目的：

- 同一公司的多个 Opportunity 可以复用 CompanyResearch
- 避免同一公司重复维护多套资料

---

# 2. Opportunity

表示：

> **一次具体求职尝试。**

核心字段概念：

```text
company_id
role_name
jd_text
action_url? optional
phase
result
created_on
```

其中：

```text
phase ∈ {写简历, 已投递, 面试, Offer}
result ∈ {active, accepted, rejected, withdrawn}
```

`已结束` 不作为 phase 存储。

它只是：

```text
result != active
```

的 View。

---

# 3. Research

后台暂定两层：

```text
Company
└── CompanyResearch

Opportunity
└── OpportunityResearch
```

前端合并展示为：

> 岗位情报

## CompanyResearch

适合保存可跨多个 Opportunity 复用的信息：

- 公司整体
- 产品 / 商业模式
- 公司级动态

## OpportunityResearch

保存与这次机会直接相关的信息：

- 岗位真实职责
- 业务信息
- 团队信息
- 招聘背景
- 当前岗位判断
- 未确认问题

暂不强制建立完整：

```text
Company → BusinessUnit → Department → Team
```

组织树。

如果未来同一组织单元被多个 Opportunity 反复引用，再评估升级成 OrgUnit Entity。

---

# 4. ResumeDocument

Opportunity 不一定需要简历。

关系：

```text
Opportunity 1:0..1 ResumeDocument
```

第一次真正开始加工简历时才创建。

ResumeDocument 保存：

> 当前正在编辑的简历内容。

当前编辑内容可以自动持久化，但不会自动制造版本历史。

---

# 5. ResumeVersion

关系：

```text
ResumeDocument 1:N ResumeVersion
```

普通 ResumeVersion 只有在用户主动：

```text
[保存版本]
```

时产生。

投递时，无论当前内容是否手动保存过，系统都自动生成一个特殊的投递版本。

投递版本：

- 默认保存
- 不可修改
- 绑定对应 Opportunity / Submission
- 在 Resume Workspace 历史版本中可查看

---

# 6. GreetingMessage

属于投递前准备。

可以：

- 手动编辑
- AI辅助

投递前可修改。

真正投递后，对应内容冻结为 Submission 的 Greeting Snapshot。

---

# 7. Submission

关系：

```text
Opportunity 1:0..1 Submission
```

当前规则：

> 一个 Opportunity 只对应一次正式 Submission。

如果未来同一岗位重新尝试，创建新的 Opportunity。

Submission 主要保存：

```text
submitted_on
submitted_resume_snapshot? optional
submitted_greeting_snapshot
```

Submission 不承担渠道、备注等重复信息录入。

它的核心意义是：

> **冻结“我当时到底发了什么”。**

历史 Submission 内容不可修改。

---

# 8. CommunicationEvent

关系：

```text
Opportunity 1:N CommunicationEvent
```

统一表达：

- 线上聊天
- 电话沟通
- Offer 谈薪沟通

可以使用类似：

```text
type = text | phone | other
purpose = general | negotiation
```

具体字段以后由现有代码和真实使用情况决定。

不为电话和线上聊天建立两套业务系统。

---

# 9. InterviewSession

关系：

```text
Opportunity 1:N InterviewSession
```

InterviewSession 有：

```text
type = real | simulation
```

## real

表示真实正式面试。

最低信息：

```text
name
date
```

例如：

```text
业务一面
2026-09-20
```

## simulation

表示模拟面试。

模拟面试必须绑定一个目标真实面试：

```text
target_real_interview_id
```

因此概念上：

```text
Real Interview 1:N Simulation Interview
```

例如：

```text
业务一面
├── 模拟1
└── 模拟2
```

模拟和真实 InterviewSession 共享：

- Raw Transcript
- Final Review
- PatchProposal 处理流程

---

# 10. Interview Raw

当前 MVP 长期保存：

> 带时间戳的文本 Transcript。

Career 不要求长期保存 audio。

例如：

```text
[00:00:03] 面试官：……
[00:00:12] 我：……
```

Raw 可被用户直接修正。

用户确认后的修正版直接覆盖当前 Raw，不保留旧 Raw 修订历史。

这是当前单用户本地系统为了降低复杂度作出的取舍。

---

# 11. Final Review

InterviewSession 可拥有一份当前 Final Review。

内容结构：

1. 本轮结论
2. 关键问答
3. 跨问题模式
4. 新信息发现
5. 下一轮建议

AI 先生成。

用户可直接编辑最终结果。

不额外保存：

```text
AI 原始复盘
+
用户修订版
```

两套版本。

Raw 是事实来源，Final Review 是当前有效复盘。

---

# 12. Offer

关系：

```text
Opportunity 1:0..1 Offer
```

Offer 表示当前 Opportunity 的 Offer 阶段核心对象。

包含：

- 当前 Offer 信息
- 相关 Raw
- AI分析结果
- 谈薪沟通
- 最终决定

当前 MVP 不强制保存每一次 Offer 条件版本。

谈薪继续复用 CommunicationEvent：

```text
purpose = negotiation
```

---

# 13. RawSource

RawSource 是统一资料入口的基础对象。

可以关联：

- Opportunity
- CommunicationEvent
- InterviewSession
- Offer
- 未来 Project / Employment 等

核心原则：

> Raw 是证据和原始依据，不等于正式 Career Context。

例如：

```text
HR聊天
面试Transcript
Offer文本
JD
```

进入系统后先作为 RawSource。

Raw 默认不被所有 AI 请求直接读取。

---

# 14. PatchProposal

当前将：

```text
Candidate
+
Patch
```

合并成一个概念：

> `PatchProposal`

流程：

```text
RawSource
↓
对应 Domain Skill
↓
PatchProposal
↓
用户：
编辑 / 接受 / 拒绝
↓
接受后立即 Apply
↓
正式对象更新
```

AI 不能直接修改正式业务事实。

用户确认是最高决策层。

---

# 15. Timeline 不是 Entity

Timeline 不应该拥有第二份求职事实。

它从真实对象派生：

```text
Opportunity.created_on
Submission
CommunicationEvent
InterviewSession
Offer
Opportunity.result
```

然后：

```text
按时间排序
↓
生成摘要
↓
点击进入真实对象
```

因此：

> Timeline = Derived View / Projection

不是第二套 Event 数据库。

---

# 16. 当前阶段日期

Opportunity 表格会显示：

> 进入当前 phase 的日期。

产品意义是：

```text
我从哪一天开始进入当前阶段？
```

细颗粒度日期仍属于具体对象：

- Submission 日期
- InterviewSession 日期
- Communication 日期
- Offer 日期

Codex 在实现时可以：

- 从真实对象推导
- 或为了查询方便缓存 `phase_changed_on`

但不能形成互相矛盾的两套事实源。

---

# 17. 当前核心关系表

| 父对象 | 关系 | 子对象 |
|---|---:|---|
| Company | 1:N | Opportunity |
| Opportunity | 1:0..1 | ResumeDocument |
| ResumeDocument | 1:N | ResumeVersion |
| Opportunity | 1:0..1 | Submission |
| Opportunity | 1:N | CommunicationEvent |
| Opportunity | 1:N | InterviewSession |
| Real InterviewSession | 1:N | Simulation InterviewSession |
| Opportunity | 1:0..1 | Offer |
| Company | 1:1 当前档案 | CompanyResearch |
| Opportunity | 1:1 当前档案 | OpportunityResearch |
| RawSource | 1:N | PatchProposal |

这些是当前业务语义，不要求数据库一定完全按表实现。

---

# 18. 可修改 vs 不可修改

## 可修改

- Opportunity 当前信息
- JD 当前内容
- Research 当前档案
- ResumeDocument 当前编辑内容
- 普通 Career Context
- Raw 修正版
- Final Review

## 历史发生后不可修改

- Submission 实际投递快照
- 投递 ResumeVersion
- 投递 Greeting Snapshot
- 已发生现实沟通的原始记录，除非属于用户明确修正 Raw
- Offer 原始材料本身

当前原则：

> 现实发生过的“当时版本”要保留；
> 当前认知可以继续修正。

---

# 19. Employment 的边界

本周期不深度设计 Employment。

明确一点即可：

> Offer accepted 不自动创建 Employment。

Employment 未来由用户自主：

- 创建
- 编辑
- 删除

以后最多提供：

> 从 Opportunity 带入部分基础信息

作为便捷填充。

它不是 Opportunity 生命周期的强制子对象。

---

# 20. 长尾异常处理原则

不试图提前覆盖所有现实异常。

统一判断：

```text
异常出现
↓
当前对象能表达？
├── 能 → 用当前对象处理
└── 不能
     ↓
   是否形成一次新的独立现实关系？
   ├── 是 → 新建对应对象
   └── 否 → 用户手动修正
```

只有同一种异常反复出现，才升级领域模型。

---

# 你怎么看这份文档

不要先想数据库表。

只检查：

> **现实世界里的对象关系有没有说反。**

例如：

- Opportunity 能不能有多个 Submission？
- 模拟面试是不是必须绑定真实面试？
- 投递版本到底该不该修改？

# 你怎么用

Codex AS-IS 审计完成后，用这份文档做 Gap Analysis：

> 当前代码里的对象，和这里的业务对象分别是什么关系？

重点发现：

- 一个旧对象承担多个职责
- 同一事实被重复保存
- 前端状态代替了真正后端状态

# 你怎么给我反馈

最适合这样反馈：

> 第 7 节 Submission：我觉得 0..1 不对，因为……
>
> 第 15 节 Timeline：这里我理解了 / 这里我觉得还需要……
>
> 第 18 节：这个数据我认为应该允许修改。

看不懂任何关系，直接指出编号即可。
