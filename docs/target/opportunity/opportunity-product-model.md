# Opportunity Product Model V1

## 0. 核心定义

> **Opportunity = 用户决定认真推进的“一次具体求职尝试”。**

它从“加入 Career”开始，到以下任一结果结束：

- `accepted`
- `rejected`
- `withdrawn`

岗位、简历、沟通、面试、Offer 都围绕这一次求职尝试展开。

---

# 1. 创建 Opportunity

创建最低信息：

- Company
- 岗位名称
- JD
- 外部跳转链接 `optional`

其中 Company 在后台复用：

```text
输入公司名
↓
已有 Company → 直接关联
没有 Company → 创建 Company
```

创建后默认：

```text
phase = 写简历
result = active
```

“写简历”是默认阶段和视觉提醒。

它不意味着必须真的制作简历才能继续。

---

# 2. Opportunity 的四个阶段

Opportunity 只保留四个大阶段：

```text
写简历
↓
已投递
↓
面试
↓
Offer
```

任何阶段都可能：

```text
rejected
withdrawn
```

只有 Offer 阶段可能：

```text
accepted
```

这是一条主路径，不是强制流水线。

---

# 3. 阶段一：写简历

这个阶段本质上是：

> **投递准备。**

主要包含：

## 3.1 简历，可选

如果需要简历：

```text
导入 / 复制已有简历
↓
编辑
↓
AI 辅助 optional
```

普通编辑可以自动持久化，但不会自动产生历史版本。

只有用户主动：

```text
[保存版本]
```

才产生普通 ResumeVersion。

## 3.2 打招呼语

属于投递前准备的一部分。

可以：

- 用户自己编辑
- AI 辅助

它不单独成为 Opportunity 阶段。

## 3.3 记录已投递

现实中已经完成投递后，用户点击：

```text
[记录已投递]
```

系统：

- 自动记录投递日期
- 如果使用了简历，保存这次实际投递版本
- 保存本次打招呼语
- 将这些内容冻结为历史事实
- `phase → 已投递`

不要求用户再填写投递日期、备注等低价值字段。

---

# 4. 阶段二：已投递

含义：

> **已经向招聘方发出正式申请，但还没有确认进入正式面试。**

主要活动：

- 线上沟通
- 电话沟通

当前工作区主要围绕：

```text
[添加线上沟通]
[记录电话沟通]
```

这些沟通内容可能产生：

- 新岗位信息
- 新团队信息
- 薪资信息
- 正式面试安排

如果确认正式面试：

```text
创建真实 InterviewSession
↓
phase → 面试
```

阶段切换发生在“正式面试被确认”的当天，不等真正面试完成。

---

# 5. 阶段三：面试

Opportunity 只显示：

> **面试**

不会出现：

- 一面阶段
- 二面阶段
- 三面阶段

这些由 InterviewSession 自己管理。

例如：

```text
Opportunity
└── 面试
    ├── 业务一面
    ├── 业务二面
    └── HR面
```

## 5.1 一轮真实面试

最低只需要：

- 轮次名称
- 日期

例如：

```text
业务一面
2026-09-20
```

每轮面试是一个完整小闭环：

```text
收到安排
↓
面试前准备
↓
模拟面试 N 次
↓
真实面试
↓
上传 Transcript Raw
↓
Final Review
↓
信息回流
```

## 5.2 模拟面试

只有已经存在目标真实面试时才创建。

例如：

```text
业务一面
├── 模拟1
└── 模拟2
```

模拟面试和真实面试使用相同后处理链：

```text
Raw Transcript
↓
Interview Skill
↓
Final Review
↓
PatchProposal
```

区别只在：

- 来源
- 证据意义

模拟面试中 AI 扮演的面试官自己生成的信息，不具备现实事实资格。

用户本人在模拟过程中明确补充或确认的个人事实，可以产生 Career Patch 候选。

## 5.3 Final Review

固定关注：

1. 本轮结论
2. 关键问答
3. 跨问题模式
4. 新信息发现
5. 下一轮建议

用户可以直接编辑终版。

长期只需要：

```text
Raw
+
Final Review
```

不额外保留 AI 原始复盘版本。

---

# 6. 阶段四：Offer

进入条件：

> 现实中收到 Offer。

此时：

```text
phase → Offer
```

Offer 阶段包含：

```text
Offer 信息
↓
AI分析
↓
谈薪 / 条件沟通
↓
条件变化
↓
最终决定
```

谈薪继续使用 CommunicationEvent：

```text
purpose = negotiation
```

不单独建立 Negotiation 模块。

多 Offer 对比本周期暂不做。

未来可新增：

```text
选择多个 Offer
↓
offer_comparison Skill
↓
AnalysisSession
```

