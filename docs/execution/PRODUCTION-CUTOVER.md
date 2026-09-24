# Career 生产切换账本

> 历史切换账本：其中 Chrome 配对、重新配对和临时假数据免配对记录是 2026-09-21 以前的真实历史证据。个人本机版已于 2026-09-24 统一免配对；不要把旧记录解释为当前需要配对或重新启用配对。

本账本是 `PRODUCTION-CUTOVER-PROMPT.md` 阶段 0、1、1.5、2、2.5、3 的实际记录。阶段 3 已按用户绑定的发布身份在强制 `LOCAL_ONLY` 下完成正式本机切换；原正式数据目录、旧 App、旧 Python 环境、旧 runtime、LaunchAgent 配置和即时恢复点均保留。没有读取真实 Keychain、调用真实 Provider、修改正式周任务、Git push 或进入 Stage 4。

## 计划身份

- `plan_id`: `career-cutover-20260920-stage25-resume-template-e2dcd25c`
- `plan_hash`: `a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`
- `release_id`: `career-0.7.0-batch-f-stage25-resume-template-20260920`
- `source_fingerprint`: `e2dcd25c1479f895f4c540ea19812a08e7bdacdde2d91747d367f5fdeb440d0d`
- `static_fingerprint`: `2daf9f5aaddf62d94cd3d555555d0f734057b42a6a9132ccde927fd921568ede`
- `branch`: `codex/review-t00-t01-20260919`
- `HEAD`: `82af33dfe4d572e6ab04f36f3757b13a28049037`
- `release_mode`: `LOCAL_ONLY`（Stage 1.5 已在 SecretStore、Provider、ModelGateway、Research web search 和启动器边界验证 fail closed）
- `cutover_gate`: `STAGE_3_LOCAL_ONLY_DEPLOYED_VERIFIED`
- `release_gate`: `PASS_LOCAL_ONLY`

`source_fingerprint` 覆盖 90 个实际运行源码、脚本、前端源、必要静态资源、锁文件和 App 构建源文件；不含 `STATUS.md`、本账本、测试运行产物、Worktree `.venv`、`node_modules`、运行目录、真实数据、备份、Keychain 或正式 `macos/Career.app`。Stage 2.5 修改了 `src/workbench/resume_pdf.py` 的模板映射，旧 `plan_hash/source_fingerprint` 自动作废，以上为当前重算身份；`static_fingerprint` 未变化。`plan_hash` 的计算输入固定为 `plan_id`、`stage=2.5`、`mode=LOCAL_ONLY`、`release_id`、修复说明和两个 fingerprint，按文件行序列化后 SHA-256。旧逐文件清单位于 `/tmp/career-fake-nopair-identity.twhlcX`，本次源指纹是在同一冻结文件列表上重算。

## 阶段 0：当前事实与冻结对象

### 路径、Git 和边界

- 原 Career：`/Users/frog/Projects/Career`；本轮只读盘点，未写入。
- 当前 Worktree：`/Users/frog/Projects/Career-worktrees/review-t00-t01-20260919`；所有源码、文档更新仅在此处。
- 主项目 `main` 与本 Worktree 共同基线为 `82af33dfe4d572e6ab04f36f3757b13a28049037`。Worktree 有 T01–T13 及 Final Acceptance 的未提交有效修改；主项目的未知未跟踪 `Career-review/` 与 Worktree 未跟踪 `-` 均不属于发布对象，不能删除或覆盖。
- 完整 staged/unstaged/untracked 快照见受限证据目录的 `worktree-status.txt`、`untracked-files.txt`、`worktree.patch`；不把真实数据或秘密放入快照。

### 正式运行组合（只读核验）

| 项目 | 当前事实 |
|---|---|
| 数据 | `/Users/frog/Library/Application Support/Career Data`，同盘设备 `16777230`，约 `816K`、3 个文件、目录权限 `0700` |
| DB | `workspace.sqlite3`，schema/user_version `6`，journal `delete`，无 `-wal/-shm`，`quick_check=ok`，DB SHA-256 `6c7b6bbe1e04ed86ccc4862e86fd5bac3f2305535f38db3d844071cde3ee3721` |
| 现有 schema | 物理表为 `applications/current/meta/records/revisions`；未发现 `ai_operations` 等新物理表。不得在正式 DB 实例化新版 `Store` 以免隐式写 DDL；迁移只能在阶段 2 副本做 |
| 备份 | `/Users/frog/Library/Application Support/Career Data-backups`，当前 0 个文件、`0B`；本阶段未写入 |
| App | `/Users/frog/Projects/Career/macos/Career.app`；正式 App 未替换 |
| runtime | `/Users/frog/Projects/Career/.career-runtime`；当前只有 `career.log`、`career.pid`，无新版 `process.json` |
| 服务 | PID `79422`，监听 `127.0.0.1:8765`，启动时间 `2026-09-19 12:11:16 +0800`，实际命令为 `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python /Users/frog/Projects/Career/scripts/run.py --port 8765 --no-browser` |
| Python | 正式 `/usr/bin/python3` 和 `/Users/frog/Projects/Career/.venv/bin/python` 均为 `3.9.6`；当前代码合同为 Python `3.10+`，正式环境因此阻断 |
| LaunchAgent | label `local.career.weekly-backup`；plist `/Users/frog/Library/LaunchAgents/local.career.weekly-backup.plist`；使用正式 `.venv`、`/Users/frog/Projects/Career/scripts/weekly_backup.py`、正式数据/默认备份路径；当前 `not running`、`runs=0`、无历史退出码。本阶段未 load/unload/修改 |
| 磁盘 | 系统卷约 `305Gi` 可用、使用率 `28%`；正式数据与备份目录同设备，满足“无打开连接且已批准”时的同盘原子重命名前提，但本阶段未执行 |

