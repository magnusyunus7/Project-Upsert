# -*- coding: utf-8 -*-
"""
chime.py —— QR login(QR Code -> userId + token)
================================================================================

Features:putQR code string(or QR code URL)Hand over aimedb server,fetch userId And token.

Corresponding interface:POST https://ai.sys-allnet.cn/wc_aime/api/get_data

--------------------------------------------------------------------------------
Agreement Basis
--------------------------------------------------------------------------------
source/ChimeLib.NET/ChimeLib/NET/COMM/CCommGetUserData.cs
    CCommGetUserData_Create(strGameID, strChipID, strCommonKey,
                            strQRData, strTitleKey, serverURLIndex)
        strGameID  = "MAID"
        strChipID  = KeychipID
        strQRData  = QR code string[20:]      <- text CCommQRCode.EraseHashIdentifier()
        strTitleKey= "SDGB"

source/ChimeLib.NET/ChimeLib/NET/COMM/CCommQRCode.cs
    IsValid()              : Prefix "SGWC"(Chime.WechatID) + Offset 4 is gameID
    GetTimeStamp()         : [8:20]  12 Bit yymmddHHMMss
    EraseHashIdentifier()  : [20:]   64 Potential loading

source/Assembly-CSharp/Manager/ChimeReaderManager.cs:250-255
    KeychipID = AMDaemon.System.KeychipId.Value
    TitleKey  = AMDaemon.System.GameId
    GameID    = "MAID"

docs/maimai DX_QR loginmd
    - first name key = SHA-256(chipID + timestamp + SIGN_KEY) Uppercase hex
    - ★ requestHead[nocan]Belt Content-Type,Otherwise, the server returns errorID=57
    - qrCode What the field says is 64 Potential loading,Not complete 84 String

--------------------------------------------------------------------------------
call exampleExample
--------------------------------------------------------------------------------
    from api import ParseQRCode

    user_id, token = ParseQRCode("SGWCMAID2610022219463A...")
    # You can also pass the QR code directly URL
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

from config import KEYCHIP_ID

# =============================================================================
# aimedb QR loginConstant(Originally at config.py,2026-10-06 sink to this module)
# =============================================================================
# Basis:source/ChimeLib.NET/ChimeLib/NET/COMM/CCommGetUserData.cs
#       + docs Branch《maimai DX_QR login》

#: aimedb server
AIMEDB_HOST = "ai.sys-allnet.cn"
AIMEDB_PORT = 443
AIMEDB_PATH = "/wc_aime/api/get_data"

#: first nameKey(With Leading X,32 Character)
#: chimelib_dll.dll .rdata UTF-16 @0x00B040,packetMatch
QR_SIGN_KEY = "XcW5FW4cPArBXEk4vzKz3CIrMuA5EVVW"

#: Fixed Field
QR_OPEN_GAME_ID = "MAID"
QR_TITLE_KEY = "SDGB"
QR_USER_AGENT = "WC_AIME_LIB"

from .log_setup import log_debug, log_error, log_info, log_request, log_response

# =============================================================================
# QR code format constant(CCommQRCode.cs + )
# =============================================================================

QR_PREFIX = "SGWC"              # Chime.WechatID
QR_GAME_ID = "MAID"
QR_PREFIX_LEN = 20              # SGWC(4) + MAID(4) + timestamp(12)
QR_PAYLOAD_LEN = 64
QR_TOTAL_LEN = QR_PREFIX_LEN + QR_PAYLOAD_LEN   # 84

#: defaultmachine state chipID
#:
#: ★★ Must use**Full Format**(Hyphenated),Not short value —— this isPieceof
#:     source/Assembly-CSharp/Manager/ChimeReaderManager.cs:250
#:         KeychipID = AMDaemon.System.KeychipId.Value;          // Full Format
#:     source/Assembly-CSharp/Manager/ChimeReaderManager.cs:255
#:         Chime.Instance.Init(GameID, KeychipID, _chimeDevice, TitleKey);
#:     andserverthatuseofisshortValue:
#:     source/Assembly-CSharp/Net.Packet.Mai2/PacketGetGameSetting.cs:23
#:         clientId = AMDaemon.System.KeychipId.ShortValue;      // shortValue
#:
#:     i.e.:aimedb useFull KeychipId,serveruse ShortValue.
#:     docs Branched《QR login》§3.4 inAlsohasCorrespondingpackettowards
#:     token And chipID useMeetingslead toFollow-upinterface"returnCode=1 But not out of stock.".
DEFAULT_CHIP_ID = KEYCHIP_ID


# =============================================================================
# Internal Tools
# =============================================================================

def _extract_qr_from_url(url: str) -> str:
    """
    From QR Code URL fetchFull 84 String.

    URL Shape like:
        https://wq.wahlap.net/qrcode/req/MAID2610022219463A....html?l=...&t=...&d=...
    Take /qrcode/req/ And .html between 80 Character,Fill in front "SGWC".
    """
    path = urlparse(url).path
    match = re.search(r"/qrcode/req/([^/]+)\.html", path)
    if not match:
        raise ValueError("URL nonofetchQR Codedata:" + url)
    return QR_PREFIX + match.group(1)


def _normalize_qr(qr_input: str) -> str:
    """URL or string -> standard 84 Character QR code string(With formatting checksum)."""
    qr = (qr_input or "").strip()

    if qr.startswith("http://") or qr.startswith("https://"):
        log_debug("is URL,Extract the QR code string first")
        qr = _extract_qr_from_url(qr)

    if len(qr) != QR_TOTAL_LEN:
        raise ValueError(
            "The length of the QR code should be " + str(QR_TOTAL_LEN) + " Character,Actual " + str(len(qr)) + " Character:" + qr
        )
    if not qr.startswith(QR_PREFIX):
        raise ValueError("The QR code must be '" + QR_PREFIX + "' Beginning:" + qr)
    if qr[4:8] != QR_GAME_ID:
        raise ValueError(
            "QR Code GameID should be '" + QR_GAME_ID + "',Actual '" + qr[4:8] + "':" + qr
        )
    if not all(c in "0123456789ABCDEF" for c in qr[QR_PREFIX_LEN:]):
        raise ValueError("QR code payload must be in uppercase hex:" + qr)

    log_debug(
        "QR code verification passed:timestamp=" + qr[8:20]
        + " payload_len=" + str(len(qr[QR_PREFIX_LEN:]))
    )
    return qr


def _build_body(qr_string: str, chip_id: str) -> Tuple[bytes, str, str]:
    """
    constructrequest body.

    first name(text §4.1):
        key = SHA-256(chipID + timestamp + SIGN_KEY).hexdigest().upper()
        ★ inExcluding qrCode,Excluding titlekey

    qrCode Field(CCommQRCode.EraseHashIdentifier):
        qr_string[20:]  i.e. 64 Potential loading

    Returns:
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
    Send HTTPS POST and parse JSON Response.

    ★ requestHeadOnly Connection / User-Agent / Content-Length.
      nocanPlus Content-Type —— Plus, you'll get errorID=57(text §3.3).
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "Connection": "Keep-Alive",
        "User-Agent": QR_USER_AGENT,
        "Content-Length": str(len(body_bytes)),
        # ★ placenoPlus Content-Type
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
        raise RuntimeError("aimedb Response is not legal JSON:" + text[:300]) from exc


