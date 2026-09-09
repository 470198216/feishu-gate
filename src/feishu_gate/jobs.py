from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from feishu_gate.projects import parse_project

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
    project: str = "topology"
    baseline: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def evolve(job: Job, **changes: object) -> Job:
    payload = asdict(job)
    payload.update(changes)
    return Job(**payload)


def with_status(job: Job, status: str, note: str = "") -> Job:
    return evolve(job, status=status, note=note)


def infer_risk(text: str) -> str:
    if _DESTROY.search(text):
        return "destroy"
    if _WRITE.search(text):
        return "write"
    return "read"


def new_job(*, user: str, text: str, channel: str = "feishu", project: str | None = None) -> Job:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    risk = infer_risk(text)
    hit = parse_project(text)
    return Job(
        id=f"job-{now}-{short}",
        channel=channel,
        user=user,
        text=text,
        risk=risk,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="waiting" if risk in {"write", "destroy"} else "queued",
        project=project or hit.id,
    )


def append_job(path: Path, job: Job) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(job.to_json() + "\n")


def receipt(job: Job) -> str:
    next_hint = {
        "read": "只读，已入队，无需点头。",
        "write": "写入档。回复「通过」才开工，「确认」才收下改动，「驳回」取消/还原。",
        "destroy": "破坏档。即便点通过，本程序也不会执行删除/关机。",
    }[job.risk]
    return (
        f"工单 {job.id}\n"
        f"risk={job.risk}  status={job.status}  project={job.project}\n"
        f"text={job.text}\n"
        f"{next_hint}"
    )


def review_card(job: Job, cwd: str, title: str = "", explicit: bool = True) -> str:
    if job.risk == "destroy":
        return (
            f"【审核卡】{job.id}\n"
            f"风险：destroy\n"
            f"任务：{job.text}\n"
            f"回复「通过」只表示已知悉并归档，不会真删/关机。\n"
            f"回复「驳回」取消。"
        )
    default_hint = ""
    if not explicit:
        default_hint = (
            "未写明仓库，默认拓扑。若要改机器人，请驳回后发：改机器人：……\n"
        )
    return (
        f"【审核卡】{job.id}\n"
        f"风险：write\n"
        f"项目：{title or job.project}\n"
        f"任务：{job.text}\n"
        f"仓库：{cwd}\n"
        f"{default_hint}"
        f"通过后会按项目手册搭本地环境、测试、分析、改代码；改完再发【验收卡】。\n"
        f"不提交 git。回复「通过」或「驳回」。多单待审时写：通过 {job.id}"
    )


def accept_card(job: Job, cwd: str, title: str, summary: str, git_status: str, git_diff: str) -> str:
    body = (
        f"【验收卡】{job.id}\n"
        f"项目：{title or job.project}\n"
        f"仓库：{cwd}\n"
        f"任务：{job.text}\n"
        f"\n工人摘要：\n{summary or '(无)'}\n"
        f"\ngit status:\n{git_status or '(无)'}\n"
    )
    if git_diff:
        body += f"\ngit diff:\n{git_diff}\n"
    body += (
        "\n回复「确认」留下改动（不 commit）。\n"
        "回复「驳回」还原这次改动。\n"
        f"多单时写：确认 {job.id}"
    )
    if len(body) > 3500:
        return body[:3500] + "\n…（已截断）"
    return body
