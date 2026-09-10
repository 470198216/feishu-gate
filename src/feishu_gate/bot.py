from __future__ import annotations

import json
import logging
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from feishu_gate.coder import WriteReport, run_write
from feishu_gate.config import Settings, load_settings
from feishu_gate.gitwork import revert_to_snapshot, snapshot_json
from feishu_gate.intent import parse_approval, parse_probe
from feishu_gate.jobs import (
    Job,
    accept_card,
    append_job,
    evolve,
    new_job,
    receipt,
    review_card,
    with_status,
)
from feishu_gate.projects import parse_project
from feishu_gate.probe import run_probe
from feishu_gate.shutdown import (
    config_path,
    enabled_devices,
    load_devices,
    load_options,
    run_shutdown,
    schedule_self_shutdown,
    shutdown_card,
)
from feishu_gate.store import JobStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("feishu-gate")
_CODE_LOCK = threading.Lock()
_OPS_LOCK = threading.Lock()


def extract_text(event: P2ImMessageReceiveV1) -> str | None:
    msg = event.event.message
    if msg.message_type != "text":
        return None
    try:
        payload = json.loads(msg.content)
    except json.JSONDecodeError:
        return None
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    text = re.sub(r"<at[^>]*>.*?</at>", "", text)
    text = re.sub(r"@_user_\d+\s*", "", text)
    return text.strip() or None


def sender_open_id(event: P2ImMessageReceiveV1) -> str:
    sender = event.event.sender
    if sender is None or sender.sender_id is None:
        return ""
    return sender.sender_id.open_id or ""


def allowed(settings: Settings, event: P2ImMessageReceiveV1) -> bool:
    sender = event.event.sender
    if sender is None or sender.sender_type != "user":
        return False
    if not settings.allow_open_ids:
        return True
    return sender_open_id(event) in settings.allow_open_ids


@dataclass(frozen=True)
class ChatTarget:
    chat_type: str
    chat_id: str
    message_id: str


def chat_target(event: P2ImMessageReceiveV1) -> ChatTarget:
    msg = event.event.message
    return ChatTarget(chat_type=msg.chat_type, chat_id=msg.chat_id, message_id=msg.message_id)


