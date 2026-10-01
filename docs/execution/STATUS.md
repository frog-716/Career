# 当前状态

## 2026-10-01：Feishu Read Adapter — SYNTHETIC PASS / GATE 2 WAITING

- 按用户正式任务实现单向 Feishu Read Adapter；真实 Docs/Drive 搜索和文档内容均尚未读取。Phase 1 仅检查现有 lark-cli 能力、连接状态和当前 identity；没有 login/logout、scope 修改或重新授权。当前 CLI `1.0.96`，用户身份通过现有身份命令可读，Docs/Drive JSON 读接口可用；Wiki/Base 不在 V1。
- 架构为 Career → `FeishuReadAdapter` → 固定 allowlist 的 lark-cli → Feishu。支持连接检查、DOC/DOCX 元数据搜索、缓存选择后 Preview、用户确认后导入 `feishu_doc` Raw；只在用户选择后 fetch 对应文档正文，不自动建 Wiki，不调用 DeepSeek/Tavily，也没有 Feishu 写路径。不改 Career Domain 主模型、SQLite schema 或正式资料。
- 全量后端回归 **557 passed**；Feishu adapter 13 项聚焦测试通过。前端 16 组测试脚本、TypeScript typecheck 与 Vite build 通过；本批 HTML 转义、URL 白名单、无正文导入请求、本地 TXT/Markdown 编码和大小边界均有合成测试。隔离浏览器用独立临时数据、合成 lark-cli、TestProvider 和 `127.0.0.1:8766` 实走 Project → 添加资料 → 飞书搜索 → 选择 → 预览 → 导入 Raw，并在设置页验证连接身份。内置浏览器未提供系统文件选择器自动化，本地文件选择 UI 路径未做浏览器实测。正式运行实例仍未改动。最终 `git diff --check` 通过；真实 Feishu 资源内容仍未读取。
- 下一步停止于 Gate 2：获准前不执行真实搜索/读取。要进行一次有限真实验证，用户需批准并提供一个文档 URL/ID，或提供用于限定一次 Drive 搜索的关键词；获准后只搜索至多 10 条 DOC/DOCX 元数据，用户再选其中一项后读取该文档正文并核对 Preview 与 Raw 一致。

## 2026-09-29：Target Mode Phase 10 — FINAL CHAIN ACCEPTANCE COMPLETE / PASS

- 本阶段真实 Provider 未再次调用：此前唯一获准的 DeepSeek outbound 已用于 D4 价值验收；本阶段只用虚构隔离资料和 TestProvider，Tavily 调用为零。
- 修改前完成条件：对最终提交与正式 Runtime 跑全量后端、全部前端测试、typecheck/build、依赖、Secret、文档链接和 diff 检查；虚构隔离资料实走机会→简历→版本/PDF→投递冻结、Resume AI 隐私/按需来源和 Mac 编辑路径。核对正式 schema/data identity、备份到新目录并恢复核验、AI operation/Provider 零新增及正式 HTTP 静态文件。最后对齐 Git、Runtime、STATUS、Roadmap、Authority/Target；任何手工 Mac 项须等用户验收，不把自动浏览器结果当用户验收。
- 最终工作区全量 **544 passed**；其中投递版本/PDF 冻结及 Interview Simulation Context Pack 读取冻结简历的回归通过。仅已提交 Phase H 文件的独立检出全量 **543 passed**；前端 15 组测试、typecheck/build、`pip check`、npm 依赖检查、Secret scan、文档链接和 diff 检查通过。受保护的用户未提交改动仍在工作区，独立检出结果不冒称覆盖这些改动。
- 隔离虚构资料浏览器重走机会 A 建稿/自动保存/命名版本、机会 B 从 A 复制后独立编辑/恢复/PDF/实际投递及投递后冻结不变，结果 `PASS ALL`；另以 TestProvider 重走 Resume AI 三次独立 Preview、按需 Raw、刷新找回、逐条接受，真实 Provider 0 次。脚本、日志和截图见 `/tmp/career-target-phase10/`。
- 正式服务仍为 PID **44363**、`/healthz=ok`、仅本机 `127.0.0.1:8765`；正式 11 个静态文件与验收构建、HTTP 响应逐文件相同。用户在 Mac 正式页面手工确认 `⌘⇧←/→` 只选光标所在行、`⌘S` 打开版本命名框、`⌘F` 打开简历内查找框，三项均符合预期。正式库 schema v6、instance `42ff565e28a08e31414442521540ac3e`、`quick_check=ok`，AI operations 仍为 26，未新增 DeepSeek/Tavily 调用。
- 手工验收后，正式库相对 Phase H 切换基线多 1 个 `resume_document` 当前对象及 4 个历史记录（`editor_version` 1、`artifact` 1、`opportunity_command` 2）；这是用户手工操作期间的变化，未读取正文或自行清理。当前正式库重新备份到 `/tmp/career-target-phase10/final-recovery/backups/post-mac-acceptance`，清单 `complete`、`healthy/recoverable`，恢复到新的隔离目录后 schema、完整性、表计数及记录身份一致：current 45 / records 233 / revisions 203 / AI operations 26。正式数据、Secret 和备份均未进入 Git。
- 代码提交 `260511c` 已推送 main；Phase H 正式 Runtime 含该提交及保留的用户 Resume/Profile/PDF 工作区改动，不等同纯 Git 提交。D4 实测产品判断仍为 **REMOVE**；真实 Resume AI 建议质量因本次仅允许一回 DeepSeek outbound 而保持 **NOT VERIFIED**，不以 TestProvider 证明语义质量。

## 2026-09-29：Target Mode Phase 9 — MAC SHORTCUTS COMPLETE / PASS

- 修改前完成条件：在虚构隔离 Resume 编辑器实测 `⌘S` 阻止浏览器保存网页并进入现有命名版本流程；`⌘F` 阻止浏览器页面查找，打开当前简历内查找/替换并能作用到所选编辑正文；`⌘Z/⌘⇧Z`、`⌘B`、对齐、复制/剪切/粘贴/全选在焦点正确时只作用于当前编辑上下文，留有真实浏览器证据。`⌘⇧←/→` 先观察 macOS/Chrome 的原生选区，再按用户明确确认的范围实现或保持，不凭文字猜算法；最后请用户在 Mac 上短验。
- 现状复现：旧 document keydown 只自定义 `⌘B`、`⌘←/↓/→` 对齐与 `⌘Z/⌘⇧Z`，没有 `⌘S` 或 `⌘F` 拦截。隔离 macOS Chrome 的实际 `.editable` 中，单行从光标 `⌘⇧←/→` 选至该行首/行尾；在同一条目中按 Return 换行后也只选光标所在行。用户确认保持这一原生选区。
- Git `260511c` 已精确提交并推送 main。`⌘S` 进入现有命名版本流程；`⌘F` 打开当前简历内查找/替换；剪切/粘贴可随编辑撤销，对齐/粗体在搜索框有焦点时不误改简历。隔离 macOS Chrome 的按键、焦点、选区、查找替换和版本浏览器回归通过，截图见 `/tmp/career-target-phase9/find-panel.png`；独立暂存检出全量 543 passed，前端 15 组测试、typecheck/build 通过。正式 Runtime 更新至 PID **44363**，当时 schema v6、current 44 / records 229 / revisions 203、AI operations 26 未变，静态文件/HTTP 11 项一致，DeepSeek/Tavily 增量 0/0；切换证据 `/tmp/career-target-phase9/runtime-result.json`。其后用户在正式 Mac 页面完成三项手工验收，详情见 Phase 10。

## 2026-09-29：Target Mode Phase 8 — RESUME AI RETRIEVAL COMPLETE / SYNTHETIC PASS

- 修改前完成条件：虚构机会的 AI 先依据本机会/JD/Research/当前稿指出缺失证据，再经受控 Career 检索只返回 Wiki/Project/Employment 候选 ID，回正本读取少量相关当前知识；仅在明确缺少事实细节时读取所指 Raw/Evidence。每次外发都可预览实际 DTO，Profile 只含存在状态和固定字段名，不含真实值；不得读其它机会、Person 私聊、Feedback、整库 Raw/Wiki 或旧历史。建议限 `rewrite/add/delete`，每条带来源、单独编辑/接受/拒绝、过期保护，不批量接受、不自动写事实；无相关证据时明确缺口并允许 0 建议。用隔离 TestProvider 验收及捕获实际请求，不进行第二次真实 DeepSeek 或 Tavily 调用。
- 现状复现：当前 `_resume_ai_packet` 仅收本机会、当前稿、公司/机会 Research；没有 Career 检索。输出 schema 只支持既有字段 `rewrite`，`resolve` 可以一次接受多条，UI 有“接受选中建议”；与上述目标不符。分步先建立隔离红测试，再实现受控检索/最小 DTO，最后收敛逐条提案和用户界面。保留旧 pending 提案的读取与安全拒绝路径；受保护用户 Resume 源码修改精确分离。
- 已实现本地受限 Career 检索：先只返回 Wiki/Project/Employment 候选 ID/revision；用户选中后才读取少量当前 Wiki 和对象最小字段。其它 Opportunity 的私有 Wiki 在 SQLite 查询层就被排除。模型确需核对所选 Wiki 已引用的 Raw/Evidence 时，另建来源请求；用户明确选中后第三次 Preview 才带入每条不超过 3000 字的原文。三轮分别确认、独立 AI operation，不自动追加 Provider 请求或重试。
- 新建议可 `rewrite/add/delete`，新增必须引用本轮选中 Wiki；每条单独编辑、接受或拒绝，接受时复核来源、原文 hash 与当前稿 revision，新提案不能批量接受。Profile 外发仍只有存在状态和固定字段名。旧 pending 提案保留兼容读取/拒绝，不向正式 Career 资料自动写入任何建议。
- 先红后绿测试覆盖未授权 Raw 注入、其它 Opportunity Wiki 整表读取、三轮 Preview/来源/逐条应用。工作区全量 542 passed；仅本批提交文件的独立检出全量 **542 passed**、前端 15 组测试、typecheck/build 通过。独立 Chrome 用虚构机会、Wiki、Raw、TestProvider 实走三轮 Preview、按需原文、刷新找回计划和逐条接受；实际 TestProvider 调用 3 次，真实 DeepSeek/Tavily **0/0**。浏览器脚本与截图在 `/tmp/career-target-phase8/`；这证明流程和边界，尚不证明真实模型产出质量。
- Git `5844b3f` 已精确提交并 push main，仅含 Phase G 文件；正式 Runtime PID **36577** 已加载工作区源码和 11 个正式静态文件，HTTP 响应与验收构建逐文件 hash 相同，`AI_ENABLED`、仅监听 `127.0.0.1:8765`。重启前后 schema v6、data instance、current 44 / records 229 / revisions 203、26 条 AI operation（23 dispatched）均不变；唯一既有 `ai_secret_operation.updated_at` 在启动恢复时前进，其他正式业务行及 operation metadata 不变。切换前 SQLite 备份与逐表对比、构建/HTTP hash 见 `/tmp/career-target-phase8/`。正式源码仍包含保留的用户 Profile/PDF/Resume 工作区改动，不等同纯 Git HEAD。
- Phase G 代码、隔离产品路径和正式装载完成；真实 Resume AI 建议质量仍 **NOT VERIFIED**，本次用户批准的唯一真实 DeepSeek 请求已在 D4 用完，不进行第二次 outbound。进入 Phase H 快捷键，`⌘⇧←/→` 需先观察 macOS/浏览器真实选区并请用户验收预期。

## 2026-09-29：Target Mode Phase 7 — OPPORTUNITY-OWNED RESUME COMPLETE / PASS

- 本批真实 Provider 未调用；仅使用虚构隔离资料和 TestProvider，不新增 DeepSeek/Tavily outbound。
- 修改前完成条件：全新虚构库中，机会 A 无简历可创建当前工作稿，首次打开直接呈现 A4 基础结构（基础资料、专业技能、工作经历、项目经历、教育背景；第一版不预填 GitHub）；机会 B 可明确从 A 的命名版本复制当前内容，复制后归属和后续编辑完全独立。普通自动保存不生成版本；命名版本、历史恢复、PDF、返回所属机会及实际投递冻结均可从用户页面自然完成，刷新回读一致；ResumeUse 不进入正常新建路径。`⌘S` 等快捷键依 handoff 的 Phase H 最后单独验真，不把按钮可用冒称快捷键已完成。
- 先复现服务端基础模板与页面文案是否符合正本，再只改缺口；存储/版本行为先红测试后实现。所有验收均用虚构隔离库，不读正式简历或扩大 AI 范围，不调用 DeepSeek/Tavily。
- 原服务端空白建稿返回 `sections=[]`，新测试先失败；现在新建文档立即持有专业技能、工作经历、项目经历、教育背景四个可编辑分区，Profile 区沿用当前基础资料同步，未填写时不预填 GitHub。旧测试原先假定 `sections[0]` 必有选中内容，已改按类型寻找，不改变来源/投递语义。
- 独立 macOS Chrome 用全新虚构 Store / TestProvider 实走机会 A 建稿、自动保存但无版本、命名版本；机会 B 从 A 的版本复制后独立编辑、保存版本、PDF 下载正文、恢复、PDF 预览、记录已投递、刷新找回以及投递后改稿不覆盖冻结快照。返回机会可用，正常入口没有 ResumeUse 新建。详情与截图、PDF 在 `/tmp/career-target-phase7/fresh-eyes.md`；未做 PDF 每页像素排版或快捷键验收。
- 当前工作区全量 **539 passed**；前端 15 组测试与 typecheck 通过。仅本批暂存文件的独立检出先有 532 passed、2 failed、4 errors，均因临时检出缺少 `frontend/node_modules` 使浏览器测试无法启动 Vite；补齐本机依赖链接后，受影响文件 **10 passed**。这不代表任何正式数据或真实 Provider 已参与测试。
- Git `8afacd7` 已精确提交并 push main；正式 Runtime 受控更新到 PID **28378**，`AI_ENABLED`、仅监听 `127.0.0.1:8765`。正式 11 个静态文件与当前临时构建及 HTTP 实际响应逐文件 hash 相同。更新前后 schema v6、data instance `42ff565e28a08e31414442521540ac3e`、current 44 / records 229 / revisions 203、ID manifest、26 条 AI operation 元数据与 23 次 dispatched 不变，DeepSeek/Tavily 增量 0/0；本机证据 `.career-runtime/target-phase7.json`。正式源码包含该提交加保留的用户旧 Resume/Profile/PDF 工作区修改，不能等同纯 Git HEAD。
- Phase F 完成，继续 Phase G。自动简历建议目前仍只覆盖既有字段改写；相关 Wiki/Project/Cognition 的按需检索、增删建议及逐条审批尚未实现，不能因本阶段简历主链通过就宣称 Resume AI 目标完成。

## 2026-09-29：Target Mode Phase 6 — LEGACY RETIREMENT COMPLETE / PASS

- 修改前完成条件：仅在可证明归属的范围分类 REAL/TEST/UNKNOWN，不删真实/未知或任何正式业务行；旧 Project Event/Achievement/Evidence/T14 的新增写入口和可见按钮退出，新 Raw+Wiki 可写/可读、旧历史/来源/PDF/冻结投递仍可读；旧 Wiki/ResumeUse 后续停写需先查全调用链和受保护文件边界。先红测试，再实现与回归；不做 schema migration 或未知归属清理。
- 正式库只读 metadata 盘点见 `/tmp/career-target-phase6/inventory.md`：旧 work_achievement/event/evidence/link、wiki_entry、knowledge_candidate/source 有 demo 标记与 manifest 双重归属，可判 TEST；resume_use 2 条中 1 TEST、1 UNKNOWN。UNKNOWN 保留，不能因引用演示 PDF 猜测可删。当前没有必要 Gate 3/4。
- 旧 Project Event/Achievement/Evidence 与 T14 新复用、旧 ResumeUse、旧 Wiki Source/Candidate 新建/确认、旧 Note→Candidate 全部停止新写；旧 Profile 整理只归档原文为 personal Raw，再保存基础字段。旧来源、条目历史、待审候选拒绝、已有复用撤销、PDF 与冻结 Submission 保持可读。旧 Context / Resume 中的历史 `wiki_entry` 只作兼容读取，后续 Phase G 会收敛新 AI 检索，不把旧容器扩成新知识入口。D4 REMOVE 后新 prepare/execute 也返回 409，已有 pending Proposal/审计和手工 Cognition Wiki 保留；正式接口已实际验证两条 POST 均为 409 且零写入。
- 用户已确认仅恢复 Project/Employment/Person 的显眼字号与字重。查因结果是上轮 UX-3 的大字样式随 Phase 1 Runtime 更新首次在正式页加载，全局基础字号仍为 14px；本批将对象标题 38→20px、重点 28→13px 等局部样式恢复，不改布局/功能和其它页面。隔离真实 Chrome 的 4 个页面/视口截图及宽度检查见 `/tmp/career-font-diagnosis/`；正式静态文件与验收构建逐字节一致。
- 测试先红后绿：退休保护测试覆盖旧入口 409/事务零写、原有资料读取/撤销；当前工作区全量 **538 passed**、15 组 frontend tests、typecheck、临时 build、pip check、secret scan、Markdown links、diff check 通过；npm 依赖检查退出 0，仍有已知本机 extraneous 包。仅暂存提交文件的独立 checkout 在 D4 关闭前全量 **536 passed**，D4 关闭后 28 项聚焦回归与前端构建通过，未夹带用户旧 Resume/Profile/PDF hunks。
- Git `989221a` 已精确提交并 push main。正式 Runtime 从 PID 6293 受控更新到 PID 19114，`AI_ENABLED`、仅监听 `127.0.0.1:8765`，服务静态响应与正式 dist/验收构建 hash 一致。前后 schema v6、data instance `42ff565e28a08e31414442521540ac3e`、current 44 / records 229 / revisions 203、ID manifest、全部 26 条 operation metadata 与 23 次 dispatched 均不变；本批 DeepSeek/Tavily 增量 0/0。证据 `/tmp/career-target-phase6/`。正式 Runtime 源码仍包含保留的用户旧 Resume hunks，不等同纯 Git HEAD。
- 本批未删除任何正式业务行或未知归属的 ResumeUse；不做 schema migration。Phase F 开始，Resume 归属与首次创建/复制、版本、PDF、返回机会和 Submission 需按目标整体核对，不能因早期导航验收就提前称 F 完成。

## 2026-09-29：Target Mode Phase 5 — ONE REAL SMOKE COMPLETE / REMOVE

- 最新用户仅批准 A/B 两个虚构 Project 的当前 Wiki 进行一次 DeepSeek outbound，禁止 Raw、其它 Career 范围、Tavily、第二次请求、重试及正式资料自动修改。旧 Preview 已过期，因此新建本地 preparation；新 DTO 严格为 A/B 各 1 条当前 Wiki、已有 Cognition 0，内容和最终发送 payload hash `a3e7cc08…` 与已批准的预览完全一致，模型仍为 `deepseek-flash`。唯一一次执行成功返回 1 条待审建议，没有接受或应用。
- 建议核心：把两项虚构项目共同的“实现前先梳理边界与状态，再拆任务”合并为一句长期认知。两条 source_refs 均可追，但“数据归属”只见 A，“再拆分实现任务”只见 B；建议把这些单边细节写成双方共同做法，并以“都倾向于”概括行为倾向。没有人格诊断或无来源收益数字，然而没有新增适用条件、效果、例外或可复用决策线索，主要是原 Wiki 的改写。
- 价值判断 **REMOVE**：针对 D4 自动跨经历提炼，不继续扩建或默认保存这条建议；单次虚构样本不能证明所有跨经历分析都无价值，但本次实测没有支撑 GO，也没有展示值得为现有宽范围继续维护的具体高价值用途。已有 Cognition 手工 Wiki 语义与原提案审计仍按原合同保留；新旧两条建议均 pending，不自动接受、拒绝或删除。独立第二意见同判 REMOVE。
- 本批仅增加 1 个 DeepSeek dispatched/succeeded operation，Tavily 0；执行脚本为不可重复的单次哨兵，不执行 retry。正式 current 44、revisions 203、schema v6、数据实例及源码/静态文件 hash 不变；records 增加本地准备和操作/审计/提案记录，不新增 Cognition 当前知识。证据 `/tmp/career-target-phase5/smoke-approved/`。Phase 1–5 已完成价值判定，继续 Phase 6。
- 预览 UI 计数修复已独立于本次调用先红后绿、独立审查及虚构浏览器复验通过，Git `83eb60d` 已 push main、当时正式 Runtime PID 6293 已核验；旧 Gate 2 等待状态在本次用户授权后解除。随后字号问题已按用户确认在 Phase 6 恢复。

## 2026-09-29：Target Mode Phase 4 — UX-5 COMPLETE / PASS

- 本轮真实 Provider 未调用；D4 仍 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED。Phase 1–3 已完成提交、推送与 Runtime 核验。
- 完成条件：全新虚构空库，由没有历史上下文、源码/设计文档或点击路线的独立 Fresh-Eyes 自行完成 Project→资料→Wiki→Employment/Person→Opportunity→Resume/版本→Submission→Communication→Interview→找回资料/历史。实际阻断先复现、修复、回归与独立复验；非阻断偏好不扩建。通过前不恢复 D4。
- 隔离环境仅 TestProvider 与内存 SecretStore，外网阻断；确定性假结果用于核验审批和资料链，不能冒称真实 AI 质量。正式库不用于盲审。
- 首次入口版本不匹配来自隔离服务自定义 build_id，与产品代码无关；恢复为匹配前端的 build_id 后，空库实际页面握手通过。Fresh-Eyes 随后发现空项目页中央新建按钮无响应，左侧加号可用；同根因静读也见于任职空态。修复前验收条件：两页中央和左侧入口均打开相应表单，取消不创建资料；先以真实 Chrome 测试复现，再最小修复并请盲审复验。
- 测试先行：真实 Chrome 四入口测试修复前 2 failed / 2 passed，修复后 4 passed；中央与列表入口共用显式动作绑定，取消不写入。独立代码审查 PASS；提交候选独立 checkout 的同四项亦通过。
- 独立 Fresh-Eyes 完整盲审 PASS：自拟空库资料，经 Project/Raw/Wiki、任职/人物、机会/简历/命名版本、投递、沟通、面试准备，再找回原文/沟通/准备/Wiki 历史。中央项目与任职入口另在空库复验通过。中途隔离服务连接中断，恢复同一数据库后读回成功，不计为产品数据丢失。证据 `/tmp/career-ux5-blind/report.md` 及 16 张截图。冻结简历 JSON 与部分术语仅列非阻断阅读困难；PDF 内容、真实模型、模拟面试等未在该盲审验证，不扩大 PASS 范围。
- 全量 525 passed；14 组 frontend tests、typecheck、临时 build、secret scan、Markdown links、diff check 通过。未调用真实 Provider；Git `304425a` 已 push main；正式 Runtime 已受控更新至 PID 5036、AI_ENABLED、仅 127.0.0.1:8765。schema/data identity/业务行数/全部 operation metadata 不变，验收构建、正式静态文件与 HTTP hash 一致，DeepSeek/Tavily 增量 0/0。源码包含该提交加保留的用户旧 Resume hunks；证据 `.career-runtime/target-phase4.json`。UX-5 已满足恢复 D4 Preview 的前置条件，真实调用仍必须停在 Hard Gate 2。

## 2026-09-29：Target Mode Phase 3 — Resume AI Privacy DTO COMPLETE / PASS

- 本轮真实 Provider 未调用。完成条件：从空 DTO 逐层添加白名单字段；Profile 仅区存在与固定字段名，不含真实值；未知键、未知嵌套值与其它机会资料不得进入 Provider-ready payload；实际捕获 Preview 与发送请求，覆盖姓名/电话/邮箱/微信/地址、裸值、恶意字段名；保留正常字段建议、逐条确认和过期保护。本批不扩大职业资料检索范围，不执行真实 Provider。
- 用户旧 Resume hunks 保持；本批在独立构造模块、出站校验、当前 AI 包构造函数的非重叠位置实施，精确检查与暂存。涉及默认 Profile 的保证不等同于自动识别用户主动写入经历正文的任意个人信息，不能以正则扩展这项承诺。
- 测试先行：包构造测试先证明 Profile 原值已进入 packet；中文/英文 × TestProvider/真实适配器捕获的 4 例先在实际发送边界检出姓名，再全部通过。Preview 与捕获请求相等，未触网；正常字段表达与来源 ID 保留。独立代码审查 PASS。全量 521 passed，14 组前端测试、typecheck、临时 build、secret scan、Markdown links 与 diff check 通过；独立提交候选聚焦 30 passed。浏览器 Preview Fresh Check PASS：实际弹窗不含原稿姓名/电话/邮箱/微信值，技能与当前机会资料保留，关闭后原稿未变；没有确认发送。最初 LOCAL_ONLY 阻止准备属隔离环境配置，改为注入 TestProvider 的 AI_ENABLED 并继续阻断真实发送/外网后通过。证据 `/tmp/career-privacy-fresh/`。Git `f9b4315` 已 push main；正式 Runtime 已受控更新至 PID 2470、AI_ENABLED、仅 127.0.0.1:8765。静态文件与验收临时构建/HTTP hash 一致，schema/data identity/业务行数/operation metadata 不变，DeepSeek/Tavily 增量 0/0。源码为该提交加保留的用户旧 Resume hunks；证据 `.career-runtime/target-phase3.json`。

