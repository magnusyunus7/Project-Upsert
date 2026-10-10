# -*- coding: utf-8 -*-
"""
get_user_activity.py —— Pick up user activity records(GetUserActivityApi)
================================================================================

Pick a player's activity/Achievement Record(playList And musicList Two Lists).

Corresponding interface:GetUserActivityApi
request body  :UserIdRequestVO
Response:{userActivity:{playList:[...], musicList:[...]}}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserActivityRequestVO.cs

★ Shape Exceptions(36 Piece Upsert nodesinUniqueOne Get And Upsert different shapes):
    Get Side  :Single Object userActivity = {playList, musicList}
    Upsert Side:**Array of elements** userActivityList = [ {playList, musicList} ]
    Instead of spreading the two arrays end to end,.

Example:
    from api import GetUserActivity
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserActivity(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Pick up user activity records(Corresponding GetUserActivityApi).

    Returns:
        Raw Response dict,Contains userActivity Child Objects
    """
    log_info("Pick up user activity records:user_id=" + str(user_id))
    return _get("GetUserActivityApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
