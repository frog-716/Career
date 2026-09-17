# Opportunity UI Flow V1

## 0. 核心原则

这份文档只做一件事：

> **让每个重要按钮都知道“为什么存在，以及点下去后台发生什么”。**

统一格式：

```text
用户动作
↓
Domain Action
↓
后端变化
↓
前端变化
```

---

# 1. 添加 Opportunity

## 前端

用户填写：

- 公司
- 岗位
- JD
- 外部链接 optional

点击：

```text
[添加机会]
```

## 后端

```text
查找 Company
├── 已存在 → 关联
└── 不存在 → 创建

创建 Opportunity
phase = 写简历
result = active
```

## 前端变化

机会管线新增一行：

```text
公司 | 岗位 | 写简历 | 创建日期
```

点击整行进入 Opportunity Workspace。

---

# 2. 开始制作简历

Opportunity 处于：

```text
phase = 写简历
```

如果用户确实需要简历：

```text
[打开简历]
```

第一次进入：

```text
选择 / 导入已有简历
↓
创建 ResumeDocument
```

如果 Opportunity 不需要简历：

> 可以直接跳过。

---

# 3. 编辑简历

用户在 Resume Workspace 中：

- 编辑内容
- AI辅助
- 调整格式
- 预览

普通编辑自动持久化当前内容。

不会自动制造 ResumeVersion。

只有点击：

```text
[保存版本]
```

才创建：

```text
ResumeVersion
```

---

# 4. AI 辅助简历

按钮示例：

```text
[AI辅助]
```

或局部：

```text
[AI优化选中内容]
```

AI 通过 ContextCompiler 获取：

- Opportunity
- JD
- 当前 Career Context
- Research
- 当前 Resume

输出修改建议。

如果发现新事实：

```text
PatchProposal
↓
用户编辑 / 接受 / 拒绝
```

用户确认后即可落盘。

---

# 5. 编辑打招呼语

写简历阶段提供：

```text
[编辑打招呼语]
[AI辅助]
```

当前 Greeting 可以继续修改。

不单独切换 Opportunity 阶段。

---

# 6. 记录已投递

现实中完成投递后：

```text
[记录已投递]
```

不再要求填写日期、备注等无效信息。

如果存在简历：

```text
选择：
- 当前内容
- 某个已保存版本
- 本次未使用简历
```

## 后端

自动：

```text
submitted_on = 今天

创建 Submission
冻结：
- submitted resume snapshot? optional
- submitted greeting snapshot

如果当前简历未手动保存：
自动生成“投递版本”
```

然后：

```text
Opportunity.phase = 已投递
```

## 前端变化

当前阶段工作区从：

> 投递准备

切换为：

> 招聘沟通

---

# 7. 添加线上沟通

已投递阶段：

```text
[添加线上沟通]
```

用户：

- 粘贴聊天文本
- 上传相关文本资料

## 后端

```text
创建 CommunicationEvent
创建 RawSource
↓
Communication Skill
↓
PatchProposal
```

可能产生：

- Research 更新
- 面试安排
- 薪资信息

## 前端

Timeline 新增沟通记录。

Patch 按目标对象聚合展示。

---

# 8. 记录电话沟通

按钮：

```text
[记录电话沟通]
```

MVP 可以先：

- 用户粘贴自己的文字记录
- 或上传转写后的文本

底层仍然：

```text
CommunicationEvent
+
RawSource
```

不建立单独 PhoneCall 系统。

---

# 9. 确认正式面试

当现实中已经确认：

> 某日进行某轮正式面试。

用户创建：

```text
InterviewSession
type = real
```

最低填写：

- 轮次名称
- 日期

## 后端

```text
创建 real InterviewSession
Opportunity.phase = 面试
```

阶段切换发生在确认正式面试当天。

## 前端

当前阶段工作区切换为：

> 当前面试轮次

---

# 10. 面试前准备

进入某轮真实 InterviewSession：

```text
[准备这一轮]
```

AI Context Pack 可以读取：

- JD
- 实际投递简历
- Research
- HR沟通
- 之前真实面试复盘

输出：

- 预计问题
- 重点项目
- 高风险问题
- 待准备信息

Preparation 属于这一轮真实面试。

---

# 11. 开始模拟面试

只有已经存在目标真实 InterviewSession 时：

```text
[开始模拟面试]
```

## MVP