## 2026-09-29：Target Mode Phase 2 — UX-4 COMPLETE / PASS

- 本轮真实 Provider 未调用；D4 仍 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED。
- 完成条件：Opportunity→Resume 保存→返回识别同一工作稿→Submission→Communication→Interview→Preparation 连续可用；阶段变化后沟通/面试历史可达；已结束不恢复新建/推进；刷新回读冻结投递且后改工作稿不覆盖它；完整浏览器链、独立审查、Fresh-Eyes 与全量回归通过后精确提交并更新 Runtime。
- 已复现：轮次级 research-patches 404；面试/Offer 的普通沟通被阶段拦住；canonical 机会 ID 读取 state 丢失投递材料。新增测试先失败再实现修复。研究建议改从既有机会接口读取并限定本轮，无新增领域实体或 schema。
- 当前实现从所属机会接口读取保存状态；详情读取包含冻结投递材料；普通沟通支持 active submitted/interview/offer，ended 仍拒绝新增。独立审查发现切机会读取失败时会将上一机会资料显示在新标题下，已用真实 Chrome 先红后绿修复：成功 owner 匹配且全部结构校验通过后才发布详情，失败只显示当前标题与重试。
- 完整真实 Chrome UI 链和独立 Fresh-Eyes 主链均 PASS：创建/保存稿、命名版本、投递、沟通、面试准备、刷新找回；后改草稿的冻结 Submission JSON 与 PDF 字节不变，隔离库 AI operations=0。盲审仅记录冻结简历当前以 JSON 展开不够直观，未阻断找回，本批不顺带改排版。证据 `/tmp/career-ux4-full-chain/`、`/tmp/career-ux4-fresh/`。
- 当前工作区全量 516 passed；14 组 frontend tests、typecheck、临时 build、pip check、npm dependency check（既有 extraneous）、secret scan、Markdown links、diff check 通过。独立审查复核 PASS；独立提交候选全量 515 passed（不含用户旧额外测试），14 组前端测试及 typecheck 同样通过。用户旧源码/测试/AGENTS 哈希不变，README 仅本批新增段纳入。Git `3d02af1` 已 push main；正式 Runtime 已受控更新至 PID 556、AI_ENABLED、仅 127.0.0.1:8765。11 个 dist 文件与临时构建和服务实际响应 hash 一致；schema v6、data identity、ID/revision manifest、44/217/203 行数和全部 operation metadata 不变；DeepSeek/Tavily 增量 0/0。运行源码包含该提交加保留的用户 Resume 修改；证据 `.career-runtime/target-phase2.json`。

## 2026-09-29：Target Mode Phase 1 — COMPLETE / PASS

- 本轮真实 Provider 未调用；D4 继续 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED。最新用户授权按 Phase 1–10 连续推进；普通代码批次允许精确 commit/push main 与受控 Runtime Update，仅在 handoff 六类 Hard Gate 停止。旧 execution 中逐批另行授权的停止描述不覆盖本轮。
- 完成条件：一级仅 Wiki / 机会 / 项目 / 任职；已有 ResumeDocument 在任何阶段从所属机会打开；无稿只沿用合法创建规则且不自动创建；原编辑器、版本、PDF、选材、AI Proposal、Submission 冻结与旧 deep links 保留；用户旧 hunks 可独立保留。Phase F 的创建简化/复制/命名版本完整目标未因此宣称完成。
- 独立代码审查与 Fresh-Eyes 已完成。盲审实际走通已有稿编辑虚构技能、保存后刷新/后退回读、历史版本、返回所属机会、已投递稿、无简历分支；发现 shell 标题错误及 owner 独立网格行导致纸面遮盖，已先复现并修复，独立复验通过。修复只在 workspace/resume-workspace，不修改 protected legacy 编辑器。PDF 下载有 UI 成功提示；IAB PDF 预览空白，保留 NOT VERIFIED，不以下载提示冒称预览内容通过。
- 验证：全量 pytest 509 passed；12 组前端测试、typecheck、临时 build、secret scan、Markdown links、git diff --check 通过。修复后导航测试再次通过；独立提交候选 checkout 全量 508 passed（未包含用户旧 Resume 额外测试），12 组前端测试与 typecheck/build 也通过；证据保存在 `/tmp/career-target-phase1/`。截图/盲审报告为本机虚构证据，不进入 Git。
- Public 与 Feishu 最新覆盖已写回长期模型；正式用户数据、Secret、本地资料仍不得进入 Git。Feishu 本轮不开发，未来仅依现有 lark-cli 单向读取，登录身份与 Resume 联系人隔离。
- 开工 Git 为 `1eda69ed46d839fbf1144ec0d6ed994ee328543f`，fetch 后 HEAD/main/origin/main 一致。正式服务 PID 43209；health/quick_check=ok，schema v6、data instance、44/217/203 行数及 ID manifest 与既有基线一致；25 operations，22 dispatched。正式服务尚未加载 UX-3 与本批导航；提交后的 Runtime 核验完成前不宣称加载。
- Git `036f59c` 已精确提交并 push main。正式 Runtime 已受控更新至 PID 96335，AI_ENABLED，仅监听 127.0.0.1:8765；11 个正式静态文件与验收临时构建及 HTTP 实际返回逐字节一致。schema、数据实例、ID/revision manifest、业务行数和全部 operation metadata 与更新前相同；DeepSeek / Tavily 增量 0/0。Runtime 使用该提交加保留的用户 Resume 修改，不能等同纯 Git HEAD；本机逐文件证据 `.career-runtime/target-phase1.json`。UX-3 与导航本批已正式加载；UX-4 开始。
- 所有权：既有 protected 文件开工哈希一致；frontend README 只收本批导航文案与模块/测试说明，原 PDF/Profile 两段保持未暂存；其余早期 Resume 源码/测试、AGENTS 与本机 Agent/Skill 不纳入。本轮不修改正式 schema 或业务资料。

## 2026-09-29：UX-3 COMPLETE / PASS

- 用户已通过 UX-3 V4 的 Project、Employment Active、Employment Ended、Person 四张隔离截图；随后确认 Project 最近 Wiki 只能标为“最近更新”，Employment 只能使用自身非空 focus。空 focus 显示“还没有填写当前重点”，Wiki 仍留在“当前理解”中。Person 与样式未修改；没有变更 Domain、API、schema 或对象关系。
- UX-3 使用虚构隔离数据；前端 11 组测试、全量 pytest（509 passed）、typecheck、/tmp build 与 git diff --check 均通过。本轮真实 Provider 未调用，DeepSeek / Tavily outbound 增量为 0 / 0；没有正式 Runtime Cutover。
- UX-3 COMPLETE / PASS。D4 继续 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED；UX-4 未开始。

## 2026-09-28：UX-2 COMPLETE / PASS

- 保留现有页面结构，只做用户要求的减法。Opportunity 列表去掉每行重复的阶段日期；提醒日期使用“今天 / 明天 / 26年9月30日”等表达，今天和逾期才用克制强调；阶段以 6px 弱色点配可读文字，仍低于公司/岗位与“下一步”；空态“添加第一个机会”仍是已绑定打开新建表单的按钮，并以链接样式明确可点击。
- Wiki 首页把正文移到对象名、类别/日期 metadata 前；日期改成“今天 / 昨天 / 9月28日”，来源标题去除重复日期，长期认知不重复显示对象名。Wiki 历史保留“当前 / 之前的变化 / 首次记录”，当前正文维持焦点；时间使用两位年份与分钟，来源变成低权重标题链接。
- 用户已通过四张 1280×720 隔离 Career 截图及 Shared Visual Foundation：Opportunity Empty、Opportunity Populated、Wiki Home、Wiki History 均 PASS。A/B 使用同一隔离标签、视口和 `53743` 地址；页面骨架一致。A/B 作为本轮会话内图像呈现；C/D 文件为 `/tmp/career-ux2/final-review/C-wiki-home.png`、`/tmp/career-ux2/final-review/D-wiki-history.png`。
- 截图服务使用 LOCAL_ONLY、禁止 TestProvider 调用并拦截外网 socket。本轮截图服务已关闭，正式数据库与 Runtime 未触碰，没有调用 DeepSeek/Tavily，也没有 commit/push。
- UX-2 聚焦后端回归 124 项、全量 pytest 509 项、全部 10 组前端测试均通过；typecheck、`/tmp/career-ux2-closeout/build` 临时构建、pip check、npm ls、secret scan、Markdown links 与 `git diff --check` 通过。临时构建未覆盖正式 `frontend/dist`。
- Fresh-Eyes 自查：机会列表可直接先读“北辰创新 · 解决方案顾问 / 确认下一轮安排”，公司岗位与下一步自然突出，阶段色点可扫读；Wiki 首页回答是“红色原型改为下周一交付”；历史页能直接区分当前改为红色原型下周一交付，以及之前的蓝色原型周五交付和内部评审版本。虚构数据没有今天或逾期日期，因此截图不显示紧急色。空态按钮已在隔离页面实际点击并打开表单，随即关闭，没有保存或新增数据。
- Git 主提交 `f157cdbfaf9c6e6a2a1a45e3923110deb7e58538`（`Refine Career workspace visual hierarchy`）已 push；HEAD = main = origin/main。精确提交仅含 14 个 UX-2 文件。
- 正式 Runtime 已从 PID `55437` 受控切换为 `43209`，使用 `AI_ENABLED`，仅监听 `127.0.0.1:8765`。工作树仍 dirty；运行时代码清单为 103 个文件，manifest SHA-256 `b5fad1ce913b90a17571d3126cd0cc9a151105f80a60d7ff40a3fff3cd062e1d`。它包含已提交 UX-2 与用户保留的 Resume 源码改动，不等于 Git HEAD。
- 正式 `frontend/dist` 共 11 个文件，SHA-256 manifest `19b23d2018bc53d1aab0ee3201f2e0b8d45ae107ff149ba0235f9943430eea40`；与临时构建逐文件一致，服务实际返回的首页及引用资源也与 dist 一致。
- Runtime health=ok、SQLite quick_check=ok、schema v6；数据实例、业务行数和 ID manifest 与重启前一致。DeepSeek/Tavily outbound 增量均为 0。Opportunity / Wiki 用户验收版本已正式加载。
- UX-1、UX-2 均 COMPLETE / PASS；UX-3 READY。D4 仍为 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED；本轮没有恢复 D4 smoke。


## 2026-09-28：Checkpoint 导航断言授权修正，进入最终 Git / Runtime 收口

- 用户明确批准 `tests/test_t15_navigation.py` 中“职业 Wiki”→“Wiki”的单行断言作为 checkpoint compatibility test update。工作区原本已经是正确的一行，本轮未重写文件；仅把该行相对 HEAD 的差异加入 index。修改前 hash `f1438fca98b291db413f498243b8381e7913e8ff066539b4ee1d20468640a1b8` 与修改后完全一致，其余字节不变。
- 解除前节受保护测试依赖阻断；checkpoint 精确范围为原 34 个文件加这一行，README 仍仅追加 7 行。其余 12 个旧 Resume 文件、AGENTS unknown hunk 与 Agent/Skill 本机资料不纳入提交。
- D4：SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED；UX-1：用户 UI、机器核验及生命周期 COMPLETE / PASS；UX-2：NOT STARTED，Git/Runtime 全部核验完成后 READY，不自动进入。
- 真实 Provider 本轮未调用。提交前重跑当前工作区及独立暂存 checkout 回归；commit/push 后才执行正式 Runtime Update。实际测试结果、Git SHA、PID、working-tree source/dist manifest 与安全核验写入 `.career-runtime/cognition-ux-checkpoint.json`；不得把 dirty runtime 说成 SOURCE=GIT。


## 2026-09-28：Checkpoint 暂存完成；受保护导航测试依赖阻断 commit

- 真实 Provider 本轮未调用。D4 保持 SYNTHETIC READY / REAL SMOKE PAUSED / NOT YET PASSED；UX-1 功能与用户 UI COMPLETE / PASS；UX-2 NOT STARTED，Git/Runtime 收口尚未完成，不启动下一批。
- 已精确暂存 34 个 D4 + UX Review/UX-1 文件；README 只追加 7 行，旧 36,748 字节与保护副本完全相同，92 个保护文件 hash 不变。未暂存 AGENTS、其余旧 Resume 文件或本机 Agent/Skill/dist/runtime。cached name-status/stat/check 已核对。
- 当前 working tree：聚焦 74 passed，全量 509 passed；全部前端测试、typecheck、/tmp build、pip check、npm ls、secret scan、Markdown links、diff check 通过。暂存独立 checkout：前端测试/typecheck/build 通过，但全量 **507 passed / 1 failed**。
- 精确阻断：`tests/test_t15_navigation.py:10` 在 HEAD/index 仍断言 `"wiki", "职业 Wiki"`，HEAD 与当前 `frontend/src/workspace.ts` 均已使用 `"wiki", "Wiki"`。该测试工作区已有的唯一修正为上述断言改成 Wiki，属于用户明确保护的旧 hunk。本次不能擅自stage；不能以跳过测试、加入无用途兼容字符串或回退正式导航来伪造通过。
- 依赖完整的 D4/UX 代码边界已解决；剩余仅是这条受保护测试断言的提交范围。需用户明确允许该一行进入 checkpoint，才可满足“checkout 后代码完整且全量通过”。目前保持原文件不变、该 hunk 未 stage；未 commit/push。
- Git HEAD/main/origin/main 仍为 `6b32ce4fc98187fe1d4614a33f5d3d7d2c0a0acf`。正式 Runtime 仍 PID `16242`、旧 working-tree source manifest `e0be5942a701b3f27bbc866ca5d9c3e1b7ed79d9824b6e63f90f3f99c2725607`。按用户“Git收口后再更新Runtime”的顺序，本轮尚未正式build/restart；最新过期提示仅已隔离验收，未宣称正式加载。


## 2026-09-28：Cognition foundation + recoverable AI UX checkpoint

- 用户批准把已完成 synthetic/自动测试的 D4 基础实现、UX Review、UX-1 与必要共同代码作为一个依赖完整的 checkpoint 收进 Git。解除上一节的提交范围阻断；不拆成无法独立运行的 Phase commit。
- **D4：SYNTHETIC READY；REAL SMOKE PAUSED / NOT YET PASSED。** 本 checkpoint 包含 Cognition 基础实现，但正式 Cognition 未完成真实验收，不能标 COMPLETE。本轮真实 Provider 未调用，不能用 Git 提交代替真实 smoke。
- **UX-1：COMPLETE / PASS。** 用户 UI 与机器核验 PASS；关闭/切页/刷新不取消后端生命周期，恢复原 operation/Proposal；本次 TestProvider 恰好一次 dispatch、无重复发送，审批状态正确持久化。失败与结果未知分离，Preview 过期显示“尚未发送”。既有隔离测试业务数据已清理，审计保留。
- **UX-2：NOT STARTED。** checkpoint/push 与本次受控 Runtime 更新全部通过后为 READY，仍须另行启动；D4 smoke 不恢复，不进入 D5。
- Ownership：33 个 D4/UX 文件整文件纳入，`src/workbench/README.md` 仅纳入 D4 追加段落。README 旧 36,748 字节与 `/tmp/career-src-workbench-readme-pre-d4.md` 完全一致；13 个用户旧 Resume 文件、AGENTS.md 原 4 行、本机 Agent/Skill 文件保持。无 git add .，无混入本机 dist/runtime。
- 验证采用两层：当前工作区执行 D1–D4/UX-1 聚焦、全量回归和前端/安全检查；暂存导出的独立 checkout 再验证，确保代码不依赖未提交 Resume 改动。最新执行结果与文件级证据保留于本机 `/tmp/career-cognition-ux-checkpoint/`。
- Git checkpoint 提交时，正式 Runtime 仍为 PID `16242` 的旧 working-tree baseline。按用户批准流程在 commit/push 后执行正式 Runtime Update，运行结果、实际 Git HEAD、dirty source manifest、dist manifest 统一记录到本机 `.career-runtime/cognition-ux-checkpoint.json`，不把未知后续运行结果提前写成已完成，也不为更新文档再重启。
- Runtime 源码继续包含 Git checkpoint **加 13 个未提交 Resume 源码/文档改动**，AGENTS 等本机资料不参与运行；不得声称 SOURCE=GIT=RUNTIME。正式更新保持 AI_ENABLED、127.0.0.1:8765、schema v6；只做白名单 metadata/健康/静态资源核验，不做 DeepSeek/Tavily smoke。普通 build 始终输出 `/tmp`。


## 2026-09-28：UX-1 用户复验与机器核验 PASS；Git 收口 BLOCKED

