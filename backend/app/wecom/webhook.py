"""
POST /wecom/callback 接收企业微信回调。
验签 → 解密 → 解析 XML（MsgType/Content/群聊ID/发送者）→ 仅处理群聊且 @ 机器人的文本 → 调用问答 → 加密回复。
"""
import re
import xml.etree.ElementTree as ET
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.wecom.crypto import decrypt, encrypt_reply_xml
from app.wecom.verify import verify_callback_body, verify_url_and_echo

router = APIRouter(prefix="/wecom", tags=["wecom"])


def _extract_cdata(el: Optional[ET.Element]) -> str:
    if el is None or el.text:
        return (el.text or "").strip()
    return (el.text or "") + "".join(ET.tostring(e, encoding="unicode", method="xml") for e in el)


def _parse_encrypt_body(body: str) -> str:
    root = ET.fromstring(body)
    enc = root.find("Encrypt")
    if enc is not None and enc.text:
        return enc.text.strip()
    raise ValueError("Missing Encrypt in body")


def _el_text(root: ET.Element, *tags: str) -> str:
    for tag in tags:
        el = root.find(tag) or root.find(tag.lower()) or root.find(tag.upper())
        if el is not None and (el.text or len(el) > 0):
            return (el.text or "").strip() or _extract_cdata(el)
    return ""


def _parse_decrypted_msg(xml_str: str) -> dict:
    """解析解密后的消息 XML，提取 MsgType, Content, FromUserName, ChatId 等。"""
    root = ET.fromstring(xml_str)
    return {
        "msg_type": _el_text(root, "MsgType", "msgtype"),
        "content": _el_text(root, "Content", "content"),
        "from_user": _el_text(root, "FromUserName", "from"),
        "to_user": _el_text(root, "ToUserName", "to"),
        "msg_id": _el_text(root, "MsgId", "msgid"),
        "agent_id": _el_text(root, "AgentID", "agentid"),
        "chat_id": _el_text(root, "ChatId", "chatid"),
    }


def _normalize_parsed(parsed: dict) -> dict:
    """兼容不同字段名（大小写）。"""
    def get(el, *keys):
        for k in keys:
            v = (parsed.get(k) or parsed.get(k.lower()) or parsed.get(k.upper()))
            if v is not None:
                return v
        return ""
    return {
        "msg_type": get(parsed, "msg_type", "MsgType"),
        "content": get(parsed, "content", "Content"),
        "from_user": get(parsed, "from_user", "FromUserName", "from"),
        "to_user": get(parsed, "to_user", "ToUserName", "to"),
        "msg_id": get(parsed, "msg_id", "MsgId"),
        "agent_id": get(parsed, "agent_id", "AgentID"),
        "chat_id": get(parsed, "chat_id", "ChatId"),
    }


def _is_group_message(parsed: dict) -> bool:
    """有 ChatId 即为群聊。"""
    return bool(parsed.get("chat_id") or parsed.get("ChatId"))


def _is_text_message(parsed: dict) -> bool:
    return (parsed.get("msg_type") or "").lower() == "text"


def _extract_question_and_should_reply(
    content: str,
    bot_user_id: Optional[str] = None,
    at_bot_pattern: Optional[str] = None,
) -> tuple[str, bool]:
    """
    判断是否 @ 机器人并提取纯问题文本。
    企业微信 @ 格式可能为：@机器人名 问题 或 问题中带 @。
    若未配置 bot_user_id，可用关键字触发（如「问」开头或整句作为问题）。
    """
    text = (content or "").strip()
    if not text:
        return "", False

    # 常见 @ 格式：<@userid> 或 @用户名
    at_mention = re.compile(r"@[^\s\u2005]+|\s*<@[^>]+>\s*")
    stripped = at_mention.sub(" ", text).strip()
    # 若去掉 @ 后为空，说明只是 @ 没有实质问题
    if not stripped:
        return "", False

    # 若配置了必须 @ 才回复：这里简化处理为「内容中包含 @ 或关键字」即视为触发
    if at_bot_pattern and not re.search(at_bot_pattern, content):
        return "", False

    return stripped, True


