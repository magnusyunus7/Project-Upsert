# -*- coding: utf-8 -*-
"""
chime.py —— 扫码登录（二维码 -> userId + token）
================================================================================

功能：把微信二维码串（或二维码 URL）交给 aimedb 服务器，换取 userId 与 token。

对应接口：POST https://ai.sys-allnet.cn/wc_aime/api/get_data

--------------------------------------------------------------------------------
协议依据
--------------------------------------------------------------------------------
source/ChimeLib.NET/ChimeLib/NET/COMM/CCommGetUserData.cs
    CCommGetUserData_Create(strGameID, strChipID, strCommonKey,
                            strQRData, strTitleKey, serverURLIndex)
        strGameID  = "MAID"
        strChipID  = KeychipID
        strQRData  = 二维码串[20:]      <- 见 CCommQRCode.EraseHashIdentifier()
        strTitleKey= "SDGB"

source/ChimeLib.NET/ChimeLib/NET/COMM/CCommQRCode.cs
    IsValid()              : 前缀 "SGWC"(Chime.WechatID) + 偏移 4 处为 gameID
    GetTimeStamp()         : [8:20]  12 位 yymmddHHMMss
    EraseHashIdentifier()  : [20:]   64 位载荷

source/Assembly-CSharp/Manager/ChimeReaderManager.cs:250-255
    KeychipID = AMDaemon.System.KeychipId.Value
    TitleKey  = AMDaemon.System.GameId
    GameID    = "MAID"

docs/舞萌DX_扫码登录协议技术规范.md
    - 签名 key = SHA-256(chipID + timestamp + SIGN_KEY) 大写 hex
    - ★ 请求头【绝不能】带 Content-Type，否则服务端返回 errorID=57
    - qrCode 字段传的是 64 位载荷，不是完整 84 字符串

--------------------------------------------------------------------------------
调用示例
--------------------------------------------------------------------------------
    from api import ParseQRCode

    user_id, token = ParseQRCode("SGWCMAID2610022219463A...")
    # 也可以直接传二维码 URL
    user_id, token = ParseQRCode("https://wq.wahlap.net/qrcode/req/MAID261002....html?l=...")
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import ssl
from datetime import datetime
from typing import Tuple
from urllib.parse import urlparse

from config import (
    AIMEDB_HOST,
    AIMEDB_PATH,
    AIMEDB_PORT,
    KEYCHIP_ID,
    QR_OPEN_GAME_ID,
    QR_SIGN_KEY,
    QR_TITLE_KEY,
    QR_USER_AGENT,
)

from .log_setup import log_debug, log_error, log_info, log_request, log_response

# =============================================================================
# 二维码格式常量（CCommQRCode.cs + 技术规范）
# =============================================================================

QR_PREFIX = "SGWC"              # Chime.WechatID
QR_GAME_ID = "MAID"
QR_PREFIX_LEN = 20              # SGWC(4) + MAID(4) + timestamp(12)
QR_PAYLOAD_LEN = 64
QR_TOTAL_LEN = QR_PREFIX_LEN + QR_PAYLOAD_LEN   # 84

#: 默认机台 chipID
#:
#: ★★ 必须用**完整形式**（带连字符），不是短值 —— 这是个容易搞错的点：
#:     source/Assembly-CSharp/Manager/ChimeReaderManager.cs:250
#:         KeychipID = AMDaemon.System.KeychipId.Value;          // 完整形式
#:     source/Assembly-CSharp/Manager/ChimeReaderManager.cs:255
#:         Chime.Instance.Init(GameID, KeychipID, _chimeDevice, TitleKey);
#:     而游戏服务器那边用的是短值：
#:     source/Assembly-CSharp/Net.Packet.Mai2/PacketGetGameSetting.cs:23
#:         clientId = AMDaemon.System.KeychipId.ShortValue;      // 短值
#:
#:     即：aimedb 扫码用完整 KeychipId，游戏服务器用 ShortValue。
#:     docs/舞萌DX_扫码登录协议技术规范.md §3.4 的抓包验证向量也是
#:     chipID = "XXXX-XXXXXXXXXXX"。
#:     token 与 chipID 绑定，用错会导致后续接口「returnCode=1 但不落库」。
DEFAULT_CHIP_ID = KEYCHIP_ID


# =============================================================================
# 内部工具
# =============================================================================

def _extract_qr_from_url(url: str) -> str:
    """
    从二维码 URL 提取完整 84 字符串。

    URL 形如：
        https://wq.wahlap.net/qrcode/req/MAID2610022219463A....html?l=...&t=...&d=...
    取 /qrcode/req/ 与 .html 之间的 80 字符，前面补 "SGWC"。
    """
    path = urlparse(url).path
    match = re.search(r"/qrcode/req/([^/]+)\.html", path)
    if not match:
        raise ValueError("URL 路径格式不符合预期，无法提取二维码数据：" + url)
    return QR_PREFIX + match.group(1)


def _normalize_qr(qr_input: str) -> str:
    """URL 或字符串 -> 标准 84 字符二维码串（含格式校验）。"""
    qr = (qr_input or "").strip()

    if qr.startswith("http://") or qr.startswith("https://"):
        log_debug("输入是 URL，先提取二维码字符串")
        qr = _extract_qr_from_url(qr)

    if len(qr) != QR_TOTAL_LEN:
        raise ValueError(
            "二维码长度应为 " + str(QR_TOTAL_LEN) + " 字符，实际 " + str(len(qr)) + " 字符：" + qr
        )
    if not qr.startswith(QR_PREFIX):
        raise ValueError("二维码必须以 '" + QR_PREFIX + "' 开头：" + qr)
    if qr[4:8] != QR_GAME_ID:
        raise ValueError(
            "二维码 GameID 应为 '" + QR_GAME_ID + "'，实际 '" + qr[4:8] + "'：" + qr
        )
    if not all(c in "0123456789ABCDEF" for c in qr[QR_PREFIX_LEN:]):
        raise ValueError("二维码载荷必须为大写十六进制：" + qr)

    log_debug(
        "二维码校验通过：timestamp=" + qr[8:20]
        + " payload_len=" + str(len(qr[QR_PREFIX_LEN:]))
    )
    return qr


def _build_body(qr_string: str, chip_id: str) -> Tuple[bytes, str, str]:
    """
    构造请求体。

    签名（技术规范 §4.1）：
        key = SHA-256(chipID + timestamp + SIGN_KEY).hexdigest().upper()
        ★ 拼接里不含 qrCode、不含 titlekey

    qrCode 字段（CCommQRCode.EraseHashIdentifier）：
        qr_string[20:]  即 64 位载荷

    返回：
        (body_bytes, timestamp, key)
    """
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    key = hashlib.sha256((chip_id + timestamp + QR_SIGN_KEY).encode()).hexdigest().upper()

    body_dict = {
        "chipID": chip_id,
        "openGameID": QR_OPEN_GAME_ID,
        "key": key,
        "qrCode": qr_string[QR_PREFIX_LEN:],
        "timestamp": timestamp,
        "titlekey": QR_TITLE_KEY,
    }
    body_bytes = json.dumps(body_dict, separators=(",", ":")).encode("utf-8")
    return body_bytes, timestamp, key


def _send(body_bytes: bytes) -> dict:
    """
    发送 HTTPS POST 并解析 JSON 响应。

    ★ 请求头只放 Connection / User-Agent / Content-Length。
      绝不能加 Content-Type —— 加了会得到 errorID=57（技术规范 §3.3）。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "Connection": "Keep-Alive",
        "User-Agent": QR_USER_AGENT,
        "Content-Length": str(len(body_bytes)),
        # ★ 此处刻意不加 Content-Type
    }

    conn = http.client.HTTPSConnection(AIMEDB_HOST, AIMEDB_PORT, context=ctx, timeout=20)
    try:
        conn.request("POST", AIMEDB_PATH, body=body_bytes, headers=headers)
        resp = conn.getresponse()
        text = resp.read().decode("utf-8")
        status = resp.status
    finally:
        conn.close()

    log_response(status=status, body=text, api_name="aimedb/get_data")
    try:
        return json.loads(text)
    except Exception as exc:
        raise RuntimeError("aimedb 响应不是合法 JSON：" + text[:300]) from exc


