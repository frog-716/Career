# 既有简历工作台本地接入

状态：本批独立工作台主链技术验收通过，待用户体验反馈。产品目标仅见 01-product.md；本批交付可独立打开的原工作台，保持纸面编辑，接入本地草稿、不可变版本与 PDF。全流程 AI 适配另在结构化契约完成后接入，不将旧纯文本提案直接覆盖结构化稿。

来源：用户已有妙搭应用 app_17dspw78s10 的发布分支 main，commit `cc4f247a6556bb7369e5a24cbf2539e0fd3679a8`。真实入口为 client/index.html → legacy-entry.ts → legacy-app.js；不是同仓库未使用的 React ResumeEditorPage。取用 HTML、legacy JS/CSS 和本地字体，排除 .env、用户 resume-data.json 和平台 SDK。

## 本批 Interface

- 独立页面 `/editor.html`，只使用本地同源 `/api/editor`；不连接妙搭数据库，不自动迁移线上个人资料。初始空白结构。
- `GET /api/editor` → `{document,revision,savedAt}`，初始 revision 0，不在 GET 隐式写入。
- `PUT /api/editor {document,expected_revision}` → 同结构；保存串行，revision 不符 409。失败保留页面输入，明确提示，不能自动覆盖服务器。JSON 最大 1MB，schemaVersion=1，保留 profile/sections/formatting/meta 与条目 ID。
- `GET /api/editor/versions` → `{versions:[{id,name,createdAt,artifact_id}]}`。
- `POST /api/editor/versions {name,document,expected_revision,pdf_base64,idempotency_key}` → `{id,name,createdAt,document,artifact_id}`。document 必须与已保存 revision 对应内容一致；PDF 上限 5MB；源结构和实际 PDF 同批登记，重复 key 返回同版本，修改参数重复 key 拒绝。
- `GET /api/editor/versions/{id}` → 完整版本；PDF 走已有 `/api/artifacts/{artifact_id}?download=true`。
- `POST /api/editor/restore {version_id,expected_revision}` → 当前稿；恢复产生新 revision 和独立 RecoveryPoint，不新建正式版本。历史 PDF 不变。初批不提供不可逆删除入口。
- 新工作稿/版本使用独立 kind（editor_draft/editor_version/editor_recovery），附件使用现有 artifact kind 以纳入备份。默认 Context 不读取它们。既有纯文本数据不原地改型。
- 本批沿用既有 html2canvas/jsPDF 图片式 PDF，界面和说明准确提示不可选中文本；不以此验收未来可检索文本 PDF 要求。不重新改成纯文本排版。

## 实现范围及验收

- 前端范围：frontend/editor.html、frontend/src/editor/、frontend/public/assets/fonts/、frontend/vite.config.ts、frontend/package*.json、frontend/README.md。复用原编辑代码，替换平台保存与同步，保留原纸面、格式、增删/排序、撤销/重做。去除真实样例与 localStorage 正文，失败显式保留内存输入。只读 WebMCP 保留，整版写入必须等待实际保存并诚实返回。
- 后端范围：src/workbench/editor.py、tests/test_editor.py。导出 `editor_router(store)` APIRouter，使用现有 Store/事务和错误类型；PDF 原子写入，所有源数据放现有代码外目录。先验证冲突、版本冻结、幂等、恢复、备份和 Context 隔离。
- 集成与验收范围：app.py 路由接入、main.ts 独立入口、必要集成修正、文档、构建、真实浏览器编辑/重载/版本/PDF验证。不修改线上应用。

完成证据：源码入口与复用范围、实际测试命令、隔离虚构浏览器路径、实际 PDF 与不可变哈希、限制及独立审查。不得仅凭构建宣布工作台合格。

## 实际结果与证据（2026-09-14）

原编辑/渲染函数和纸面 CSS 直接复用。新增同源本地保存、保存状态、页面内命名对话框、可读冲突对比、版本失败重试、独立入口与文字反馈；去除云端 SDK、localStorage 正文、无效 sendBeacon 与会虚报 saved=true 的 WebMCP 整版写入。只读文档工具保留并标明可能包含未保存修改。CSS 只追加本地控件样式和 PDF 空字段占位符隐藏。

- 实际执行 `PYTHONPATH=src .venv/bin/pytest tests -q`：27 passed。覆盖结构往返、非法形状/重复分区拒绝、revision 冲突、版本幂等并发、恢复前稿、备份恢复、Context 隔离和现有回归。单元测试 PDF 使用协议 fixture，仅验证存储；实际 PDF 证据见下项。
- `npm --prefix frontend run build` 与 typecheck 通过；`node --check frontend/src/editor/legacy-app.js`、`git diff --check` 通过。Vite 对 PDF 依赖包产生 chunk >500kB 提示，不影响构建。
- 浏览器隔离地址 `http://127.0.0.1:8766/editor.html`，数据 `/tmp/career-resume-editor-check`。从空白编辑姓名、增加技能行、保存及重载回读；双窗口以旧 revision 保存被拒绝，对比保留两边，人工选择“保存当前输入”后落盘。
- 原版加粗快捷键真实生成 `<b>` 内容并保存，撤销/重做可操作。记录文字反馈后对话框关闭、当前工作稿保留。
- 浏览器真实生成版本 v1，修改姓名后恢复 v1；数据库 RecoveryPoint.before 为恢复前新姓名，正式版本数仍为 1，原 PDF 哈希不变。
- PDF 已实际经 html2canvas/jsPDF 生成；Poppler `pdfinfo` 验证一页 A4，`pdftoppm` 渲染查看中文与版式。空联系方式占位符未渲染到最终 PDF；第二次“导出 PDF”实际执行归档并触发下载，文件 `artifacts/4405f0bc-d3c8-4518-a44a-2d571ccdbad6.pdf`，87,656 bytes。两次文件都位于上述隔离数据目录。
- 规范轴审查发现请求 header 缺失、冲突 HTML 注入、假保存回执、PDF 期间编辑、失败新 key 和原生 prompt 不兼容，均在本轮修复。独立复查当前代码未发现新增确定阻塞。规格轴核对实际发布入口和纸面基线，未以另一套 React 页面替换。
- 正式服务已备份后重启，`http://127.0.0.1:8765/editor.html` 浏览器实际打开为空白稿，没有迁入线上数据或虚构验收资料。正式备份位于 `~/Library/Application Support/CareerOS-backups/career-backup-4233af91-132f-4da2-b65b-900a177cefbd`。

## 尚未接入

当前为独立单工作稿；线上简历/历史版本迁入、结构化文件导入、岗位多稿与版本回传、AI 逐段提案尚未实现。MD/JSON 导出与历史恢复可用，JSON 导入无入口。原版图片 PDF 不支持文本检索；可选中文本 PDF 尚未验收。恢复前稿已保存于独立 RecoveryPoint，暂未提供其单独恢复界面。此批通过不代表整套 Career OS 或真实 AI 闭环完成。
