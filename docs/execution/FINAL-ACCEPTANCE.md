# Final Acceptance

日期：2026-09-20

工作范围：仅使用隔离 Worktree `/Users/frog/Projects/Career-worktrees/review-t00-t01-20260919`、临时目录、虚构数据和假供应商。未合并主 Career，未删除 Worktree，未操作生产数据库、正式周备份、真实 Keychain、真实收费 Provider、部署或 Git push。

结论：`MERGE_READY: NO`。当前结果为 `ISOLATED_READY + PRODUCTION_AUTHORIZATION_REQUIRED`；`ACCEPTED` 留待最终用户验收。

## PASS

### 代码与隔离候选环境

- 使用 `/tmp/career-final-acceptance-seeded` 的 Python 3.12.14 候选环境安装锁定依赖；`pip check` exit `0`。
- 独立候选 App 使用独立端口和独立 runtime/data 目录。冷启动、第二次打开、已运行时复用、未知占用端口拒绝、process identity 校验和候选服务正常停止均有隔离证据；正式 8765 服务 PID `79422` 全程未被终止。
- `scripts/install_macos_app.py` 已支持把候选端口写入 launcher，`scripts/macos_app.py` 在无法核实服务身份时拒绝复用占用端口。

### 隔离 Chrome 与用户链片段

- 候选 App 完成首次假配对、刷新后会话保持、退出、重新生成假配对码并重新配对。
- 四个一级导航均可访问；候选机会列表和机会详情可加载。
- 机会详情此前因合法 `null` offer 响应被前端错误拒绝；修复后真实隔离 Chrome 详情页不再显示“服务器返回格式不正确”。
- T01 未保存表单的真实隔离 Chrome 操作已看到放弃输入确认提示；完整 Esc/遮罩/路由/beforeunload 选择链仍列为未验项。

### PDF 与备份

- 虚构中文简历 PDF 用 `pypdf` 提取到姓名、公司、岗位、日期、项目和联系方式等文字；实际摘录为 `林晓岚·验收版A`、`验收虚构星河科技`、`2024年1月―2025年6月`、`候选 App 验收`。部分中文 CID 字形在提取文本中显示为相近 Unicode 字符，因此精确复制文字仍需人工验收。
- Chrome 实际打开 PDF，中文和分页可见；鼠标选择并复制文字的人工证据未取得。
- 隔离数据实际运行 `scripts/weekly_backup.py`：`status=complete`；`verify_backup` 为 `healthy=True`；恢复到全新目录为 `complete`，业务记录源/恢复目录均为 `1`；`.career-weekly-status.json` 写入成功时间；受控备份目录文件失败返回 exit `1`，未覆盖原数据。

### AI、规模和质量门禁

- `tests/test_ai_operations.py` 的 `CountingFakeProvider` 每次调用递增并返回不同内容；专项 `11 passed`。测试直接断言：串行 5 次 `call_count == 1`、并发 5 次且首调用阻塞时 `call_count == 1`、同 key 不同输入拒绝、重启后成功结果 `call_count == 1`、`outcome_unknown` 重试仍 `call_count == 1`。
- 隔离 UI Research 无来源时没有产生 Provider 调用，测试供应商 `call_count=0`；因此没有把该次浏览器操作误报为真实远端重复调用验收。UI 每次主动操作生成新 key 的后续 UX 风险仍保留。
- 虚构 1000 条机会的实际 API 记录：`limit=50` 返回 50 条、32,135 bytes、12.86 ms；`limit=100` 返回 100 条、63,885 bytes、11.02 ms；summary 返回 1,000 条、1,094,381 bytes、47.10 ms；分页两页各 100 条且无重叠。未据此推导完整浏览器性能结论。
- `scripts/review_checks.py` exit `0`，内含 full pytest、frontend typecheck/build、pip check、npm ls、secret scan、Markdown link check 和 diff check。

## FAIL

- `pip-audit` exit `1`：`starlette==0.46.2` 仍有 14 条数据库记录，归一为 7 个唯一 advisory：`PYSEC-2026-1941`、`PYSEC-2026-1942`、`PYSEC-2026-161`、`PYSEC-2026-2281`、`PYSEC-2026-2280`、`PYSEC-2026-249`、`PYSEC-2026-248`。没有使用 `--ignore-vuln`。当前 FastAPI 版本约束使安全升级需要一并评估运行栈，不能在最终验收中盲升。

## BLOCKED / 未授权 / 未验

