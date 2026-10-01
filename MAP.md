# Career 项目地图

- `src/workbench/app.py`：FastAPI 组合根，装配各业务路由与静态前端；`src/workbench/core.py`：SQLite Store、记录与 revision 基础设施。
- `src/workbench/`：Career 领域与用户任务接口；`src/workbench/wiki/`：Raw、Wiki、来源引用与语义流程。Feishu 只读入口在 `src/workbench/feishu_read.py`，经固定 allowlist 调用本机 `lark-cli`；用户确认导入后保存为带 Feishu provenance 的 Raw，没有 Feishu 写 Gateway。
- `frontend/src/`：Vite/TypeScript 单页应用。`wiki-semantic-bindings.ts` 接入“添加资料”流程，`feishu-source-ui.ts` 负责飞书结果/预览转义、不含正文的导入请求及受限本地 TXT/Markdown 解析，`ai-config-ui.ts` 显示连接状态。
- `tests/` 与 `frontend/tests/`：Python API/领域回归及前端契约测试。模块接口和测试命令分别见 `src/workbench/README.md`、`src/workbench/wiki/README.md`、`frontend/README.md`。
- 权威入口：`docs/00-authority.md`；产品边界、资料合同、架构、旅程、验收与阶段状态分别见 `docs/01-product.md`、`docs/02-context-contract.md`、`docs/03-architecture.md`、`docs/04-journeys.md`、`docs/05-acceptance.md`、`docs/07-roadmap.md` 与 `docs/execution/STATUS.md`。