def send_text(api: lark.Client, target: ChatTarget, text: str) -> None:
    content = json.dumps({"text": text}, ensure_ascii=False)
    if target.chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(target.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        response = api.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(
                f"发消息失败 code={response.code} msg={response.msg} log_id={response.get_log_id()}"
            )
        return
    request = (
        ReplyMessageRequest.builder()
        .message_id(target.message_id)
        .request_body(
            ReplyMessageRequestBody.builder().content(content).msg_type("text").build()
        )
        .build()
    )
    response = api.im.v1.message.reply(request)
    if not response.success():
        raise RuntimeError(
            f"回复失败 code={response.code} msg={response.msg} log_id={response.get_log_id()}"
        )


def reply_text(api: lark.Client, event: P2ImMessageReceiveV1, text: str) -> None:
    send_text(api, chat_target(event), text)


def run_probe_job(settings: Settings, api: lark.Client, target: ChatTarget, job: Job) -> None:
    ask = parse_probe(job.text)
    if ask is None:
        return
    try:
        body = run_probe(settings.topology_url, ask)
        send_text(api, target, f"工单 {job.id}\n{body}")
    except Exception:
        log.exception("只读探测失败 job=%s", job.id)
        try:
            send_text(api, target, f"工单 {job.id}\n探测失败，看本机窗口日志。")
        except Exception:
            log.exception("连失败回执也没发出去")


def run_shutdown_job(settings: Settings, store: JobStore, api: lark.Client, target: ChatTarget, job: Job) -> None:
    root = Path(settings.gate_cwd)
    opts = load_options(config_path(root))
    replied = False
    try:
        body = run_shutdown(root)
        if opts.shutdown_self:
            body = f"{body}\n本机将在本条回执发出后关机。"
        store.put(with_status(job, "done", note=body[:500]))
        send_text(api, target, f"工单 {job.id} 关机结果\n{body}")
        replied = True
    except Exception:
        log.exception("下班关机失败 job=%s", job.id)
        store.put(with_status(job, "done", note="shutdown-error"))
        try:
            extra = "\n随后仍会关本机。" if opts.shutdown_self else ""
            send_text(api, target, f"工单 {job.id}\n关机失败，看本机窗口日志。{extra}")
            replied = True
        except Exception:
            log.exception("连失败回执也没发出去")
    finally:
        if _OPS_LOCK.locked():
            _OPS_LOCK.release()
    if opts.shutdown_self and replied:
        try:
            schedule_self_shutdown(delay_sec=opts.self_delay_sec)
        except Exception:
            log.exception("本机关机命令没发出去 job=%s", job.id)


def _has_diff(report: WriteReport) -> bool:
    status = (report.git_status or "").strip()
    if not status or status in {"(工作区干净)", "(不是 git 仓库)"}:
        return bool((report.git_diff or "").strip())
    return True


def run_write_job(settings: Settings, store: JobStore, api: lark.Client, target: ChatTarget, job: Job) -> None:
    project = settings.project(job.project)
    try:
        report = run_write(
            api_key=settings.cursor_api_key,
            model=settings.cursor_model,
            cwd=project.cwd,
            task=job.text,
            playbook=project.playbook,
            project=project.id,
        )
        current = store.get(job.id) or job
        baseline = current.baseline or report.baseline
        if report.failed and not _has_diff(report):
            store.put(evolve(current, status="done", note=report.summary[:500], baseline=baseline))
            send_text(api, target, f"工单 {job.id}\n{report.summary}")
            return
        reviewed = evolve(
            current,
            status="review",
            note=report.summary[:500],
            baseline=baseline,
        )
        store.put(reviewed)
        send_text(
            api,
            target,
            accept_card(
                reviewed,
                project.cwd,
                project.title,
                report.summary,
                report.git_status,
                report.git_diff,
            ),
        )
    except Exception:
        log.exception("写入工人失败 job=%s", job.id)
        current = store.get(job.id) or job
        store.put(evolve(current, status="done", note="coder-error"))
        try:
            send_text(api, target, f"工单 {job.id}\n改代码失败，看本机窗口日志。")
        except Exception:
            log.exception("连失败回执也没发出去")
    finally:
        if _CODE_LOCK.locked():
            _CODE_LOCK.release()


def _list_jobs(jobs: list[Job]) -> str:
    return "\n".join(f"{j.id}  {j.project}/{j.risk}  {j.text}" for j in jobs)


def _pick_by_status(
    store: JobStore,
    user: str,
    job_id: str | None,
    status: str,
    empty: str,
) -> Job | str:
    if job_id:
        job = store.get(job_id)
        if job is None:
            return f"没有工单 {job_id}"
        if job.status != status:
            if status == "waiting" and job.status == "review":
                return f"{job.id} 已经改完，请回「确认」收下改动，或「驳回」还原。"
            return f"{job.id} 不是待审（status={job.status} risk={job.risk} project={job.project}）"
        return job
    found = store.by_status(status, user) or store.by_status(status, None)
    if not found:
        last = store.latest(user)
        if last is None:
            return empty
        return (
            f"{empty}\n"
            f"最近一单 {last.id} 是 {last.project}/{last.risk}/{last.status}：{last.text}\n"
            f"写入任务请写成「改拓扑：…」或「改机器人：…」，出现【审核卡】后再回「通过」。"
        )
    if len(found) > 1:
        hint = "通过 job-xxxx" if status == "waiting" else "确认 job-xxxx"
        return f"有多单，请写：{hint}\n" + _list_jobs(found)
    return found[0]


def _pick_rejectable(store: JobStore, user: str, job_id: str | None) -> Job | str:
    if job_id:
        job = store.get(job_id)
        if job is None:
            return f"没有工单 {job_id}"
        if job.status not in {"waiting", "review"}:
            return f"{job.id} 不能驳回（status={job.status}）"
        return job
    review = store.reviewing(user) or store.reviewing(None)
    waiting = store.waiting(user) or store.waiting(None)
    both = review + waiting
    if not both:
        last = store.latest(user)
        if last is None:
            return "没有待审或待验收工单。"
        return f"没有待审或待验收工单。最近一单 {last.id} 是 {last.project}/{last.status}。"
    if len(both) > 1:
        return "有多单，请写：驳回 job-xxxx\n" + _list_jobs(both)
    return both[0]


def handle_approval(
    settings: Settings,
    store: JobStore,
    api: lark.Client,
    event: P2ImMessageReceiveV1,
    user: str,
    approval,
) -> None:
    if approval.action == "confirm":
        picked = _pick_by_status(store, user, approval.job_id, "review", "没有待验收工单。")
        if isinstance(picked, str):
            reply_text(api, event, picked)
            return
        store.put(with_status(picked, "done", note=picked.note or "confirmed"))
        proj = settings.project(picked.project)
        reply_text(
            api,
            event,
            f"已确认 {picked.id}。改动留在 {proj.cwd}，未 git commit / push。",
        )
        return
    if approval.action == "reject":
        picked = _pick_rejectable(store, user, approval.job_id)
        if isinstance(picked, str):
            reply_text(api, event, picked)
            return
        extra = ""
        if picked.status == "review":
            extra = revert_to_snapshot(Path(settings.cwd_for(picked.project)), picked.baseline)
            extra = f"\n{extra}" if extra else ""
        store.put(with_status(picked, "rejected", note=approval.reason))
        reply_text(api, event, f"已驳回 {picked.id}\n{approval.reason or '无原因'}{extra}")
        return
    picked = _pick_by_status(store, user, approval.job_id, "waiting", "没有待审工单。")
    if isinstance(picked, str):
        reply_text(api, event, picked)
        return
    job = picked
    if job.risk == "destroy":
        store.put(with_status(job, "blocked", note="human-ack"))
        reply_text(api, event, f"{job.id} 已归档。破坏档不会执行。")
        return
    if job.risk == "shutdown":
        if not _OPS_LOCK.acquire(blocking=False):
            reply_text(api, event, "上一轮关机还在跑，稍后再通过。")
            return
        try:
            running = with_status(job, "running")
            store.put(running)
            reply_text(api, event, f"{job.id} 已通过，开始按 .agent/shutdown.json 关机（现场关完、飞书回执发出后再关本机）")
            threading.Thread(
                target=run_shutdown_job,
                args=(settings, store, api, chat_target(event), running),
                daemon=True,
                name=f"shutdown-{job.id}",
            ).start()
        except Exception:
            _OPS_LOCK.release()
            raise
        return
    if not _CODE_LOCK.acquire(blocking=False):
        reply_text(api, event, "编码工人还在改上一单，稍后再通过。")
        return
    try:
        cwd = settings.cwd_for(job.project)
        running = evolve(job, status="running", baseline=snapshot_json(Path(cwd)))
        store.put(running)
        proj = settings.project(job.project)
        reply_text(api, event, f"{job.id} 已通过，开始改 {proj.title}：{proj.cwd}")
        threading.Thread(
            target=run_write_job,
            args=(settings, store, api, chat_target(event), running),
            daemon=True,
            name=f"write-{job.id}",
        ).start()
    except Exception:
        _CODE_LOCK.release()
        raise


def handle_message(
    settings: Settings, store: JobStore, api: lark.Client, event: P2ImMessageReceiveV1
) -> None:
    if not allowed(settings, event):
        log.info("忽略非用户或未授权发送者")
        return
    text = extract_text(event)
    if text is None:
        reply_text(api, event, "请发纯文本。通道在，但只处理文字。")
        return
    log.info("收到 %s: %s", sender_open_id(event), text)
    if settings.mode == "echo":
        reply_text(api, event, text)
        return
    user = sender_open_id(event)
    approval = parse_approval(text)
    if approval is not None:
        handle_approval(settings, store, api, event, user, approval)
        return
    hit = parse_project(text)
    job = new_job(user=user, text=text, project=hit.id)
    append_job(settings.jobs_path, job)
    store.put(job)
    if job.risk == "shutdown":
        cfg = config_path(Path(settings.gate_cwd))
        devices = enabled_devices(load_devices(cfg))
        opts = load_options(cfg)
        reply_text(
            api,
            event,
            shutdown_card(job.id, job.text, devices, cfg, shutdown_self=opts.shutdown_self),
        )
        return
    if job.risk in {"write", "destroy"}:
        proj = settings.project(job.project)
        reply_text(
            api,
            event,
            review_card(job, proj.cwd, proj.title, explicit=hit.source != "default"),
        )
        return
    ask = parse_probe(text)
    if ask is None:
        reply_text(api, event, receipt(job) + "\n暂无只读工人认领这类问题。问「N80-B 通不通」会去查拓扑。")
        return
    reply_text(api, event, f"工单 {job.id}\n正在查拓扑（只读，不用点头）…")
    threading.Thread(
        target=run_probe_job,
        args=(settings, api, chat_target(event), job),
        daemon=True,
        name=f"probe-{job.id}",
    ).start()


def build_handler(settings: Settings, store: JobStore, api: lark.Client):
    def on_message(data: P2ImMessageReceiveV1) -> None:
        try:
            handle_message(settings, store, api, data)
        except Exception:
            log.exception("处理消息失败")

    return (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )


def main() -> None:
    settings = load_settings()
    store = JobStore(settings.state_path)
    api = lark.Client.builder().app_id(settings.app_id).app_secret(settings.app_secret).build()
    handler = build_handler(settings, store, api)
    log.info("长连接启动 mode=%s app_id=%s", settings.mode, settings.app_id)
    log.info("只读查 %s", settings.topology_url)
    log.info(
        "项目 topology=%s  feishu-gate=%s  key=%s",
        settings.write_cwd,
        settings.gate_cwd,
        "已配" if settings.cursor_api_key else "缺失",
    )
    log.info("下班关机配置 %s", config_path(Path(settings.gate_cwd)))
    ws = lark.ws.Client(
        settings.app_id,
        settings.app_secret,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    ws.start()


if __name__ == "__main__":
    main()
