# -*- coding: utf-8 -*-
"""
get_user_intimate.py —— Take the intimacy of the user's partner（GetUserIntimateApi）
================================================================================

Take the intimacy of the player with each partner（real machine 2 item）。

Corresponding interface：GetUserIntimateApi
request body  ：UserIdRequestVO
Response    ：{userId, length, userIntimateList:[{partnerId,intimateLevel,intimateCountRewarded}]}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserIntimateRequestVO.cs

call exampleExample：
    from api import GetUserIntimate
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserIntimate(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take the intimacy of the user's partner（Corresponding GetUserIntimateApi）。

    returntimes：
        Raw Response dict，Contains userIntimateList
    """
    log_info("Take the intimacy of the user's partner：user_id=" + str(user_id))
    return _get("GetUserIntimateApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