### 候选身份

- 固定 Candidate 环境：`/Users/frog/Library/Application Support/Career Environments/career-0.7.0-batch-f-3.12.14`，Python `3.12.14`，从 `requirements.lock` 安装；`python -m pip check` exit `0`。正式 `/Users/frog/Projects/Career/.venv` 保留为 Python `3.9.6`，未原地升级。
- SQLite：候选 Python 实际链接 `3.51.0`。
- Chrome：`Google Chrome 153.0.8010.50`；PDF renderer 为锁定 `Playwright 1.51.0` 驱动的本机 Chrome；字体 `SourceHanSansCN-VF.woff2` SHA-256 `f971e3bff46f76b49e1d5510556c2297c618ec4b491a295a4e741cdd38257799`。
- 当前 backend/frontend build identity：`career-0.7.0-batch-f`；frontend dist 12 个文件，`static_fingerprint` 如上。

### 冻结发布对象

发布对象为当前 Worktree 的实际有效未提交源码、脚本、前端源、中文字体/图标、`requirements.lock`、`frontend/package-lock.json` 和由它们生成且与 `static_fingerprint` 一致的静态 dist。明确排除：原主项目未知资料、`-`、生产 `Career.app`、正式 `.venv`、真实 DB/附件/备份、Keychain、日志、`.career-runtime`、`node_modules` 和临时候选目录。Stage 1.5 已改变源码与运行边界，旧阶段 2 授权请求自动作废；若阶段 2/3 任何源、锁文件、schema、静态产物、模式或路径改变，以上身份立即失效，必须重新冻结、复验并申请新 hash。

## 阶段 1：隔离补验结果

### A. Chrome 用户链和未保存保护

- 新建候选 App/端口 `18803`、隔离 runtime/data 和虚构机会“隔离验收星河科技 / 中文平台工程师”，真实 Chrome 完成：Wiki → 机会列表 → 机会详情 → 创建独立简历工作稿 → 页面显示文字 PDF 提示 → 记录已投递 → 投递冻结成功 → 确认“一面” → 面试阶段显示“时间待定·待排期”。服务已停止，标签已关闭。
- 当前代码的 T01 弹窗关闭、遮罩、Esc、路由和 `beforeunload` 防护有自动回归；完整 Chrome 分支（尤其刷新/关闭页面、取消放弃后输入保留、明确放弃后退出）仍没有在本阶段取得完整独立证据，继续列为 Final Acceptance 未验项。

### B. PDF 文字和冻结

- `tests/test_resume_pdf.py` 及当前专项回归：exit `0`，`42 passed`（包含 PDF、AI、安全、会话、备份、分页相关专项）。冻结 A → 编辑 B 的 PDF、版本、投递快照不变由自动测试覆盖。
- 对隔离 PDF `/tmp/career-final-acceptance.pdf`，Poppler `pdftotext` exit `0`，实际提取出 `林晓岚·验收版A`、`验收虚构星河科技`、`中文平台工程师`、`2024年1月—2025年6月`、`项目经历`、`负责人`，顺序正确。`pypdf` 在本机 Chromium CJK 子集上把部分字映射为相近 Unicode 兼容字符；这不是将错误汉字归一化为正确汉字，已保留为工具兼容风险。
- 原编辑器提示与 T04 实现冲突，已做最小修复：`frontend/editor.html` 改为“导出的 PDF 保留真实文字层，可在 PDF 查看器中选择文字。”。浏览器页面已看到新提示。Chrome/Preview 中真实鼠标选择、复制粘贴和人工分页检查因浏览器 file URL/系统人工操作限制未完成，不能标记通过。

### C. AI 重试与模式

- `tests/test_ai_operations.py` 的 `CountingFakeProvider` 直接断言供应商次数：串行重复 5 次为 `call_count=1`；首调用阻塞时并发 5 次最终为 `1`；同 key 不同输入拒绝；成功后模拟重启仍为 `1`；`outcome_unknown` 再请求仍为 `1`。这是自动不变量证据，不是 UI 证据。
- 已核对 Research、Resume suggestion、Interview review/patch 和 legacy analyze 均在 provider 前登记 operation。真实 UI 的快速重复/关闭后重开仍可能生成新 key；当前没有一个可统计 CountingFakeProvider 的完整浏览器 harness，故 UI 用户意图链仍未验。
- 阶段 1.5 前的缺口已复现：`CAREER_AI_PROVIDER=test` 只控制测试 Provider，正式 DB 仍有旧 AI 配置行，缺少 production-data `LOCAL_ONLY` fail-closed 边界；该缺口由下一节专项修复并验证。

