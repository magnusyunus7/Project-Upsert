# -*- coding: utf-8 -*-
"""
ping.py —— Heartbeat Probe Alive（PingMaimaiChn）
================================================================================

Features：Send a heartbeat to the game server，text。

Corresponding interface：PingMaimaiChn
request body  ：{}（source/Assembly-CSharp/Net.VO.Mai2/PingRequestVO.cs isemptytext）
Response    ：{"result": "Pong"}

★ interfaceFirst name（Easily misspelled，note）：
    source/Assembly-CSharp/Net.Packet.Mai2/PacketPing.cs:22
        new NetQuery<PingRequestVO, PingResponseVO>("Ping", 0uL);
    The logical name passed by the client is **"Ping"**，NetQuery.cs:14 Make it up again "MaimaiChn" Suffix，
    So the full name of the confusion is "PingMaimaiChn"：
        md5("PingMaimaiChn" + "8bF76dE9") = 3bae8c1162b3148abcfc38a89c03e3e7
    textPassing on "Ping" Just do it，obfuscate_api_name Will autofill suffixes。

    （Packet.cs:96 use Query.Api.StartsWith("Ping") Determine if the cardiac packet，
      It is also based on the completion suffix "PingMaimaiChn"。）

★ Why run it?（It's not just looking for work.）：
    Packet.cs:189  non- Ping interfaceallMeetingsBelt HTTP Head number = GameManager.PingMsec
    PingChecker.cs:227   GameManager.PingMsec = Ping Packet round trip in milliseconds

    So **Ping is number The only source of the head**。First Ping Once，Subsequent business requests will
    Bring the real thing number（real machineMeasured 63ms）；No Ping Then number = 0，
    First screen after starting up with a real machine（textHeartbeat）oftextforMatch。
    MaimaiNetClient Received at Ping Automatically counts round-trip milliseconds after response client.ping_msec。

call exampleExample：
    from api import Ping
    if Ping():
        print("servertext")
"""

from __future__ import annotations

from typing import Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict


def Ping(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> bool:
    """
    Heartbeat Probe Alive。

    Parameter：
        client_id:  machineStageshortValue（Optional）
        timeout_ms: timeout milliseconds（Optional）
        client:     Reusable MaimaiNetClient（Optional）

    returntimes：
        True = serverreturntimes "Pong"
    """
    log_info("Send Heartbeat Probe Active")

    raw = request_dict(
        "Ping", {},
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    result = raw.get("result", "")
    ok = (result == "Pong")
    if ok:
        log_info("Normal heartbeat：result=Pong")
    else:
        log_warning("Heartbeat returned abnormal：result=" + str(result))
    return ok


if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("ping_test")
        try:
            ok = Ping()
            print("")
            print("servertext：" + str(ok))
            return 0 if ok else 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
