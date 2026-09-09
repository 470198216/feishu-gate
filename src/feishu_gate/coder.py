from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from feishu_gate.agentfiles import read_hint
from feishu_gate.gitwork import git_diff_text, git_status_text, snapshot_json


@dataclass(frozen=True)
class WriteReport:
    summary: str
    git_status: str
    git_diff: str
    baseline: str
    failed: bool = False


def run_write(
    *,
    api_key: str,
    model: str,
    cwd: str,
    task: str,
    playbook: str,
    project: str,
) -> WriteReport:
    if not api_key:
        return WriteReport(
            summary="还没配 CURSOR_API_KEY。写进 feishu-gate/.env（可与 cursor-lan 同一把）。工单仍停在闸门前。",
            git_status="",
            git_diff="",
            baseline="",
            failed=True,
        )
    root = Path(cwd).expanduser()
    if not root.is_dir():
        return WriteReport(
            summary=f"仓库目录不存在：{root}",
            git_status="",
            git_diff="",
            baseline="",
            failed=True,
        )
    baseline = snapshot_json(root)
    return asyncio.run(
        _run_write_async(
            api_key=api_key,
            model=model,
            root=root,
            task=task,
            playbook=playbook,
            project=project,
            baseline=baseline,
        )
    )


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…（已截断）"


async def _run_write_async(
    *,
    api_key: str,
    model: str,
    root: Path,
    task: str,
    playbook: str,
    project: str,
    baseline: str,
) -> WriteReport:
    prompt = (
        f"你在仓库 {root}（项目 {project}）。任务：{task}\n"
        "只改这个仓库里的文件。不要 git commit / push。不要改密钥、.env、.agent/environment.md 里的账号密码。\n"
        f"{read_hint(root)}\n"
        "按这个顺序做，某步失败就停并说明，不要假装测过：\n"
        "1. 用工具打开环境记录和验收说明（以及 README / AGENTS.md）\n"
        "2. 按环境记录搭测试环境（IP、账号、启动命令以文件为准）\n"
        "3. 按验收说明先复现或跑最小验证\n"
        "4. 分析根因\n"
        "5. 改代码\n"
        "6. 按验收说明再测一遍（含硬规则和回归命令）\n"
        "7. 关掉你自己起的进程\n"
        "完成后用不超过 20 行说明：环境怎么起的、测了哪些验收项、根因、改了哪些文件、怎么再验、残留进程有没有关掉。不要写密码。\n"
        f"\n项目手册：\n{playbook}"
    )
    from cursor_sdk import (
        AgentOptions,
        AsyncAgent,
        AsyncClient,
        CursorAgentError,
        LocalAgentOptions,
    )

    failed = False
    try:
        async with await AsyncClient.launch_bridge(workspace=str(root)) as client:
            result = await AsyncAgent.prompt(
                prompt,
                AgentOptions(
                    api_key=api_key,
                    model=model,
                    local=LocalAgentOptions(
                        cwd=str(root),
                        setting_sources=["project", "user"],
                    ),
                ),
                client=client,
            )
    except CursorAgentError as err:
        return WriteReport(
            summary=f"Agent 没启动起来：{err}",
            git_status=git_status_text(root),
            git_diff=git_diff_text(root),
            baseline=baseline,
            failed=True,
        )
    status = getattr(result, "status", "")
    body = getattr(result, "result", None)
    if body is None:
        text = str(result)
    elif isinstance(body, str):
        text = body
    else:
        text = str(body)
    summary = _clip(f"status={status}\n{text}", 1500)
    return WriteReport(
        summary=summary,
        git_status=_clip(git_status_text(root), 800),
        git_diff=git_diff_text(root),
        baseline=baseline,
        failed=failed,
    )
