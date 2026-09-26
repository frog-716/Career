# Raw 与 Wiki Semantic Layer

本模块是 Phase D1 的手工 Raw / Wiki 接口。它不调用 Provider，不生成 Patch，也不修改旧 `wiki_entry`、T14 或 Resume Context。

## 数据合同

- 新的手工 Raw 写入 `records` 的 `raw_material` kind，创建后不可编辑或删除；稳定引用由 `kind + id + revision + hash` 组成。
- 旧 `knowledge_source`、项目原文、`work_event`、`work_evidence`、`journey_note`、`interview_raw` 与 Communication 由 `sources.py` 按原始 ID 读取，不复制正文。面试复盘、Research 派生条目与 Achievement 不作为 Raw。
- Wiki 当前对象使用 `current` kind `wiki_knowledge`，历史复用共享的 `revisions` 表。唯一语义类型为 `fact`、`observation`、`hypothesis`；状态为 `current` / `retired`。
- 新 Wiki 的来源只保存服务器核对过的 typed `source_refs`。空来源表示用户直接写入；provenance 固定为 `{"kind":"user"}`，不伪造 Raw。
- Scope 是 Project、Employment、Opportunity、已确认 Person、Personal 或 Cognition。Opportunity 来源只允许留在同一 Opportunity；Cognition 暂不接收 Opportunity 私有来源。

## HTTP 接口

- `POST /api/raw`、`GET /api/raw?scope_type=...&scope_id=...`、`GET /api/raw/{source_kind}/{source_id}?revision=...&hash=...`。带版本和 hash 打开来源时，若原件当前已变化则拒绝冒充旧正文。
- `GET /api/wiki?scope_type=...&scope_id=...&status=current|retired|all`。
- `GET /api/wiki/workspace?scope_type=...&scope_id=...` 返回一个范围的当前/退役知识和 Raw 来源目录。
- `POST /api/wiki` 新建；`POST /api/wiki/{id}` 编辑或退役；`GET /api/wiki/{id}/history` 查看共享 revision 历史。
- 新建/修改均要求 `idempotency_key`；修改同时要求 `expected_revision`。Raw 仅提供创建接口，不存在编辑或删除接口。

## 测试

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_wiki_d1.py
```