def _parse(resp: dict) -> Tuple[int, str]:
    """parseResponse,returns (user_id, token)."""
    error_id = resp.get("errorID", -1)
    user_id = resp.get("userID", -1)
    token = resp.get("token", "") or ""

    if error_id != 0:
        raise RuntimeError(
            "QR loginFailed:errorID=" + str(error_id) + ",Response=" + json.dumps(resp, ensure_ascii=False)
            + "\n  errorID=57 isQR CodeAlready/Already in use,or request headband Content-Type"
        )
    if user_id == -1 or not token:
        raise RuntimeError(
            "QR loginFailed:userID=" + str(user_id) + ", token='" + token + "'"
        )
    return int(user_id), str(token)


# =============================================================================
# Public API
# =============================================================================

def ParseQRCode(qr_input: str, *, chip_id: str = DEFAULT_CHIP_ID) -> Tuple[int, str]:
    """
    parseQR Codefetch userId And token.

    Parameter:
        qr_input: 84 Character QR code string(SGWCMAID...),or QR code URL
        chip_id:  machine state Keychip shortValue(Optional,defaultTake config.CLIENT_ID)

    Returns:
        (user_id, token) Tuples,can be passed directly to GetUserPreview / UserLogin etc

    Exceptions:
        ValueError:   Invalid QR code format
        RuntimeError: serverreturnserrorornetworkExceptions
    """
    log_info("parseQR Codelogin:chip_id=" + chip_id)

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

    log_info("Send login request:timestamp=" + timestamp + " host=" + AIMEDB_HOST + AIMEDB_PATH)
    resp = _send(body_bytes)
    user_id, token = _parse(resp)

    log_info("QR loginSuccess:user_id=" + str(user_id) + " token=" + token[:8] + "...(length "
             + str(len(token)) + ")")
    return user_id, token


# =============================================================================
# Run separately(debug)
# =============================================================================

if __name__ == "__main__":
    import sys

    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("chime_test")
        try:
            if len(sys.argv) < 2:
                print("usage: python -m api.chime <QR code string orURL> [chip_id]")
                return 1
            chip = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_CHIP_ID
            user_id, token = ParseQRCode(sys.argv[1], chip_id=chip)
            print("")
            print("user_id =", user_id)
            print("token   =", token)
            return 0
        except Exception as exc:
            log_error("QR loginFailed:" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
