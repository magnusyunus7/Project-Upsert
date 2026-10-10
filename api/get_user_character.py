# -*- coding: utf-8 -*-
"""
get_user_character.py —— Take a list of user roles(GetUserCharacterApi)
================================================================================

Take the level and awakening of all of the player's characters(real machine 312 item).

Corresponding interface:GetUserCharacterApi
request body  :UserIdRequestVO
Response:{userId, length, userCharacterList:[...]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserCharacterRequestVO.cs

    ★ Callback Upsert timeOnlyHold characterId / level / awakening / useCount Four Fields
      (real machine source/2026-10-05.log:123 of userCharacterList That's it. 4 keys).

Example:
    from api import GetUserCharacter
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserCharacter(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take a list of user roles(Corresponding GetUserCharacterApi).

    Returns:
        Raw Response dict,Contains userCharacterList
    """
    log_info("Take a list of user roles:user_id=" + str(user_id))
    return _get("GetUserCharacterApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
