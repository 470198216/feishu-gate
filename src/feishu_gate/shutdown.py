from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("feishu-gate")

_IP = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_EMPTY = {"", "待填写", "无", "none", "null"}

KYLIN_CMD = "sudo -S -p '' /usr/sbin/shutdown -h now"
ANDROID_SSH_CMD = "reboot -p"


def _redact_secret(text: str, secret: str) -> str:
    if not text:
        return ""
    if secret and secret in text:
        text = text.replace(secret, "***")
    return text.strip()


@dataclass(frozen=True)
class Device:
    name: str
    ip: str
    os: str
    via: str
    port: int
    user: str
    password: str
    key_path: str
    adb_serial: str
    enabled: bool
    order: int
    adb_bin: str = ""
    sudo_password: str = ""

    def sudo_secret(self) -> str:
        if _is_filled(self.sudo_password):
            return self.sudo_password
        return self.password


def bundled_adb(root: Path) -> Path:
    return Path(root) / "tools" / "platform-tools" / "adb.exe"


def resolve_adb(configured: str, root: Path | None = None) -> str:
    candidates: list[Path] = []
    if _is_filled(configured):
        candidates.append(Path(configured))
    if root is not None:
        candidates.append(bundled_adb(root))
    local_sdk = Path(os.environ.get("LOCALAPPDATA") or "") / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    candidates.append(local_sdk)
    candidates.append(Path(r"C:\platform-tools\adb.exe"))
    for item in candidates:
        if item.is_file():
            return str(item)
    found = shutil.which("adb")
    return found or ""


def config_path(root: Path) -> Path:
    local = root / ".agent" / "shutdown.json"
    if local.is_file():
        return local
    return root / ".agent" / "shutdown.example.json"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _is_filled(value: str) -> bool:
    return value.strip().lower() not in _EMPTY


def _norm_os(raw: str) -> str:
    text = raw.strip().lower()
    if text in {"kylin", "linux", "麒麟", "uos", "ubuntu"}:
        return "kylin"
    if text in {"android", "安卓"}:
        return "android"
    return text


def _norm_via(os_id: str, raw: str) -> str:
    text = raw.strip().lower()
    if text in {"ssh", "adb"}:
        return text
    return "adb" if os_id == "android" else "ssh"


def load_devices(path: Path) -> list[Device]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("devices") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    root = path.parent.parent if path.parent.name == ".agent" else path.parent
    configured = _clean(raw.get("adb_path")) if isinstance(raw, dict) else ""
    adb_bin = resolve_adb(configured, root)
    devices: list[Device] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ip = _clean(row.get("ip"))
        os_id = _norm_os(_clean(row.get("os")))
        via = _norm_via(os_id, _clean(row.get("via")))
        enabled = bool(row.get("enabled"))
        try:
            port = int(row.get("port") or (5555 if via == "adb" else 22))
        except (TypeError, ValueError):
            port = 5555 if via == "adb" else 22
        try:
            order = int(row.get("order") or 100)
        except (TypeError, ValueError):
            order = 100
        devices.append(
            Device(
                name=_clean(row.get("name")) or ip or "未命名",
                ip=ip,
                os=os_id,
                via=via,
                port=port,
                user=_clean(row.get("user")),
                password=_clean(row.get("password")),
                key_path=_clean(row.get("key_path")),
                adb_serial=_clean(row.get("adb_serial")),
                enabled=enabled,
                order=order,
                adb_bin=adb_bin,
                sudo_password=_clean(row.get("sudo_password")),
            )
        )
    devices.sort(key=lambda d: (d.order, d.name))
    return devices


def enabled_devices(devices: list[Device]) -> list[Device]:
    out: list[Device] = []
    for dev in devices:
        if not dev.enabled:
            continue
        if not _is_filled(dev.ip) or not _IP.match(dev.ip):
            continue
        if any(int(part) > 255 for part in dev.ip.split(".")):
            continue
        if dev.os not in {"kylin", "android"}:
            continue
        if dev.port < 1 or dev.port > 65535:
            continue
        out.append(dev)
    return out


def preview_lines(devices: list[Device]) -> list[str]:
    lines = []
    for dev in devices:
        lines.append(f"- {dev.name}  {dev.ip}:{dev.port}  {dev.os}/{dev.via}")
    return lines


def shutdown_card(job_id: str, text: str, devices: list[Device], cfg: Path) -> str:
    if not devices:
        return (
            f"【审核卡】{job_id}\n"
            f"风险：shutdown（下班关机）\n"
            f"任务：{text}\n"
            f"配置：{cfg}\n"
            "还没有可关机设备。先填 .agent/shutdown.json（从 shutdown.example.json 复制），"
            "写上 IP，os 填 kylin 或 android，并把 enabled 设为 true。\n"
            "现在点「通过」也不会关机。回复「驳回」取消。"
        )
    body = "\n".join(preview_lines(devices))
    return (
        f"【审核卡】{job_id}\n"
        f"风险：shutdown（下班关机）\n"
        f"任务：{text}\n"
        f"通过后按配置关机（网关请把 order 填大、放最后关）：\n"
        f"{body}\n"
        f"配置：{cfg}\n"
        "回复「通过」立刻关机，「驳回」取消。"
    )


