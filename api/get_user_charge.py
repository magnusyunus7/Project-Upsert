# -*- coding: utf-8 -*-
"""
get_user_charge.py —— Pick up user tickets(GetUserChargeApi)
================================================================================

Take the holdings of the player's tickets(real machine 3 item).

Corresponding interface:GetUserChargeApi
request body  :UserIdRequestVO
Response:{userId, length, userChargeList:[{chargeId,stock,purchaseDate,validDate,extNum1}]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserChargeRequestVO.cs

★ Callback Upsert timemustDiscard extNum1(real machine Upsert packetinnonethisfields).

Example:
    from api import GetUserCharge
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserCharge(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Pick up user tickets(Corresponding GetUserChargeApi).

    Returns:
        Raw Response dict,Contains userChargeList
    """
    log_info("Pick up user tickets:user_id=" + str(user_id))
    return _get("GetUserChargeApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
