# R01–R18 回归映射

本表是测试入口映射，不把历史测试总数当作完成条件。`CODE` 表示可在隔离仓库运行的 unit 或 API integration；`browser` 使用 `scripts/browser_regression.py` 和 `tests/fixtures/t12_browser_fixture.json`；`platform` 与 `real-provider` 只记录需要真实环境的验收，不用 mock 冒充通过。

| 要求 | CODE / API integration 真实测试 | browser | platform | real-provider |
| --- | --- | --- | --- | --- |
| R01 | `tests/test_resume_documents.py`, `tests/test_interview.py`, `tests/test_work_domain.py`, `tests/test_resume_pdf.py` | `scripts/browser_regression.py` | 真实 macOS 冷启动与恢复仍待最终验收 | 未调用真实 Provider |
| R02 | `tests/test_ai_operations.py`, `tests/test_applications.py`, `tests/test_editor.py`, `tests/test_interview.py` | `scripts/browser_regression.py` | 文件系统故障场景见最终清单 | 未调用真实 Provider |
| R03 | `tests/test_t10_backup.py`, `tests/test_backup.py`, `tests/test_migration_baseline.py` | — | 真实周任务/恢复读回仍待最终验收 | 不适用 |
| R04 | `tests/test_context.py`, `tests/test_outbound_policy.py`, `tests/test_t05_secret_config.py`, `tests/test_providers_artifacts.py` | — | 真实 Keychain 仍待最终验收 | 真实请求资料范围仍待最终验收 |
| R05 | `tests/test_local_runtime.py`, `tests/test_macos_app.py`, `tests/test_t11_pages.py` | `scripts/browser_regression.py` | Career.app / Chrome 完整链仍待最终验收 | 不适用 |
| R06 | `tests/test_context.py`, `tests/test_outbound_policy.py`, `tests/test_ai_enhancements.py` | — | — | 真实 Provider 质量与资料范围仍待最终验收 |
| R07 | `tests/test_t05_secret_config.py` | — | 真实 Keychain 仍待最终验收 | 不适用 |
| R08 | `tests/test_t05_secret_config.py`, `tests/test_outbound_policy.py` | — | 真实 Keychain/目的地组合仍待最终验收 | 真实连接仍待最终验收 |
| R09 | `tests/test_t05_secret_config.py`, `tests/test_providers_artifacts.py` | — | 真实 Keychain 生命周期仍待最终验收 | 真实 Provider 仍待最终验收 |
| R10 | `tests/test_local_runtime.py`, `tests/test_macos_app.py` | `scripts/browser_regression.py` | 冷启动、端口占用、PID 身份仍待最终验收 | 不适用 |
| R11 | `tests/test_t07_research_evidence.py`, `tests/test_research.py` | `scripts/browser_regression.py` | — | 真实 Research Provider 仍待最终验收 |
| R12 | `tests/test_t08_resume_suggestions.py`, `tests/test_resume_documents.py`, `tests/test_resume_pdf.py` | `scripts/browser_regression.py` | 真实 PDF 选择文字仍待最终验收 | 真实 Resume Provider 仍待最终验收 |
| R13 | `tests/test_context.py`, `tests/test_outbound_policy.py`, `tests/test_ai_operations.py` | — | — | 真实发送范围仍待最终验收 |
| R14 | `tests/test_ai_operations.py`, `tests/test_outbound_policy.py`, `tests/test_t08_resume_suggestions.py` | — | — | 真实 Provider 重试语义仍待最终验收 |
| R15 | `tests/test_local_runtime.py`, `tests/test_macos_app.py` | `scripts/browser_regression.py` | 个人本机无配对访问、跨站请求拒绝与启动器控制保护 | 不适用 |
| R16 | `tests/test_t10_backup.py`, `tests/test_backup.py` | — | 周任务、完整性、全新目录恢复和受控文件系统失败仍待最终验收 | 不适用 |
| R17 | `tests/test_interview.py`, `tests/test_journey.py`, `tests/test_t11_pages.py` | `scripts/browser_regression.py` | 真实用户链仍待最终验收 | 不适用 |
| R18 | `tests/test_t07_research_evidence.py`, `tests/test_t08_resume_suggestions.py`, `tests/test_t11_pages.py`, `tests/test_resume_pdf.py` | `scripts/browser_regression.py` | 真实平台链仍待最终验收 | 真实 AI 仍待最终验收 |

当前批次不修改原始 Review 文件；本表只链接当前仓库中可运行的证据入口，具体批次状态仍以 [STATUS](STATUS.md) 为准。
