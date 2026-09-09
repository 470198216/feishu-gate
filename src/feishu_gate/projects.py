from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_PROJECT = "topology"

TOPOLOGY_PLAYBOOK = """
必读：.agent/environment.md（没有则 environment.example.md）和 .agent/acceptance.md。
本地测试（必须用 18080，不要占 8080，避免和麒麟现场混在一起）：
  python server.py --probe --self-demo --http-port 18080
验证：按验收说明；至少 curl http://127.0.0.1:18080/api/status
测完必须停掉你启动的这个进程。
禁区：不要改 topology.json 里的现场 ip；不要 git commit / push；不要改密钥、.env、environment.md 里的账号密码。
硬规则：以验收说明第 4 节为准；未填写时 N80-B ping 不通则自组网-B3 必须灰。
""".strip()

GATE_PLAYBOOK = """
必读：.agent/environment.md（没有则 environment.example.md）和 .agent/acceptance.md。
本地测试：在仓库根目录用已有 .venv 跑 pytest
  .\\.venv\\Scripts\\python.exe -m pytest
不要启动第二个 feishu-gate.exe（长连接同时只能一个）。
禁区：不要改 .env、密钥、environment.md 里的账号密码；不要 git commit / push；不要把密码写进回执。
""".strip()

_PREFIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^改拓扑[:：]"), "topology"),
    (re.compile(r"^改心跳[:：]"), "topology"),
    (re.compile(r"^改机器人[:：]"), "feishu-gate"),
    (re.compile(r"^改闸门[:：]"), "feishu-gate"),
)

_GATE_HINT = re.compile(r"机器人|闸门|feishu-gate|飞书工人")
_TOPO_HINT = re.compile(r"拓扑|心跳|topology|n80|自组网", re.I)


@dataclass(frozen=True)
class Project:
    id: str
    title: str
    cwd: str
    playbook: str


@dataclass(frozen=True)
class ProjectHit:
    id: str
    source: str  # prefix | hint | default

    @property
    def explicit(self) -> bool:
        return self.source != "default"


def catalog(*, topology_cwd: str, gate_cwd: str) -> dict[str, Project]:
    return {
        "topology": Project(
            id="topology",
            title="拓扑心跳页",
            cwd=topology_cwd,
            playbook=TOPOLOGY_PLAYBOOK,
        ),
        "feishu-gate": Project(
            id="feishu-gate",
            title="飞书闸门",
            cwd=gate_cwd,
            playbook=GATE_PLAYBOOK,
        ),
    }


def parse_project(text: str, default: str = DEFAULT_PROJECT) -> ProjectHit:
    stripped = text.strip()
    for pat, pid in _PREFIXES:
        if pat.search(stripped):
            return ProjectHit(id=pid, source="prefix")
    if _GATE_HINT.search(text):
        return ProjectHit(id="feishu-gate", source="hint")
    if _TOPO_HINT.search(text):
        return ProjectHit(id="topology", source="hint")
    return ProjectHit(id=default, source="default")


def playbook_for(project_id: str) -> str:
    if project_id == "feishu-gate":
        return GATE_PLAYBOOK
    return TOPOLOGY_PLAYBOOK
