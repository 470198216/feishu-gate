from pathlib import Path

from feishu_gate.intent import parse_approval
from feishu_gate.jobs import new_job, review_card, with_status
from feishu_gate.store import JobStore


def test_parse_approve():
    a = parse_approval("通过")
    assert a is not None and a.action == "approve" and a.job_id is None
    b = parse_approval("通过 job-20260909-1-abc")
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


def test_review_card_write():
    job = new_job(user="ou_1", text="给拓扑加按钮")
    text = review_card(job, "C:/repo")
    assert "审核卡" in text
    assert "通过" in text
