# -*- coding: utf-8 -*-
"""
game_ng_music_id.py —— 取禁用曲目列表（GetGameNgMusicIdApi）
================================================================================

取服务器下发的 NG（不可游玩）曲目 ID 列表。

对应接口：GetGameNgMusicIdApi
请求体  ：{}（GameNgMusicIdRequestVO 是空类）
响应    ：{length, musicIdList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameNgMusicIdRequestVO.cs（空类）
          source/2026-10-05.log:11

调用示例：
    from api import GetGameNgMusicId
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


def GetGameNgMusicId(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取禁用曲目列表（对应 GetGameNgMusicIdApi）。

    返回：
        原始响应 dict，含 musicIdList
    """
    log_info("取禁用曲目列表")
    return request_dict(
        "GetGameNgMusicIdApi", {},
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
