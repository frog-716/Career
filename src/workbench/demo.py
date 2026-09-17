"""Load and remove one isolated, synthetic end-to-end dataset."""
import hashlib
import json
from pathlib import Path

from fastapi import APIRouter

from .artifacts import write_pdf, read_artifact
from .core import Conflict, Invalid, Missing, digest, dump, now


DATASET_ID = "career-os-b5-demo-v1"
PREFIX = "demo-b5-"
PDF_ID = PREFIX + "resume-pdf"
PDF_PATH = "artifacts/" + PDF_ID + ".pdf"


def _body(id, **values):
    return dict(id=id, demo_dataset_id=DATASET_ID, **values)


def _manifest_body(manifest):
    return _body(DATASET_ID, manifest=manifest, created_at=now())


def _current(store, c, manifest, kind, obj, expected=0):
    result = store._save(c, kind, obj, expected)
    manifest["current"].append({"id": result["id"], "kind": kind})
    rows = c.execute("SELECT revision FROM current WHERE id=?", (result["id"],)).fetchone()
    manifest["revisions"].append({"id": result["id"], "revision": rows[0]})
    return result


def _record(store, c, manifest, kind, obj):
    store._record(c, kind, obj)
    manifest["records"].append({"id": obj["id"], "kind": kind})
    return obj


def _collision(c, ident):
    return bool(c.execute("SELECT 1 FROM current WHERE id=?", (ident,)).fetchone()
                or c.execute("SELECT 1 FROM records WHERE id=?", (ident,)).fetchone()
                or c.execute("SELECT 1 FROM applications WHERE id=?", (ident,)).fetchone())


def _check_ids(c, ids):
    for ident in ids:
        if _collision(c, ident):
            raise Conflict("演示数据标识已被占用：" + ident)


def _source_set(store, c, manifest, episode_id, job_id):
    sources = []
    candidates = []
    entries = []
    values = [
        ("strategy", "[案例] 机会判断依据", "岗位需要可验证的产品交付与跨团队协作案例。", "confirmed", "job", job_id),
        ("capability", "[案例] 待确认的交付能力", "能够拆解问题、推进协作并复盘结果。", "pending", "job", job_id),
        ("achievement", "[案例] 待确认的项目成果", "在跨团队项目中完成关键交付并保留证据。", "pending", "episode", episode_id),
    ]
    for index, (entry_type, title, content, status, scope_type, scope_id) in enumerate(values, 1):
        sid = f"{PREFIX}wiki-source-{index}"
        cid = f"{PREFIX}wiki-candidate-{index}"
        eid = f"{PREFIX}wiki-entry-{index}"
        source = _body(sid, title=title + "原始来源", content=content + "（原始材料）",
                       source_type="text", locator="demo://wiki/" + str(index),
                       scope_type=scope_type, scope_id=scope_id,
                       semantics="仅用于全链路案例演练", created_at=now())
        _record(store, c, manifest, "knowledge_source", source)
        candidate = _body(cid, status=status, entry_id=eid if status == "confirmed" else None, created_at=now(),
                          source_ids=[sid], entry_type=entry_type, title=title,
                          content=content, scope_type=scope_type, scope_id=scope_id,
                          verification="demo", resolved_at=now() if status == "confirmed" else None)
        _current(store, c, manifest, "knowledge_candidate", candidate)
        if status == "confirmed":
            entry = _body(eid, title=title, content=content, entry_type=entry_type,
                          scope_type=scope_type, scope_id=scope_id, source_ids=[sid],
                          status="active", verification="demo", created_at=now())
            _current(store, c, manifest, "wiki_entry", entry)
            entries.append(entry)
        sources.append(source); candidates.append(candidate)
    return sources, candidates, entries


