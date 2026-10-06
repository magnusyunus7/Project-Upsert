# -*- coding: utf-8 -*-
"""
get_user_map.py —— 取用户地图进度（GetUserMapApi）
================================================================================

取玩家各地图的推进距离（真机 104 条）。

对应接口：GetUserMapApi
请求体  ：UserMapRequestVO（userId + nextIndex + maxCount=1000）
响应    ：{userId, length, nextIndex, userMapList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserMapRequestVO.cs

    ★ Get 侧下发 100+ 条；Upsert 只回传「本次距离变化」的那 1 条
      （真机：mapId=550003 的 distance 1424000 -> 1435000）。

调用示例：
    from api import GetUserMap / GetUserMapAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdPageRequestVO, get_all_pages


def GetUserMap(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户地图进度（单页，对应 GetUserMapApi）。

    参数：
        next_index: 分页起始索引（0 = 首页）

    返回：
        原始响应 dict，含 userMapList
    """
    log_info("取用户地图进度：user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserMapApi",
        UserIdPageRequestVO(userId=user_id, nextIndex=next_index, maxCount=1000),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserMapAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户地图进度（自动翻页取全）。

    返回：
        {"userMapList": [...]}
    """
    log_info("取用户地图进度（全量）：user_id=" + str(user_id))
    items = get_all_pages(
        "GetUserMapApi", user_id, "userMapList",
        body_factory=lambda ni: UserIdPageRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=1000),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("地图进度获取完成：" + str(len(items)) + " 条")
    return {"userMapList": items}
