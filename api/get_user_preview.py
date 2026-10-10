# -*- coding: utf-8 -*-
"""
get_user_preview. py — user(GetUserPreviewApi)
================================================================================

Features: Data of the welcome screen after swiping the card(, Rating, isNoAlreadylogin, Ghosting Status…).

Corresponding interface: GetUserPreviewApi
request body:{"userId":.., "segaIdAuthKey":"", "token":"..", "clientId":".."}
     source/Assembly-CSharp/Net. VO. Mai2/UserPreviewRequestVO. cs
     source/Assembly-CSharp/Net. Packet. Mai2/PacketGetUserPreview. cs:20-25
Response: UserPreviewResponseVO(23 Field, Contains errorId)

- real machinecallusetimemachine: to userId/token After, UserLoginApi Before
  (source/2026-10-05. log:23).
- Client Behavior: isLogin=True timecontinuelogin, text
  (source/Assembly-CSharp/Process. Entry. State/ConfirmPlay. cs:151).

Example:
  from api import GetUserPreview
  pv = GetUserPreview(12345678, "TESTTOKEN0000000000")
  print(pv. userName, pv. playerRating)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class UserPreviewRequestVO:
    """request VO(Corresponding UserPreviewRequestVO)."""
    userId: int
    segaIdAuthKey: str = ""
    token: str = ""
    clientId: str = ""


@dataclass
class UserPreviewResponseVO:
    """
  Response VO(Corresponding UserPreviewResponseVO + real machineResponse Fields).

  - Field order by source/Assembly-CSharp/Net. VO. Mai2/UserPreviewResponseVO. cs
   And source/2026-10-05. log:24 ofreal machineResponseMerge.
  """
    userId: int = 0
    userName: str = ""
    isLogin: bool = False
    lastGameId: Optional[str] = None
    lastRomVersion: str = ""
    lastDataVersion: str = ""
    lastLoginDate: str = ""
    lastPlayDate: str = ""
    playerRating: int = 0
    nameplateId: int = 0
    iconId: int = 0
    trophyId: int = 0
    partnerId: int = 0
    frameId: int = 0
    dispRate: int = 0
    totalAwake: int = 0
    isNetMember: int = 0
    dailyBonusDate: str = ""
    headPhoneVolume: Optional[int] = None
    isInherit: bool = False
    banState: int = 0
    errorId: int = 0


def GetUserPreview(
    user_id: int,
    token: str,
    *,
    client_id: str = CLIENT_ID,
    sega_id_auth_key: str = "",
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> UserPreviewResponseVO:
    """
  getFetch Users

  Parameter:
    user_id:     user ID(Required)
    token:      Session Token(Required, ParseQRCode)
    client_id:    machine stateshortValue(Optional)
    sega_id_auth_key: SEGA ID key(Optional, Is Empty)
    timeout_ms:    timeout milliseconds(Optional)
    client:      Reusable MaimaiNetClient(Optional)

  Returns:
    UserPreviewResponseVO
  """
    log_info("getFetch Usersuser_id=" + str(user_id) + " client_id=" + client_id)

    raw = request_dict(
        "GetUserPreviewApi",
        UserPreviewRequestVO(
            userId=user_id,
            segaIdAuthKey=sega_id_auth_key,
            token=token,
            clientId=client_id,
        ),
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    known = {f for f in UserPreviewResponseVO.__dataclass_fields__}
    resp = UserPreviewResponseVO(**{k: v for k, v in raw.items() if k in known})

    if resp.errorId != 0:
        log_warning("serverreturns errorId=" + str(resp.errorId))
    if resp.banState != 0:
        log_warning("canbanState=" + str(resp.banState))
    if resp.isLogin:
        log_warning("placeinAlreadylogin(isLogin=True), continueloginMeetings")

    log_info(
        "userfetch complete: userName=" + resp.userName
        + " playerRating=" + str(resp.playerRating)
        + " isLogin=" + str(resp.isLogin)
        + " isNetMember=" + str(resp.isNetMember)
    )
    return resp


if __name__ == "__main__":
    import sys

    from .log_setup import log_error, setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("userpreview_test")
        try:
            if len(sys.argv) < 3:
                print("usage: python -m api. get_user_preview <user_id> <token> [client_id]")
                return 1
            cid = sys.argv[3] if len(sys.argv) > 3 else CLIENT_ID
            pv = GetUserPreview(int(sys.argv[1]), sys.argv[2], client_id=cid)
            print("")
            for name in UserPreviewResponseVO.__dataclass_fields__:
                print("  " + name.ljust(18) + "= " + str(getattr(pv, name)))
            return 0
        except Exception as exc:
            log_error("getFetch UsersFailed:" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
