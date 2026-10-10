# -*- coding: utf-8 -*-
"""
get_user_kaleidx_scope.py —— Take KALEIDX text(GetUserKaleidxScopeApi / GetGameKaleidxScopeApi)
================================================================================

Corresponding interface:
    GetUserKaleidxScopeApi  request body UserIdRequestVO(userId)
                            Response   {userId, userKaleidxScopeList:[...]}
    GetGameKaleidxScopeApi  request body **emptyObject {}**(GameKaleidxScopeRequestVO noneAnyField)
                            Response   {gameKaleidxScopeList:[{gateId, phaseId}]}
Basis:
    source/Assembly-CSharp/Net.VO.Mai2/UserKaleidxScopeRequestVO.cs
    source/Assembly-CSharp/Net.VO.Mai2/GameKaleidxScopeRequestVO.cs(empty)
    source/Assembly-CSharp/Net.VO.Mai2/GameKaleidxScopeResponseVO.cs
    source/2026-10-05.log:15,119

★★ mustDistinguish(lead to userData Empty)
--------------------------------------------------------------------------------
GameKaleidxScopeResponseVO in**Only** gameKaleidxScopeList Field,none userData.
file userData ofcurrentis GetUserDataApi(text get_user_data.py).

real machinelogin"GetGameKaleidxScope ofResponseBelt userData"ispacketToolsputtimerelatedof
Illusion caused by merging two responses —— Do not give accordingly GetGameKaleidxScopeApi hair userId,
Multiple fields will cause the server to return empty content.

Example:
    from api import GetUserKaleidxScope, GetGameKaleidxScope
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, EmptyRequestVO, UserIdRequestVO


def GetUserKaleidxScope(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Pick player KALEIDX text(Corresponding GetUserKaleidxScopeApi).

    Returns:
        Raw Response dict,Contains userKaleidxScopeList
    """
    log_info("Pick player KALEIDX user_id=" + str(user_id))
    return _get("GetUserKaleidxScopeApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)


def GetGameKaleidxScope(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take a full serving KALEIDX text(Corresponding GetGameKaleidxScopeApi).

    ★ request bodyisemptyObject {} —— the RequestVO None of the fields,**Do not pass userId**.

    Returns:
        Raw Response dict,Contains gameKaleidxScopeList
    """
    log_info("Take a full serving KALEIDX text")
    return _get("GetGameKaleidxScopeApi", EmptyRequestVO(), 0,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