- 正式 `/Users/frog/Projects/Career/.venv` 和 `/usr/bin/python3` 均为 Python `3.9.6`，而当前代码要求 Python `3.10+`。已建立并验证 Python 3.12.14 候选环境，但没有原地改动正式 `.venv`；平台迁移与正式切换是发布阻断项。
- 正式 8765 当前仍由旧 Career 进程 PID `79422` 监听；未对它执行停止、替换或旧 build 清理。真实正式 Career.app 冷启动、连续双击、旧 build、可信停止/PID、端口占用和错误不误杀仍需用户授权后的平台验收。
- 真实 Chrome 的完整“机会 → 面试 → 简历”用户链、所有 T01 未保存输入分支、真实网页完整验收尚未完成；候选 App 的配对、刷新、退出/重配对、四个一级导航和机会详情仅构成部分证据。
- PDF 在 Chrome/Preview 中鼠标选择并复制姓名、经历、日期的人工验收未完成；`pypdf` 文本提取不是该人工验收的替代品。
- 正式周任务、正式 Career 数据的备份/恢复未执行；已完成的 weekly script、manifest/SQLite/hash、全新隔离恢复和受控文件系统失败均只针对隔离虚构数据。
- T11 的 100/1000 数据集浏览器首屏、分页和页面切换交互退化尚未实际记录；已有 API 请求规模数据不能替代真实浏览器证据。
- 真实 Keychain 未执行。需要用户明确授权后，才可用专用假测试 secret 做写入、读取、替换、删除和拒绝/锁定失败验收；本轮没有读取、覆盖或删除现有真实 Career API Key。
- 真实 Provider 未执行。需要单独授权；最小 smoke test 应只发送虚构 JD/简历，预计 1 次受控调用，且应先确认目标 Provider、费用和回滚边界。本轮没有收费调用。
- 独立 Subagent 的实际 `Luna / High` 配置无法从宿主元数据核实，本轮由主线程串行实施并完成只读规格/安全检查，不计独立审查证据。

## 本轮为验收 Bug 做的最小修复

- `frontend/src/opportunity-ui.ts`、`frontend/src/main.ts`：统一弹窗关闭、遮罩点击和 Esc 路径使用未保存输入保护；首次真实候选 Chrome 验收发现长文本关闭会静默丢失，修复后会出现确认提示。
- `frontend/src/contracts.ts`：允许合同中已声明的 JSON `null` envelope，避免无 Offer 的合法机会详情被错误显示为“服务器返回格式不正确”。
- `scripts/macos_app.py`、`scripts/install_macos_app.py`、`tests/test_macos_app.py`：候选 App 支持隔离端口，并在端口已有未核实服务时于启动前拒绝复用；增加对应回归测试。未终止正式或未知进程。

## 修改文件

- `frontend/src/contracts.ts`
- `frontend/src/main.ts`
- `frontend/src/opportunity-ui.ts`
- `scripts/install_macos_app.py`
- `scripts/macos_app.py`
- `tests/test_macos_app.py`
- `docs/execution/STATUS.md`
- `docs/execution/FINAL-ACCEPTANCE.md`

## 最终验证命令与结果

以下均在隔离 Worktree 执行；命令中的 Python 为临时 Python 3.12.14 候选环境或 `uv` 隔离环境。

| 命令 | exit | short summary |
|---|---:|---|
| `pytest -q tests/test_t12_quality.py tests/test_macos_app.py` | 0 | `10 passed` |
| `pytest -q tests/test_ai_operations.py` | 0 | `11 passed`；CountingFakeProvider 调用次数断言通过 |
| `pytest -q` | 0 | `275 passed in 108.90s` |
| `npm --prefix frontend run typecheck` | 0 | TypeScript check passed |
| `npm --prefix frontend run build` | 0 | Vite production build passed |
| `python -m pip check` | 0 | No broken requirements |
| `npm --prefix frontend ls --depth=0` | 0 | 依赖树可解析；仅已有 extraneous 本地条目 |
| `python scripts/secret_scan.py` | 0 | 未发现配置规则命中的 secret-like 内容 |
| `python scripts/review_checks.py` | 0 | 内含 `275 passed`、typecheck/build、pip check、npm ls、secret scan、links、diff check |
| `git diff --check` | 0 | no whitespace errors |
| `pip-audit -r requirements.lock --format columns` | 1 | 1 个包、14 条记录、7 个唯一 Starlette advisory，保留风险记录 |

## 最终状态

- `MERGE_READY: NO`
- `FINAL_ACCEPTANCE: BLOCKED / PRODUCTION_AUTHORIZATION_REQUIRED`
- `ACCEPTED: NO`
- 仅剩阻止 Merge Ready 的项目：Python 3.10+ 正式平台迁移和正式 App/旧 build/PID/端口验收；真实 Chrome 完整用户链及 PDF 选择复制；正式周任务和正式数据隔离备份恢复；T11 浏览器规模验收；Starlette 7 个唯一 advisory 的兼容升级决策；真实 Keychain 与真实 Provider 的明确授权及验收。
