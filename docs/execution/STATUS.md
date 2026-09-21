# 当前状态

最后整理：2026-09-21（T01–T13 开发冻结；Stage 3 已按绑定身份完成 `LOCAL_ONLY` 正式本机切换，未进入 Stage 4）。本文顶部只维护当前源码/运行身份、阶段状态、阻断项、下一动作和证据位置；历史批次的过程和证据留在下方既有章节及各自文档。

## 当前生产切换阶段

- 唯一切换账本：[PRODUCTION-CUTOVER](PRODUCTION-CUTOVER.md)。本轮已完成阶段 0、1、1.5、2、2.5、3，状态为 `CUTOVER_GATE=STAGE_3_LOCAL_ONLY_DEPLOYED_VERIFIED`、`RELEASE_GATE=PASS_LOCAL_ONLY`；未执行 Stage 4。
- Stage 3 执行门已通过；[RELEASE-GATE](RELEASE-GATE.md) 保留的是执行前重分类历史。`AI_ENABLED`、真实 Keychain/Provider 和收费调用没有包含在本次发布授权内。
- 真实 Provider 未调用，真实 Keychain 未读取、修改或删除；本次通过仅适用于 `LOCAL_ONLY`。
- 当前计划身份：`plan_id=career-cutover-20260920-stage25-resume-template-e2dcd25c`，`plan_hash=a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`，`release_id=career-0.7.0-batch-f-stage25-resume-template-20260920`。
- 当前冻结身份：`HEAD=82af33dfe4d572e6ab04f36f3757b13a28049037`，`source_fingerprint=e2dcd25c1479f895f4c540ea19812a08e7bdacdde2d91747d367f5fdeb440d0d`，`static_fingerprint=2daf9f5aaddf62d94cd3d555555d0f734057b42a6a9132ccde927fd921568ede`，backend/frontend build=`career-0.7.0-batch-f`。Stage 2.5 修改了服务端 PDF 模板映射，上一版阶段 2 / Stage 3 身份自动作废；新身份按冻结发布文件列表重算，`source_fingerprint` 变化，`static_fingerprint` 未变化。
- 旧正式 PID `79422` 已在完整身份核验后优雅停止；原正式数据、旧 App、旧 Python 环境和旧 runtime 均保留。当前正式 PID=`39300`、Python=`3.12.14`、build=`career-0.7.0-batch-f`、data instance=`42ff565e28a08e31414442521540ac3e`、端口=`127.0.0.1:8765`、模式=`LOCAL_ONLY`。LaunchAgent plist 和正式周任务未修改或触发。

## 当前源码/运行身份

- 隔离 worktree：`/Users/frog/Projects/Career-worktrees/review-t00-t01-20260919`；正式目录 `/Users/frog/Projects/Career` 已按批准发布对象完成本机切换，未合并 Git、未 push。
- 当前基线：`HEAD=82af33dfe4d572e6ab04f36f3757b13a28049037`，T01–T11 的有效未提交修改与本批 T12 修改均保留在该隔离树；schema v6、前端构建入口和 requirements/package lock 以当前源码为准。
- 测试身份：自动测试继续使用虚构数据、`TestProvider` 和隔离临时目录；Stage 3 仅通过一致性备份读取正式源并在恢复副本上验收，未读取真实 Keychain、未调用收费模型。
- 最终交付身份：正式 Python 已切到固定 `3.12.14` 环境；source/static fingerprint 与授权值一致。Stage 3 没有源码修复、提交、Git 合并或 push。

## 当前阶段任务状态

- Final Acceptance / Stage 3：`PASS — DEPLOYED_VERIFIED (LOCAL_ONLY)`；`ACCEPTED` 留待用户确认。即时恢复点、显式 schema 准备、固定 Python/App/data/runtime、macOS/Chrome/PDF、LOCAL_ONLY 和回滚对象见 [PRODUCTION-CUTOVER](PRODUCTION-CUTOVER.md)。
- Stage 3 最新质量门禁：`scripts/review_checks.py` exit `0`，内含 `pytest -q` `282 passed`、frontend typecheck/build、pip check、npm ls、secret scan、Markdown links、git diff check；LOCAL_ONLY+Range/Host 专项 `7 passed`。最新 `pip-audit` exit `1`，仅 Starlette `14` 条记录、`7` 个唯一 advisory，未隐藏。
- Stage 3 未修改源码。切换中发现并显式处理恢复点缺少 T03 内部表的问题：只在恢复副本上 inventory → dry-run → apply → verify，原有业务 row hash、冻结材料和附件逐项不变。