## 阶段 1.5：production-data LOCAL_ONLY fail-closed

### 实现边界

- `CAREER_AI_MODE` 只接受显式 `LOCAL_ONLY` 或 `AI_ENABLED`；缺失、空值、非法值解析为安全的 `LOCAL_ONLY`，但启动器 `scripts/run.py` / `scripts/macos_app.py` 会拒绝未显式配置的启动，不会自动回退真实 AI。
- `Store` 在 `LOCAL_ONLY` 下使用非 Keychain 的 `LocalOnlySecretStore`；即使加载带 `api_key_ref`、`secret_status=ready`、默认模型配置的生产样式数据库副本，也不会读取、清理或探测真实 Secret。
- 最终 Provider 边界：`LocalOnlyProvider`、`TestProvider.complete`、`RealProvider.complete`、`OpenAICompatibleAdapter._request` 均拒绝 `local_only_disabled`。`ModelGateway` 在选择配置和读取 Secret 之前再次拒绝；连接测试、legacy analyze、Resume AI、Interview AI 均复用该边界。
- Research web search 在 `web_search` 入口拒绝，且业务路径不依赖前端按钮隐藏；Research 搜索、模型调用和所有遗留分析入口均不能通过数据库配置、环境 API Key、`CAREER_AI_PROVIDER=test` 或注入 Provider 绕过。
- AI 配置创建、更新、删除、设默认、清默认和 ephemeral connection test 在 `LOCAL_ONLY` 下也被拒绝；人工编辑、结构化简历保存、机会读取、PDF/附件、备份/恢复不经 AI 边界，保持可用。

### 专项测试证据

- `tests/test_local_only_gate.py` 使用虚构隔离 DB、生产样式 `ModelConfig`/`api_key_ref`、环境中的假真实样式 API Key、注入 `TestProvider` 和会在任何调用时立即失败的网络 trap。
- 直接覆盖 legacy analyze、Research web search、Resume AI suggestion、Interview final review；同时覆盖真实 Provider、TestProvider、OpenAI-compatible adapter、AI 配置创建/连接测试和 SecretStore 读取边界。
- 关键断言：所有 AI 路径返回 `503` + `code=local_only_disabled`；Secret trap 调用为 `0`；网络 trap 未触发；本地 profile/机会/Resume 编辑链仍返回成功。缺失/非法模式不会得到真实 Provider，显式启动模式才允许启动器继续。
- 本专项不读取正式数据库、真实 Keychain 或环境中的真实 Key；没有真实 Provider 出站。

### 阶段 1.5 状态

- `LOCAL_ONLY` 硬阻断：`CODE_VERIFIED`，可作为阶段 2 候选副本启动的安全模式。
- 全局发布门禁仍为 `BLOCKED`：Python 3.10+ 环境、真实 App/Chrome/PDF/备份平台验收、Starlette residual risk 及用户授权仍未完成；Stage 1.5 不等同阶段 2 或阶段 3 授权。

### D. T11 虚构规模

- 用 1000 条虚构机会启动候选 App，浏览器真实看到机会列表摘要为 `1000 条`；列表首屏显示约 500 条，浏览器无可见“下一页”按钮，顶层页面切换可用，已记录为交互观察而非性能结论。
- `GET /api/state?view=summary`：HTTP `200`，1000 条机会，`1,292,277` bytes，`0.074188s`；`GET /api/opportunities?view=all`：HTTP `200`，1000 条，`749,781` bytes，`0.022617s`。仅为本机一次隔离采样，不代表生产性能；是否满足摘要首屏合同仍需产品/最终验收确认。

### E. 候选启动器和定时任务

- 隔离候选曾验证冷启动、服务健康、独立端口、未知占用拒绝、实例身份和可信停止；正式 PID `79422` 全程存活。最新候选完整 Chrome 链使用独立端口 `18803`，结束后端口已释放。
- 连续双击、旧 build 与真实 macOS App/LaunchAgent 的 OS 级证据、一次性周任务触发和真实文件系统故障仍是平台阻断；本阶段没有修改或触发正式周任务。

### 安全残余

- 当前 `pip-audit` exit `1`：`starlette==0.46.2` 14 条记录、7 个唯一 advisory：`PYSEC-2026-1941`、`PYSEC-2026-1942`、`PYSEC-2026-161`、`PYSEC-2026-2281`、`PYSEC-2026-2280`、`PYSEC-2026-249`、`PYSEC-2026-248`。未使用 `--ignore-vuln`。
- FastAPI/Starlette 当前锁定兼容范围不支持未经评估的盲升；Range DoS 和 Host/path reconstruction 的应用层前置拒绝专项仍通过。发布前必须重新查兼容版本和官方 advisory；不能将 audit exit 1 改写成通过。

