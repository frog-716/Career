# Opportunity Enhancement Sprint — Sidebar / AI / Research

日期：2026-09-18（Asia/Shanghai）

## 范围

本轮在 schema v6 上完成三组增量，没有新增业务表或执行领域迁移：

- Sidebar 一级模块本地拖拽排序，顺序写入浏览器 `localStorage`，未知模块读取时忽略并将新模块追加。
- `ModelConfig` / `AISettings`、macOS Keychain `SecretStore`、OpenAI-compatible `ModelGateway`、最小真实连接测试和统一调用审计。
- Interview Real AI、结构化 Resume proposal、Company/Opportunity Research proposal；Simulation 在服务层、路由和 UI 均没有 Research Patch 能力。

## 已验证

- `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q`：160 passed。
- `npm --prefix frontend run typecheck`：通过。
- `npm --prefix frontend run build`：通过；保留既有大 chunk warning。
- `git diff --check`：通过。
- 新增定向测试覆盖 Key 不进入 DTO/SQLite/log 审计、默认模型删除、Resume proposal 确认边界、Research provenance、Provider 状态分类和 Gateway 选用配置：8 passed。
- 隔离浏览器 `127.0.0.1:8766` 实际观察到 Sidebar、AI 设置、Opportunity 岗位情报、手动 Research 写入、Resume “AI 优化当前稿”；无默认模型时 Web Research 返回失败提示且当前 Research 未变化。
- Production Chrome 实际完成 Sidebar 桌面拖拽：将“今天”拖到末尾后页面顺序改变，刷新后仍保持；随后已拖回默认顺序并再次刷新核对。后续按用户反馈改为拖动浮层 + 原位占位，拖动过程中不改变邻近入口颜色，顺序在松手时一次写入 localStorage；桌面拖动与移动端长按共用 Pointer Events。
- Production 已用真实 DeepSeek `deepseek-flash` 完成连接测试和一次 Resume “AI 优化当前稿”调用；返回结果先进入建议窗口，因当前演示稿为空而未接受写回，AI 未生成虚构经历。
- Production `127.0.0.1:8765` 备份后以当前源码重启；`GET /api/state` 核对 schema v6、`app_version=0.7.0-batch-f`、4 个机会和空 AI 配置；Production 设置页 smoke 通过，浏览器 console error/warning 为 0。

## Review 结论

- 规格轴：本轮已实现 Sidebar、AI-Config/SecretStore/ModelGateway、Interview/Resume/Research 的请求范围；提案型 AI 结果均先进入 pending，再由用户确认写回；Simulation 没有 Research Patch 路径。真实模型语义阶段因无用户配置保持待验。
- 规范轴：新增接口沿用现有 `Store`/revision/CAS 边界；Key 只经 SecretStore 读取，DTO、备份、审计和前端状态不返回原文；Research 与 Resume 均保留 provenance 且不直接覆盖当前事实。未发现需要在本轮继续修复的代码级阻塞。
- 未验部分：IAB 的原生 HTML5 拖拽事件仍不能稳定代表真实浏览器；Pointer Events 版本已在本地浏览器完成拖动—刷新—保持实测。真实 Provider 的长期质量、后台启动器问题仍按上节记录待后续处理。

## Secret / 数据边界

业务库仅保存 `api_key_ref`；API response 只返回 `api_key_set` 与 `••••••••`。Keychain 不可用时没有文件、SQLite、localStorage 或环境变量 fallback。ModelGateway 审计只保存 task/model/context reference/schema version/success/error，不保存 API Key 或完整 prompt/output。

## 未完成或未验收

- 当前真实 Provider 已完成连接与 Resume 建议调用；Interview FinalReview、Research Web proposal 及模型长期质量仍未完整验收。TestProvider 仅证明流程和边界。
- 本次检查时 Production 已没有 `ai_model_config`，`default_model_config_id` 为空，且对应 Keychain 项不存在；重新使用需在客户端填写新 Key。API 只返回 masked 状态，Key 不写入数据库、备份或日志。
- Production deploy 启动器的后台返回值曾与实际进程状态不一致；已改用前台 `scripts/run.py --port 8765 --no-browser` 保持当前 writer，并用 HTTP/浏览器复核。该启动器问题未扩展修复。
- 本轮未执行 Offer Comparison、云同步、Employment/Project 重构、复杂模型路由或 schema migration。

备份：`/Users/frog/Library/Application Support/Career Data-backups/career-backup-4c10d994-9198-466c-9c7f-d2a4768b83c4`。没有业务 POST、迁移或真实资料改写。
