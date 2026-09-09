from __future__ import annotations

import json
import urllib.error
import urllib.request

from feishu_gate.intent import ProbeAsk

_LABEL = {
    "n80-a": "N80-A",
    "n80-b": "N80-B",
    "n80-c": "N80-C",
    "mesh-b3": "自组网-B3",
    "gw-a": "网关A",
    "gw-b": "网关B",
}

_DEFAULT_IDS = ("n80-a", "n80-b", "n80-c", "mesh-b3")


def fetch_status(url: str, timeout: float = 2.5) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("拓扑接口返回不是对象")
    return data


def _online_map(data: dict) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for node in data.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("id") or "")
        if nid:
            out[nid] = bool(node.get("online"))
    return out


def format_probe(data: dict, ask: ProbeAsk) -> str:
    online = _online_map(data)
    ids = ask.targets or _DEFAULT_IDS
    lines: list[str] = []
    for nid in ids:
        label = _LABEL.get(nid, nid)
        if nid not in online:
            lines.append(f"{label}：图上没有这个节点")
            continue
        lines.append(f"{label}：{'通' if online[nid] else '不通（灰）'}")
    n80b = online.get("n80-b")
    b3 = online.get("mesh-b3")
    if "mesh-b3" in ids and n80b is False and b3 is False:
        lines.append("硬规则：N80-B 不通时 B3 必须灰。")
    b3_report = data.get("b3") if isinstance(data.get("b3"), dict) else {}
    if "mesh-b3" in ids and b3_report:
        up = b3_report.get("up")
        if up is False and n80b:
            lines.append("B3 口上报不通（N80-B 仍通时也可能灰）。")
    return "\n".join(lines)


def run_probe(url: str, ask: ProbeAsk) -> str:
    try:
        data = fetch_status(url)
    except urllib.error.URLError as err:
        return f"拓扑服务连不上：{url}\n{err}"
    except Exception as err:
        return f"读拓扑失败：{err}"
    body = format_probe(data, ask)
    mode = data.get("mode") or ""
    extra = f"\n来源：{url}"
    if mode:
        extra += f"  mode={mode}"
    return body + extra
