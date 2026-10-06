# -*- coding: utf-8 -*-
"""
game_charge.py —— 取游戏计费配置（GetGameChargeApi）
================================================================================

取服务器下发的计费档位。

对应接口：GetGameChargeApi
请求体  ：{"isAll": false}（GameChargeRequestVO）
响应    ：{length, gameChargeList:[{orderId,chargeId,price,startDate,endDate}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/GameChargeRequestVO.cs
          source/2026-10-05.log:9  真机请求 {"isAll":false}

调用示例：
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
    """请求 VO（对应 GameChargeRequestVO）。"""
    isAll: bool = False


def GetGameCharge(
    *,
    is_all: bool = False,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取游戏计费配置（对应 GetGameChargeApi）。

    返回：
        原始响应 dict，含 gameChargeList
    """
    log_info("取游戏计费配置：isAll=" + str(is_all))
    return request_dict(
        "GetGameChargeApi", GameChargeRequestVO(isAll=is_all),
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