def _parse(resp: dict) -> Tuple[int, str]:
    """解析响应，返回 (user_id, token)。"""
    error_id = resp.get("errorID", -1)
    user_id = resp.get("userID", -1)
    token = resp.get("token", "") or ""

    if error_id != 0:
        raise RuntimeError(
            "扫码登录失败：errorID=" + str(error_id) + "，响应=" + json.dumps(resp, ensure_ascii=False)
            + "\n  提示：errorID=57 通常是二维码已失效/已被使用，或请求头带了 Content-Type"
        )
    if user_id == -1 or not token:
        raise RuntimeError(
            "扫码登录失败：userID=" + str(user_id) + ", token='" + token + "'"
        )
    return int(user_id), str(token)


# =============================================================================
# 公开 API
# =============================================================================

def ParseQRCode(qr_input: str, *, chip_id: str = DEFAULT_CHIP_ID) -> Tuple[int, str]:
    """
    解析二维码并换取 userId 与 token。

    参数：
        qr_input: 84 字符二维码串（SGWCMAID...），或二维码 URL
        chip_id:  机台 Keychip 短值（可选，默认取 config.CLIENT_ID）

    返回：
        (user_id, token) 元组，可直接传给 UserPreview / UserLogin 等

    异常：
        ValueError:   二维码格式不合法
        RuntimeError: 服务器返回错误或网络异常
    """
    log_info("解析二维码登录：chip_id=" + chip_id)

    qr_string = _normalize_qr(qr_input)
    body_bytes, timestamp, key = _build_body(qr_string, chip_id)

    log_request(
        url="https://" + AIMEDB_HOST + ":" + str(AIMEDB_PORT) + AIMEDB_PATH,
        body={
            "chipID": chip_id,
            "openGameID": QR_OPEN_GAME_ID,
            "key": key,
            "qrCode": qr_string[QR_PREFIX_LEN:],
            "timestamp": timestamp,
            "titlekey": QR_TITLE_KEY,
        },
        headers={"Connection": "Keep-Alive", "User-Agent": QR_USER_AGENT,
                 "Content-Length": str(len(body_bytes))},
        api_name="aimedb/get_data",
    )

    log_info("发送登录请求：timestamp=" + timestamp + " host=" + AIMEDB_HOST + AIMEDB_PATH)
    resp = _send(body_bytes)
    user_id, token = _parse(resp)

    log_info("扫码登录成功：user_id=" + str(user_id) + " token=" + token[:8] + "...（长度 "
             + str(len(token)) + "）")
    return user_id, token


# =============================================================================
# 单独运行（调试）
# =============================================================================

if __name__ == "__main__":
    import sys

    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("chime_test")
        try:
            if len(sys.argv) < 2:
                print("用法: python -m api.chime <二维码串或URL> [chip_id]")
                return 1
            chip = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CHIP_ID
            user_id, token = ParseQRCode(sys.argv[1], chip_id=chip)
            print("")
            print("user_id =", user_id)
            print("token   =", token)
            return 0
        except Exception as exc:
            log_error("扫码登录失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
