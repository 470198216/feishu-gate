from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DESTROY = re.compile(r"(删除|destroy|关机|格式化|rm\s+-rf)", re.I)
_WRITE = re.compile(
    r"(改代码|改文件|部署|写入|发布|合入|修改|加按钮|加一个.{0,12}按钮|增加|新增|导出|实现|开发|commit|push)",
    re.I,
)


@dataclass(frozen=True)
class Job:
    id: str
    channel: str
    user: str
    text: str
    risk: str
    created_at: str
    status: str = "queued"
    note: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def with_status(job: Job, status: str, note: str = "") -> Job:
    return Job(
        id=job.id,
        channel=job.channel,
        user=job.user,
        text=job.text,
        risk=job.risk,
        created_at=job.created_at,
        status=status,
        note=note,
    )


def infer_risk(text: str) -> str:
    if _DESTROY.search(text):
        return "destroy"
    if _WRITE.search(text):
        return "write"
    return "read"


def new_job(*, user: str, text: str, channel: str = "feishu") -> Job:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    risk = infer_risk(text)
    return Job(
        id=f"job-{now}-{short}",
        channel=channel,
        user=user,
        text=text,
        risk=risk,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="waiting" if risk in {"write", "destroy"} else "queued",
    )


def append_job(path: Path, job: Job) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(job.to_json() + "\n")


def receipt(job: Job) -> str:
    next_hint = {
        "read": "只读，已入队，无需点头。",
        "write": "写入档。回复「通过」才改代码，「驳回」取消。",
        "destroy": "破坏档。即便点通过，本程序也不会执行删除/关机。",
    }[job.risk]
    return (
        f"工单 {job.id}\n"
        f"risk={job.risk}  status={job.status}\n"
        f"text={job.text}\n"
        f"{next_hint}"
    )


def review_card(job: Job, cwd: str) -> str:
    if job.risk == "destroy":
        return (
            f"【审核卡】{job.id}\n"
            f"风险：destroy\n"
            f"任务：{job.text}\n"
            f"回复「通过」只表示已知悉并归档，不会真删/关机。\n"
            f"回复「驳回」取消。"
        )
    return (
        f"【审核卡】{job.id}\n"
        f"风险：write\n"
        f"任务：{job.text}\n"
        f"仓库：{cwd}\n"
        f"通过后会用 Cursor SDK 改这个仓库，不提交 git。\n"
        f"回复「通过」或「驳回」。多单待审时写：通过 {job.id}"
    )
