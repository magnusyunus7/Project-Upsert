# -*- coding: utf-8 -*-
"""
get_user_login_bonus. py — Take User Login Reward(GetUserLoginBonusApi)
================================================================================

Collect Player Login Rewards Progress(real machine 38 item, Two pages).

Corresponding interface: GetUserLoginBonusApi
request body: UserLoginBonusRequestVO(userId + nextIndex + maxCount=20)
Response:{userId, length, nextIndex, userLoginBonusList:[{bonusId, point, isCurrent, isComplete}]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserLoginBonusRequestVO. cs

- Callback Upsert timeOnly send back isCurrent=true ofthatOneitem(toofthatitem).

Example:
  from api import GetUserLoginBonus, GetUserLoginBonusAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserLoginBonusRequestVO, get_all_pages


def GetUserLoginBonus(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take User Login Reward(Single Page, Corresponding GetUserLoginBonusApi).

  Parameter:
    next_index: Pagination Start Index(0 = first)

  Returns:
    Raw Response dict, Contains userLoginBonusList
  """
    log_info("Take User Login Reward: user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserLoginBonusApi",
        UserLoginBonusRequestVO(userId=user_id, nextIndex=next_index, maxCount=20),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserLoginBonusAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take User Login Reward(auto-pagingTakeFull).

  Returns:
    {"userLoginBonusList": [...]}
  """
    log_info("Take User Login Reward(Full Amount): user_id=" + str(user_id))
    items = get_all_pages(
        "GetUserLoginBonusApi", user_id, "userLoginBonusList",
        body_factory=lambda ni: UserLoginBonusRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=20),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("loginRewardsfetch complete:" + str(len(items)) + " item")
    return {"userLoginBonusList": items}
