# -*- coding: utf-8 -*-
"""
ping.py —— 心跳探活（PingMaimaiChn）
================================================================================

功能：向游戏服务器发一次心跳，确认链路可达。

对应接口：PingMaimaiChn
请求体  ：{}（source/Assembly-CSharp/Net.VO.Mai2/PingRequestVO.cs 是空类）
响应    ：{"result": "Pong"}

★ 接口名（容易写错，注意）：
    source/Assembly-CSharp/Net.Packet.Mai2/PacketPing.cs:22
        new NetQuery<PingRequestVO, PingResponseVO>("Ping", 0uL);
    客户端传的逻辑名是 **"Ping"**，NetQuery.cs:14 再补上 "MaimaiChn" 后缀，
    所以混淆用的全名是 "PingMaimaiChn"：
        md5("PingMaimaiChn" + "8bF76dE9") = 3bae8c1162b3148abcfc38a89c03e3e7
    本模块传 "Ping" 即可，obfuscate_api_name 会自动补后缀。

    （Packet.cs:96 用 Query.Api.StartsWith("Ping") 判断是否心跳包，
      也是基于补完后缀的 "PingMaimaiChn"。）

★ 为什么要跑它（不只是探活）：
    Packet.cs:189  非 Ping 接口都会带 HTTP 头 number = GameManager.PingMsec
    PingChecker.cs:227   GameManager.PingMsec = Ping 包的往返毫秒

    所以 **Ping 是 number 头的唯一来源**。先 Ping 一次，后面的业务请求才会
    带上真实 number（真机实测 63ms）；不 Ping 则 number = 0，
    与真机开机后第一屏（还没跑过心跳）的行为一致。
    MaimaiNetClient 在收到 Ping 响应后会自动把往返毫秒记进 client.ping_msec。

调用示例：
    from api import Ping
    if Ping():
        print("服务器可达")
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
    心跳探活。

    参数：
        client_id:  机台短值（可选）
        timeout_ms: 超时毫秒（可选）
        client:     可复用的 MaimaiNetClient（可选）

    返回：
        True = 服务器返回 "Pong"
    """
    log_info("发送心跳探活")

    raw = request_dict(
        "Ping", {},
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    result = raw.get("result", "")
    ok = (result == "Pong")
    if ok:
        log_info("心跳正常：result=Pong")
    else:
        log_warning("心跳返回异常：result=" + str(result))
    return ok


if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("ping_test")
        try:
            ok = Ping()
            print("")
            print("服务器可达：" + str(ok))
            return 0 if ok else 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
