from feishu_gate.jobs import new_job
from feishu_gate.projects import parse_project


def test_prefix_topology():
    hit = parse_project("改拓扑：给页面加导出按钮")
    assert hit.id == "topology"
    assert hit.source == "prefix"


def test_prefix_gate():
    hit = parse_project("改机器人：加一条确认口令")
    assert hit.id == "feishu-gate"
    assert hit.source == "prefix"


def test_hint_topology():
    hit = parse_project("给拓扑加一个导出按钮")
    assert hit.id == "topology"
    assert hit.source == "hint"


def test_hint_gate():
    hit = parse_project("给机器人加一条命令")
    assert hit.id == "feishu-gate"
    assert hit.source == "hint"


def test_default_topology():
    hit = parse_project("给页面加一个导出按钮")
    assert hit.id == "topology"
    assert hit.source == "default"


def test_new_job_carries_project():
    job = new_job(user="ou", text="改机器人：修改验收口令")
    assert job.project == "feishu-gate"
    assert job.risk == "write"
