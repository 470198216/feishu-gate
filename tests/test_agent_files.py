from pathlib import Path

from feishu_gate.agentfiles import env_path, read_hint
from feishu_gate.config import _ROOT


def test_gate_agent_files_exist():
    agent = _ROOT / ".agent"
    assert (agent / "environment.example.md").is_file()
    assert (agent / "acceptance.md").is_file()
    text = (agent / "environment.example.md").read_text(encoding="utf-8")
    assert "## 4. 账号与密钥" in text
    accept = (agent / "acceptance.md").read_text(encoding="utf-8")
    assert "## 3. 功能用例" in accept
    assert "## 4. 硬规则" in accept


def test_topology_agent_files_exist():
    root = _ROOT.parent / "演示方案讨论" / "topology-heartbeat-viewer"
    agent = root / ".agent"
    assert (agent / "environment.example.md").is_file()
    assert (agent / "acceptance.md").is_file()


def test_read_hint_prefers_local(tmp_path: Path):
    agent = tmp_path / ".agent"
    agent.mkdir()
    (agent / "environment.example.md").write_text("example", encoding="utf-8")
    (agent / "acceptance.md").write_text("acc", encoding="utf-8")
    hint = read_hint(tmp_path)
    assert "还没填写" in hint
    (agent / "environment.md").write_text("filled", encoding="utf-8")
    hint2 = read_hint(tmp_path)
    assert "已填写" in hint2
    assert str(env_path(tmp_path)).endswith("environment.md")
