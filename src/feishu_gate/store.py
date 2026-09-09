from __future__ import annotations

import json
import threading
from pathlib import Path

from feishu_gate.jobs import Job


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _dump(self, data: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def put(self, job: Job) -> None:
        with self._lock:
            data = self._load()
            data[job.id] = asdict_job(job)
            self._dump(data)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._load().get(job_id)
        return job_from_dict(row) if row else None

    def by_status(self, status: str, user: str | None = None) -> list[Job]:
        with self._lock:
            rows = list(self._load().values())
        jobs = [job_from_dict(row) for row in rows]
        jobs = [j for j in jobs if j.status == status]
        if user:
            jobs = [j for j in jobs if j.user == user]
        jobs.sort(key=lambda j: j.created_at)
        return jobs

    def waiting(self, user: str | None = None) -> list[Job]:
        return self.by_status("waiting", user)

    def reviewing(self, user: str | None = None) -> list[Job]:
        return self.by_status("review", user)

    def latest(self, user: str | None = None) -> Job | None:
        with self._lock:
            rows = list(self._load().values())
        jobs = [job_from_dict(row) for row in rows]
        if user:
            scoped = [j for j in jobs if j.user == user] or jobs
            jobs = scoped
        if not jobs:
            return None
        jobs.sort(key=lambda j: j.created_at)
        return jobs[-1]


def asdict_job(job: Job) -> dict:
    return {
        "id": job.id,
        "channel": job.channel,
        "user": job.user,
        "text": job.text,
        "risk": job.risk,
        "created_at": job.created_at,
        "status": job.status,
        "note": job.note,
        "project": job.project,
        "baseline": job.baseline,
    }


def job_from_dict(row: dict) -> Job:
    return Job(
        id=str(row["id"]),
        channel=str(row.get("channel") or "feishu"),
        user=str(row.get("user") or ""),
        text=str(row.get("text") or ""),
        risk=str(row.get("risk") or "read"),
        created_at=str(row.get("created_at") or ""),
        status=str(row.get("status") or "queued"),
        note=str(row.get("note") or ""),
        project=str(row.get("project") or "topology"),
        baseline=str(row.get("baseline") or ""),
    )
