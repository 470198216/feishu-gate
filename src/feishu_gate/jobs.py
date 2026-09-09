from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DESTROY = re.compile(r"(删除|destroy|关机|格式化|rm\s+-rf)", re.I)
_WRITE = re.compile(r"(改|部署|写入|发布|合入|修|加按钮|commit|push)", re.I)


@dataclass(frozen=True)
class Job:
    id: str
    channel: str
    user: str
    text: str
    risk: str
    created_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def infer_risk(text: str) -> str:
    if _DESTROY.search(text):
        return "destroy"
    if _WRITE.search(text):
        return "write"
    return "read"


def new_job(*, user: str, text: str, channel: str = "feishu") -> Job:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return Job(
        id=f"job-{now}-{short}",
        channel=channel,
        user=user,
        text=text,
        risk=infer_risk(text),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def append_job(path: Path, job: Job) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(job.to_json() + "\n")


def receipt(job: Job) -> str:
    next_hint = {
        "read": "只读，已入队，无需点头。",
        "write": "写入档，以后要回复「通过」才执行。",
        "destroy": "破坏档，永远等你点头，AI 不会自己走完。",
    }[job.risk]
    return (
        f"工单 {job.id}\n"
        f"risk={job.risk}\n"
        f"text={job.text}\n"
        f"{next_hint}"
    )