- T12：`CODE_VERIFIED`；完成类型边界、状态文档、R01–R18 回归映射、浏览器回归入口、最小 CI、依赖/秘密/文档检查。浏览器入口本机因 Chromium 下载阻塞未取得运行证据，未标 `BROWSER_VERIFIED`；`ACCEPTED` 留待最终用户验收。
- T12.1：`CODE_VERIFIED`；5 个可安全升级的包已按最小修复版本更新，2 条实际 Starlette 边界已加应用层防护；`pip-audit` 仍保留 Starlette 的 14 条重复/别名记录，逐项分类与接受理由见下方 T12.1 章节，未伪造为通过。
- T13：开发已冻结；`tests/test_t13_release_readiness.py` 专项与阶段 0/1 隔离验收已通过或已明确列为未验，仍不等同 `ACCEPTED` 或 `DEPLOYED_VERIFIED`。
- Stage 1.5：`CODE_VERIFIED`；`CAREER_AI_MODE=LOCAL_ONLY` 在 SecretStore、Provider、ModelGateway、Research web search 与启动器边界 fail closed。生产样式 `ModelConfig`/`secret_ref`、假 API Key、注入 TestProvider、四条 AI 路径和网络 trap 专项通过；不等同阶段 2 或正式切换授权。
- Stage 2：`PASS`（Candidate-only rehearsal）+ `BLOCKED`（正式切换/Stage 3）；固定 Python 3.12.14、正式数据一致性备份、全新隔离恢复、schema v6/inventory/restore verify、Candidate App/8865、Chrome 只读链、PDF 文本层和 LOCAL_ONLY 证据已完成。正式源 DB hash 未改变，正式 PID `79422` 未停止。没有执行 migration apply、Keychain、真实 Provider 或正式切换。
- Stage 2 follow-up：`CODE_VERIFIED`；新增 `CAREER_TEST_MODE=1` + `CAREER_AI_MODE=LOCAL_ONLY` + `CAREER_ALLOW_UNPAIRED_FAKE_DATA=1` + 临时目录 `.career-fake-data` 标记的免配对模式。四重条件齐全时真实 `scripts/run.py` 的业务 API 无需配对；缺少显式开关仍返回 `401 pairing_required`。正式数据和恢复正式副本不满足临时目录约束，继续要求配对。
- Stage 2.5：`CODE_VERIFIED`；仅修改 `src/workbench/resume_pdf.py`，将结构化 Chromium PDF 的纸面布局映射回 T04 前 `legacy.css`/`legacy-app.js` 的既有模板：9mm 页边距、居中姓名与联系方式图标、深灰标题块+横线、三列经历/项目表头、圆点 bullet 和教育背景位置；真实文字层、中文字体、分页、冻结一致性与 hash/renderer 元数据保持。历史基准为 `docs/archive/reviews/2026-09-15-novice/2026-09-15-novice-assets/03-empty-editor.png`；同一虚构简历的旧编辑器截图与新版 PDF 已逐项对照。此前锁屏阻断已解除：Preview 选择/⌘C/TextEdit 粘贴实际通过，证据已写入 [RELEASE-GATE](RELEASE-GATE.md)。
- T01–T11：按用户确认保留既有状态；T11 为 `CODE_VERIFIED + BROWSER_VERIFIED`，`ACCEPTED` 留待最终用户验收。
- 证据：T12 专项为 `tests/test_t12_quality.py`；本地质量入口为 `scripts/review_checks.py`；浏览器入口为 `scripts/browser_regression.py`；R 映射为 [REGRESSION-MATRIX](REGRESSION-MATRIX.md)。

## 阻断项与最终验收保留项

- `LOCAL_ONLY` Stage 3 没有剩余硬阻断；正式 App、Python 3.12、恢复点、显式 schema 准备、回滚对象、Chrome/PDF 和 LOCAL_ONLY 边界均已取得真实证据。`ACCEPTED` 仍由用户确认。
- `AI_ENABLED` 继续阻断：真实 Keychain、真实 Provider、收费调用和真实网页 Research 未授权、未执行；不得把本次 `LOCAL_ONLY` 通过外推为 AI 发布通过。
- 供应链残余：`starlette==0.46.2` 的 7 个唯一 advisory 仍存在，`pip-audit` exit `1`。Range/Host 两项由直接前置拒绝测试覆盖，其余按 T12.1 分类；完整消除至少需要升级到允许 Starlette `1.3.1` 的 FastAPI `0.133.0+` 运行线，须作为独立栈升级验证，不在本次切换中盲升。
- 非阻断观察：LOCAL_ONLY 设置页仍按数据库配置显示“真实 AI”；旧 demo 机会曾显示 `Research owner 不合法`；退出后同进程不会重新生成一次性配对码，需要重启服务再配对；PDF 复制的加粗字段边界在 TextEdit 表现为 `**`。后端安全边界、真实机会读取和中文文字层均已独立通过。
- T11 规模数据仍只用于事实报告：1000 条虚构机会 summary `1,292,277` bytes/`0.074188s`，all opportunities `749,781` bytes/`0.022617s`；Chrome 显示总数和页面切换，未见分页按钮，不据此给出性能好坏结论。
- 正式周任务 plist 未改且未运行；它不是本次 Stage 3 的新增阻断。旧数据/App/Python/runtime、即时恢复点和失败候选副本均保留，任何清理或 Stage 4 行为需另行授权。

