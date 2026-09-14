# 职场中台系统

默认中文，事实、推断、未知分开。以当前用户指令为准；包内权威顺序见 [docs/00-authority.md](docs/00-authority.md)。

首次开发依次读 `docs/00-authority.md`、`docs/01-product.md`、`docs/02-context-contract.md`、`docs/03-architecture.md`、`docs/07-roadmap.md`。其他文档按 README 的触发条件加载。只按需读取 reference_code，避免旧实现反推产品。

用户授权后台临时协作：Astra + high 负责规划、接口与最终验收，Luna + medium 负责有验收标准的执行任务。按 [协作契约](docs/06-agent-workflow.md) 派工；不能把说明文字当作已切换模型的证据。每名执行者只改派发文件，不创建用户可见的新任务、分支、worktree或侧边栏项目。

开发技能：拆批用 `$workbench-plan`；执行具体批次用 `$workbench-implement`；验收变更用 `$workbench-review`。技能路径在 `.agents/skills/`；若宿主不自动发现，读取对应 `SKILL.md` 执行即可。

先建设可运行的纵向任务闭环。资料写入与分析读取执行 `docs/02-context-contract.md`；测试用虚构资料。实际运行、模型调用、语音或浏览器结果必须真实验证才可宣称成功。

只在真实资料无法判断且阻塞任务、不可恢复数据操作、主链无法接入、根本产品取舍或必要外部能力无访问方式时报告 Gate；普通技术选择自主解决。不要恢复旧项目的票号、阶段或全量聊天。

新代码、测试命令与模块接口在对应模块README及构建配置中维护。规划状态集中在首次创建的 `docs/execution/STATUS.md`；用户确认的新产品决策修订其唯一所属文档。
