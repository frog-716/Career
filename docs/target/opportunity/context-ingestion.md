# Context & Ingestion V1

## 0. 核心目标

这套系统解决：

> **Career 保存了很多资料，但 AI 每一次只读取当前任务真正需要的信息。**

核心原则：

> **“系统存了什么”与“AI 这一次看什么”彻底分离。**

统一资料链：

```text
明确业务入口
↓
RawSource
↓
对应 Domain Skill
↓
PatchProposal
↓
用户编辑 / 接受 / 拒绝
↓
立即更新正式业务对象
↓
ContextCompiler 后续读取更新后的结果
```

---

# 1. RawSource 是什么

RawSource 是用户导入 Career 的原始依据。

例如：

- JD
- HR聊天
- 电话沟通转写
- 模拟面试 Transcript
- 真实面试 Transcript
- Offer 文本
- PDF
- 项目资料
- 手工文本

RawSource 的核心作用：

> **需要时能够回看原始依据。**

---

# 2. 前端可以有很多上传入口

例如：

```text
Opportunity
[添加资料]

沟通
[粘贴聊天]

面试
[上传文字稿]

Offer
[上传Offer]
```

这些前端入口不同。

后端统一进入同一个：

```text
IngestionService
```

区别在于前端已经告诉系统：

- 当前属于什么业务场景
- 当前关联哪个对象

用户无需每次再手工分类。

---

# 3. MVP 不做全局智能 Inbox

当前所有资料从明确业务页面进入。

例如：

```text
InterviewSession
→ 上传 Transcript

CommunicationEvent
→ 粘贴聊天
```

以后真实使用发现大量：

> “我手里有资料，但不知道该放哪里”

再增加全局 Inbox。

---

# 4. Raw 不等于 AI 上下文

非常重要：

```text
上传 HR聊天
≠
以后所有 AI 请求都读取整段聊天
```

Raw 默认只作为证据存在。

平常 AI 优先读取整理后的：

- Career Context
- Research
- Final Review
- 当前业务对象

只有需要核验细节时才回 Raw。

结果：

> Raw 可以越来越厚，但工作上下文不会无限膨胀。

---

# 5. Raw 可以修正

例如 Transcript 写：

```text
提升30%
```

实际：

```text
提升13%
```

用户可以直接修改 Raw。

当前规则：

> 用户最终确认版本覆盖当前 Raw。

MVP 不保留 Raw 的旧修订历史。

这是为了降低个人本地系统的维护复杂度。

---

# 6. Raw 进入不同 Domain Skill

统一的是资料生命周期。

业务理解仍由对应 Skill 负责。

例如：

```text
HR Chat
↓
Communication Skill
```

```text
Interview Transcript
↓
Interview Skill
```

```text
Offer
↓
Offer Skill
```

```text
Research Web Result
↓
Research Skill
```

不要建立一个“万能资料 Prompt”。

---

# 7. PatchProposal

当前将：

```text
Candidate
+
Patch
```

合并成：

> **PatchProposal**

表示：

> AI 从 Raw 或分析中发现某些信息，并建议怎样更新当前正式业务对象。

例如：

```text
Raw：
HR聊天

发现：
团队 = AI商业化
```

对应：

```text
PatchProposal

target:
OpportunityResearch

change:
团队：未知 → AI商业化
```

---

# 8. Patch 前端按目标对象聚合

不要一次弹 20 个确认框。

例如：

```text
本次发现：

岗位情报 · 3项
[查看]

业务一面 · 2项
[查看]

个人资料 · 1项
[查看]
```

用户进入某组后：

- 编辑
- 接受
- 忽略
- 全部接受

底层可以细粒度保存。

前端按业务对象聚合。

---

# 9. 用户确认后立即 Apply

流程：

```text
AI 生成 PatchProposal
↓
用户编辑 / 接受
↓
立即 Apply
↓
正式对象更新
```

不增加：

> “确认以后还需要第二次点击应用”

这种额外流程。

---

# 10. 用户自己编辑正式资料

用户直接手动修改正式资料时：

```text
用户编辑
↓
直接保存
```

不需要再走：

```text
Candidate
→ Patch
→ 再确认
```

AI 提议才需要 PatchProposal。

---

# 11. ContextCompiler

所有重要 AI Skill 不应该自己随意扫描数据库。

统一经过：

