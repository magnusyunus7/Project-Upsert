# -*- coding: utf-8 -*-
"""
get_user_mission.py —— Fetching user tasks and weekly data(GetUserMissionDataApi)
================================================================================

Take the player's quest progress and weekly data(real machine 6 itemTask).

Corresponding interface:GetUserMissionDataApi
request body  :UserIdRequestVO
Response:{userId, userWeeklyData:{...}, userMissionDataList:[...]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserMissionRequestVO.cs

★ One interface sends two at the same time Upsert nodes:
    userMissionDataList  Task List
    userWeeklyData       Weekly data(★ is**Object**Not an array)
★ Both backhaul Upsert timeallmustDiscardEachof userId Field.

Example:
    from api import GetUserMissionData
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserMissionData(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetching user tasks and weekly data(Corresponding GetUserMissionDataApi).

    Returns:
        Raw Response dict:{"userId":.., "userWeeklyData":{..}, "userMissionDataList":[..]}
    """
    log_info("Fetching user tasks and weekly data:user_id=" + str(user_id))
    return _get("GetUserMissionDataApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
