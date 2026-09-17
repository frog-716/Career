# 职场中台系统

默认中文，事实、推断、未知分开。以当前用户指令为准；包内权威顺序见 [docs/00-authority.md](docs/00-authority.md)。

先读 `docs/00-authority.md`，判断任务所属业务模块，再读该模块的 authoritative docs；按任务加载 architecture / context / journey / acceptance / roadmap，具体入口见 README 文档地图。跨模块任务分别确认所属正本与边界。

`docs/audit/` 是现状证据或分析快照，不是目标规范；`docs/target/` 是目标规范，不代表已经实现。实际状态查 `docs/execution/STATUS.md` 并按需核验代码与运行证据。`docs/archive/` 仅用于历史追溯，不覆盖当前权威。

开发技能：拆批用 `$workbench-plan`；执行具体批次用 `$workbench-implement`；验收变更用 `$workbench-review`。技能路径在 `.agents/skills/`；若宿主不自动发现，读取对应 `SKILL.md` 执行即可。

先建设可运行的纵向任务闭环。资料写入与分析读取执行 `docs/02-context-contract.md`；测试用虚构资料。实际运行、模型调用、语音或浏览器结果必须真实验证才可宣称成功。

只在真实资料无法判断且阻塞任务、不可恢复数据操作、主链无法接入、根本产品取舍或必要外部能力无访问方式时报告 Gate；普通技术选择自主解决。不要恢复旧项目的票号、阶段或全量聊天。

新代码、测试命令与模块接口在对应模块README及构建配置中维护。规划状态集中在首次创建的 `docs/execution/STATUS.md`；用户确认的新产品决策修订其唯一所属文档。
