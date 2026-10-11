# -*- coding: utf-8 -*-
"""
userlogout. py — user logout (UserLogoutApi)
================================================================================

Features: login Session, Optionally escalate network statistics for this session (delayLog).

Corresponding interface: UserLogoutApi
request body: Two Forms, source/Assembly-CSharp/Net. Packet. Mai2/PacketUserLogout. cs:22-63
      type == 1 (Logout) -> UserLogoutRequest2VO(Contains delayLog)
      Other type     -> UserLogoutRequestVO (Excluding delayLog)

--------------------------------------------------------------------------------
logout(source/Assembly-CSharp/Net. VO. Mai2/LogoutType. cs)
--------------------------------------------------------------------------------
  None  = 0
  Logout = 1  current logout (Belt delayLog system count)
  Cancel = 2  Cancel / Force Logout of Assigned Agents (NetPacketUtil. cs:47)
  Error = 3  error Force Logout (GameMain. cs:91)
  TestIn = 4  /(GameMain. cs:104)
  Quit  = 5  out time Force Logout, Releasable Residual Sessions (GameMainObject. cs:200)

- real machine Session time use of is type=4 (TestIn), source/2026-10-05. log:125.

- delayLog(source/Assembly-CSharp/Net. VO. Mai2/DelayLog. cs)
  request is long 26 of number group (DelayLog. cs:17 new RequestAPI[26]),
  eachPieceElement {count, size, msec, retry}.

Example:
  from api import UserLogout, LogoutType
  UserLogout(12345678, token, login. loginDateTime,
        logout_type=LogoutType. TestIn, region_id=1, place_id=1000)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLACE_ID, REGION_ID, TIMEOUT_MS

from .log_setup import log_debug, log_error, log_info
from .maimai_net import MaimaiNetClient, request_dict

#: DelayLog. request oflong(DelayLog. cs:17)
DELAY_LOG_SLOTS = 26


class LogoutType:
    """logout (Corresponding Net. VO. Mai2. LogoutType)."""
    None_ = 0
    Logout = 1      # currentlogout(Belt delayLog)
    Cancel = 2      # Cancel / Force Logout
    Error = 3       # errorForce Logout
    TestIn = 4      # /(real machineSessionusethisPiece)
    Quit = 5        # outForce Logout


@dataclass
class RequestAPI:
    """Statistics for a single interface (Corresponding Net. VO. Mai2/RequestAPI. cs)."""
    count: int = 0
    size: int = 0
    msec: int = 0
    retry: int = 0


@dataclass
class DelayLog:
    """Session Network Statistics (Corresponding Net. VO. Mai2/DelayLog. cs)."""
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
    """logout request VO (Corresponding UserLogoutRequestVO)."""
    userId: int
    accessCode: str = ""
    regionId: int = 0
    placeId: int = 0
    clientId: str = ""
    loginDateTime: int = 0
    type: int = 0


@dataclass
class UserLogoutRequest2VO:
    """Full Logout Request VO (Corresponding UserLogoutRequest2VO, Contains delayLog)."""
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
    """Response VO (Corresponding UserLogoutResponseVO)."""
    returnCode: int = 0


def create_empty_delay_log() -> DelayLog:
    """Create an all-zero DelayLog (26 slots)."""
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
  use system count data construct DelayLog.

  Parameter:
    requests_stats: each Piece interface of system count List, Elements are shaped like
            {"count":1,"size":2090,"msec":73,"retry":0}
            press DelayLog. request ofBitorderFill(Max. 26 Piece)
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
  userlogout.

  Parameter:
    user_id:     user ID(Required)
    token:      Session Token(Required)
    login_date_time: login time (Required, Retrieved from UserLogin of loginDateTime)
    logout_type:   logout(Optional, default 4=TestIn, Consistent with the real machine)
    access_code:  (Optional)
    region_id:    Area ID(Optional)
    place_id:    Store ID(Optional)
    client_id:    machine state short Value (Optional)
    delay_log:    Session Stats(Optional; Only logout_type=1 timepackethairout)
    timeout_ms:   timeout milliseconds(Optional)
    client:     Reusable MaimaiNetClient(Optional)

  Returns:
    UserLogoutResponseVO

  Exceptions:
    RuntimeError: returnCode!= 1
  """
    log_info(
        "user logout: user_id=" + str(user_id) + " logout_type=" + str(logout_type)
        + " loginDateTime=" + str(login_date_time)
    )

    if logout_type == LogoutType.Logout:
        body: Any = UserLogoutRequest2VO(
            userId=user_id, accessCode=access_code,
            regionId=region_id, placeId=place_id, clientId=client_id,
            loginDateTime=login_date_time, type=logout_type,
            delayLog=delay_log if delay_log is not None else create_empty_delay_log(),
        )
        log_debug("Use full logout message (Contains delayLog)")
    else:
        body = UserLogoutRequestVO(
            userId=user_id, accessCode=access_code,
            regionId=region_id, placeId=place_id, clientId=client_id,
            loginDateTime=login_date_time, type=logout_type,
        )
        log_debug("Use Simple Logout Packet (Excluding delayLog)")

    raw = request_dict(
        "UserLogoutApi", body,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    resp = UserLogoutResponseVO(returnCode=int(raw.get("returnCode", 0) or 0))
    if resp.returnCode != 1:
        msg = "logout Failed: returnCode=" + str(resp.returnCode)
        log_error(msg)
        raise RuntimeError(msg)

    log_info("user logout Success: returnCode=" + str(resp.returnCode))
    return resp


if __name__ == "__main__":
    import sys

    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("userlogout_test")
        try:
            if len(sys.argv) < 4:
                print("usage: python -m api. userlogout <user_id> <token> <loginDateTime> "
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
            log_error("user logout Failed: " + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