def _load_dataset(store):
    data_dir = Path(store.data_dir)
    pdf_written = False
    manifest = {"schemaVersion": 1, "dataset_id": DATASET_ID, "current": [],
                "records": [], "applications": [], "revisions": [], "artifacts": [PDF_PATH]}
    all_ids = [
        DATASET_ID, PREFIX + "episode", "employment:" + PREFIX + "episode",
        PREFIX + "stage", PREFIX + "job", "opportunity:" + PREFIX + "job",
        PREFIX + "plan", PREFIX + "company", PREFIX + "org", PREFIX + "role",
        PREFIX + "cycle", "opportunity-context:" + PREFIX + "job", PREFIX + "research",
        PREFIX + "communication", PREFIX + "interview", PREFIX + "offer",
        PREFIX + "research-snapshot", PREFIX + "communication-activity",
        PREFIX + "interview-activity", PREFIX + "offer-activity",
        PREFIX + "project", PREFIX + "project-source", PREFIX + "person",
        PREFIX + "participant", PREFIX + "work-event", PREFIX + "achievement",
        PREFIX + "evidence", PREFIX + "evidence-link", PREFIX + "version",
        PREFIX + "resume-use", PREFIX + "submission", PREFIX + "analysis", PREFIX + "feedback",
    ] + [f"{PREFIX}wiki-{kind}-{n}" for kind in ("source", "candidate", "entry") for n in range(1, 4)]
    with store.connect() as c:
        existing_manifest = c.execute("SELECT body FROM records WHERE id=? AND kind='demo_manifest'", (DATASET_ID,)).fetchone()
        if existing_manifest:
            old = json.loads(existing_manifest[0])
            if old.get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示数据清单标识冲突")
            return {"dataset_id": DATASET_ID, "status": "already_loaded", "manifest": old["manifest"]}
        _check_ids(c, all_ids)
        if (data_dir / PDF_PATH).exists():
            raise Conflict("演示 PDF 路径已被占用")
        try:
            episode_id = PREFIX + "episode"
            episode = _body(episode_id, revision=0, company="[案例] 澄明科技", role="产品与交付负责人",
                             start_date="2021-04-01", end_date="2024-08-31",
                             focus="在多团队协作中推动数据产品从试点走向稳定交付",
                             created_at=now(), updated_at=now())
            c.execute("INSERT INTO current VALUES(?,?,?,?)", (episode_id, "journey_episode", 0, dump(episode)))
            manifest["current"].append({"id": episode_id, "kind": "journey_episode"})
            employment_id = "employment:" + episode_id
            employment = _current(store, c, manifest, "employment", _body(
                employment_id, legacy_episode_id=episode_id, company=episode["company"],
                role=episode["role"], start_date=episode["start_date"], end_date=episode["end_date"],
                focus=episode["focus"], created_at=episode["created_at"],
            ))
            _current(store, c, manifest, "work_employment_stage", _body(
                PREFIX + "stage", employment_id=employment["id"], name="[案例] 产品稳定交付阶段",
                start_date="2022-01-01", end_date="2023-12-31",
                focus="统一指标口径并推动看板从试点进入稳定交付", status="completed",
                created_at=now(),
            ))

            company = _current(store, c, manifest, "domain_company", _body(PREFIX + "company", kind="company", name="[案例] 澄明科技", description="虚构企业数据产品公司", created_at=now()))
            org = _current(store, c, manifest, "domain_org_unit", _body(PREFIX + "org", kind="org_unit", name="[案例] 增长平台组", description="负责增长与数据平台", company_id=company["id"], parent_id=None, created_at=now()))
            role = _current(store, c, manifest, "domain_target_role", _body(PREFIX + "role", kind="target_role", name="[案例] 数据产品负责人", description="虚构目标方向", created_at=now()))
            cycle = _current(store, c, manifest, "domain_search_cycle", _body(PREFIX + "cycle", kind="search_cycle", name="[案例] 2026 秋季周期", description="演示求职周期", created_at=now()))
            job = _current(store, c, manifest, "job", _body(PREFIX + "job", company="[案例] 远岑软件", title="高级产品经理", jd="负责数据产品策略、跨团队交付与结果复盘。", url="https://example.test/demo-job", status="active", source="demo", created_at=now()))
            opportunity = _current(store, c, manifest, "opportunity", _body("opportunity:" + job["id"], legacy_job_id=job["id"], company=job["company"], title=job["title"], jd=job["jd"], url=job["url"], status="active", source="demo", created_at=job["created_at"]))
            _current(store, c, manifest, "opportunity_context", _body("opportunity-context:" + job["id"], job_id=job["id"], company_id=company["id"], org_unit_id=org["id"], target_role_id=role["id"], search_cycle_id=cycle["id"]))
            _current(store, c, manifest, "journey_plan", _body(PREFIX + "plan", job_id=job["id"], stage="interview", next_action="准备第二轮案例复盘", due_date="2026-09-18", created_at=now()))

            raw_notes = {}
            for kind, title, content in (("research", "[案例] 公司研究", "研究原始记录：客户结构与产品线待进一步核实。"), ("communication", "[案例] 沟通记录", "沟通原始记录：招聘方确认下一轮关注跨团队推进。"), ("interview", "[案例] 面试复盘", "面试原始记录：回答了指标拆解和冲突处理案例。"), ("offer", "[案例] Offer 原文", "Offer 原始记录：薪酬与入职时间仍待人工核对。")):
                ident = PREFIX + kind
                raw_notes[kind] = _record(store, c, manifest, "journey_note", _body(ident, scope_type="job", scope_id=job["id"], kind=kind, title=title, content=content, submission_id=None, idempotency_key=ident, created_at=now()))
            _source_set(store, c, manifest, episode_id, job["id"])

            project = _current(store, c, manifest, "work_project", _body(PREFIX + "project", name="[案例] 客户数据看板升级", description="从试点到稳定交付的虚构项目", scope_type="employment", scope_id=employment["id"], created_at=now()))
            _record(store, c, manifest, "work_project_source", _body(PREFIX + "project-source", project_id=project["id"], scope_type="employment", scope_id=employment["id"], title="[案例] 任职项目来源", content="项目复盘原文", semantics="任职期间的用户原始项目记录", created_at=now()))
            person = _current(store, c, manifest, "work_person", _body(PREFIX + "person", name="[案例] 林岚", role="数据分析师", created_at=now()))
            _record(store, c, manifest, "work_project_participant", _body(PREFIX + "participant", project_id=project["id"], person_id=person["id"], person_revision=person["revision"], role="共同推进", created_at=now()))
            _record(store, c, manifest, "work_event", _body(PREFIX + "work-event", target_type="project", target_id=project["id"], title="交付节点", kind="delivery", content="原始事件：完成指标口径统一并上线第一版看板。", created_at=now()))
            achievement = _current(store, c, manifest, "work_achievement", _body(PREFIX + "achievement", project_id=project["id"], title="[案例] 看板交付成果", content="完成跨团队指标统一和看板上线。", created_at=now()))
            evidence = _record(store, c, manifest, "work_evidence", _body(PREFIX + "evidence", scope_type="project", scope_id=project["id"], title="[案例] 验收记录", source_type="document", content="不可变证据：验收记录显示首版按期上线。", created_at=now()))
            _record(store, c, manifest, "work_evidence_link", _body(PREFIX + "evidence-link", achievement_id=achievement["id"], evidence_id=evidence["id"], achievement_revision=achievement["revision"], evidence_created_at=evidence["created_at"], created_at=now()))

            document = {"schemaVersion": 1, "profile": {"id": "demo-profile", "name": "周岚", "contacts": []}, "sections": [{"id": "demo-experience", "type": "experience", "title": "工作经历", "items": [{"id": "demo-item", "organization": "澄明科技", "role": "产品与交付负责人", "date": "2021-04—2024-08", "bullets": [{"id": "demo-bullet", "content": "推动数据产品稳定交付"}]}]}], "formatting": {}, "meta": {"title": "周岚 · 数据产品负责人"}}
            pdf = write_pdf(data_dir, PDF_ID, "周岚\n高级产品经理\n数据产品策略与跨团队交付\n虚构演示材料")
            pdf_written = True
            version = _body(PREFIX + "version", name="[案例] 数据产品方向正式版", createdAt=now(), document=document, artifact_id=PDF_ID, idempotency_key=PREFIX + "version-key", request_fingerprint=digest(document))
            _record(store, c, manifest, "artifact", _body(PDF_ID, version_id=version["id"], **pdf))
            _record(store, c, manifest, "editor_version", version)
            use = _body(PREFIX + "resume-use", scope_type="opportunity", scope_id=opportunity["id"], target_name=opportunity["company"] + " · " + opportunity["title"], version_id=version["id"], version_name=version["name"], artifact_id=PDF_ID, artifact_hash=pdf["sha256"], created_at=now())
            _record(store, c, manifest, "resume_use", use)
            applied_at = "2026-03-20T10:00:00+08:00"
            channel = "演示招聘平台"
            status = "applied"
            submission = _body(PREFIX + "submission", job_id=job["id"], opportunity_id=opportunity["id"], version_id=version["id"], artifact_id=PDF_ID, applied_at=applied_at, status=status, channel=channel, version_kind="editor_version", request_fingerprint=digest([opportunity["id"], version["id"], PDF_ID, applied_at, channel, status]), status_history=[{"status": status, "changed_at": now(), "source": "created"}], job_snapshot=job, opportunity_snapshot={"opportunity": opportunity, "job_posting": job, "context": {"company_id": company["id"], "org_unit_id": org["id"], "target_role_id": role["id"], "search_cycle_id": cycle["id"]}, "relations": {"company_id": company, "org_unit_id": org, "target_role_id": role, "search_cycle_id": cycle}}, resume_snapshot=version, artifact_snapshot=dict(pdf, id=PDF_ID, version_id=version["id"]))
            c.execute("INSERT INTO applications VALUES(?,?,?,?,?,?)", (submission["id"], job["id"], version["id"], PDF_ID, PREFIX + "submission-key", dump(submission)))
            manifest["applications"].append(submission["id"])

            _record(store, c, manifest, "research_snapshot", _body(
                PREFIX + "research-snapshot", captured_at=raw_notes["research"]["created_at"],
                source_locator="demo://research/company", content=raw_notes["research"]["content"],
                opportunity_ids=[opportunity["id"]], raw_note_id=raw_notes["research"]["id"],
                created_at=raw_notes["research"]["created_at"],
            ))
            _record(store, c, manifest, "communication", _body(
                PREFIX + "communication-activity", opportunity_id=opportunity["id"],
                occurred_at=raw_notes["communication"]["created_at"], channel="演示招聘平台",
                participants=["[案例] 招聘方"], outcome="约定第二轮面试",
                raw_note_id=raw_notes["communication"]["id"], created_at=raw_notes["communication"]["created_at"],
            ))
            _record(store, c, manifest, "interview", _body(
                PREFIX + "interview-activity", opportunity_id=opportunity["id"],
                submission_id=submission["id"], round="第二轮", occurred_at=raw_notes["interview"]["created_at"],
                participants=["[案例] 业务负责人"], outcome="待补充案例复盘",
                raw_note_id=raw_notes["interview"]["id"], created_at=raw_notes["interview"]["created_at"],
            ))
            _record(store, c, manifest, "offer", _body(
                PREFIX + "offer-activity", opportunity_id=opportunity["id"],
                occurred_at=raw_notes["offer"]["created_at"], terms={"薪酬": "待人工核对"},
                status="pending", raw_note_id=raw_notes["offer"]["id"],
                created_at=raw_notes["offer"]["created_at"],
            ))

            packet_source = {"id": job["id"], "revision": job["revision"], "hash": digest(job["jd"]), "purpose": "target_jd", "selected_content": job["jd"], "content": job["jd"]}
            run = _body(PREFIX + "analysis", idempotency_key=PREFIX + "analysis-key", request_fingerprint=digest([job["id"], "job"]), kind="job", job_id=job["id"], status="succeeded", packet={"schemaVersion": 2, "task_type": "job", "target": {"type": "opportunity", "id": opportunity["id"]}, "policy_version": "context-v2", "taskKind": "job", "taskId": job["id"], "sources": [packet_source], "unknowns": ["客户规模尚未核实"], "conflicts": [], "omissions": [], "budget_used": {"source_count": 1, "content_chars": len(job["jd"])}, "epoch": 0}, payload={"model": "synthetic-demo", "sources": [job["id"]]}, result={"core_goal": "完成数据产品交付", "requirements": ["跨团队推进"], "hard_gates": [], "evidence": ["案例项目可供核对"], "gaps": ["客户规模未知"], "expression_issues": [], "priorities": ["准备项目复盘"], "investment": "继续准备", "claims": [{"kind": "Fact", "text": "岗位要求跨团队交付", "source_ids": [job["id"]]}]}, provider={"mode": "test", "model": "synthetic-demo"}, created_at=now())
            _record(store, c, manifest, "run", run)
            _record(store, c, manifest, "feedback", _body(PREFIX + "feedback", text="演示反馈：请继续核对面试原话。", created_at=now(), app_version="demo", current_page="demo", entity_id=job["id"], notes=[]))

            _record(store, c, manifest, "demo_manifest", _manifest_body(manifest))
            return {"dataset_id": DATASET_ID, "status": "loaded", "manifest": manifest}
        except Exception:
            if pdf_written:
                try:
                    read_artifact(data_dir, PDF_PATH).unlink()
                except Exception:
                    pass
            raise


