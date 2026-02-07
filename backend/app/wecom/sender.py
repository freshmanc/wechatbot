"""
企业微信发消息到群聊。
自建应用发群消息：先获取 access_token，再调「应用推送消息到群聊」接口。
文档：https://developer.work.weixin.qq.com/document/path/90248
"""
import time
from typing import Optional

import httpx

from app.config import get_settings

# access_token 内存缓存（生产建议用 Redis）
_token_cache: dict[str, tuple[float, str]] = {}


def _get_access_token() -> str:
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
        raise RuntimeError(f"gettoken failed: {data}")
    token = data["access_token"]
    _token_cache[key] = (now + min(7200, int(data.get("expires_in", 7200))), token)
    return token


def send_group_text(chat_id: str, content: str, mentioned_list: Optional[list[str]] = None) -> dict:
    """
    应用推送文本消息到群聊。
    chat_id: 群聊 ID（从回调 ChatId 获取）
    content: 文本内容
    mentioned_list: 要 @ 的成员 userid 列表，可选
    """
    token = _get_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"
    body = {
        "chatid": chat_id,
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": mentioned_list or [],
        },
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        return r.json()
