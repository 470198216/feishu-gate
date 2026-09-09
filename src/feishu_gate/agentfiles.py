from __future__ import annotations

from pathlib import Path

ENV_NAME = "environment.md"
ENV_EXAMPLE = "environment.example.md"
ACCEPT_NAME = "acceptance.md"


def agent_dir(root: Path) -> Path:
    return Path(root) / ".agent"


def env_path(root: Path) -> Path:
    local = agent_dir(root) / ENV_NAME
    if local.is_file():
        return local
    return agent_dir(root) / ENV_EXAMPLE


def accept_path(root: Path) -> Path:
    return agent_dir(root) / ACCEPT_NAME


def read_hint(root: Path) -> str:
    """告诉 Agent 去读哪些文件。不把文件内容塞进 prompt，避免密码进飞书回执。"""
    root = Path(root)
    local = agent_dir(root) / ENV_NAME
    example = agent_dir(root) / ENV_EXAMPLE
    accept = accept_path(root)
    if local.is_file():
        env_line = f"- 环境记录（已填写，必读）：{local}"
    elif example.is_file():
        env_line = f"- 环境记录还没填写，只有大纲：{example}。缺账号/IP 就停并说明，不要猜密码。"
    else:
        env_line = "- 没有 .agent/environment.md，只用项目手册。"
    if accept.is_file():
        acc_line = f"- 验收说明（必读，按里面的用例测）：{accept}"
    else:
        acc_line = "- 没有 .agent/acceptance.md，用项目手册里的验证步骤。"
    return (
        "用工具打开下面文件，按里面的 IP/账号搭环境，按验收说明测试。\n"
        "禁止：改 environment.md 里的账号密码；把密码/密钥写进摘要、飞书回执、代码、commit。\n"
        f"{env_line}\n"
        f"{acc_line}"
    )
