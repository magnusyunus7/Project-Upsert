# -*- coding: utf-8 -*-
"""
get_game_ranking.py —— 取游戏排行（GetGameRankingApi）
================================================================================

取服务器下发的排行榜数据。

对应接口：GetGameRankingApi
请求体  ：{"type": <排行类型>}（GameRankingRequestVO.type 是 long）
响应    ：{type, gameRankingList:[{id,point,userName}], gameRankingInstantList}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameRankingRequestVO.cs
          source/2026-10-05.log:3  真机请求 {"type":1}

调用示例：
    from api import GetGameRanking
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class GameRankingRequestVO:
    """请求 VO（对应 GameRankingRequestVO）。"""
    type: int = 1


def GetGameRanking(
    ranking_type: int = 1,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取游戏排行（对应 GetGameRankingApi）。

    参数：
        ranking_type: 排行类型（真机用 1）

    返回：
        原始响应 dict，含 gameRankingList
    """
    log_info("取游戏排行：type=" + str(ranking_type))
    return request_dict(
        "GetGameRankingApi", GameRankingRequestVO(type=ranking_type),
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
