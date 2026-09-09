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
    topology_url: str
    cursor_api_key: str
    cursor_model: str
    write_cwd: str
    data_dir: Path

    @property
    def jobs_path(self) -> Path:
        return self.data_dir / "jobs.jsonl"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "jobs-state.json"


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
    topology_url = (
        os.environ.get("TOPOLOGY_STATUS_URL") or "http://192.168.1.107:8080/api/status"
    ).strip()
    cursor_api_key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not cursor_api_key:
        lan_env = _ROOT.parent / "cursor-lan" / ".env"
        if lan_env.is_file():
            from dotenv import dotenv_values

            cursor_api_key = (dotenv_values(lan_env).get("CURSOR_API_KEY") or "").strip()
    cursor_model = (os.environ.get("CURSOR_LAN_MODEL") or os.environ.get("CURSOR_MODEL") or "composer-2.5").strip()
    write_cwd = (
        os.environ.get("WRITE_CWD")
        or str(_ROOT.parent / "演示方案讨论" / "topology-heartbeat-viewer")
    ).strip()
    return Settings(
        app_id=app_id,
        app_secret=app_secret,
        mode=mode,
        allow_open_ids=allow,
        topology_url=topology_url,
        cursor_api_key=cursor_api_key,
        cursor_model=cursor_model,
        write_cwd=write_cwd,
        data_dir=data_dir,
    )
