"""Canonical Employment identity with journey episode compatibility."""
import json

from fastapi import APIRouter

from .core import Conflict, Invalid, Missing, dump, now, required, uid


def canonical_id(episode_id):
    return "employment:" + episode_id


def sync_episode(store, connection, episode):
    """Keep the public Employment projection in the episode transaction."""
    ident = canonical_id(episode["id"])
    row = connection.execute(
        "SELECT revision,body FROM current WHERE id=? AND kind='employment'",
        (ident,),
    ).fetchone()
    old = json.loads(row[1]) if row else {}
    obj = dict(
        old,
        id=ident,
        legacy_episode_id=episode["id"],
        company=episode["company"],
        role=episode["role"],
        start_date=episode.get("start_date"),
        end_date=episode.get("end_date"),
        focus=episode.get("focus", ""),
        created_at=episode.get("created_at", old.get("created_at", now())),
    )
    return store._save(connection, "employment", obj, row[0] if row else 0)


def current_employments(store, connection):
    items = store._current(connection, "employment")
    seen = {item["legacy_episode_id"] for item in items}
    for episode in store._current(connection, "journey_episode"):
        if episode["id"] in seen:
            continue
        items.append(dict(
            id=canonical_id(episode["id"]), legacy_episode_id=episode["id"],
            company=episode["company"], role=episode["role"],
            start_date=episode.get("start_date"), end_date=episode.get("end_date"),
            focus=episode.get("focus", ""), revision=episode.get("revision", 0),
            created_at=episode.get("created_at"),
        ))
    return items


def _values(body):
    company = required(body.get("company"), "公司", 500)
    role = required(body.get("role"), "角色", 500)
    start = body.get("start_date") or None
    end = body.get("end_date") or None
    for value, label in ((start, "开始日期"), (end, "结束日期")):
        if value is not None:
            from datetime import date
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                raise Invalid(label + "必须是 YYYY-MM-DD 或为空") from None
    if start and end and end < start:
        raise Invalid("结束日期不能早于开始日期")
    focus = body.get("focus", "")
    if not isinstance(focus, str) or len(focus) > 100000:
        raise Invalid("重点内容超出长度限制")
    return company, role, start, end, focus


def employment_router(store):
    router = APIRouter(prefix="/api/employments")

    @router.get("")
    def read():
        with store.connect(False) as connection:
            return current_employments(store, connection)

    @router.post("")
    def create(body: dict):
        company, role, start, end, focus = _values(body)
        episode_id = uid()
        timestamp = now()
        episode = dict(id=episode_id, revision=0, company=company, role=role,
                       start_date=start, end_date=end, focus=focus,
                       created_at=timestamp, updated_at=timestamp)
        with store.connect() as connection:
            connection.execute("INSERT INTO current VALUES(?,?,?,?)",
                               (episode_id, "journey_episode", 0, dump(episode)))
            return sync_episode(store, connection, episode)

    @router.post("/{employment_id}")
    def update(employment_id: str, body: dict):
        company, role, start, end, focus = _values(body)
        expected = body.get("expected_revision")
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            raise Invalid("expected_revision 不合法")
        with store.connect() as connection:
            ident = employment_id if employment_id.startswith("employment:") else canonical_id(employment_id)
            row = connection.execute(
                "SELECT body FROM current WHERE id=? AND kind='employment'", (ident,)
            ).fetchone()
            if row:
                employment = json.loads(row[0])
                if employment["revision"] != expected:
                    raise Conflict("任职已在其它窗口更新，请重新载入")
                episode_id = employment["legacy_episode_id"]
            else:
                episode_id = ident.split(":", 1)[1]
                episode = store._get(connection, episode_id, "journey_episode")
                if episode.get("revision", 0) != expected:
                    raise Conflict("任职已在其它窗口更新，请重新载入")
            episode = store._get(connection, episode_id, "journey_episode")
            saved = store._save(connection, "journey_episode", dict(
                episode, company=company, role=role, start_date=start,
                end_date=end, focus=focus,
            ), episode.get("revision", 0))
            return sync_episode(store, connection, saved)

    return router
