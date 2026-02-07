"""
企业微信回调 URL 校验与消息体验签。
GET /wecom/callback?msg_signature=xxx&timestamp=xxx&nonce=xxx&echostr=xxx
需解密 echostr 并原样返回以通过 URL 校验。
"""
from app.wecom.crypto import decrypt, verify_signature


def verify_url_and_echo(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str:
    """
    校验 URL 时企业微信会带 echostr（已加密）。
    验签后解密 echostr，原样返回明文即通过校验。
    """
    if not verify_signature(token, timestamp, nonce, echostr, msg_signature):
        raise ValueError("URL 校验签名失败")
    return decrypt(encoding_aes_key, echostr, corp_id)


def verify_callback_body(
    token: str,
    timestamp: str,
    nonce: str,
    msg_encrypt: str,
    msg_signature: str,
) -> bool:
    """校验 POST body 中加密内容的签名（解密前调用）。"""
    return verify_signature(token, timestamp, nonce, msg_encrypt, msg_signature)
