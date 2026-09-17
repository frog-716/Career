# Opportunity Batch B — 机会正本与管线计划

状态：已按用户确认的计划和两项调整完成 workbench-implement → workbench-review；**Batch B 隔离验收通过，未执行 Production Cutover**。源码交付在独立 worktree，生产 0.2.0 / schema v1 保持；本批完成后停止，不进入 C。实际证据与限制见 §11。

## 1. 目标、依据与用户可观察结果

将Job、Opportunity复制行和JourneyPlan分散承载的当前机会信息与状态，收敛到唯一canonical Opportunity。交付最小闭环：**创建 → 管线查看 → 单机会Workspace → 编辑机会信息 → 明确结束 → 历史仍可读**。不以四阶段展示声称已经完成四阶段全部业务动作。

依据[authority](../00-authority.md)、[Product](../target/opportunity/opportunity-product-model.md) §0–2/7–10、[Domain](../target/opportunity/opportunity-domain-model.md) §1–2/15–20、[UI Flow](../target/opportunity/opportunity-ui-flow.md) §1/17–20、[Context & Ingestion](../target/opportunity/context-ingestion.md)；对照[Gap Analysis](../audit/OPPORTUNITY-GAP-ANALYSIS.md) §2–5/7/8 Batch B及§9。跨模块约束采用当前[Acceptance](../05-acceptance.md)、[Architecture](../03-architecture.md)、[Context Contract](../02-context-contract.md)、[Journey](../04-journeys.md)、[Roadmap](../07-roadmap.md)。这些是目标或约束，不是已有实现证据。

用户将能：

1. 输入公司、岗位、JD及可选链接创建一次尝试；默认“写简历＋active”，不要求简历、方向、组织、周期或AI。
2. 在“全部 / 写简历 / 已投递 / 面试 / Offer / 已结束”六个View查看公司、岗位、阶段、阶段日期；整行进入Workspace，返回保留筛选。
3. 在稳定顶部读取同一个后端状态；修改岗位/JD/链接或明确更换公司，冲突时保留输入；退出/被拒后进入已结束，最后阶段保持。
4. 对已有且经过明确核对的Offer阶段机会记录accepted；接受条件由后端检查，不创建Employment。
5. 继续打开旧Job URL、旧投递/PDF/活动/资料引用。未能可靠映射的旧记录以“历史资料，状态待核对”只读呈现，不消失，不随机放进四阶段或已结束。

**本批隔离v2可用性边界**：新机会的前向推进动作由C/E/F分别交付，B不提供通用“选一个phase”按钮，也不以旧note创建冒充确认真实面试/收到Offer。当前阶段区域可以说明后续能力尚未接入，但不呈现虚假的可执行按钮。旧投递/面试/Offer的新建入口在schema v2上按§6受控暂停；已存在的材料读取和幂等回放保留。这是本计划明确披露的兼容期限制，不等于完整MVP主链已替换；这些限制只作用于隔离v2；正式生产继续v1，保持原投递、面试、Offer写能力。Production Cutover为后续显式授权的部署动作，不在本批执行。

## 2. 已核对基线与证据等级

### 2.1 Batch A证据

已读取[Batch A记录](OPPORTUNITY-BATCH-A.md)与私有目录`/Users/frog/Library/Application Support/Career Migration Audits/batch-a-20260917T114422Z`中的`batch-a-manifest.json`、`restored-final.json`等；manifest所列16份证据文件SHA256均复核一致。计划补充检查使用备份SQLite的`mode=ro + query_only + BEGIN`，没有初始化Store或读取生产正文。

| Verified by Batch A evidence / 本轮只读复核 | 对B的含义 |
| --- | --- |
| A记录运行0.2.0、生产目录`~/Library/Application Support/Career Data`，备份目录为其同级`Career Data-backups/batch-a-20260917T114422Z` | 这是A的时间点证据；B执行窗口必须重新核对运行代码/路径，不能沿用为实时承诺 |
| schema v1，meta 1/current 24/records 27/applications 1/revisions 146；恢复199行和1份PDF一致 | 迁移前后保护集合包含全部表，不能只导出新机会字段 |
| 2个Job、1个materialized Opportunity、2个JourneyPlan、1个opportunity_context、1个Company | 不存在可直接改名即完成的唯一正本；第二个Opportunity现在仅是读投影 |
| 两个Job与对应Opportunity候选的title/JD/url/status无值差异 | 可提出信息字段复制候选；不证明phase/result或公司关系已确认 |
| 未带demo标记的Job：status=active、plan.stage=resume、无company_id且无精确Company名称匹配 | 名称可成为创建Company的候选依据；旧active/resume只是线索，不证明真实求职状态，也不证明该记录是真实用户业务 |
| demo Job公司文字与已关联Company.name不同；plan=interview、application.status=applied且有Offer记录 | G1/G2按demo/legacy兼容保留，不选“最新值”或“最大阶段” |
| demo application.applied_at为2026-03-20，而Job创建于2026-09-15 | 日期并非可靠一致的阶段时间线；不能把导入/案例创建日或这个投递日自动设为当前phase日期 |
| research_snapshot/communication/interview/offer各1条，均为demo；typed分别关联既有Raw/note | ID与材料完整保留；有typed对象不等于目标真实轮次/当前Offer能力已完成 |
| 多Submission=0、多Offer=0；A报告migration_gates为空 | 说明安全盘点当时无所列用户Gate，不代表B业务字段映射全部已获确认 |
| 2个ResumeUse，其中未标记项引用demo版本/PDF/方向 | 不重归属、不清理；尤其不能让demo/remove破坏跨数据集引用 |

### 2.2 Verified by code（规划时的 v1 基线，不是实施后现状）

- `core.py:save_job/_save_job_in_transaction`写Job后调用`opportunity.sync_job`；`save_opportunity`反过来修改Job，仍是双写。
- `opportunity.current_opportunities`对缺行Job做内存投影；`core.record_application`会在缺Opportunity时调用sync_job补写，是必须封闭的旁路。
- `domain.assign`独立写opportunity_context.company_id；`journey.save_plan`写stage。实际demo plan ID为`demo-b5-plan`，不能假设全部plan ID都是`journey:<job_id>`。
- `application_status`独立修改applied/interviewing/rejected/offer/closed；`engagement.create_activity`及`journey.create_note`可建typed活动，但没有目标phase/result联动或real/simulation。
- `demo._load_dataset`直接写Job/Opportunity/plan；不能只封HTTP机会接口而留下导入旁路。
- `workspace.ts`以jobs、job.status、plan.stage/due_date及评估/用途/投递有无推导界面；`main.ts`仍向/jobs、journey/plans、applications/status写入。旧hash路由会在ID失效时回退第一条机会，需要替换为显式不存在/历史结果，避免串看。
- `ContextCompiler`直接取Job与opportunity_context；editor/knowledge若干scope校验也直接取Job。B需适配身份读取，但不因此改简历所有权或Raw政策。

