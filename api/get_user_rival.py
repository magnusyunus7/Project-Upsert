# -*- coding: utf-8 -*-
"""
get_user_rival.py —— Fetch User Opponent Data(GetUserRivalDataApi / GetUserRivalMusicApi)
================================================================================

Take a list of players' opponents and their track scores.

Corresponding interface:
    GetUserRivalDataApi   request body UserRivalRequestVO(userId + rivalId)
                          Response   {userId, userRivalData:{rivalId, rivalName}}
    GetUserRivalMusicApi  request body UserRivalMusicRequestVO(userId + rivalId + nextIndex
                                                       + userRivalMusicLevelList)
                          Response   {userId, rivalId, length, nextIndex, userRivalMusicList}
Basis:
    source/Assembly-CSharp/Net.VO.Mai2/UserRivalRequestVO.cs
    source/Assembly-CSharp/Net.VO.Mai2/UserRivalMusicRequestVO.cs
    source/2026-10-05.log:95,101

★ Opponent ID needcalluseFor(First by GetUserFavoriteItemApi of kind=2 Retrieved at).

Example:
    from api import GetUserRivalData, GetUserRivalMusic
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
    get_all_pages,
)


def GetUserRivalData(
    user_id: int,
    rival_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetching opponent data(Corresponding GetUserRivalDataApi).

    Parameter:
        user_id:  user ID(Required)
        rival_id: Opponent ID(Required)

    Returns:
        Raw Response dict,Contains userRivalData
    """
    log_info("Fetching opponent data:user_id=" + str(user_id) + " rival_id=" + str(rival_id))
    return _get(
        "GetUserRivalDataApi",
        UserRivalRequestVO(userId=user_id, rivalId=rival_id),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserRivalMusic(
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
    Take Opponent Track Score(Single Page,Corresponding GetUserRivalMusicApi).

    Parameter:
        user_id:    user ID(Required)
        rival_id:   Opponent ID(Required)
        next_index: Paged Index(0 = first)
        levels:     difficultyfileBitList(Optional,default 0/1/2/3/4/10)

    Returns:
        Raw Response dict,Contains userRivalMusicList
    """
    lv = list(levels) if levels else list(RIVAL_MUSIC_LEVELS)
    log_info("Take Opponent Track Score:user_id=" + str(user_id) + " rival_id=" + str(rival_id)
             + " levels=" + str(lv))
    return _get(
        "GetUserRivalMusicApi",
        UserRivalMusicRequestVO(
            userId=user_id, rivalId=rival_id, nextIndex=next_index,
            userRivalMusicLevelList=[{"level": x} for x in lv],
        ),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserRivalMusicAll(
    user_id: int,
    rival_id: int,
    *,
    levels: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take Opponent Track Score(auto-pagingTakeFull).

    Returns:
        {"userRivalMusicList": [...]}
    """
    lv = list(levels) if levels else list(RIVAL_MUSIC_LEVELS)
    log_info("Take Opponent Track Score(Full Amount):user_id=" + str(user_id) + " rival_id=" + str(rival_id))
    items = get_all_pages(
        "GetUserRivalMusicApi", user_id, "userRivalMusicList",
        body_factory=lambda ni: UserRivalMusicRequestVO(
            userId=user_id, rivalId=rival_id, nextIndex=ni or 0,
            userRivalMusicLevelList=[{"level": x} for x in lv]),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("Opponent track acquisition complete:" + str(len(items)) + " item")
    return {"userRivalMusicList": items}
