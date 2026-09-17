# 任务工作台首试批次

状态：手动任务工作台主路径已实际验收并更新本地正式服务，可开始试用；完整AI链路未完成。产品正本见 01-product，资料规则见 02-context-contract；本文件只记录本批接口与验收。

用户结果：今天看到下一步；岗位卡保存阶段、下一行动与日期；在岗位内记录研究、沟通、面试、Offer；独立工作期沉淀事务/协作/收获；材料页进入原版简历并查看本地版本；全局反馈不打断编辑。没有接入的 AI/搜岗/语音明确说明，不能用预置分析伪装。

## 本批接口

新增 `journey_router(store)`，复用现有 SQLite 和备份，无 schema 变更，不改 Context 白名单。

- GET /api/journey → {plans:[], episodes:[], notes:[]}，只读。
- POST /api/journey/plans/{job_id} → 最新 plan。body: {stage,next_action,due_date,expected_revision}；stage ∈ screening,research,resume,outreach,applied,interview,offer,closed；due_date 为空或 YYYY-MM-DD。plan.id = journey:<job_id>，revision 初始 0；岗位必须存在且 active 才可更新。不把人为设置阶段伪装成实际投递事件。
- POST /api/journey/episodes → 工作卡。body: {company,role,start_date,end_date,focus}，company/role 必填，日期允许空，end 不早于 start。返回 {id,revision,company,role,start_date,end_date,focus,created_at,updated_at}。
- POST /api/journey/episodes/{id} → 更新同字段 + expected_revision。
- GET /api/journey/episodes/{id}/export → Markdown附件，按时间输出该工作期与原话记录，标记“用户记录汇编（非 AI 总结）”；只读，不另建资料正本。
- POST /api/journey/notes → 记录。body: {scope_type,scope_id,kind,title,content,idempotency_key}；scope_type=job|episode；kind=research|communication|interview|offer|action|collaboration|reflection；目标必须存在。content 保留原话和空白，非空、<=100000字符；title<=500。存为不可变原始手动记录；同key同body返回原记录，异body409。返回id/created_at和原字段。只记录，不调用AI、不发送消息，不自动进入个人事实或求职分析。

所有变更继承同源保护。422格式错误、404目标缺失、409旧revision冲突；失败不清输入。UI冲突必须保留输入并提供最新值比较后显式重存。暂不做notes修改/删除，允许追加更正。

## 前端交付约束

导航：今天、正在推进、我的材料、工作阶段、练习与收获、足迹；个人资料从材料进入，反馈独立可达，诊断次要。首页去掉营销球体，突出真实下一行动/日期、继续任务、快捷记录。岗位详情以阶段与下一步为首，JD编辑收进展开区，研究/沟通/面试/Offer作为真实可保存笔记；保留岗位分析入口和状态删除/恢复。阶段不强制顺序。工作卡可新建编辑、追加具体事务/协作/收获。练习页聚合已有面试和复盘，明确语音未接入。足迹聚合真实记录，不生成样例。材料显示独立编辑器版本及PDF引用（GET /api/editor/versions），旧文本草稿入口保持次要。正文不要展示数据库ID/内部任务枚举。所有新界面转义内容、错误保留输入、禁止native prompt。

## 验收

后端测试岗位隔离/不存在scope/旧revision409/日期校验/重试幂等/手动笔记不进入实际Context/重新打开Store持久化；回归旧编辑器与Context测试。浏览器用隔离虚构资料实际新增岗位→更新阶段/下一步→保存研究笔记→新建工作卡→追加阶段收获→反馈→刷新重读，并检查正式空状态与布局。构建通过不能替代该路径。

## 实际验收（2026-09-14）

