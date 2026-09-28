# Raw 与 Wiki Semantic Layer

本模块实现 Phase D1 手工 Raw / Wiki 接口、Phase D2 单 Raw Wiki Compiler、Phase D3 业务工作区接入和 Phase D4 长期 Cognition。各阶段复用现有 AI operation、prepare/preview/confirm、Provider gateway、幂等、dispatch slot、outbound audit 与 `current` / `revisions`；不修改旧 `wiki_entry`、T14、Resume Context 或 Raw。

## 数据合同

- 新的手工 Raw 写入 `records` 的 `raw_material` kind，创建后不可编辑或删除；稳定引用由 `kind + id + revision + hash` 组成。
- 旧 `knowledge_source`、项目原文、`work_event`、`work_evidence`、`journey_note`、`interview_raw` 与 Communication 由 `sources.py` 按原始 ID 读取，不复制正文。面试复盘、Research 派生条目与 Achievement 不作为 Raw。
- Wiki 当前对象使用 `current` kind `wiki_knowledge`，历史复用共享的 `revisions` 表。唯一语义类型为 `fact`、`observation`、`hypothesis`；状态为 `current` / `retired`。用户界面统一显示为“已确认事实 / 观察 / 待验证判断”，底层枚举不变。
- 历史页只把最高 revision 标成“当前”；更早 revision 标成“历史”。如果最高 revision 已 retired，只显示“不再有效”，更早 revision 仍是“历史”。该展示直接读取共享 revision 与当前 status，不建立第二套历史状态。
- 新 Wiki 的来源只保存服务器核对过的 typed `source_refs`。空来源表示用户直接写入；provenance 固定为 `{"kind":"user"}`，不伪造 Raw。
- Scope 是 Project、Employment、Opportunity、已确认 Person、Personal 或 Cognition。Opportunity 来源只允许留在同一 Opportunity；Cognition 暂不接收 Opportunity 私有来源。

## HTTP 接口

