from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from feishu_gate.config import Settings, load_settings
from feishu_gate.intent import parse_probe
from feishu_gate.jobs import Job, append_job, new_job, receipt
from feishu_gate.probe import run_probe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("feishu-gate")


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


def run_probe_job(
    settings: Settings, api: lark.Client, target: ChatTarget, job: Job
) -> None:
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


def handle_message(settings: Settings, api: lark.Client, event: P2ImMessageReceiveV1) -> None:
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
    job = new_job(user=sender_open_id(event), text=text)
    append_job(settings.jobs_path, job)
    if job.risk != "read":
        reply_text(api, event, receipt(job))
        return
    ask = parse_probe(text)
    if ask is None:
        reply_text(api, event, receipt(job) + "\n暂无只读工人认领这类问题。问「N80-B 通不通」会去查拓扑。")
        return
    reply_text(api, event, f"工单 {job.id}\n正在查拓扑（只读，不用点头）…")
    target = chat_target(event)
    threading.Thread(
        target=run_probe_job,
        args=(settings, api, target, job),
        daemon=True,
        name=f"probe-{job.id}",
    ).start()


def build_handler(settings: Settings, api: lark.Client):
    def on_message(data: P2ImMessageReceiveV1) -> None:
        try:
            handle_message(settings, api, data)
        except Exception:
            log.exception("处理消息失败")

    return (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )


def main() -> None:
    settings = load_settings()
    api = lark.Client.builder().app_id(settings.app_id).app_secret(settings.app_secret).build()
    handler = build_handler(settings, api)
    log.info("长连接启动 mode=%s app_id=%s", settings.mode, settings.app_id)
    log.info("jobs 模式：问「N80-B 通不通」会查 %s", settings.topology_url if settings.mode == "jobs" else "")
    ws = lark.ws.Client(
        settings.app_id,
        settings.app_secret,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    ws.start()


if __name__ == "__main__":
    main()
