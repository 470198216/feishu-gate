from __future__ import annotations

import asyncio
from pathlib import Path


def run_write(*, api_key: str, model: str, cwd: str, task: str) -> str:
    if not api_key:
        return "还没配 CURSOR_API_KEY。写进 feishu-gate/.env（可与 cursor-lan 同一把）。工单仍停在闸门前。"
    root = Path(cwd).expanduser()
    if not root.is_dir():
        return f"仓库目录不存在：{root}"
    return asyncio.run(_run_write_async(api_key=api_key, model=model, root=root, task=task))


async def _run_write_async(*, api_key: str, model: str, root: Path, task: str) -> str:
    # Windows 上同步 Agent.prompt → Bridge.launch 会调 os.get_blocking，直接崩。
    # 本机已验证的路径是 AsyncClient.launch_bridge（与 cursor-lan 相同）。
    prompt = (
        f"工作目录就是当前仓库。任务：{task}\n"
        "只改这个仓库里的文件。不要 git commit / push。不要改密钥和 .env。\n"
        "完成后用不超过 12 行说明改了哪些文件、怎么验证。"
    )
    from cursor_sdk import (
        AgentOptions,
        AsyncAgent,
        AsyncClient,
        CursorAgentError,
        LocalAgentOptions,
    )

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
        return f"Agent 没启动起来：{err}"
    status = getattr(result, "status", "")
    body = getattr(result, "result", None)
    if body is None:
        text = str(result)
    elif isinstance(body, str):
        text = body
    else:
        text = str(body)
    if len(text) > 2500:
        text = text[:2500] + "\n…（已截断）"
    return f"status={status}\n{text}"
