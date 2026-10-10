# -*- coding: utf-8 -*-
"""
get_user_ghost.py —— Fetching user ghost data（GetUserGhostApi）
================================================================================

Take Player「Ghosts」Match Record（real machine 15 item）。

Corresponding interface：GetUserGhostApi
request body  ：UserIdRequestVO
Response    ：{length, userGhostList:[...]}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserGhostRequestVO.cs

    ★ Upsert Side userGhost defaultleave blank：source code VOExtensions.cs:235 is
        dst.userGhost = (!src.MyGhost.NeedSave) ? null : new GetUserGhost[1] {...};
      Only「this gameGeneratetextGhosts」Only returned，textnetworkscriptReprintNooutGhostsdata。

call exampleExample：
    from api import GetUserGhost
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserGhost(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetching user ghost data（Corresponding GetUserGhostApi）。

    returntimes：
        Raw Response dict，Contains userGhostList
    """
    log_info("Fetching user ghost data：user_id=" + str(user_id))
    return _get("GetUserGhostApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