上述规划基线采集时未运行测试、前端构建、浏览器业务操作、生产重启或迁移。A的9项通过及两项旧profile失败只作已有基线，不计为B验收。

## 3. Domain不变量与最小模型

### 3.1 存储取舍

**继续使用current JSON模型，不新建Company/Opportunity/JobPosting/Timeline表，不换ORM。** Company复用`current.kind=domain_company`，canonical Opportunity复用`current.kind=opportunity`。旧Job/plan/context行保留历史用途；已迁移机会的当前读只读canonical，绝不fallback到旧Job覆盖新值。

即使没有业务表DDL，也要将**数据库user_version从1显式升到2**：JSON领域语义不再与旧写代码兼容，需要旧程序拒绝打开。备份manifest的`schemaVersion=1`是既有包格式，不与数据库user_version混为一谈；B工具需明确报告两者，支持v1/v2各自的完整性检查。迁移不由Store启动自动执行。

### 3.2 Canonical Opportunity字段（计划Interface）

| 字段 | 唯一拥有者及规则 |
| --- | --- |
| id | 沿用`opportunity:<旧job_id>`；新对象也生成稳定同形ID，后缀可供只读旧ID适配，但不创建新Job行 |
| company_id | 必需，指向domain_company；公司显示名实时读取Company，不另存可写company文字副本 |
| title / jd | 复用内部字段名，语义分别为role_name/jd_text；必填。名称统一通过DTO，不为更名全仓改写 |
| url（DTO action_url） | 可空，仅http/https；一份存储值，旧url与新action_url只是输入/输出映射；两者同时传且不一致则422 |
| phase | 严格`resume / submitted / interview / offer`，标签“写简历 / 已投递 / 面试 / Offer”；没有closed/ended/unknown枚举 |
| phase_changed_on | 当前phase进入日，YYYY-MM-DD；新建必有，已核对阶段但历史日期未知可null并显式标记来源不足 |
| phase_source | 最小来源元信息：action、source_id、发生/确认时间及known/unknown说明。它解释phase日期，不是第二份可独立编辑的日期正本 |
| result | 严格`active / accepted / rejected / withdrawn`；只由结束动作或明确历史确认初始化，job/application状态不是来源 |
| result_changed_at | 保留。新建active为null，End时为带时区的服务器动作时间；用于记录结束事实，不能借updated_at推断。迁入已有终态但日期未知时null且记录Unknown；不创建Timeline表 |
| created_on | 加入Career的日期。新建取业务时区当日；历史来自可确认的created_at，不取迁移日，不能解释为实际开始求职日 |
| revision | 以current.revision为CAS权威；返回body revision必须相同。迁入已有ID时新revision高于相关旧机会/Job revision，不能让旧快照误过CAS |
| legacy_job_id / format_version | 旧ID与格式识别元信息；新建对象的legacy_job_id可空，其ID后缀仅作兼容请求别名，不声称旧Job行曾存在。format_version=2识别canonical，缺此标记的旧opportunity行不因kind同名获得新写权限 |

辅助计划`next_action/due_date`仍可由JourneyPlan持有，独立revision；stage停止写入并只作legacy解释。组织/方向/周期引用保留现有兼容数据，不作为创建前置，本批不扩组织树。

Company只保存自己的名称/身份与现有资料。创建时按**trim + Unicode NFKC normalization + trim + casefold生成确定性匹配键**：0个匹配则同事务创建；1个匹配复用；多个匹配返回409及候选ID让当前创建者选定。展示名称保留用户确认的原始写法（仅去首尾空白），不以NFKC/casefold键覆盖展示。不给相似简称做模糊合并，不猜别名，不自动合并不同名称主体；多个既有主体即使匹配键相同也返回歧义，不自动合并。Company选择参数company_id/company_name二选一；ID存在且kind正确。公司目录新建复用同一规则，修改名称保留原Company ID，不合并历史Company；更换机会所属公司调用机会动作，不改Company来“修复”某一条机会。

### 3.3 必须保持的不变量

1. canonical当前信息/phase/result只写一行Opportunity；旧Job、旧context.company_id及plan.stage绝不跟写。
2. Company 1:N Opportunity；一个canonical必须有且只有一个有效Company。未确认旧记录走独立legacy读DTO，不给canonical塞一个猜测Company或伪造默认状态。
3. `result != active`是已结束View的唯一业务判定；phase保留最后位置。四阶段View只含对应phase且result=active；全部含active及结束记录。legacy Unknown不参与此布尔判定。
4. accepted仅当phase=offer且有明确同机会的有效Offer来源；多个旧Offer未选定、未知活动或跨机会引用均不允许。rejected/withdrawn可在任一phase发生。
5. 普通信息编辑、辅助计划、Company改名、简历/评估/Raw/旧application.status变化不切phase，不刷新阶段日。
6. 任何新状态写入通过Domain Action及同一事务；前端不能先保存记录再第二次POST phase/result。
7. 原Submission JSON、ID/外键列、版本/PDF、ResumeUse、Raw/Wiki/Candidate及已有revisions保留；不能重建冻结快照或清掉旧数据使测试通过。
8. ended拒绝新推进动作；本批无Reopen/任意结果改写。结束动作不删除资料、不写Offer.status副本、不创建Employment。

## 4. 最小Domain Action、日期与并发Interface

以下是拟实施合同，HTTP路径可沿用现有路由，但不能改变动作语义。

| Action / 边界 | 输入 | 原子结果与错误 |
| --- | --- | --- |
| CreateOpportunity；POST /api/opportunities | company_id或company_name、title、jd、action_url?、idempotency_key | Company解析/创建＋Opportunity＋请求回放记录一次提交；resume/active、created_on=phase_changed_on=当日；不建Job/plan/简历/Submission |
| UpdateOpportunity；POST /api/opportunities/{id} | expected_revision、idempotency_key、允许的信息字段 | 只改company/title/JD/url，bump epoch；拒绝phase/result/date等越权字段，不接收任意JSON patch |
| EndOpportunity；POST /api/opportunities/{id}/end | expected_revision、idempotency_key、result及accepted所需明确Offer来源 | 校验当前状态和来源，保存result/result_changed_at、revision及动作回放；phase/phase_changed_on不变。已结束同结果可返回当前结果且不改时间，换结果409 |
| SaveOpportunityPlan；旧plan端点适配 | plan expected_revision、next_action、due_date；可识别旧stage回传 | 只写辅助计划；禁止改stage，原样回传只忽略且明确标legacy字段。按job_id查真实plan，不拼ID误建第二条；多plan先报冲突。结束或未核对历史不开放该写入 |
| ResolveLegacyOpportunity（迁移决策应用，不开放通用phase接口） | 绑定inventory/hash的明确映射：公司、phase/result、已知日期/Unknown及依据 | 仅用于指定legacy记录一次性建立canonical；没有事实就保留legacy。经人工选择的值记录来源，不把脚本默认值当用户确认；重复决策幂等，改变输入409 |
| List/Get/Resolve | canonical ID或已知旧Job ID；View参数 | GET只读，返回canonical DTO或带read_only/unknown_fields的legacy DTO；ID不存在404，不返回第一条机会，不在GET创建Opportunity |

