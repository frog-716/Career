# Wiki、Project 与 Resume 新周期实施计划

日期：2026-09-25
状态：已批准；Phase A 已完成。Phase B COMPLETE / PASS；Runtime Rebaseline、两轮用户 UI 验收和本轮测试数据清理均完成。未进入 Phase C
范围：Career 仓库

## 一、目标与边界

按本轮 Career 规格实现四个一级工作区：Wiki、机会、项目、任职。Project 是长期资产；Person 归属于任职环境；Raw 保存发生过的原始材料；Wiki 保存从 Raw 整理出的当前知识；Wiki Compiler 逐条提出并等待用户确认；每个 Opportunity 仍有自己的 ResumeDocument。

2026-09-29 用户覆盖：GitHub 仓库保持 Public，代码与允许公开的开发资料可入库；正式用户数据、Secret 和本地资料不得进入 Git。本计划不包含公开网站、云部署或发布 Career。

第二份附件是另一套从空目录开始搭建飞书会议记忆系统的规格，包含新仓库、飞书应用、OSS、Linux 服务器和定时任务。这些属于另一个产品，与 Career 当前 local-first 边界不符，不纳入本计划。只借鉴其中 Raw 到语义 Wiki 的思路，以及用户提供的 lesson7 页面中“先看语义页面，需要细节时回到原始记录”的做法。

## 二、完成条件

- Project、Employment、Person、Raw、Wiki、Cognition 和 Wiki Compiler 的唯一权威规则写在 [长期 Career 模型](../target/long-term-career-model.md)，其他当前文档只引用并同步必要摘要。
- 每个开发批次都有可观察的用户结果、对应测试、数据迁移保护办法和停止条件。
- 保留当前用户改动、机会隔离、冻结投递材料、PDF 与面试 Context Pack。
- 自动化测试使用虚构资料；需要真实界面确认时再按一次一个操作的方式请用户验收。
- GitHub 仓库保持 Public；Career 正式用户数据、Secret 和本地资料不得进入 Git，不要求公开网站或云部署。

## 三、现状：已经确认的事实

