from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_id: str
    app_secret: str
    mode: str
    allow_open_ids: frozenset[str]
    data_dir: Path

    @property
    def jobs_path(self) -> Path:
        return self.data_dir / "jobs.jsonl"


def load_settings() -> Settings:
    load_dotenv(_ROOT / ".env")
    app_id = (os.environ.get("FEISHU_APP_ID") or os.environ.get("APP_ID") or "").strip()
    app_secret = (os.environ.get("FEISHU_APP_SECRET") or os.environ.get("APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        raise SystemExit(
            "缺少 FEISHU_APP_ID / FEISHU_APP_SECRET。先按 README 创建飞书应用，再复制 .env.example 为 .env 填入。"
        )
    mode = (os.environ.get("FEISHU_MODE") or "echo").strip().lower()
    if mode not in {"echo", "jobs"}:
        raise SystemExit("FEISHU_MODE 只能是 echo 或 jobs")
    raw_ids = os.environ.get("FEISHU_ALLOW_OPEN_IDS") or ""
    allow = frozenset(part.strip() for part in raw_ids.split(",") if part.strip())
    data_dir = _ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    return Settings(
        app_id=app_id,
        app_secret=app_secret,
        mode=mode,
        allow_open_ids=allow,
        data_dir=data_dir,
    )