def _remove_dataset(store):
    data_dir = Path(store.data_dir)
    with store.connect() as c:
        row = c.execute("SELECT body FROM records WHERE id=? AND kind='demo_manifest'", (DATASET_ID,)).fetchone()
        if not row:
            raise Missing("演示数据集不存在")
        manifest_record = json.loads(row[0])
        if manifest_record.get("demo_dataset_id") != DATASET_ID:
            raise Conflict("演示数据集清单归属不一致")
        manifest = manifest_record["manifest"]
        for item in manifest["current"]:
            body = store._get(c, item["id"], item["kind"])
            if body.get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示数据对象归属不一致：" + item["id"])
        for item in manifest["records"]:
            body = store._get(c, item["id"], item["kind"], True)
            if body.get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示记录归属不一致：" + item["id"])
        for ident in manifest["applications"]:
            found = c.execute("SELECT body FROM applications WHERE id=?", (ident,)).fetchone()
            if not found or json.loads(found[0]).get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示投递归属不一致：" + ident)
        for path in manifest["artifacts"]:
            if not path.startswith("artifacts/"):
                raise Invalid("演示附件路径不合法")
            artifact = c.execute("SELECT body FROM records WHERE kind='artifact' AND json_extract(body,'$.path')=?", (path,)).fetchone()
            if not artifact or json.loads(artifact[0]).get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示附件归属不一致：" + path)
        for item in manifest["revisions"]:
            row = c.execute("SELECT body FROM revisions WHERE id=? AND revision=?", (item["id"], item["revision"])).fetchone()
            if not row or json.loads(row[0]).get("demo_dataset_id") != DATASET_ID:
                raise Conflict("演示历史归属不一致：" + item["id"])
        for ident in manifest["applications"]:
            c.execute("DELETE FROM applications WHERE id=?", (ident,))
        for item in manifest["current"]:
            c.execute("DELETE FROM current WHERE id=? AND kind=?", (item["id"], item["kind"]))
        for item in manifest["records"]:
            c.execute("DELETE FROM records WHERE id=? AND kind=?", (item["id"], item["kind"]))
        for item in manifest["revisions"]:
            c.execute("DELETE FROM revisions WHERE id=? AND revision=?", (item["id"], item["revision"]))
        for path in manifest["artifacts"]:
            target = data_dir / path
            if target.exists():
                target.unlink()
        c.execute("DELETE FROM records WHERE id=? AND kind='demo_manifest'", (DATASET_ID,))
        return {"dataset_id": DATASET_ID, "status": "removed"}


def demo_router(store):
    router = APIRouter()

    @router.post("/api/demo/load")
    def load():
        return _load_dataset(store)

    @router.post("/api/demo/remove")
    def remove():
        return _remove_dataset(store)

    return router
