import json

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import Store
from workbench.providers import TestProvider


H = {"X-Career-Request": "1"}


def post(c, path, body):
    return c.post("/api" + path, json=body, headers=H)


def test_typed_activity_keeps_raw_note_and_is_restartable(tmp_path):
    store = Store(tmp_path / "data", TestProvider())
    c = TestClient(create_app(store))
    store.save_profile("当前资料", 0)
    job = post(c, "/jobs", {"company": "虚构公司", "title": "岗位", "jd": "JD", "idempotency_key": "job1"}).json()
    second = post(c, "/jobs", {"company": "另一公司", "title": "岗位", "jd": "JD2", "idempotency_key": "job2"}).json()
    opportunity = "opportunity:" + job["id"]
    second_opportunity = "opportunity:" + second["id"]

    research = post(c, "/opportunity-activity/research", {
        "opportunity_ids": [opportunity, second_opportunity], "captured_at": "2026-09-15T10:00:00Z",
        "source_locator": "https://example.test/research", "content": "研究原文", "title": "研究",
        "idempotency_key": "research-1",
    })
    assert research.status_code == 200, research.text
    communication = post(c, "/opportunity-activity/communication", {
        "opportunity_id": opportunity, "occurred_at": "2026-09-15T11:00:00Z",
        "channel": "邮件", "participants": ["招聘方"], "content": "沟通原文",
        "outcome": "约定面试", "idempotency_key": "communication-1",
    })
    assert communication.status_code == 409, communication.text
    interview = post(c, "/opportunity-activity/interview", {
        "opportunity_id": opportunity, "occurred_at": "2026-09-16T11:00:00Z",
        "round": "一面", "participants": ["面试官"], "content": "面试原文",
        "outcome": "待反馈", "idempotency_key": "interview-1",
    })
    assert interview.status_code == 409, interview.text
    offer = post(c, "/opportunity-activity/offer", {
        "opportunity_id": opportunity, "occurred_at": "2026-09-17T11:00:00Z",
        "terms": {"薪资": "待核对"}, "status": "pending", "content": "Offer 原文",
        "idempotency_key": "offer-1",
    })
    assert offer.status_code == 409, offer.text
    assert post(c, "/opportunity-activity/communication", {
        "opportunity_id": opportunity, "occurred_at": "2026-09-15T11:00:00Z",
        "channel": "邮件", "participants": ["招聘方"], "content": "沟通原文",
        "outcome": "约定面试", "idempotency_key": "communication-1",
    }).status_code == 409

    activity = c.get("/api/opportunity-activity").json()
    assert len(activity["research_snapshots"]) == 1
    assert activity["research_snapshots"][0]["opportunity_ids"] == [opportunity, second_opportunity]
    assert activity["communications"] == []
    assert activity["interviews"] == activity["offers"] == []
    raw_ids = {x["raw_note_id"] for values in (activity["research_snapshots"], activity["communications"], activity["interviews"], activity["offers"]) for x in values}
    with store.connect(False) as db:
        raws = [json.loads(row[0]) for row in db.execute("SELECT body FROM records WHERE kind='journey_note'")]
    assert {raw["id"] for raw in raws} == raw_ids
    assert {raw["content"] for raw in raws} >= {"研究原文"}
    assert "研究原文" not in json.dumps(store.context(job["id"], "job"), ensure_ascii=False)

    reopened = TestClient(create_app(Store(tmp_path / "data", TestProvider())))
    assert reopened.get("/api/opportunity-activity").json() == activity