Career：

```text
生成 Simulation Context Pack
↓
复制
↓
用户粘贴到全新 ChatGPT 对话
↓
Voice 模拟
↓
用户自行录音 / 转写
↓
上传文本 Transcript
```

## 后端

创建：

```text
InterviewSession
type = simulation
target_real_interview_id = 当前真实面试
```

模拟面试进入 Timeline。

---

# 12. 上传模拟面试 Transcript

用户：

```text
[上传模拟面试文字稿]
```

## 后端

```text
RawSource
↓
Interview Skill
↓
Final Review
↓
PatchProposal
```

Final Review：

1. 本轮结论
2. 关键问答
3. 跨问题模式
4. 新信息发现
5. 下一轮建议

用户可直接编辑 Final Review。

---

# 13. 上传真实面试 Transcript

真实面试完成后：

```text
[上传真实面试文字稿]
```

走与模拟面试完全相同的加工链：

```text
RawSource
↓
Interview Skill
↓
Final Review
↓
PatchProposal
```

区别：

> 真实面试官明确透露的信息可以成为 Opportunity Research 候选。

---

# 14. 添加下一轮面试

收到二面安排：

```text
创建新的 real InterviewSession
```

Opportunity 仍然：

```text
phase = 面试
```

不会出现：

- 一面 phase
- 二面 phase

当前阶段工作区显示最新待进行真实面试。

---

# 15. 收到 Offer

用户记录现实 Offer。

## 后端

```text
创建 / 更新 Offer
Opportunity.phase = Offer
```

## 前端

当前工作区切换：

- 当前 Offer
- AI分析
- 谈薪沟通
- 最终决定

---

# 16. 添加谈薪沟通

点击：

```text
[添加谈薪沟通]
```

后端仍然创建：

```text
CommunicationEvent
purpose = negotiation
```

不建立独立 Negotiation 模块。

Timeline 显示对应谈薪记录。

---

# 17. 结束 Opportunity

## 被招聘方终止

```text
result = rejected
```

## 用户主动退出

```text
result = withdrawn
```

## 接受 Offer

```text
result = accepted
```

只要：

```text
result != active
```

Opportunity 自动进入：

> 已结束 View

`phase` 不改变成“已结束”。

它保留最后走到的阶段。

---

# 18. 机会管线

View：

- 全部
- 写简历
- 已投递
- 面试
- Offer
- 已结束

第一版核心列：

```text
公司 | 岗位 | 阶段 | 阶段日期
```

点击整行进入 Workspace。

不在每行堆：

- 查看
- 编辑
- 研究
- 面试
- Offer

等大量按钮。

---

# 19. Opportunity Workspace

## 顶部

稳定展示：

- 公司
- 岗位
- 阶段
- 阶段日期
- 阶段条
- 外部链接 optional

## 当前阶段工作区

由 `phase` 自动变化。

## 岗位情报

显示当前 Research 摘要。

## 投递材料

投递后显示：

- 实际投递简历
- 实际打招呼语
- 投递日期

不在这里管理全部 ResumeVersion。

## Timeline

统一展示：

- 投递
- 沟通
- 模拟面试
- 真实面试
- Offer
- 谈薪
- Opportunity 结束

点击某一项进入它的真实对象详情。

---

# 20. UI 最重要的产品原则

1. 主按钮表达用户意图，不表达数据库操作。
2. 用户不需要理解 Entity 名称。
3. 当前阶段工作区优先显示现在真正要处理的事情。
4. 历史信息进入 Timeline。
5. AI 按业务对象出现。
6. Raw 不成为普通一级页面。
7. 表格负责看全局，Workspace 负责推进单个机会。

---

# 你怎么看这份文档

重点不是看按钮名字好不好听。

重点问：

> **我做一个现实动作以后，页面变化是不是符合直觉？**

例如：

> 记录已投递后，页面是否应该自然切到招聘沟通？

# 你怎么用

未来前端修改前，先写一行：

```text
用户为什么要点这个按钮？
```

再找到这里对应的 Domain Action。

如果找不到，很可能按钮本身没有被设计清楚。

# 你怎么给我反馈

可以直接描述场景：

> 我投递后第一件事其实不是这个，而是……
>
> 面试阶段这个按钮我不会这样用……
>
> 这里点击后我希望还留在当前页面……

我再根据真实场景回改前后端映射。
