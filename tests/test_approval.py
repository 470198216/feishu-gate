from pathlib import Path

from feishu_gate.intent import parse_approval
from feishu_gate.jobs import new_job, review_card, with_status
from feishu_gate.store import JobStore


def test_parse_approve():
    a = parse_approval("通过")
    assert a is not None and a.action == "approve" and a.job_id is None
    b = parse_approval("通过 job-20260909-1-abc")
    assert b is not None and b.job_id == "job-20260909-1-abc"


def test_parse_confirm():
    a = parse_approval("确认")
    assert a is not None and a.action == "confirm" and a.job_id is None
    b = parse_approval("确认 job-20260909-1-abc")
    assert b is not None and b.job_id == "job-20260909-1-abc"


def test_parse_reject():
    a = parse_approval("驳回：按钮太大")
    assert a is not None and a.action == "reject" and a.reason == "按钮太大"


def test_parse_not_approval():
    assert parse_approval("给拓扑加按钮") is None


def test_store_waiting(tmp_path: Path):
    store = JobStore(tmp_path / "state.json")
    job = new_job(user="ou_1", text="给拓扑加按钮")
    store.put(job)
    waiting = store.waiting("ou_1")
    assert len(waiting) == 1
    store.put(with_status(job, "rejected", "no"))
    assert store.waiting("ou_1") == []


def test_store_reviewing(tmp_path: Path):
    store = JobStore(tmp_path / "state.json")
    job = new_job(user="ou_1", text="给拓扑加按钮")
    store.put(job)
    assert store.waiting("ou_1")
    store.put(with_status(job, "review", "diff"))
    assert store.waiting("ou_1") == []
    reviewing = store.reviewing("ou_1")
    assert len(reviewing) == 1
    assert reviewing[0].project == "topology"


def test_legacy_state_defaults_project(tmp_path: Path):
    from feishu_gate.store import job_from_dict

    job = job_from_dict(
        {
            "id": "job-1",
            "channel": "feishu",
            "user": "ou",
            "text": "给拓扑加按钮",
            "risk": "write",
            "created_at": "2026-09-09T00:00:00",
            "status": "waiting",
        }
    )
    assert job.project == "topology"
    assert job.baseline == ""


def test_pick_review_not_waiting(tmp_path: Path):
    from feishu_gate.bot import _pick_by_status

    store = JobStore(tmp_path / "state.json")
    job = new_job(user="ou_1", text="给拓扑加按钮")
    store.put(with_status(job, "review"))
    picked = _pick_by_status(store, "ou_1", job.id, "waiting", "没有待审工单。")
    assert isinstance(picked, str)
    assert "确认" in picked
    found = _pick_by_status(store, "ou_1", None, "review", "没有待验收工单。")
    assert not isinstance(found, str)
    assert found.id == job.id


def test_review_card_write():
    job = new_job(user="ou_1", text="给拓扑加按钮")
    text = review_card(job, "C:/repo", "拓扑心跳页")
    assert "审核卡" in text
    assert "通过" in text
    assert "拓扑心跳页" in text


def test_accept_card():
    from feishu_gate.jobs import accept_card

    job = new_job(user="ou_1", text="给拓扑加按钮")
    text = accept_card(job, "C:/repo", "拓扑心跳页", "改了 web/app.js", " M web/app.js", "diff")
    assert "验收卡" in text
    assert "确认" in text
    assert "驳回" in text
