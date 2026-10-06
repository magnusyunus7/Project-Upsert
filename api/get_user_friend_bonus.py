# -*- coding: utf-8 -*-
"""
get_user_friend_bonus.py —— 取用户好友里程（GetUserFriendBonusApi）
================================================================================

取玩家本次可领取的好友里程（getMiles）。

对应接口：GetUserFriendBonusApi
请求体  ：UserIdRequestVO
响应    ：{returnCode, userId, getMiles}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserFriendBonusRequestVO.cs
          source/2026-10-05.log:111  真机响应 {"returnCode":1,"userId":..,"getMiles":90}

调用示例：
    from api import GetUserFriendBonus, extract_gift_points
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserFriendBonus(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户好友里程（对应 GetUserFriendBonusApi）。

    返回：
        原始响应 dict：{"returnCode":1, "userId":.., "getMiles":..}
    """
    log_info("取用户好友里程：user_id=" + str(user_id))
    resp = _get("GetUserFriendBonusApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)

    if int(resp.get("returnCode", 0) or 0) != 1:
        log_warning("好友里程接口返回 returnCode=" + str(resp.get("returnCode")))
    return resp


def extract_gift_points(friend_bonus: Dict[str, Any]) -> int:
    """
    从好友里程响应里取出 getMiles（本次可领取的里程数）。

    参数：
        friend_bonus: GetUserFriendBonus 的返回值

    返回：
        getMiles 整数（取不到则为 0）
    """
    try:
        return int((friend_bonus or {}).get("getMiles", 0) or 0)
    except Exception:
        return 0
