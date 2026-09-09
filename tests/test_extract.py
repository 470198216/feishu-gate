import json
from types import SimpleNamespace

from feishu_gate.bot import extract_text


def _event(message_type: str, content: str) -> object:
    return SimpleNamespace(
        event=SimpleNamespace(message=SimpleNamespace(message_type=message_type, content=content))
    )


def test_extract_text_ok():
    payload = json.dumps({"text": "  hello  "})
    assert extract_text(_event("text", payload)) == "hello"


def test_extract_non_text():
    assert extract_text(_event("image", "{}")) is None
