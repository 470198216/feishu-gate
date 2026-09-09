from pathlib import Path

from feishu_gate.jobs import append_job, infer_risk, new_job, receipt


def test_infer_risk():
    assert infer_risk("B3 怎么又灰了") == "read"
    assert infer_risk("给拓扑加按钮") == "write"
    assert infer_risk("给拓扑加一个导出按钮") == "write"
    assert infer_risk("删除全部数据") == "destroy"


def test_append_and_receipt(tmp_path: Path):
    job = new_job(user="ou_test", text="B3 灰了吗")
    path = tmp_path / "jobs.jsonl"
    append_job(path, job)
    line = path.read_text(encoding="utf-8").strip()
    assert job.id in line
    text = receipt(job)
    assert job.id in text
    assert "risk=read" in text
    assert "project=" in text
