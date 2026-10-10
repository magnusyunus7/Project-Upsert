# -*- coding: utf-8 -*-
"""
get_user_map. py — Take user map progress(GetUserMapApi)
================================================================================

Take the propulsion distance of the player's various maps(real machine 104 item).

Corresponding interface: GetUserMapApi
request body: UserMapRequestVO(userId + nextIndex + maxCount=1000)
Response:{userId, length, nextIndex, userMapList:[...]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserMapRequestVO. cs

  - Get Side issuance 100+ item; Upsert Only send back"Variation"ofthat 1 item
   (real machine: mapId=550003 of distance 1424000 -> 1435000).

Example:
  from api import GetUserMap / GetUserMapAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdPageRequestVO, get_all_pages


def GetUserMap(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take user map progress(Single Page, Corresponding GetUserMapApi).

  Parameter:
    next_index: Pagination Start Index(0 = first)

  Returns:
    Raw Response dict, Contains userMapList
  """
    log_info("Take user map progress: user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserMapApi",
        UserIdPageRequestVO(userId=user_id, nextIndex=next_index, maxCount=1000),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserMapAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take user map progress(auto-pagingTakeFull).

  Returns:
    {"userMapList": [...]}
  """
    log_info("Take user map progress(Full Amount): user_id=" + str(user_id))
    items = get_all_pages(
        "GetUserMapApi", user_id, "userMapList",
        body_factory=lambda ni: UserIdPageRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=1000),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("Map Progress Acquisition Complete:" + str(len(items)) + " item")
    return {"userMapList": items}
