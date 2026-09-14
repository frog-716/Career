# 来源、筛选与限制

核对日：2026-09-14。此包面向新项目，下面的旧源定位仅用于溯源，不是需要加载的外部依赖。

## 筛选依据

主要需求来自用户最新“个人职场工作台”完整需求，以及本轮“精选zip、Astra高规划/Luna中执行”要求。旧项目 `docs/tickets/personal-workbench/spec.md` 中与这些要求一致的设计已按职责重新组织；不复制旧文件形成第二正本。

| 旧材料 | 保留内容 | 处理 |
| --- | --- | --- |
| 新职场工作台设计 | 最新资料协议、求职/任职链、深模块、可行性 | 凝练为docs/01–07，区分用户需求与工程建议 |
| V1数据库与测试 | SQLite一致性备份思路、快照/投递/原文语义 | 只提取备份参考；整套旧schema/Store/UI不带入 |
| 新版妙搭简历本地代码 | 生成PDF与存储解耦、保存编辑源和原件 | 写成简历接缝说明，不复制平台包/数据/凭据 |
| 项目工作规范与技能 | 深模块、按需上下文、主路径验证、双轴审查 | 新建三个短技能，删除旧票据工具链依赖 |
| 旧线程与V2演示 | 教训：任务驱动、输入负担、演示不能冒充AI | 只保留明确产品准则；不携带聊天、预设分析与单向流程 |

## 明确剔除

真实姓名/联系方式/任职背景/简历内容、业务SQLite、PDF、聊天、录音、账号配置、环境文件、私有线上URL、本机绝对路径、node_modules、Git历史、缓存、旧票号/Gate与暂停状态、旧后台页面、Miaoda鉴权和对象存储绑定、固定方向枚举、演示AI、强制手填评分/改进答案。

没有把未知个人事实重写成干净的“新事实”。用户数据留在旧环境；新项目从资料入口明确导入。新包不自动读取或迁移原项目。

## 代码出处与改动

`reference_code/sqlite_archive.py` 根据旧项目 `career-hub/career_hub/database.py` 中backup/restore方法重写成独立函数，去掉旧schema、类依赖和路径绑定；补充源文件只读、目标排他创建、完整性检查。它只处理一个SQLite文件，不包含附件清单、版本迁移或生产备份调度。

参考测试在临时目录使用虚构内容；运行结果记录在PACKAGING-REPORT。它是可选参考，Astra可采用或替换，不属于新系统已实现功能。

技能为本轮项目专用新写内容，吸收深模块与按需读取原则；没有复制不明许可的第三方仓库。备份参考来自用户现有项目，随个人内部开发包交付，不额外宣称对旧项目拥有开源授权。

## 官方依据（按需核验，链接无需启动时联网）

- SQLite适合本地单应用：[适用场景](https://www.sqlite.org/whentouse.html)。
- 运行中一致备份：[SQLite Backup API](https://www.sqlite.org/backup.html)。
- 本地PDF生成与path输出：[Playwright page.pdf](https://playwright.dev/docs/api/class-page#page-pdf)。
- 离线ASR与本机能力限制：[whisper.cpp](https://github.com/ggml-org/whisper.cpp)。
- 本地LLM显式messages：[llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)。
- 本地TTS候选，须选音色并核对许可：[Piper](https://github.com/OHF-Voice/piper1-gpl)。
- 按公司公开岗位，不等于全网覆盖：[Lever Postings API](https://github.com/lever/postings-api)、[Greenhouse Job Board](https://docs.greenhouse.io/job-board.html)。
- Codex可配置子代理模型与推理档位：[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)。模型在新宿主的实际权限仍需检查。

本包没有下载模型或依赖，没有测试真实语音，没有导出线上妙搭历史，也没有验证招聘账号。以上是可行性依据，不是实现成果。
