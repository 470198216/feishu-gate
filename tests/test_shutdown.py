import json
from pathlib import Path

from feishu_gate.jobs import infer_risk, new_job
from feishu_gate.shutdown import enabled_devices, load_devices, run_shutdown, shutdown_card


def test_infer_shutdown():
    assert infer_risk("下班关机") == "shutdown"
    assert infer_risk("关机") == "shutdown"
    assert infer_risk("关现场") == "shutdown"
    assert infer_risk("删除全部数据") == "destroy"
    assert infer_risk("给拓扑加按钮") == "write"


def test_new_job_shutdown():
    job = new_job(user="ou", text="下班关机")
    assert job.risk == "shutdown"
    assert job.status == "waiting"


def test_load_skips_placeholder_and_disabled(tmp_path: Path):
    path = tmp_path / "shutdown.json"
    path.write_text(
        json.dumps(
            {
                "devices": [
                    {
                        "name": "空的",
                        "ip": "待填写",
                        "os": "kylin",
                        "enabled": True,
                        "order": 1,
                    },
                    {
                        "name": "关掉的",
                        "ip": "192.168.1.10",
                        "os": "kylin",
                        "enabled": False,
                        "order": 1,
                    },
                    {
                        "name": "网关A",
                        "ip": "192.168.1.107",
                        "os": "麒麟",
                        "via": "ssh",
                        "port": 22,
                        "enabled": True,
                        "order": 100,
                    },
                    {
                        "name": "安卓1",
                        "ip": "192.168.1.50",
                        "os": "android",
                        "via": "adb",
                        "port": 5555,
                        "enabled": True,
                        "order": 10,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    ready = enabled_devices(load_devices(path))
    assert [d.name for d in ready] == ["安卓1", "网关A"]
    assert ready[0].via == "adb"
    assert ready[1].os == "kylin"
    assert ready[1].sudo_secret() == ""


def test_sudo_password_falls_back_to_login():
    from feishu_gate.shutdown import Device

    same = Device(
        name="a",
        ip="10.0.0.1",
        os="kylin",
        via="ssh",
        port=22,
        user="kylin",
        password="loginpw",
        key_path="",
        adb_serial="",
        enabled=True,
        order=1,
        sudo_password="",
    )
    other = Device(
        name="a",
        ip="10.0.0.1",
        os="kylin",
        via="ssh",
        port=22,
        user="kylin",
        password="loginpw",
        key_path="",
        adb_serial="",
        enabled=True,
        order=1,
        sudo_password="sudopw",
    )
    assert same.sudo_secret() == "loginpw"
    assert other.sudo_secret() == "sudopw"


def test_run_shutdown_uses_runner(tmp_path: Path):
    agent = tmp_path / ".agent"
    agent.mkdir()
    (agent / "shutdown.json").write_text(
        json.dumps(
            {
                "devices": [
                    {
                        "name": "安卓1",
                        "ip": "10.0.0.8",
                        "os": "android",
                        "via": "adb",
                        "port": 5555,
                        "enabled": True,
                        "order": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    seen: list[str] = []

    def fake(dev):
        seen.append(f"{dev.name}:{dev.via}")
        return f"{dev.name} ok"

    body = run_shutdown(tmp_path, runner=fake)
    assert seen == ["安卓1:adb"]
    assert "安卓1 ok" in body


def test_redact_secret():
    from feishu_gate.shutdown import _redact_secret

    assert "***" in _redact_secret("pw=secret123", "secret123")
    assert "secret123" not in _redact_secret("pw=secret123", "secret123")


def test_resolve_adb_uses_configured(tmp_path: Path):
    fake = tmp_path / "adb.exe"
    fake.write_text("", encoding="utf-8")
    from feishu_gate.shutdown import resolve_adb

    assert resolve_adb(str(fake), tmp_path) == str(fake)


def test_shutdown_card_hides_secrets():
    path = Path("C:/tmp/shutdown.json")
    text = shutdown_card("job-1", "下班关机", [], path)
    assert "密码" not in text
    assert "通过后仍会关本机" in text
    off = shutdown_card("job-1", "下班关机", [], path, shutdown_self=False)
    assert "还没有可关机设备" in off
    assert "密码" not in off


def test_load_options_and_self_shutdown(tmp_path: Path):
    from feishu_gate.shutdown import load_options, schedule_self_shutdown, self_shutdown_command

    missing = load_options(tmp_path / "nope.json")
    assert missing.shutdown_self is True
    assert missing.self_delay_sec == 8

    path = tmp_path / "shutdown.json"
    path.write_text(
        json.dumps({"shutdown_self": False, "self_delay_sec": 3, "devices": []}),
        encoding="utf-8",
    )
    opts = load_options(path)
    assert opts.shutdown_self is False
    assert opts.self_delay_sec == 3

    slept: list[int] = []
    ran: list[list[str]] = []
    schedule_self_shutdown(delay_sec=2, sleeper=slept.append, runner=ran.append)
    assert slept == [2]
    assert ran == [self_shutdown_command()]
    assert "shutdown" in ran[0][0].lower()
