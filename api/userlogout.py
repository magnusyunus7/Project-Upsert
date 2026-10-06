# -*- coding: utf-8 -*-
"""
userlogout.py —— 用户登出（UserLogoutApi）
================================================================================

功能：结束登录会话，可选上报本次会话的网络统计（delayLog）。

对应接口：UserLogoutApi
请求体  ：两种形态，见 source/Assembly-CSharp/Net.Packet.Mai2/PacketUserLogout.cs:22-63
            type == 1 (Logout) -> UserLogoutRequest2VO（含 delayLog）
            其他 type          -> UserLogoutRequestVO （不含 delayLog）

--------------------------------------------------------------------------------
登出类型（source/Assembly-CSharp/Net.VO.Mai2/LogoutType.cs）
--------------------------------------------------------------------------------
    None   = 0
    Logout = 1   正常登出（带 delayLog 统计）
    Cancel = 2   取消 / 强制登出指定座席（NetPacketUtil.cs:47）
    Error  = 3   错误强制登出（GameMain.cs:91）
    TestIn = 4   测试登入 / 顶号（GameMain.cs:104）
    Quit   = 5   退出时强制登出，可释放残留会话（GameMainObject.cs:200）

★ 真机会话结束时用的是 type=4（TestIn），见 source/2026-10-05.log:125。

★ delayLog 结构（source/Assembly-CSharp/Net.VO.Mai2/DelayLog.cs）
    request 是定长 26 的数组（DelayLog.cs:17  new RequestAPI[26]），
    每个元素 {count, size, msec, retry}。

调用示例：
    from api import UserLogout, LogoutType
    UserLogout(12345678, token, login.loginDateTime,
               logout_type=LogoutType.TestIn, region_id=1, place_id=1000)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLACE_ID, REGION_ID, TIMEOUT_MS

from .log_setup import log_debug, log_error, log_info
from .maimai_net import MaimaiNetClient, request_dict

#: DelayLog.request 的定长（DelayLog.cs:17）
DELAY_LOG_SLOTS = 26


class LogoutType:
    """登出类型（对应 Net.VO.Mai2.LogoutType）。"""
    None_ = 0
    Logout = 1      # 正常登出（带 delayLog）
    Cancel = 2      # 取消 / 强制登出
    Error = 3       # 错误强制登出
    TestIn = 4      # 测试登入 / 顶号（真机会话结束用这个）
    Quit = 5        # 退出强制登出


@dataclass
class RequestAPI:
    """单个接口的统计（对应 Net.VO.Mai2/RequestAPI.cs）。"""
    count: int = 0
    size: int = 0
    msec: int = 0
    retry: int = 0


@dataclass
class DelayLog:
    """会话网络统计（对应 Net.VO.Mai2/DelayLog.cs）。"""
    dlRequests: int = 0
    dlSize: int = 0
    dlRetry: int = 0
    loginMsec: int = 0
    saveMsec: int = 0
    reductionMusic: int = 0
    reductionItem: int = 0
    request: List[RequestAPI] = field(
        default_factory=lambda: [RequestAPI() for _ in range(DELAY_LOG_SLOTS)]
    )


@dataclass
class UserLogoutRequestVO:
    """简单登出请求 VO（对应 UserLogoutRequestVO）。"""
    userId: int
    accessCode: str = ""
    regionId: int = 0
    placeId: int = 0
    clientId: str = ""
    loginDateTime: int = 0
    type: int = 0


@dataclass
class UserLogoutRequest2VO:
    """完整登出请求 VO（对应 UserLogoutRequest2VO，含 delayLog）。"""
    userId: int
    accessCode: str = ""
    regionId: int = 0
    placeId: int = 0
    clientId: str = ""
    loginDateTime: int = 0
    type: int = 0
    delayLog: Optional[DelayLog] = None


@dataclass
class UserLogoutResponseVO:
    """响应 VO（对应 UserLogoutResponseVO）。"""
    returnCode: int = 0


def create_empty_delay_log() -> DelayLog:
    """创建全零的 DelayLog（26 个槽位）。"""
    return DelayLog()


def create_delay_log_from_stats(
    requests_stats: Optional[List[Dict[str, Any]]] = None,
    *,
    dl_requests: int = 0,
    dl_size: int = 0,
    dl_retry: int = 0,
    login_msec: int = 0,
    save_msec: int = 0,
    reduction_music: int = 0,
    reduction_item: int = 0,
) -> DelayLog:
    """
    用统计数据构造 DelayLog。

    参数：
        requests_stats: 每个接口的统计列表，元素形如
                        {"count":1,"size":2090,"msec":73,"retry":0}
                        按 DelayLog.request 的槽位顺序填入（最多 26 个）
    """
    dl = DelayLog(
        dlRequests=dl_requests, dlSize=dl_size, dlRetry=dl_retry,
        loginMsec=login_msec, saveMsec=save_msec,
        reductionMusic=reduction_music, reductionItem=reduction_item,
    )
    for i, stat in enumerate(requests_stats or []):
        if i >= DELAY_LOG_SLOTS:
            break
        dl.request[i] = RequestAPI(
            count=int(stat.get("count", 0)),
            size=int(stat.get("size", 0)),
            msec=int(stat.get("msec", 0)),
            retry=int(stat.get("retry", 0)),
        )
    return dl


def UserLogout(
    user_id: int,
    token: str,
    login_date_time: int,
    *,
    logout_type: int = LogoutType.TestIn,
    access_code: str = "",
    region_id: int = REGION_ID,
    place_id: int = PLACE_ID,
    client_id: str = CLIENT_ID,
    delay_log: Optional[DelayLog] = None,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> UserLogoutResponseVO:
    """
    用户登出。

    参数：
        user_id:         用户 ID（必填）
        token:           会话令牌（必填）
        login_date_time: 登录时刻（必填，取自 UserLogin 的 loginDateTime）
        logout_type:     登出类型（可选，默认 4=TestIn，与真机一致）
        access_code:     访问码（可选）
        region_id:       区域 ID（可选）
        place_id:        店铺 ID（可选）
        client_id:       机台短值（可选）
        delay_log:       会话统计（可选；仅 logout_type=1 时随报文发出）
        timeout_ms:      超时毫秒（可选）
        client:          可复用的 MaimaiNetClient（可选）

    返回：
        UserLogoutResponseVO

    异常：
        RuntimeError: returnCode != 1
    """
    log_info(
        "用户登出：user_id=" + str(user_id) + " logout_type=" + str(logout_type)
        + " loginDateTime=" + str(login_date_time)
    )

    if logout_type == LogoutType.Logout:
        body: Any = UserLogoutRequest2VO(
            userId=user_id, accessCode=access_code,
            regionId=region_id, placeId=place_id, clientId=client_id,
            loginDateTime=login_date_time, type=logout_type,
            delayLog=delay_log if delay_log is not None else create_empty_delay_log(),
        )
        log_debug("使用完整登出报文（含 delayLog）")
    else:
        body = UserLogoutRequestVO(
            userId=user_id, accessCode=access_code,
            regionId=region_id, placeId=place_id, clientId=client_id,
            loginDateTime=login_date_time, type=logout_type,
        )
        log_debug("使用简单登出报文（不含 delayLog）")

    raw = request_dict(
        "UserLogoutApi", body,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    resp = UserLogoutResponseVO(returnCode=int(raw.get("returnCode", 0) or 0))
    if resp.returnCode != 1:
        msg = "登出失败：returnCode=" + str(resp.returnCode)
        log_error(msg)
        raise RuntimeError(msg)

    log_info("用户登出成功：returnCode=" + str(resp.returnCode))
    return resp


if __name__ == "__main__":
    import sys

    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("userlogout_test")
        try:
            if len(sys.argv) < 4:
                print("用法: python -m api.userlogout <user_id> <token> <loginDateTime> "
                      "[logout_type] [region_id] [place_id]")
                return 1
            lt = int(sys.argv[4]) if len(sys.argv) > 4 else LogoutType.TestIn
            rid = int(sys.argv[5]) if len(sys.argv) > 5 else REGION_ID
            pid = int(sys.argv[6]) if len(sys.argv) > 6 else PLACE_ID
            resp = UserLogout(int(sys.argv[1]), sys.argv[2], int(sys.argv[3]),
                              logout_type=lt, region_id=rid, place_id=pid)
            print("")
            print("returnCode =", resp.returnCode)
            return 0
        except Exception as exc:
            log_error("用户登出失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
