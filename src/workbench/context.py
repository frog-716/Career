"""Public compiler for the controlled ContextPacket read model."""


class ContextCompiler:
    """Compile one transactionally consistent, provider-ready context packet.

    The compiler only reads through the Store's current-record helpers.  It
    deliberately does not accept a provider or a database connection created
    outside the caller's transaction.
    """

    schema_version = 2
    policy_version = "context-v2"

    def __init__(self, store):
        self.store = store

    def compile(self, connection, job_id, task_type, instruction="", wiki_ids=None):
        from .core import Invalid, digest
        from .knowledge import selected_wiki_sources

        if task_type not in ("job", "resume"):
            raise Invalid("分析任务不支持")
        if not isinstance(instruction, str) or len(instruction) > 10000:
            raise Invalid("指令过长")

        profile = self.store._get(connection, "profile", "profile")
        from .opportunity import active, job_view
        opportunity=active(self.store,connection,job_id)
        job=job_view(self.store,connection,job_id)
        job_id=job["id"]
        if job["status"] != "active":
            raise Invalid("岗位已删除或排除，请先恢复再分析")
        wiki = selected_wiki_sources(self.store, connection, wiki_ids, job_id)
        demo_dataset_id = job.get("demo_dataset_id")
        if demo_dataset_id:
            isolated = []
            for item in wiki:
                entry = self.store._get(connection, item["id"], "wiki_entry")
                if entry.get("demo_dataset_id") == demo_dataset_id:
                    isolated.append(item)
                elif wiki_ids and item["id"] in wiki_ids:
                    raise Invalid("案例机会只能使用同一案例数据集内的 Wiki 条目")
            wiki = isolated
        include_profile = not demo_dataset_id and profile["content"].strip()
        if not include_profile and not wiki:
            raise Invalid("请先保存基础资料或选择已确认 Wiki 条目")

        sources = []
        if include_profile:
            sources.append(self._source(
                profile["id"], profile["revision"], profile["content"],
                "current_fact", digest(profile["content"])))

        target_content = {key: job[key] for key in ("company", "title", "jd", "url")}
        sources.append(self._source(
            opportunity["id"], opportunity["revision"], target_content, "target_jd",
            digest(target_content)))

        sources.append(self._source(opportunity['company_id'],opportunity['company_revision'],
            {'id':opportunity['company_id'],'name':opportunity['company']},'company_identity',
            digest([opportunity['company_id'],opportunity['company']])))

        for item in wiki:
            selected = item.get("content")
            sources.append(self._source(
                item["id"], item["revision"], selected, item["purpose"],
                item["hash"], source_ids=item.get("source_ids", [])))

        content_size = sum(len(str(source["selected_content"])) for source in sources)
        unknowns = []
        packet = {
            "schemaVersion": self.schema_version,
            "task_type": task_type,
            "target": {"type": "opportunity", "id": opportunity["id"],
                       "job_posting_id": job_id},
            "policy_version": self.policy_version,
            "sources": sources,
            "unknowns": unknowns,
            "conflicts": [],
            "omissions": [],
            "budget_used": {
                "source_count": len(sources),
                "content_chars": content_size,
                "source_limit": 30,
                "content_limit": 100000,
            },
            "epoch": self.store._epoch(connection),
            # Compatibility fields retained for the current frontend and
            # Provider adapters while callers migrate to the public schema.
            "taskKind": task_type,
            "taskId": job_id,
            "instruction": instruction,
        }
        return packet

    @staticmethod
    def _source(source_id, revision, selected_content, purpose, source_hash,
                source_ids=None):
        source = {
            "id": source_id,
            "revision": revision,
            "hash": source_hash,
            "purpose": purpose,
            "selected_content": selected_content,
            # Existing Provider/tests consume `content`; keep it as an alias
            # until all callers use selected_content.
            "content": selected_content,
        }
        if source_ids:
            source["source_ids"] = source_ids
        return source
