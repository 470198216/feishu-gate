from __future__ import annotations

import re
from dataclasses import dataclass

_PROBE_HINT = re.compile(
    r"(通不通|在不在|在线|掉线|掉了|灰了|灰了吗|ping|状态|拓扑|心跳)",
    re.I,
)

# 先写长的，避免 n80-b 被 n80 吃掉
_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("n80-a", ("n80-a", "n80a", "n80－a")),
    ("n80-b", ("n80-b", "n80b", "n80－b")),
    ("n80-c", ("n80-c", "n80c", "n80－c")),
    ("mesh-b3", ("mesh-b3", "自组网-b3", "自组网b3", "b3")),
    ("gw-a", ("gw-a", "网关a", "网关-a", "麒麟")),
    ("gw-b", ("gw-b", "网关b", "网关-b")),
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower().replace("－", "-")


@dataclass(frozen=True)
class ProbeAsk:
    targets: tuple[str, ...]


@dataclass(frozen=True)
class Approval:
    action: str
    job_id: str | None
    reason: str


_APPROVE = re.compile(r"^(通过|ok|批准)\s*(job-[0-9a-zA-Z-]+)?\s*$", re.I)
_CONFIRM = re.compile(r"^(确认|验收)\s*(job-[0-9a-zA-Z-]+)?\s*$", re.I)
_REJECT = re.compile(r"^(驳回|拒绝)(?:[:：]\s*|\s+)?(job-[0-9a-zA-Z-]+)?\s*(.*)$", re.I)


def parse_approval(text: str) -> Approval | None:
    stripped = text.strip()
    m = _APPROVE.match(stripped)
    if m:
        return Approval(action="approve", job_id=(m.group(2) or "").strip() or None, reason="")
    m = _CONFIRM.match(stripped)
    if m:
        return Approval(action="confirm", job_id=(m.group(2) or "").strip() or None, reason="")
    m = _REJECT.match(stripped)
    if m:
        job_id = (m.group(2) or "").strip() or None
        reason = (m.group(3) or "").strip()
        return Approval(action="reject", job_id=job_id, reason=reason)
    return None


def parse_probe(text: str) -> ProbeAsk | None:
    raw = normalize(text)
    hits: list[str] = []
    for nid, keys in _ALIASES:
        if any(k in raw for k in keys):
            hits.append(nid)
    if hits:
        return ProbeAsk(targets=tuple(dict.fromkeys(hits)))
    if _PROBE_HINT.search(text):
        return ProbeAsk(targets=())
    return None
