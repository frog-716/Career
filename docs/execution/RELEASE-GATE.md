# Release Gate Reconciliation

日期：2026-09-20

目标发布模式：`CAREER_AI_MODE=LOCAL_ONLY`。本次只整理证据，不修改源码、不进入 Stage 3；当前计划身份不变：`career-cutover-20260920-stage25-resume-template-e2dcd25c` / `a4dc6c46fab037bb17303439773285d2709bfc379839549aed0f5c5548a0a26e`。

## A：Stage 3 前真正硬阻断

当前无已证实的 A 类阻断。

`LOCAL_ONLY` 已有直接边界证据：生产样式 `ModelConfig/secret_ref`、假 Key、四条 AI 路径和 Research 均被拒绝；Secret access 和网络 trap 均为 `0`；人工编辑、机会、简历/PDF、备份恢复继续可用。当前没有证据表明正式数据会损坏、候选版无法启动、无法回滚、LOCAL_ONLY 会出站，或核心非 AI 用户链已知不可用。

## B：Stage 3 执行中必须通过，失败立即回滚/停止

- Python：固定 `3.12.14` Candidate 已真实运行通过；正式 `3.9.6` 不得继续承载新版本。Stage 3 中切换 App/LaunchAgent/周任务到固定环境并核验，失败回滚旧运行组合。
- App：Candidate 冷启动、连续打开、未知端口拒绝、正常停止、PID/实例身份测试已通过。正式切换时仍须重新核验正式 PID、启动时间、build/data identity、端口释放和不误杀；身份不完整即停止。
- 数据：Stage 2 恢复点的 manifest、SQLite、附件 hash、恢复已通过；Stage 3 停写后必须新建最新即时恢复点，验证失败不切换，不用旧演练点覆盖新数据。
- Chrome/核心链：Candidate 已完成配对、刷新、退出/重配对、四导航及机会/面试/简历/任职入口。尚缺正式切换后的只读 smoke、完整机会→面试→简历→投递连续链和全部未保存分支；这些是执行中检查，发现核心链失败立即回滚，不构成当前已知不可用。
- 切换默认只读，用户确认前不开放正常业务写入；真实周任务属于 Stage 4 受控验证，不做破坏性演练。

## C：仅 `AI_ENABLED` 需要

- 真实 Keychain 写入/读取/替换/删除与拒绝/锁定场景。
- 真实 Provider、真实 Research web search 和收费 smoke。

这些不阻塞 `LOCAL_ONLY`；LOCAL_ONLY 必须继续保持 Keychain access `0`、Provider outbound `0`、Research outbound `0`。

## D：非当前发布阻断 / 后续事项

- PDF：技术文字层、`pypdf` 提取、冻结一致性、视觉回归已通过；本次解锁后 Preview 选择并复制，TextEdit 实际粘贴为“虚构星河科技 / 高级产品经理 2023年07月—2025年06月”。不再阻塞 LOCAL_ONLY。
- T11：1000 条虚构机会已有 API 与浏览器规模证据；缺少更完整分页/性能结论属于后续 UX/规模验收，不是当前数据安全或核心可用性阻断。
- Starlette 残余 advisory（`pip-audit` exit `1` 不单独等于发布阻断）：`PYSEC-2026-1941`（无 `form`/`UploadFile` 路径）、`PYSEC-2026-2281`（Windows UNC，目标为 macOS/POSIX）、`PYSEC-2026-2280`（无 `HTTPEndpoint`）和 `PYSEC-2026-249`（无 `request.form`）当前不适用；`PYSEC-2026-1942`（Range）和 `PYSEC-2026-161`（Host/path）属于历史 A，已有进入 Starlette 前的拒绝与直接回归测试；`PYSEC-2026-248`（非 `/` 路径重建）当前鉴权使用 ASGI scope path，已有边界约束。当前无证据表明这些 advisory 在本发布模式下仍可触发；保留供应链残余风险，发布前重查兼容升级，不使用 `--ignore-vuln`。
- 正式平台迁移、真实周任务完整性、完整生产恢复和受控文件系统失败：按切换/Stage 4 计划执行，不提前破坏正式环境。
- 无法核实 Subagent 实际 `Luna/High`：属于证据质量限制，不是产品发布阻断；本轮不计独立 Agent 审查。

## 当前结论

已具备“请求 `LOCAL_ONLY` Stage 3”的条件，但不等于已获准执行或 `MERGE_READY`。下一步若用户授权，只能按 B 类检查、最新即时恢复点和明确回滚步骤执行；本轮不发起授权、不进入 Stage 3。
