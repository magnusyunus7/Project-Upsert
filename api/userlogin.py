# -*- coding: utf-8 -*-
"""
userlogin.py —— 用户正式登录（UserLoginApi）
================================================================================

功能：创建登录会话，返回 loginId / loginDateTime / 登录天数统计。
      loginId 与 loginDateTime 是后续结算上报与登出的**必需输入**。

对应接口：UserLoginApi
请求体  ：10 个字段，见 source/Assembly-CSharp/Net.VO.Mai2/UserLoginRequestVO.cs
          source/Assembly-CSharp/Net.Packet.Mai2/PacketUserLogin.cs:21-31
响应    ：UserLoginResponseVO（returnCode=1 表示成功）

--------------------------------------------------------------------------------
★ 关于 loginDateTime（与后续接口强相关，务必理解）
--------------------------------------------------------------------------------
    真机取的是「本地墙上时间被当作 UTC 时刻」的秒数，即

        loginDateTime = 标准 Unix 时间戳 + 本地时区偏移

    东八区即 now + 28800。

    成因：MAI2.DateTime.cs 里 DateTime.UtcNow + LocalOffset 得到 Kind=Unspecified
          的值，PacketUserLogin.cs:29 再用 new DateTimeOffset(该值) 又加一次本地偏移。

    影响：PacketUserLogin.cs:43 会把请求值回填响应；
          PacketUpsertUserAll.cs:31 / PacketUserLogout.cs:29 都复用该值，
          与登录时不一致会被服务端拒绝。

    本模块默认按真机算法生成；需要手动指定时传 login_date_time。

★ 关于 dateTime 与 loginDateTime 的区别
    dateTime     = ALL.Net 认证时刻（Auth.AuthTime，标准 Unix 秒）
    loginDateTime= 本次登录时刻（上面的特殊算法）
    两者都出现在 UserLoginRequestVO 里，但只有 loginDateTime 会被后续接口复用。

调用示例：
    from api import UserLogin
    login = UserLogin(12345678, "TESTTOKEN0000000000", region_id=1, place_id=1000)
    print(login.loginId, login.loginDateTime)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from config import CLIENT_ID, PLACE_ID, REGION_ID, TIMEOUT_LONG_MS

from .log_setup import log_debug, log_error, log_info
from .maimai_net import (
    MaimaiNetClient,
    local_utc_offset_seconds,
    login_date_time_now,
    request_dict,
)


@dataclass
class UserLoginRequestVO:
    """请求 VO（对应 UserLoginRequestVO，字段顺序照 C# 声明）。"""
    userId: int
    accessCode: str = ""
    regionId: int = 0
    placeId: int = 0
    clientId: str = ""
    dateTime: int = 0
    loginDateTime: int = 0
    isContinue: bool = False
    genericFlag: int = 0
    token: str = ""


@dataclass
class UserLoginResponseVO:
    """
    响应 VO（对应 UserLoginResponseVO）。

    ★ 后两个字段是**客户端回填**的，服务端不返回：
        loginDateTime —— PacketUserLogin.cs:43 用请求值回填，
                         UpsertUserAll / UserLogout 都复用它
        dateTime      —— 本次请求发出的 ALL.Net 认证时刻，
                         UpsertUserAll 的 userData.dateTime 要用它
                         （真机 source/2026-10-05.log:123 两处都是 1791134329）
    """
    returnCode: int = 0
    lastLoginDate: str = ""
    loginCount: int = 0
    consecutiveLoginCount: int = 0
    loginId: int = 0
    loginDateTime: int = 0
    token: str = ""
    dateTime: int = 0


