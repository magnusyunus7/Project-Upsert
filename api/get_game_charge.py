# -*- coding: utf-8 -*-
"""
get_game_charge.py —— Take Game Billing Configuration(GetGameChargeApi)
================================================================================

Get the billing gear issued by the server.

Corresponding interface:GetGameChargeApi
request body  :{"isAll": false}(GameChargeRequestVO)
Response:{length, gameChargeList:[{orderId,chargeId,price,startDate,endDate}]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/GameChargeRequestVO.cs
          source/2026-10-05.log:9  real machinerequest {"isAll":false}

Example:
    from api import GetGameCharge
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class GameChargeRequestVO:
    """request VO(Corresponding GameChargeRequestVO)."""
    isAll: bool = False


def GetGameCharge(
    *,
    is_all: bool = False,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take Game Billing Configuration(Corresponding GetGameChargeApi).

    Returns:
        Raw Response dict,Contains gameChargeList
    """
    log_info("Take Game Billing Configuration:isAll=" + str(is_all))
    return request_dict(
        "GetGameChargeApi", GameChargeRequestVO(isAll=is_all),
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