## 下一动作

- 等待用户对 `DEPLOYED_VERIFIED (LOCAL_ONLY)` 结果做最终确认。不得自动进入 Stage 4，不得合并、删除 Worktree、访问 Keychain、调用 Provider、push 或清理旧版本/恢复点。

## Stage 2 Candidate-only rehearsal：2026-09-20

- 正式源与恢复：正式 DB 备份前后 hash 均为 `6c7b6bbe1e04ed86ccc4862e86fd5bac3f2305535f38db3d844071cde3ee3721`；`cutover-rehearsal-20260920` manifest `complete/healthy/valid/recoverable`；恢复验证 exit `0`，snapshot hash=`7eb49d921c13c8931eab01d224ec4b1cb72d7a666f3e567a0560b27391e7d3cb`，counts applications=1/current=31/meta=1/records=51/artifacts=1；inventory exit `0`，无 migration gate，未 apply。
- Candidate：固定 Python `3.12.14` 环境、独立 App/data/runtime/log/`8865` 均已建立；冷启动、运行中双击、未知端口拒绝、正常停止和 `/healthz` 已实测；正式 PID `79422` 始终存活。
- Chrome/PDF/规模：真实 Chrome 完成配对、刷新会话、退出/重配对、Wiki/机会/面试/简历/任职入口和只读详情；恢复简历摘要 DTO 的最小合同修复后工作台正常。Preview 显示真实 PDF 文本层；1000 条虚构机会页面显示总数并完成页面切换，未见分页按钮，不作性能结论。
- 门禁：`pytest -q` exit `0` — `282 passed in 149.19s`（由最后一次 `review_checks.py` 内含全量运行记录）；`npm --prefix frontend run typecheck` exit `0`；`npm --prefix frontend run build` exit `0`；固定 Python `-m pip check` exit `0`；`npm --prefix frontend ls --depth=0` exit `0`（已有 extraneous 条目）；`python scripts/secret_scan.py` exit `0`；`python scripts/review_checks.py` exit `0`；`git diff --check` exit `0`。`pip-audit` 既有重查 exit `1`，Starlette `14` 条记录、`7` 个唯一 advisory，未隐藏。
- 安全边界：Candidate 进程实际环境包含 `CAREER_AI_MODE=LOCAL_ONLY`；未读取真实 Keychain、未调用真实 Provider、未发起 Research web outbound。Stage 2 不执行 Stage 3。
- 免配对回归：四重条件的虚构临时数据服务 `127.0.0.1:8866` `/api/state` exit `0`/HTTP `200`；同一标记数据缺少 `CAREER_ALLOW_UNPAIRED_FAKE_DATA` 的 `127.0.0.1:8867` `/api/state` exit `0`/HTTP `401`，均已优雅停止。

## T13：最终隔离验收与生产切换准备，2026-09-19