新可变命令必须带正确整数revision和幂等key；同key同指纹先回放原结果，再考虑当前CAS，时间不随重试改变；同key异内容409。旧投递/活动的既有幂等回放只返回旧结果，不重放写入或补phase。SQLite `BEGIN IMMEDIATE`串行化Company选择、CAS、机会与命令记录；操作间不得重开连接形成半成功。并发同公司创建两个不同尝试时，一个Company、两个Opportunity；同动作重试只一个Opportunity。没有全局按公司＋岗位去重，一次新尝试是新对象。

错误：404无此对象；422字段/URL/枚举/accepted前提不合法；409旧revision、重复key冲突、公司多匹配、legacy待核对或旧生命周期入口不可用。响应使用稳定code及可展示detail；对缺新契约的旧客户端提示刷新，不能在后端悄悄取最新revision替它通过CAS。前端保存失败保留输入，成功后回读同一Opportunity。

### 阶段日期规则

| 来源 | phase与日期规则 | B实际范围 |
| --- | --- | --- |
| CreateOpportunity | resume，创建动作业务日 | 实施 |
| RecordSubmitted | submitted，真实登记投递动作日，同Submission事务 | C实施；B只固定接入规则，不写假Submission或开任意切阶段接口 |
| ConfirmRealInterview | interview，确认日，不是未来面试日期；已在interview时下一轮不重置 | E实施；B用隔离已核对历史输入验证展示/不推断规则 |
| 首次RecordOffer | offer，真实收到并记录的领域来源日；更新条件不重置 | F实施；B不让旧通用Offer note自动触发 |
| EndOpportunity | 保留原phase日期，单独记录result_changed_at | 实施 |
| 历史迁入/修正 | 只有明确依据才写日期；未知为null；plan.due_date/updated_at/迁移日不替代 | B迁移实现；日期不独立任意编辑，后续业务日期修正须在所属动作同步处理依赖 |

新动作以服务器业务时区（本机Asia/Shanghai）计算日期，保存带时区动作时间；测试注入时钟覆盖UTC跨日。迁移manifest固定采用的时区与转换依据；来源时区/日期语义不明则Unknown。B不提供“纠正当前phase日期”来绕开尚未实现的所属领域动作，也不预写C–G全部服务。

## 5. AS-IS → B映射与迁移策略

| AS-IS | B目标 / 保留方式 |
| --- | --- |
| job＋复制opportunity | 沿用canonical ID；信息字段一致且业务状态已明确才建立format_version=2的唯一行；旧job保存原JSON，停止当前写入 |
| company文字＋context.company_id | canonical只存company_id；有冲突不按ID优先或文字优先自动决策。旧两值都可回读 |
| JourneyPlan stage | 保留原stage与历史，不翻译为phase/result；next_action/due_date仅辅助计划，可继续按本批新约束修改 |
| status=deleted/excluded/active | 原值只用于legacy说明/原隐藏语义，不变成rejected/withdrawn/active事实。deleted记录仍通过历史入口可达，不因迁移恢复成活动机会 |
| applications/status_history | 原表、列与body全保留；canonical通过ID alias查关联，不改基数/非空约束；不按status推结果 |
| research/communication/interview/offer＋raw_note | typed ID与note原件不变，按alias展示；不重新typed化同一note、不确认真实/模拟、不猜阶段 |
| resume/version/use/PDF/Wiki/Raw | 只适配机会ID读取，保留所有内容、owner、scope原值及文件；不批量改引用JSON |
| demo G1/G2、其他未决历史 | 保留只读legacy，列明Unknown及原记录；不生成带假状态的canonical，不清理demo |

**Unknown承载**：`LegacyOpportunityView`与`CanonicalOpportunity`是明确区分的读DTO。legacy DTO可有phase/result/company_id=null和unknown_fields，这些null不是canonical枚举新成员。现有旧opportunity行无format_version=2时是历史兼容来源；新旧同ID最多返回一行。全部View内另列“历史待核对”分组，仍只有六个View，不增加第七业务阶段；原deleted/excluded记录保留独立的历史资料入口/原URL可达，不偷偷纳入四阶段计数。legacy只读权限由后端保证，不依赖页面隐藏。

当前未标记旧Job的resume/active可列为候选，未确认为事实前允许整体保持legacy；这不阻止新建canonical机会。Company可按明确原公司名称提出新建候选，但在该机会整体被延期时不单独落入一个无用途Company。demo明确保持legacy，不能让用户替案例决定公司或面试类型。真实用户若希望继续推进未决记录，仅在迁移准备中核对该记录；不会为了查看旧材料强制补齐。

### 迁移执行步骤（本轮均不执行）

1. 固定B执行代码与前端构建版本，保存可回到A的源码/构建快照及hash。工作树未提交时不能只记Git HEAD；不使用reset/clean去制造“干净基线”。配置只记非敏感运行元信息，不触碰.codex/config.toml。
2. 核对实时生产路径/运行PID与源码，readonly inventory覆盖Company/Job/Opportunity/所有按job_id关联的plan/application/typed。为每个旧ID输出canonical候选、字段来源、歧义、`migrate`或`defer_legacy`及前置hash；不读取正文到仓库。
3. 使用A工具取得新备份并恢复到**新隔离目录**；原A备份和证据只读保留。先在隔离副本演练migration、业务读取和rollback。独立证据目录保存前后schema、对象/文件hash、决策、代码版本。
4. 在隔离副本模拟停写窗口，记录副本最后epoch/hash，确认没有副本写者。正式生产服务不停止、不迁移、不切换写路径；最新生产备份由现有一致备份能力取得。待迁移副本必须与决策清单hash一致，不符重新dry-run。
5. 在现有五表上执行单事务v1→v2：保存会被替换的旧opportunity完整行到明确迁移before-image记录，追加而不覆盖已有revisions；创建已确认Company/Opportunity，保留legacy来源/映射；记迁移ID、指纹、预后计数及完成标记；bump epoch与user_version=2一起提交。出错全回滚，无附件写入，无applications表重建。
6. v2首次启动只校验已完成迁移；新空库可初始化v2，已有v1明确拒绝并提示显式迁移。旧A程序因user_version>1拒绝打开；不得在新Store启动里重新执行`PRAGMA user_version=1`。
7. 开放新写前核验变化白名单：只有批准的Company/canonical Opportunity、追加Opportunity revisions、迁移/命令记录、epoch/version可变；旧Job、原plan/context、原applications/records/revisions及artifact字节必须与before-image或原行逐一匹配。不能要求整库hash相同，也不能仅比总行数。
8. 用对应版本服务在迁移副本完成§8验收后停止，保留隔离产物与生产v1。后续Production Cutover必须另有显式部署授权，届时重新备份、停写、复核迁移输入；本批不执行。repeat apply同一迁移ID/输入只验证原完成状态，不重新覆盖canonical后续编辑；输入不一致失败。

