"""
POST /wecom/callback 接收企业微信回调。
验签 → 解密 → 解析 XML → 仅当明确 @ 机器人时才触发 → 立即返回 success → 后台调问答并 appchat/send 发群消息。

联调三关（A/B/C）及必备点：

A. URL 验证（GET 校验）
  - 逻辑：验签并解密 echostr 后原样返回（verify.py → webhook PlainTextResponse）。
  - 回调地址必须 443/标准 HTTPS；非 443 或弱证书/自签/不完整链可能导致企业微信校验失败。
  - 服务器时间需基本准确（NTP），否则签名校验可能因 timestamp 偏差失败。

B. 仅 @ 时触发
  - 触发规则三选一：MentionedList 含 bot_user_id / 内容含 <@...> / 以 @机器人名 开头。
  - 兜底过滤：只处理群聊、只处理文本消息；去掉 @ 后若文本为空（例如只@不问）则不回复。
  - 日志会输出解析到的 MentionedList 与 content 预览（脱敏），便于区分「字段未带」与「正则未匹配」。

C. 主动发群消息（gettoken + appchat/send）
  - token 缓存：gettoken 有频率限制，当前实现缓存约 7200s 并提前 60s 刷新，避免高频失败。
  - 幂等去重：企业微信回调会重试，已用 Redis SETNX wecom:dedupe:{msg_id} 仅首次处理，防刷屏。
  - 发送失败兜底：errcode≠0 或异常时日志带 trace_id/msg_id/chat_id/from_user 便于追踪。
"""
import logging
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request, Query
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.core.limiter import get_redis
from app.wecom.crypto import decrypt
from app.wecom.verify import verify_callback_body, verify_url_and_echo

logger = logging.getLogger(__name__)

# 幂等去重 key 过期时间（企业微信重试窗口）
DEDUPE_TTL_SEC = 86400 * 2  # 2 天

router = APIRouter(prefix="/wecom", tags=["wecom"])

# 回复纯文本时统一使用 UTF-8，避免企业微信或客户端乱码
TEXT_UTF8_MEDIA_TYPE = "text/plain; charset=utf-8"


def _decode_body(raw: bytes) -> str:
    """解码回调 body：优先 UTF-8，去掉 BOM；失败则试 GBK。"""
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("gbk")
        except Exception:
            return raw.decode("utf-8", errors="replace")


