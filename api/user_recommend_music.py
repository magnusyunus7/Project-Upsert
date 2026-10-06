# -*- coding: utf-8 -*-
"""
user_recommend_music.py —— 取推荐曲目（GetUserRecommendRateMusicApi / GetUserRecommendSelectMusicApi）
================================================================================

对应接口：
    GetUserRecommendRateMusicApi    请求体 UserIdRequestVO
                                    响应 {userId, userRecommendRateMusicIdList:[...]}
    GetUserRecommendSelectMusicApi  请求体 UserIdRequestVO
                                    响应 {userId, userRecommendSelectionMusicIdList:[...]}
依据：
    source/Assembly-CSharp/Net.VO.Mai2/UserRecommendRateMusicRequestVO.cs
    source/Assembly-CSharp/Net.VO.Mai2/UserRecommendSelectionMusicRequestVO.cs
    source/2026-10-05.log:79,81

调用示例：
    from api import UserRecommendRateMusic, UserRecommendSelectMusic
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def UserRecommendRateMusic(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取推荐上分曲目（对应 GetUserRecommendRateMusicApi）。

    返回：
        原始响应 dict，含 userRecommendRateMusicIdList
    """
    log_info("取推荐上分曲目：user_id=" + str(user_id))
    return _get("GetUserRecommendRateMusicApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)


def UserRecommendSelectMusic(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取推荐选曲（对应 GetUserRecommendSelectMusicApi）。

    返回：
        原始响应 dict，含 userRecommendSelectionMusicIdList
    """
    log_info("取推荐选曲：user_id=" + str(user_id))
    return _get("GetUserRecommendSelectMusicApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