无需修改 Opportunity / Offer 基础业务逻辑。

---

# 7. phase 和 result 必须分开

## phase

回答：

> **这次 Opportunity 最后走到了哪里？**

只有：

- 写简历
- 已投递
- 面试
- Offer

## result

回答：

> **这条 Opportunity 现在还在推进吗？如果结束，是怎么结束的？**

只有：

- `active`
- `accepted`
- `rejected`
- `withdrawn`

例如：

```text
面试 + rejected
```

表示：

> 面试阶段被招聘方终止。

```text
面试 + withdrawn
```

表示：

> 面试阶段用户主动退出。

```text
Offer + accepted
```

表示：

> 用户接受 Offer，这次求职 Opportunity 结束。

---

# 8. “已结束”只是 View

> **只要 `result != active`，就进入“已结束” View。**

例如：

| phase | result | View |
|---|---|---|
| 写简历 | active | 写简历 |
| 写简历 | withdrawn | 已结束 |
| 已投递 | active | 已投递 |
| 已投递 | rejected | 已结束 |
| 已投递 | withdrawn | 已结束 |
| 面试 | active | 面试 |
| 面试 | rejected | 已结束 |
| 面试 | withdrawn | 已结束 |
| Offer | active | Offer |
| Offer | rejected | 已结束 |
| Offer | withdrawn | 已结束 |
| Offer | accepted | 已结束 |

`已结束` 不是第五个阶段。

---

# 9. 机会管线

机会管线采用多维表式概览。

一行一个 Opportunity。

第一版核心字段：

- 公司
- 岗位
- 阶段
- 阶段日期

可选：

- 外部跳转链接，以轻量图标呈现

View：

- 全部
- 写简历
- 已投递
- 面试
- Offer
- 已结束

点击整行进入 Opportunity Workspace。

---

# 10. Opportunity Workspace

Workspace 只回答三个问题：

> **我在哪里？现在干什么？过去发生了什么？**

结构：

## 10.1 稳定顶部

展示：

- 公司
- 岗位
- 当前阶段
- 进入当前阶段日期
- 阶段条
- 外部链接

## 10.2 当前阶段工作区

根据 phase 自动切换：

### 写简历

- 打开简历
- 编辑打招呼语
- 记录已投递

### 已投递

- 添加线上沟通
- 记录电话沟通

### 面试

- 当前真实面试轮次
- 面试前准备
- 开始模拟面试
- 上传真实面试文字稿

### Offer

- 查看 Offer
- AI 分析
- 添加谈薪沟通
- 接受 / 拒绝 / 主动退出

## 10.3 岗位情报

前端统一展示：

- 公司与业务
- 岗位
- 团队 / 组织
- 招聘背景
- 当前机会判断

后台实际来自：

```text
CompanyResearch
+
OpportunityResearch
```

## 10.4 投递材料

只回答：

> **当时到底发了什么？**

展示：

- 投递简历
- 打招呼语
- 投递日期

这些内容不可修改。

简历历史统一去 Resume Workspace 查看。

## 10.5 Timeline

Timeline 展示完整求职活动流，包括：

- 加入 Career
- 完成投递
- HR 沟通
- 电话沟通
- 模拟面试
- 真实面试
- Offer
- 谈薪
- rejected / withdrawn / accepted

点击某项进入对应对象详情。

不记录：

- 保存简历版本
- 修改字号
- AI重新分析
- 接受 Patch
- 普通软件操作

---

# 11. 当前产品原则

1. 一条 Opportunity = 一次具体求职尝试。
2. phase 描述推进位置，result 描述最终结果。
3. “已结束”只是筛选 View。
4. 当前阶段工作区负责行动。
5. Research 负责当前认知。
6. Timeline 负责真实活动历史。
7. AI 贴着具体任务出现，不设置万能 AI 聊天框。
8. 同一事实只保留一个权威位置。
9. 用户拥有最终确认和编辑权。
10. 长尾异常优先人工修正，重复出现后再升级产品模型。

---

# 你怎么看这份文档

先完全不考虑代码。

只判断：

> **如果 Career 已经做完，我是否愿意按这个流程真正使用它？**

重点检查：

- 四阶段是否自然
- 哪个地方会让我觉得“为什么还要点这一步”
- 哪些信息实际上不需要
- 哪些现实求职动作漏掉了

# 你怎么用

这份文档未来是 Opportunity 的产品定义。

任何前端新功能先问：

> 它是否符合这里的产品模型？

如果不符合，要先改产品模型，再改代码。

# 你怎么给我反馈

可以直接：

> 第 5 节：模拟面试这里我觉得……
>
> 第 10.4：投递材料这里太重……
>
> 整体：我实际使用时还会出现……

无需正式格式。