## 阶段 2：LOCAL_ONLY 候选切换演练

### 数据恢复点与迁移

- 正式源 `/Users/frog/Library/Application Support/Career Data` 仅通过已验证的一致性 `backup()` 机制读取；未停止正式 PID `79422`，未改动正式源。备份目标为 `/Users/frog/Library/Application Support/Career Data-backups/cutover-rehearsal-20260920`，不覆盖既有备份。
- 新恢复点 manifest 为 `schemaVersion=1`、`status=complete`、`healthy=true`、`valid=true`、`recoverable=true`、`needs_attention=[]`；manifest SQLite hash=`a856e0ac14fb95e4dda7a4a5a94b31d3fad8246e984ca2ca3a8efc42248c9202`，附件 `artifacts/demo-b5-resume-pdf.pdf` hash=`8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。
- 恢复到全新隔离目录 `/Users/frog/Library/Application Support/Career Data-cutover-candidate-20260920` 后，`migration_baseline.py verify` exit `0`：`differences=[]`、`backup_integrity=["ok"]`、`restored_integrity=["ok"]`，snapshot SHA-256=`7eb49d921c13c8931eab01d224ec4b1cb72d7a666f3e567a0560b27391e7d3cb`；applications=1、current=31、meta=1、records=51、attachments=1，schema=6，SQLite `quick_check=ok`。候选 DB hash 与 manifest 一致，正式 DB 在备份前后仍为 `6c7b6bbe1e04ed86ccc4862e86fd5bac3f2305535f38db3d844071cde3ee3721`。
- `inventory` exit `0`，schema v6、完整性和 FK 验证通过，`migration_performed=false`；无 migration gate，因此未执行 apply。没有修改正式源。证据：`/tmp/career-stage2-evidence.bihngI/candidate-inventory.json`、`restore-verification.json`。

### Candidate 身份与 macOS

- Candidate Python=`/Users/frog/Library/Application Support/Career Environments/career-0.7.0-batch-f-3.12.14/bin/python`（3.12.14）；App=`/Users/frog/Applications/Career Review Candidate.app`；data=`/Users/frog/Library/Application Support/Career Data-cutover-candidate-20260920`；runtime=`/Users/frog/Library/Application Support/Career Runtime/career-0.7.0-batch-f-20260920`；logs 在同一 runtime；端口 `127.0.0.1:8865`。Candidate 进程环境实际包含 `CAREER_AI_MODE=LOCAL_ONLY`、独立 data/runtime 路径，`/healthz` 返回 build=`career-0.7.0-batch-f`。
- 已验证 Candidate 冷启动、运行中再次 `open -na`/连续双击不生成第二进程（PID 保持稳定）、未知服务占用端口时拒绝启动且不杀 dummy 或正式 PID、正常停止释放 `8865`。正式 PID `79422` 全程存活，正式 `8765` 未被 Candidate 使用。
- 正式旧 Career 未经历停止/恢复切换：PID=`79422`、启动时间=`Sat Sep 19 12:11:16 2026`、原命令和 `8765` listener 未改变。旧 build 没有 `/healthz` 路由，访问 404 与该旧身份一致；不能把它误记为 Candidate 健康证据。

### Chrome、业务链、PDF 与规模

- 隔离 Chrome 完成首次配对、刷新后会话保持、退出、重新配对；真实恢复数据下访问 Wiki、机会、面试、简历/任职四个一级入口，机会详情和简历编辑器均加载，未执行业务写入。历史 `[案例]远岑软件` 详情显示既有 `Research owner 不合法` 警告，记录为恢复数据的未修复观察，不扩大 Stage 2 范围。设置页仍显示“真实 AI”诊断文案，但 Candidate 进程是显式 `LOCAL_ONLY`，后端最终边界拒绝所有 AI/Research 出站；该文案不作为安全边界证据。
- Resume catalogue 首次真实访问暴露了一个阻断 UI 的最小代码 bug：后端返回合法摘要 DTO，前端却强制要求 `document`/`revision`。仅修改 `frontend/src/contracts.ts` 使摘要 DTO 合同可选字段化；源码/静态身份随即按本节顶部重算，修复后全量门禁通过，简历工作台和真实恢复简历正常加载。
- Preview 实际打开恢复附件 `demo-b5-resume-pdf.pdf`，窗口 AX 文本层可见 `周岚 高级产品经理 数据产品策略与跨团队交付 虚构演示材料`；自动 `pypdf/pdfinfo/pdftotext` 与冻结 hash 证据保留。人工剪贴板回读未完成，因此不把复制结果宣称为独立通过。
- 用 1000 条虚构机会的隔离数据启动 Candidate/Chrome，页面显示 `1000 条`，列表首屏可见部分记录，页面切换到简历完成；本轮未见可操作分页按钮，未作性能结论。此前隔离请求采样：`/api/state?view=summary` HTTP 200、1,292,277 bytes、0.074188s；`/api/opportunities?view=all` HTTP 200、749,781 bytes、0.022617s。

### Stage 2 状态

> 以下三项是 2026-09-20 的历史验收结果；其临时免配对限制已被 2026-09-24 的个人本机版决策取代，具体记录不改写。

- `PASS`（Candidate-only rehearsal）：恢复点、隔离数据链、Candidate 身份、LOCAL_ONLY、只读业务链、PDF 文本层、macOS 启动器和质量门禁满足本阶段可证明条件；后续新增的临时假数据免配对模式也已完成四重条件验证。
- `BLOCKED`（release/Stage 3）：真实 Keychain/Provider 未授权且未触碰；正式 Python 仍为 3.9.6；真实周任务/恢复故障、真实 PDF 鼠标复制、完整用户链和 Starlette residual risk 仍需最终验收。新增免配对能力只对四重条件同时满足的临时假数据生效；源码变化使上一版阶段 2 身份自动作废，Stage 3 必须基于本节顶部新身份另行授权。
- 免配对回归：四重条件的虚构临时数据服务 `127.0.0.1:8866` `/api/state` HTTP `200`；同一标记数据缺少显式免配对开关的 `127.0.0.1:8867` `/api/state` HTTP `401 pairing_required`；两个临时服务均已优雅停止。

## Stage 2.5：简历 PDF 视觉兼容修复（2026-09-20）

本阶段暂停 Stage 3，仅处理 T04 将截图式 PDF 替换为结构化文字 PDF 时越界改变原简历模板的问题。旧模板正本为当前未改动的 `frontend/src/editor/legacy.css`、`frontend/src/editor/legacy-app.js`；历史视觉基准为 `docs/archive/reviews/2026-09-15-novice/2026-09-15-novice-assets/03-empty-editor.png`。事实核对显示旧模板具有 9mm 纸面内边距、居中姓名、图标联系方式、深灰左侧标题块与灰色横线、三列经历/项目表头、圆点 bullet、教育背景同级分区和紧凑间距。

T04 的 `src/workbench/resume_pdf.py` 原先另建了白底极简模板：12/14mm 页边距、无联系方式图标、普通 `h2` 线、字段使用点号横排、无旧模板分区块和 bullet 结构。此次最小修复仅改该服务端结构化 HTML/CSS 映射，继续使用本地 Chromium/Playwright 真文字层、中文字体、A4 分页、清洗后的富文本、`document_hash`、PDF hash 和 renderer version；未恢复 `html2canvas`/jsPDF，未改结构化数据或冻结语义。

隔离视觉验收使用同一份虚构中文简历：旧编辑器 `http://127.0.0.1:8868/editor.html` 截图与 `/tmp/career-stage25-structured-resume-v2.pdf` 渲染图逐项对照，整体布局、字体层级、标题块、对齐、间距、bullet、分隔线和页边距均回到旧模板；空“教育背景”在前端规范化后也一致。新版 PDF `pypdf` 提取为 1 页 A4，姓名、联系方式、公司、岗位、日期、项目和教育标题存在且顺序正常。

