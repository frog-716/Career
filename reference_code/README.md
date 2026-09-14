# 可选参考代码

仅在建设备份或简历时读取。这里没有旧系统完整后端、UI、数据库和平台依赖，不承担产品主链。

- [sqlite_archive.py](sqlite_archive.py)：从历史项目一致性备份做法提炼的独立SQLite复制函数。只用Python标准库；读取现有数据库，以排他方式创建新目标，检查一致性；已有目标不覆盖。恢复就是把备份复制到新的隔离路径。
- [测试](tests/test_sqlite_archive.py)：真实临时SQLite验证数据、WAL、覆盖保护、失败清理。
- [简历迁出说明](resume-local-seam.md)：明确可复用的接缝、平台替换项和PDF验收，不携带旧简历内容或整个妙搭SDK。

运行：在包根执行 `python3 -B -m unittest discover -s reference_code/tests -v`。需要Python 3.9+。本片段不是完整备份系统：多数据库/附件的一致清单、加密、备份调度、容量管理与恢复UI需要新项目另行实现。

引用它不会自动改变新系统结构。Astra可在Artifacts模块内采用并适配；不要将这个目录当成未来模块架构。