- 实际运行 `PYTHONPATH=src .venv/bin/pytest tests -q`：34 passed；TypeScript/Vite build通过，`git diff --check`通过。PDF依赖包仍有大于500kB构建提醒，不影响结果；未为此改原版编辑器。
- 后端覆盖：无效类型/日期422、任务scope、旧revision409、排除岗位不能更新计划、并发同key只存一条笔记、同key异body409、GET只读、整库备份在新目录恢复。实际TestProvider的完整payload不含工作期/协作/岗位笔记sentinel，也不含被替换个人资料旧值。
- 隔离服务使用 `CAREER_DATA_DIR=/tmp/career-task-workspace-check`、`CAREER_AI_PROVIDER=test`、端口8766。浏览器新增虚构岗位，保存研究阶段/下一行动/日期，追加带首尾空白的研究记录并实际回显。
- 新建虚构工作卡，编辑阶段重点；在未保存编辑表单内打开反馈，保存带空白的反馈后原编辑表单和输入保留，继续保存工作卡成功。反馈记录关联该episode_id，不采集工作卡正文。
- 用独立HTTP写入制造真实并发：工作卡后台revision2，浏览器旧revision1保存显示409和两份中文内容；选择基于最新版本继续编辑、人工合并、保存成为revision3。没有静默覆盖。
- 追加阶段收获，在“练习与收获”中实际出现；服务停止重启为新进程后，工作卡、收获和首页下一行动仍能回读。
- 计划编辑后清空日期，切换正在推进再返回，输入和空日期完整保留并成功保存。
- 阶段导出最初Blob下载事件无法从内置浏览器得到可靠完成信号，主控改为本地HTTP附件接口。实际浏览器触发下载；HTTP200、attachment header及UTF-8内容验证通过，384bytes样本保存 `/tmp/career-task-workspace-check/stage-export.md`，包含阶段原话。未宣称浏览器最终下载路径已核验。
- 材料页实际读到 `{versions:[]}` 并渲染name/createdAt/artifact_id；为有版本场景，通过API将上一批已生成的虚构文档与对应真实PDF导入本轮隔离目录，浏览器显示正确版本及PDF链接。不是复制真实线上简历，也不是新一轮PDF生成验收。
- 实际浏览器检查窄窗口页面：深绿导航、主任务、阶段工作卡无横向表单挤压；材料页可进入个人资料与独立纸面编辑器。原版editor文件本轮未修改。

## 两轴审查与修正

规格轴：纠正首次强迫填资料、岗位阶段显示内部枚举、重复一级导航、工作卡没有编辑入口、材料版本字段错配/列表崩溃、记录反馈按钮仅导航、笔记没有工作期说明。前端现在用任务组织，未接入的搜岗/公司研究/语音和纸面AI明确说明。

规范轴审查发现并处理plan输入丢失、note重试换key、工作卡409无法恢复、反馈替换原弹窗、集合非法类型500、来源白名单测试不充分。随后实现嵌套弹窗保留、编辑冲突内联比较、notes固定请求/冻结重试；卡片写入成功但刷新失败时锁定已保存输入并仅重试刷新，避免二次创建或丢掉后续输入。没有把构建结果当成主链完成。

## 正式服务与剩余限制

正式入口 `http://127.0.0.1:8765/#home`，更新前备份为 `~/Library/Application Support/CareerOS-backups/career-backup-54e01863-0eff-4dc5-bfcc-1fe2da9e48cc`。实际重启进程75278并打开正式首页；原有岗位保留，新journey模块初始没有记录。本轮虚构资料只写隔离目录，没有云端写入/发布。

首试可用：手动资料、手动岗位、计划与下一步、原话记录、工作卡编辑/阶段导出、独立原版简历和本地版本/PDF入口、反馈。资料仍为自由文本整体；自动分条和任务选材未实现。工作阶段暂为卡片和文字记录，没有事项完成状态/独立StageDocument对象，也没有领导同事专用建模界面。notes追加不可改，允许追加更正。

完整方案已在01/02/03/05/07唯一所属文档修订，但真实AI仍未配置；实际模型、自动搜岗、联网公司研究、聊天补救、文件上传解析、语音/录音复盘、Offer智能比较、结构化简历AI及岗位版本回传均未验收或未实现。当前人工记录不能作为这些能力完成的证据。全部记录目前整批读取，需后续按实际规模分页；前端仍是轻量vanilla实现，尚未完成所有目标深模块拆分。
