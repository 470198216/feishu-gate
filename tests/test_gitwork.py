import subprocess
from pathlib import Path

from feishu_gate.gitwork import revert_to_snapshot, snapshot_json


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "keep.txt").write_text("old\n", encoding="utf-8")
    _git(root, "add", "keep.txt")
    _git(root, "commit", "-m", "init")


def test_revert_keeps_pre_dirty_and_drops_job_files(tmp_path: Path):
    _init_repo(tmp_path)
    (tmp_path / "pre_dirty.txt").write_text("before\n", encoding="utf-8")
    baseline = snapshot_json(tmp_path)

    (tmp_path / "keep.txt").write_text("changed by job\n", encoding="utf-8")
    (tmp_path / "new_file.txt").write_text("job new\n", encoding="utf-8")
    (tmp_path / "pre_dirty.txt").write_text("before and more\n", encoding="utf-8")

    msg = revert_to_snapshot(tmp_path, baseline)
    assert (tmp_path / "keep.txt").read_text(encoding="utf-8").replace("\r\n", "\n") == "old\n"
    assert not (tmp_path / "new_file.txt").exists()
    assert "changed by job" not in (tmp_path / "keep.txt").read_text(encoding="utf-8")
    assert (tmp_path / "pre_dirty.txt").read_text(encoding="utf-8").replace("\r\n", "\n") == "before and more\n"
    assert "已还原" in msg or "已删除" in msg
