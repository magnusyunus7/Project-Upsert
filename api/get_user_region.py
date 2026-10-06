# -*- coding: utf-8 -*-
"""
get_user_region.py —— 取用户地区游玩统计（GetUserRegionApi）
================================================================================

取玩家在各地区的游玩次数。

对应接口：GetUserRegionApi
请求体  ：UserIdRequestVO
响应    ：{userId, length, userRegionList:[{regionId,playCount,created}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserRegionRequestVO.cs
          source/2026-10-05.log:77

调用示例：
    from api import GetUserRegion
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserRegion(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户地区游玩统计（对应 GetUserRegionApi）。

    返回：
        原始响应 dict，含 userRegionList
    """
    log_info("取用户地区统计：user_id=" + str(user_id))
    return _get("GetUserRegionApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
