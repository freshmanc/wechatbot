"""
企业微信发消息到群聊。
自建应用发群消息：先获取 access_token，再调「应用推送消息到群聊」接口。
文档：https://developer.work.weixin.qq.com/document/path/90248

联调第三关：若 @ 后无回复，看后端日志中 appchat/send 的 errcode；
常见原因：应用无群聊发消息权限、chat_id 无效、Secret/AgentID 配错。

稳定性：gettoken 有频率限制，token 缓存约 7200s（官方 expires_in），提前 60s 刷新，避免高频失败。
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# access_token 内存缓存（约 7200s，提前 60s 刷新；生产可改为 Redis）
_token_cache: dict[str, tuple[float, str]] = {}


def _get_access_token_sync() -> str:
    """获取企业微信 access_token（带简单内存缓存）。"""
    s = get_settings()
    key = f"{s.wecom_corp_id}_{s.wecom_agent_id}"
    now = time.time()
    if key in _token_cache:
        expires_at, token = _token_cache[key]
        if expires_at > now + 60:  # 提前 60s 刷新
            return token
    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    with httpx.Client(timeout=10.0) as client:
        r = client.get(
            url,
            params={"corpid": s.wecom_corp_id, "corpsecret": s.wecom_secret},
        )
        r.raise_for_status()
        data = r.json()
    if data.get("errcode") != 0:
        logger.warning("wecom gettoken failed: errcode=%s errmsg=%s", data.get("errcode"), data.get("errmsg"))
        raise RuntimeError(f"gettoken failed: {data}")
    token = data["access_token"]
    _token_cache[key] = (now + min(7200, int(data.get("expires_in", 7200))), token)
    return token


def _get_access_token() -> str:
    """同步获取 token（供 send_group_text 用）。"""
    return _get_access_token_sync()


async def async_send_group_text(
    chat_id: str,
    content: str,
    mentioned_list: Optional[list[str]] = None,
) -> dict:
    """异步：获取 token 后调用 appchat/send，供回调后台任务使用。"""
    token = await asyncio.to_thread(_get_access_token_sync)
    url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"
    body = {
        "chatid": chat_id,
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list or [],
        },
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
        if data.get("errcode") != 0:
            logger.warning(
                "wecom appchat/send failed: errcode=%s errmsg=%s chat_id=%s",
                data.get("errcode"), data.get("errmsg"), chat_id,
            )
        return data


def send_group_text(chat_id: str, content: str, mentioned_list: Optional[list[str]] = None) -> dict:
    """
    应用推送文本消息到群聊（同步）。
    chat_id: 群聊 ID（从回调 ChatId 获取）
    content: 文本内容
    mentioned_list: 要 @ 的成员 userid 列表，可选
    """
    token = _get_access_token_sync()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"
    body = {
        "chatid": chat_id,
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list or [],
        },
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    with httpx.Client(timeout=10.0) as client:
        r = client.post(url, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
        if data.get("errcode") != 0:
            logger.warning(
                "wecom appchat/send failed: errcode=%s errmsg=%s chat_id=%s",
                data.get("errcode"), data.get("errmsg"), chat_id,
            )
        return data