原Job与context、plan读取档案保留在原位置，已有Opportunity被替换前的原行由before-image及原历史保全。数据库级的表名复用不意味着旧格式仍可写。公开resolver只认显式schema/format和确定ID映射，不能猜字符串前缀后读任意行。

## 6. 兼容入口与反绕行矩阵

兼容期以能力为边界，不无限保留旧写逻辑。新老请求统一经过canonical resolver与Domain Action；只读历史永不触发sync_job。

| 现有入口 | B的处理 |
| --- | --- |
| /api/opportunities GET/POST、Store.save_opportunity | GET统一投影；POST分别委派Create/Update；删除反向save_job调用，不再复制当前值 |
| POST /api/jobs 与 /api/jobs/{id}、Store.save_job | 元信息字段映射到Create/Update。旧请求缺幂等key或有效canonical revision则明确拒绝并提示刷新；回传Job-shaped DTO中的revision是canonical CAS。旧status只能在可识别的原样回传时忽略，改变status拒绝；active不代表重新开启 |
| sync_job/_save_job_in_transaction | 隔离v2新写调用清零并退役，不能留下内部方法继续写Job；测试构造旧库使用专用v1 fixture，不调用被退役生产方法伪装新流程 |
| /api/state.jobs及所有当前Job读者 | 返回canonical的只读Job-shaped适配＋显式legacy资料，不读取旧Job作为已迁移机会的当前值。增加窄resolver/job-view reader；不全局改通用_get的任意kind语义。editor/knowledge仅必要ID/scope reader改动 |
| /api/domain/opportunities/{job_id} 公司关联 | 公司修改转UpdateOpportunity；必须携带canonical revision，不用context revision代替。B旧混合赋值请求无法安全适配时409整笔拒绝，不部分保存公司/组织。组织/方向/周期引用当前兼容读取，目录对象自身管理仍保持 |
| /api/domain/objects Company创建/改名 | 复用Company解析、CAS、epoch；不写每条Opportunity.company副本；已有多同名对象不删除合并。OrgUnit/Role/Cycle其他行为不扩展 |
| /api/journey/plans/{job_id} | 委派SaveOpportunityPlan，仅next_action/due_date；变更stage/closed拒绝。plan自己的revision与Opportunity revision不混用；不存在计划可懒创建辅助计划，不创造阶段事实 |
| POST /api/applications；record_application | 原有key同请求仍回放冻结结果。schema v2下新投递返回409 `submission_action_pending`，等待C，不新增Submission/自动补Opportunity；保留原GET和PDF读取。不能为B偷偷补Greeting/唯一投递/无简历逻辑 |
| /api/applications/{id}/status | v2拒绝新状态修改，指向明确结束动作或后续领域能力；不映射closed/rejected/offer为Opportunity结果/phase。历史status_history原样可读 |
| /api/opportunity-activity/interview、/offer；job scope对应journey/notes | 已有幂等回放保留；新的生命周期活动在v2返回409 `lifecycle_action_pending`，不先写Raw再失败。E/F接管后才能开放。不能只堵typed API而留下note自动typed旁路 |
| research/communication/普通job note | 只作现有资料记录能力保留，身份改读resolver，result/phase字段不可写入；不切phase、不称新Research/Communication产品已完成。ended/legacy是否可新记资料按兼容能力明确只读，原读取/来源回看保持 |
| note更正/候选、ResumeUse | 仅核对alias与原scope，不能修改Opportunity状态或补写Job；不改Raw政策、简历owner、版本及用途基数。已存在资料更正仍保持原有历史合同，不套新Raw规则 |
| /api/demo/load、/remove | schema v2下在任何SQL/文件副作用前明确拒绝旧整包装载/删除；UI说明原案例可读，完整案例更新另批。避免载入复活双写，也避免删除跨数据集PDF；不调整Employment/Project案例数据或自动清理 |
| /api/context、/api/analysis及Compiler | 用canonical ID/revision、当前JD及Company身份读源；legacy Unknown请求明确不可用于新当前机会分析。保留profile/选定active Wiki与demo隔离，移除因旧context关联自动带入的目录description，不能误当Research；只做身份/资料边界适配，不接真实AI或新增Skill |

`/api/domain/objects`不是任意kind写接口；迁移与新增路由也不能暴露任意current JSON写入。拒绝路径全部测试数据库/附件未变化，包括幂等记录不得在验证失败前写入。schema升级阻止旧二进制；HTTP边界阻止旧浏览器请求，二者都需要，不能相互替代。

### 旧ID与URL

- 保留`/#jobs/<旧ID>?tab=...`、`#progress`和来源回跳；新路由拟为`/#opportunities/<canonicalID>`，旧路由解析后定向至同一Workspace/历史资料锚点。采用encodeURIComponent，不用首条机会兜底。
- `tab=resume`转现有投递/版本历史阅读区；`tab=interview/offer/research/communication`定位已有记录，显示其legacy语义，不宣称进入已实现的新领域工作区。
- 原artifact下载URL、版本ID、application ID、Wiki及note/history链接保持。没有当前canonical行不妨碍历史材料读取。
- 不将旧editor URL偷偷解释为“该机会拥有的ResumeDocument”。B不改editor-main所有权或独立工作台行为；新Workspace不把共享稿入口标成“本机会简历”。旧资料阅读与未来C的独立稿入口分清。
- /work、Employment/Project、任职practice/reflection及其深链不重定向、不修改领域数据。

## 7. 前端和修改范围、执行顺序

### 界面合同

管线直接读后端Opportunity DTO。六个View、四核心列、可选外链图标；外链点击不触发行导航，使用http/https与noopener；整行可键盘进入。列表页与Workspace分开，不继续把主体验做成旧左右栏。空列表可直接添加机会，缺URL不显示无效图标。

Workspace顶部固定公司、岗位、phase标签、阶段日期、阶段条、外链及编辑/结束动作。阶段条是展示，不允许点击伪造推进。已结束保留phase并显示结果/结束日期，正常推进按钮不出现。日期未知直写“历史日期待核对”，不展示当天；legacy信息不伪装canonical已生效。

