# -*- coding: utf-8 -*-
"""
user_activity.py —— 取用户活动记录（GetUserActivityApi）
================================================================================

取玩家的活动/成就记录（playList 与 musicList 两个列表）。

对应接口：GetUserActivityApi
请求体  ：UserIdRequestVO
响应    ：{userActivity:{playList:[...], musicList:[...]}}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserActivityRequestVO.cs

★ 形状特例（36 个 Upsert 节点里唯一一个 Get 与 Upsert 形状不同的）：
    Get 侧  ：单个对象 userActivity = {playList, musicList}
    Upsert 侧：**单元素数组** userActivityList = [ {playList, musicList} ]
    不是把两个数组首尾相接摊平。

调用示例：
    from api import UserActivity
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def UserActivity(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户活动记录（对应 GetUserActivityApi）。

    返回：
        原始响应 dict，含 userActivity 子对象
    """
    log_info("取用户活动记录：user_id=" + str(user_id))
    return _get("GetUserActivityApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
