# -*- coding: utf-8 -*-
"""
get_game_event.py —— 取游戏活动（GetGameEventApi）
================================================================================

取服务器下发的活动列表。

对应接口：GetGameEventApi
请求体  ：{"type":1, "isAllEvent":true}（GameEventRequestVO）
响应    ：{type, length, gameEventList:[{type,id,startDate,endDate}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameEventRequestVO.cs
          source/2026-10-05.log:5  真机请求 {"type":1,"isAllEvent":true}

调用示例：
    from api import GetGameEvent
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class GameEventRequestVO:
    """请求 VO（对应 GameEventRequestVO）。"""
    type: int = 1
    isAllEvent: bool = True


def GetGameEvent(
    event_type: int = 1,
    *,
    is_all_event: bool = True,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取游戏活动列表（对应 GetGameEventApi）。

    参数：
        event_type:   活动类型（真机用 1）
        is_all_event: 是否取全部活动（真机 True）

    返回：
        原始响应 dict，含 gameEventList
    """
    log_info("取游戏活动：type=" + str(event_type) + " isAllEvent=" + str(is_all_event))
    return request_dict(
        "GetGameEventApi",
        GameEventRequestVO(type=event_type, isAllEvent=is_all_event),
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
