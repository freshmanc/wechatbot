"""
企业微信消息加解密 — 严格按官方文档实现
https://developer.work.weixin.qq.com/document/path/90968
AES-256-CBC, PKCS#7, IV=前16字节AESKey, 签名=sha1(sort(token,timestamp,nonce,msg_encrypt))
"""
import base64
import hashlib
import os
import struct
from typing import Tuple

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def _get_aes_key(encoding_aes_key: str) -> bytes:
    """EncodingAESKey 43字符，Base64解码后为32字节。文档：AESKey=Base64_Decode(EncodingAESKey + '=')"""
    key_b64 = encoding_aes_key.strip()
    if len(key_b64) == 43:
        key_b64 += "="
    return base64.b64decode(key_b64)


def _signature(token: str, timestamp: str, nonce: str, msg_encrypt: str) -> str:
    """消息体签名：sha1(sort(token, timestamp, nonce, msg_encrypt))，按参数值字典序拼接后 sha1，小写十六进制"""
    sort_str = "".join(sorted([token, timestamp, nonce, msg_encrypt]))
    return hashlib.sha1(sort_str.encode()).hexdigest().lower()


def verify_signature(
    token: str,
    timestamp: str,
    nonce: str,
    msg_encrypt: str,
    msg_signature: str,
) -> bool:
    """校验 URL 或 body 中的 msg_signature"""
    return _signature(token, timestamp, nonce, msg_encrypt) == msg_signature.lower()


def decrypt(
    encoding_aes_key: str,
    msg_encrypt: str,
    corp_id: str,
) -> str:
    """
    解密企业微信回调密文。
    密文格式：16 随机字节 + 4 字节 msg_len(网络序) + msg + receiveid。
    企业应用回调时 receiveid 为 corpid，解密后需校验尾部与 corp_id 一致。
    """
    aes_key = _get_aes_key(encoding_aes_key)
    iv = aes_key[:16]
    raw = base64.b64decode(msg_encrypt)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    rand_msg = unpad(cipher.decrypt(raw), AES.block_size)

    # 去掉 16 随机字节，取 4 字节长度（大端）
    content = rand_msg[16:]
    msg_len = struct.unpack(">I", content[:4])[0]
    msg = content[4 : 4 + msg_len].decode("utf-8")
    receive_id = content[4 + msg_len :].decode("utf-8")

    if receive_id != corp_id:
        raise ValueError("receiveid 与 corpid 不一致")
    return msg


def encrypt(
    encoding_aes_key: str,
    plain_text: str,
    corp_id: str,
) -> str:
    """
    加密回复消息。
    明文字符串：16 随机字节 + 4 字节 msg 长度(网络序) + msg + receiveid(corpid)。
    """
    aes_key = _get_aes_key(encoding_aes_key)
    iv = aes_key[:16]
    msg_bytes = plain_text.encode("utf-8")
    rand_prefix = os.urandom(16)
    msg_len_bytes = struct.pack(">I", len(msg_bytes))
    to_encrypt = rand_prefix + msg_len_bytes + msg_bytes + corp_id.encode("utf-8")
    to_encrypt = pad(to_encrypt, AES.block_size)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(to_encrypt)
    return base64.b64encode(encrypted).decode("ascii")


def encrypt_reply_xml(
    token: str,
    encoding_aes_key: str,
    corp_id: str,
    reply_msg: str,
    timestamp: str,
    nonce: str,
) -> str:
    """生成被动回复的加密 XML 包。先加密 reply_msg，再计算签名，最后包成 XML。"""
    msg_encrypt = encrypt(encoding_aes_key, reply_msg, corp_id)
    signature = _signature(token, timestamp, nonce, msg_encrypt)
    return f"""<xml>
<Encrypt><![CDATA[{msg_encrypt}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