@router.get("/callback", response_class=PlainTextResponse)
async def wecom_verify_url(
    msg_signature: str = Query(..., alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
    echostr: str = Query(..., alias="echostr"),
):
    """企业微信 GET 校验 URL：解密 echostr 并原样返回。"""
    s = get_settings()
    try:
        echo = verify_url_and_echo(
            s.wecom_token,
            s.wecom_aes_key,
            s.wecom_corp_id,
            msg_signature,
            timestamp,
            nonce,
            echostr,
        )
        return PlainTextResponse(echo)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=400)


@router.post("/callback", response_class=PlainTextResponse)
async def wecom_callback(request: Request):
    """
    接收企业微信 POST 回调：验签、解密、只处理群聊文本且 @ 机器人的消息，
    调用内部 /v1/chat/ask，再加密回复到群。
    """
    s = get_settings()
    body = (await request.body()).decode("utf-8")
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")

    try:
        msg_encrypt = _parse_encrypt_body(body)
    except Exception as e:
        return PlainTextResponse(f"parse body error: {e}", status_code=400)

    if not verify_callback_body(s.wecom_token, timestamp, nonce, msg_encrypt, msg_signature):
        return PlainTextResponse("invalid signature", status_code=403)

    try:
        plain_xml = decrypt(s.wecom_aes_key, msg_encrypt, s.wecom_corp_id)
    except Exception as e:
        return PlainTextResponse(f"decrypt error: {e}", status_code=400)

    try:
        parsed = _parse_decrypted_msg(plain_xml)
        parsed = _normalize_parsed(parsed)
    except Exception as e:
        return PlainTextResponse(f"parse msg error: {e}", status_code=400)

    if not _is_group_message(parsed):
        return PlainTextResponse("ok")  # 非群聊不处理，直接 200

    if not _is_text_message(parsed):
        return PlainTextResponse("ok")

    question, should_reply = _extract_question_and_should_reply(parsed["content"])
    if not should_reply or not question:
        return PlainTextResponse("ok")

    # 调用内部问答接口（同步 HTTP 调用自身）
    import httpx
    base_url = str(request.base_url).rstrip("/")
    chat_url = f"{base_url}/v1/chat/ask"
    payload = {
        "platform": "wecom",
        "group_id": parsed.get("chat_id") or f"wecom_room_{parsed.get('msg_id', '')}",
        "user_id": parsed.get("from_user") or "unknown",
        "text": question,
        "domain": "montreal_realestate",  # 默认领域，可后续从群/配置映射
        "conversation_id": parsed.get("msg_id"),
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(chat_url, json=payload)
            data = r.json()
    except Exception as e:
        reply_text = "服务暂时不可用，请稍后再试。"
    else:
        if r.status_code == 200 and isinstance(data, dict):
            reply_text = data.get("answer") or "暂无回答。"
            if data.get("flags", {}).get("limited"):
                reply_text = "今日提问次数已达上限，明天再试哦。"
            elif data.get("flags", {}).get("fallback"):
                reply_text = reply_text or "服务繁忙，请稍后再试。"
        else:
            reply_text = "处理出错，请稍后再试。"

    # 被动回复：加密 XML 返回
    import time
    reply_ts = str(int(time.time()))
    reply_nonce = str(int(time.time() * 1000))
    reply_xml = f"""<xml>
<ToUserName><![CDATA[{parsed.get("from_user", "")}]]></ToUserName>
<FromUserName><![CDATA[{parsed.get("to_user", "")}]]></FromUserName>
<CreateTime>{reply_ts}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{reply_text}]]></Content>
</xml>"""
    encrypted = encrypt_reply_xml(
        s.wecom_token,
        s.wecom_aes_key,
        s.wecom_corp_id,
        reply_xml,
        reply_ts,
        reply_nonce,
    )
    return PlainTextResponse(encrypted, media_type="application/xml")