Computer Use 已在 macOS 解锁后完成 Preview 选择“虚构星河科技 · 高级产品经理 · 2023年07月—2025年06月”→⌘C→TextEdit 粘贴；实际粘贴文本为“虚构星河科技 / 高级产品经理 2023年07月—2025年06月”。临时文稿已删除且未保存。该项不再阻塞 `LOCAL_ONLY`；其余切换门按 [RELEASE-GATE](RELEASE-GATE.md) 的 A/B/C/D 分类执行。

Stage 2.5 未读取正式数据、正式 Keychain、真实 Provider，未停止正式服务、未修改正式周任务、未部署、未 push。源码变化使原阶段 2/Stage 3 身份自动作废；当前身份见本账本顶部。当前已具备请求 `LOCAL_ONLY` Stage 3 的条件，但不等于授权或执行；Python/正式 App 身份/最新即时恢复点/完整切换用户链仍是 Stage 3 执行中的检查，失败即停止或回滚。

## 阶段 3 历史预案（已按本轮授权执行）

只有阶段 2 演练健康、Python 3.10+ 固定环境可运行、已使用本账本绑定的 `LOCAL_ONLY` 模式、A 类前置阻断为零且 B 类执行检查已纳入授权，且用户另行批准阶段 3 后，才能执行：

1. 用户保存并确认停止写入；核验正式 PID `79422`、正式 LaunchAgent 状态和无其他 Career 写入者。
2. 在切换瞬间重新创建最新恢复点，记录 DB/附件/manifest hash；不得使用本阶段较早演练副本覆盖新数据。
3. 仅整合本账本冻结的 release object；保留原 App、旧 `.venv`、旧 plist、旧 runtime、旧数据和可恢复备份。
4. 经身份核验后停止旧服务，确认 `8765` 释放；若身份不明、端口未释放或旧服务仍有写入，立即停止，不杀未知进程。
5. 将新版 App、固定 Python、迁移后副本和批准的模式按已演练路径切换；原 LaunchAgent 只更新已批准的解释器/代码/数据路径，label、周期和保留策略不变。
6. 维护/只读启动，校验 PID/启动时间/实例身份、build/static/source/schema/data identity；确认页面无需配对即可访问，同时跨站请求仍被拒绝；正常业务写入必须等待用户人工确认。