当前阶段区域本批只提供已实现动作及简短能力说明，投递准备/沟通/面试/Offer可结构占位；Research/投递材料/历史记录复用读取组件，显示旧数据真实边界。没有Greeting时不造文本，没有real轮次时不显示“开始模拟”，没有已确认Offer时不显示可接受动作。不实现Timeline全量聚合或把普通保存加入活动流。

### 本批允许的实现范围

| 模块/文件 | 允许改动的边界 |
| --- | --- |
| src/workbench/opportunity.py | canonical模型、reader/resolver、动作与管线DTO；若文件职责过重，仅拆出实际需要的只读/迁移小模块，不重建通用Repository |
| src/workbench/core.py、app.py | 状态装配、schema门禁、旧Job/投递旁路移交与拒绝；保留Store事务/冻结实现，其他业务不重构 |
| src/workbench/domain.py | Company复用、旧公司赋值适配、ResumeUse的机会身份读取；不改用途所有权/基数 |
| src/workbench/journey.py、engagement.py | 辅助计划、alias读取、旧生命周期写门禁；任职分支不变，不实现real/simulation或Offer模型 |
| src/workbench/context.py | canonical当前源/CAS/epoch、去隐式目录正文；不做任务注册、Research编译或总预算工程 |
| src/workbench/editor.py、knowledge.py | 仅直接Job存在性/scope读取调用的窄适配；不得改稿/版本/Raw/Patch写入合同。若需超出reader改动则停下重划范围 |
| src/workbench/demo.py | v2旧整包写入口门禁，现有demo保留；不重做跨Employment/Project案例 |
| 新src/workbench/opportunity_migration.py、scripts/migrate_opportunity.py | 显式v1→v2 dry-run/apply/verify；新的受控CLI，不自动启动迁移、不任意SQL修复 |
| src/workbench/migration_baseline.py、必要时backup.py | 按v1/v2读格式核验、变化白名单、包格式/DB版本区分；旧A测试与证据语义继续可回读，不弱化hash验证 |
| frontend/src/main.ts、workspace.ts、style.css | 管线、路由、Workspace顶部、Create/Edit/End、旧入口限制与错误恢复。可抽一个opportunity-ui.ts承载该闭环并定义DTO；当前main.ts的Obj/Page和workspace.ts的Row只在相关边界收窄，不重构其他页面 |
| frontend/src/knowledge-ui.ts | 其中现有directoryView/opportunityObjects与公司关联表单，仅适配Company选择/旧关联入口提示；不改Wiki/Candidate产品流程 |
| tests下Opportunity/迁移测试与直接受影响现有测试 | 新不变量/旧入口/迁移/回滚和关键回归；旧schema fixture与新canonical fixture分开。profile两项已知失败不顺手重写 |
| 服务/前端README、本批记录、STATUS | 维护实际API、命令与证据；不回写两份审计快照、不改四份目标或其他产品权威正文 |

实施顺序固定为：①测试与公共DTO/决策格式 → ②canonical/Company/actions及schema门禁 → ③迁移与恢复比较 → ④所有旧写/读适配与Context最小边界 → ⑤管线/Workspace及旧URL → ⑥隔离自动/浏览器验收 → ⑦隔离恢复演练、生产未迁移核对与最终范围审查。任何步骤不得用新前端隐藏旧API风险来跳过④；Production Cutover是后续显式授权的部署动作，本批验收通过也不执行。实现采用独立源码工作区及独立前端输出，避免生产延迟导入新代码或读取新dist；不替换生产进程和启动路径。

## 8. 编码前固定的验收（实际结果见 §11）

### 自动测试

扩充现有`tests/test_opportunity_flow.py`，新增`tests/test_opportunity_migration.py`；使用临时目录、虚构主体、Fake/TestProvider或拦截请求，不调用真实模型。旧Opportunity测试的投递冻结断言转为“v1虚构快照迁入后仍不变”的验证，不能因v2暂停旧新建动作而删掉历史保护覆盖。

| ID | 预先确定的可观察条件 |
| --- | --- |
| B01 创建/Company | 必填校验、可无URL/无简历；默认resume/active/正确业务日；无Job/Resume/Submission副作用。NFKC/casefold/首尾空白等价名复用（包含全角、组合字符、大小写、ß），显示名原写法保留；不同名称/相似简称不猜合并，不同尝试不去重，多个既有主体键相同则409不写 |
| B02 原子/幂等 | 并发Unicode/casefold等价名并发创建复用一Company；同key重试一机会；同key异内容409；Company创建后注入失败无孤儿Company；revision冲突保留原记录 |
| B03 单正本 | 新旧信息更新路由读到相同当前值；旧Job/body、旧context.company_id不跟写；旧revision不能覆盖；未知字段/phase注入失败 |
| B04 phase/result | 四phase×active/允许终态的View结果；非Offer accepted、无/跨机会/未选定Offer拒绝；rejected/withdrawn保留phase和阶段日；结束重试不刷新结束时间，无Employment |
| B05 日期 | 创建跨UTC午夜按业务日；普通编辑/计划/Company改名不变阶段日；迁移无日期null；due_date/updated_at/typed数量不生成日期或phase；下一轮/Offer更新接入规则本批只验纯状态约束，不假装已实现领域动作 |
| B06 旧接口攻击 | §6每个入口通过旧Job ID与canonical ID分别测试；status=deleted/excluded/active、plan.closed、applications.status、typed和note绕行、demo load/remove均不偷写状态。403/409/422等拒绝后DB/附件无副作用 |
| B07 原回放 | 迁移后原application及活动key回放保持原JSON、原日期/hash，不新建行、不调用sync_job、不切phase；不同请求仍冲突 |
| B08 Context | 新旧ID同一次尝试读取当前canonical JD/Company身份；修订后旧epoch/来源过期；旧Job/JD、目录description、其他机会材料/Raw/历史run/Feedback不混入；不扩展现有允许Wiki/profile范围 |
| B09 历史身份 | canonical与legacy同ID去重、未知ID404；note/application/version/PDF/Wiki旧链接可回读；legacy Unknown不自动进入已结束或四阶段 |
| B10 越界回归 | Employment/Project及episode note创建/更正/候选路径在临时资料上行为不变；任职/反馈对象的既有行迁移hash不变；editor仅验证scope读取适配，不改变owner和冻结材料 |

### 迁移/rollback测试