def UserLogin(
    user_id: int,
    token: str,
    *,
    access_code: str = "",
    region_id: int = REGION_ID,
    place_id: int = PLACE_ID,
    client_id: str = CLIENT_ID,
    is_continue: bool = False,
    generic_flag: int = 0,
    date_time: Optional[int] = None,
    login_date_time: Optional[int] = None,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> UserLoginResponseVO:
    """
    用户正式登录（创建登录会话）。

    参数：
        user_id:         用户 ID（必填）
        token:           会话令牌（必填，来自 ParseQRCode）
        access_code:     访问码（可选，通常为空）
        region_id:       区域 ID（可选，默认 config.REGION_ID）
        place_id:        店铺 ID（可选，默认 config.PLACE_ID）
        client_id:       机台短值（可选）
        is_continue:     是否续玩（可选）
        generic_flag:    通用标志位（可选）
        date_time:       ALL.Net 认证时刻（可选，默认当前 Unix 秒）
        login_date_time: 本次登录时刻（可选，默认按真机算法生成）
        timeout_ms:      超时毫秒（可选，默认 60 秒）
        client:          可复用的 MaimaiNetClient（可选）

    返回：
        UserLoginResponseVO（loginDateTime 已按真机行为回填）

    异常：
        RuntimeError: returnCode != 1
    """
    log_info(
        "用户正式登录：user_id=" + str(user_id)
        + " region_id=" + str(region_id) + " place_id=" + str(place_id)
    )

    now = int(time.time())
    if date_time is None:
        date_time = now
    if login_date_time is None:
        login_date_time = login_date_time_now()

    log_debug(
        "时间戳：dateTime=" + str(date_time) + " loginDateTime=" + str(login_date_time)
        + "（本地时区偏移 " + str(local_utc_offset_seconds()) + " 秒）"
    )

    raw = request_dict(
        "UserLoginApi",
        UserLoginRequestVO(
            userId=user_id,
            accessCode=access_code,
            regionId=region_id,
            placeId=place_id,
            clientId=client_id,
            dateTime=date_time,
            loginDateTime=login_date_time,
            isContinue=is_continue,
            genericFlag=generic_flag,
            token=token,
        ),
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_LONG_MS, client=client,
    )

    known = {f for f in UserLoginResponseVO.__dataclass_fields__}
    resp = UserLoginResponseVO(**{k: v for k, v in raw.items() if k in known})

    if resp.returnCode != 1:
        msg = "登录失败：returnCode=" + str(resp.returnCode)
        log_error(msg)
        raise RuntimeError(msg)

    # ★ 回填 loginDateTime（对应 PacketUserLogin.cs:43）
    #   服务端不返回该字段，客户端用请求值回填；后续 UpsertUserAll / UserLogout 复用。
    if not resp.loginDateTime:
        resp.loginDateTime = login_date_time
        log_debug("服务端未返回 loginDateTime，按真机行为回填为 " + str(login_date_time))

    # ★ 回填 dateTime：本次请求实际发出的 ALL.Net 认证时刻。
    #   UpsertUserAll 的 userData.dateTime 要用它（真机两处一致）。
    resp.dateTime = date_time

    log_info(
        "用户登录成功：loginId=" + str(resp.loginId)
        + " loginDateTime=" + str(resp.loginDateTime)
        + " dateTime=" + str(resp.dateTime)
        + " lastLoginDate=" + resp.lastLoginDate
        + " loginCount=" + str(resp.loginCount)
        + " consecutiveLoginCount=" + str(resp.consecutiveLoginCount)
    )
    return resp


if __name__ == "__main__":
    import sys

    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("userlogin_test")
        try:
            if len(sys.argv) < 3:
                print("用法: python -m api.userlogin <user_id> <token> [region_id] [place_id]")
                return 1
            rid = int(sys.argv[3]) if len(sys.argv) > 3 else REGION_ID
            pid = int(sys.argv[4]) if len(sys.argv) > 4 else PLACE_ID
            lg = UserLogin(int(sys.argv[1]), sys.argv[2], region_id=rid, place_id=pid)
            print("")
            for name in UserLoginResponseVO.__dataclass_fields__:
                print("   " + name.ljust(24) + "= " + str(getattr(lg, name)))
            return 0
        except Exception as exc:
            log_error("用户登录失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
