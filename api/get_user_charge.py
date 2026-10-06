# -*- coding: utf-8 -*-
"""
get_user_charge.py —— 取用户票券（GetUserChargeApi）
================================================================================

取玩家的票券持有情况（真机 3 条）。

对应接口：GetUserChargeApi
请求体  ：UserIdRequestVO
响应    ：{userId, length, userChargeList:[{chargeId,stock,purchaseDate,validDate,extNum1}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserChargeRequestVO.cs

★ 回传 Upsert 时要丢掉 extNum1（真机 Upsert 报文里没有这个字段）。

调用示例：
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
    取用户票券（对应 GetUserChargeApi）。

    返回：
        原始响应 dict，含 userChargeList
    """
    log_info("取用户票券：user_id=" + str(user_id))
    return _get("GetUserChargeApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