| ID | 预先确定的可观察条件 |
| --- | --- |
| M01 dry-run | v1仅Job、Job＋旧opportunity、公司多匹配/冲突、多plan、无日期、各旧status与typed混合都输出准确候选/Unknown，源SQL/附件hash不变 |
| M02 保留 | 明确决策迁移后唯一canonical、原ID可达；全部旧行/历史/PDF及冻结JSON与before-image保护集合相同；G1/G2继续legacy且未擅自选值 |
| M03 失败/重跑 | 事务中每个关键写点注入异常全部回滚到v1；同迁移ID重跑不重置新数据；输入/hash/版本变动拒绝；不支持schema明确失败 |
| M04 版本/旁路 | A匹配旧程序拒绝v2；B启动已有v1不隐式迁移；新空库为v2；v2重启不降版；缺行旧投递GET/回放不补实体 |
| M05 恢复 | 新备份真实恢复到新临时目录，以匹配版本验证SQL integrity/FK/对象/原行hash和附件；迁移前恢复、迁移后恢复各验证一次，A旧包格式仍可读 |
| M06 回滚 | 开写前回到新隔离恢复目录＋A代码，v1原内容一致；开写后模拟新增机会/JD改动，证明简单恢复旧备份会丢数据并被流程禁止，保留v2新备份/变更清单；没有完备逆变换不宣称可无损降版 |
| M08 生产保护 | 正式Career Data仍为v1；生产PID/版本/静态资源hash和源码路径保持；不执行生产POST业务请求；旧投递/面试/Offer路由及v1源码不变。对业务数据的外部变化单独归因，不以读取快照宣称永久未变 |
| M07 本次真实副本 | 使用届时实际备份只在隔离目录演练；不以demo决定语义。未标记旧记录若缺事实可全部defer，验证仍可阅读；报告分别列migrate/defer/blocked，不把defer算迁移完成 |

预先固定两组执行范围：核心组为`test_opportunity_flow.py test_opportunity_migration.py test_migration_baseline.py test_backup.py`；兼容回归组为`test_core.py test_http.py test_applications.py test_context.py test_domain.py test_journey_http.py test_engagement.py test_editor_http.py test_wiki_integration.py test_work_domain.py test_demo.py`，路径均在tests/下。这些文件分别覆盖变更的共享Store/HTTP、旧入口、scope读取和非本期边界，使用`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest <上述tests路径> -q -p no:cacheprovider`执行。不为绿色删除旧断言；需要调整旧语义测试时保留v1兼容覆盖并说明对应新需求。`tests/test_profile_ownership.py`的两项既知失败单独列基线，新增失败不豁免。前端执行`npm --prefix frontend run typecheck`及一次`build`。不重复无关全量测试。

### 实际浏览器验收

服务必须使用虚构临时数据目录和不同于生产的端口；seed仅在测试fixture明确设定历史phase/Offer，不能用生产案例自动补字段。

| ID | 实际浏览器动作与结果 |
| --- | --- |
| U01 空库创建 | 从空管线创建无链接机会，进入稳定顶部；再建同Company另一岗位，列表两行共用主体，无简历操作前置 |
| U02 六View | 四阶段active及三终态虚构数据；过滤计数和行正确，全部可读，已结束保留最后phase；legacy Unknown独立标识，不混入业务筛选 |
| U03 导航 | 鼠标整行/键盘进入，外链单独打开；返回保留View，刷新仍定位原机会；旧jobs URL与tab锚点可读，坏ID明确不存在，无回退首条 |
| U04 编辑/CAS | 双窗口编辑同机会，一成功一冲突，第二窗口输入仍在；刷新比对再明确提交；重载和服务重启当前信息不丢 |
| U05 结束 | 写简历时withdrawn、面试时rejected、经过确认的Offer fixture accepted，页面进入已结束且原阶段日不变；没有确认Offer不提供可接受按钮；后端直接请求同样拦截 |
| U06 真实边界 | 四阶段占位不出现虚假可执行Resume/模拟/Offer动作；旧冻结PDF可下载、无Greeting显示历史缺失；被暂停的旧操作提示明确且不显示成功 |
| U07 非本期 | 原/work与Project入口、任职记录深链、个人资料与独立编辑器仍可访问；不显示“本机会独立简历已完成”，不修改生产数据 |

覆盖Acceptance：O01/O02；O03的创建/结束/迁移日期部分；O19的历史保护、旧ID及恢复；O20的管线/基本Workspace部分；R01–R04与本批有关部分。**O04–O18、完整O03/O20与完整求职主链不得整体勾选通过。**

## 9. Rollback、Gates与反向审查

### Rollback

以下策略本批仅在隔离副本演练，不停生产、不更换正式数据目录。开写前回退和开写后恢复须分别提供实际证据；不能只靠文字设计声明成功。

- **未开放新写入**：停B服务；用切换前已验证备份恢复到另一个新目录，使用保存的A代码/前端构建启动并核对hash/身份。切换数据路径而非覆盖原生产目录；迁移目录保留调查，不把user_version直接改回1。
- **已开放新写入**：立即停写、备份完整v2及附件，保存切换后新增/修改行清单。首选在v2上向前修复；若必须回迁，另行实现并验收能表达全部新增canonical信息的逆映射。旧Job/status无法无损表达新result/日期时不做自动降版，不用旧快照抹掉新资料。
- 回滚切换使用匹配code＋DB version＋非敏感运行参数；A原旧进程完整内存代码无法追溯，但A重启后的0.2.0源快照可在B开工前保存。仅HEAD不足以恢复未提交源码。双目录保留期间只开放一个服务写入。

### Gates分层

| 类别 | 本次状态 / 停止范围 |
| --- | --- |
| 技术执行前置 | 新备份/隔离恢复、运行身份、v1/v2工具和停写控制需要B执行时重验；未通过不宣称隔离验收完成；本批无论通过与否都不切生产，不要求用户重选技术栈 |
| demo G1/G2 | 明确defer_legacy，不报用户产品Gate；不阻塞新canonical开发与管线验收 |
| 未标记旧Job phase/result | 当前只有旧字段线索，真实属性Unknown；默认defer可继续查看。只有用户要将该实际记录转成可推进canonical且事实不能推导时，才针对该记录确认，不一概称真实用户Gate |
| 多公司/多Submission/多Offer/多plan | 当前A无多Submission/多Offer，B临迁移仍重查；不合并/删行。多个Submission不阻止B保留关联，唯一基数改造留C；不能确定phase/accepted来源的记录defer |
| 旧客户端需求超出分批范围 | 暂停前向生命周期写只在隔离v2；生产v1完整保留当前写路径，不因本批交付停用。后续cutover另行授权，不能提前部署 |

### 反向审查结果（规划判断，不是实现验收）

