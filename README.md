# Career

当前 MVP 实施与验收见 [STATUS](docs/execution/STATUS.md)。本地启动：

```sh
.venv/bin/python scripts/run.py
```

macOS 用户可以双击项目内的 `macos/Career.app` 启动。它会复用已运行的服务；服务未运行时会在后台启动，并用 Google Chrome 打开用户在导航栏右键设置的默认首页。该行为只影响 `Career.app`，不会修改 macOS 的系统默认浏览器。

App 图标源文件为 `macos/career-icon.png`，生成器会自动制作标准 macOS `Career.icns` 并写入 App；重新生成 App 时会保留该图标。

手动控制本地服务：

```sh
# 启动并打开工作台
.venv/bin/python scripts/macos_app.py start
# 查看状态
.venv/bin/python scripts/macos_app.py status
# 停止由 macOS App 管理的服务
.venv/bin/python scripts/macos_app.py stop
```

如果项目目录发生移动，重新运行 `.venv/bin/python scripts/install_macos_app.py` 生成 App，以更新 App 内保存的项目路径。启动器代码独立放在 `scripts/macos_app.py`，不混入业务模块。

运行边界：生产业务数据保存在 `~/Library/Application Support/Career Data`，这是代码工作空间之外的持久化正本，避免重建代码时误删资料；备份保存在同级的 `Career Data-backups`。App 的 PID 和日志只放在项目内的 `.career-runtime/`。测试必须通过 `CAREER_DATA_DIR` 指向临时隔离目录并使用虚构资料，不得读取或写入生产目录。除 macOS 系统字体等平台依赖外，Python 虚拟环境、前端依赖和构建产物都在项目工作空间内。

每周备份已安装为 macOS 用户级任务，每周一 00:00 运行一次，按周一日期生成 `Career Data-backups/YYYYMMDD`。管理命令：`.venv/bin/python scripts/install_weekly_backup.py status|uninstall|install`；备份脚本支持 `--dry-run` 查看目标路径，不会提前生成正式备份。

测试资料位置：单元测试使用 pytest 自动创建的 `tmp_path` 临时目录，测试结束后清理；浏览器隔离测试使用 `/tmp/career-*` 临时目录；虚构输入样例在 [`fixtures/scenarios.json`](fixtures/scenarios.json)。

首次安装、AI 配置、测试和备份恢复见 [服务 README](src/workbench/README.md)。入口 http://127.0.0.1:8765，生产数据与代码分离。

## 文档与目录

| 位置 | 内容 | 什么时候读 |
| --- | --- | --- |
| `AGENTS.md` | 精简项目入口、权威顺序、执行约束 | 自动/首先 |
| [docs/00-authority.md](docs/00-authority.md) | 模块权威、冲突规则、目标与证据的区别 | 首先读取，再判断任务模块 |
| [Opportunity Product Model](docs/target/opportunity/opportunity-product-model.md) | Opportunity产品目标正本 | 所有Opportunity任务 |
| [Opportunity Domain Model](docs/target/opportunity/opportunity-domain-model.md) | Opportunity领域语义正本 | 所有Opportunity任务 |
| [Opportunity UI Flow](docs/target/opportunity/opportunity-ui-flow.md) | Opportunity用户动作正本 | 所有Opportunity任务 |
| [Context & Ingestion](docs/target/opportunity/context-ingestion.md) | 本周期资料与AI生命周期正本 | 所有Opportunity任务及相关资料/AI边界变更 |
| [docs/01-product.md](docs/01-product.md) | 产品总览、非本期模块边界 | 对应产品任务，不能覆盖模块正本 |
| [docs/02-context-contract.md](docs/02-context-contract.md) | 当前机制与目标Context合同 | 资料/AI任务完整读取 |
| [docs/03-architecture.md](docs/03-architecture.md) | Current Architecture、Stable Contracts、Target Direction | 接口、架构、持久化及工程审查 |
| [docs/04-journeys.md](docs/04-journeys.md) | 场景输入、动作、产出与状态变化 | 对应功能开发 |
| [docs/05-acceptance.md](docs/05-acceptance.md) | Target acceptance及验证边界 | 拆批、实施和验收读取相关条目 |
| [docs/07-roadmap.md](docs/07-roadmap.md) | Current / Next / Later范围和推进顺序 | 拆批与范围调整 |
| [docs/execution/STATUS.md](docs/execution/STATUS.md) | 当前交付、已知问题和本批状态 | 核对现状与下一步；不是产品规格 |
| [AS-IS System Map](docs/audit/AS-IS-system-map.md) | 现状证据快照 | 核对代码/运行/测试边界，不作目标规范 |
| [Opportunity Gap Analysis](docs/audit/OPPORTUNITY-GAP-ANALYSIS.md) | 差异、迁移与增量批次建议快照 | 规划迁移和重构；不代表实施授权或完成 |
| `.agents/skills/` | `mattpocock/skills` 通用技能与 Career 专用技能 | 按description触发 |
| `fixtures/` | 明确虚构的求职与任职验收案例 | 开发和测试 |
| `src/workbench/` | 本地服务、领域模块、备份和 Provider | 运行及后端开发 |
| `frontend/` | 任务工作区与结构化简历编辑器 | 前端开发与构建 |
| `tests/` | 当前 Interface 和关键用户链路回归 | 与改动风险相称地运行 |
| `scripts/` | 启动、备份和 macOS 本地工具 | 对应运维动作 |
| `docs/archive/` | 已退出当前链路的启动包、旧契约和历史证据 | 仅做来源追溯 |

工程规范通过链接按需读；个人事实只能来自运行时资料存储。不要把源码、历史证据或归档材料作为产品 AI 的“个人记忆”。
