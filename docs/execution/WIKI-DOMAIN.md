# 职业 Wiki 与业务对象整合

状态：本轮手工 Wiki 与对象引用增量已验收，正式入口已更新。用户最新材料（2026-09-14）被吸收为目标模型；完整目标尚未全部实现。

本轮用户结果：文本原始资料留存 → 手工整理候选 → 确认进 Wiki → 修改/撤回形成 revision → 按机会明确选取最新 Wiki → 预览并发送实际分析。项目/目标/约束/能力等用独立条目；项目可关联任职。机会保持原 job ID，任职保持原 episode ID。独立简历正式版本可明确引用到机会，不改原工作台和已导出 PDF。

接口冻结（后台 Sol 执行 knowledge.py 与 tests/test_knowledge.py；主控负责其余整合）：

- `GET /api/knowledge` → `{sources:[], candidates:[], entries:[]}`。
- `POST /api/knowledge/sources` → immutable `{id,title,content,source_type:'text'|'document'|'local_repository'|'git_repository'|'url', locator:'', scope_type:'personal'|'job'|'episode',scope_id:'',created_at}`；body 同字段 + idempotency_key。locator 只登记，绝不自动读路径或出网；文本不trim。
- `POST /api/knowledge/candidates` body `{source_ids:[],entry_type,title,content,scope_type,scope_id,expected_revision?,idempotency_key}`；候选 current，状态 pending，初始 revision1。entry_type ∈ goal,constraint,experience,capability,project,achievement,person,growth,strategy。目标范围必须与每个 source 完全一致，拒绝未显式提升的跨范围材料。
- `POST /api/knowledge/candidates/{id}` body 同候选字段 + expected_revision + idempotency_key；仅 pending 可编辑。
- `POST /api/knowledge/candidates/{id}/resolve` `{decision:'confirm'|'reject',expected_revision,idempotency_key}`，事务内确认创建 wiki_entry 并记录 candidate entry_id；重复 key 同请求回原结果，不同请求409。拒绝不创建条目。API 返回 candidate（含 entry_id）。
- `POST /api/knowledge/entries/{id}` `{title,content,entry_type,status:'active'|'withdrawn',expected_revision}`；scope 不变；source_ids 可显式替换为同 scope 来源并形成修订；更新 bump epoch；修改不自称已核验。
- `GET /api/knowledge/entries/{id}/history` → `{revisions:[]}`，只供查看，不进分析。
- `selected_wiki_sources(store,c,ids,job_id)` 返回 packet source 数组，形状 `{id,revision,hash,purpose:'current_fact'|'task_context',content:{title,entry_type,content,scope_type,scope_id},source_ids:[]}`。只接受 active、personal 或该job 范围；episode 一律拒绝。本轮个人 goal/constraint 默认必选，其他 ids 明确选择，最多30条/正文总量100k，超限报422不静默截断；不读 raw/candidate/history。默认 ids=None 仅 mandatory，无其它隐式加载。

所有 source/candidate 创建及 resolve 有幂等指纹；current/revisions/records复用 schema v1；数据更新事务 CAS；个人/机会/任职范围校验实体存在；Source 非文本路径不会执行。知识录入和候选不 bump，Wiki确认/修改/撤回 bump，使旧分析失效。候选仅是人工整理，本轮不假装 AI 提取已接通。

主控增加：context/analysis body wiki_ids 显式选材；旧 profile 保持单一独立基础资料正本，不复制到 Wiki；支持仅 Wiki 无 profile 的分析；未选来源不加载。UI 保持上一批极简固定视口，新导航为今天、职业 Wiki、求职机会、简历工作台、任职、复盘；Wiki内原始资料/待确认/Wiki、项目作为类别；scope清晰。机会资料选材、独立简历版本引用及任职内关联材料入口真实落库。

测试：原件不可改，未确认/拒绝/旧revision/他人任务/任职私聊不进packet；确认幂等与冲突、修改失效、explicit选择；引用独立版本不修改其PDF。主控完成隔离浏览器路径与本地备份后运行更新。

## 主控验收与审查记录（2026-09-14）

- 主控运行 `PYTHONPATH=src .venv/bin/pytest tests -q`：44 passed；`npm run typecheck` 与 `npm run build` 通过。未调用真实模型。
- 隔离服务 8766 使用 `/tmp/career-task-workspace-check`、TestProvider；生产数据未加入本批测试材料。实际浏览器走通原始文本 → 人工候选 → 确认 Wiki → v2 修订 → 机会选材 → 预览 → 显式发送。实际 payload 有 v2，不含原始未核实数字或旧版正文；原件首尾空白保留。
- 浏览器创建虚构公司、事业部、下级团队、目标方向，再关联同一个原 job ID；机会显示完整组织路径。后端测试拒绝跨公司组织、循环层级与错误 revision。
- 浏览器从机会简历页引用现有正式版本；实际下载接口返回 87656 bytes PDF，SHA256 与冻结用途记录一致，applications 仍为空，没有自动登记投递。
- 独立 Sol medium 审查指出跨 taskKind 继承选材、归档岗位冷启动筛选不一致、接口文档来源修订说明过期；主控修复为每轮非必选项均重新选择、深链同步筛选、文档与同 scope 来源修订一致。主控另修复候选确认重试 key 和来源标签。
- 审查关于 TestProvider 简历输出忽略 JD 的发现：实际 payload 完整包含当前 JD 和 task_context；确定性输出刻意只回显个人资料，不能用于证明岗位适配。维持此防串料测试模板，明确不认定为真实 AI/岗位适配验收。
- 更新前完成生产备份：`~/Library/Application Support/CareerOS-backups/career-backup-361814e3-73b1-41ac-a413-db6f890b06af`。审查者误运行构建写了 dist；主控发现后完成备份并切换匹配后端，随后重建最终前端。没有变更 schema version 或清空数据。

## 当前边界

最终构建浏览器检查：Wiki 白灰分栏、固定视口；628×771 窗口 document 尺寸与 viewport 一致。新一轮分析不继承上轮勾选。正式服务 8765 的 knowledge/domain 接口与 Wiki 页面实际回读通过；未在正式空间创建本轮测试对象。生产进程更新为 PID 82469，使用原数据目录。

生产 1280×720 视口也无文档层溢出；数据库逐行对比更新前备份：current 5、revisions 11、records 0 全部不变。测试服务与本轮测试页已关闭，正式 Wiki 页面保留。

文本/文档摘录能留存，文件路径/Git/URL 只登记，尚未自动读取、解析或上传。候选目前人工整理。项目与人物已有 Wiki 类型及同 scope 多来源，但项目参与者多对多、独立 Stage、Problem、EvidenceLink 定位仍是目标架构。简历当前仍为一个可编辑工作稿加不可变版本；版本用途可关联方向/机会，不等于多个独立 ResumeDocument 或实际 Submission。公司目录说明不自动进 AI。
