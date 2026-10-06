# -*- coding: utf-8 -*-
"""
get_game_weekly_data.py —— 取游戏周常配置（GetGameWeeklyDataApi）
================================================================================

取服务器下发的周常周期信息。

对应接口：GetGameWeeklyDataApi
请求体  ：{}（GameWeeklyRequestVO 是空类）
响应    ：{gameWeeklyData:{missionCategory, updateDate, beforeDate}}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameWeeklyRequestVO.cs（空类）
          source/2026-10-05.log:13

调用示例：
    from api import GetGameWeeklyData
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


def GetGameWeeklyData(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取游戏周常配置（对应 GetGameWeeklyDataApi）。

    返回：
        原始响应 dict，含 gameWeeklyData
    """
    log_info("取游戏周常配置")
    return request_dict(
        "GetGameWeeklyDataApi", {},
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
