# -*- coding: utf-8 -*-
"""
get_user_friend_bonus.py —— Fetching user friend miles（GetUserFriendBonusApi）
================================================================================

Collect friend miles that players can claim this time（getMiles）。

Corresponding interface：GetUserFriendBonusApi
request body  ：UserIdRequestVO
Response    ：{returnCode, userId, getMiles}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserFriendBonusRequestVO.cs
          source/2026-10-05.log:111  real machineResponse {"returnCode":1,"userId":..,"getMiles":90}

call exampleExample：
    from api import GetUserFriendBonus, extract_gift_points
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserFriendBonus(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetching user friend miles（Corresponding GetUserFriendBonusApi）。

    returntimes：
        Raw Response dict：{"returnCode":1, "userId":.., "getMiles":..}
    """
    log_info("Fetching user friend miles：user_id=" + str(user_id))
    resp = _get("GetUserFriendBonusApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)

    if int(resp.get("returnCode", 0) or 0) != 1:
        log_warning("Friend Mileage Interface Return returnCode=" + str(resp.get("returnCode")))
    return resp


def extract_gift_points(friend_bonus: Dict[str, Any]) -> int:
    """
    Pull from friend mileage response getMiles（textTakeofintextnumber）。

    Parameter：
        friend_bonus: GetUserFriendBonus ofreturntimesValue

    returntimes：
        getMiles textnumber（If you can't get it, it's 0）
    """
    try:
        return int((friend_bonus or {}).get("getMiles", 0) or 0)
    except Exception:
        return 0
