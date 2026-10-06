# -*- coding: utf-8 -*-
"""
user_rating.py —— 取用户 Rating 明细（GetUserRatingApi）
================================================================================

取玩家的 Rating 构成（旧谱 / 新谱 / 下一档候选 + 段位）。

对应接口：GetUserRatingApi
请求体  ：UserIdRequestVO
响应    ：{userId, userRating:{rating, ratingList, newRatingList, nextRatingList,
                              nextNewRatingList, udemae}}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserRatingRequestVO.cs

★ 回传 Upsert 时是**单元素数组** userRatingList:[{...}]，不是对象。

调用示例：
    from api import UserRating
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def UserRating(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户 Rating 明细（对应 GetUserRatingApi）。

    返回：
        原始响应 dict，含 userRating 子对象
    """
    log_info("取用户 Rating 明细：user_id=" + str(user_id))
    return _get("GetUserRatingApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