## 阶段 3：LOCAL_ONLY 正式本机切换（2026-09-21）

### 授权与冻结身份

- 执行前重新核对 `plan_id=career-cutover-20260920-stage25-resume-template-e2dcd25c`、`plan_hash=a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`、`release_id=career-0.7.0-batch-f-stage25-resume-template-20260920`、`source_fingerprint=e2dcd25c1479f895f4c540ea19812a08e7bdacdde2d91747d367f5fdeb440d0d`、`static_fingerprint=2daf9f5aaddf62d94cd3d555555d0f734057b42a6a9132ccde927fd921568ede`，均与授权一致。完整门禁构建后按同一 90 个源文件和 12 个静态文件清单复算，两个 fingerprint 仍一致。
- 冻结发布对象位于 `/Users/frog/Library/Application Support/Career Releases/career-0.7.0-batch-f-stage25-resume-template-20260920`；固定 Python 位于 `/Users/frog/Library/Application Support/Career Environments/career-0.7.0-batch-f-stage25-resume-template-20260920-3.12.14`，实际为 Python `3.12.14`。正式 `/Users/frog/Projects/Career/.venv` 仅切换为指向该固定环境的符号链接；旧 Python 3.9 环境保留为 `/Users/frog/Projects/Career/.venv-python3.9-pre-stage3-20260921T014451Z`，没有原地升级。
- 旧正式 PID `79422` 在停止前按 PID、启动时间、命令、cwd、端口、数据和 App 身份重新核对，仅发送 `SIGTERM` 并确认退出及 `8765` 释放。旧 App、runtime、数据和发布文件的回滚材料位于 `/Users/frog/Library/Application Support/Career Cutover Rollback/stage3-20260921T014451Z` 及各 `*-pre-stage3-*` 保留路径；没有删除或覆盖。

### 即时恢复点、隔离副本与 schema

- 即时私有恢复点：`/Users/frog/Library/Application Support/Career Data-backups/pre-stage3-local-only-20260921T014451Z`，`created_at=2026-09-21T01:45:15.390631+00:00`，manifest 为 `complete/valid/healthy/recoverable`，`differences=[]`、`needs_attention=[]`、`quarantine=[]`。SQLite hash=`a856e0ac14fb95e4dda7a4a5a94b31d3fad8246e984ca2ca3a8efc42248c9202`，冻结 PDF hash=`8d8a5563e64b9acf4a8771fbcfd44fd4693a6afcd4ce4a54a82ec50643b2d082`。
- 原正式源目录已原子改名并保留为 `/Users/frog/Library/Application Support/Career Data-pre-stage3-local-only-20260921T014451Z`；其数据库 SHA-256 仍为切换前的 `6c7b6bbe1e04ed86ccc4862e86fd5bac3f2305535f38db3d844071cde3ee3721`。Candidate 从未直接打开该目录；正式运行链始终是“正式源 → 一致性备份 → 全新恢复副本 → 已验证副本切换到默认路径”。
- 首次正式候选启动发现 schema v6 恢复点尚无 T03 的 `ai_operations`、`ai_dispatch_slot` 与 `ai_operation_identity`。业务行和附件哈希未变，但 schema hash 变化；因此未把它误记为“无迁移”。随后从同一恢复点另建 `/Users/frog/Library/Application Support/Career Data-stage3-explicit-prepare-20260921T020542Z`，补齐只读 inventory → hash-bound dry-run → `LOCAL_ONLY` apply → verify，再切到正式路径。
- 显式 verify：原有 `applications/current/meta/records/revisions` 的全部 row hash、计数、冻结材料和附件 hash 不变；仅新增上述 3 个 schema object，`ai_operations=0`、`ai_dispatch_slot=1`，完整性 `ok`、FK/完整性问题均为 `0`。正式重启后的 final inventory 与已验证副本逐项相等。证据位于 `/Users/frog/Library/Application Support/Career Cutover Evidence/stage3-20260921T014451Z`。

### 正式 App、macOS、Chrome 与 PDF