- 用户已确认真实隔离 UI 链：让 AI 整理→立即关闭→切机会→刷新→AI→原对象→继续→原 Wiki Proposal。无需再让用户重复该验收。真实 Provider 本轮未调用；D4 smoke 继续暂停，未进入 UX-2。
- 机器证据：`/tmp/career-ux1-recheck` 中唯一 operation `ai-operation:d2da215d-c6b5-4ab5-820c-79777abf2ea9` 为 succeeded，dispatch 于 00:15:18，完成于 00:15:36（北京时间）；唯一 Proposal `wiki-compiler-proposal:ac863c45-e63f-4ea5-a52c-e1c3bd401e33` 的 operation_id 正是该 ID，唯一 Patch pending，持久化进度 0/1。`ai_call=1`、`ai_audit=5`，没有第二次发送或 Proposal。两次 preparation 均在发送前，最早一份已过期；最近准备于 00:15:15，发送和恢复以后没有新 preparation。
- 审批持久化证据不越权代用户审批：本次用户只恢复，保留 0/1；此前 Fresh-Eyes 接受后为 resolved/accepted；真实 HTTP 断连回归中接受一条后，新客户端恢复进度 1/2。六状态、预览过期≠AI失败，以及前端不决定操作存活的边界已冻结到[长期模型正式规格](../target/long-term-career-model.md#ai-操作状态与恢复ux-1)。
- 隔离清理完成：`career-ux1`、`career-ux1-fresh`、`career-ux1-user`、`career-ux1-recheck` 四套明确虚构数据库的 Project/Raw/Wiki/Proposal/业务request/revision/prepare/结果副本均删除，残留业务对象为 0，quick_check 均 ok；保留原 operation、dispatch slot、ai_audit/ai_call，未改写其状态。测试服务已停止；metadata证据 `/tmp/career-ux1-closeout/isolated-evidence-metadata.json`，清理记录 `/tmp/career-ux1-closeout/cleanup-metadata.json`。不读取或删除正式职业正文。
- 自动回归：UX-1 + D1–D4 聚焦 **74 passed**；全量 pytest **509 passed**；全部 8 组前端测试、typecheck、`/tmp/career-ux1-closeout/dist` build、pip check、npm ls（既有 extraneous）、secret scan、Markdown links、git diff --check 通过。正式 frontend/dist 未被测试覆盖。
- 正式健康：PID `16242`，health/SQLite quick_check=ok、schema v6、data instance `42ff565e28a08e31414442521540ac3e`；current/records/revisions `44/217/203` 与 ID manifest `4e91cd541a4fdf67ef106a8f1cbfab5574e931d0785a3189838339b372b249c1` 不变。全部 operation ID/task/state/dispatched_at 与 UX-1 前基线相同，DeepSeek/Tavily 新增 **0/0**；未读取、显示或记录 Secret。
- Runtime 区分：用户本次验收的是隔离 `53693` + `index-pKPz6fi6.js`；正式 `8765` 仍运行上次 PID `16242` 的 dirty working-tree baseline，主 JS `index-D_1mFyyV.js`，source manifest SHA `e0be5942a701b3f27bbc866ca5d9c3e1b7ed79d9824b6e63f90f3f99c2725607`。正式尚未加载后续预览过期分类和“AI进度”文案修复；不能宣称正式Runtime已验收该最新版本。本轮未重启。
- Git ownership：13 个旧 Resume 文件、AGENTS.md、Agent/Skill 本机资料共 92 个保护文件相对 UX-1 开工 SHA 完全一致；AGENTS 仍保留原 4 行 unknown ownership。无新增未知 tracked diff。UX Review/UX-1 与 D4 的修改可识别，但部分存在提交依赖，不是可以直接整文件stage的独立文件。
- **Git BLOCKED 原因**：`frontend/src/wiki-semantic-bindings.ts` 中 UX-1 的 `startCognitionCompiler` 处理/过期/恢复改动依附于 HEAD 尚不存在的 D4 函数；Cognition 恢复还依赖 `wiki-semantic-ui.ts` 的 D4 展示函数、`compiler.py` 的 D4 context_kind/selected_experiences 与审批分派，以及未提交的 `wiki/cognition.py` / app router。提交完整函数会带入 D4 实现；仅提交可分离的公用部分则会留下已验收 UX-1 的 Cognition 集成未提交。此次授权只允许 UX Review/UX-1，故没有把 D4 实现偷带入 commit，也没有为凑提交重构当前已验收代码。
- 未 stage、commit、push。HEAD/main/origin/main 仍为 `6b32ce4fc98187fe1d4614a33f5d3d7d2c0a0acf`。工作区剩余：UX Review/UX-1 待收口、既有 D4 实现/测试/文档、13 个旧 Resume 改动、AGENTS 4 行未知改动及本机 Agent/Skill 文件；generated dist/runtime 继续忽略。须先明确 D4 依赖的 Git 基线收口范围，才能整体提交 UX-1。**UX-1 功能/UI/机器检查通过，整体仍 BLOCKED；UX-2 NOT READY。**


## 2026-09-27：UX-1 用户验收 FAIL — 预览过期诊断与修复，继续 BLOCKED

- 真实 Provider 本轮未调用，DeepSeek/Tavily 增量 0；D4 smoke 继续暂停，不进入 UX-2。正式 Runtime PID `16242` 仍为上一轮 working-tree baseline，本轮未重启、未覆盖正式 frontend/dist。
- 旧隔离现场 `127.0.0.1:63127` 保持原样。operation `ai-operation:4369933d-6ea2-4d91-b99a-4dab5c28cf09`、task `wiki_compiler`：准备时间 22:49:26，到期 22:59:26，用户确认时间 23:27:20（北京时间）。confirm 进入 reserved 后约 4ms 因 Missing“准备对象已过期，请重新预览”终止为 failed。dispatched_at/result_ref 均 null，dispatch slot 无占用，Provider/Proposal/结果记录均 0。数据库完整文件 SHA 与只读诊断前一致。
- 根因 G：10 分钟 Preview 已过期，尚未进入 Provider；叠加 E：状态投影把发送前的过期错误误报成 AI 执行失败。没有证据指向关闭弹窗、TestProvider 返回、Proposal 保存或读错 operation。上一轮交付过早准备 Preview 且没有到期提示，造成真实验收失败；旧 Fresh-Eyes 成功不能覆盖本次失败。
- 修复：保留有效期与严格确认；为过期添加固定 code `prepared_request_expired`，旧未 dispatch 的精确 Missing 过期记录也只读映射为准备中，不改旧审计。Wiki/Cognition Preview 到期即时收起发送按钮，显示“预览已过期，尚未发送”和手动重新预览；点击确认及服务端仍复查，无自动 prepare/retry。计时器不会覆盖已经处理中的操作或已保存建议。顶部改“AI 进度”，失败卡片减为“整理 Wiki失败 / 没有修改资料。”。
- 未改后端执行模型。真实 HTTP 断连测试已证明：Provider 被阻塞时关闭原客户端 socket，随后放行 Provider，原服务端线程仍保存 Proposal；新连接读取待处理、同 operation/Proposal、审批后进度 1/2，且只有一次 dispatch/preparation/Proposal。进程退出仍按既有 recover：发送前中断失败，发送后中断结果未知，不自动重试，不承诺进程崩溃后继续计算。
- 测试先行：只读复现旧场景状态误报；新增过期 API 回归先因缺少 code 失败，修复后通过；新增真实 Uvicorn/HTTP 断连时序与前端到期/状态文案测试。首次全量 508 passed / 1 failed，失败是 STATUS 顶部缺少既有 release-readiness 要求的真实 Provider 未调用声明，现已如实补充；最终重跑 **509 passed**。全部前端测试、typecheck、临时 build、secret scan、文档链接、git diff --check 通过。
- 用户重验使用全新隔离库和 TestProvider，旧失败库不删除、不重发、不修状态；全量回归完成后新建 `/tmp/career-ux1-recheck/isolated-data`，端口 `53693`，项目“UX1 恢复复验项目”；只连接 TestProvider，外网连接拦截，无真实凭据，使用 `/tmp/career-ux1-diagnosis/dist` 新临时构建。新 Preview 未由 Agent 确认发送。UX-1 仍 BLOCKED，等待新一轮用户 UI 验收。


## 2026-09-27：UX-1 — SYNTHETIC / Fresh-Eyes / Runtime PASS，等待用户 UI 验收

- 范围：只实现 AI 状态可见、原操作恢复与对象归属；未进入 UX-2/3/4、D5，D4 smoke 继续暂停。用户层六状态及后端映射见 [UX Reset Plan §15](CAREER-UX-RESET-PLAN.md#15-ux-1-已批准实施合同2026-09-27)。没有新状态表、schema migration、自动 prepare 或重发路径。
- 实现：新增只读 AI activity 投影与顶部轻量 AI 入口；当前对象仅显示一行处理中/待处理提示。Wiki Compiler / Cognition 关闭、切页、刷新后继续原 Proposal，审批进度从后端读取；Research / Resume 保持兼容状态与所属页面入口，不重做旧界面。0 Patch 完成不形成永久待办；失败/结果未知分开；页面网络读取失败不冒充 Provider 失败。
- 测试先行：接口初始 404 与前端缺模块的失败先于实现；Fresh-Eyes 发现跨页刷新后对象名退化，接口测试先复现 KeyError，再补返回原 Proposal 冻结的最小身份。没有修改 Proposal 数据或 Provider 合同。
- 自动检查：全量 pytest **507 passed**；全部 8 组 frontend test 命令、typecheck、临时目录 build、pip check、npm ls（既有 extraneous 本机依赖）、secret scan、文档链接与 git diff --check 通过。新增覆盖处理中读取、状态恢复、四条建议已审批 2/4 后恢复、终态、stale、0 Patch、Cognition/Research/Resume 归属、只读无重复 dispatch。
- 独立 Fresh-Eyes：gpt-6-astra / high，仅隔离 TestProvider、不读源码/规格、不改代码、不给点击路线。一次发起→立即关闭→切机会页→自行找回→刷新→继续审批成功。发现的归属显示问题修复后，再在另一个既有 pending 隔离现场只读复核通过，未再次发 Provider。原始报告 `/tmp/career-ux1-fresh/report.md`。浏览器权限/可用性限制曾改用原生 Safari，复核边界已在报告记录。
- Runtime Update：正式 PID **91171 → 16242**，正式启动方式、保持 AI_ENABLED，只监听 `127.0.0.1:8765`。先构建 `/tmp/career-ux1/runtime-build`，再明确更新正式 `frontend/dist`；11 个文件与临时构建及服务实际返回逐文件 hash 相同。主 JS `index-D_1mFyyV.js`。
- Git HEAD/main/origin/main 仍为 `6b32ce4fc98187fe1d4614a33f5d3d7d2c0a0acf`。Runtime 是本轮 **dirty working-tree baseline**，包含 D4/UX-1 与既有 Resume 源码；不能称 SOURCE=GIT。110 个运行/构建输入文件 manifest：`/tmp/career-ux1/runtime-source-manifest.json`，SHA-256 `e0be5942a701b3f27bbc866ca5d9c3e1b7ed79d9824b6e63f90f3f99c2725607`。
- 正式健康：health / SQLite quick_check 均 ok，schema v6；data identity `42ff565e28a08e31414442521540ac3e` 不变；current/records/revisions `44/217/203` 不变；ID manifest `4e91cd541a4fdf67ef106a8f1cbfab5574e931d0785a3189838339b372b249c1` 不变。全部 operation ID/task/state/dispatched_at 与开工快照相同，**DeepSeek/Tavily 本轮增量 0/0**。只用白名单 metadata 健康检查；未读取、显示或记录 Secret。
- D4 现场：原 Proposal `47edc08e…` 仍 pending、原 operation `a8d2e4e5…` 仍 succeeded，正式 Cognition 仍 0；新恢复接口显示待处理、0/1、两段经历归属。没有审批、删除、替换或重新调用。
- Ownership：与本轮开工 SHA 快照逐文件比对，13 个旧 Resume 文件、AGENTS.md 与 Agent/Skill 本机文件共 92 个保护文件逐字节未变。UX-1 只改计划/本 STATUS、独立 AI activity 模块与测试、main 接入、Wiki UI/接口恢复、局部样式、package 测试入口及 Wiki 模块 README；D4 既有改动继续隔离。没有 stage、commit 或 push。
- 用户验收：独立虚构库 `/tmp/career-ux1-user/isolated-data`，`127.0.0.1:63127`，同一正式 dist、TestProvider 模拟延迟、外网连接拦截、无真实凭据。已打开“UX1 隔离验收项目”的 Preview，尚未确认发送；等待用户完成发起→关闭→切页→刷新→全局入口恢复。正式 D4 不用作重新发送测试。**UX-1 暂不 COMPLETE/PASS；UX-2 NOT READY。**


## 2026-09-27：Career UX Reset — 审查与计划，D4 smoke 暂停

- 用户要求系统性审查信息架构、页面层级、文案、视觉与 AI 反馈；本轮真实 Provider 未调用，不继续 D4 smoke、不进入 D5、不修改业务代码。D4 底层实现保留，既有待审建议不处理。
- 白名单 metadata 复核：D4 DeepSeek dispatched 累计 `3`，较前节基线新增 `1`（用户上次点击后）；最新 operation `a8d2e4e5…` 为 succeeded，约 4 秒完成，关联 Proposal `47edc08e…` 为 pending。正式 Cognition `0`；Tavily dispatch `7`。没有 reserved / dispatching / outcome_unknown；failed 历史操作保留。当前 health / quick_check 正常、schema v6，正式 Runtime 未重启。
- 独立 Fresh-Eyes 使用 `gpt-6-astra / high`，不继承本讨论、不给产品规格/源码/既往抱怨或点击路径；使用隔离空库和 TestProvider、25 秒模拟延迟。隔离服务不读取正式数据或 Keychain，外部连接被拦截。最初 LOCAL_ONLY 导致 prepare 被拒、一次重启中断保存，已明确排除为测试环境干扰，不能算产品问题。
- Fresh-Eyes 已完成真实UI审查：独立项目、资料、任职/人物、关系、机会/简历、TestProvider建议、关闭后找回、完成后刷新、来源和历史均有操作证据；长期认知找到但未生成，面试内部被404阻断，处理中刷新未验证。原始报告见[独立盲审](../audit/2026-09-27-career-ux-fresh-eyes.md)。主Agent复核AI容器不一致、直接资料与可引用来源混用、面试接口路径不一致，全部仅记录，未修改代码。
- 收尾：隔离审查服务已停止；正式 D4 operations / Proposal metadata 前后完全一致，Cognition仍0、本轮DeepSeek/Tavily增量0/0。文档链接及diff空白检查通过；逐文件hash确认除本STATUS外所有既有tracked文件未改变。本轮仅新增计划及审查报告，未stage/commit/push；UX实施等待审阅，D4仍暂停。
- 方案正本：[CAREER-UX-RESET-PLAN.md](CAREER-UX-RESET-PLAN.md)。这是待审计划，不是已实现的新规范；审批前不重写已确认目标模型。新增计划与本 STATUS 是本轮文档改动，原 D4/Resume/AGENTS/本机配置保持隔离。

## 2026-09-27：D4 旧 Proposal 终结与第二次 smoke Preview — 等待用户确认

- 旧 pending Proposal 并非来自上一轮 `invalid_result`：它关联的真实 D4 operation 已成功，选了 3 段经历，其中包括 A/B 和另一段虚构经历；invalid-result operation 没有创建 Proposal。为避免把不同范围的旧建议混入本次只选 A/B 的验收，系统将旧 Proposal 和其 1 条 Patch 标为 `superseded`，原因码为 `smoke_scope_replaced`。没有设置用户拒绝决定、没有写入 Cognition；关联 operation 保持 `succeeded`，原 85 条 AI 审计行前后不变。
- 第二次 smoke 起始基线：D4 DeepSeek outbound 总数 `2`，Tavily 搜索 dispatch 总数 `7`，Cognition `0`，pending D4 Proposal `0`。A/B Project revision 均为 `1`，各有一条当前 Wiki revision `1`；只在内存计算的 Context DTO / manifest SHA-256 分别为 `4c7a9da10528799b9d34fdddffc69339cbac2ec8d077b36cfdf81927c128a267` / `690ee99346d579e57c82953f3e376bfedf5e693bc7e15d5ba59da321bd14deb2`。
- 本轮真实 Provider 未再次调用；第二次 smoke 只停在用户确认前的 Preview。
- Career 页面已重新准备一份新的 D4 `ai_preparation`（`prepared`，不是 Provider operation；真实 operation 只会在用户确认时创建）。它的两个来源恰好是 A/B Wiki，manifest 恰好是 A/B Project 与各自 Wiki；UI 当前显示 A/B 两段实际 Wiki 内容与“不会读取原始资料”。confirm 前 DeepSeek 增量 `0`、Tavily 增量 `0`；未点击“让 AI 整理”。本轮 A/B 与 Wiki 没有修改。
- 正式 Runtime 未重启，仍是已验收的 PID `91171`，`127.0.0.1:8765`、`AI_ENABLED`。白名单健康脚本 `/Users/frog/Projects/Career/scripts/runtime_health_check.py` 只读取 `/healthz` 与 schema、行数、数据实例标识、ID manifest hash；不请求 `/api/state`，SQLite 查询不读取 `body` 列。回归测试通过 SQLite authorizer 禁止读取 `body`，并植入 Profile / Resume / Person / Raw 虚构哨兵。此前一次宽泛状态检查的工具输出包含 Profile 联系字段，但没有在聊天中复述；本轮没有再读取这些字段，也没有读取 Secret。
- 检查：D1–D4 聚焦测试 `42 passed`；修正文档回归断言后，全量 pytest `501 passed`。文档链接、`git diff --check`、secret scan、`pip check` 均通过；`npm ls --depth=0` exit 0，只有既有本机 extraneous 包。未执行正式 build 或重启，避免无关改变 Preview Runtime。
- 最近健康检查：health=`ok`，SQLite `quick_check=ok`，schema v6，data instance=`42ff565e28a08e31414442521540ac3e`；`current / records / revisions` 为 `44 / 208 / 203`，ID manifest SHA-256=`c6110440f7f32e5bfb3d957b8b3f60f529e19c8c3adb22007931ae7bfb686993`。Git `HEAD = main = origin/main = 6b32ce4fc98187fe1d4614a33f5d3d7d2c0a0acf`，working tree dirty；未 stage、commit 或 push。D4 虚构数据保留，未进入 D5。

## 2026-09-27：Phase D4 Cognition — SYNTHETIC READY

- 建模：Cognition 是 Wiki 的 `cognition` scope，复用 schema v6 的 `current` / `revisions`、typed `source_refs`、现有 Proposal 与逐条审批；没有新表、schema migration 或第二套历史。用户选择 2–20 段 Project / Employment，未选择的经历不进入 Context。
- 发送边界：专用 DTO 仅含所选经历的 `{type,id,name}`、其当前 Wiki 的 `{knowledge_id,type,content,tags}` 和当前 Cognition 的 `{id,type,content,revision,supporting_experience_ids}`。不含 Raw 正文、Person、Opportunity、Resume、Interview、Feedback、历史 revision 或 Secret。Preview 与实际 DTO 共用数据；来源 UI 先显示经历和具体 Wiki revision，原始资料保持折叠并只在用户点击后读取。
- 跨经历与候选：本地按不同 Project / Employment ID 校验。add / rewrite 必须引用至少两段不同经历的本轮当前 Wiki；retire 至少引用一条所选 Wiki。同一 Project 的多条 Wiki 不会增加经历数。只允许 add / rewrite / retire；返回 0 Patch 是成功；pending 不写正式 Cognition；每条仍单独接受、编辑后接受或拒绝。当前输出校验拦截人格/心理诊断和伪精确评分，不产生 Resume 或 Interview 更新。
- 合成验收：全部经隔离 TestProvider 与临时数据库；D1–D4 聚焦 `61 passed`，全量 pytest `495 passed`。前端导航 8 项、本地请求 3 项、Employment/Person、Project 协作、workspace mutation、Wiki semantic、Wiki D3 回归全部通过；typecheck 通过；Vite build 输出到 `/tmp/career-d4-final-build.avzAOm`，没有覆盖 `frontend/dist`。`pip check` 通过；`npm ls --depth=0` exit 0，只有既有 extraneous 本机包；secret scan、文档链接（含长期模型目标文档）及 `git diff --check` 通过。
- Fresh-Eyes：已尝试一次只读独立 UI 观察。Subagent 没有可用隔离浏览器或已确认的 TestProvider UI 入口，未进入应用、未生成数据、未读取设计文档；因此“长期认知”理解度、来源清晰度、审批压力和 0 Patch 文案不作通过声明。当前没有真实用户 UI 验收。
- 正式环境：没有改正式 Runtime 或生产数据库；仍是 D3.5 基线 PID `83321`，`127.0.0.1:8765`、health=`ok`、运行模式沿用已确认的 `AI_ENABLED`。生产 SQLite `quick_check=ok`、schema v6，`current / records / revisions` 行数仍为 `40 / 182 / 199`。生产 `ai_call` 总数仍为基线 `19`；D4 `ai_operations=0`、D4 dispatched audit=`0`，无本轮 DeepSeek 或 Tavily outbound。未读取、显示或记录 Secret。
- 文档与 Git：长期模型、产品/上下文/架构/旅程/路线图和模块 README 已补 D4 合同及当前实现状态。`src/workbench/README.md` 原有字节前缀与 D4 修改前快照完全一致，D4 只追加独立章节。13 个用户旧 Resume 文件中其余 12 个 hash 与 D3.5 基线一致；README 因新增 D4 尾部章节而整体 hash 改变，原有 36,748 字节逐字节保留。`AGENTS.md` hash 未变；`.agents/skills/` 与 `docs/agents/` 未触碰。没有 stage、commit 或 push；Runtime 未更新。
- 判定：Phase D4 `SYNTHETIC READY`。`D4 REAL SMOKE = NOT READY`：正式 Runtime 仍未加载 D4，Fresh-Eyes/UI 验收也尚未完成。真实 smoke 需另行受控 Runtime 更新和用户 Preview 验收；本阶段不调用真实 Provider、不进入 D5。

## 2026-09-27：Post-D3.5 Runtime Cutover — PASS

- Git 基线：`HEAD = main = origin/main = 6b32ce4fc98187fe1d4614a33f5d3d7d2c0a0acf`。本次只对齐正式 Runtime；真实 Provider 未调用，没有进入 D4，也没有提交或推送新代码。开工时剩余 tracked diff 精确为 13 个用户旧 Resume 文件和 `AGENTS.md` 未知 4 行；它们与 D3.5 开工前哈希一致，`.agents/skills/` 和 `docs/agents/` 本机资料清单哈希亦未变。本节 STATUS 是本次明确归属的新增文档 diff。
- 实际源码：正式 Runtime 加载当前 working tree，不冒称 `SOURCE = GIT`。87 个受控运行源码/前端构建输入的逐文件 SHA-256 清单，聚合 SHA-256=`f1e57af5206f9c1bf55084d418bf7510b0e69644714dfcb3f67b1f51348e2051`；其中仍有 6 个用户未提交的运行输入：`frontend/index.html`、`frontend/src/editor/legacy-app.js`、`frontend/src/editor/legacy.css`、`src/workbench/profile.py`、`src/workbench/resume_documents.py`、`src/workbench/resume_pdf.py`。其余 7 个受保护 Resume 文件属于 README/测试，不是本清单运行输入；`AGENTS.md` 和本机 Agent/Skill 资料不参与 Runtime。
- 前端：先在 `/tmp/career-post-d35-frontend-verify` 完成 typecheck 与 Vite 验证 build，再明确生成正式 `frontend/dist`。两处 11 个文件路径及字节逐一相同；正式 dist 清单 SHA-256=`b3c9d8fb20201af75d4ae8b59f59e3de95ee99d702aed46392a8ff0e1d021d07`。正式 HTTP 对全部 11 个静态文件提供的字节与 dist 一致。后续普通 build 仍输出 `/tmp`，只有正式 Runtime Update 才覆盖 dist。
- 受控重启：旧 PID `70394` 经 `scripts/macos_app.py stop` 的身份验证控制通道优雅退出；端口释放后以显式 `CAREER_AI_MODE=AI_ENABLED` 和正式启动器启动新 PID `83321`。`/healthz=ok`，只监听 `127.0.0.1:8765`，运行模式仍为 `AI_ENABLED`，schema v6、SQLite `quick_check=ok`、data instance 不变。
- 数据核对：`current` 与 `revisions` 的完整内容摘要一致；`current`、`records`、`revisions` 的 ID/kind/revision 清单及数量不变（40 / 182 / 199）。`records` 完整摘要发生启动期变化；只读定位到既有 `ai_secret_operation` 清理日志的 `updated_at` 被恢复流程刷新，仍是 `manual_cleanup_required`；不属于职业业务对象、Wiki/Raw 或 Provider 调用。未读取、显示、复制或记录 Secret 值。
- D3.5 正式加载：正式入口 JS 含“保存到：”“继续处理建议”、来源标题目录及当前理解；Wiki 只读 API 在当前正式资料上返回 1 个非空来源标题，来源目录不含 Raw 正文且只引用当前可见知识。不创建任何测试业务对象，不重复用户 D3 验收。DeepSeek `ai_call` 增量 `0`、`wiki_compiler` dispatch 增量 `0`；Tavily/research dispatch 增量 `0`。Phase D4 = `READY TO START`，本次未开发 D4。

## 2026-09-27：Phase D3 / D3.5 — COMPLETE / PASS

- D3 两轮用户 UI 验收均已 PASS；D3 专属虚构测试数据已从隔离环境清理。D3.5 真实 Provider 未调用：本轮 DeepSeek outbound 增量 `0`、Tavily `0`。用户已确认此前那笔来源不明的 DeepSeek 调用由用户本人触发，本批不再调查或归类为异常。
- Fresh-Eyes：使用独立的 `gpt-6-astra` / high Subagent，刻意不提供设计文档、源码和点击路径；其在全新隔离库、`TestProvider` 下独立完成 10 项核心目标及误操作探索，不需外部提示或浏览器刷新，未改代码。发现的主要摩擦是 Wiki 来源按钮缺少可识别标题、待审建议不易找回、取消编辑误报未保存、资料保存目标不清楚，以及少量内部术语/反馈文案。没有核心任务阻断或产品模型分叉。重复同名项目、长任职页、Project 人物直达、历史时间等列为后续优化，本批不扩功能。
- D3.5 修复：来源标题只按当前可见 Wiki 的 source_refs 提供，不传 Raw 正文；Raw 行显示待审建议数量与继续入口；资料表单明确保存对象；取消建议编辑恢复原文且不触发未保存警告；保存、关联、建议生成给出更准确的即时反馈；压低内部术语。当前 Project / Employment / Person 页面和当前 Wiki 均不新增正本或历史库。
- 第二轮回归：同一 Subagent 与新 Subagent 的隔离浏览器通道均不可用，因此二者未能执行第二轮 UI 回归。主 Agent 使用另一套全新隔离库和临时前端构建，从 UI 验证来源标题、建议找回、取消编辑、资料归属、人物编辑与建议生成后即时回显；这部分证据属于主 Agent 实际 UI 回归，不冒称 Subagent 完成。全部隔离环境均无真实 Provider 凭据。
- 自动检查：D1/D2/D3 聚焦 `41 passed`，全量 pytest `475 passed`；7 组前端测试、typecheck、临时目录 Vite build、`pip check`、`npm ls --depth=0`、secret scan、文档链接与 `git diff --check` 均 exit 0。`npm ls` 只显示此前已存在的 extraneous 本机依赖。
- 隔离测试对象已清理：两套 D3.5 临时数据库、TestProvider 服务和临时前端 build 均已停止/移除；D3 专属虚构测试对象此前已清理。正式服务 health=`ok`、SQLite `quick_check=ok`、schema v6；`current` / `records` / `revisions` 的 ID、kind、revision 摘要与 D3.5 开始前逐项相同。`ai_operations` dispatch、`ai_audit` dispatch 与 `ai_call` Provider 计数增量均为 `0`。
- Git ownership：D3/D3.5 自有范围为长期模型/验收/roadmap/本 STATUS、Wiki Compiler 与 API/README、Project/Employment/Person Wiki UI、前端构建脚本及对应测试。13 个用户旧 Resume 文件和 `AGENTS.md` 未知 4 行与开工哈希逐字节一致；本机 `.agents/skills/`（77 文件）与 `docs/agents/`（3 文件）的清单摘要未变，均不纳入本批。精确提交与 push 后的 SHA 以最终 Git 核验为准。
- 正式 Runtime 仍是 D3 用户验收时的 PID `70394` 和当时的 working-tree 基线，D3.5 未覆盖正式 `frontend/dist`，也未重启正式服务。Git 收口后 HEAD 会前进，Runtime 不因此冒称已加载 D3.5；下次正式 Runtime Update 应重新建立基线。Phase D4 仅 READY，尚未开始。

## 2026-09-27：Phase D3 — 自动验证与 Runtime PASS；两轮用户 UI 验收前的历史快照

- 当前目标：让 Project、Employment 和已确认 Person 工作区直接查看各自 Raw / Wiki，并从对象页面复用 D2 同一套 Compiler。D3 不实现 D4 Cognition，不改 Opportunity 主链、Resume AI、T14 / Event / Achievement / Evidence，也没有 schema migration。
- 作用域合同：业务工作区在 prepare / confirm 显式绑定一个 `target_scope`；服务端要求它与所选 Raw 直接所属对象相同，并把它冻结进幂等意图、manifest、Proposal 与审批新鲜度校验。Project / Employment / Person 页面只读取自身当前 Wiki，Patch 只能写回该 scope。省略 `target_scope` 的原 Wiki 入口保留 D2 多范围合同。Person Raw 只能由已确认 Person 详情明确添加；普通 mention 不创建 Person。
- UI 接入：Project 显示“当前理解”后显示轻量“资料”列表；Employment 显示任职当前理解和资料；打开已确认 Person 后显示人物当前理解、关联 Project 与 Person-scope 资料。统一 Compiler 绑定处理 prepare、confirm、Proposal 与单条审批。当前理解按 Fact → Observation → Hypothesis、同类最近更新时间排序，隐藏 retired；来源和历史沿用 D1。0 Patch 不写 Wiki、不重试，用户完成提示后回原工作区。写入/审批后重新读取当前 workspace，不使用 `location.reload()`。
- 自动验证：D1/D2/D3 聚焦 pytest `40 passed`；全量 pytest `474 passed`。前端 navigation（8）、local request（3）、Employment/Person relations、Project collaboration、workspace mutation、Wiki semantic、D3 workspace 均通过；typecheck 通过。临时目录 build 成功；正式 build 后的 11 个文件与临时 build 逐字节一致。`pip check`、`npm ls --depth=0`、secret scan、文档链接检查和 `git diff --check` 通过；`npm ls` 仍显示此前已有 extraneous 本机依赖，没有修改依赖。
- 正式 Runtime：受控更新旧 PID `63058` → 新 PID `70394`；health=`ok`，只监听 `127.0.0.1:8765`。显式 `AI_ENABLED` 保持；schema v6、SQLite `quick_check=ok`、data instance `42ff565e28a08e31414442521540ac3e` 不变。旧、新 `ai_operations` dispatched=`18`，`ai_audit` dispatched=`17`，各 task 数量一致；D3 DeepSeek outbound 增量 `0`、Tavily `0`。当前正式 Provider diagnostics 为 mode=`real`、configured=`false`；本轮没有触发真实 Provider。
- Runtime 基线：HEAD = main = origin/main = `17804cfc9c1cb350d778d135c046490ceb6bc6fd`，working tree dirty。Runtime 后端与构建来源是当时实际 working tree，不是 HEAD；100 个运行源码 / 构建输入文件的 manifest SHA-256=`116984d5b3279fa2474ddc41bda6aa6ad0fdcb2dcaf3ab8230b738e1e7865719`。正式 `frontend/dist` 含 11 个文件，SHA-256 manifest=`7645608e18ca36c32b79f3a70a8529f392cacd855b5e23bd5d556878153dadb2`；HTTP 提供的 `/`、`/editor.html` 和引用资源都与构建产物逐字节相同。
- UI 验收环境：正式数据库没有新增 D3 数据。另启动隔离的 `127.0.0.1:8766` 测试 UI（PID `70553`），空白临时数据库、schema v6，Provider 是本机 `TestProvider` 的合成建议实现，无真实网络请求。页面当前停在空的“项目”列表，等待用户第一轮：创建虚构 Project、添加虚构 Raw、接受一条合成建议并验证当前理解与来源。该验收通过后再单独引导 Employment / Person scope 场景；在此之前 Phase D3 不判 PASS。
- Git ownership：D3 自有改动是 Compiler、workspace / Wiki UI、前端测试、`tests/test_wiki_d3.py` 与长期模型/验收/roadmap/Wiki 模块说明。13 个用户旧 Resume 文件、`AGENTS.md` 未知 hunk、`.agents/skills/`、`docs/agents/` 的开工哈希均未变化；无 stage、commit 或 push。D3 未提交，未有 UI 验收前不关闭阶段。

## 2026-09-27：Phase D2 — COMPLETE / PASS

- 真实用户验收：DeepSeek 为虚构 smoke 提出 1 条 rewrite；用户编辑后接受。接受前确认 Proposal 已 resolved/accepted、正式 Wiki 未被 pending Proposal 改动；接受后 revision 2 保存的是用户编辑内容。revision 1 保留原 Fact，revision 2 保留新 Fact；二者都只有本轮 Raw revision 1 的 source_ref。Raw 正文和稳定摘要在发送、审批前后与 smoke 基线相同。没有重新调用 Provider。
- Wiki UI 收口：历史页按最高 revision 唯一显示“当前”；早期 revision 显示“历史”；若最新 revision retired 则标成“不再有效”，旧版本仍是历史。Preview、当前理解、编辑表单、项目 Wiki 卡片和历史统一把 `fact / observation / hypothesis` 显示为“已确认事实 / 观察 / 待验证判断”，底层 enum 与 `current` / `retired` 数据合同不变。
- smoke 数据清理：删除本轮虚构 Project、Raw、Wiki 当前对象、已处理 Proposal、Project/Raw/Wiki 请求记录及 Project/Wiki 共 3 条 revision；其他 current、record 与 revision 的逐行摘要清理前后相同。业务对象在 `current`、`records`、`revisions` 中均无残留。按既有审计规则保留 `ai_operations`、operation result、prepare、`ai_call`、dispatch/outbound audit。
- Provider / 正式数据：相对 smoke 前基线 `wiki_compiler|dispatched` 与 `response_received` 各增加 1；`research_search|dispatched` 增加 0。早先两次 stale 确认均在 Provider `complete` 调用前被拒，不构成 Provider outbound。UI 修正、Runtime 更新与测试数据清理期间没有新增 Provider dispatch。最终 health=`ok`、仅监听 `127.0.0.1:8765`、SQLite `quick_check=ok`、schema v6、data instance `42ff565e28a08e31414442521540ac3e`。
- Runtime：为发布中文标签/历史状态 UI，旧 PID `50460` 受控更新至 `62356`；停服务后离线清理 smoke 数据，再按显式 `AI_ENABLED` 正式重启至当前 PID `63058`。当前服务 health=`ok`，只有 `127.0.0.1:8765` 监听。Runtime 使用当时 D2 working tree；没有为 Git commit 再重启。正式 `frontend/dist` 共 11 个文件，与 `/tmp/career-d2-final-ui-check` 构建逐文件一致，manifest SHA-256=`076c1cb1d3aee508310e7bea0e826ff13f1f9a1241ca2adc79b9efacb9a36701`；HTTP 实际提供的入口脚本含最新中文类型及历史标签。
- 自动检查：D1/D2 聚焦 pytest `34 passed`；全量 pytest `468 passed`。前端导航 `8 passed`、local request `3 passed`，Employment/Person、Project collaboration、workspace mutation、Wiki semantic 测试通过。TypeScript typecheck、输出到 `/tmp` 的 build、`pip check`、`npm ls --depth=0`、secret scan、文档链接检查和 `git diff --check` 均 exit 0。`npm ls` 显示既有 23 个 extraneous 本机依赖，没有因此改动依赖。
- Git ownership：D2 commit 只包括长期模型/STATUS、Wiki 实现/README、Compiler、其测试及 Wiki UI/样式/测试。13 个用户旧 Resume 文件与 `AGENTS.md` 未知 hunk 未修改、未 stage；`.agents/skills/` 与 `docs/agents/` 未 stage。`frontend/dist` 与 `.career-runtime/` 是本机生成/运行文件，不提交。Git 状态及 D2 closeout commit/push 以本节对应的最终提交为准。
- 阶段：Phase D2 `COMPLETE / PASS`；没有实现 D3。Phase D3 `READY`。

## 2026-09-27：Phase D2 — stale 修复后、首次真实 DeepSeek dispatch 前的状态快照

以下条目记录本节写入前的状态；当前真实 smoke 和 Runtime 以本节上方最新记录为准。

- 当前门槛：真实 Provider smoke 尚未调用；DeepSeek 与 Tavily outbound 增量均为 0。当前 Preview 已在 Chrome 等用户查看和点击“让 AI 整理”。
- 范围：已实现单份新手工 Raw 驱动的 Wiki Compiler。Compiler 只生成候选 add / rewrite / retire Patch；pending proposal 与正式 Wiki 分开保存，AI 不直接改正式 Wiki。未进入 D3，没有 Cognition 跨经历提炼、Agent Tool Calling、全 Career 搜索、Resume AI 修改或旧 Event / Achievement / Evidence 退役。
- Context DTO：仅含任务名；用户选中的 Raw `id / source_kind / created_at / content`；直接范围和明确关系对象的 `type / stable_id / minimal_identity`；这些范围当前 Wiki 的 `knowledge_id / type / content / tags / revision` 及用于归属目标范围的 `scope_type / scope_id`。不含 Raw hash / 内部 metadata、历史与退役 Wiki、其它 Career 范围、Resume、Feedback、Secret 或未确认人物。新版 Preview 的正文、Tags 与可读对象名称由同一份已清洗 DTO 投影，不额外读取其它数据；长正文完整保留在有界滚动区。
- stale 根因与修复：Raw、Wiki、Project 的 manifest、revision、内容摘要在 prepare 与 confirm 间完全一致。误报只来自模型请求哈希：准备时 UI 未传 `model_config_id`，确认时 ModelGateway 补上实际默认配置 ID。现改为 prepare 时冻结“实际配置 ID + provider + model + payload”哈希并持久化，确认时先比较冻结值；配置在两者之间变化仍在 dispatch 前 stale。请求幂等复用也核对该冻结摘要。没有把时间戳、UI 展示字段、Runtime build、operation ID 或列表/JSON 键顺序混入哈希。UI stale 显示“资料在预览后发生了变化，请重新确认发送内容。”和手动“重新预览”按钮；错误处理不自动 prepare 或重试。
- 安全与审批：prepare 只准备和预览，不发送 Provider 请求；Preview 按“新资料 → 所属项目 / 任职 / 人物 → Wiki 里已有的信息 → AI 会判断”的顺序展示。核心说明是“AI 会比较‘新资料’和‘Wiki 里已有的信息’，判断 Wiki 是否需要更新”；Fact / Observation / Hypothesis 显示为“已有事实 / 观察 / 待验证判断”，不重复显示每条知识的 Project 名称；边界说明为“仅限上面这些内容，不会读取其他 Career 资料”。Preview 的 Raw 全文、当前 Wiki 全文 / Tags 和范围名称均来自同一份清洗后的 outbound DTO；长正文有界滚动、可查看全文。技术模型与条数默认折叠。“让 AI 整理”仍走既有单独 confirm，取消只关闭预览。输出严格限 add / rewrite / retire；每次逐条审批，stale fail closed，`outcome_unknown` 不自动重试。schema v6，无 migration。
- Synthetic 验收：使用隔离临时数据库、虚构 Project / Raw、TestProvider 和本机 Chrome 完成 Preview → 明确确认 → 单次 fake Provider 调用 → 逐条接受 → 当前 Wiki 即时刷新。`provider.calls=1`、无页面错误；没有连接真实 DeepSeek / Tavily，也没有使用正式数据库或正式 Runtime。
- 正式 Runtime / 数据：受控重启链为 `38997 → 46187 → 46886`；第二次重启是因为合成对抗测试补出“同名模型配置切换”的冻结绑定缺口。当前只监听 `127.0.0.1:8765`，`/healthz=ok`，显式保持 `AI_ENABLED`。HEAD = `main` = `origin/main` = `92d9ba1f9df5715ff6266bfd10fd264063af1ac6`；Runtime 后端 / 前端来自 dirty working tree（不是 HEAD）。89 个运行源码与构建输入文件 manifest SHA-256=`9b538f8b83c889a996b8a60b4a8fad938f64d31ffe735d2b6d751bf71b116701`。正式 `frontend/dist` 的 11 个文件与 `/tmp/career-d2-stale-confirm-build-final2` 逐字节一致，manifest SHA-256=`945de52db6370c6660658b07d666bac74354ee711dc61e3e251f99f091d28dfd`；HTTP 实际提供的 11 个文件全部匹配。SQLite `quick_check=ok`、schema v6、data instance `42ff565e28a08e31414442521540ac3e` 不变。
- 正式虚构 smoke：继续复用 Project `D2-WIKI-COMPILER-SMOKE-b8d412f6`（ID `0ab6b9bf-9477-43e8-9c0b-457ee806e45f`，无 Employment）、Raw（ID `fc8e2742-bbe8-45be-b9bd-8798da42d818`，revision 1）和当前 Wiki Fact（ID `98e15e97-cda2-4720-adb8-a951584a9f13`）。三个对象均存在，revision 和正文哈希未变；没有新建 Project、Raw 或 Wiki。最终 Preview 在 PID `46886` 重启后重新生成，清楚显示同一 Raw 全文与时间、所属 Project、标题“Wiki 里已有的信息”下的事实正文与标签、AI 会比较什么和资料边界；Project 名称只在所属范围出现一次；“让 AI 整理”和“取消”都完整可见，发送详情默认折叠。没有点击发送。
- Outbound 与数据健康：Provider `dispatched` 审计与基线仍为 16 条（connection_test 1、research_search 7、research_update 6、resume_optimization 2），没有 wiki_compiler dispatch；DeepSeek outbound 增量 0、Tavily outbound 增量 0。formal DB 有 2 条先前失败的 wiki_compiler 操作和对应本地失败 audit，但两条的 `dispatched_payload_hash` 都为空、没有 Provider dispatch；发送槽已释放。health、SQLite quick_check 和 schema 正常；未读取、输出或泄露 Secret。
- 自动检查：D2 聚焦 `tests/test_wiki_d2.py` 为 26 passed；全量 pytest 为 468 passed。前端导航 8 项、本地请求 3 项、Employment / Person、Project collaboration、workspace mutation、Wiki semantic 测试全部通过；typecheck、临时目录 Vite build、pip check、npm ls、secret scan、文档链接检查和 `git diff --check` 通过。`npm ls` 仍只显示既有 extraneous 本机包；正式构建与临时构建逐文件一致。
- Git ownership：HEAD = `main` = `origin/main` = `92d9ba1f9df5715ff6266bfd10fd264063af1ac6`；没有 staged 内容、没有 commit/push。D2 包含长期模型规范、STATUS、Wiki UI / CSS / tests、Compiler API / gateway / provider 代码与测试。既有 13 个 Resume 用户文件、`AGENTS.md` 未知改动、`.agents/skills/` 和 `docs/agents/` 哈希都保持；没有清理、暂存或提交。
- 阶段门槛：stale 根因、synthetic 回归、全量测试和 Runtime Update 已通过；真实 Provider smoke 尚未开始，Phase D2 不能判 COMPLETE。新版虚构 Preview 已留在 Chrome，等待用户查看并点击一次“让 AI 整理”；本轮没有发送 DeepSeek 或 Tavily 请求。未进入 D3。

## 2026-09-26：Phase D1 — COMPLETE / PASS

- 范围与合同：完成手工 Raw、Wiki Semantic、typed `source_refs`、修订/退役；未实现 Wiki Compiler、Cognition 自动提炼、Resume AI Context 或 D2。Raw 是原始依据，有稳定 ID 和 provenance；Wiki 不复制 Raw 正文，修改 Wiki 不会反写 Raw。用户手工 Wiki 的 provenance 是 `user`，来源可为空，不伪造 Raw。Fact / Observation / Hypothesis 是 D1 唯一知识类型；scope / Tags 表达范围和分类；Opportunity 知识只在明确的 Opportunity 范围视图出现；Person scope 只接受已存在的确认人物，不创建 Person。
- 历史合同：rewrite 以同一 Wiki ID 的新 revision 更新当前语义；retire 退出默认当前视图；既有 `current` / `revisions` 与 `source_refs` 保留历史和来源，不建立第二套 provenance、revision 或 history 系统。
- D1 反向审查：Wiki 正文只保存语义内容，Raw 原文通过稳定引用读取；全局 Wiki 列表排除 Opportunity 知识；Person scope 要求既有已确认 Person；模块没有 Provider、Compiler 或 Raw 修改/删除入口。旧 Event / Evidence 只按原 ID 兼容读取，Achievement 不会被当作 Raw；本轮未删除这些旧对象。
- 两段用户 UI 验收均 PASS：Raw → Wiki Fact → source_ref → 打开 Raw 原文；rewrite → retire 后历史仍可追溯且 Raw 原文完全不变。
- 测试数据清理：删除本轮 1 条虚构 Raw、1 条 Wiki 当前对象、3 条 Wiki revision、4 条对应 D1 请求/幂等记录。验收 Project `demo-b5-project` 在 D1 前已存在，已保留；其 ID、revision 与内容摘要清理前后不变。D1 测试对象无残留。
- 清理后正式数据：`/healthz=ok`、SQLite `quick_check=ok`、schema v6、data instance `42ff565e28a08e31414442521540ac3e` 不变；`ai_operations` 仍为 15 项，`ai_audit` dispatch 仍为 16 条（connection_test 1、research_search 7、research_update 6、resume_optimization 2），与 D1 前记录相同，DeepSeek / Tavily outbound 增量均为 0。真实 Provider 本轮未调用，供应商质量未验收；未读取、显示或记录 Secret。
- 最终自动回归：D1 聚焦 `tests/test_wiki_d1.py` 为 8 passed；全量 pytest 为 441 passed（47.18s）。前端导航 8 passed、本地请求 3 passed，其余 Employment/Person、Project collaboration、workspace mutation、Wiki semantic 测试通过；typecheck 和 `/tmp/career-d1-build-closeout` 临时构建通过，未覆盖正式 `frontend/dist`。`pip check` 通过；`npm ls --depth=0` exit 0（23 项为现有 extraneous 包）；secret scan、文档链接检查和 `git diff --check` 通过。
- Runtime：PID `9270` 未重启，仍只监听 `127.0.0.1:8765` 且 `/healthz=ok`。它继续运行通过 D1 UI 验收的 working-tree baseline；Git commit / push 后仍不更新 Runtime。
- README 保护：`src/workbench/README.md` 以及开工前记录的 13 份用户旧 Resume 文件 SHA-256 全部逐字节一致；没有修改受保护文件。
- Git ownership：本次提交只含精确核验过的 20 个 D1 文件。13 份 Resume 用户改动保持 unstaged；`AGENTS.md` 4 行作为 pre-existing / unknown ownership tracked diff 保持 unstaged；`.agents/skills/`、`docs/agents/` 本机配置保持 untracked。D1 提交不包含它们；不要求工作区 clean。提交信息为 `Add Raw and semantic Wiki foundation`。Git 后仍使用已验收的 PID `9270`，不重启 Runtime。
- 最终门槛：D1 功能、自动/用户验收、数据清理和 Git 收口均通过；Phase D1 `COMPLETE / PASS`，Phase D2 `READY`，没有进入 D2。

## 2026-09-26：Phase C — COMPLETE / PASS

- 用户验收：人物创建、编辑补充、页面即时刷新，以及 Project A/B 关联人物和跨任职隔离均 PASS。Person 的 Employment `role` 与每个 Project 自由填写的 `project_role` 独立。
- 权威规则已补齐：手工创建即确认；Raw mention 不建 Person；未解决身份留给未来 Raw / Wiki Compiler；正常 UI 隐藏技术状态；任职结束后人物历史仍可读；人物语义进入 Wiki，不扩 Person 字段。
- 清理正式库中本轮专属虚构数据：2 段 Employment、4 个 Person、2 个 Project、3 条人物关系、10 条 revision、11 条测试幂等请求。其他业务行摘要不变；无 Phase C ID/标记残留；health `ok`、SQLite `quick_check=ok`、schema v6、无 migration，data-instance 仍为 `42ff565e28a08e31414442521540ac3e`。
- 回归：Phase C 聚焦 14 passed，全量 pytest 433 passed；前端人物、协作、刷新测试通过，导航 8 passed、本地请求 3 passed；typecheck、`/tmp` build、`pip check`、`npm ls`、secret scan、Markdown 链接及 `git diff --check` 通过。`npm ls` 仅有既有 extraneous 条目。
- Runtime 未重启，仍为 PID `98210`、仅监听 `127.0.0.1:8765`、health `ok`；Provider 账本仍为 15 条，DeepSeek / Tavily outbound 增量均为 0；未读取或泄露 Secret。
- Git ownership：Phase C 文件及 README 单独 hunk 已与 13 份用户旧 Resume 文件/README 旧 hunk 区分；旧内容逐字保持，未 stage。Phase C 精确提交并 push 作为本次收尾最后一步。

## 2026-09-26：Phase B — COMPLETE / PASS

- 实现内容：增加 Project 一级入口及左右工作区；Project 可独立新建/编辑，支持名称、说明、用户自建 Tags、`active / paused / completed / canceled`、`status_note` 和可选 Employment 关联。任职页展示关联项目并提供轻量关联/新建入口，两处打开同一 Project 正本。简历工作台一级入口保留；旧 Event/Achievement/Evidence/Participant 仍在折叠兼容区；未改 Person、Resume AI，未进入 Phase C。
- 自动验证：定向 `tests/test_work_domain.py tests/test_t14_reuse.py` 17 passed；全量 pytest 425 passed；前端 typecheck 通过；导航测试 8 passed；Vite 临时构建通过；`pip check`、`npm ls --depth=0`、secret scan、Markdown 本地链接和 `git diff --check` 通过。`npm ls` 有既有 extraneous 项但 exit 0。Phase B 没有 SQL schema migration；字段保存在既有 JSON body，正式数据库 schema 保持 v6。
- Runtime Rebaseline：HEAD、`main`、`origin/main` 均为 `5cbb21b74524527385cf46013095195e9663e81c`；working tree dirty，包含用户原有、Phase A/B 的 tracked 改动。运行后端来自 `/Users/frog/Projects/Career` 当前 working tree（不是 HEAD），运行源码清单 SHA-256=`bcff9f766e102c520078142e89c7a7ab1ed1808c9857db105627f9f7e9512ceb`。旧 PID `38721` 已由正式启动器停止，新 PID=`76246`；服务健康 `ok`，仅监听 `127.0.0.1:8765`，模式为显式 `AI_ENABLED`。SQLite `quick_check=ok`、schema v6 且摘要不变，正式数据实例身份不变。
- 前端正式产物：两次 `/tmp` 构建逐文件一致；随后正式生成 `frontend/dist`，11 个文件与临时构建一致，manifest SHA-256=`e6922a3ad14c08d3a9bdfe49625f6b485bd905ef0278a8ced1dd4090b31534d7`。重启后 HTTP 提供的 11 个文件均与该目录逐字节一致。旧 dist 未尝试恢复；它是可再生成的构建产物。
- AI/Provider 范围：真实 Provider 质量未验收；本轮 Git 收口没有调用 Provider，DeepSeek 与 Tavily outbound 增量仍为 0。
- 用户 UI 验收：两轮均由用户确认 PASS。第一轮：从「项目」创建不关联 Employment 的虚构 Project，两个自定义 Tags 保存成功。第二轮：从 Employment 关联该 Project 后打开同一正本，Tags 保留，未生成第二个同名 Project。
- 测试数据清理与正式库复核：只删除本轮新建的 `TEST-PROJECT` 正本、5 条对应 revision 和 5 条仅含该 Project ID 的幂等请求记录；清理后 Project ID 集合恢复为 UI 验收前基线。关联的 Employment 早于本轮创建，已保留；Employment 与其 episode 内容摘要未变化。清理后 `/healthz=ok`、SQLite `quick_check=ok`、schema v6、正式数据实例身份正常。DeepSeek model dispatch 增量 0、Tavily search dispatch 增量 0；没有显示、复制或记录 Secret。
- 构建纪律：普通 frontend build、CI 和验证输出到临时目录，不覆盖正式 `frontend/dist`；只有明确执行正式 runtime update 才生成正式 dist。`frontend/dist` 是 generated artifact，未知旧文件不作为需长期维护的业务状态。
- Phase A/B Git Baseline（2026-09-26）：对 `docs/01-product.md` 至 `docs/05-acceptance.md` 做完整语义审查并纳入权威基线；已修正过期阶段状态、旧导航/ResumeUse/T14目标表述、未经标记的 Phase C+ 目标、过期 runtime 身份及 Resume copy-lineage 规则。仍有效的 Opportunity 流程、Profile 手动同步/隐私、真实发送确认、Submission 冻结、CAS/幂等和 local-first 规则保留。Phase A/B 共 23 个精确文件组成完整提交 `1e0f136a2399e0e48a3a7a2c6e27a005dd31e032`，已推送 `main`；当次 fetch 验证 HEAD=`main`=`origin/main`。13 个剩余 tracked 修改逐一对应原有用户业务文件：`frontend/README.md`、`frontend/index.html`、`frontend/src/editor/legacy-app.js`、`frontend/src/editor/legacy.css`、`src/workbench/README.md`、`src/workbench/profile.py`、`src/workbench/resume_documents.py`、`src/workbench/resume_pdf.py`、`tests/test_profile_ownership.py`、`tests/test_record_submitted.py`、`tests/test_resume_documents.py`、`tests/test_resume_pdf.py`、`tests/test_t15_navigation.py`；均未编辑、回滚或格式化。收口时无其他 tracked diff、无 staged 或 untracked 文件。`frontend/dist`、`.career-runtime/` 和 `/tmp` 的构建、清单与清理核验文件是生成物/运行产物，没有提交。
- Git 后的 Runtime：本次 Git 收口没有重启 Career；仍为 PID `76246`，最近 `/healthz=ok`，工作区源码清单 SHA-256=`bcff9f766e102c520078142e89c7a7ab1ed1808c9857db105627f9f7e9512ceb`。Runtime 保持上一轮 working-tree baseline；本次 Git commit 改变了 HEAD，不把该 runtime 描述为按新 HEAD 重启。
- 最终状态：Phase B `COMPLETE / PASS`。本轮到此停止，不进入 Phase C。

## 2026-09-25：Phase A — 长期 Career 模型与权威文档对齐（完成）

- GitHub 仓库已按用户要求从 Public 改为 Private；没有公开发布，也没有为此推送代码。
- 当前计划：[WIKI-PROJECT-RESUME-IMPLEMENTATION-PLAN](WIKI-PROJECT-RESUME-IMPLEMENTATION-PLAN.md)。用户已批准计划并确认四项修正；Phase A 已新增唯一长期模型正本、对齐现行权威摘要，未改业务代码。随后用户已批准 Phase B；当前进展见本文顶部。
- Phase A 范围：只修改目标/导航/验收/路线图/状态等 Markdown；`docs/audit/`、`docs/archive/` 未改。没有修改开始前已脏的业务代码、测试、前端页面及实现README；其中 5 份已脏权威产品文档仅做本阶段必要对齐，原有用户改动保留。
- Phase A 检查：`.venv/bin/python scripts/review_checks.py --docs-only` exit 0；对本轮全部 18 个改动/新建 Markdown 文件执行本地链接与尾随空白检查 exit 0；`git diff --check` exit 0。没有运行业务测试，因为本轮没有代码改动。
- 盘点基线：main 与 origin/main 均为 5cbb21b74524527385cf46013095195e9663e81c；Phase A 开始前工作区已有 18 个未提交改动，代码/测试保持不动，必要的文档对齐见本状态与实施计划。
- 当前工作区基线测试：.venv/bin/python -m pytest -q，421 passed（22.63s）。
- 生产 SQLite schema 只读检查为 v6；未读取业务记录。当前本机服务仍在 127.0.0.1:8765，构建标识 career-0.7.0-batch-f；运行源码与未提交改动不能由该标识完全证明一致。

最后整理：2026-09-24（T00–T15 implementation tasks = `COMPLETE`；Review stabilization / implementation program = `CLOSED`）。本文顶部只维护当前源码/运行身份、阶段状态、阻断项、下一动作和证据位置；历史批次的过程和证据留在下方既有章节及各自文档。

## 2026-09-24：个人本机版取消配对与浏览器登录

当前个人本机版的 `Career.app`、`scripts/run.py` 和 `scripts/macos_app.py start` 都直接打开，仅监听 `127.0.0.1`；浏览器配对码、Bearer 会话、恢复句柄、会话转交和退出登录入口已从当前实现移除。Host/Origin/Fetch Metadata/写请求保护、App 运行身份核验、单实例锁及启动器专用的受控停止凭据保留。服务器/多人身份认证仍未实现，未来需另行设计。

下方 T09 与旧切换记录保留当时配对方案的历史证据，不是当前操作要求；旧实现已由本地免配对决策取代。

本轮免配对源码批次尚未重新启动正式长驻服务，也未重新运行质量门禁；T15 与 Stage 3 的历史运行证据不替代本轮验证。

## 当前生产切换阶段

- 唯一切换账本：[PRODUCTION-CUTOVER](PRODUCTION-CUTOVER.md)。本轮已完成阶段 0、1、1.5、2、2.5、3；Stage 4A.1 已完成 Git/source consolidation，状态为 `CUTOVER_GATE=STAGE_3_LOCAL_ONLY_DEPLOYED_VERIFIED`、`RELEASE_GATE=PASS_LOCAL_ONLY`、`SOURCE_CONSOLIDATION=SOURCE_CONSOLIDATED`。
- Stage 3 执行门已通过；[RELEASE-GATE](RELEASE-GATE.md) 保留的是执行前重分类历史。`AI_ENABLED`、真实 Keychain/Provider 和收费调用没有包含在本次发布授权内。
- 真实 Provider 未调用，真实 Keychain 未读取、修改或删除；本次通过仅适用于 `LOCAL_ONLY`。
- 当前计划身份：`plan_id=career-cutover-20260920-stage25-resume-template-e2dcd25c`，`plan_hash=a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`，`release_id=career-0.7.0-batch-f-stage25-resume-template-20260920`。
- 当前冻结身份：T14 Git 收口后的基线为 `main`/`origin/main`=`ebf528446e4b5d07d92165b5a1fbf0ac3ba10fb3`；T15 已完成收口并以本轮提交后的 local/remote HEAD 核验为准。Stage 3 的 source/static fingerprint 和 `career-0.7.0-batch-f` 仍仅代表其历史发布对象。
- 旧正式 PID `79422` 已在完整身份核验后优雅停止；原正式数据、旧 App、旧 Python 环境和旧 runtime 均保留。当前正式 PID=`39300`、Python=`3.12.14`、build=`career-0.7.0-batch-f`、data instance=`42ff565e28a08e31414442521540ac3e`、端口=`127.0.0.1:8765`、模式=`LOCAL_ONLY`。LaunchAgent plist 和正式周任务未修改或触发。

## 当前源码/运行身份

- 当前开发目录：`/Users/frog/Projects/Career` 的 `main`；T14、T15 均已按批次范围收口到 `origin/main`。历史 review worktree、review branch、安全分支及本机资料均未纳入 T15。
- 历史整合基线：T14/T15 review commit `920d08b645db14d272bc524103e969a2f504f1fb` 是生产切换文档所述的 source-consolidation 起点；其后的 `main` 变更另行记录，Stage 3 的 fingerprint 和 `career-0.7.0-batch-f` 只对应当时冻结的发布对象。主项目原有本机资料未进入 Git；保护提交为 `d8c25f7b0ff321a256b2376909986d8f76845ecd`，安全分支为 `safety/pre-stage4a-main-20260921`。
- 测试身份：自动测试继续使用虚构数据、`TestProvider` 和隔离临时目录；Stage 3 仅通过一致性备份读取正式源并在恢复副本上验收，未读取真实 Keychain、未调用收费模型。
- 最终交付身份：正式 Python 已切到固定 `3.12.14` 环境；source/static fingerprint 与授权值一致。Stage 3 没有源码修复、提交、Git 合并或 push。

## 当前阶段任务状态

- Final Acceptance / Stage 3：`PASS — DEPLOYED_VERIFIED (LOCAL_ONLY)`；T14/T15 用户验收已记录，T00–T15 implementation tasks 完成。即时恢复点、显式 schema 准备、固定 Python/App/data/runtime、macOS/Chrome/PDF、LOCAL_ONLY 和回滚对象见 [PRODUCTION-CUTOVER](PRODUCTION-CUTOVER.md)。
- Stage 3 最新质量门禁：`scripts/review_checks.py` exit `0`，内含 `pytest -q` `282 passed`、frontend typecheck/build、pip check、npm ls、secret scan、Markdown links、git diff check；LOCAL_ONLY+Range/Host 专项 `7 passed`。最新 `pip-audit` exit `1`，仅 Starlette `14` 条记录、`7` 个唯一 advisory，未隐藏。
- Stage 3 未修改源码。切换中发现并显式处理恢复点缺少 T03 内部表的问题：只在恢复副本上 inventory → dry-run → apply → verify，原有业务 row hash、冻结材料和附件逐项不变。

- T12：`CODE_VERIFIED`；完成类型边界、状态文档、R01–R18 回归映射、浏览器回归入口、最小 CI、依赖/秘密/文档检查。浏览器入口本机因 Chromium 下载阻塞未取得运行证据；该历史平台项不阻断本轮实现收口。
- T12.1：`CODE_VERIFIED`；5 个可安全升级的包已按最小修复版本更新，2 条实际 Starlette 边界已加应用层防护；`pip-audit` 仍保留 Starlette 的 14 条重复/别名记录，逐项分类与接受理由见下方 T12.1 章节，未伪造为通过。
- T13：`CODE_VERIFIED`；实现任务已完成。`tests/test_t13_release_readiness.py` 专项与阶段 0/1 隔离验收记录保留在历史证据，不重新打开已完成的实现批次。
- T14：`CODE_VERIFIED + BROWSER_VERIFIED`，完成最小职业成果回流链。新增接口复用现有 personal `wiki_entry`：用户从任职成果查看 Evidence 后，编辑/脱敏并明确批准，Resume 只读取批准表达；`fact_status=confirmed` 与 `reuse_status=approved|revoked` 分离，Evidence 仅以指针/hash 进入 provenance；撤销只影响未来选材，冻结版本不变。专项 `tests/test_t14_reuse.py` 为 `11 passed`；全量 `pytest -q` 为 `296 passed`；前端 typecheck/build、pip check、npm ls、secret scan、review_checks、git diff --check 均 exit `0`。隔离虚构数据 Computer Use 已完成任职→证据→批准→Resume 选材/保存→冻结 A→撤销→新简历不可选，未访问正式数据、Keychain 或 Provider。
- T14 Git 收口：commit=`ebf528446e4b5d07d92165b5a1fbf0ac3ba10fb3`，message=`Add approved career achievement reuse flow`；已 push `main`→`origin/main`，两者 HEAD 一致。提交范围仅含 T14 成果复用、授权/撤销、provenance/Evidence pointer、Resume 最小 UI/过滤、T14 测试与对应文档；App binary、`.venv`、runtime、`Career-review/`、数据/附件/备份和其他 C 类本机资料未纳入。
- T15：`CODE_VERIFIED + BROWSER_VERIFIED（IAB）`；修正重复模块去重、键盘 ContextMenu/Shift+F10 菜单、Escape 与触发项焦点回归、pin/order 原子写入失败回滚及轻量语义提示。IAB 隔离假数据完成根路径、显式深链刷新、A→B、排序、取消 pin、重启持久化、正常/窄窗口和零 console error/warning；Chrome loopback = `TOOL_BLOCKED / UNVERIFIED`，原因是本机扩展返回 `ERR_BLOCKED_BY_CLIENT`，失败标签已关闭，不将其写成 Chrome 通过。
- T00–T15 implementation tasks：`COMPLETE`；原 Review stabilization / implementation program：`CLOSED`。未开启新功能、`AI_ENABLED` 或 Starlette/FastAPI 升级。
- Stage 4A.1：`SOURCE_CONSOLIDATED`；review commit `920d08b645db14d272bc524103e969a2f504f1fb` 从原 `main` 基线 `82af33dfe4d572e6ab04f36f3757b13a28049037` fast-forward 合并。A 类 tracked 修改与 C 类 17 个源码/测试/文档文件均纳入 review 历史；未发现 review 之外的合法源码修改；D 类本机资料仍在原处且未进入 Git。主项目门禁重新通过：`pytest 282 passed`、前端 typecheck/build、pip check、npm ls、secret scan、review_checks、git diff --check 均 exit `0`。主项目 90 个源文件和 12 个静态文件按 Stage 3 冻结清单重算，与授权 fingerprint 一致；正式 Career PID `39300` 健康运行且 `LOCAL_ONLY`，正式 DB 与 Stage 3 最终 inventory 的 hash 一致。
- Stage 1.5：`CODE_VERIFIED`；`CAREER_AI_MODE=LOCAL_ONLY` 在 SecretStore、Provider、ModelGateway、Research web search 与启动器边界 fail closed。生产样式 `ModelConfig`/`secret_ref`、假 API Key、注入 TestProvider、四条 AI 路径和网络 trap 专项通过；不等同阶段 2 或正式切换授权。
- Stage 2 / Stage 3 历史证据：Candidate-only rehearsal = `PASS`；当时记录的正式切换 gate 已由后续 Stage 3 `DEPLOYED_VERIFIED (LOCAL_ONLY)` 完成，不作为当前阻断。固定 Python 3.12.14、正式数据一致性备份、全新隔离恢复、schema v6/inventory/restore verify、Candidate App/8865、Chrome 只读链、PDF 文本层和 LOCAL_ONLY 证据已完成。
- Stage 2 follow-up（历史记录，已被 2026-09-24 决策取代）：当时只有带临时目录标记的假数据可免配对，正式数据仍要求配对；这不再描述当前个人本机行为。现行边界见本节顶部和 [Architecture 本地可靠性](../03-architecture.md#本地可靠性)。
- Stage 2.5：`CODE_VERIFIED`；仅修改 `src/workbench/resume_pdf.py`，将结构化 Chromium PDF 的纸面布局映射回 T04 前 `legacy.css`/`legacy-app.js` 的既有模板：9mm 页边距、居中姓名与联系方式图标、深灰标题块+横线、三列经历/项目表头、圆点 bullet 和教育背景位置；真实文字层、中文字体、分页、冻结一致性与 hash/renderer 元数据保持。历史基准为 `docs/archive/reviews/2026-09-15-novice/2026-09-15-novice-assets/03-empty-editor.png`；同一虚构简历的旧编辑器截图与新版 PDF 已逐项对照。此前锁屏阻断已解除：Preview 选择/⌘C/TextEdit 粘贴实际通过，证据已写入 [RELEASE-GATE](RELEASE-GATE.md)。
- T01–T11：按用户确认保留既有状态，实现任务均已完成；历史 acceptance/platform 记录不影响当前关闭状态。T11 为 `CODE_VERIFIED + BROWSER_VERIFIED`。
- 证据：T12 专项为 `tests/test_t12_quality.py`；本地质量入口为 `scripts/review_checks.py`；浏览器入口为 `scripts/browser_regression.py`；R 映射为 [REGRESSION-MATRIX](REGRESSION-MATRIX.md)。

## 阻断项与最终验收保留项

- 当前没有 T00–T15 implementation task 硬阻断；`LOCAL_ONLY`、正式 App/恢复点/回滚对象及本轮代码门禁均以最新证据为准。
- Chrome loopback 保留为 `TOOL_BLOCKED / UNVERIFIED`，不阻塞 T15 收口，也不继续修改产品代码。
- `AI_ENABLED`、真实 Keychain、真实 Provider、收费调用和真实网页 Research 未授权、未执行；这是未启用范围，不是本轮实现阻断。
- 供应链残余：`starlette==0.46.2` 的 7 个唯一 advisory 仍存在，`pip-audit` exit `1`；该项按 T12.1 既有分类保留为非阻断观察，不在本轮升级 Starlette/FastAPI。
- 非阻断观察（部分为历史）：LOCAL_ONLY 设置页曾按数据库配置显示“真实 AI”；旧 demo 机会曾显示 `Research owner 不合法`；T09 旧实现曾使用配对及浏览器恢复会话，现已整体退役；PDF 复制的加粗字段边界在 TextEdit 表现为 `**`。后端安全边界、真实机会读取和中文文字层均已独立通过。
- T11 规模数据仍只用于事实报告：1000 条虚构机会 summary `1,292,277` bytes/`0.074188s`，all opportunities `749,781` bytes/`0.022617s`；Chrome 显示总数和页面切换，未见分页按钮，不据此给出性能好坏结论。
- 正式周任务 plist 未改且未运行；它不是本次 Stage 3 的新增阻断。旧数据/App/Python/runtime、即时恢复点和失败候选副本均保留，任何清理或 Stage 4 行为需另行授权。

## 下一动作

- T00–T15 及原 Review stabilization / implementation program 已 `CLOSED`；完成后停止。不得进入其他产品任务，不得删除 Worktree、安全分支、旧版本、恢复点或本机资料，不得访问 Keychain、调用 Provider。

## Stage 2 Candidate-only rehearsal：2026-09-20

- 正式源与恢复：正式 DB 备份前后 hash 均为 `6c7b6bbe1e04ed86ccc4862e86fd5bac3f2305535f38db3d844071cde3ee3721`；`cutover-rehearsal-20260920` manifest `complete/healthy/valid/recoverable`；恢复验证 exit `0`，snapshot hash=`7eb49d921c13c8931eab01d224ec4b1cb72d7a666f3e567a0560b27391e7d3cb`，counts applications=1/current=31/meta=1/records=51/artifacts=1；inventory exit `0`，无 migration gate，未 apply。
- Candidate：固定 Python `3.12.14` 环境、独立 App/data/runtime/log/`8865` 均已建立；冷启动、运行中双击、未知端口拒绝、正常停止和 `/healthz` 已实测；正式 PID `79422` 始终存活。
- Chrome/PDF/规模（历史验收）：真实 Chrome 当时完成配对、刷新会话、退出/重配对、Wiki/机会/面试/简历/任职入口和只读详情；个人本机版现已取消配对。恢复简历摘要 DTO 的最小合同修复后工作台正常。Preview 显示真实 PDF 文本层；1000 条虚构机会页面显示总数并完成页面切换，未见分页按钮，不作性能结论。
- 门禁：`pytest -q` exit `0` — `282 passed in 149.19s`（由最后一次 `review_checks.py` 内含全量运行记录）；`npm --prefix frontend run typecheck` exit `0`；`npm --prefix frontend run build` exit `0`；固定 Python `-m pip check` exit `0`；`npm --prefix frontend ls --depth=0` exit `0`（已有 extraneous 条目）；`python scripts/secret_scan.py` exit `0`；`python scripts/review_checks.py` exit `0`；`git diff --check` exit `0`。`pip-audit` 既有重查 exit `1`，Starlette `14` 条记录、`7` 个唯一 advisory，未隐藏。
- 安全边界：Candidate 进程实际环境包含 `CAREER_AI_MODE=LOCAL_ONLY`；未读取真实 Keychain、未调用真实 Provider、未发起 Research web outbound。Stage 2 不执行 Stage 3。
- 临时免配对机制回归（历史机制，已退役）：当时四重条件的虚构临时数据服务 `127.0.0.1:8866` `/api/state` HTTP `200`；同一标记数据缺少开关的 `127.0.0.1:8867` `/api/state` HTTP `401`，均已优雅停止。当前个人本机版所有本机启动方式都直接可用，不再按临时数据标记区分是否配对。

## T13：最终隔离验收与生产切换准备，2026-09-19

- 原问题复核：最终收口前没有一次可复跑的交付身份/交叉场景/生产门禁证据；`frontend/README.md` 与 `docs/03-architecture.md` 还保留 T04 以前的 `html2canvas/jsPDF` 图片 PDF 描述。T13 专项先按该事实建立红灯，随后修正文档并保留测试约束。
- 实现：新增 `tests/test_t13_release_readiness.py`，实际用临时 `Store`、`TestProvider` 和 `TestClient` 检查 backend/frontend `build_id` 与 schema v6 一致、隔离浏览器入口固定 loopback/临时目录/TestProvider、T12.1 两条危险输入前置拒绝与 7 个 Starlette advisory 记录不被隐藏、未宣称 `ACCEPTED`/`DEPLOYED_VERIFIED`。`scripts/browser_regression.py` 仅调整缺失 Chromium 时的确定性失败记录，不改变真实用户链或连接边界。更新两份过时工程文档。
- 最终身份（`STATUS.md` 不计入差异指纹，避免证据记录自引用）：`HEAD=82af33dfe4d572e6ab04f36f3757b13a28049037`；branch=`codex/review-t00-t01-20260919`；schema=`6`；backend/frontend build=`career-0.7.0-batch-f`；requirements 锁定 `fastapi==0.115.12`、`starlette==0.46.2`、`playwright==1.51.0`、`pypdf==6.16.1`、`pytest==9.0.3`、`anyio==4.14.2`、`click==8.3.3`、`Pillow==12.3.0`；排除 `STATUS.md` 后的有效源文件清单 SHA-256 指纹为 `ac5e29028e8e769c4db98f1665879d5fb0c22de123f3083729e74725f2af7e96`。
- T13 专项（历史验收命令）：当时 `tests/test_t13_release_readiness.py` 为 `5 passed`；交叉专项运行了 `tests/test_t09_local_session.py` 等旧配对测试，记录为 `63 passed`。旧测试路径已移除，当前本机启动/身份/跨站保护回归见 `tests/test_local_runtime.py` 与 `tests/test_macos_app.py`。
- 全量与质量门禁：`pytest -q` exit `0`，`273 passed`；`npm --prefix frontend run typecheck` exit `0`；`npm --prefix frontend run build` exit `0`；`pip check` exit `0`；`npm --prefix frontend ls --depth=0` exit `0`（仅已有 extraneous 本地 node_modules 条目）；`python scripts/secret_scan.py` exit `0`；`python scripts/review_checks.py` exit `0`（内含 `273 passed`、typecheck/build、pip check、npm ls、secret scan、Markdown links、diff check）；`git diff --check` exit `0`。
- 供应链重查：`uv run --no-project --with-requirements requirements.txt --with pip-audit pip-audit -r requirements.lock --format columns` exit `1`，`starlette==0.46.2` 共 14 条重复/别名记录，归一为 7 个唯一 advisory：`PYSEC-2026-1941`、`PYSEC-2026-1942`、`PYSEC-2026-161`、`PYSEC-2026-2281`、`PYSEC-2026-2280`、`PYSEC-2026-249`、`PYSEC-2026-248`。未使用 `--ignore-vuln`；T12.1 的完整分类、A 类 Range/Host 直接回归和升级条件继续有效。
- 浏览器/平台：隔离浏览器入口实际执行 exit `1`，失败原因为本机缺少 Playwright Chromium 可执行文件（入口现保留脱敏短日志目录）；未取得 `BROWSER_VERIFIED`。未执行真实 Provider、真实 Keychain、真实网页/Chrome、真实 macOS Career.app、正式周任务或生产资料验收；这些不以构建/单测替代。独立 Subagent 的实际 Luna/High 配置无法核实，因此本批由主线程串行实施并完成只读规格/安全审查，不计独立审查证据。
- T13 状态：`ISOLATED_READY + PRODUCTION_AUTHORIZATION_REQUIRED`。不是 `ACCEPTED`，不是 `DEPLOYED_VERIFIED`；不自动进入 T14，不合并、不删除 Worktree、不操作正式数据。
- 下一任务：Final Acceptance；先清除下方所有平台、真实服务、规模、供应链与用户验收门禁，再由用户另行明确生产切换授权。

## Career Review 稳定化：T00 基线 / T01、T02、T03、T04 已收口，2026-09-19

- 基线：记录 T00 时原工作树 `main` 的 HEAD 为 `82af33dfe4d572e6ab04f36f3757b13a28049037`，当时唯一未跟踪文件是 `docs/execution/IMPLEMENTATION-PLAN.md`，已按原 hash 纳入隔离基线，原目录未写业务代码。此后原目录出现 `Career-review/` 未跟踪资料；它们与未核实子线程临时树同 hash，本轮未读取其内容、未修改、未删除、未纳入交付，按现状保留。
- 隔离工作树：`/Users/frog/Projects/Career-worktrees/review-t00-t01-20260919`，分支 `codex/review-t00-t01-20260919`。虚构数据目录：`/tmp/career-t00-data.sONDvl`，权限 `0700`；未使用生产数据库、真实 Keychain、正式端口或周备份任务。
- 运行环境：Python `3.9.6`、Node `v22.23.2`、npm `10.9.8`；前端依赖按 `package-lock.json` 在隔离树安装。测试进程清除 `CAREER_AI_API_KEY`、`OPENAI_API_KEY`、`CAREER_AI_MODEL`、`CAREER_AI_BASE_URL`；假供应商使用现有 `TestProvider`，秘密测试使用 `MemorySecretStore`，未发起真实出站请求。
- T00 状态：`CODE_VERIFIED`（static/unit/integration）。`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL CAREER_DATA_DIR=/tmp/career-t00-data.sONDvl PYTHONPATH=src /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q`：exit `0`，`161 passed`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；假供应商/安全定向测试未产生真实出站。
- T00 Review 对照：排期的 `scheduled_at: null` 和取消在当前 `frontend/src/interview-ui.ts` 共用 null 拦截；准备/Raw/Final Review 保存成功后没有用服务端响应更新本地 revision；当前弹窗没有统一的独立 dirty 关闭保护。原问题在当前代码仍存在，未标记 `ALREADY_FIXED`。
- T01 状态：`CODE_VERIFIED`（static/unit/integration，browser partial）。修改 `frontend/src/interview-ui.ts`、`frontend/src/main.ts`、新增 `frontend/src/edit-session.ts`，并在 `tests/test_interview.py` 增加 nullable timestamp、连续保存和 409 冲突回归；后端合同未需修改。
- T01 验证日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL CAREER_DATA_DIR=/tmp/career-t00-data.sONDvl PYTHONPATH=src /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q`：exit `0`，`164 passed`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`git diff --check`：exit `0`。
- T01 浏览器日志：隔离服务 `127.0.0.1:18765` + 虚构机会 `虚构公司 T01 / T01 面试工程师`；日期对话框关闭未改变原排期，填写 `2026-10-05` 后页面保留该日期；准备表单连续保存两次均显示“已保存”，第二次输入为“第二版准备”。未保存 Raw 关闭路径确实触发原生 confirm，但 IAB 的阻塞式 confirm 令浏览器控制通道超时，Esc/遮罩/路由继续编辑或放弃选择未取得完整 browser evidence，不能标记 `ACCEPTED`。
- T01 只读审查：主线程按规格轴/规范轴检查了实际 diff、旁路、revision 更新、dirty 聚合、关闭/路由/`beforeunload` 入口，并复跑 3 项定向回归，未发现需要返工的问题。独立审查缺失：宿主创建子线程仅返回 `clientThreadId`，未提供可核实的实际 Luna/High 元数据，因此没有把该子线程作为实施或审查证据。
- T02 开工复核：在同一隔离工作树用真实 `Store`、`TestProvider` 和临时数据确认旧问题仍在：Research 更新返回 `200` 但 Interview 与 Research 的物理 ID 不一致，`ids_equal=false`；旧提案缺少 `manifest`，原路径只有 revision 约束。未复用缩减 SQL 作为证据。
- T02 状态：`CODE_VERIFIED`（static/unit/integration；真实浏览器链未在 T02 重跑）。新增 `src/workbench/research_store.py` 作为 CompanyResearch/OpportunityResearch 唯一读写入口，保留旧物理 ID、规范化旧 item 缺省为 `unknown`、重复读取不写入或 bump，并在规范 owner 冲突时报告 `research_owner_conflict`。新增 `src/workbench/context_manifest.py`，Research、Interview Patch、Resume AI proposal 均绑定 target/dependencies/expected-absence；接受在同一事务复核，stale 分为 `source_changed`/`target_changed`，旧无 manifest 只能查看/拒绝，不能接受或自动重新调用模型。
- T02 回归日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL CAREER_DATA_DIR=/tmp/career-t00-data.sONDvl PYTHONPATH=src /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q tests/test_research.py`：exit `0`，`10 passed`；同环境全量 `pytest -q`：exit `0`，`174 passed`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`，仅保留既有大 chunk warning；`git diff --check`：exit `0`。
- T02 只读审查：主线程检查了实际 diff、Research 写入旁路、旧/新 ID、owner 冲突、manifest stale、拒绝优先、原子失败和来源 hash/revision 校验；未发现需要返工的问题。独立审查缺失：宿主仍只返回 `clientThreadId`，不能核实子 Agent 实际模型为 Luna/High，因此本轮不把它记为独立审查。
- T02 未验/阻断：未执行真实浏览器用户链；本轮没有 T02 前端改动，API/领域链使用虚构资料和假供应商已实际验证。真实模型、Keychain、生产数据库、周备份、部署和 Git push 均未触碰；T01 的部分浏览器证据继续保留到最终验收，不阻断无依赖任务。
- T03 开工复核：在同一隔离工作树核实四条生成路径与 legacy analyze 均直接经 `ModelGateway` 出站，原有 proposal/command 幂等位于供应商调用之后或未统一覆盖；问题仍存在，未重复修改 T02 已解决的 Research 正本与 manifest 绑定。
- T03 状态：`CODE_VERIFIED`（static/unit/integration；浏览器与真实供应商未验）。新增 `src/workbench/ai_operations.py`，以 `(task_type,target_kind,target_id,idempotency_key)` 唯一约束在准备前抢占 operation，区分 `reserved/dispatching/succeeded/failed/outcome_unknown`，在 provider 前持久化 dispatch marker 与最终 payload hash；Research、Resume AI suggestion、Interview Final Review、Interview Research Patch 和 legacy analyze 统一接入。新增数据库原子单 outbound slot，繁忙且尚未发送返回 `429 busy`；超时、进程中断、生成后持久化不确定均禁止同 key 自动再调用。
- T03 关键证据：`tests/test_ai_operations.py` 11 项使用 `CountingFakeProvider`；每次 `complete` 递增 `call_count`、返回带调用序号的不同内容，并直接断言供应商调用次数。相同 key 串行请求 5 次为 `call_count == 1`；首调用阻塞期间其余 4 个并发请求均进入 `_existing`，最终仍为 `call_count == 1`；Research 与 Resume 同 key 不同输入为 `409` 且不增加调用；成功后清空内存结果并重启，重放仍为 `call_count == 1`；`outcome_unknown` 重放仍为 `call_count == 1`。原四路径、搜索去重、busy、空 Research、持久化失败和 Final Review 重启证据继续保留；未发生真实供应商出站。
- T03 验证日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL CAREER_DATA_DIR=/tmp/career-t00-data.sONDvl PYTHONPATH=src /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q tests/test_ai_operations.py`：exit `0`，`11 passed`；同环境 `pytest -q`：exit `0`，`185 passed`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`（保留既有大 chunk warning）；`git diff --check`：exit `0`。
- T03 只读审查：主线程按规格轴/规范轴复核实际 diff、所有 ModelGateway 调用点、provider 前置登记、竞争失败、dispatch marker、状态迁移、旧 analyze 兼容、数据库 slot、结果过期与恢复；未发现需要返工的问题。无法核实 Subagent 实际为 Luna/High，故独立实施/独立审查缺失，不将宿主仅返回 `clientThreadId` 的子线程计为独立证据。
- T03 未验/阻断：Computer Use 已打开隔离 UI 并核对 AI 入口，但当前“更新研究”按钮每次点击生成新的随机 `idempotency_key`，不具备同一逻辑操作重试条件，因此未将其冒充为同 key 端到端证据；临时假服务、标签和活动假数据已停止/移出活动路径。真实浏览器同 key 用户链与真实收费模型仍保留到最终验收；真实 AI、Keychain、生产数据库、周备份、部署和 Git push 均未触碰，不阻断后续无依赖任务。
- T04 开工复核：重读 T04 任务卡、R05 对应历史证据、简历权威文档、当前实现和测试；确认旧正式路径为 `html2canvas → canvas image → jsPDF`，当前问题仍存在，未重复修改 T01–T03 已收口部分。
- T04 状态：`CODE_VERIFIED`（结构化 API/集成、真实 PDF 文本提取、冻结一致性、全量回归和前端构建通过；真实用户 PDF 查看/选择文字仍待最终验收）。新增 `src/workbench/resume_pdf.py`，使用本地固定 Chromium/Playwright 从结构化简历生成受控 HTML/CSS 的 A4 真文字 PDF，内嵌项目中文字体、禁用 JavaScript、拦截外部/文件资源、按实体换页；当前导出、版本保存和草稿投递统一服务端生成，冻结版本绑定 `document_hash`、artifact hash 与 renderer version。前端正式版本/投递不再上传客户端 PDF bytes，已移除 `html2canvas`/`jsPDF` 依赖。
- T04 冻结证据：虚构中文简历 A 冻结/投递后编辑为 B；已冻结 PDF、`editor_version` 和 `application.resume_snapshot` 仍为 A，新当前导出为 B。`pypdf` 普通提取结果为 3 页 A4，姓名、电话、邮箱、公司、岗位、日期、项目均存在且姓名→公司→岗位→项目顺序正确。
- T04 验证日志：`tests/test_resume_pdf.py`：exit `0`，`2 passed`；全量 `pytest -q`：exit `0`，`187 passed`；`npm run typecheck`：exit `0`；`npm run build`：exit `0`；`git diff --check`：exit `0`。PDF 文本提取使用虚构资料，`pdfinfo`：exit `0`，`Pages: 3`、`Page size: A4`。依赖仅增加锁定的 `playwright==1.51.0`、`pypdf==5.3.1` 及其直接运行依赖，未使用真实模型或个人资料。
- T04 只读审查：主线程按规格轴/规范轴复核 PDF 安全边界、文本层/中文字体/分页、服务端生成旁路、revision/hash 二次检查、冻结快照与旧 artifact 保留、依赖和测试证据，未发现需要返工的问题。无法核实 Subagent 实际为 Luna/High，故本轮由主线程串行完成，独立实施/独立审查缺失。
- T04 未验/阻断：Computer Use 已用本地虚构 PDF 尝试打开并执行 `super+a`/`super+c`，查看器 AX 仅暴露根节点、剪贴板为空且截图未显示完成的 PDF 页面，未取得真实用户“打开并选择文字”证据，保留到最终验收；成功 PDF 标签已关闭，早期失败标签 `id=3` 因浏览器 URL policy 阻止关闭，无法进一步操作。临时 HTTP 服务已停止。真实 Keychain、生产数据库、周备份、部署和 Git push 均未触碰；生产未改、未重启、未迁移。
- 下一动作：T05 已按后续明确指令完成并单独记录；不自动进入 T06。生产：未改、未重启、未迁移、未部署、未推送 Git。

- T05 开工复核：按 T05 任务卡、R07/R08/R09 对应范围、AI 权威文档、当前源码和测试核对；原始 Review 文件 `Career-deep-review-2026-09-18.md` 不在当前隔离树，故未虚构其全文内容，改用任务卡验收条款和当前代码复现。当前代码仍存在 `security -w <key>` argv、更新原地覆盖 ref、保存/测试/正式调用 URL 规则不统一、目的地变更留空 Key 复用旧 Key、DTO 无 `configured_ref`/`secret_status` 等问题；T01–T04 没有顺带解决这些部分。
- T05 状态：`CODE_VERIFIED`（static/unit/integration，browser partial；platform 未验）。保持单一主线程串行实施；宿主没有提供可核实的 Subagent 实际 Luna/High 元数据，因此没有把子 Agent 计为实施者或独立审查者。
- T05 实现：`src/workbench/secret_store.py` 改为显式 `keyring.backends.macOS.Keyring`，移除 `security` subprocess 和秘密 argv；加入安全错误分类及 `MemorySecretStore.allocate_ref`。`src/workbench/ai_config.py` 建立无秘密 `ai_secret_operation` journal、预分配新 ref、事务外写入/短事务 CAS 切换/补偿清理、删除先解除配置再清理、重启只处理 journal 已知 ref；DTO 分离 `configured_ref` 与 `secret_status`，启动后不携带上一进程的 `ready` 断言。`model_gateway.py`、保存和临时连接测试共用 URL/目的地规范化，拒绝 userinfo/query/fragment 和外部 HTTP；编辑目的地变化必须重新录入 Key。前端设置页显示 Key 状态并提示目的地变化时重新录入。新增固定依赖 `keyring==25.7.0` 及锁文件条目。
- T05 专项证据：`tests/test_t05_secret_config.py` 使用 Memory/Fake secret store 覆盖 30 项；直接断言假 Key 不进入数据库/DTO/备份、设置列表不调用 `get`、新 ref 的 put→CAS→old delete 顺序、目的地变化拒绝、等价默认端口/尾斜杠归一化、URL 三处共用拒绝、Keychain missing/locked/delete failure、真实 commit 失败后的旧 ref 可用、新 ref 清理、CAS 竞争、重启只删除 journal 已知 orphan、失败 journal `cleanup_pending`。
- T05 浏览器日志：隔离服务 `127.0.0.1:18766`、虚构配置 `虚构模型 / fake-model / https://example.test/v1`、后端 MemorySecretStore；设置页保存后显示“Key 已配置 · 当前使用”，编辑 Base URL 后留空 Key 显示“模型目的地已变化，必须重新录入 API Key；不会复用旧 Key”。标签和临时服务已关闭。
- T05 验证日志：专项 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q tests/test_t05_secret_config.py`：exit `0`，`30 passed`；受影响 AI 定向 `... pytest -q tests/test_t05_secret_config.py tests/test_ai_enhancements.py tests/test_providers_artifacts.py`：exit `0`，`47 passed`；T04 PDF 专项 `pytest -q tests/test_resume_pdf.py`：exit `0`，`2 passed`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`/Users/frog/Projects/Career/.venv/bin/python -m pip check`：exit `0`；`npm --prefix frontend ls`：exit `0`（node_modules 保留既有 extraneous 条目）；`git diff --check`：exit `0`。
- T05 全量回归补充：复现并修复 `tests/test_resume_documents.py::test_startup_cannot_quarantine_another_process_pending_pdf` 在 `assert renamed.wait(3)` 处实际 `False`、预期 `True` 的失败。单测原实现稳定失败；直接计时显示 T04 真实 Chromium `render_pdf` 冷启动约 `6.86s`，在测试要验证的 `after_rename` 事务边界之后才发出事件，故是测试把 PDF renderer 延迟耦合进恢复并发窗口，不是 T05 逻辑或共享状态。仅在该测试注入确定性的假 `render_pdf` 返回值，保留 `after_rename`、阻塞启动恢复和最终 artifact 校验；未改变生产 PDF 路径、核心断言或任意 timeout。修复后目标测试连续 5 次均 exit `0`，全量 `pytest -q`：exit `0`，`217 passed`。
- T05 平台未验：没有调用真实 Keychain、真实 Key、收费模型或生产资料；未做真实 macOS Keychain 权限/锁定/授权弹窗验证。T05 浏览器仅为虚构数据用户链证据，不能替代平台证据。生产数据库、真实附件、周备份任务、部署和 Git push 均未触碰。
- 下一任务：T06（统一发送清单、外发策略、审计和完整预算）；本轮到 T05 停止，不自动进入 T06。

- T06 开工复核：重新读取 T06 任务卡、`docs/02-context-contract.md`、`docs/03-architecture.md`、相关 Opportunity Context/UI 文档、当前源码和 T01–T05 机制；当前隔离树没有原始 `Career-deep-review-2026-09-18.md`，未虚构其正文。实际代码仍有四类 AI 入口和旧 `analyze` 直接进入 Provider，缺少统一的确认前准备、任务级资料白名单、Research 搜索二阶段确认、统一预算/审计和出站前 hash 复核；旧 `run` 还会持久化原始 payload。上述问题均在本批复现，未重复重构 T01–T05 已收口部分。
- T06 状态：`CODE_VERIFIED`（自动专项、全量回归、前端构建和静态审查通过）；`BROWSER_VERIFIED` 仅覆盖隔离虚构数据下 Research 的用户可见“搜索前确认”半链，未将未执行的搜索或模型执行冒充完整浏览器验收；`ACCEPTED` 尚未由用户确认。
- T06 实现：新增 `src/workbench/outbound_policy.py`，统一 task required/optional/forbidden sources、联系方式脱敏、10 分钟准备有效期、最终 payload preview/hash、来源/manifest 元数据和 256 KiB / 4096 tokens / 2 MiB / 50 sources / 10s-45s-90s / 单并发 / 零自动重试预算。`src/workbench/ai_operations.py` 将准备前抢占、running/succeeded/failed/outcome_unknown、dispatch marker、恢复和单出站槽统一落库；`model_gateway.py`、`providers.py`、`ai_config.py` 统一真实适配器/连接测试边界，流式响应超限、429/5xx/TLS/超时不吞错。`core.py`、`research.py`、`resume_documents.py`、`interview.py` 的 legacy analysis、Research、Resume AI suggestion、Interview Final Review/Research Patch 全部经相同 prepare→confirm→execute 路径；新 `run` 只留 `payload_meta` hash/预算，不再保存原始 Provider payload。`frontend/src/main.ts`、`frontend/src/editor/legacy-app.js`、`frontend/src/opportunity-ui.ts` 接入同 key 的请求预览和明确确认；无对应 AI 按钮的 Interview 页面未新增无关 UI。
- T06 关键证据：`tests/test_outbound_policy.py`、`tests/test_ai_operations.py` 及受影响旧测试使用隔离 Store、虚构资料、`TestProvider`/`CountingFakeProvider`；专项 `49 passed`。覆盖旧分析、Resume 脱敏、Research 搜索确认→模型确认、同 key 重复搜索仍仅一次、Interview 确认、同 key 重放/并发/输入变化/outcome_unknown/重启/持久化失败，以及 `ai_preparation`、`ai_audit`、`run` 不含原始 Provider payload；Provider 实际调用次数边界由 CountingFakeProvider 直接断言。
- T06 验证日志：专项 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL PYTHONPATH=src /Users/frog/Projects/Career/.venv/bin/python -B -m pytest -q tests/test_outbound_policy.py tests/test_ai_operations.py tests/test_research.py tests/test_resume_documents.py tests/test_interview.py`：exit `0`，`49 passed`；全量同环境 `pytest -q`：exit `0`，`221 passed in 179.11s`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`/Users/frog/Projects/Career/.venv/bin/python -m pip check`：exit `0`，无 broken requirements；`npm --prefix frontend ls`：exit `0`，node_modules 有既有 extraneous 条目；`git diff --check`：exit `0`。
- T06 浏览器日志：隔离服务 `127.0.0.1:18767`、隔离数据 `/tmp/career-t06-browser-20260919`、TestProvider 和虚构机会“虚构浏览器公司 / 虚构产品岗位”；Computer Use 打开“更新岗位情报”后先显示搜索范围和“确认开始搜索”，未点击确认，故未触发真实搜索或模型。标签已关闭、服务已停止；临时数据目录保留在系统临时区，不属于项目或生产目录。
- T06 只读审查：主线程按规格轴/规范轴检查了所有 `ModelGateway` 出站点、旧 `RealProvider` 兼容边界、准备记录留存、来源/manifest/hash、状态恢复、审计失败和前端同 key 连续确认；未发现需返工的问题。无法核实 Subagent 实际为 Luna/High，故本批由主线程串行完成，独立实施/独立审查缺失。
- T06 未验/阻断：真实 Provider、真实 Keychain、真实收费模型、完整 Research 搜索及模型执行浏览器链、Interview AI 用户按钮链未验；真实 PDF 文字选择、T01/T04 等既有人工验收继续保留到最终验收。以上不阻断后续无依赖任务。生产数据库、真实附件、周备份任务、部署和 Git push 均未触碰。
- 下一任务：T07；本轮到 T06 停止，不自动进入 T07。

## Career Review 稳定化：T07 Research 证据、更正与待处理建议，2026-09-19

- T07 开工复核：重新读取 T07 任务卡、Opportunity Research/Context 权威文档、T02/T03/T06 相关机制、当前 Research 源码与测试；原始 `Career-deep-review-2026-09-18.md` 仍不在隔离树，未虚构其正文。当前代码仍允许标题/URL-only 的模型输出保留 `fact/inference`，Research item 没有 evidence status/摘录元数据，手动来源没有 owner 校验，机会页不返回可重开的 pending proposal；T02/T03/T06 已解决的 owner/manifest/AI operation 部分直接复用，未重复重构。
- T07 状态：`CODE_VERIFIED`（static/unit/integration/browser）。按计划状态定义，`ACCEPTED` 未由用户在本轮确认；浏览器证据已取得但不替代自动不变量测试。保持主线程串行实施与只读审查；无法核实 Subagent 实际模型为 Luna/High，因此独立实施/独立审查缺失，不将子 Agent 计为独立证据。
- T07 实现：`src/workbench/research_store.py` 为 item 增加 `evidence_status`（`lead/excerpt_present/user_confirmed/unknown`）、`evidence`（owner、source type、input method、scope、日期、content hash、item revision）、`verification`、item revision/status 及显式 `supersedes/replaces`；旧条目缺省为 `unknown`，保留原内容和历史，不伪造认证。`src/workbench/research.py` 将搜索标题/URL 固定为 lead，模型不能升级为 fact/inference；过滤空/验证码样式结果，标记日期过旧/未知，拒绝 forged/cross-opportunity source，提供同 owner/source/content hash 的 duplicate hint；手动更正使用稳定 item_id 与文档 CAS，缺失 404，新增按 item_id 撤回为 `retracted`，并把请求控制字段排除出 item 正文。
- T07 UI：`frontend/src/opportunity-ui.ts` 显示事实分类与证据状态、用户摘录和来源日期；手动编辑使用受控分类、用户摘录和“我已核对”确认动作；支持按稳定 item_id 更正/撤回；机会页列 pending proposals，重开后查看/接受/拒绝已有建议，过期建议显示原因并保留拒绝入口，重复项只提示不自动合并。未增加自动正文抓取或全局 Inbox。
- T07 关键证据：新增 `tests/test_t07_research_evidence.py`，使用虚构资料和 `CountingProvider/MisleadingProvider` 覆盖 title prompt injection、过期日期、验证码结果零 Provider 调用、用户摘录/用户确认、伪造来源 ID、跨机会来源、稳定 item 更正、并发 CAS、撤回、pending proposal 重启重开；重复重开断言 Provider `call_count` 仍为 `1`。T07 专项及相关 Research/AI 回归：`39 passed`。
- T07 验证日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q tests/test_t07_research_evidence.py tests/test_research.py tests/test_ai_operations.py tests/test_ai_enhancements.py`：exit `0`，`39 passed`；同环境全量 `pytest -q`：exit `0`，`230 passed in 142.85s`；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`uv run --no-project --with-requirements requirements.txt python -m pip check`：exit `0`，无 broken requirements；`npm --prefix frontend ls --depth=0`：exit `0`，仅报告既有 extraneous node_modules 条目；`git diff --check`：exit `0`。
- T07 浏览器日志：最终隔离服务 `127.0.0.1:18779`、`CAREER_AI_PROVIDER=test`、临时数据 `/tmp/career-t07-browser-final-20260919`、虚构机会“**T07 最终浏览器虚构公司 / 证据状态验收岗位**”；Computer Use 实际保存用户摘录并勾选“我已核对摘录”，页面显示 `fact / 用户已确认`，并在前一轮同类隔离验收实际完成更正和撤回；console error/warning 为 `[]`，标签和服务已关闭。未触发 Web 搜索或模型调用。
- T07 只读审查：主线程按规格轴/规范轴检查了 evidence 状态降级、source owner/CAS、旧条目兼容、proposal stale/reject、重启读取、UI pending 入口、无自动正文抓取和 diff；发现并修正了分类自由文本导致真实用户输入 422、缺少显式 user confirmation、source date_status 未随 proposal item 保存及控制字段写入 item 的问题；修正后专项、全量、前端构建和浏览器链全部复验通过。
- T07 未验/阻断：真实 Provider、真实网页正文抓取（按 T07 明确不在范围）、真实 Keychain、真实收费模型、生产数据库/真实附件、周备份任务、部署和 Git push 均未触碰；待处理 proposal 的重开/零新增 Provider 调用已由 API 重启测试验证，未在浏览器执行真实 Web Research 重开链。无阻断下游的 Gate。
- 下一任务：T08；本轮到 T07 停止，不自动进入 T08。

## Career Review 稳定化：T08 Resume AI 字段级建议与冻结事实保护，2026-09-19

- T08 开工复核：重新读取 T08 任务卡、`docs/00-authority.md`、`docs/02-context-contract.md`、Opportunity 简历权威文档、当前简历实现与 T01–T07 相关机制；原始 Review 文件仍缺失，按用户指定以 `IMPLEMENTATION-PLAN.md` 为唯一施工图，并以当前代码事实核实范围。旧 `resume_documents.py` 会接受 Provider 返回的整份 `document` 并整体替换，前端只显示整稿前后结果且没有逐条待处理/重开入口，原问题仍存在；T01–T07 没有顺带解决，不重复其幂等、manifest、PDF 或 Research 机制。
- T08 状态：`CODE_VERIFIED + BROWSER_VERIFIED`；`ACCEPTED` 尚未由用户确认。主线程按规格轴/规范轴完成只读审查；未核实到 Subagent 实际 Luna/High 元数据，因此本批由主线程串行完成，独立实施/独立审查缺失，不将任何子线程计为独立证据。
- T08 实现：`src/workbench/resume_documents.py` 将 Resume AI 输出收敛为带 `change_id`、稳定 `item_id`/白名单 `field`、`before_hash`、`proposed_text`、`source_refs`、`reason`、`requires_fact_check` 的字段变更；拒绝整份旧 `document` 输出、未知条目/字段、身份/组织/职位/日期/教育等锁定字段和 manifest 外来源；数字/单位/时间文本自动标记需核对。接受时复核 manifest、整稿 revision 和每个字段 hash，支持用户选择/编辑，所有选中变更一次 CAS 保存，失败不产生部分写入；版本、投递快照和 PDF 冻结语义未改变。`model_gateway.py` 将 v2 输出约束带入 Provider 提示，`providers.py` 的假 Provider 改为字段变更形状。
- T08 UI：`frontend/editor.html`、`frontend/src/editor/legacy-app.js`、`frontend/src/editor/legacy.css` 增加逐条 before/after/source/reason/fact-check 展示、选择、编辑、接受/拒绝、待处理建议列表和重开；重开读取已持久化 proposal，不重新生成模型请求。`src/workbench/README.md` 记录字段白名单与过期处理合同。
- T08 关键不变量测试：新增 `tests/test_t08_resume_suggestions.py`，全部使用隔离 Store、虚构中文简历、假 Key/假 Provider；覆盖旧整稿输出在落库前拒绝、字段白名单与锁定身份字段、数字改写强制 fact-check、同一 proposal 选择性编辑且多项原子应用、未选项不变、未知/伪造来源拒绝、revision/hash 过期禁止部分写入、应用重启后 pending proposal 重开不新增 Provider 调用，以及长文本不改变结构。专项 `... pytest -q tests/test_t08_resume_suggestions.py`：exit `0`，`8 passed`；受影响回归：exit `0`，`63 passed`。
- T08 浏览器证据：隔离服务 `127.0.0.1:18788`、`CAREER_DATA_DIR=/tmp/career-t08-browser-20260919`、自定义假 Provider 和虚构简历；Computer Use 实际完成“生成→逐字段查看→用户编辑→接受选中→待处理建议重开”，页面显示编辑后的技能文本，组织/职位/日期/项目保持不变；重开复用 pending proposal，没有重新生成入口。浏览器标签已关闭，临时服务已停止；未调用真实 Provider、真实 Key 或收费模型。
- T08 验证日志：全量 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q`：exit `0`，`238 passed`、1 warning；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`uv run --no-project --with-requirements requirements.txt python -m pip check`：exit `0`，无 broken requirements；`npm --prefix frontend ls --depth=0`：exit `0`，仅报告既有 extraneous node_modules 条目；`git diff --check`：exit `0`。
- T08 未验/阻断：真实 Provider、真实 Keychain、真实收费模型、真实用户资料、生产数据库/附件、周备份任务、生产网页和生产环境仍保留到最终验收；本批没有部署、Git push 或生产写入。现无阻断 T09 的技术 Gate。
- 下一任务：T09；本批到 T08 停止，不自动进入 T09。

## 历史：Career Review 稳定化 T09 配对会话与可信启动器，2026-09-19

> 历史实现与验收记录。一次性配对、Bearer、浏览器恢复会话及对应前端流程已于 2026-09-24 从当前个人本机版退役；请勿把以下规格、阻断项或测试结论当成当前要求。运行身份核验、单实例锁和启动器控制凭据继续保留。

- T09 开工复核：重新读取 T09 任务卡、`docs/00-authority.md`、Opportunity 工程/Context 合同、当前 `app.py`、`scripts/run.py`、`scripts/macos_app.py`、前端请求适配及 T01–T08 机制。当前代码只有 loopback Host/Origin/写请求头检查：`/api/state`、业务 API、artifact 无 Bearer 会话；启动器只按 PID 文件存活并可直接 `SIGTERM`，没有配对码、重启失效会话或 OS 单实例锁；问题仍存在，未重复建立 T03/T05/T06/T08 已有机制。
- T09 状态：`CODE_VERIFIED + BROWSER_VERIFIED`；`ACCEPTED` 尚未由用户确认。浏览器证据为隔离 IAB 用户链，不计为 Chrome 独立验收；真实 Mac/Chrome 平台项保留为 `PLATFORM_VERIFICATION_REQUIRED`。主线程完成规格轴/规范轴只读审查；无法核实 Subagent 实际 Luna/High，因此本批主线程串行实施，独立实施/独立审查缺失。
- T09 实现：新增 `src/workbench/local_session.py`，为每个运行实例生成 128-bit 一次性配对码（5 分钟、一次消费、owner-only 文件）、256-bit Bearer 会话（8 小时、仅进程内、重启后失效）和仅保存 digest 的同源本机恢复凭据、受保护控制凭据、数据实例/启动实例身份和诊断信息。`src/workbench/app.py` 将匿名面收敛为静态无资料页面、最小 `/healthz`、`/api/pair` 和仅凭恢复凭据换发新内存会话的 `/api/session/resume`；业务 API、artifact、配置、state 和诊断均需会话，Origin/Host/写请求头仍保留；提供退出、授权诊断和优雅停止控制路径，健康响应不泄露数据目录或秘密。
- T09 启动器：`scripts/run.py` 使用 OS `flock` 单实例锁，写入 owner-only PID+启动时间+实例身份元数据，锁和元数据在进程退出时清理；`scripts/macos_app.py` 只在 PID、OS 启动时间、实例身份和受保护控制通道均验证后复用/停止，不再按 PID 猜测终止未知进程；健康复用还核对 build/static resource、startup instance 与 data instance。`pair` 子命令只在交互式 TTY 显示配对码，不写日志、URL、argv 或环境变量。
- T09 前端：新增 `frontend/src/local-session.ts`，所有主站、简历编辑器和敏感下载使用 `Authorization: Bearer`；Bearer 仅进 `sessionStorage`，同源本机恢复凭据单独持久保存且只用于换发新的内存 Bearer；无 token 时先尝试恢复，再向同源已有 Career 标签页请求内存会话转交，无可用路径才提示配对，IAB 不支持原生 `prompt()` 时使用同页配对输入回退；PDF、截图和反馈导出改为鉴权 fetch + Blob，设置页提供“退出本地会话”，build ID 不匹配提示重载。`tests/conftest.py` 仅为旧 TestClient 设置 `CAREER_TEST_MODE=1`，生产启动器不设置该变量。
- T09 关键不变量测试：新增 `tests/test_t09_local_session.py`，覆盖未配对 state/artifact/API docs 拒绝、最小 health、配对码一次消费、token 退出/过期/重启失效、Origin/Host、不同运行实例隔离、授权诊断不泄露路径/配对码、PID+启动身份校验和第二启动器被 OS lock 拒绝；`tests/test_macos_app.py` 更新为验证未知服务不复用、已验证服务才打开页面。专项 `... pytest -q tests/test_t09_local_session.py tests/test_macos_app.py tests/test_http.py`：exit `0`，`13 passed`。
- T09 浏览器证据：隔离服务 `127.0.0.1:18789`、`CAREER_AI_PROVIDER=test`、`/tmp/career-t09-browser-20260919` 与 `/tmp/career-t09-runtime-20260919`；未配对时业务页面显示本地配对输入，输入虚构实例配对码后主页面可读，重载保持会话，设置页点击“退出本地会话”后立即回到配对页；浏览器 error/warn 日志为 `[]`。IAB 标签已关闭，临时服务已停止。Chrome 隔离会话打开本地地址被客户端 `ERR_BLOCKED_BY_CLIENT`，未将其冒充为 Chrome 验收。
- T09 全量验证：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q`：exit `0`，`247 passed`、1 warning；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`uv run --no-project --with-requirements requirements.txt python -m pip check`：exit `0`，无 broken requirements；`npm --prefix frontend ls --depth=0`：exit `0`，仅报告既有 extraneous node_modules 条目；`git diff --check`：exit `0`。
- T09 未验/阻断：真实 macOS `Career.app` 冷启动、连续双击、无关端口占用、旧 build、PID 重用、启动失败/延迟退出、陈旧静态资源和真实 Chrome 独立链仍未验，按任务卡保留 `PLATFORM_VERIFICATION_REQUIRED`；真实 Keychain、真实 Provider、生产数据库/附件、周备份任务、部署和 Git push 均未触碰。无阻断 T10 的代码 Gate。
- T09 最终发布阻断清单（用户补充）：真实 macOS `Career.app` 冷启动、连续双击、端口占用、旧 build、可信停止/PID 身份、真实 Chrome 配对与完整用户链；这些项目在最终合并主项目前必须逐项验证，不得以 mock/IAB 证据替代。
- 下一任务：T10；本批到 T09 停止，不自动进入 T10。

## Career Review 稳定化：T10 周备份完整性与可恢复性，2026-09-19

- T10 开工复核：重新读取 T10 任务卡、`docs/00-authority.md`、`docs/03-architecture.md`、备份/恢复 README、当前 `src/workbench/backup.py`、`scripts/weekly_backup.py`、`migration_baseline.py` 及 T01–T09 相关附件/会话机制；原始 R16 Review 文件仍缺失，以 `IMPLEMENTATION-PLAN.md` 和当前代码事实为施工依据。原问题仍存在：同周目录只按存在跳过、不校验 manifest/schema/SQLite/附件 hash；孤儿直接使备份失败；登记附件缺失直接失败；失败会删除 `.partial-*`；没有恢复状态记录。未重复 T09 会话/启动器机制。
- T10 状态：`CODE_VERIFIED`；无用户可见前端改动，`BROWSER_VERIFIED` 不适用；`ACCEPTED` 待最终用户确认。主线程完成规格轴/规范轴只读审查；无法核实 Subagent 实际 Luna/High 元数据，因此本批主线程串行实施，独立实施/独立审查缺失，不将任何子线程计为独立证据。
- T10 实现：`src/workbench/backup.py` 新增只读 `verify_backup`、显式 `complete/complete_with_quarantine/incomplete` manifest 状态、同周损坏后的 `.repair-<id>` 发布、登记附件缺失/损坏的 `needs_attention`、孤儿附件的 hash-bound `quarantine`、SQLite schema/integrity/foreign-key/hash 校验、文件/manifest/directory `fsync`、唯一 `.partial-*` 原子发布和可辨认中断残留；`restore` 只恢复到不存在的新目录，允许显式 incomplete 部分恢复但不标为健康，并记录恢复校验时间。`scripts/weekly_backup.py` 复用上述验证，只有健康恢复点才跳过，状态写入备份目录 `.career-weekly-status.json`（`last_success_at`、`last_restore_verified_at`、`last_error`、`recovery_point_age`）。
- T10 锁边界：新增 `src/workbench/attachment_lock.py`，并将 `Store` 写事务、PDF/截图写入、resume staging/recovery 与备份统一为“附件生命周期锁 → SQLite 写锁”；避免备份持附件锁时写路径反向等待 DB 锁，也避免文件发布与登记之间被备份截断。未修改或运行 `scripts/install_weekly_backup.py`，未改变用户既有每周任务。
- T10 关键不变量测试：新增 `tests/test_t10_backup.py`，全部使用隔离临时目录、虚构记录和假 Provider；专项及相关备份回归 `18 passed`。覆盖同周 manifest 篡改后保留原目录并生成 repair、孤儿复制到 quarantine 且源文件不删除、登记附件缺失/损坏与危险/超长路径发布 `incomplete`、中断保留 `.partial-*`、schema/SQLite/hash 验证、恢复到新目录、只读验证不启动 Store，以及 1000 个虚构附件 4 线程并发人工保存与备份并行的 P95 对比。最近一次压力日志：基线 `0.0302s`、备份中 `0.0074s`、增量 `-0.0229s`；两次运行均未超过 500ms 预算。
- T10 验证日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q -s tests/test_t10_backup.py tests/test_backup.py tests/test_migration_baseline.py`：exit `0`，`18 passed`、1 warning；全量 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q`：exit `0`，`256 passed`、1 warning；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`uv run --no-project --with-requirements requirements.txt python -m pip check`：exit `0`，无 broken requirements；`npm --prefix frontend ls --depth=0`：exit `0`，仅报告既有 extraneous node_modules 条目；`git diff --check`：exit `0`。
- T10 未验/阻断：未运行 `install_weekly_backup.py`，未读取/改写正式周备份任务，未用生产数据库或真实附件做恢复；最终发布阻断清单加入：真实 macOS 周任务执行、真实测试备份完整性验证、恢复到全新隔离目录、从恢复数据读取业务记录和附件、至少一个真实/受控文件系统失败场景，保留 `PLATFORM_VERIFICATION_REQUIRED`。异机灾备作为后续能力记录，不作为本轮默认发布阻断项。真实 Keychain、真实 Provider、收费模型、部署和 Git push 均未触碰。无阻断 T11 的代码 Gate。
- 下一任务：T11；本批到 T10 停止，不自动进入 T11。

## Career Review 稳定化：T11 页面闭环、错误状态与按需加载，2026-09-19

- T11 开工复核：重读 T11 任务卡、`docs/00-authority.md`、Opportunity 目标页、Context/Architecture/Journey/Acceptance、当前主加载器、各列表 API、Interview 入口和 T01–T10 相关机制。当前代码仍把 `/work-domain` 失败 catch 成空集合；启动时无条件下载 `/journey`、`/knowledge`、`/domain`、`/work-domain`、编辑器版本和简历文档；机会/Wiki/工作域列表没有稳定分页游标；Interview 后端已有生成接口但页面没有“生成复盘建议”和真实轮次“提议研究补丁”入口。未重复 T01–T10 已建立的会话、AI 幂等、研究正本、冻结材料和备份机制。
- T11 状态：`CODE_VERIFIED + BROWSER_VERIFIED`；`ACCEPTED` 待最终用户确认。主线程串行实施并完成只读自审；无法核实 Subagent 实际 `Luna / High` 元数据，因此独立实施/独立审查缺失，不将任何子线程计为独立证据。
- T11 实现：`src/workbench/core.py` 与 `src/workbench/app.py` 增加不携带历史正文的 `state?view=summary`，并将当前岗位的 AI/投递状态收敛为摘要；`frontend/src/main.ts` 改为摘要首屏和按页面加载，维护页面级加载状态/请求序号，A→B 的迟到响应不再覆盖当前页，work-domain 失败保留已有数据并显示失败/重试；`src/workbench/pagination.py`、`opportunity.py`、`knowledge.py`、`work.py` 建立稳定排序、scope/order 绑定 cursor 的兼容分页接口，旧接口默认形状保留；`frontend/src/knowledge-ui.ts` 使用当前 Wiki 范围/类别的分页请求；`frontend/src/interview-ui.ts` 增加“生成复盘建议”和真实面试“提议研究补丁”，simulation 不渲染现实研究 Patch；`frontend/src/workspace.ts` 使用摘要状态决定当前动作。
- T11 关键不变量测试：新增 `tests/test_t11_pages.py`，使用隔离 Store、虚构机会/资料和 `TestProvider`，直接断言 summary 不返回 runs/applications/versions/artifacts/feedback 正文、机会/Wiki cursor 翻页无重复且 scope/view 不匹配返回 `409`，并断言前端不再把 work-domain 失败伪装为空且两个 Interview AI 入口存在；专项 `4 passed`。既有 Interview 测试继续直接断言 simulation 无 GenerateResearchPatch 能力。
- T11 浏览器证据：隔离 `127.0.0.1:8877` + 临时数据目录 + `CAREER_AI_PROVIDER=test`，用虚构机会/投递/真实轮次打开机会→Interview Detail；页面可见“生成复盘建议”和真实轮次“提议研究补丁”，点击生成在缺少虚构 Raw 时显示“资料不存在”，没有显示伪造的已生成结果；任职页可正常加载。IAB 标签已关闭，临时服务已停止。该证据计为 `BROWSER_VERIFIED`，不替代真实 Provider、真实 Keychain、真实 Chrome 或生产链验收。
- T11 验证日志：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q -s tests/test_t11_pages.py`：exit `0`，`4 passed`、1 warning；全量 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q`：exit `0`，`260 passed`、1 warning；`npm --prefix frontend run typecheck`：exit `0`；`npm --prefix frontend run build`：exit `0`；`uv run --no-project --with-requirements requirements.txt python -m pip check`：exit `0`；`npm --prefix frontend ls --depth=0`：exit `0`，仅既有 extraneous node_modules 条目；`git diff --check`：exit `0`。
- T11 未验/阻断：未调用真实收费模型/真实 Provider，未使用真实 Keychain、生产数据库、正式周备份、真实附件或部署；未取得真实 Chrome/真实 macOS 平台链证据。T09/T10 已登记的最终发布阻断清单继续有效：真实 macOS Career.app 冷启动/连续双击/端口占用/旧 build/PID 身份/Chrome 完整链，以及真实周任务、测试备份完整性、隔离恢复读回业务记录与附件、受控文件系统失败场景。T11 无新增生产代码 Gate。
- 下一任务：T12；本批到 T11 停止，不自动进入 T12。

## Career Review 稳定化：T12 类型、文档与回归体系，2026-09-19

- T12 开工复核：重新读取 T12 任务卡、`docs/00-authority.md`、Opportunity 四份目标正本、Context/Architecture/Acceptance、T01–T11 相关实现与测试；原始 Review 文件在当前隔离树仍缺失，未虚构其正文，以 IMPLEMENTATION-PLAN、权威文档和当前代码事实核对。问题仍存在：本轮触及的前端 API/DTO 使用开放 `Record<string, any>` / `Promise<any>` 边界，Resume/Interview/Research JSON 进入 UI 前无统一结构解析；Resume、Profile、Interview 链仍有跨模块私有 helper 调用；仓库没有 CI、浏览器回归入口和 R01–R18 实际测试映射。
- T12 状态：`CODE_VERIFIED`；`BROWSER_VERIFIED` 未标记，`ACCEPTED` 待最终用户确认。主线程使用 Luna/High 要求串行完成；无法核实 Subagent 实际模型配置，因此无独立 Subagent 实施或审查证据。
- T12 实现：新增 `frontend/src/contracts.ts`，为 Opportunity、Research、Interview、Resume 定义具体 DTO，加入 JSON envelope、Interview/Research/Resume 列表运行期校验；主加载器在相关页面使用这些解析边界，保留旧 view-model 兼容范围并未宣称全仓库消除所有松散类型。`editor.py`、`knowledge.py`、`communication.py` 暴露 Resume/Profile/Interview 跨模块公开 helper，`resume_documents.py`、`resume_pdf.py`、`profile.py`、`interview.py` 改用公开入口，旧私有别名只保留兼容层。新增 `tests/test_t12_quality.py`、`docs/execution/REGRESSION-MATRIX.md`、虚构 `tests/fixtures/t12_browser_fixture.json`、`scripts/review_checks.py`、`scripts/browser_regression.py`、`scripts/secret_scan.py` 和 `.github/workflows/quality.yml`；STATUS 顶部收敛为当前状态，旧批次原文保留。
- T12 关键测试：专项 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt pytest -q tests/test_t12_quality.py`：exit `0`，`5 passed`；类型/公开 helper 受影响回归（Resume、PDF、Interview、Profile）：exit `0`，`34 passed`。测试直接检查具体 DTO、运行期解析入口、无 `Promise<any>` 的 API 泛型边界、公开 helper、R01–R18 映射和真实 fixture/CI/local-check 文件，不以测试总数代替覆盖。
- T12 本地质量入口：`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --no-project --with-requirements requirements.txt python scripts/review_checks.py`：exit `0`；其中全量 `pytest -q`：exit `0`，`265 passed`、1 warning；frontend typecheck/build：均 exit `0`；`pip check`：exit `0`；`npm --prefix frontend ls --depth=0`：exit `0`，仅既有 extraneous node_modules 条目；secret scan：exit `0`，当前文件和 Git history 未命中配置的 secret-like 规则；Markdown 本地链接：exit `0`；`git diff --check`：exit `0`。
- T12 供应链证据：`npm --prefix frontend audit --audit-level=low --json`：exit `0`，锁定依赖无 npm audit vulnerability。`uv run --no-project --with-requirements requirements.txt --with pip-audit pip-audit -r requirements.lock --format columns`：exit `1`，扫描报告当前锁定的 `anyio 4.12.1`（FastAPI/Starlette 运行链，修复版本 `4.14.2`）、`click 8.1.8`（Uvicorn CLI 链，`8.3.3`）、`starlette 0.46.2`（FastAPI 运行链，报告修复版本范围 `0.47.2` 至 `1.3.1`）、`Pillow 11.3.0`（截图/附件验证运行链，`12.1.1` 至 `12.3.0`）、`pypdf 5.3.1`（PDF 提取测试链，最高报告修复版本 `6.16.1`）和 `pytest 8.3.5`（仅测试链，`9.0.3`）共 `131` 条已知漏洞记录。未做无依据全量升级或 `--force`；这些版本、可达性和修复版本保留为供应链后续处理项，不宣称扫描通过。
- T12 浏览器/CI证据：`npm --prefix frontend run build`：exit `0` 后运行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with-requirements requirements.txt python scripts/browser_regression.py`：exit `1`，本机缺少 Playwright Chromium；仅尝试本地缓存安装，下载在约 40% 长时间无进展后停止。入口默认只建临时 `TestProvider`、虚构 fixture 和 loopback 服务，不连接生产；`.github/workflows/quality.yml` 已配置但未在 CI 实际运行，不能把配置写成 CI 通过。
- T12 未验/阻断：本批不调用真实 Provider、真实 Keychain、生产数据库、正式周备份、部署或 Git push；浏览器回归入口、真实 Chrome/网页、真实平台链、真实供应商、T09/T10 `PLATFORM_VERIFICATION_REQUIRED` 发布清单和 T11 大数据规模验收继续留到最终验收。供应链扫描存在上述未修复漏洞记录，需后续兼容性评估和最小升级计划；不阻塞本批代码回归收口，但不能标记供应链清洁。
- 下一任务：T13；本批到 T12 停止，不自动进入 T13。

## T12.1 Python 依赖漏洞分类与最小修复，2026-09-19

- 基线审计：对原 `requirements.lock` 执行 `pip-audit` 为 exit `1`，报告 `131` 条记录、涉及 6 个锁定包；同一 advisory 的别名、重复数据库记录按 `package + advisory ID + fix version` 归一后为 70 个唯一 ID/fix 组合。未使用 `--ignore-vuln`。
- 运行边界核对：当前源码已经使用 Python 3.10 的 `str | None` 类型语法，CI 固定 Python `3.12`；用 Python `3.9.6` 解析当前 `requirements.txt` 虽能解析旧依赖，但创建当前 app 会在既有 PEP 604 注解处失败。因此本批不把历史环境中的 Python 3.9 误当作当前有效运行基线，也不借漏洞修复名义改生产环境。
- 最小升级：`anyio 4.12.1 → 4.14.2`（CVE-2026-63374 / GHSA-82r6-8w77-94w6：国际化域名 TLS 连接劫持；CVE-2026-64847 / GHSA-5p39-cfhj-2xmp：进程池 stderr 管道阻塞；Career 无直接 AnyIO 调用，B，升级风险低）；`click 8.1.8 → 8.3.3`（PYSEC-2026-2132 / CVE-2026-7246 / GHSA-47fr-3ffg-hgmw：`click.edit()` 命令注入；Career 不调用 `click.edit`，B）；`pillow 11.3.0 → 12.3.0`（下列 18 条图像解析/资源消耗发现，Career 之前在 `artifacts.py` 直接以 Pillow 解析不可信截图，A，升级并增加标准库边界校验）；`pypdf 5.3.1 → 6.16.1`（下列 41 条恶意 PDF 解析资源耗尽/死循环发现，仅测试中的普通文本提取路径，B）；`pytest 8.3.5 → 9.0.3`（PYSEC-2026-1845 / CVE-2025-71176 / GHSA-6w46-j5rx-g56g：Unix `/tmp/pytest-of-{user}` 本地竞争问题，仅测试链，B）。
- Pillow 的 A 类防护不只依赖版本：`artifacts.py` 已移除 `PIL.Image.open(...).verify()` 对用户提交 bytes 的调用，改为标准库实现的 PNG chunk/CRC/尺寸上限和 JPEG marker/尺寸上限校验；ReportLab 仍因自身依赖保留 Pillow，但 Career 当前没有把用户截图交给 Pillow。`tests/test_t12_1_dependency_security.py` 在屏蔽 `PIL` 模块时直接验证虚构 PNG 仍可保存。

### 原始 6 个包的逐条发现与分类

- `anyio==4.12.1`：`CVE-2026-63374 → 4.14.2`（IDNA 2003/TLS 连接劫持，Career 使用 HTTPX 同步客户端且没有 AnyIO `connect_tcp`/`TLSStream` 入口，B）；`CVE-2026-64847 → 4.14.2`（未排空进程池 stderr 导致阻塞，Career 没有 AnyIO process-pool/`to_process` 入口，B）。
- `click==8.1.8`：`PYSEC-2026-2132`（别名 `CVE-2026-7246`、`GHSA-47fr-3ffg-hgmw`）`→ 8.3.3`（`click.edit()` 可执行命令注入；Career 脚本使用 argparse/直接 Python API，无 `click.edit`，B）。
- `starlette==0.46.2`：`PYSEC-2026-1941`（`CVE-2025-54121`、`GHSA-2c2j-9gv5-cj73`）`→ 0.47.2`（大 multipart 文件 rollover 阻塞事件循环；Career 不调用 `request.form()`/`UploadFile`，JSON-only middleware 拒绝非 JSON，C）；`PYSEC-2026-1942`（`CVE-2025-62727`、`GHSA-7f5h-v6xp-fcq8`）`→ 0.49.1`（`FileResponse`/`StaticFiles` Range 合并平方复杂度；Career 曾使用两者，现由 middleware 在进入 Starlette 前拒绝 Range，A 已修复，依赖本身未升级）；`PYSEC-2026-161`（`CVE-2026-48710`、`GHSA-86qp-5c8j-p5mr`、`X41-2026-002`）`→ 1.0.1`（畸形 Host 改写 `request.url.path`；Career 的鉴权 gate 曾实际可触发，现严格校验 Host 并改用 ASGI scope path，A 已修复，依赖本身未升级）；`PYSEC-2026-2281`（`CVE-2026-48818`、`GHSA-wqp7-x3pw-xc5r`）`→ 1.1.0`（Windows UNC 静态文件解析触发 SMB/NTLM 泄露；本项目目标平台为 macOS/POSIX，D，环境不适用）；`PYSEC-2026-2280`（`CVE-2026-48817`、`GHSA-x746-7m8f-x49c`）`→ 1.1.0`（未限定 HTTP method 的 `HTTPEndpoint` 属性调用；Career 没有 `HTTPEndpoint` 路由，D）；`PYSEC-2026-249`（`CVE-2026-54283`、`GHSA-82w8-qh3p-5jfq`）`→ 1.3.1`（urlencoded `request.form()` 忽略字段/大小限制；Career 不调用 form parser 且 middleware 仅接受 JSON，D）；`PYSEC-2026-248`（`CVE-2026-54282`、`GHSA-jp82-jpqv-5vv3`）`→ 1.3.0`（非 `/` 路径参与 URL 重建；Career 鉴权判断已不读取 `request.url.path`，D）。Starlette 不升级是因为当前 FastAPI `0.115.12` 将其限制为 `<0.47.0`；为清除全部 Starlette advisory 需要升级 FastAPI/Starlette 主运行链，风险高于当前已验证的边界修复，保留为 C/D 后续兼容性任务。
- `pillow==11.3.0`：18 条均为恶意 PNG/JPEG/图像元数据解析导致的越界、内存耗尽、长时间运行或死循环类问题；每条均以 pip-audit 主 ID、别名和最小修复版本记录如下：`PYSEC-2026-2249 (CVE-2026-25990) → 12.1.1`；`PYSEC-2026-2250 (CVE-2026-40192) → 12.2.0`；`PYSEC-2026-165 (CVE-2026-42308) → 12.2.0`；`PYSEC-2026-2251 (CVE-2026-42309) → 12.2.0`；`PYSEC-2026-2874 (CVE-2026-42310) → 12.2.0`；`PYSEC-2026-2252 (CVE-2026-42311) → 12.2.0`；`PYSEC-2026-2253 (CVE-2026-54059) → 12.3.0`；`PYSEC-2026-2255 (CVE-2026-55379) → 12.3.0`；`PYSEC-2026-2257 (CVE-2026-55798) → 12.3.0`；`PYSEC-2026-2256 (CVE-2026-55380) → 12.3.0`；`PYSEC-2026-2254 (CVE-2026-54060) → 12.3.0`；`PYSEC-2026-3453 (CVE-2026-59205) → 12.3.0`；`PYSEC-2026-3451 (CVE-2026-59199) → 12.3.0`；`PYSEC-2026-3493 (CVE-2026-54058) → 12.3.0`；`PYSEC-2026-3454 (CVE-2026-59197) → 12.3.0`；`PYSEC-2026-3494 (CVE-2026-59198) → 12.3.0`；`PYSEC-2026-3495 (CVE-2026-59200) → 12.3.0`；`PYSEC-2026-3496 (CVE-2026-59204) → 12.3.0`。分类 A，已升级并移除不可信截图到 Pillow 的调用。
- `pypdf==5.3.1`：所有发现均要求恶意 PDF 进入 reader/writer，影响为 CPU/内存耗尽、长时间运行或死循环；Career 只在测试用普通 PDF 做文本提取，生产生成链为 Chromium，不读取用户上传 PDF。逐条为：`PYSEC-2026-1830 (CVE-2025-55197) → 6.0.0`；`PYSEC-2026-1833 (CVE-2025-62707) → 6.1.3`；`PYSEC-2026-1831 (CVE-2025-62708) → 6.1.3`；`PYSEC-2026-1832 (CVE-2025-66019) → 6.4.0`；`PYSEC-2026-1829 (CVE-2026-22690) → 6.6.0`；`PYSEC-2026-1828 (CVE-2026-22691) → 6.6.0`；`PYSEC-2026-1827 (CVE-2026-24688) → 6.6.2`；`PYSEC-2026-3015 (CVE-2026-27026) → 6.7.1`；`PYSEC-2026-3013 (CVE-2026-27024) → 6.7.1`；`PYSEC-2026-3024 (CVE-2026-27025) → 6.7.1`；`PYSEC-2026-3005 (CVE-2026-27628) → 6.7.2`；`PYSEC-2026-3027 (CVE-2026-27888) → 6.7.3`；`PYSEC-2026-3017 (CVE-2026-28351) → 6.7.4`；`PYSEC-2026-3014 (CVE-2026-28804) → 6.7.5`；`PYSEC-2026-3019 (CVE-2026-31826) → 6.8.0`；`PYSEC-2026-3023 (CVE-2026-33123) → 6.9.1`；`PYSEC-2026-3012 (CVE-2026-33699) → 6.9.2`；`PYSEC-2026-3006 (CVE-2026-40260) → 6.10.0`；`PYSEC-2026-3021 (CVE-2026-41168) → 6.10.1`；`PYSEC-2026-3007 (CVE-2026-41313) → 6.10.2`；`PYSEC-2026-3011 (CVE-2026-41312) → 6.10.2`；`PYSEC-2026-3026 (CVE-2026-41314) → 6.10.2`；`PYSEC-2026-3004 (CVE-2026-48156) → 6.12.0`；`PYSEC-2026-3016 (CVE-2026-48155) → 6.12.0`；`PYSEC-2026-3025 (CVE-2026-48735) → 6.12.1`；`PYSEC-2026-3020 (CVE-2026-49461) → 6.12.2`；`PYSEC-2026-3010 (CVE-2026-49460) → 6.12.2`；`PYSEC-2026-3022 (CVE-2026-54531) → 6.13.0`；`PYSEC-2026-3009 (CVE-2026-54530) → 6.13.0`；`PYSEC-2026-3018 (CVE-2026-54651) → 6.13.1`；`PYSEC-2026-3611 (CVE-2026-59938) → 6.14.0`；`PYSEC-2026-3610 (CVE-2026-59937) → 6.14.0`；`PYSEC-2026-3613 (CVE-2026-59935) → 6.14.2`；`PYSEC-2026-3612 (CVE-2026-59936) → 6.14.1`；`PYSEC-2026-3656 (CVE-2026-71852) → 6.15.0`；`PYSEC-2026-3655 (CVE-2026-71870) → 6.15.0`；`PYSEC-2026-3910 (CVE-2026-84310) → 6.16.1`；`PYSEC-2026-3912 (CVE-2026-82398) → 6.15.0`；`PYSEC-2026-3911 (CVE-2026-84311) → 6.16.1`；`PYSEC-2026-3913 (CVE-2026-84309) → 6.16.0`；`CVE-2026-57204 (GHSA-jm82-fx9c-mx94) → 6.13.3`。分类 B，升级到能覆盖全部当前记录的 6.16.1，并由 PDF 专项/全量回归验证。
- `pytest==8.3.5`：`PYSEC-2026-1845`（`CVE-2025-71176`、`GHSA-6w46-j5rx-g56g`）`→ 9.0.3`（本地用户可竞争 `/tmp/pytest-of-{user}`，仅测试工具链，不进入 Career 运行服务，B）。

- 最终审计：升级后执行 `pip-audit -r requirements.lock` 仍为 exit `1`，仅 `starlette==0.46.2` 的 14 条重复/别名记录（7 个唯一 advisory）存在；这不是假绿。`pip check`、全量回归、前端和本地质量入口均已重新执行。
- T12.1 状态：`CODE_VERIFIED`（供应链扫描保留真实残余；未标记供应链清洁或 `ACCEPTED`）。独立 Subagent 的实际 Luna/High 配置仍无法核实，本批由主线程串行完成，无独立审查证据。
- 下一任务：T13，等待用户明确指令；本批不进入 T13。

## Opportunity Enhancement Sprint — 已实现并部署，2026-09-18

Sidebar 拖拽排序、AI-Config/Keychain/ModelGateway、Interview/Resume/Research AI 增强已完成；完整范围和证据见 [Enhancement Sprint](OPPORTUNITY-ENHANCEMENT-SPRINT.md)。Production 已备份并以当前源码重启；此前已验证 DeepSeek 真实调用，本次检查发现当前 ModelConfig 与 Keychain 项已被删除，重新使用需在客户端填写新 Key。

## 导航默认首页收敛 — 已实现，2026-09-18

- 已移除“今天”一级入口及其专属首页内容；默认启动地址改为 `/`，由浏览器本地偏好决定实际进入的一级模块，旧 `#home` 深链接会回落到该默认模块。
- 一级导航支持桌面鼠标右键“置顶/取消置顶”，置顶模块自动移动到第一位并显示 home 标识；仅保存模块 ID 到 `localStorage`，不新增业务数据或服务端状态；拖拽排序继续使用原有本地顺序。
- Production Chrome 已核对一级导航不再显示“今天”，右键菜单可置顶/取消置顶并显示 home 标识；macOS `Career.app` 已重新生成，启动器测试 `2 passed`，前端 typecheck/build 与 `git diff --check` 通过。

## Opportunity MVP Production Cutover — 成功，2026-09-18

完整部署证据见 [Batch F §23](OPPORTUNITY-BATCH-F.md#23-opportunity-mvp-production-cutover2026-09-18)。

- 2026-09-18 18:27（Asia/Shanghai）正式启动 `0.7.0-batch-f` / schema v6；唯一 writer 为 PID `43589`，端口 `127.0.0.1:8765`，数据目录仍是 `/Users/frog/Library/Application Support/Career Data`。
- 部署来源固定为 `/Users/frog/Projects/Career-worktrees/batch-f`、commit `eafacb8427d80b36c5d569813157a55380c1d4bd` 及其已验收工作树；正式源码与 frontend dist 已由该工作树构建和核对，没有从旧 HEAD 重拼。
- 最终回滚点 `PRE_CUTOVER_BACKUP` 为 `/Users/frog/Library/Application Support/Career Data-backups/pre-cutover-20260918T101916Z`；独立恢复验证 `verified=true`、`differences=[]`。旧 v1 数据目录另完整保留于 `/Users/frog/Library/Application Support/Career Data-pre-cutover-v1-20260918T101916Z`，逻辑 snapshot 与切换前一致。
- 在最终备份的系统临时恢复副本严格执行 v1→v2→v3→v4→v5→v6，每段均 dry-run/apply/verify；五次 verify 均 `differences=[]`。无真实 Migration Gate；两个旧 Job 保持 legacy/defer，demo 公司冲突与 Interview 语义未知保持待核对，没有自动猜测。
- v6 切换后 integrity `ok`、外键无异常；原 `current=24/applications=1/records=27/revisions=146` 全部业务行保留，新增仅五条 migration manifest。Submission 六个原列及冻结 Resume/Artifact/Job/Opportunity snapshot 逐字节一致，ResumeVersion、PDF hash、Communication、Interview、Offer、Wiki/Candidate、Employment/Project 均核对通过。
- Production 浏览器只读 smoke 已通过六个 Pipeline View、Opportunity Workspace、统一 Resume Workspace、Timeline、Wiki、Employment/Project 与 390×844；legacy 保持 Unknown，console error/warning 为 0。验收没有业务 POST，数据库 snapshot 前后相同；唯一受控浏览器 tab 已关闭。
- 当前基础业务可以正式使用；真实 AI/AI-Config、Offer Comparison、深度 Research 与异机灾备仍未完成。本次没有用真实用户 Opportunity 重放完整写链，也没有实际触发 rollback。

## Opportunity MVP Finalization — 隔离实施与验收通过，2026-09-18

完整记录见 [Batch F §22](OPPORTUNITY-BATCH-F.md#22-opportunity-mvp-finalization2026-09-18)。

- 产品表面已收敛为唯一 Opportunity 管线、Opportunity Workspace 与一个多文档简历工作台；独立面试/足迹入口从主导航隐藏，旧深链接与历史资料继续兼容读取。“今天”一级入口已移除，默认首页由导航右键设置并仅保存在浏览器本地，不新增第二套任务状态。
- Workspace 先显示当前动作，再显示岗位情报、冻结投递材料和纯投影 Timeline；面试区聚焦当前/下一轮，用户不需要理解 Raw、Patch、ContextSnapshot、schema 或 revision。没有真实模型也可手工完成准备、模拟资料包外带、记录和复盘。
- 实际浏览器完整走通 Resume/Greeting→Submission→Communication→多轮 Real/Simulation/Raw/Review→Offer/谈薪→accepted，并覆盖无简历、rejected、withdrawn、两 Opportunity 隔离、旧核心数据读取、390×844 和零 console error/warning；唯一 tab 已关闭，临时服务已停止。
- 最终完整 Python 回归 `152 passed`；frontend build/typecheck 和 `git diff --check` 通过。风险 review 未发现双写正本、Timeline 事实、Simulation Patch、Employment 副作用或 schema v6 fence 回归。
- Production 最终仍为 0.2.0/schema v1、integrity ok、数据库 hash 不变；没有 Cutover、重启、迁移、业务 POST 或代码覆盖。Production Cutover 仍需后续显式授权。

## Opportunity Batch F — 隔离实施与验收通过，2026-09-18

已按 `$workbench-implement` 在 `/Users/frog/Projects/Career-worktrees/batch-f`（`codex/opportunity-f`）完成 Offer Vertical，并在原 v5 兼容 Gate 后实施最小 v5→v6 runtime fence；定点 `$workbench-review` 已通过。完整记录见 [Batch F §21](OPPORTUNITY-BATCH-F.md#21-schema-v6-fence实施与定点review2026-09-18)。

- 已实现唯一 current Offer、Record/Update/Accept、明确 `offered_role_title`、谈薪 Communication、三种 result、legacy 显式升级、纯投影 Timeline 与最基础 Offer Workspace；浏览器主链仍使用已通过的 F 功能验收证据。
- F runtime 现只接受 schema v6；v5→v6 migration 只增加一条 hash-bound manifest 并更新 `user_version`，业务行、Offer terms 和 schema objects 零改写。冻结 `0.6.0-batch-e` 在 Store 初始化、任何业务写入前拒绝 v6。
- 最终定向回归 `33 passed`；最终完整 Python 回归 `152 passed`；TypeScript/Vite build 成功，仅有已知大 chunk 提示。stale Offer revision 在 F 旧 adapter 返回 409，缺少 Offer revision 返回 422，冻结 E 则无法打开 v6。
- 最新生产备份的新隔离恢复副本完成 v1→v6；pre-v6 v5 rollback 恢复后 E 可读/F 拒绝，含 F Offer revision 1 的 v6 forward recovery 后 F 可读/E 拒绝。Production 保持 PID 2994、0.2.0/schema v1，DB hash/计数/附件未变。
- 本轮未进入 Offer Comparison、真实 AI/AI-Config、Employment/Project 或 Production Cutover；Batch F 隔离交付最终通过，下一批仍需新指令。

## Opportunity Batch E — 隔离实施与验收通过，2026-09-18

已按 `$workbench-plan` → `$workbench-implement` → `$workbench-review` 完成 [Batch E：完整 Interview Vertical](OPPORTUNITY-BATCH-E.md#20-实施与两轴验收记录2026-09-18)。

- 隔离交付位于 `/Users/frog/Projects/Career-worktrees/batch-e`（`codex/opportunity-e`），运行身份 `0.6.0-batch-e` / schema v5。实现 submitted→明确 ConfirmRealInterview→多轮 real→Preparation→0..N simulation→文本 Raw→当前 Final Review→real-only OpportunityResearch PatchProposal 确认闭环，并扩展纯投影 Timeline。
- 无日期确认创建 pending real；只有首次 submitted→interview 写 phase_changed_on。改期/待重约保持同一 ID；完成/永久取消不改变 Opportunity。Simulation 必须绑定同机会 real，且所有路径永远禁止 Patch。
- Context Pack 固定读取实际 Submission snapshot，不用当前 ResumeDocument；Simulation 可多选同机会历史 real/simulation Final Review，但默认不读对应 Raw。
- 复用现有 JSON/records typed 身份，没有机械新增业务表；schema v5 作为写契约门禁，v4→v5 migration 不重写旧业务行。旧 Interview 新建/关联 Note correction/candidate 旁路已停写；legacy Unknown 保留并只允许完整显式升级。
- 最终全量138通过，TypeScript/Vite build与实际浏览器完整主路径通过。最新真实生产备份已创建，隔离 v1→v5 clean verify、pre-E rollback、旧程序拒绝、含E写入 forward recovery通过；E inventory无真实Migration Gate。
- Production 最终仍为 PID2994、0.2.0/schema1，SQLite hash、表计数与附件hash保持；没有Cutover、重启、业务POST或源码/dist替换。Batch F具备隔离规划前置；Production Cutover、Offer、真实AI/AI-Config、Employment/Project仍不在当前授权内。

## Opportunity Batch D — 隔离实施与验收通过，2026-09-18

已按 `$workbench-plan` → `$workbench-implement` → `$workbench-review` 完成 [Batch D：Communication + Timeline 第一阶段](OPPORTUNITY-BATCH-D.md#20-实施与两轴验收记录2026-09-18)。

- 交付位于 `/Users/frog/Projects/Career-worktrees/batch-d`（`codex/opportunity-d`），运行身份 `0.5.0-batch-d` / schema v4。已投递机会支持 text/phone/other Communication Create/Update/Archive、CAS/幂等、ended 历史更正；Timeline 只投影 Opportunity/Submission/Communication，不建第二事实库。
- 删除采用对象内最小 archive；UI、默认 List/Detail/Timeline 隐藏，底层同 ID 与 legacy provenance 保留。无回收站、恢复 UI 或通用软删除平台。
- 旧 typed/JourneyNote 读取保留，两个旧新建入口及 typed Note correction 停写；Job alias/canonical URL 共用 scoped Domain Action，没有已知 Communication 双写旁路。phase/result 不受任何 Communication 动作影响。
- 完整回归129通过；review后定向18通过；TypeScript/Vite build和实际浏览器 U01–U10 通过。最新生产备份隔离v1→v2→v3→v4、旧程序拒绝、pre-D rollback和含D写入的v4 forward recovery通过；无真实Migration Gate。
- Production 最终仍为 PID2994、0.2.0/schema1，数据库/逻辑快照/附件hash及表计数保持；没有Cutover、重启、POST或源码/dist替换。具备在隔离环境规划 Interview Core 的前置，但未进入下一批。

## Opportunity Batch C — 隔离核心验收通过，2026-09-18

已完成workbench-implement → workbench-review；用户追加的统一Resume Workspace边界已落实，详细证据与未验边界见 [Batch C §17](OPPORTUNITY-BATCH-C.md#17-实施与两轴验收记录2026-09-1718)。

- 交付位于 `/Users/frog/Projects/Career-worktrees/batch-c`（codex/opportunity-c），基于完整B工作树；仅此目录实现schema3/0.4.0-batch-c。每Opportunity独立稿、三种显式来源、普通/特殊投递版本、Greeting当前值与冻结snapshot、一次投递/none、Profile显式刷新已接通；一个工作台UI、明确目录选择与返回来源机会。
- 最终全量120通过、前端build/tsc通过；真实浏览器双稿/冲突/PDF/none/统一导航及进程中断恢复已验证。原两profile失败按已确认产品目标消除隐式sync，未放宽CAS或跳过测试。
- 最新生产备份真实创建，隔离v1→v2→v3、旧程序拒绝、pre-C rollback、开写后v3 forward recovery通过；原199行/附件保全，C未猜测归属。完整PDF恢复分支228行/3个artifact/66个引用验证通过。
- 生产PID2994、0.2.0/schema1、DB物理/逻辑hash、附件、源码/dist保持。没有Production Cutover；生产原投递/面试/Offer写路径仍保留。
- 无新增真实资料Migration Gate，demo/legacy继续defer。具备Batch D隔离开发前置；本轮停止，不进入D。Resume Workspace Productization与AI Infrastructure → AI-Config仅在[Roadmap/Feedback](../07-roadmap.md)登记后续范围，AI-Config未实现。

## Opportunity Batch B — 隔离验收通过，2026-09-17

已按用户补充的Company匹配与禁止Production Cutover约束完成 workbench-implement → workbench-review。完整实现、测试、浏览器、迁移与恢复证据见[本批记录](OPPORTUNITY-BATCH-B.md) §11。

- 业务源码交付在 `/Users/frog/Projects/Career-worktrees/batch-b`（`codex/opportunity-b`）；原生产源码目录仅同步B记录和本状态，不回拷新业务代码/dist。现有未提交文档对齐/A改动不计为B。
- canonical Opportunity/Company、元数据与结束动作/CAS/幂等、六View与基础Workspace已实现；旧Job/plan.stage/context.company及旧投递/面试/Offer旁路受控。NFKC+trim+casefold身份匹配保留展示名，不猜别名、不合并主体。
- 最终兼容回归77通过；最后迁移安全/记录候选定向复验21通过（有重叠），typecheck/build通过。原profile基线仍1通过2失败，仅补测试创建Job所需幂等键，未改原revision断言或产品行为。
- 最新生产备份 `Career Data-backups/batch-b-20260917T133523Z` 已真实创建/隔离恢复。v2演练全部旧199行/PDF保全；新增1迁移manifest，2旧机会defer，0条被猜测迁入canonical。v1实际rollback恢复、旧程序拒绝v2、开写后v2 forward recovery和原v1活动/投递回放均已验证。
- 生产PID2994、0.2.0、schema1、数据库物理/逻辑hash、附件及源码/dist保持；无生产业务POST、重启或迁移。生产保留现有投递/面试/Offer能力。
- B批次结束时C具备隔离开发前置；当前C实施验收状态见上节。Production Cutover为后续显式部署授权，不能把隔离B当作完整生产替换。真实AI、无损逆迁移、异机灾备与完整C–G仍未验证/未实现。

## Opportunity Batch A — 2026-09-17

状态：可恢复迁移基线已完成，已按workbench-plan → workbench-implement → workbench-review规划、实施及独立验收；该轮结束时Batch B实施未开始，当前B状态见上节。完整范围、复现命令、manifest与恢复证据见[本批记录](OPPORTUNITY-BATCH-A.md)。

- 新增只读inventory/verify工具，补现有backup/restore目的地保护；schema仍为1，无领域迁移、前端改动或数据清理。两份审计与四份目标文档保持原文。
- 已从实际服务确认生产目录`~/Library/Application Support/Career Data`。真实备份已创建并恢复到新的系统临时目录；SQLite integrity、199条全表记录/ID/hash、冻结快照、版本、Raw/Wiki与1个PDF均一致。
- 旧服务自2026-09-15运行，启动器复用健康进程导致未加载更新源码。已先验证隔离副本启动，再受控重启生产为0.2.0；数据路径与Provider状态不变，逻辑内容和附件不变。现有初始化改变SQLite物理字节，未改业务记录或schema。
- 当前inventory无真实用户决策Gate；G1公司文字冲突、G2面试类型/业务日期未知均关联demo，保留为legacy兼容问题，不自动选值。未带demo标记的ResumeUse引用案例版本/PDF，必须保留；未标记本身不证明真实业务事实。
- 针对性测试9通过；原profile测试再次复现1通过、2失败。保存profile会同步当前全局草稿并提高revision；旧测试仍传0/旧revision而遇到409，第二项把错误JSON当document产生KeyError。读取最新revision的隔离HTTP场景通过；本批未修改profile/editor或旧测试，不宣称全套测试已通过。
- 具备规划并在隔离数据上启动Batch B的安全前置；生产迁移前仍须按届时数据重新盘点、备份和处理真实歧义。当前未验证真实AI、浏览器全流程、迁移/回滚代码或异机灾备。

## Documentation & Agent Alignment — 2026-09-17

当时状态：文档对齐完成；Gap Analysis增量路线已确认，实现Batch A/B及后续批次尚未开始。以下为该轮历史证据，Batch A现状见上节。

- 已对齐authority模块权威、AGENTS/README读取路由及三个Workbench Skill的文档加载方式；产品、Context、Architecture、Journey、Acceptance、Roadmap分别承接目标与验证范围。四份人工确认目标保持原文，AS-IS与Gap Analysis保持历史快照。
- 已区分Current Architecture / Stable Contracts / Target Direction，以及target acceptance与实际测试证据。独立机会稿、唯一Submission/Greeting冻结、real/simulation、当前Research、统一Raw/Patch、领域AI及Timeline等仍是TO-BE，不因文档修改变为已交付。
- 下一批建议：[Gap Analysis §8](../audit/OPPORTUNITY-GAP-ANALYSIS.md)的**A：建立可恢复迁移基线**；先细化允许范围、dry-run/备份恢复验收与冲突处理，不直接进入业务模型切换。
- 已知失败未修复：AS-IS运行71项中69通过、2失败，均在`tests/test_profile_ownership.py`的profile保存后旧revision选材路径；typecheck当时通过。本批未重跑业务测试，也未调整断言或实现。
- 运行身份问题未解决：AS-IS观察runtime自报0.1.0、source为0.2.0，准确加载组合未知。本批未查询生产服务、重启、构建或更改Provider配置；未接真实AI、未操作数据库或用户数据。默认生产备份目录当时为空，恢复能力仍需Batch A核验。
- 文档自审完成：13个允许的Markdown文件、95个本地链接及代码围栏检查通过，`git diff --check`通过；AGENTS为15行，三个Skill各仅修改读取段落，README仅修改文档地图。两份审计、四份目标及业务文件共74个文件hash无变化；任职Journey、产品中的任职/协作/反馈/案例说明和Architecture非本期对象行均保留。未新增业务实现或测试。
- 剩余文档边界：本次范围内未发现未消解的Opportunity目标冲突。未修改的模块README、旧execution记录及两份审计仍保留历史说法；其适用性由authority限定，不覆盖当前目标。Domain §5与UI §6的投递版本读取口径、Offer原件与通用Raw更正边界已在authority说明，目标原文未改。

以下保留2026-09-16交付记录供现状追溯，**不能解释为新Opportunity目标已实现**。其中旧“独立JobPosting待后续”不再是本期目标；`Employment→Stage→Project→…→Wiki`是原交付概括，AS-IS已确认不存在完整连续引用/自动回流链。当前范围按[authority](../00-authority.md)和[Roadmap](../07-roadmap.md)，具体已验证能力按[AS-IS](../audit/AS-IS-system-map.md)。


## 当前交付

[Career 结构优化与产品化重构](STRUCTURE-REFACTOR.md) B1—B5 已交付。当前应用以 Opportunity 与 Employment 为两条任务主干：

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
