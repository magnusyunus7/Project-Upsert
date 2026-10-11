# -*- coding: utf-8 -*-
"""
userlogin. py — user current login (UserLoginApi)
================================================================================

Features: Create Login Session, returns loginId / loginDateTime / login days number system count.
   loginId And loginDateTime is Follow-up settlement Escalations And logout of **Required**.

Corresponding interface: UserLoginApi
request body:10 fields, source/Assembly-CSharp/Net. VO. Mai2/UserLoginRequestVO. cs
     source/Assembly-CSharp/Net. Packet. Mai2/PacketUserLogin. cs:21-31
Response: UserLoginResponseVO(returnCode=1 Success)

--------------------------------------------------------------------------------
- About loginDateTime(Strong correlation with subsequent interfaces, It's important to understand)
--------------------------------------------------------------------------------
  real machine Take is "Wall Time When UTC time" of seconds number, i. e.

    loginDateTime = standard Unix time + timeOffset

  Eastern Eight Wards now + 28800.

  Causes: MAI2. DateTime. cs in DateTime. UtcNow + LocalOffset Get Kind=Unspecified
     value of, PacketUserLogin. cs:29 Reuse new DateTimeOffset(theValue) Add another local offset.

  Impact: PacketUserLogin. cs:43 will backfill the response with the requested value;
     PacketUpsertUserAll. cs:31 / PacketUserLogout. cs:29 allMultiplexingtheValue,
     Inconsistent with login will be rejected by the server.

  default press real machine calculate; need specified time Passing on login_date_time.

- About dateTime And loginDateTime of
  dateTime   = ALL. Net time (Auth. AuthTime, standard Unix seconds)
  loginDateTime = login time (Special algorithm above)
  Both appear in the UserLoginRequestVO in, But only loginDateTime Will be multiplexed by subsequent interfaces.

Example:
  from api import UserLogin
  login = UserLogin(12345678, "TESTTOKEN0000000000", region_id=1, place_id=1000)
  print(login. loginId, login. loginDateTime)
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
    """request VO (Corresponding UserLoginRequestVO, Field order photo C# Declaration)."""
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
  Response VO (Corresponding UserLoginResponseVO).

  - The last two fields are **Client Backfill** of, server No Returns:
    loginDateTime — PacketUserLogin. cs:43 userequestValueBackfill,
             UpsertUserAll / UserLogout allMultiplexing
    dateTime   — requesthairoutof ALL. Net time,
             UpsertUserAll of userData. dateTime mustuse
             (real machine source/2026-10-05. log:123 Both 1791134329)
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
  user current login (Create Login Session).

  Parameter:
    user_id:     user ID(Required)
    token:      Session Token(Required, ParseQRCode)
    access_code:  (Optional, Is Empty)
    region_id:    Area ID(Optional, default config. REGION_ID)
    place_id:    Store ID(Optional, default config. PLACE_ID)
    client_id:    machine state short Value (Optional)
    is_continue:   is No continue (Optional)
    generic_flag:  useBit(Optional)
    date_time:    ALL. Net time (Optional, default Current Unix seconds)
    login_date_time: login time (Optional, default press real machine calculate)
    timeout_ms:   timeout milliseconds(Optional, default 60 seconds)
    client:     Reusable MaimaiNetClient(Optional)

  Returns:
    UserLoginResponseVO(loginDateTime Backfilled according to real machine behavior)

  Exceptions:
    RuntimeError: returnCode!= 1
  """
    log_info(
        "user current login: user_id=" + str(user_id)
        + " region_id=" + str(region_id) + " place_id=" + str(place_id)
    )

    now = int(time.time())
    if date_time is None:
        date_time = now
    if login_date_time is None:
        login_date_time = login_date_time_now()

    log_debug(
        "time dateTime=" + str(date_time) + " loginDateTime=" + str(login_date_time)
        + " (time Offset " + str(local_utc_offset_seconds()) + " seconds)"
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
        msg = "login Failed: returnCode=" + str(resp.returnCode)
        log_error(msg)
        raise RuntimeError(msg)

    # - Backfill loginDateTime(Corresponding PacketUserLogin. cs:43)
    #  serverNoreturnstheField, Client backfill with request value; Follow-up UpsertUserAll / UserLogout Multiplexing.
    if not resp.loginDateTime:
        resp.loginDateTime = login_date_time
        log_debug("server not returns loginDateTime, press real machine for Backfill for " + str(login_date_time))

    # - Backfill dateTime: requestactualhairoutof ALL. Net time.
    #  UpsertUserAll of userData. dateTime mustuse(real machineplaceMatch).
    resp.dateTime = date_time

    log_info(
        "user login Success: loginId=" + str(resp.loginId)
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
                print("usage: python -m api. userlogin <user_id> <token> [region_id] [place_id]")
                return 1
            rid = int(sys.argv[3]) if len(sys.argv) > 3 else REGION_ID
            pid = int(sys.argv[4]) if len(sys.argv) > 4 else PLACE_ID
            lg = UserLogin(int(sys.argv[1]), sys.argv[2], region_id=rid, place_id=pid)
            print("")
            for name in UserLoginResponseVO.__dataclass_fields__:
                print("  " + name.ljust(24) + "= " + str(getattr(lg, name)))
            return 0
        except Exception as exc:
            log_error("user login Failed: " + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
