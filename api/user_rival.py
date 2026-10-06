# -*- coding: utf-8 -*-
"""
user_rival.py —— 取用户对手数据（GetUserRivalDataApi / GetUserRivalMusicApi）
================================================================================

取玩家的对手名单及其曲目成绩。

对应接口：
    GetUserRivalDataApi   请求体 UserRivalRequestVO（userId + rivalId）
                          响应   {userId, userRivalData:{rivalId, rivalName}}
    GetUserRivalMusicApi  请求体 UserRivalMusicRequestVO（userId + rivalId + nextIndex
                                                       + userRivalMusicLevelList）
                          响应   {userId, rivalId, length, nextIndex, userRivalMusicList}
依据：
    source/Assembly-CSharp/Net.VO.Mai2/UserRivalRequestVO.cs
    source/Assembly-CSharp/Net.VO.Mai2/UserRivalMusicRequestVO.cs
    source/2026-10-05.log:95,101

★ 对手 ID 需要调用方提供（先由 GetUserFavoriteItemApi 的 kind=2 取到）。

调用示例：
    from api import UserRivalData, UserRivalMusic
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import (
    _get,
    UserRivalRequestVO,
    UserRivalMusicRequestVO,
    RIVAL_MUSIC_LEVELS,
    fetch_all_pages,
)


def UserRivalData(
    user_id: int,
    rival_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取对手资料（对应 GetUserRivalDataApi）。

    参数：
        user_id:  用户 ID（必填）
        rival_id: 对手 ID（必填）

    返回：
        原始响应 dict，含 userRivalData
    """
    log_info("取对手资料：user_id=" + str(user_id) + " rival_id=" + str(rival_id))
    return _get(
        "GetUserRivalDataApi",
        UserRivalRequestVO(userId=user_id, rivalId=rival_id),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def UserRivalMusic(
    user_id: int,
    rival_id: int,
    *,
    next_index: int = 0,
    levels: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取对手曲目成绩（单页，对应 GetUserRivalMusicApi）。

    参数：
        user_id:    用户 ID（必填）
        rival_id:   对手 ID（必填）
        next_index: 分页索引（0 = 首页）
        levels:     难度档位列表（可选，默认 0/1/2/3/4/10）

    返回：
        原始响应 dict，含 userRivalMusicList
    """
    lv = list(levels) if levels else list(RIVAL_MUSIC_LEVELS)
    log_info("取对手曲目成绩：user_id=" + str(user_id) + " rival_id=" + str(rival_id)
             + " levels=" + str(lv))
    return _get(
        "GetUserRivalMusicApi",
        UserRivalMusicRequestVO(
            userId=user_id, rivalId=rival_id, nextIndex=next_index,
            userRivalMusicLevelList=[{"level": x} for x in lv],
        ),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def UserRivalMusicAll(
    user_id: int,
    rival_id: int,
    *,
    levels: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取对手曲目成绩（自动翻页取全）。

    返回：
        {"userRivalMusicList": [...]}
    """
    lv = list(levels) if levels else list(RIVAL_MUSIC_LEVELS)
    log_info("取对手曲目成绩（全量）：user_id=" + str(user_id) + " rival_id=" + str(rival_id))
    items = fetch_all_pages(
        "GetUserRivalMusicApi", user_id, "userRivalMusicList",
        body_factory=lambda ni: UserRivalMusicRequestVO(
            userId=user_id, rivalId=rival_id, nextIndex=ni or 0,
            userRivalMusicLevelList=[{"level": x} for x in lv]),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("对手曲目获取完成：" + str(len(items)) + " 条")
    return {"userRivalMusicList": items}