| 问题 | 计划处理 |
| --- | --- |
| 真要新增表吗？ | 不需要；current JSON＋现有records/revisions足够。schema v2是写语义兼容门禁，不是借机建全领域表 |
| 为了命名做无价值重写吗？ | title/jd/url内部保留，DTO明确语义；不引入JobPosting、ORM、全局Repository，不重写编辑器 |
| 还会有两个可写Opportunity吗？ | canonical只写opportunity；旧Job/context.company/plan.stage冻结，sync_job所有调用清零；legacy只读，辅助计划不拥有phase |
| deleted/excluded/closed/application.status自动映射结果？ | 全部禁止；也不把active视为可信历史业务结论，只有明确决策初始化 |
| 根据Offer/Interview存在猜历史phase？ | 禁止最大阶段/最新时间推断；typed记录只作证据，未知留legacy |
| 侵入C–G？ | 只固定接入合同并封旧旁路；无ResumeDocument/Greeting/唯一Submission/real-simulation/当前Offer/Research/Raw-Patch/AI Skill/完整Timeline实现 |
| 影响Employment/Project？ | 不改其对象和写合同；只在shared router按Opportunity scope分流，明确回归原路径。demo旧整包停用属于入口保护，不重写任职案例 |
| 旧客户端能绕开？ | HTTP、Store旧方法、application补写、note自动typed、domain赋值、demo整包及版本门禁一起验收；仅前端隐藏不合格 |
| 日期双正本或假历史？ | 当前phase与来源同事务，辅助计划独立；Unknown可空；不拿今天、updated_at或due_date补历史 |
| 分批暂停掩盖交付不足？ | 明确B只闭环创建/信息/结束与基础视图；完整前向推进未交付。上线前必须按此限制评估，不称完整机会流程已完成 |

## 10. 明确停止点与本轮产物

本轮先写回以上两项调整，再在独立源码工作区实施并验收。自动测试用虚构临时资料；最新生产备份只恢复到新隔离目录，migration/rollback/v2启动验证不指向正式Career Data。浏览器操作使用非生产端口、虚构资料。生产源码/静态文件/进程及v1正式写路径保持，原审计/目标/A记录不改。

完成本计划限定的canonical闭环、兼容保护、隔离迁移恢复和独立验收后停止；Production Cutover留到后续显式授权。任何真实Gate只暂停受影响映射。不得顺手进入C、重做Resume、修旧profile测试、接AI、清理资料或调整Employment/Project/.codex/config.toml。


## 11. 实施与独立验收记录 — 2026-09-17

### 交付位置与生产保护

业务实现位于 `/Users/frog/Projects/Career-worktrees/batch-b`，分支 `codex/opportunity-b`，基于 `368af740fd2b17e5718ce31675bf526df4591347` 加开工时已有工作树内容。原生产进程从 `/Users/frog/Projects/Career` 延迟导入模块并直接提供 dist，因此本批没有向该目录回拷业务源码/前端产物。原目录仅同步本记录与 STATUS；原有未提交修改不计入本批，也没有提交或推送。

生产 PID `2994`、版本 `0.2.0`、目录 `/Users/frog/Library/Application Support/Career Data`、schema v1 均保持。最终核对数据库物理 SHA、全部逻辑快照、附件、生产源码/dist 与开工基线一致；没有生产业务 POST、重启、数据清理或迁移。backup 仅在稳定写入窗口保留锁并复制，不改变记录。Employment/Project/profile 和纸面编辑器业务实现、四份目标、两份审计、A记录、AGENTS、技能及 `.codex/config.toml` 未作本批修改。

### 实际实现

- 继续使用现有 current/records/revisions：canonical Opportunity 只写 opportunity 行，复用 Company；新机会不产生 Job 行。Create/Update/End 封装事务、CAS、幂等、Company 选择与日期。accepted 只允许已明确核对的同机会唯一 Offer，未接入 F 的当前 Offer 管理。
- Company 匹配键采用 trim → NFKC → trim → casefold；保留展示写法。inventory 同时保留原 exact_name_matches 供历史解释，增加 identity_matches/rule；它不替用户合并或选定主体。
- 旧 Job 元数据适配委派同一动作；Job 状态、plan.stage、context 公司赋值混合请求、投递状态、面试/Offer typed 与 note 新建、demo 整包被相应门禁封闭。原 application/活动请求先核对指纹再回放，冻结 JSON 不变。已有更正/候选仍只校验原范围，不套新写门禁。
- Context 读取 canonical JD/revision 和 Company 身份，去掉旧目录 description 的隐式正文。editor/knowledge 只适配机会存在性读取；没有改变 ResumeDocument owner 或版本/Raw 合同。
- `opportunity-ui.ts` 提供六 View、四核心列、Create/Edit/End、基础 Workspace、真实占位说明、历史材料及来源回看；CAS 比较保留输入，旧 URL 不回退首条。settings 的旧整包案例按钮明确禁用。独立 editor-main 不被标成每机会独立稿。
- `opportunity_migration.py`/CLI 显式迁移，绑定源 schema/全行/附件 hash，保存旧 current before-image；报告路径先预留、拒绝覆盖。apply 仅接受系统临时目录独立普通 SQLite，拒绝符号/硬链接；启动已有 v1 先只读拒绝，启动新空库为 v2。

修改模块以本记录 §7 和私有 `batch-b-changes.json` 为准；工作树相对 HEAD 的 diff 还包含之前文档对齐与 A 的未提交内容，不能全部归入 B。

### 自动测试与修正

| 实际执行 | 结果与含义 |
| --- | --- |
| §8 固定核心/兼容组 | 55 passed；覆盖 canonical、Company、CAS、所有 phase 的拒绝/退出、已确认 Offer 接受、迁移/恢复/旧入口及非本期接口 |
| 加上本批直接修改 fixture 的 journey/record_candidates/editor/knowledge 四文件 | 最终 77 passed（2.38s），含前述用例；不与55相加 |
| 最后审查定向重验 opportunity_migration + record_candidates | 21 passed（1.27s），含新增硬链接/报告路径冲突保护和 manifest/before-image 校验；与77存在重叠，不算98个独立测试 |
| profile_ownership 单独基线 | 1 passed / 2 failed。新增 Company/Job fixture 只补幂等键；原两个失败断言不改。profile 保存同步共享草稿，旧测试继续使用 revision=0/旧 revision，收到409；另一测试直接从错误JSON取 document 导致KeyError。读取最新revision的 A/B 隔离HTTP断言通过；不是本批 Resume 修复 |
| frontend typecheck / build | 通过；界面最后的暂停提示变更后重新 build（含 tsc），保留原 editor chunk >500KB 提示，不借此重构 |
| git diff --check | 通过；本批新增文件另做空白/语法与链接检查 |

旧测试适配是测试资料准备变化：旧新增投递/面试路径改成既存 v1 冻结 fixture，并继续断言版本、PDF、原文、修订、重放与 Context 隔离；没有通过修改产品目标让旧新增动作返回200。补充实际使用原0.2.0程序生成虚构 Submission/Interview/Offer，再确认迁入v2，三类原请求回放JSON一致且未改变任何行。

