# Career OS · 职场中台系统

当前 MVP 实施与验收见 [STATUS](docs/execution/STATUS.md)。本地启动：

```sh
.venv/bin/python scripts/run.py
```

首次安装、AI 配置、测试和备份恢复见 [服务 README](src/workbench/README.md)。入口 http://127.0.0.1:8765，生产数据与代码分离。

## 启动包说明（保留来源）

版本：1.0 · 2026-09-14。用途：解压后作为全新本地项目的根目录，交给 Astra 主控、Luna 执行。此包是精选需求、工程契约、工作技能和可运行参考代码，不是已完成应用，也不包含用户业务数据库。

## 开始使用

1. 将 zip 解压到一个新目录；以其中 `workplace-workbench-kit/` 为项目根，可自行改名。不要覆盖已有项目。
2. 在开发工具中打开该根目录，选择 Astra + high。模型分工见 [协作说明](docs/06-agent-workflow.md)。
3. 把 [完整启动提示词](prompts/START.md) 全文粘贴到新对话。
4. 若要用项目配置固定模型，先核对本机支持，再将 `config-templates/codex-config.toml.example` 复制为新项目 `.codex/config.toml`。模板不修改全局配置，不包含凭据或权限覆盖。
5. 无需旧仓库、旧对话、妙搭登录或真实简历即可完成工程启动。真实资料和模型凭据通过新应用后续导入/配置。

启动前可独立验证包：`python3 -B scripts/verify_bundle.py`。参考代码测试：`python3 -B -m unittest discover -s reference_code/tests -v`。二者只验证交付包，不代表新系统通过业务验收。

包在新项目修改前可用 `--strict` 完整核验；开发改动后清单自然不再匹配，不应把它当业务回归测试。重新打包可用 `python3 -B scripts/build_bundle.py --output ../new-kit.zip`；仅对自己生成的可信包运行 `python3 -B scripts/check_archive.py ../new-kit.zip` 做隔离解压验收。

## 目录和读取规则

| 位置 | 内容 | 什么时候读 |
| --- | --- | --- |
| `AGENTS.md` | 精简项目入口、权威顺序、协作约束 | 自动/首先 |
| `docs/00-authority.md` | 已确认需求、建议与未知的优先级 | 首轮 |
| `docs/01-product.md` | 产品目标、用户任务、界面要求、做不了的部分 | 首轮 |
| `docs/02-context-contract.md` | 最新上下文、原件、提案、并发与隔离契约 | 首轮和资料/AI开发 |
| `docs/03-architecture.md` | 深模块、数据对象、落盘、扩展与维护 | 首轮和架构修改 |
| `docs/04-journeys.md` | 全链路场景的输入、输出和边界 | 对应功能开发 |
| `docs/05-acceptance.md` | 可执行验收、质量与不能冒充完成的情况 | 拆批和验收 |
| `docs/06-agent-workflow.md` | Astra/Luna职责、派工、评审与恢复执行 | 派工 |
| `docs/07-roadmap.md` | 分批顺序、交付范围、状态记录规则 | 首轮 |
| `docs/08-provenance.md` | 筛选依据、剔除项、官方资料及已知限制 | 溯源 |
| `prompts/` | 主控启动、Luna任务、后续恢复提示词 | 对应时机 |
| `.agents/skills/` | 三个自洽、项目专用开发技能 | 按description触发 |
| `reference_code/` | 独立SQLite备份参考与测试；简历迁出接缝说明 | 做备份/简历时 |
| `fixtures/` | 明确虚构的求职与任职验收案例 | 开发和测试 |
| `config-templates/` | 可选Codex模型分工配置 | 核对宿主支持后 |
| `scripts/` | 校验、可重建zip工具 | 打包与验收 |
| `MANIFEST.json` | 每文件大小和SHA-256 | 校验 |
| `PACKAGING-REPORT.md` | 本批实际验证结果 | 交付审查 |

工程规范通过链接按需读；个人事实只能来自新项目的运行时资料存储。不要把整个包作为产品AI的“个人记忆”。
