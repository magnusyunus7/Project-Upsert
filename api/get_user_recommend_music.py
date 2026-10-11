# -*- coding: utf-8 -*-
"""
get_user_recommend_music. py — Get recommended tracks (GetUserRecommendRateMusicApi / GetUserRecommendSelectMusicApi)
================================================================================

Corresponding interface:
  GetUserRecommendRateMusicApi  request body UserIdRequestVO
                  Response {userId, userRecommendRateMusicIdList:[...]}
  GetUserRecommendSelectMusicApi request body UserIdRequestVO
                  Response {userId, userRecommendSelectionMusicIdList:[...]}
Basis:
  source/Assembly-CSharp/Net. VO. Mai2/UserRecommendRateMusicRequestVO. cs
  source/Assembly-CSharp/Net. VO. Mai2/UserRecommendSelectionMusicRequestVO. cs
  source/2026-10-05. log:79,81

Example:
  from api import GetUserRecommendRateMusic, GetUserRecommendSelectMusic
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserRecommendRateMusic(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take recommended last track (Corresponding GetUserRecommendRateMusicApi).

  Returns:
    Raw Response dict, Contains userRecommendRateMusicIdList.
  """
    log_info("Take recommended last track: user_id=" + str(user_id))
    return _get("GetUserRecommendRateMusicApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)


def GetUserRecommendSelectMusic(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take recommended songs (Corresponding GetUserRecommendSelectMusicApi).

  Returns:
    Raw Response dict, Contains userRecommendSelectionMusicIdList.
  """
    log_info("Take recommended songs: user_id=" + str(user_id))
    return _get("GetUserRecommendSelectMusicApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