- `POST /api/raw`、`GET /api/raw?scope_type=...&scope_id=...`、`GET /api/raw/{source_kind}/{source_id}?revision=...&hash=...`。带版本和 hash 打开来源时，若原件当前已变化则拒绝冒充旧正文。
- `GET /api/wiki?scope_type=...&scope_id=...&status=current|retired|all`。
- `GET /api/wiki/workspace?scope_type=...&scope_id=...` 返回一个范围的当前/退役知识和 Raw 来源目录。
- Wiki 列表按需传 `include_source_titles=true`，只返回当前可见知识所引用来源的标题目录，不返回 Raw 正文；`all` 仍排除 Opportunity 私有知识和来源。原文当前版本与引用的 revision/hash 不同时，界面明确提示来源版本已变化，不把新版冒充旧版。
- 原始资料目录与业务 Wiki 工作区为当前 scope 的每份手工 Raw 返回 `pending_patch_count`。项目/任职/人物页面据此显示“建议待处理”和“继续处理建议”；继续入口读取已有 Proposal，不重新调用 Provider。计数仅包含目标 scope 相同的待审 Patch，不扩大 Compiler 的发送范围。
- `POST /api/wiki` 新建；`POST /api/wiki/{id}` 编辑或退役；`GET /api/wiki/{id}/history` 查看共享 revision 历史。
- 新建/修改均要求 `idempotency_key`；修改同时要求 `expected_revision`。Raw 仅提供创建接口，不存在编辑或删除接口。
- `POST /api/wiki/compiler/prepare` 仅为用户选择的一份新手工 Raw 准备最小 Context DTO 和用户可读 Preview，不发送请求。Preview 按“新资料 → 所属项目 / 任职 / 人物 → Wiki 里已有的信息 → AI 会判断”展示；Wiki 类型分别显示为“已确认事实 / 观察 / 待验证判断”，不在每条知识上重复显示范围名称。Preview 的 Raw 全文、当前 Wiki 全文 / Tags 和范围身份只从已清洗的 outbound DTO 投影，不额外读取资料；长正文完整保留在有界滚动区，技术模型与条数放在默认折叠的详情里。边界说明是“仅限上面这些内容，不会读取其他 Career 资料”。
- `POST /api/wiki/compiler/execute` 需要与预览匹配的 `prepared_id`、`payload_hash` 和 `confirm_outbound: true`；确认前重新核对 Raw / Wiki / 范围清单，以及 Provider 请求摘要中的模型配置 ID、provider、model 和 payload（不含 Secret）。真实语义内容或选中的模型配置变化会在 dispatch 前拒绝；时间戳、展示和存储排序不参与请求摘要。stale 时 UI 显示“资料在预览后发生了变化，请重新确认发送内容。”，只有用户点击“重新预览”才准备新请求；不自动 prepare 或重试。使用现有 AI operation 幂等与 dispatch slot。0 Patch 是成功结果；`outcome_unknown` 不自动重试。
- `GET /api/wiki/compiler/proposals?raw_id=...` 与 `GET /api/wiki/compiler/proposals/{id}` 读取待审建议；`POST /api/wiki/compiler/proposals/{id}/patches/{patch_id}/resolve` 每次只接受、编辑后接受或拒绝一条。只有接受才通过 D1 Wiki mutation 改正式 Wiki；没有批量审批接口。
- Project、Employment 和已确认 Person 工作区调用同一组 Compiler API 与前端绑定。业务入口传入 `target_scope: {scope_type, scope_id}`；服务端要求它与所选 Raw 的直接范围相同，并将这一个范围写入 prepare intent、Context manifest 与 Proposal。确认时重新校验目标；Patch 只能写回该范围。业务入口只发送该范围的当前 Wiki，不因 Project 关联 Employment / Person 而读取它们的 Wiki。省略 `target_scope` 的既有 D2 Wiki 页面继续按原多范围上下文合同工作。
- `/api/wiki/workspace` 仍是每个业务页唯一的范围读取接口。Raw 添加时直接绑定当前 Project / Employment / Person；Person 只允许用户从已确认 Person 详情明确添加的 Person-scope Raw，不从普通 mention 推断。当前理解只投影 `status=current`，Fact → Observation → Hypothesis 排序、同类按更新时间倒序；retired 默认不显示，历史和来源仍复用 Wiki revision / source_refs。
- Raw 保存、Wiki 手工保存和 Compiler Patch 逐条审批后，业务页重新读取当前 workspace 数据并重绘，保留已选对象与路由，不调用整页 `location.reload()`。0 Patch 不写 Wiki；用户完成提示后回到原业务页。
- 编辑新增/改写 Patch 时修改的是 Wiki 正文；编辑退役 Patch 时修改的是审批中的退役原因，原 Wiki 正文保持不变。
- 待审界面一次展示一条建议。rewrite / retire 的原文必须从目标知识共享修订历史中读取 `before_revision` 对应内容；找不到该修订就停止显示审批动作，不能拿当前正文代替。新增、改写和退役分别用“新增信息”“修改已有信息”和“建议将这条信息标记为不再有效”展示。
- 每条建议的正常动作是“接受”“编辑后接受”“拒绝”。编辑只改变本地表单；用户点“确认修改并接受”后才提交编辑值，取消只回到原建议。打开 pending 建议、看原文和取消编辑只读，不调用 Provider；不自动重做 prepare，也没有批量接受。
- Context 仅含所选 Raw、其直接范围/明确关联范围，以及这些范围的当前 Wiki；Cognition、全库资料、其它 Raw、退役知识、Resume、Feedback 与未确认 Person 均不进入模型输入。模型输出本地严格验证，只允许 `add` / `rewrite` / `retire`，且每条来源必须精确回到本轮 Raw。Preview 的“让 AI 整理”仍通过单独 confirm 执行；取消只关闭预览。
- 继续使用 schema v6，无数据库 migration。隔离 Chrome 合成流程已验证 Preview → TestProvider 确认 → 单条接受 → 当前 Wiki 立即刷新。D2 正式 smoke、用户逐条审批、最终正文、来源和清理状态见 [STATUS](../../../docs/execution/STATUS.md)。

## D4 长期 Cognition