```text
ContextCompiler.prepare(
  task_type,
  target_object,
  user_request
)
```

例如 Resume Skill：

```text
Opportunity
+
JD
+
相关Career Context
+
Research
+
当前Resume
```

例如 Interview Preparation：

```text
JD
+
实际投递简历
+
Research
+
HR沟通
+
此前真实面试复盘
```

---

# 12. ContextSnapshot

重要 AI 分析建议记录：

```text
task_type
target_object
使用的对象
对象当前 revision
context_snapshot_id
generated_at
skill_version
```

目的：

> 后续能知道“AI 当时究竟看了什么”。

---

# 13. AI 不直接写正式事实

禁止：

```text
AI推测
↓
直接写正式Career数据
```

正确：

```text
AI
↓
PatchProposal
↓
用户确认
↓
正式数据
```

避免：

```text
AI自己猜
→ AI自己写
→ 下次AI自己读
→ 错误不断自我强化
```

---

# 14. 用户是最高决策层

如果 AI 发现一个 Career Context 中没有的新事实：

用户可以：

```text
[确认]
[修改后确认]
[拒绝]
```

用户确认后，即可作为当前系统的正式认知。

系统不强制用户同步修改所有相关旧内容。

如果以后出现冲突，可以提示，但不能擅自覆盖。

---

# 15. Research 的资料回流

Research Profile 的信息来源可能包括：

- JD
- Web Research
- HR沟通
- 电话
- 真实面试
- Offer
- 用户手动编辑

新 Raw 发现 Research 信息：

```text
Raw
↓
对应 Skill
↓
PatchProposal
↓
用户确认
↓
CompanyResearch / OpportunityResearch
```

前端按主题展示。

后台保留来源引用。

---

# 16. Interview 的资料回流

模拟 / 真实 InterviewSession 共用：

```text
Raw Transcript
↓
Interview Skill
↓
Final Review
↓
PatchProposal
```

## 模拟面试

AI 面试官自己生成的信息：

> 不具备现实事实资格。

用户本人明确补充或确认的个人信息：

> 可成为 Career Patch 候选。

## 真实面试

真实面试官透露：

- 岗位
- 团队
- 业务

等信息，可以成为 OpportunityResearch Patch 候选。

---

# 17. Context 渐进式披露

默认：

```text
先读当前整理后的资料
↓
需要时读相关对象
↓
需要证据时回 Raw
```

不要：

```text
把所有旧JD
所有聊天
所有面试
所有PDF
所有旧AI总结
一次性塞进模型
```

目标：

> **资料越积越多，AI 输入仍然保持清晰。**

---

# 18. 与未来 Employment / Project 的关系

本周期只要求：

Opportunity / Resume / Interview 不要直接依赖未来 Employment / Project 的具体数据库结构。

统一通过：

```text
Career Context Interface
↓
ContextCompiler
↓
各 Skill
```

未来下个周期重构 Employment / Project 时：

只需要继续向这一层提供职业资料。

Opportunity 不应该因此整体重写。

---

# 19. Feedback 与 Career Context 完全隔离

Product Feedback 不进入：

- Career Wiki
- Opportunity Research
- Resume
- Interview Context

Feedback 的未来链：

```text
FeedbackEntry
↓
AI Grill + 用户澄清
↓
ProductIssue
↓
Spec
↓
开发
```

可以理解为：

> Feedback 是 GitHub Issue 的上游原材料。

---

# 20. 当前 MVP 不做

- 全局 Inbox
- 自动分类所有未知资料
- 复杂 Raw 历史版本
- 自动信任评分
- AI 自动修改正式事实
- 所有 Raw 自动进入上下文

---

# 你怎么看这份文档

只问一个问题：

> **“AI 到底为什么会知道这件事？”**

如果任何 AI 输出让你无法追溯：

> 它读取了什么？

说明 Context 设计还不够清楚。

# 你怎么用

以后增加任何 AI Skill 前，先写：

```text
它需要哪些 Context？
哪些不应该看到？
输出会修改什么？
需不需要用户确认？
```

再开发。

# 你怎么给我反馈

最适合的反馈：

> Interview Skill 这里应该再看到……
>
> 这个资料不应该进入 Research……
>
> 我希望这里用户确认后直接……
>
> Raw 这里我觉得过度复杂……

指出具体场景即可。
