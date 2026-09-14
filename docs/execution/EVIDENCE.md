# MVP 运行证据

2026-09-14。仅使用 `fixtures/scenarios.json` 虚构资料；不读取旧项目/旧线程/真实职业资料。数据在代码外临时目录。本文记录验收证据，当前计划与状态仅见 STATUS。

## 工具链与协作

初始 `python3 -B scripts/verify_bundle.py`：PASS，28 payload files。初始非 Git 仓库，已初始化；Python 3.9.6、Node v22.23.2、npm 10.9.8。Python direct+transitive 依赖固定于 requirements.lock，前端依赖由 package-lock.json 固定。

后台工具显式接受 gpt-5.6-luna / medium。已收到 Provider/Artifact、初版 frontend、独立 review 的结果。初版 frontend 自报存在投递缺项，主控未视为完成；旧执行者不再出现在当前宿主可调度列表后，已重派 frontend_finish。宿主可能显示 Subagent 聊天面板；没有调用 create_thread，没有额外分支/worktree。主控实际模型/reasoning 无运行配置可读，无法核验。

## 自动化验证

`PYTHONPATH=src .venv/bin/pytest tests -q`：21 passed（本轮恢复后实际复验）。

- Context：旧事实修订后实际 Provider payload 只含新资料；不会混入反馈；只有 fresh system/user messages。非法来源引用会失败且不改正本。
- Revision：旧 expected_revision 返回冲突；分析中修改资料结果 stale；预览后更改资料拒绝发送；手改简历让待应用提案 stale。
- Proposal：确认后同事务写草稿与 applied_result，重复应用不重复修改；并发手改不会被旧提案覆盖。
- History：正式版本与实际 PDF 独立保存；投递关联岗位/版本/PDF并保存事件快照，后续资料/草稿/岗位删除不会修改事件。错配岗位/版本拒绝。
- Idempotency：同一分析 key 只调用一次 Provider；同一投递 key 只生成一次事件；并发PDF导出返回同一 artifact且只保留一文件。
- Feedback：原话包括空白不变、补充追加、JSON/Markdown 导出；不会进入 Context。
- Local：Origin/Host/自定义写入 header 限制；新 Store 读取已存对象；SQLite 快照备份后在新隔离目录恢复，PDF字节一致。
- Provider：未配置真实模式仍能启动和手动编辑，调用返回503并记录失败；Real adapter请求体通过模拟HTTP client捕获，无真实模型调用。

关键 TDD 证据：core 未实现时测试 collection失败；新增重复分析/并发PDF测试时2 failed；反馈原文空白测试1 failed。实施后相应测试通过。不是仅靠静态代码宣称正确。

`python -m compileall -q src scripts/run.py scripts/backup.py`：通过。

## 两轴审查

规格轴已处理：Provider返回格式错配；默认未配置影响独立手动链；JD不应写成本人简历事实；反馈原文被strip；简历后续编辑导致旧提案不可应用却未显示过期；初版前端缺投递表单/正确预览。最后一项仍在前端验收中。

工程轴已处理：重复分析会重复收费调用；并发PDF重复文件；字体fallback缓存后续失败；artifact根目录symlink逃逸；实际请求无旧会话；缺密钥错误脱敏。初版 frontend 自报构建不能证明完整主链，已要求重做表单/冲突处理后实测。

## 浏览器与实际文件

隔离服务 `CAREER_AI_PROVIDER=test CAREER_DATA_DIR=/tmp/career-os-mvp-browser .venv/bin/python scripts/run.py --port 8766 --no-browser`。实际浏览器已打开首页、填写 fixtures 个人资料并保存，页面显示 revision 1。其余主链与PDF视觉待新版前端整合后记录。

## 真实能力边界

未检测到 CAREER_AI_API_KEY / OPENAI_API_KEY / CAREER_AI_MODEL。真实岗位分析与真实简历适配尚未验收；TestProvider只证明流程与隔离。不得称真实AI闭环完成。配置步骤位于 src/workbench/README.md。

## 最终整合验收（18:37–18:45）

前端已由主控完成交互整合，Luna 完成样式并作只读审查。`npm --prefix frontend run typecheck` 与 `npm --prefix frontend run build` 实际通过；Vite 6.4.3 构建本地静态资源。未加载远端字体。页面浏览器 console error/warn 检查为空。

实际浏览器操作：

1. 个人资料保存并显示 revision 1；表单添加虚构公司甲 JD。
2. 岗位分析先展示 taskKind=job、profile/JD revision 1 和完整 sources，再点击测试模式发送，返回 job 字段与可展开实际 payload。
3. 从岗位进入独立草稿，taskKind=resume 也先预览；提案返回后工作稿仍空，查看 before/after、确认应用后变为版本1，正本不变。
4. 人工编辑成简历格式，后台自动保存为版本2；编辑时打开全局反馈，保存反馈后仍停留简历且正文不丢。
5. 保存正式版本并实际生成 PDF（32636 bytes、1页 A4）。`pdfinfo` 读取成功，`pdftoppm -scale-to 1200 -png -singlefile` 渲染后主控查看图片，中文清晰无黑块/裁切。macOS Preview 实际打开 PDF，AX 文本与所保存的简历正文一致。
6. PDF 内置浏览器预览失败，因此增加下载兼容入口。浏览器实际触发 PDF download；HTTP 验证 Content-Disposition=attachment，文件以 %PDF 开头，哈希与登记一致。
7. 从该版本打开投递表单，确认岗位、正式版本、PDF、正常日期时间控件和中文状态，保存实际投递事件，更新状态为“面试中”。此为虚构验收事件，未执行任何对外投递。
8. 反馈页显示原话，追加说明后两者并列保留；JSON 和 Markdown 均触发浏览器 download。另用测试 PDF 的渲染图片作为可选截图上传，保存后出现可访问的截图链接。
9. 双窗口同时打开 profile revision1：第二窗口先保存 revision2，旧窗口再保存时出现“你的未保存内容 / 服务器当前内容”差异，内容未丢。显式基于最新版本继续编辑，合并后保存 revision3。
10. 添加虚构公司乙并进入简历，显示版本0空稿且无甲公司的投递。切回甲时原稿和投递恢复。删除甲岗位后其退出活动列表，仍可查看历史简历/PDF/面试中状态，分析按钮禁用。

实际进程重启：停止测试/生产进程 65452/65776，重新启动为66894/66895。重启前将合成状态保存到隔离目录；重启后比较 profile/jobs/resumes/versions/artifacts/applications/feedback/runs 全部相同，所有附件 HTTP 字节 SHA-256 与登记一致。浏览器重载后读取工作稿版本2、正式版本、历史 PDF、面试中状态，个人资料更新导致旧分析明确显示过期。

生产入口 8765 已实际启动并打开首页：当前资料为空、岗位/投递为0、显示“真实 AI · 未配置”。没有写入测试样例。生产与测试目录不同。

最终回归：`npm --prefix frontend run typecheck`、`npm --prefix frontend run build`、`.venv/bin/pytest -q` 均通过，后者21 passed。后续仅增加了导航恢复及保存串行化的小修复，重新typecheck/build通过。真实模型从未调用，保留外部配置 Gate。

最终两轴结论：当前 MVP 独立能力符合预览/确认/不改历史/反馈隔离要求；工程关键数据和文件路径已通过测试及浏览器验证。当前局限集中记录 STATUS，未以任职、语音、自动采集等未来功能充数。
