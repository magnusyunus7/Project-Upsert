# -*- coding: utf-8 -*-
"""
get_user_rating.py —— Fetch Users Rating details（GetUserRatingApi）
================================================================================

Take Player Rating text（text / text / Next Tier Candidate + textBit）。

Corresponding interface：GetUserRatingApi
request body  ：UserIdRequestVO
Response    ：{userId, userRating:{rating, ratingList, newRatingList, nextRatingList,
                              nextNewRatingList, udemae}}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserRatingRequestVO.cs

★ Callback Upsert timeis**Array of elements** userRatingList:[{...}]，Not an object。

call exampleExample：
    from api import GetUserRating
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserRating(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetch Users Rating details（Corresponding GetUserRatingApi）。

    returntimes：
        Raw Response dict，Contains userRating Child Objects
    """
    log_info("Fetch Users Rating details：user_id=" + str(user_id))
    return _get("GetUserRatingApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
