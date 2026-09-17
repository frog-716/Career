# 职业事实闭环整改 · 2026-09-15

状态：本批人工事实闭环已完成并通过实际验收。用户已授权把剩余全流程修复完成；继续使用原工作树，保留已有改动。前批见 COLD-START-REPAIR.md。

## 用户结果和不变量

已确认事实 → 主动选入结构化简历 → 自由表达 → 固定版本/PDF → 机会投递 → 面试/研究/任职记录 → 更正或选段整理 → 待确认候选 → 用户确认事实。未确认记录不进分析；旧版本/投递不漂移。

## 固定 Interface / 实现范围

### C1 结构化编辑器选材与来源

- GET `/api/editor/materials?job_id=<可选>` → `{entries:[Wiki条目], profile:当前profile}`。只列active个人或指定job条目，不列episode。不自动选择。
- POST `/api/editor/select-facts`：`{expected_revision, idempotency_key, job_id?:string, selections:[{id,revision,section_type:skills|experience|projects|education}], include_profile:boolean, profile_revision?:number}` → 与GET editor同形 `{document,revision,savedAt}`。保存当前稿后调用；原子CAS，验证来源最新版，追加有稳定item ID的表达；不得重复导入当前仍有表达的同一source；删除表达后允许重新选材，原ref保留为removed历史；空选择拒绝。个人资料仅在structured模式时可以明确选入，保留来源revision。
- 来源放 `document.meta.source_refs` 数组，每项 `{item_id,source_kind:wiki_entry|profile,source_id,revision,hash,title,scope_type,scope_id}`。由服务产生；普通草稿保存必须保留现有refs，不允许伪造或修改；删除条目时保留来源历史也可。恢复版本恢复当时refs。
- GET `/api/editor/sources` → `{sources:[...ref,status:current|updated|withdrawn|removed]}`，只提示工作稿来源变化，不自动同步。
- 编辑器新增“从 Wiki 选材”和“材料来源”入口，先保存未保存稿；选择条目及分区、可选基础信息。409保留输入并提示重新载入。新稿响应替换当前稿、更新revision/savedSnapshot，保留撤销/恢复；不得把新稿状态丢进旧文字稿。
- 从机会链接携带 `?job_id=`；返回 `/#jobs/<id>?tab=resume`（主控主应用处理此hash）；全局返回 `/#resume`。job_id只限制选材/返回，不隐式创建用途或投递。

### C2 记录更正与候选回流

- notes仍不可变原话。新增当前 `journey_note_revision`（id=`note-revision:<note_id>`）经_save形成correction版本；GET journey返回notes附 `note_revision`（初始0）、`original_content`、`original_title`，正文/title采用当前更正视图。
- POST `/api/journey/notes/{id}/correct`：`{expected_revision,title,content,idempotency_key}` → 当前note读视图。CAS、幂等；原件不覆盖。
- GET `/api/journey/notes/{id}/history` → `{revisions:[{revision:0,title,content,created_at},...修订]}`。
- POST `/api/journey/notes/{id}/candidate`：`{expected_revision,title,content,entry_type,scope_type,scope_id,promote_to_personal:boolean,idempotency_key}` → 已创建pending candidate。同scope默认；仅明确promote_to_personal=true可提升到personal/空scope，其他跨任务拒绝。content是用户主动整理的允许复用文本；新knowledge_source只保存该选段（不复制整份任职私聊），`origin:{kind:'journey_note',id,revision,hash,scope_type,scope_id}`保留原记录来源。source和candidate同事务，候选已有resolve正常确认；不直接建Wiki、不bump当前事实epoch。
- note可带可选 `submission_id`，服务验证仅job scope且匹配同job application；更正不改变此历史引用。
- 导出工作期采用当前更正正文，同时明确原文/更正历史，不把改进答案冒充原回答。

### C3 基础资料归属与整理

- 新独立profile服务在同一个current profile里维护结构化基础信息（name/email/phone/wechat/github/links）；无第二正本。GET state保持旧字段content用于兼容读取，structured mode的content由字段生成。
- POST `/api/profile/basics` 保存basics+expected_revision，只允许空白旧profile或已structured；非空旧自由文本必须显式整理，不能默默丢弃。
- POST `/api/profile/organize`，CAS+幂等，保存当前旧profile原件，用户明确勾选迁移确认、填写基础字段、把其余经历/目标/约束整理为pending candidates；全部同事务，然后profile进入structured mode。旧原文保留，但不再作为第二个current_fact进入Context。
- 旧POST profile接口保留旧模式兼容；已structured后拒绝自由文本写回，防止重新形成重叠正本。
- UI基础资料只编辑身份/联系字段；尚未整理旧文本展示原文、进入显式整理。Wiki维护长期经历/目标/限制；TargetRole/周期是机会分类/求职计划，JD拥有具体招聘条件。不扩展domain元数据到Context、不造隐式事实优先级。

## 验收

本批先写失败测试再实现；覆盖47项基线回归、新增来源版本/CAS/跨scope/候选不进Context测试和真实浏览器全链路。隔离数据实际重启/哈希回读；最后备份正式数据、重启8765、核对新构建和数据不变。普通记录修订不自动改Wiki，用户确认的候选才进入可信Context。无真实AI质量完成承诺。


## 实施裁决与交付

C1/C2/C3采用上述增量接口，沿用同一Store及既有来源/候选/Wiki/application对象，没有新增平行简历或投递状态。资料归属决策已修订产品及Context权威文档。UI拆为profile-ui/record-ui，统一服务于所在业务页与聚合阅读页。

独立审查提出删除表达后重选会保留两个来源引用；主控裁决保留这一行为：旧ref标为removed，新的当前表达另有来源ref，只有仍存在表达时禁止重复导入。契约及回归测试明确此生命周期。浏览器发现的首次导入CAS时序问题已修复：先flushSave再构建请求；空白稿及未保存稿均实测通过。来源refs在撤销/重做和冲突保存时保留服务端历史，恢复正式版本则使用冻结版本refs。

规格轴：确认事实→表达→固定版本→机会→投递→面试复盘→候选→确认→下一轮选材实际完成；任职默认同scope、显式提升、原话/更正区分、Profile单一归属均满足。聚合页不添加重复创建功能，无Timeline。

规范轴：57项后端测试、typecheck/build及diff检查通过；CAS/幂等、跨scope拒绝、来源防伪、快照/PDF冻结、历史兼容、真实TestProvider输入隔离均有证据。进程实际重启，业务表与附件摘要不变。正式8765已备份更新，新入口资源与构建一致，未自动迁移或写入真实资料。

完整运行证据统一见 [EVIDENCE](EVIDENCE.md#事实闭环整改2026-09-15)。实际AI质量、自动提取、结构化AI建议、语音和搜岗均未纳入本批人工闭环成功声明。

后续联系方式修订：basics可选wechat/github/links（至多10条label/url），旧三字段客户端写入保留已有扩展字段。显式重选基础资料可更新当前表达与profile来源ref，旧draft revision/正式版本仍保留历史。基础表单不再缓存跨页输入或显示版本号。