- 原问题复核：最终收口前没有一次可复跑的交付身份/交叉场景/生产门禁证据；`frontend/README.md` 与 `docs/03-architecture.md` 还保留 T04 以前的 `html2canvas/jsPDF` 图片 PDF 描述。T13 专项先按该事实建立红灯，随后修正文档并保留测试约束。
- 实现：新增 `tests/test_t13_release_readiness.py`，实际用临时 `Store`、`TestProvider` 和 `TestClient` 检查 backend/frontend `build_id` 与 schema v6 一致、隔离浏览器入口固定 loopback/临时目录/TestProvider、T12.1 两条危险输入前置拒绝与 7 个 Starlette advisory 记录不被隐藏、未宣称 `ACCEPTED`/`DEPLOYED_VERIFIED`。`scripts/browser_regression.py` 仅调整缺失 Chromium 时的确定性失败记录，不改变真实用户链或连接边界。更新两份过时工程文档。
- 最终身份（`STATUS.md` 不计入差异指纹，避免证据记录自引用）：`HEAD=82af33dfe4d572e6ab04f36f3757b13a28049037`；branch=`codex/review-t00-t01-20260919`；schema=`6`；backend/frontend build=`career-0.7.0-batch-f`；requirements 锁定 `fastapi==0.115.12`、`starlette==0.46.2`、`playwright==1.51.0`、`pypdf==6.16.1`、`pytest==9.0.3`、`anyio==4.14.2`、`click==8.3.3`、`Pillow==12.3.0`；排除 `STATUS.md` 后的有效源文件清单 SHA-256 指纹为 `ac5e29028e8e769c4db98f1665879d5fb0c22de123f3083729e74725f2af7e96`。
- T13 专项：直接 `tests/test_t13_release_readiness.py` exit `0`，`5 passed`；交叉专项 `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src CAREER_TEST_MODE=1 env -u CAREER_AI_PROVIDER -u CAREER_AI_API_KEY -u OPENAI_API_KEY -u CAREER_AI_MODEL -u CAREER_AI_BASE_URL uv run --no-project --with-requirements requirements.txt pytest -q tests/test_t13_release_readiness.py tests/test_t12_1_dependency_security.py tests/test_ai_operations.py tests/test_outbound_policy.py tests/test_resume_pdf.py tests/test_t07_research_evidence.py tests/test_t08_resume_suggestions.py tests/test_t09_local_session.py tests/test_t10_backup.py tests/test_t11_pages.py` exit `0`，`63 passed`。这覆盖 T03 幂等/未知结果、T04 PDF/冻结、T07/T08 AI 提案、T09 会话身份、T10 备份恢复/T11 页面分页及 T12.1 Range/Host 前置拒绝；所有远端调用均为假供应商/隔离目录。
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

## Career Review 稳定化：T09 本地会话与可信启动器，2026-09-19

- T09 开工复核：重新读取 T09 任务卡、`docs/00-authority.md`、Opportunity 工程/Context 合同、当前 `app.py`、`scripts/run.py`、`scripts/macos_app.py`、前端请求适配及 T01–T08 机制。当前代码只有 loopback Host/Origin/写请求头检查：`/api/state`、业务 API、artifact 无 Bearer 会话；启动器只按 PID 文件存活并可直接 `SIGTERM`，没有配对码、重启失效会话或 OS 单实例锁；问题仍存在，未重复建立 T03/T05/T06/T08 已有机制。
- T09 状态：`CODE_VERIFIED + BROWSER_VERIFIED`；`ACCEPTED` 尚未由用户确认。浏览器证据为隔离 IAB 用户链，不计为 Chrome 独立验收；真实 Mac/Chrome 平台项保留为 `PLATFORM_VERIFICATION_REQUIRED`。主线程完成规格轴/规范轴只读审查；无法核实 Subagent 实际 Luna/High，因此本批主线程串行实施，独立实施/独立审查缺失。
- T09 实现：新增 `src/workbench/local_session.py`，为每个运行实例生成 128-bit 一次性配对码（5 分钟、一次消费、owner-only 文件）、256-bit Bearer 会话（8 小时、仅进程内、重启失效）、受保护控制凭据、数据实例/启动实例身份和诊断信息。`src/workbench/app.py` 将匿名面收敛为静态无资料页面、最小 `/healthz`、`/api/pair`；业务 API、artifact、配置、state 和诊断均需会话，Origin/Host/写请求头仍保留；提供退出、授权诊断和优雅停止控制路径，健康响应不泄露数据目录或秘密。
- T09 启动器：`scripts/run.py` 使用 OS `flock` 单实例锁，写入 owner-only PID+启动时间+实例身份元数据，锁和元数据在进程退出时清理；`scripts/macos_app.py` 只在 PID、OS 启动时间、实例身份和受保护控制通道均验证后复用/停止，不再按 PID 猜测终止未知进程；健康复用还核对 build/static resource、startup instance 与 data instance。`pair` 子命令只在交互式 TTY 显示配对码，不写日志、URL、argv 或环境变量。
- T09 前端：新增 `frontend/src/local-session.ts`，所有主站、简历编辑器和敏感下载使用 `Authorization: Bearer`；token 仅进 `sessionStorage`，无 token 时提示配对，IAB 不支持原生 `prompt()` 时使用同页配对输入回退；PDF、截图和反馈导出改为鉴权 fetch + Blob，设置页提供“退出本地会话”，build ID 不匹配提示重载。`tests/conftest.py` 仅为旧 TestClient 设置 `CAREER_TEST_MODE=1`，生产启动器不设置该变量。
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