def _ssh_via_openssh(dev: Device, cmd: str) -> str:
    ssh = shutil.which("ssh")
    if ssh is None:
        return f"{dev.name} 失败：没装 paramiko，本机也没有 ssh。先 pip install paramiko，或填 key_path 并用 OpenSSH。"
    if not _is_filled(dev.key_path):
        return f"{dev.name} 失败：密码登录需要 paramiko。在 feishu-gate 目录执行 pip install paramiko"
    argv = [
        ssh,
        "-i",
        dev.key_path,
        "-p",
        str(dev.port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=NUL" if os.name == "nt" else "UserKnownHostsFile=/dev/null",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        f"{dev.user or 'root'}@{dev.ip}",
        cmd,
    ]
    try:
        subprocess.run(argv, capture_output=True, text=True, timeout=25, encoding="utf-8", errors="replace")
        return f"{dev.name} 已发出关机命令（{dev.ip} {dev.os}/ssh）"
    except subprocess.TimeoutExpired:
        return f"{dev.name} 已发出关机，等待超时（常见成功） {dev.ip}"
    except Exception:
        log.warning("openssh shutdown failed name=%s ip=%s", dev.name, dev.ip)
        return f"{dev.name} 失败：SSH 连不上或命令被拒"


def _ssh_shutdown(dev: Device) -> str:
    cmd = ANDROID_SSH_CMD if dev.os == "android" else KYLIN_CMD
    try:
        import paramiko
    except ImportError:
        return _ssh_via_openssh(dev, cmd)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": dev.ip,
        "port": dev.port,
        "username": dev.user or "root",
        "timeout": 15,
        "allow_agent": False,
        "look_for_keys": False,
        "auth_timeout": 15,
    }
    if _is_filled(dev.key_path):
        kwargs["key_filename"] = dev.key_path
    elif _is_filled(dev.password):
        kwargs["password"] = dev.password
    else:
        return f"{dev.name} 失败：SSH 没填密码也没填 key_path"
    try:
        client.connect(**kwargs)
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=20)
        sudo_pw = dev.sudo_secret()
        if dev.os != "android" and _is_filled(sudo_pw):
            stdin.write(sudo_pw + "\n")
            stdin.flush()
        try:
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            status = stdout.channel.recv_exit_status()
        except Exception as err:
            msg = str(err).lower()
            if any(token in msg for token in ("reset", "closed", "eof", "timed out", "timeout")):
                return f"{dev.name} 已发出关机，随后连接断开（常见成功） {dev.ip}"
            raise
        combined = _redact_secret((out or "") + "\n" + (err or ""), sudo_pw)
        combined = _redact_secret(combined, dev.password)
        lowered = combined.lower()
        if any(token in lowered for token in ("sorry", "try again", "incorrect password", "not in the sudoers")):
            return f"{dev.name} 失败：sudo 没通过（密码或权限）"
        if status in (0, None) or "now" in lowered or "poweroff" in lowered or "halted" in lowered:
            return f"{dev.name} 已发出关机命令（{dev.ip} {dev.os}/ssh）"
        hint = combined.splitlines()
        hint = next((line for line in hint if line and "***" not in line), f"exit={status}")
        return f"{dev.name} 失败：{hint}"
    except Exception as err:
        msg = str(err).lower()
        if any(token in msg for token in ("reset", "closed", "eof", "timed out", "timeout")):
            return f"{dev.name} 已发出关机，随后连接断开（常见成功） {dev.ip}"
        log.warning("ssh shutdown failed name=%s ip=%s err=%s", dev.name, dev.ip, type(err).__name__)
        return f"{dev.name} 失败：SSH 连不上或命令被拒"
    finally:
        try:
            client.close()
        except Exception:
            pass


def _adb_shutdown(dev: Device) -> str:
    exe = dev.adb_bin or shutil.which("adb") or ""
    if not exe:
        return (
            f"{dev.name} 失败：找不到 adb。"
            "把 platform-tools 目录加入用户 PATH，或在 shutdown.json 写 adb_path。"
        )
    serial = dev.adb_serial if _is_filled(dev.adb_serial) else f"{dev.ip}:{dev.port}"
    target = f"{dev.ip}:{dev.port}"
    try:
        subprocess.run(
            [exe, "connect", target],
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
        )
        result = subprocess.run(
            [exe, "-s", serial, "reboot", "-p"],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return f"{dev.name} 已发出 adb 关机，等待超时（常见成功） {serial}"
    except FileNotFoundError:
        return f"{dev.name} 失败：本机没有 adb"
    if result.returncode == 0:
        return f"{dev.name} 已发出关机命令（{serial} android/adb）"
    err = (result.stderr or result.stdout or "").strip().splitlines()
    hint = err[0] if err else f"exit={result.returncode}"
    return f"{dev.name} 失败：adb {hint}"


def shutdown_one(dev: Device) -> str:
    if dev.via == "adb":
        return _adb_shutdown(dev)
    return _ssh_shutdown(dev)


def run_shutdown(root: Path, *, runner=shutdown_one) -> str:
    cfg = config_path(root)
    devices = enabled_devices(load_devices(cfg))
    if not devices:
        return f"没有可关机设备。请填写 {root / '.agent' / 'shutdown.json'}（enabled=true，有效 IP）。"
    lines = [f"配置 {cfg}", f"共 {len(devices)} 台："]
    for dev in devices:
        try:
            lines.append(runner(dev))
        except Exception:
            log.exception("shutdown crashed name=%s ip=%s", dev.name, dev.ip)
            lines.append(f"{dev.name} 失败：执行异常，看本机窗口日志")
    return "\n".join(lines)
