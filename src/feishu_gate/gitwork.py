from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def is_git_repo(cwd: Path) -> bool:
    result = _git(cwd, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def snapshot(cwd: Path) -> dict:
    root = Path(cwd)
    if not is_git_repo(root):
        return {"git": False, "head": "", "porcelain": []}
    head = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain")
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    return {
        "git": True,
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "porcelain": lines,
    }


def snapshot_json(cwd: Path) -> str:
    return json.dumps(snapshot(cwd), ensure_ascii=False)


def load_snapshot(raw: str) -> dict:
    if not raw:
        return {"git": False, "head": "", "porcelain": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"git": False, "head": "", "porcelain": []}
    if not isinstance(data, dict):
        return {"git": False, "head": "", "porcelain": []}
    porcelain = data.get("porcelain") or []
    if not isinstance(porcelain, list):
        porcelain = []
    return {
        "git": bool(data.get("git")),
        "head": str(data.get("head") or ""),
        "porcelain": [str(item) for item in porcelain],
    }


def porcelain_paths(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        if len(line) < 4:
            continue
        code = line[:2]
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out[path] = code
    return out


def _safe_path(root: Path, rel: str) -> Path | None:
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def git_status_text(cwd: Path) -> str:
    if not is_git_repo(cwd):
        return "(不是 git 仓库)"
    result = _git(cwd, "status", "--porcelain")
    text = result.stdout.strip()
    return text or "(工作区干净)"


def git_diff_text(cwd: Path, limit: int = 1800) -> str:
    if not is_git_repo(cwd):
        return ""
    result = _git(cwd, "diff")
    text = result.stdout
    untracked = [
        path
        for path, code in porcelain_paths(list(snapshot(cwd).get("porcelain") or [])).items()
        if code.strip() == "??"
    ]
    extra = ""
    if untracked:
        extra = "\n未跟踪文件：\n" + "\n".join(untracked)
    text = (text + extra).strip()
    if len(text) > limit:
        return text[:limit] + "\n…（diff 已截断）"
    return text


def revert_to_snapshot(cwd: Path, baseline_raw: str) -> str:
    root = Path(cwd)
    before = load_snapshot(baseline_raw)
    if not before.get("git") or not is_git_repo(root):
        return "不是 git 仓库，没法自动还原。"
    after = snapshot(root)
    before_paths = porcelain_paths(list(before.get("porcelain") or []))
    after_paths = porcelain_paths(list(after.get("porcelain") or []))
    restored: list[str] = []
    deleted: list[str] = []
    skipped: list[str] = []
    for path, code in after_paths.items():
        if path in before_paths:
            skipped.append(path)
            continue
        target = _safe_path(root, path)
        if target is None:
            skipped.append(path)
            continue
        if code.strip() == "??":
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.exists():
                target.unlink(missing_ok=True)
            deleted.append(path)
            continue
        _git(root, "restore", "--worktree", "--staged", "--", path)
        if not (root / path).exists() and code.strip().startswith("A"):
            pass
        else:
            # 新增且已暂存：restore 后可能仍留下未跟踪文件
            leftover = _safe_path(root, path)
            status = _git(root, "status", "--porcelain", "--", path)
            if status.stdout.strip().startswith("??") and leftover is not None:
                if leftover.is_dir():
                    shutil.rmtree(leftover, ignore_errors=True)
                elif leftover.exists():
                    leftover.unlink(missing_ok=True)
                deleted.append(path)
                continue
        restored.append(path)
    bits = []
    if restored:
        bits.append("已还原：" + ", ".join(restored))
    if deleted:
        bits.append("已删除本次新文件：" + ", ".join(deleted))
    if skipped:
        bits.append("开工前已脏、未动：" + ", ".join(skipped))
    if not bits:
        return "没有需要还原的改动。"
    return "；".join(bits)
