# Career 前端

TypeScript + Vite vanilla，使用本地系统字体。页面只调用 `/api` Service，不直接读写数据库或任意文件，不将正文放进 localStorage。

```sh
npm ci
npm run typecheck
npm run build
```

T12 的隔离质量入口是项目根目录的 `python scripts/review_checks.py`；它只使用当前 worktree、测试数据和本地依赖。浏览器回归使用 `python scripts/browser_regression.py`，默认创建临时 `TestProvider` 服务并读取 `tests/fixtures/t12_browser_fixture.json`，不会自动连接生产端口；也可以显式传入 loopback 的隔离服务 `--base-url`。失败时仅保留不含业务正文的截图和短日志。

当前正式 frontend dist 已从最终通过 review 的 Batch F worktree 构建，并随 `0.7.0-batch-f` / schema v6 部署在 `/Users/frog/Projects/Career`。生产部署、数据迁移与浏览器 smoke 证据见 [Batch F §23](../docs/execution/OPPORTUNITY-BATCH-F.md#23-opportunity-mvp-production-cutover2026-09-18)。不要直接打开 index.html；Vite dev 模式不包含后端代理，本地运行以构建后的同源服务为准。

## 界面结构

`src/workspace.ts` 负责视图、模块分区和 UI 选择状态；`src/main.ts` 负责 API、revision 冲突、编辑缓冲与反馈弹窗；`src/style.css` 定义固定视口与面板滚动。侧栏收起只修改 DOM 布局，不重建表单。岗位和工作卡按 scope/id 过滤，历史记录跳转带回类型与记录 ID。窄详情区将记录列表改为选择器，正文保留独立滚动区。

主导航的顺序保存在浏览器 `localStorage`；桌面右键或纯键盘菜单可“置顶/取消置顶”，置顶项移动到第一位并成为下一次启动首页，同时显示简易 home 标识。取消置顶不恢复旧排序，当前第一项就是 fallback 首页；桌面拖拽和移动端长按拖动仍可调整顺序，将未置顶项拖到第一位会自动置顶。坏 JSON、未知/重复模块或不可用存储均回退到四个有效模块的默认顺序；显式模块深链接不会被首页规则劫持。

账户区由同一 shell 渲染：姓名字元不收缩，15px 字号、4px 间隔，头像和姓名共用居中网格。方形头像周围的本地 SVG 流光使用纹理位移、遮罩及 CSS 动画；遮罩避开头像主体，装饰不参与点击或辅助阅读，减少动态效果偏好下停止动画。没有运行时外部素材请求。

本批新增 `src/knowledge-ui.ts`，负责 Wiki 选材/来源/候选/修订和公司组织、机会关联、简历用途界面。验收见 [Wiki 与业务对象整合](../docs/execution/WIKI-DOMAIN.md)。本批后续鼠标整改见下文。

## 保留的 Batch B 管线与兼容边界

`src/opportunity-ui.ts` 承载六 View 管线与基础 Workspace；`main.ts` 处理路由/Service。状态直接读取后端 canonical DTO；前端只控制筛选和弹窗，不组合业务 phase/result。

创建公司/岗位/JD → Workspace → 编辑信息 → 明确结束。返回保留 View，旧 `#jobs/<id>?tab=...` 与 `#progress` 进入同一个 Workspace；不存在的 ID 明确报不存在。历史 Unknown 不进入阶段或已结束筛选。编辑冲突保留输入，显示服务器最新内容，用户核对后明确重试。Batch C–F 已分别接入投递、沟通、面试和 Offer 的真实 Domain Action，前端不自行组合阶段或结果。

C已将`editor-main`改为显式只读来源；工作稿按document_id进入统一编辑器，见下文。历史投递从冻结 snapshot/PDF 读取，不拼接当前稿。旧新投递/投递状态/机会 interview/offer 新建继续暂停，C的新投递只能通过RecordSubmitted；案例整包装载/删除按钮禁用，已存原件可回看。当前 Production 使用相同 schema v6 写入口与兼容门禁。

其他 Wiki、基础资料、任职/Project、反馈使用原模块。真实 AI 未接。自动测试和实际浏览器验收见[Batch B](../docs/execution/OPPORTUNITY-BATCH-B.md)，下面的历史接入记录不能解释为隔离 v2 已开放新的完整求职链路。

## 既有简历工作台本地化

正式入口是主站内的 `#resume?document_id=...`。`src/resume-workspace.ts`提供文档选择和工作台上下文，并在同页挂载唯一的`editor/legacy-app.js`编辑模块；`editor.html`与`editor/legacy-entry.ts`只保留薄兼容跳转，不再创建独立编辑状态。当前简历、状态、机会关系和简历级动作收敛为一层控制区，动作按编辑/AI/版本/PDF/投递分组，低频导出与选材收入“更多”。编辑画布使用`resume-canvas`而不是应用壳层的`.workspace`类；A4固定为`210mm × 297mm`且不收缩，宽桌面居中，窄桌面允许画布及工具区分别滚动。源码来自 app_17dspw78s10 发布分支 main 的 `cc4f247a6556bb7369e5a24cbf2539e0fd3679a8`；继续保留原纸面编辑、分区条目排序、富文本快捷键和撤销重做。字体及许可证随源码保留在 public/assets/fonts。没有复制线上简历样例、平台 SDK 或 .env。

纸面内容直接编辑；选中分区/条目显示原版操作按钮。草稿自动保存且可手动重试，冲突比较两份内容后人工选择。正式版本保存同时生成实际 PDF，历史可下载/恢复；恢复前当前稿进入独立恢复点。命名使用页面内对话框，兼容不支持 prompt 的内置浏览器。JSON/MD 可导出，JSON 导入尚未提供。

PDF 由服务端从结构化简历生成受控 HTML，并使用锁定版本的本地 Chromium/Playwright 打印为 A4 文字 PDF；中文字体内嵌，支持分页和普通文本提取。缺少渲染器时明确失败，不回退为图片 PDF。渲染时锁定编辑并冻结文档，失败可使用原请求重试。界面正文不存 localStorage；未保存时关页有提示。API与验收范围见 `docs/execution/RESUME-WORKBENCH.md`。

## 历史 v1 冷启动整改（v2 新投递暂停）

机会 → 简历 → 关联已保存版本 → 记录投递，填写实际时间、渠道和状态。机会页回看新旧投递及冻结正文/JD/PDF；旧文字稿入口保留。渲染从 `resume_snapshot` 读取，不从当前工作稿拼接。`main.ts` 复用同一登记与状态界面，`knowledge-ui.ts` 只在机会用途提供投递动作；后端再验证用途匹配。

`editor/legacy.css` 统一修复四类章节新增工具的鼠标命中：常显、在标题后按flex正常排列；条目工具保留选中并支持hover/focus，小屏章节直接显示新增。回调、单click、焦点、撤销恢复与PDF实现未改。真实验收和已知限制见 [冷启动整改](../docs/execution/COLD-START-REPAIR.md)。


## 事实闭环页面

`profile-ui.ts` 管理基础字段表单、旧文本整理与CAS；`record-ui.ts` 为机会、工作卡及聚合记录复用更正/历史/选段候选操作。`legacy-app.js` 提供明确选材和来源提示，保存工作稿成功后再发选材CAS；不确定响应复用同一请求。撤销/重做保留服务端来源历史，恢复正式版本采用冻结来源。

机会进入简历工作台的URL携带document_id，由服务端确认所属opportunity_id，返回来源Opportunity Workspace；来源可深链当前Wiki条目或基础资料。普通面试/足迹空状态只指向创建所属的机会或工作卡。分析预览先展示可读正文，允许返回调整，完整JSON收在技术详情中。T14 的 Work 页面显示 Achievement、关联 Evidence 查看入口和“整理为求职复用”弹窗；用户编辑并明确批准后，批准的 personal `wiki_entry` 才会出现在当前 Resume 的 Wiki 选材中。撤销只影响未来选材，已冻结/已投递快照不变。验收详见 [事实闭环](../docs/execution/FACT-LOOP.md)。



基础资料包括微信、GitHub和可增删的个人网页；表单输入只在当前DOM，切页不保留未提交内容，重新进入读取服务端已保存资料，后台CAS不展示为正常页面版本徽标。保存基础资料不会同步任何简历；在目标工作稿明确选入基础资料才更新姓名和联系方式区；第一行显示身份联系方式，第二行显示GitHub及其他个人网页。简历GitHub从用户提供的PNG徽标中只显示猫图形，并与电话、邮箱、微信图标保持14px视觉尺寸；未填写微信时提供带微信图标的补填入口。


## Batch C Resume Workspace

一级导航仅 Wiki、机会、项目、任职；简历保留为机会内的编辑器，列出当前ResumeDocument与最近编辑时间；用户明确选择后，在当前`#resume?document_id=...`页面直接进入完整纸面编辑状态。机会中的“编辑简历”使用相同Workspace入口，后端由did核对owner，返回链接回所属Opportunity。无owner不自动选首稿；旧job_id链接先回对应机会，`editor.html`兼容链接薄跳转回Workspace，legacy=1仅供只读查看。

沿用现有legacy-app纸面编辑、排版和PDF；autosave仅更新工作稿，导出不生成普通版本。普通版本由“保存版本”产生，RecordSubmitted产生带🔒、机会与日期的投递版本；版本管理只在工作台，机会材料面板展示已冻结实际投递。Profile刷新必须显式选入当前稿。请求固定幂等key；冲突保留输入并显示服务器值，响应未知时原请求重试。

UI验收使用明确临时数据路径/独立端口/TestProvider，不连接真实AI；命令`npm --prefix frontend run build`含tsc。范围、浏览器证据和未验项统一见[Batch C](../docs/execution/OPPORTUNITY-BATCH-C.md)。进一步视觉优化在Roadmap的Resume Workspace Productization，不为不同机会创建独立编辑器实现。

## Batch D Communication 与 Timeline

Opportunity Workspace 在已投递且未结束时显示“添加线上沟通 / 记录电话沟通 / 添加其他沟通”。表单明确选择日期、保留未提交输入，并以服务端 revision 处理并发冲突；结束后的机会隐藏新建入口，但已有 Communication 仍可查看和更正。界面“删除”调用后端归档动作，成功后该项同时从 Communication 列表与 Timeline 消失。

Timeline 只显示后端投影，不在浏览器维护或回写独立事件。Submission 跳转冻结材料，Communication 跳转同一对象详情；未知日期单独显示。旧 typed Communication 保留 ID 和原文关系，未知类型显示“类型待核对”，不会按 channel 猜测；legacy JourneyNote 仍在历史区域读取。前端不组合 phase/result，Communication 任一动作都不会改变机会阶段或结果。验收范围见[Batch D](../docs/execution/OPPORTUNITY-BATCH-D.md)。

## Batch E Interview Workspace

`src/interview-ui.ts` 在同一个 Opportunity Workspace 内提供真实轮次和模拟详情。日常界面聚焦当前/下一轮，之前的轮次收在历史列表。已投递阶段只有“确认真实面试”能进入 interview；沟通详情可以带稳定来源 ID 打开同一确认动作。多轮、排期/改期、待重约、完成和永久取消均调用 scoped Domain Action，前端不组合 Opportunity 生命周期。

真实面试显示柔性的面试准备、模拟创建、面试记录与固定五块面试复盘；模拟只显示状态和复盘，不提供真实面试记录或岗位情报更新能力。创建模拟时可 0/1/N 多选历史复盘，原始资料包不在页面铺开，仅供用户明确复制到外部工具。当前产品未配置真实模型，用户直接编辑并保存复盘；后端分离的复盘建议与岗位情报建议契约继续由领域测试覆盖。已有岗位情报更新建议必须显式采用或忽略。

Timeline 的 Interview 条目打开同一详情；legacy typed Interview 显示 Unknown，并仅通过要求完整显式事实的 upgrade 表单保留同 ID 升级。浏览器验收只使用 TestProvider、临时 schema v5 和非生产端口；验收后关闭 Agent 创建的唯一 tab 并停止临时服务。完整范围见[Batch E](../docs/execution/OPPORTUNITY-BATCH-E.md)。

## Batch F Offer Workspace

`src/offer-ui.ts` 继续嵌在唯一 Opportunity Workspace。submitted/interview 页面只有用户明确点击“记录现实 Offer”才进入 Offer 阶段；表单把 Opportunity 岗位只显示为上下文，`offered_role_title`、location 与其它 terms 默认为空且不会自动带入。当前条件原位编辑，revision 冲突保留表单输入；不显示版本历史、评分、Offer Comparison 或 AI 假结果。

Offer 阶段通过同一个 Communication 表单记录 `purpose=negotiation`，沟通内容不会改写 terms。接受动作明确说明不会创建任职；招聘方结束和主动退出继续调用唯一 Opportunity result 动作。ended Workspace 保留 Offer、两次谈薪、Submission、Interview 与 Timeline 投影，并隐藏 Offer 编辑和新增谈薪入口。

legacy typed Offer 显示“历史 Offer · 待核对”，旧 status/terms/日期不自动接管；用户完整核对后才同 ID 升级。Opportunity 深链接切换会按目标 ID 重新载入 Offer、Interview、Communication 和 Timeline，并以加载 token 丢弃过期响应，防止跨 Opportunity 显示旧 scoped 数据。浏览器验收只使用一个 Agent tab；结束后关闭 tab 并停止临时服务。完整范围与证据见[Batch F](../docs/execution/OPPORTUNITY-BATCH-F.md)。

## Opportunity MVP 产品入口

主导航固定为 Wiki、机会、项目、任职。已有简历从所属机会的稳定入口打开，各阶段与结束状态均保留；无稿只沿用现有合法创建规则，不自动创建。旧 Job/JourneyPlan、独立面试页和足迹页不再作为主流程入口，但旧深链接及历史资料仍可兼容读取。机会详情按“当前动作 → 岗位情报 → 投递材料 → Timeline”组织；阶段和结果只能由后端 Domain Action 改变，Timeline 只读取投影。

简历工作台进入时不会自动选择第一份文档。用户从目录明确选择，或从具体机会进入同一编辑器；编辑器用 `document_id` 核对所属机会并按来源返回。用户界面使用求职语言，schema、revision、RawSource、PatchProposal 等内部概念不作为日常操作入口。


## Resume 导航收口

`src/resume-navigation.ts` 统一机会与编辑器链接和已有稿/合法创建/不可创建分流。打开时读取当前机会的 Resume API；编辑器显示所属机会并返回同一机会简历区域。旧 `#resume`、`editor.html` 和 `job_id` 链接保留兼容；导航偏好剔除旧 Resume 一级项并保留其余项的相对顺序。验证：`npm --prefix frontend run test:resume-navigation`、`test:navigation`，以及 `tests/test_resume_workspace_single_page.py`、`tests/test_t15_navigation.py`。

### UX-4 机会回读与面试衔接

`src/opportunity-scope.ts` 按当前机会读取工作稿、冻结投递、沟通、面试、Offer 与研究；`interview-ui.ts` 从机会级研究建议中筛选当前轮次。阶段变化后保留沟通和面试历史，已结束仍只允许既有资料更正。验证使用 `npm run test:ux4-opportunity`、`npm run test:ux4-interview`，实际浏览器证据使用隔离虚构库。
