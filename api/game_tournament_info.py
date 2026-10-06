# -*- coding: utf-8 -*-
"""
game_tournament_info.py —— 取大会信息（GetGameTournamentInfoApi）
================================================================================

取服务器下发的大会/赛事信息。

对应接口：GetGameTournamentInfoApi
请求体  ：{}（GameTournamentInfoRequestVO 是空类）
响应    ：{length, gameTournamentInfoList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameTournamentInfoRequestVO.cs（空类）
          source/2026-10-05.log:7

调用示例：
    from api import GetGameTournamentInfo
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


def GetGameTournamentInfo(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取大会信息（对应 GetGameTournamentInfoApi）。

    返回：
        原始响应 dict，含 gameTournamentInfoList
    """
    log_info("取大会信息")
    return request_dict(
        "GetGameTournamentInfoApi", {},
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
