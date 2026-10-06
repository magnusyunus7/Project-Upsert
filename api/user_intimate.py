# -*- coding: utf-8 -*-
"""
user_intimate.py —— 取用户搭档亲密度（GetUserIntimateApi）
================================================================================

取玩家与各搭档的亲密度（真机 2 条）。

对应接口：GetUserIntimateApi
请求体  ：UserIdRequestVO
响应    ：{userId, length, userIntimateList:[{partnerId,intimateLevel,intimateCountRewarded}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserIntimateRequestVO.cs

调用示例：
    from api import UserIntimate
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def UserIntimate(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户搭档亲密度（对应 GetUserIntimateApi）。

    返回：
        原始响应 dict，含 userIntimateList
    """
    log_info("取用户搭档亲密度：user_id=" + str(user_id))
    return _get("GetUserIntimateApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
