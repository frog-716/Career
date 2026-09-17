# Career Opportunity 文档包 V1

这套文档用于把当前已经对齐的 Opportunity 产品逻辑，转成后续可交给 Codex 审计、重构和维护的正式上下文。

当前开发周期只聚焦：

> Opportunity 从加入 Career → 投递准备 → 已投递 → 沟通 → 多轮面试 → Offer → 结束。

本周期暂不深度设计 Employment / Project / People / Growth 等长期职业资产模块，只保留未来可接入的边界。

---

## 文档地图

### 1. `opportunity-product-model.md`
**给产品 Owner 看。**

回答：

- Opportunity 到底是什么
- 四个阶段分别是什么意思
- `phase` 和 `result` 为什么分开
- 什么叫“已结束”
- 机会管线和 Workspace 各自负责什么
- 用户从加入岗位到机会结束到底怎么走

### 2. `opportunity-domain-model.md`
**给你 + Codex 一起看。**

回答：

- 哪些是真正的业务对象
- 谁和谁是一对一 / 一对多
- 哪些只是前端展示，不应该建成第二份数据
- 哪些内容可以修改
- 哪些历史一旦发生就只能查看

### 3. `opportunity-ui-flow.md`
**给前端设计和 Codex 实现看。**

统一使用：

> 用户动作 → 后端动作 → 数据变化 → 前端变化

帮助检查每个按钮为什么存在，以及它点下去到底发生什么。

### 4. `context-ingestion.md`
**给 AI / Context / Raw 处理看。**

回答：

- Raw 怎么进入系统
- 为什么 Raw 不应该直接污染 AI 上下文
- 不同 Skill 怎样处理资料
- PatchProposal 怎么产生
- 用户如何拥有最终确认权
- ContextCompiler 后续应该读什么

---

# 推荐阅读顺序

第一次阅读：

1. `opportunity-product-model.md`
2. `opportunity-ui-flow.md`
3. `opportunity-domain-model.md`
4. `context-ingestion.md`

原因：

> 先理解“产品怎么用”，再理解“按钮背后发生什么”，最后才看“后端为什么这样建”。

---

# 你现在怎么用这套文档

当前先不要直接让 Codex 按文档改代码。

正确顺序：

1. 你先读这套文档，确认产品逻辑和你的使用直觉一致。
2. 把你觉得不合理、看不懂、遗漏、过度设计的地方直接反馈给我。
3. 我们修订成 V2。
4. 再让 Codex 只读审计当前 Career MVP，输出 AS-IS。
5. 用 AS-IS 对照这套 TO-BE 文档做 Gap Analysis。
6. 最后才生成真正的重构 Spec 并开始改代码。

---

# 你怎么给我反馈

不需要写正式需求。

你可以直接使用这些格式：

### 发现理解错误
> `product-model / 第3节`：我这里不是这个意思，我实际会……

### 觉得过度设计
> `domain-model / ResumeVersion`：我觉得这个对象没必要，原因是……

### 看不懂
> `ui-flow / 记录已投递`：这里我没理解为什么需要这一步。

### 想补真实场景
> 实际还会出现一种情况：HR先电话聊，再让我补发简历……

### UI直觉不对
> Opportunity Workspace 这里我更希望先看到 XXX，而不是 XXX。

### 完全同意
> 第 1、2、5 节可以保留，不用再讨论。

你的反馈不需要一次性完整。看到哪里就反馈哪里。

---

# 当前文档状态

**状态：Working Draft / V1**

这些是当前讨论后的稳定共识，不代表永远冻结。

后续真实使用如果反复出现新场景，可以继续调整领域模型。
