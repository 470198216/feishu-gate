from feishu_gate.intent import parse_probe
from feishu_gate.probe import format_probe


def test_parse_n80b():
    ask = parse_probe("N80-B 通不通")
    assert ask is not None
    assert ask.targets == ("n80-b",)


def test_parse_b3_not_n80b():
    ask = parse_probe("B3 又灰了")
    assert ask is not None
    assert ask.targets == ("mesh-b3",)


def test_parse_generic_topology():
    ask = parse_probe("拓扑现在什么状态")
    assert ask is not None
    assert ask.targets == ()


def test_parse_hello():
    assert parse_probe("你好") is None


def test_format_probe_offline():
    data = {
        "nodes": [
            {"id": "n80-b", "online": False},
            {"id": "mesh-b3", "online": False},
        ]
    }
    text = format_probe(data, parse_probe("N80-B 通不通"))
    assert "N80-B：不通（灰）" in text
    text_b3 = format_probe(data, parse_probe("B3 灰了吗"))
    assert "硬规则" in text_b3