- 正式 App 为 `/Users/frog/Projects/Career/macos/Career.app`，bundle id=`local.career-os.desktop`，ad-hoc 签名通过 `codesign --verify --deep --strict`；正式 data=`/Users/frog/Library/Application Support/Career Data`，runtime/log=`/Users/frog/Projects/Career/.career-runtime`，端口 `127.0.0.1:8765`。最终服务 PID=`39300`、启动时间=`2026-09-21 10:06:41 +0800`、Python=`3.12.14`、build=`career-0.7.0-batch-f`、data instance=`42ff565e28a08e31414442521540ac3e`，只有 loopback listener。
- 真实 App 已通过冷启动、连续打开/运行中再次打开只复用同一实例、可信停止、重新启动；受控旧 build 占用 `8765` 时新版拒绝且未误杀占用进程，释放后正常启动。正式 LaunchAgent plist SHA-256 仍为 `87b73bf9d7c179d22b9e9260678aa64231f24b677eab687079dfeee69f3f0099`，label/周期未改，也未触发正式周任务。
- 真实 Chrome 当时完成一次性配对、刷新保持会话、退出、服务重启后重新配对、四个一级导航、真实机会详情、简历工作台、任职和 Wiki 只读查看。**配对步骤现已退役；其余浏览器与数据完整性结果仍作为当时证据保留。**未保存虚构长文本分别验证关闭按钮、Esc、遮罩、路由切换和 `beforeunload`；均触发保护且最终选择放弃，未保存业务数据。正式数据 final inventory 证明浏览器验收未改变任何既有业务 row hash、冻结材料或附件。
- 正式数据中没有可在不写入的前提下形成完整“真实机会 → 新面试 → 新简历”链；唯一面试是旧 demo/unknown 记录，因此没有为验收制造生产业务写入。历史 demo 机会曾显示一次 `Research owner 不合法`，真实机会重新加载正常；设置页仍把数据库 AI 配置显示为“真实 AI”，但该文案不是运行边界，列为后续 LOCAL_ONLY 状态展示改进。
- 现有冻结 demo 简历经当前正式结构化 PDF 路径重新生成到临时目录：1 页、91,848 bytes、PDF SHA-256=`d9feeded5d9653ebd6f7517bf8f410a36dfcdebc37a2b49d28d853ae7180c544`、document hash=`038b99488315df34d770762e87cb13f199745c82aef9a76d81aa80d442f3d4fe`、renderer=`playwright-1.51.0-chrome-153.0.8010.50`。Preview 实际选择并复制“澄明科技 产品与交付负责人 2021-04—2024-08”，TextEdit 回读保留完整中文和日期顺序（字段加粗边界表现为 `**`），证明不是截图 PDF。
- T11 规模继续采用已验证的隔离 1000 条虚构机会证据：summary `1,292,277` bytes/`0.074188s`，all opportunities `749,781` bytes/`0.022617s`，Chrome 显示总数和页面切换；未见分页按钮，不据此宣称性能结论。

### LOCAL_ONLY 与质量门禁

- 最终进程环境重新读取为 `CAREER_AI_MODE=LOCAL_ONLY`。`tests/test_local_only_gate.py` 与 `tests/test_t12_1_dependency_security.py` 合计 `7 passed`：生产样式 `ModelConfig/secret_ref`、环境假 Key、注入 TestProvider、Research、Resume AI、Interview AI、legacy analyze、连接测试全部在 SecretStore/Provider/ModelGateway/web-search 最终边界前拒绝；Secret trap 调用 `0`，network trap 调用 `0`，Range/Host 危险输入在 Starlette 危险路径前拒绝。正式进程检查时只有 `127.0.0.1:8765` listener，无外部 socket；本轮未读取真实 Keychain、未调用真实 Provider。
- `scripts/review_checks.py` exit `0`：内含 `pytest -q` `282 passed`、frontend typecheck/build、`pip check`、`npm ls --depth=0`、secret scan、Markdown links、`git diff --check`，全部 exit `0`。一次把整个测试进程错误强制为 `LOCAL_ONLY` 的门禁运行因预期 fail-closed 出现 83 个假 Provider 用例失败；撤掉外层覆盖、恢复仓库标准隔离测试入口后全量通过，不是产品回归，也未修改源码或测试。
- 最新 `pip-audit` 仍为 exit `1`：`starlette==0.46.2` 14 条数据库记录、7 个唯一 advisory，未使用 `--ignore-vuln`。当前锁定 FastAPI `0.115.12` 上界 `<0.47.0`；包索引现有 FastAPI `0.141.1`/Starlette `1.6.0`，最早允许 Starlette `1.3.1` 的 FastAPI 线为 `0.133.0`，存在升级路径但不是低风险补丁，故本次已授权切换不扩栈。T12.1 的 7 项分类、Range/Host 直接缓解与剩余风险继续有效。

### Stage 3 状态

- `PASS — DEPLOYED_VERIFIED (LOCAL_ONLY)`：正式本机服务已切到批准发布对象、固定 Python 3.12.14 和已验证恢复副本；正式源始终保留未被 Candidate 修改，回滚对象和即时恢复点齐全。
- `ACCEPTED` 仍由用户决定；`AI_ENABLED` 仍未授权、未验收。真实 Keychain、真实 Provider 和收费调用继续属于独立 Gate。没有执行 Stage 4、合并、push、清理或旧资源删除。

## 回滚