### 最新生产备份上的真实 rehearsal

证据根目录：`/Users/frog/Library/Application Support/Career Migration Audits/batch-b-20260917T131011Z`（本机私有，含标识和hash；不复制用户正文到仓库）。

最新备份：`/Users/frog/Library/Application Support/Career Data-backups/batch-b-20260917T133523Z`。本批确实调用现有 backup 创建它；确实恢复到新系统临时目录。临时父目录：`/var/folders/cl/wtl8p1w508g43s7b4wqsr5gh0000gn/T/career-batch-b-rehearsal-sun4yube`。

| 证据文件 | 实际结果 |
| --- | --- |
| latest-backup-restore.json / latest-backup-inventory.json | schema1；meta1/current24/records27/applications1/revisions146，共199行；49个引用、1个PDF全部一致，integrity=ok，无FK/引用错误 |
| final-plan.json | 2个候选均 defer_legacy；demo G1/G2不升级用户Gate。另一个未标记Job只有旧状态线索，真实属性Unknown，不默认用户决策 |
| final-migration-apply.json / final-post-start-integrity.json | final-migration新隔离副本真实v1→v2；migrated=0、deferred=2，不将defer说成两条canonical已迁完。全旧行不变，records仅新增迁移manifest为28（总200行）；附件不变，schema SQL不变，user_version=2 |
| final-v2-runtime.json | 隔离8773实际启动0.3.0-batch-b；2条legacy机会可读，历史投递/资料保留；启动后再次verify通过 |
| migration-replay.json | 原隔离副本同plan重跑只回放；没有重复实体或重置状态 |
| original-v1-replay.json | 原0.2.0代码生成的虚构业务数据经明确确认迁入canonical，Submission/Interview/Offer重放逐对象相等、PDF hash一致；不以demo冒充事实迁入 |
| production-final.json | PID/0.2.0/schema1不变，数据库物理与逻辑hash、附件、生产src/scripts/dist均与开工一致 |

### Rollback / forward recovery

- `rollback-v1.json`：最新生产备份实际恢复到新 `rollback-v1` 目录，原0.2.0程序成功打开，逻辑快照与备份完全一致；不是把迁移后的数据库改回user_version1。匹配生产源码/构建另存 `production-v1-source.tar.gz`。
- `old-program-refusal.json`：把v2备份恢复到新 `old-program-probe`，原程序明确报“数据库版本高于当前应用，请使用匹配版本”，数据逻辑不变。
- `forward-recovery.json`：虚构v1→v2后实际新增机会、修改JD，再创建完整v2备份并恢复到新 `forward-restored`；新增ID和修改内容均保留。不存在可无损表示这些信息的已验逆迁移；恢复旧v1备份会丢新数据，因此禁止把它称为开写后rollback。
- 本批数据、证据、恢复副本均保留，不覆盖/删除任何生产目录。异机/磁盘故障灾备未验证。

### 实际浏览器验收

使用独立8772服务、TestProvider和虚构临时数据；没有真实AI调用。动作由实际浏览器完成，API校验只作为材料hash/持久化的补充，不替代浏览器声明。

| 编码前条件 | 观察结果 |
| --- | --- |
| U01 | 空管线无链接创建；再用 acme 创建第二岗位，显示均为首次确认的全角 ＡＣＭＥ，共用Company，不要求简历 |
| U02 | 六View逐个点击；四阶段各自正确；全部含legacy，已结束仅含明确结果，旧deleted无自动归类 |
| U03 | 点击行/Enter进入；返回保留View；刷新定位；旧jobs/tab可读；不存在ID明确不存在；外链新页打开，原列表不跳行 |
| U04 | 双窗口同revision，先保存一份JD；另一窗口409保留输入并显示当前JD；核对后加载revision明确重试成功，刷新/隔离服务重启后保留 |
| U05 | 写简历withdrawn、面试rejected、已确认Offer accepted均真实操作；阶段与2026-09-01等原阶段日保留，无Employment自动创建 |
| U06 | 阶段占位无伪造新简历/模拟/Offer动作；历史冻结正文展开可见，PDF下载链接触发，HTTP原PDF字节与artifact SHA一致；缺Greeting明确历史未记录；v2整包案例按钮禁用及说明可见 |
| U07 | 原任职页、虚构任职创建/Project创建和深链可用；独立editor.html及个人基础资料页可读；未修改这些领域实现 |

浏览器最初一页发生额外导航，发现未提交输入后保留该页并使用新测试页完成后续验证。未把该未提交输入计为已保存结果。移动设备、辅助技术完整审查与宿主下载后的系统PDF预览未作本批验证。

### workbench-review 两轴结论

规格轴：B 的创建/信息/结束/管线/基础Workspace及历史保护通过；没有声称 C–G 或四阶段完整推进通过。Company采用用户要求的确定性键；production明确不cutover。

规范轴：在开工文件hash基线上审查本批diff；无新增业务表，无两个可写机会正本，无自动历史phase/result推断；Company/Opportunity写与幂等同事务，启动/迁移双门禁，备份和恢复目的地分离。版本/PDF/Raw/Wiki及任职数据按原行hash保护。

审查发现与处理：

1. migration verifier最初只跳过被替换current，不能验证before-image；已补before-image/source-plan/schema hash一致性，并用篡改测试验证。
2. CLI最初在迁移完成后才尝试新建报告；已改为修改前独占创建，报告碰撞不写数据库。补硬链接拒绝测试。
3. inventory公司候选曾沿用区分大小写；已保留旧exact字段作为历史信息，并增加NFKC/casefold身份候选/冲突规则。
4. job-scope旧候选入口错误套入新面试门禁且引用未定义kind；已修为只读身份校验，原更正/候选测试通过。未修改Raw/Resume产品目标。
5. canonical ID作为note scope可能与旧alias漏配；新note统一alias。前端旧关联/阶段不再拥有写正本，案例按钮明确暂停。

当前未留本批阻塞缺陷。未覆盖的运行环境和后续能力如上明列，不由“无发现”推定。完整求职主链尚不能从B隔离v2接管生产。

### Gates与停止点

本次inventory没有已确认的真实用户 Migration Gate；demo冲突只是legacy兼容项。两条旧机会继续defer，若后续要求将具体真实资料变成可推进canonical，才核对company/phase/result/日期；本批不代替用户决定。

Batch C具备**在本独立worktree与隔离数据上开始规划/实施的技术前置**：唯一正本、CAS、ID resolver、备份/迁移/恢复边界已成立。C的独立ResumeDocument/Greeting/唯一Submission尚未实现；不因B通过开放生产或自动进入C。Production Cutover必须后续显式授权，并在C/E/F等必要能力接管与届时新备份/复验之后安排。
