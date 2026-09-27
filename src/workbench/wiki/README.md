# Raw 与 Wiki Semantic Layer

本模块实现 Phase D1 手工 Raw / Wiki 接口与 Phase D2 单 Raw Wiki Compiler。D2 复用现有 AI operation、prepare/preview/confirm、Provider gateway、幂等、dispatch slot、outbound audit 与 `current` / `revisions`；不修改旧 `wiki_entry`、T14、Resume Context 或 Raw，也不实现 Cognition 自动提炼。

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
- `POST /api/wiki` 新建；`POST /api/wiki/{id}` 编辑或退役；`GET /api/wiki/{id}/history` 查看共享 revision 历史。
- 新建/修改均要求 `idempotency_key`；修改同时要求 `expected_revision`。Raw 仅提供创建接口，不存在编辑或删除接口。
- `POST /api/wiki/compiler/prepare` 仅为用户选择的一份新手工 Raw 准备最小 Context DTO 和用户可读 Preview，不发送请求。Preview 按“新资料 → 所属项目 / 任职 / 人物 → Wiki 里已有的信息 → AI 会判断”展示；Wiki 类型分别显示为“已确认事实 / 观察 / 待验证判断”，不在每条知识上重复显示范围名称。Preview 的 Raw 全文、当前 Wiki 全文 / Tags 和范围身份只从已清洗的 outbound DTO 投影，不额外读取资料；长正文完整保留在有界滚动区，技术模型与条数放在默认折叠的详情里。边界说明是“仅限上面这些内容，不会读取其他 Career 资料”。
- `POST /api/wiki/compiler/execute` 需要与预览匹配的 `prepared_id`、`payload_hash` 和 `confirm_outbound: true`；确认前重新核对 Raw / Wiki / 范围清单，以及 Provider 请求摘要中的模型配置 ID、provider、model 和 payload（不含 Secret）。真实语义内容或选中的模型配置变化会在 dispatch 前拒绝；时间戳、展示和存储排序不参与请求摘要。stale 时 UI 显示“资料在预览后发生了变化，请重新确认发送内容。”，只有用户点击“重新预览”才准备新请求；不自动 prepare 或重试。使用现有 AI operation 幂等与 dispatch slot。0 Patch 是成功结果；`outcome_unknown` 不自动重试。
- `GET /api/wiki/compiler/proposals?raw_id=...` 与 `GET /api/wiki/compiler/proposals/{id}` 读取待审建议；`POST /api/wiki/compiler/proposals/{id}/patches/{patch_id}/resolve` 每次只接受、编辑后接受或拒绝一条。只有接受才通过 D1 Wiki mutation 改正式 Wiki；没有批量审批接口。
- 编辑新增/改写 Patch 时修改的是 Wiki 正文；编辑退役 Patch 时修改的是审批中的退役原因，原 Wiki 正文保持不变。
- 待审界面一次展示一条建议。rewrite / retire 的原文必须从目标知识共享修订历史中读取 `before_revision` 对应内容；找不到该修订就停止显示审批动作，不能拿当前正文代替。新增、改写和退役分别用“新增信息”“修改已有信息”和“建议将这条信息标记为不再有效”展示。
- 每条建议的正常动作是“接受”“编辑后接受”“拒绝”。编辑只改变本地表单；用户点“确认修改并接受”后才提交编辑值，取消只回到原建议。打开 pending 建议、看原文和取消编辑只读，不调用 Provider；不自动重做 prepare，也没有批量接受。
- Context 仅含所选 Raw、其直接范围/明确关联范围，以及这些范围的当前 Wiki；Cognition、全库资料、其它 Raw、退役知识、Resume、Feedback 与未确认 Person 均不进入模型输入。模型输出本地严格验证，只允许 `add` / `rewrite` / `retire`，且每条来源必须精确回到本轮 Raw。Preview 的“让 AI 整理”仍通过单独 confirm 执行；取消只关闭预览。
- 继续使用 schema v6，无数据库 migration。隔离 Chrome 合成流程已验证 Preview → TestProvider 确认 → 单条接受 → 当前 Wiki 立即刷新。D2 正式 smoke、用户逐条审批、最终正文、来源和清理状态见 [STATUS](../../../docs/execution/STATUS.md)。

## 测试

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_wiki_d1.py tests/test_wiki_d2.py
npm --prefix frontend run test:wiki-semantic
npm --prefix frontend run typecheck
npm --prefix frontend exec vite build -- --outDir /tmp/career-frontend-build --emptyOutDir
```
