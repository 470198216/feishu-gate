from __future__ import annotations

import json
import logging
import sys

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from feishu_gate.config import Settings, load_settings
from feishu_gate.jobs import append_job, new_job, receipt

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


def reply_text(api: lark.Client, event: P2ImMessageReceiveV1, text: str) -> None:
    content = json.dumps({"text": text}, ensure_ascii=False)
    chat_type = event.event.message.chat_type
    if chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(event.event.message.chat_id)
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
        .message_id(event.event.message.message_id)
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
    reply_text(api, event, receipt(job))


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
    log.info("飞书里搜机器人，发一句纯文本。echo 模式会原样回你。")
    ws = lark.ws.Client(
        settings.app_id,
        settings.app_secret,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    ws.start()


if __name__ == "__main__":
    main()
