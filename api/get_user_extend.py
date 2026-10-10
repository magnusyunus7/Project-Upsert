# -*- coding: utf-8 -*-
"""
get_user_extend.py —— Take User Extended Settings（GetUserExtendApi）
================================================================================

Take player's last selection / Categories / Expansion status of card slot etc.。

Corresponding interface：GetUserExtendApi
request body  ：UserIdRequestVO
Response    ：{userId, userExtend:{...}}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserExtendRequestVO.cs

    ★ where categoryIndex（text）And userPlaylog of extNum4 Must be consistent
      （real machineBoth 2022），groupPackagetimemustnote。

call exampleExample：
    from api import GetUserExtend
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserExtend(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take User Extended Settings（Corresponding GetUserExtendApi）。

    returntimes：
        Raw Response dict，Contains userExtend Child Objects
    """
    log_info("Take User Extended Settings：user_id=" + str(user_id))
    return _get("GetUserExtendApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
