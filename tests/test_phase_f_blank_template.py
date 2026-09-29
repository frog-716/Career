"""A new Opportunity Resume starts with the specified editable A4 structure."""

from test_record_submitted import client_at, opportunity, start


def test_first_opportunity_resume_has_four_named_sections_and_no_github_placeholder(tmp_path):
    client, store = client_at(tmp_path / "data")
    target = opportunity(client, "虚构首份简历机会")
    created = start(client, target)
    document = created["document"]
    assert [(section["type"], section["title"], section["items"]) for section in document["sections"]] == [
        ("skills", "专业技能", []),
        ("experience", "工作经历", []),
        ("projects", "项目经历", []),
        ("education", "教育背景", []),
    ]
    assert document["profile"]["contacts"] == []
    assert "github" not in str(document).lower()
    read_back = client.get(f"/api/opportunities/{target['id']}/resume")
    assert read_back.status_code == 200
    assert read_back.json()["document"] == document