def _extract_cdata(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    if el.text:
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


def _parse_mentioned_list(root: ET.Element) -> list[str]:
    """解析被 @ 列表。企业微信可能用 MentionedList/MentionedItemList + Item 或 UserID。"""
    user_ids: list[str] = []
    for list_tag in ("MentionedList", "MentionedItemList", "mentioned_list"):
        el = root.find(list_tag) or root.find(list_tag.lower()) or root.find(list_tag.upper())
        if el is None:
            continue
        for item in el.findall("Item") or el.findall("UserID") or el.findall("item") or []:
            if item.text and item.text.strip():
                user_ids.append(item.text.strip())
        # 有的格式是直接在列表标签下多个 UserID
        for uid in el.findall("UserID") or el.findall("userid") or []:
            if uid.text and uid.text.strip():
                user_ids.append(uid.text.strip())
    return user_ids


def _parse_decrypted_msg(xml_str: str) -> dict:
    """解析解密后的消息 XML，提取 MsgType, Content, FromUserName, ChatId, MentionedList 等。"""
    root = ET.fromstring(xml_str)
    mentioned = _parse_mentioned_list(root)
    return {
        "msg_type": _el_text(root, "MsgType", "msgtype"),
        "content": _el_text(root, "Content", "content"),
        "from_user": _el_text(root, "FromUserName", "from"),
        "to_user": _el_text(root, "ToUserName", "to"),
        "msg_id": _el_text(root, "MsgId", "msgid"),
        "agent_id": _el_text(root, "AgentID", "agentid"),
        "chat_id": _el_text(root, "ChatId", "chatid"),
        "mentioned_list": mentioned,
    }


def _normalize_parsed(parsed: dict) -> dict:
    """兼容不同字段名（大小写）。"""
    def get(el, *keys):
        for k in keys:
            v = (parsed.get(k) if isinstance(parsed.get(k), list) else parsed.get(k) or parsed.get(k.lower()) or parsed.get(k.upper()))
            if v is not None:
                return v
        return "" if keys[0] != "mentioned_list" else []
    return {
        "msg_type": get(parsed, "msg_type", "MsgType"),
        "content": get(parsed, "content", "Content"),
        "from_user": get(parsed, "from_user", "FromUserName", "from"),
        "to_user": get(parsed, "to_user", "ToUserName", "to"),
        "msg_id": get(parsed, "msg_id", "MsgId"),
        "agent_id": get(parsed, "agent_id", "AgentID"),
        "chat_id": get(parsed, "chat_id", "ChatId"),
        "mentioned_list": parsed.get("mentioned_list") if isinstance(parsed.get("mentioned_list"), list) else [],
    }


def _is_group_message(parsed: dict) -> bool:
    """有 ChatId 即为群聊。"""
    return bool(parsed.get("chat_id") or parsed.get("ChatId"))


def _is_text_message(parsed: dict) -> bool:
    return (parsed.get("msg_type") or "").lower() == "text"


def _extract_question_and_should_reply(
    content: str,
    mentioned_list: list[str],
    bot_user_id: str = "",
    bot_name: str = "",
) -> tuple[str, bool]:
    """
    仅当「明确 @ 机器人」时才响应。
    规则：1）回调带 MentionedList 且 bot_user_id 在列表中；或
         2）内容包含 <@...>（任一 @）；或
         3）内容以 @机器人名 开头。
    否则一律不触发，避免群里任意一句话都回复。
    """
    text = (content or "").strip()
    if not text:
        return "", False

    # 1）官方 @ 列表：若配置了 bot_user_id 且其在 mentioned_list 中，则触发
    if bot_user_id and mentioned_list and bot_user_id in mentioned_list:
        pass  # 下面统一做 strip @ 后取问题
    # 2）内容含 <@...>（企业微信常见格式）
    elif re.search(r"<@[^>]+>", content or ""):
        pass
    # 3）以 @机器人名 开头
    elif bot_name and (content or "").strip().startswith("@" + bot_name):
        pass
    else:
        return "", False

    # 去掉 @ 相关片段，得到纯问题
    at_mention = re.compile(r"@[^\s\u2005]+|\s*<@[^>]+>\s*")
    stripped = at_mention.sub(" ", text).strip()
    if not stripped:
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
        return PlainTextResponse(echo, media_type=TEXT_UTF8_MEDIA_TYPE)
    except Exception as e:
        return PlainTextResponse(str(e), status_code=400, media_type=TEXT_UTF8_MEDIA_TYPE)


async def _reply_in_background(
    base_url: str,
    chat_id: str,
    from_user_id: str,
    question: str,
    msg_id: str,
    trace_id: str,
):
    """后台：调 /v1/chat/ask，再用 appchat/send 发群消息（可 @ 提问者）。"""
    import httpx  # pyright: ignore[reportMissingImports]
    from app.wecom.sender import async_send_group_text
    chat_url = f"{base_url.rstrip('/')}/v1/chat/ask"
    payload = {
        "platform": "wecom",
        "group_id": chat_id,
        "user_id": from_user_id,
        "text": question,
        "domain": "montreal_realestate",
        "conversation_id": msg_id,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(chat_url, json=payload)
            data = r.json() if r.status_code == 200 else {}
    except Exception:
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
    try:
        res = await async_send_group_text(chat_id, reply_text, mentioned_list=[from_user_id])
        if res.get("errcode") != 0:
            logger.warning(
                "wecom send group reply failed trace_id=%s msg_id=%s chat_id=%s from_user=%s errcode=%s errmsg=%s",
                trace_id, msg_id, chat_id, from_user_id, res.get("errcode"), res.get("errmsg"),
            )
    except Exception as e:
        logger.exception(
            "wecom send group reply exception trace_id=%s msg_id=%s chat_id=%s from_user=%s error=%s",
            trace_id, msg_id, chat_id, from_user_id, e,
        )


@router.post("/callback", response_class=PlainTextResponse)
async def wecom_callback(request: Request, background_tasks: BackgroundTasks):
    """
    验签、解密、仅当群聊且明确 @ 机器人时投递后台任务，立即返回 success，避免回调超时与重试。
    """
    s = get_settings()
    raw = await request.body()
    body = _decode_body(raw)
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")

    try:
        msg_encrypt = _parse_encrypt_body(body)
    except Exception as e:
        return PlainTextResponse(f"parse body error: {e}", status_code=400, media_type=TEXT_UTF8_MEDIA_TYPE)

    if not verify_callback_body(s.wecom_token, timestamp, nonce, msg_encrypt, msg_signature):
        return PlainTextResponse("invalid signature", status_code=403, media_type=TEXT_UTF8_MEDIA_TYPE)

    try:
        plain_xml = decrypt(s.wecom_aes_key, msg_encrypt, s.wecom_corp_id)
    except Exception as e:
        return PlainTextResponse(f"decrypt error: {e}", status_code=400, media_type=TEXT_UTF8_MEDIA_TYPE)

    try:
        parsed = _parse_decrypted_msg(plain_xml)
        parsed = _normalize_parsed(parsed)
    except Exception as e:
        return PlainTextResponse(f"parse msg error: {e}", status_code=400, media_type=TEXT_UTF8_MEDIA_TYPE)

    if not _is_group_message(parsed):
        return PlainTextResponse("success", media_type=TEXT_UTF8_MEDIA_TYPE)
    if not _is_text_message(parsed):
        return PlainTextResponse("success", media_type=TEXT_UTF8_MEDIA_TYPE)

    mentioned_list = parsed.get("mentioned_list") or []
    if not isinstance(mentioned_list, list):
        mentioned_list = []
    question, should_reply = _extract_question_and_should_reply(
        parsed["content"],
        mentioned_list=mentioned_list,
        bot_user_id=s.wecom_bot_user_id or "",
        bot_name=(s.wecom_bot_name or "").strip(),
    )
    if not should_reply or not question:
        return PlainTextResponse("success", media_type=TEXT_UTF8_MEDIA_TYPE)

    # 脱敏日志：便于区分「MentionedList 未带」与「正则未匹配」
    content_preview = ((parsed.get("content") or "")[:80]).strip()
    logger.info(
        "wecom trigger reply mentioned_list=%s content_preview=%s",
        mentioned_list,
        content_preview if content_preview else "(empty)",
    )

    msg_id = parsed.get("msg_id") or ""
    # 幂等去重：企业微信重试会导致重复回复，用 Redis SETNX 仅首次处理
    if msg_id:
        r = await get_redis()
        if r is not None:
            dedupe_key = f"wecom:dedupe:{msg_id}"
            ok = await r.set(dedupe_key, "1", nx=True)
            if not ok:
                return PlainTextResponse("success", media_type=TEXT_UTF8_MEDIA_TYPE)
            await r.expire(dedupe_key, DEDUPE_TTL_SEC)

    chat_id = parsed.get("chat_id") or f"wecom_room_{msg_id or 'unknown'}"
    from_user = parsed.get("from_user") or "unknown"
    base_url = str(request.base_url).rstrip("/")
    trace_id = str(uuid.uuid4())
    background_tasks.add_task(
        _reply_in_background,
        base_url,
        chat_id,
        from_user,
        question,
        msg_id,
        trace_id,
    )
    return PlainTextResponse("success", media_type=TEXT_UTF8_MEDIA_TYPE)