- 未发生新增业务写入且旧完整恢复点健康时：可信停止候选；保留失败 App、runtime、日志、迁移证据和新目录；恢复旧 App + 原 `.venv` + 原 plist + 同一恢复点，不让旧代码打开新 schema/新数据；恢复原 LaunchAgent 加载状态并核验旧 PID/端口/只读读取。
- 已发生或无法排除新增写入时：不自动覆盖或合并；停止写入并保留现场，向用户报告数据归属/恢复点状态，等待明确决定。不能把旧备份直接覆盖正式数据。
- 任何回滚都不删除 Worktree、备份、`.partial-*`、候选环境、证据或正式 Keychain 对象；清理另行授权。

## 阶段 3 历史授权请求（已由用户批准并执行）

> Stage 2/2.5 仅在 `LOCAL_ONLY` 下完成 Candidate-only rehearsal 与简历模板兼容修复；新增免配对功能仅适用于显式标记的临时假数据，没有执行正式切换。请求阶段 3 前，必须重新确认 `plan_id=career-cutover-20260920-stage25-resume-template-e2dcd25c`、`plan_hash=a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`、`release_id=career-0.7.0-batch-f-stage25-resume-template-20260920`、`source_fingerprint=e2dcd25c1479f895f4c540ea19812a08e7bdacdde2d91747d367f5fdeb440d0d`、`static_fingerprint=2daf9f5aaddf62d94cd3d555555d0f734057b42a6a9132ccde927fd921568ede`。在新的明确授权前，不停止正式服务、不创建正式切换点、不读取 Keychain、不修改正式数据/LaunchAgent、不调用 Provider、不部署、不 push。

上述请求已由用户按完全相同的计划身份批准，实际副作用和结果见“阶段 3：LOCAL_ONLY 正式本机切换”。`AI_ENABLED` 和 Stage 4 未获授权。

## 当前状态

- `STAGE_3_LOCAL_ONLY_DEPLOYED_VERIFIED`
- `MERGE_READY: NOT_APPLICABLE`（本轮是本机正式切换，不执行 Git 合并）
- `ACCEPTED: NO`
- `DEPLOYED_VERIFIED: YES (LOCAL_ONLY)`
- 独立 Subagent：无法核实实际 Luna/High 配置，本轮未使用 Subagent；由主线程串行执行和只读审查，不计独立审查证据。

## 阶段 1 / 1.5 执行日志（脱敏）

- `pytest -q` → exit `0` — `280 passed in 102.05s`。
- `pytest -q tests/test_resume_pdf.py tests/test_t12_1_dependency_security.py tests/test_ai_operations.py tests/test_t09_local_session.py tests/test_macos_app.py tests/test_t10_backup.py tests/test_t11_pages.py` → exit `0` — `42 passed`。
- `npm --prefix frontend run typecheck` → exit `0` — TypeScript check passed。
- `npm --prefix frontend run build` → exit `0` — Vite production build passed。
- `python scripts/review_checks.py` → exit `0` — full pytest/typecheck/build/pip check/npm ls/secret scan/links/diff check passed。
- `pip-audit -r requirements.lock --format columns` → exit `1` — Starlette 14 条记录、7 个唯一 advisory，风险保留。
- `git diff --check` → exit `0` — no whitespace errors。
- `ps -p 79422 -o pid=,command=` → exit `0` — 正式旧服务仍存活，未停止。
- `pytest -q tests/test_local_only_gate.py` → exit `0` — `3 passed`；生产样式 `ModelConfig`/`secret_ref`、环境假 Key、四条 AI 路径、真实/测试 Provider、连接测试和本地手工链均覆盖。
- `pytest -q tests/test_local_only_gate.py tests/test_macos_app.py` → exit `0` — `9 passed`；启动模式和候选 App 显式嵌入 `LOCAL_ONLY` 回归通过。
- 中间回归曾出现 `278 passed, 1 failed`；唯一失败是旧 `test_t13_release_readiness` 仅按 STATUS 前 2500 字符匹配旧文案。已在 STATUS 顶部保留等价的“真实 Provider 仍未授权”明确事实，随后复跑通过；Stage 1.5 最小边界修复新增 Provider 实例绑定/注入重绑定回归后，最终 `pytest -q` exit `0`、`280 passed in 102.05s`。
- `CAREER_AI_MODE` 启动边界核验：缺失值 exit `78`、非法值 exit `78`；显式 `LOCAL_ONLY` 候选在隔离临时 data/runtime 上 `/healthz` 返回 `200`（`{"status":"ok","build_id":"career-0.7.0-batch-f"}`），候选进程退出 `143` 且端口 `18999` 已释放；正式 PID `79422` 及 `127.0.0.1:8765` 全程存活。
- `pytest -q tests/test_local_only_gate.py tests/test_ai_operations.py tests/test_outbound_policy.py tests/test_research.py tests/test_t08_resume_suggestions.py tests/test_interview.py tests/test_macos_app.py` → exit `0` — `53 passed`。
- `python scripts/review_checks.py` → exit `0` — `280 passed`，frontend typecheck/build、pip check、npm ls、secret scan、Markdown links 和 git diff check 均通过。