- 历史事实（2026-09-25）：仓库当时由 Public 改为 Private。该可见性要求已由 2026-09-29 的 Public 覆盖规则取代。
- 本地分支 main。HEAD 与 origin/main 都是 5cbb21b74524527385cf46013095195e9663e81c。
- 开始本轮写入前，工作区已有 18 个文件未提交修改，共 414 行新增、321 行删除。本机已有改动包含基础资料同步到当前简历、PDF 和链接展示等内容。业务源代码、测试、前端页面及实现README未改；其中 5 份原本就有修改的权威产品文档只做了 Phase A 必要的规则对齐，保留原有用户修改。
- 当前工作区基线命令为 .venv/bin/python -m pytest -q，结果是 421 passed，耗时 22.63 秒。
- 生产 SQLite 只读检查得到 user_version=6。表包括 current、revisions、records、applications、meta、ai_operations 和 ai_dispatch_slot。只检查了结构，没有读取业务记录或个人内容。
- 程序只接受 schema v6；旧版本使用显式迁移工具。现有迁移模式会在副本上执行，并把计划绑定到源数据摘要。新迁移应沿用这个保护办法。
- Career 本地服务正在 127.0.0.1:8765，构建标签是 career-0.7.0-batch-f。Python 服务进程的启动时间晚于当前已修改的 Python 源文件；线上首页内容与 frontend/dist/index.html 相同。不过构建标签不是 Git 提交摘要，所以不能据此证明后端每个文件都与当前源码逐字节一致。
- STATUS 最近记录日期是 2026-09-24，主要描述 T00–T15 和之前的 cutover；它不包含本轮新目标和当前本机改动。
- 用户给的 [lesson7 页面](https://ai-course-deck.daishixiong.com/lesson7/) 共有八页。相关要点是 Raw 材料可能很厚，语义 Wiki 先帮助找到关系，深入事实时再回到具体 Raw 来源。其余服务器、飞书和 OSS 流程属于另一套系统。

## 四、差距分析：最大的十项冲突

| # | 新目标 | 当前实现 | 处理方向 |
|---|---|---|---|
| 1 | 一级导航为 Wiki、机会、项目、任职。 | 当前是 Wiki、机会、简历工作台、任职。 | 删除简历工作台一级导航，增加独立项目入口；从机会进入完整简历编辑器。 |
| 2 | Project 独立存在，可选关联任职，使用用户自建 Tags。 | 后端已有 work_project，允许多种 scope；界面把项目放在任职页内。主要字段是 name、description，没有 tags、目标状态和 status_note。 | Project 改为独立长期对象；状态限定 active、paused、completed、canceled；取消原因写 status_note；任职只是可选业务关系。 |
| 3 | Employment 表示一段真实工作环境；Person 主要属于某一段 Employment。 | Employment 是从 journey_episode 投影出来的兼容对象；Person 是全局 name/role 记录，未绑定任职。 | 身份映射、长期 Person 创建和重要知识写入由用户确认；普通 mention 留在 Raw。已确认身份后的明确要求/承诺由 Compiler 作为普通 Patch 逐条审批，不重复确认身份。 |
| 4 | Raw 是原始事实依据，Wiki 保存当前语义并能回指 Raw。 | work source、event、evidence 分成多个记录类型；Wiki 是 personal/job/episode 范围的 typed entries。没有贯通 Raw 到 Wiki 的整理流程。 | 定义共用来源引用和渐进读取边界；不建设万能资料导入平台。 |
| 5 | Wiki 包含 Project、Employment、People、Cognition 等当前知识。 | Wiki 主要是人工确认的条目清单；Cognition 没有完整的、带来源的 Wiki 合同。 | 收敛为有来源的 Fact、Observation、Hypothesis；业务范围用 scope 和 Tags 表达，不另建一套 Project/Employment 库。 |
| 6 | Wiki Compiler 比较新旧认知，产生 add、rewrite、retire，逐条审批。 | 当前知识入口能生成待确认候选；T14 可以生成已批准的个人 Wiki 条目，但没有面向当前知识的差异 Patch。 | 新增逐条接受、编辑后接受、拒绝；不允许批量接受；retire 保留历史。 |
| 7 | Event 是 Raw；有价值的成果是带来源的 Wiki 知识；Evidence 是 source_refs。T14 待退役。 | work_event、work_achievement、work_evidence、work_evidence_link 分开保存；T14 把成果复制为特殊 wiki_entry，并带 reuse_status、allowed_uses 和 Resume provenance。 | 先区分真实资料与测试资料；明确属于测试的数据允许安全清理。新模型优先，不为旧实体造复杂兼容层；schema migration 仍显式、安全、可测试。 |
| 8 | ResumeUse 退役；简历编辑器从 Opportunity 进入。 | ResumeUse 仍进入应用状态和机会 UI；Resume Workspace 是一级导航。Opportunity 自己的 ResumeDocument 和冻结 Submission 已存在。 | 移除 ResumeUse 的正常 UI 与活动流程；保留每机会独立简历和历史投递快照。 |
| 9 | Resume AI 使用专门的最小 DTO，并对 rewrite/add/delete 建议逐条审批。 | 当前 AI 读取受控任务包，但提案是整份前后文本，并由一个按钮一次应用。 | DTO 默认只发送 Profile 区是否存在及其中有哪些字段，不发送姓名、电话、微信、邮箱等值；未来任务需要内容时另行定义最小范围。 |
| 10 | Mac 快捷键须明确支持编辑、对齐、历史、查找替换、版本保存和行内选择。 | 自定义快捷键只有 Command+B、Command+方向键对齐、Command/Control+Z 与 Shift+Z 撤销重做；其他指令交给浏览器或未实现。没有专门的快捷键自动测试。 | `⌘⇧←/→` 是硬性目标；Phase H 先核对浏览器/macOS 实际行为，由用户手工明确选区，再定义并测试最终算法。 |

## 五、保留、重构、退役与测试调整

### 保留

- 每个 Opportunity 自己的 ResumeDocument、自动保存和并发版本保护。
- Submission 冻结的 Resume、PDF、Greeting 和日期。
- 面试 Simulation Context Pack 使用真实投递时冻结的 Resume 快照。
- 仍有追溯价值的 Raw 来源、修订历史与 provenance。
- 当前 local-only 运行方式与代码目录外的数据目录。

### 重构

- Project 和任职页中的项目区，改为独立项目工作区与显式任职关系。
- Employment、Person 的归属和结束后的历史语义。
- Source、Event、Evidence 到 Raw 与来源引用的关系，保留原始材料。
- Wiki 条目为带 source_refs、版本和逐条确认的语义知识。
- Resume AI 输入包和提案形状，继续隔离其他 Opportunity。

### 数据核验后退役

- ResumeUse 的用户概念和活跃读写路径。
- T14 的 Achievement → Evidence → 简历复用 → 特殊 Wiki Entry → allowed_uses 链。
- Resume 工作台一级导航。
- Raw 与 Wiki 来源足以表达后不再重复维护的 event/achievement/evidence 副本。
- Wiki 和 Resume 提案的批量接受按钮。

### 需要重写或扩展的测试

- test_t14_reuse.py：改测有来源的 Wiki 知识及之后的 Resume 选材，不再保留旧复用链。
- test_work_domain.py、test_knowledge.py：覆盖独立 Project、任职归属 Person 和逐条 Wiki Patch。
- test_t15_navigation.py、test_resume_workspace_single_page.py：覆盖新导航以及机会进入编辑器。
- test_resume_documents.py、test_opportunity_flow.py、test_interview.py：证明机会简历隔离和投递/Context Pack 冻结。
- 增加浏览器快捷键测试。当前搜索到的测试没有断言编辑器键盘行为。

## 六、快捷键现状审计

代码位置均相对仓库根目录。

| 快捷键 | 当前代码与行为 | 类型 / Mac 状态 | 新目标与验证 |
|---|---|---|---|
| ⌘B | frontend/src/editor/legacy-app.js:1448；调用 applyCommand("bold")。 | Career 自定义；使用 metaKey，未在浏览器实测 Mac。 | 保留；测试只加粗当前可编辑文字。 |
| ⌘← / ⌘↓ / ⌘→ | legacy-app.js:1450–1460；分别左对齐、居中、右对齐。 | Career 自定义；Mac 未实测。 | 保留；确认只修改当前选择的简历对象。 |
| ⌘Z / ⌘⇧Z | legacy-app.js:1463–1465；自有撤销/重做。也响应 Ctrl+Z、Ctrl+Shift+Z。按钮在 frontend/src/resume-workspace.ts:59–60。 | Career 自定义。 | 保留；测试编辑历史栈与平台别名。 |
| ⌘X / ⌘C / ⌘V | 没有 Career 键盘处理器；在编辑区依赖浏览器对可编辑元素的剪切、复制、粘贴。 | 浏览器原生；受焦点和选择范围影响，Mac 未验证。 | 测试只作用于当前编辑上下文。 |
| ⌘A | 没有 Career 键盘处理器；依赖浏览器选择行为。 | 浏览器原生；焦点错误时可能选中整页，Mac 未验证。 | 保证全选限于当前编辑对象或文字上下文。 |
| ⌘F | 没有 Career 处理器，当前是浏览器页面查找。 | 浏览器原生；Career 查找替换缺失。 | 增加 Career 查找替换，并测试阻止浏览器查找。 |
| ⌘S | 没有 Career 处理器。 | 没有拦截浏览器保存网页；ResumeVersion 命名流程缺失。 | 阻止浏览器动作，打开轻量命名框并保存 ResumeVersion。 |
| ⌘Y | 没有 Career 处理器；浏览器/系统行为不固定。 | Career 未实现。 | 可作为额外重做别名；必须支持 ⌘⇧Z。 |
| ⌘⇧← / ⌘⇧→ | 没有 Career 处理器，依赖浏览器和 macOS 文本选择。 | 当前真实浏览器/macOS范围尚未核验。 | Phase H先观察真实行为，再由用户手工明确预期选择范围，随后才确定算法、实现和测试。 |

本轮没发现编辑器中其他 Career 自定义快捷键。撤销/重做按钮仍存在。自动验收应在隔离浏览器里验证焦点、选择范围、事件拦截和编辑结果；之后再按用户确认的范围做 Mac 验收。

## 七、建议实施批次

### Phase A：正式目标规格与权威文档

文件：新增 docs/target/long-term-career-model.md；更新 docs/00-authority.md、README 文档地图及 docs/01-product.md、docs/02-context-contract.md、docs/03-architecture.md、docs/05-acceptance.md、docs/07-roadmap.md；按需对齐四份 Opportunity 权威目标文件。

结果：Project、Employment、Person、Raw、Wiki、Cognition、审批、来源和迁移有一个明确的规则正本；按跨模块边界对齐 Opportunity 文档，不复制另一套字段正本。

验收：当前生效文档之间不再互相要求恢复旧模型；历史 audit 和 archive 保持原样。若发现未被用户新规格解决的已确认规则冲突，先停在该条具体冲突上。

### Phase B：独立 Project 工作区

可能文件：src/workbench/work.py、employment.py、app.py、frontend/src/workspace.ts、frontend/src/sidebar-model.ts、contracts.ts 与 work/navigation 测试。

结果：能独立创建和查看 Project；Tags 可自由填写；状态仅为 active/paused/completed/canceled；任职是可选真实关联；Employment 只展示同一 Project 的入口。

验收：个人 Project 不关联任职也能工作；两处都打开同一个 Project；不用建 Participant 也能完整使用。实现前先补迁移测试；生产数据迁移先备份，再在副本 dry-run、apply、verify，报告完整后才执行。

本轮实现判断：现有 schema v6 的 `current.body` 是 JSON，可以保存 Project 新字段，无需 SQL schema migration。正式运行前按用户授权重建了 `frontend/dist`，完成受控重启并建立新的 Runtime Rebaseline；普通验证构建输出到 `/tmp`。两轮 UI 验收通过后，只清理了本轮新建的虚构 Project 及其专属修订/幂等记录，保留了本轮前已存在的 Employment。健康检查、正式数据 identity、schema 与 Provider outbound 复核均通过；详细证据见 STATUS。

### Phase C：Employment 与 Person 生命周期

可能文件：src/workbench/employment.py、work.py、knowledge.py、frontend 任职/人物相关界面及测试。

结果：Person 属于 Employment；Raw 中的名字只是临时 mention；身份映射、长期Person创建和重要人物知识写入由用户确认；任职结束后相关知识保持历史状态。已确认身份后的明确要求/承诺作为普通Wiki Patch逐条审批，不再重复确认身份。

验收：重复提及同一名字也不会自动建人；身份未确认时不能写进长期 Person Wiki；已确认人物的明确要求/承诺直接形成逐条Patch待审批，不再另做一次身份确认；已确认内容保留任职范围和 Raw 来源。

### Phase D：Raw、Wiki 与 Wiki Compiler

#### Phase D1：Raw + Wiki Semantic Foundation

范围：建立 Raw 与用户维护的 Wiki Knowledge 统一合同；已有原始对象按稳定 ID 引用，`source_refs` 固定 kind/id/revision/hash；Wiki 使用 Fact、Observation、Hypothesis 与 current/retired/revisions；机会私有范围继续隔离。可复用 `records/current/revisions` 时不升级 schema。新 Wiki 不进入 Resume AI / Context，不调用 Provider。

验收：虚构数据证明 Raw identity/hash 稳定且不被 Wiki 改写；用户可手工创建/编辑 Wiki、查看 exact source、current、retired 与历史；Person 范围只接受已确认人物；机会 A 的知识不进入机会 B 或通用长期范围；没有自动 Compiler Patch。

#### Phase D2：Wiki Compiler

范围：比较新 Raw 与相关对象已有的当前 Wiki，提出逐条 add、rewrite、retire Patch，供用户审批；不自动执行 Cognition 提炼或批量接受。

验收：接受、编辑后接受、拒绝只影响对应条目；拒绝不改 Wiki；retire 不删历史；Raw 不被改写；每条提议能回到来源。进入 D2 前先完成 D1 自动与用户 UI 验收。

### Phase E：退役 T14 与重复实体

可能文件：work.py、knowledge.py、editor.py、机会材料选择 API/UI、迁移工具，以及 T14/work/knowledge 测试。

结果：简历从相关的、有来源的 Wiki 知识选材；不再靠旧的复用状态和单独 evidence 链流转。先分类真实资料和测试资料；明确属于测试的旧业务对象允许安全清理。正确的新模型优先，不为 T14 / ResumeUse / Achievement / Evidence 建复杂兼容迁移层。

验收：没有活跃的 T14 流程；未知或真实记录不误删，真实且需保留的知识能以 Raw + Wiki source_refs 表达；已识别为测试数据的旧业务对象可清理。schema migration 必须单独显式、安全、可测试，含副本 dry-run、备份与恢复核验。若真实记录无法无猜测地映射，才报告具体记录类型和选择。

### Phase F：Resume 导航与创建

可能文件：frontend/src/workspace.ts、resume-workspace.ts、opportunity-ui.ts、editor/legacy-app.js、resume_documents.py、contracts 和 Resume 测试。

结果：删除简历工作台一级导航；机会 → 编辑简历直接打开该机会的简历。首次建简历使用指定基础模板；已有版本时复制所选版本当前内容并立即进入编辑。移除 ResumeUse 和不必要的保存/导出 UI；⌘S 留给 Phase H 按真实 Mac 行为验收。

验收：每个 Opportunity 仍只有自己的 ResumeDocument；复制后互相独立；自动保存与命名版本行为不同；Submission 快照保持冻结。

### Phase G：Resume AI DTO 与逐条建议

可能文件：resume_documents.py、context.py、Opportunity/Context 合同、编辑器界面、Provider 输入测试与 Resume AI 测试。

结果：首轮只发送当前 Opportunity、JD、对应 Research 和当前简历表达；模型说明缺少何种经历后，本地检索才返回 Wiki/Project/Employment 候选 ID。用户选中后第二轮发送少量相关当前知识；模型明确要求核对已选 Wiki 的来源、且用户选中后，第三轮才发送对应 Raw/Evidence 原文。每轮均给准确 Preview 并单独确认。Profile DTO 只说明 Profile 区存在及有哪些固定字段，不带字段值。建议以 rewrite/add/delete 逐条呈现和审批。

验收：输入不含其他 Opportunity 和整库 Raw，也不含 Profile 真实字段值；每条建议单独接受、编辑接受或拒绝；不应用未确认事实。未来若某任务确需 Profile 内容，另行规定该任务最小发送范围。

执行状态：Phase G 已提交并装载正式 Runtime，隔离 TestProvider 与 Chrome 路径通过；真实 Resume AI 建议质量未验，本轮没有第二次真实 Provider 请求。证据与限制见 [STATUS](STATUS.md) 的 Phase 8。

### Phase H：快捷键

可能文件：frontend/src/editor/legacy-app.js、resume-workspace.ts、隔离浏览器测试和前端测试命令。

结果：实现 Mac 编辑、对齐、历史、查找替换、命名版本和行内选择。保留已有按钮；其他别名按当前清单实现。对 `⌘⇧←/→`，先实际检查浏览器/macOS 行为，再由用户手工验收希望从光标选到哪里，最后才冻结选择算法。

验收：在用户确认预期选区后，自动测试覆盖清单里的每个键，并证明不会错误触发整页选择或浏览器保存；用户再在 Mac 上做一次简短验收。

执行状态：Phase H 已提交、推送并装载正式 Runtime；用户确认保留 macOS 原生的当前行选区，且在正式 Mac 页面手工验收 `⌘⇧←/→`、`⌘S`、`⌘F` 均符合预期。自动证据与运行边界见 [STATUS](STATUS.md) 的 Phase 9–10。

### Phase I：本地整链验收和文档收口

文件：本轮涉及的测试、README、目标规格和 STATUS。

结果：跑聚焦测试、全套测试、前端检查、虚构资料浏览器验收和迁移副本演练；复核最终 diff 并按真实证据更新 STATUS。

验收：投递冻结和面试 Context Pack 回归通过；测试没有用个人资料；确需重启服务时核验启动后的实际版本。Career 保持本地运行，仓库保持 Public，正式用户数据、Secret 和本地资料不进入 Git。

执行状态：Phase I 已完成全量与虚构浏览器整链、正式 Runtime/Provider 增量核验，以及正式数据的隔离备份恢复；用户手工快捷键验收通过。真实 Resume AI 建议质量因唯一批准的真实调用已用于 D4 而未验，不能由 TestProvider 结果代替；见 [STATUS](STATUS.md) 的 Phase 10。

## 八、最高风险的五项回归

1. 迁移可能错分 Raw、Wiki、Resume 来源或修订历史。先区分真实资料和测试资料；只有明确归属测试的旧业务对象可清理。必须有备份、来源摘要、dry-run报告、可恢复副本和迁移后核对；schema迁移仍须显式、安全、可测试。
2. 当前简历、Wiki 改变时，不能改写旧 Submission PDF、Resume 快照或 Interview Simulation Context Pack。
3. Resume AI 可能读到其他机会或发送个人联系方式。必须在 DTO 构造处限制范围，并检查实际捕获的模型输入。
4. AI 可能把一句提及误认为长期人物或确定身份。普通提及保持临时；身份映射、Person 创建和重要知识写入要用户确认。已确认人物的明确要求/承诺进入普通逐条 Patch 审批，不再额外确认身份。
5. 编辑器全局按键可能选中整页、触发浏览器保存/查找或撤销错对象。先做浏览器焦点与选区测试，再做 Mac 手工验收。

## 九、首先实施哪一批

Phase A 已完成。Phase B 已实现 Project 一级入口、独立工作区、自由 Tags、四状态和可选 Employment 关联；定向及全量自动检查、Runtime Rebaseline、两轮用户 UI 验收和本轮测试数据清理均通过。用户原有业务改动未被编辑、回滚或格式化；Git ownership 审查未 stage 或 commit，5 份 Phase A 前已脏的权威文档无法按现有证据安全分离旧 hunk。Phase B 状态为 `COMPLETE / PASS`，本轮停止，不进入 Phase C。

自动检查、Runtime Rebaseline、UI 验收、清理与 Git ownership 证据记录在 STATUS。