- 专用 Context 只包含用户选择的至少两段 Project / Employment、各自当前 Wiki，以及当前 Cognition。不会发送 Raw 正文、Person、Opportunity、Resume、Interview、Feedback、历史 revision 或未选择经历。Preview 逐段展示实际发送的 Wiki；只保留“AI 将比较 N 段经历”“不会读取原始资料”和默认折叠的发送详情。已有 Cognition 数量大于 0 时才显示可展开内容。
- Prompt 与动态输出 schema 逐项说明 `add` / `rewrite` / `retire` 的必填字段、来源引用结构、知识类型枚举、目标 ID / revision 配对、禁止额外字段和 `null`。Schema 的示例使用本轮选中 Wiki 的合法 ID；示例正文完全虚构。本地仍按字段类型、长度、目标版本、来源范围和不同经历数严格校验，不修补模型输出。
- 模型输出校验失败只在操作错误记录中保存固定错误码与 JSON 字段路径，不保存模型正文；用户看到“AI 返回的结果无法安全使用，本次没有修改长期认知。”和“关闭”，没有重试入口。add / rewrite 至少由两个不同经历的 Wiki 支撑，retire 至少由一条支撑。
- Proposal 一次显示一条：知识类型、建议内容、支撑经历和“接受 / 编辑后接受 / 拒绝”；rewrite 保留冻结的原版本与建议版本，原因默认折叠。来源引用 ID 不出现在主视图。schema 继续为 v6，不新增表或迁移。
- 仅当测试/运维明确替换了原 smoke 经历范围，系统才可将旧 pending Proposal 和其 Patch 终结为 `superseded`；必须留下系统原因和关联 operation，不能记作用户拒绝或写入 Wiki，原 Proposal 与 Provider 审计保留。
- 本机运行健康核验使用 `PYTHONPATH=src .venv/bin/python scripts/runtime_health_check.py`。脚本只请求 `/healthz`，并只读取 schema、表行数、数据实例标识和 `id/kind/revision` 元数据；不调用 `/api/state`，不读取 SQLite `body`。`tests/test_runtime_health_check.py` 用数据库读取拦截和虚构隐私哨兵验证此边界。
- D4 聚焦测试：`PYTHONPATH=src .venv/bin/python -B -m pytest -q tests/test_wiki_d4.py tests/test_model_gateway.py`；前端：`npm --prefix frontend run test:wiki-semantic && npm --prefix frontend run typecheck`。

## 测试

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_wiki_d1.py tests/test_wiki_d2.py
npm --prefix frontend run test:wiki-semantic
npm --prefix frontend run test:wiki-d3
npm --prefix frontend run typecheck
npm --prefix frontend exec vite build -- --outDir /tmp/career-frontend-build --emptyOutDir
```


## UX-1 AI状态与原建议恢复

`workbench.ai_activity` 提供 `GET /api/ai/activity` 和 `GET /api/ai/activity/{operation_id}`：读取已有AI operations与Proposal，按准备中/处理中/待处理/完成/失败/结果未知投影，不创建第二套任务数据、不调用Provider、不加载职业正文。对象归属仅返回最小身份，审批数量实时取原Proposal。Wiki/Cognition恢复使用原 `GET /api/wiki/compiler/proposals/{id}` 与既有逐条resolve，不prepare/execute。

前端 `ai-activity.ts` 的全局入口与对象轻提示共用同一只读快照；关闭/导航/刷新后重新读服务器，前端内存不是任务正本。Research/Resume只做状态兼容和所属页面入口，本批不重写其编辑/审批UI。详细映射见[UX Reset计划的UX-1合同](../../../docs/execution/CAREER-UX-RESET-PLAN.md)。

验证：`PYTHONPATH=src .venv/bin/python -m pytest tests/test_ai_activity.py tests/test_wiki_d1.py tests/test_wiki_d2.py tests/test_wiki_d3.py tests/test_wiki_d4.py`；`npm --prefix frontend run test:ai-activity`。普通build继续输出临时目录。关闭浏览器时服务端请求可继续；进程中断不重试，按原recover规则处理。

Preview 有效期仍为 10 分钟。到期固定错误码 `prepared_request_expired`，发送前拒绝；旧审计中未 dispatch 且精确匹配过期原因的 `Missing` 也只读投影为准备中，不改审计。Preview 到期或点击时发现到期，只显示手动重新预览入口，不自动 prepare/execute；定时器不能覆盖已进入处理中的页面。

断连时序测试：`tests/test_ai_activity.py::test_real_http_disconnect_before_provider_completion_restores_original_proposal` 使用真实 Uvicorn/HTTP 连接，在 TestProvider 返回前关闭客户端 socket，再放行 Provider；新连接恢复原 Proposal、审批并再次读取进度，确认一次 dispatch、一次 preparation、一个 Proposal。不是只测试“已完成后刷新”。

## UX-2 Wiki 阅读

前端 `wiki-semantic-ui.ts` 只读投影已有知识与 revision：最近更新、按对象浏览、详情、来源、历史；`main.ts` 通过既有 cursor 读齐列表，hash query 保存浏览位置。状态筛选和编辑动作降为次级；旧资料数据不删。`style.css` 的 `.reading-*` 为 opt-in 阅读骨架，未全局改写其他工作区。无新 API/schema/Provider 合同。

前端回归：`npm --prefix frontend run test:wiki-reading`（路由恢复、分页、跨范围隔离、历史唯一当前、来源版本与只读投影）及现有 `test:wiki-semantic`、`test:wiki-d3`、`test:ai-activity`。验收使用完全隔离虚构资料；正常 build 输出 `/tmp`，仅正式 Runtime Update 覆盖 dist。
