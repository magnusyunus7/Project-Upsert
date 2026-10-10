# -*- coding: utf-8 -*-
"""
get_user_item.py —— Pick up user items(GetUserItemApi)
================================================================================

Take inventory of players' various items(real machinepress kind Minutes 12 request).

Corresponding interface:GetUserItemApi
request body  :UserItemRequestVO(userId + nextIndex + maxCount=100)
Response:{userId, length, nextIndex, itemKind, userItemList:[{itemKind,itemId,stock,isValid}]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserItemRequestVO.cs

--------------------------------------------------------------------------------
★★ firsthair nextIndex Must have Sentinel value(The easiest pit to step on)
--------------------------------------------------------------------------------
source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserItem.cs:17-24

    public PacketGetUserItem(ulong userId, long itemId, ...)
    {
        Create(GetNetQuery(userId, itemId * 10000000000L));   // <- firstPackage
    }
    // Proc(): nextIndex != 0 timecontinue

real machinelog source/2026-10-05.log:32 Also nextIndex=10000000000.
Passing on 0 will be rejected by the server(HTTP 500).

★ request bodyin**none itemKind Field** —— is nextIndex ofvalueof:
    number 1 text nextIndex = kind * 1e10
    Subsequent page flips follow a response back of nextIndex

Example:
    from api import GetUserItem, GetUserItemAll
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_debug, log_info, log_warning
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserItemRequestVO, ITEM_KINDS, ITEM_NEXT_INDEX_FACTOR


def GetUserItem(
    user_id: int,
    item_kind: int,
    *,
    next_index: Optional[int] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetching a certain type of props from a user(Corresponding GetUserItemApi).

    Parameter:
        user_id:   user ID(Required)
        item_kind: text(Required):1=Designer Tags 2=text 3=Avatar 4=text 5=Music …
        next_index: Paged Index;**None(default)first**,will be automatically converted to
                    item_kind * 10000000000 ofvalue.

    Returns:
        Raw Response dict,Contains userItemList
    """
    if next_index is None:
        next_index = item_kind * ITEM_NEXT_INDEX_FACTOR

    log_info("Pick up user items:user_id=" + str(user_id) + " item_kind=" + str(item_kind)
             + " nextIndex=" + str(next_index))

    return _get(
        "GetUserItemApi",
        UserItemRequestVO(userId=user_id, nextIndex=next_index, maxCount=100),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserItemAll(
    user_id: int,
    *,
    item_kinds: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Fetch all user items(press ITEM_KINDS categoriesfetch,and automatically flip the page).

    Parameter:
        item_kinds: list(Optional,default ITEM_KINDS)

    Returns:
        {"userItemList": [...]},Merged all categories and pagination
    """
    kinds = list(item_kinds) if item_kinds else list(ITEM_KINDS)
    log_info("Fetch all user items:user_id=" + str(user_id) + " kinds=" + str(kinds))

    merged: List[Dict[str, Any]] = []
    for kind in kinds:
        next_index: Optional[int] = kind * ITEM_NEXT_INDEX_FACTOR
        page = 0
        while next_index:
            page += 1
            resp = _get(
                "GetUserItemApi",
                UserItemRequestVO(userId=user_id, nextIndex=next_index, maxCount=100),
                user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
            )
            items = resp.get("userItemList") or []
            if isinstance(items, dict):
                items = [items]
            merged.extend(items)

            next_index = int(resp.get("nextIndex") or 0)
            log_debug("item_kind=" + str(kind) + " number " + str(page) + " "
                      + str(len(items)) + " item,nextIndex=" + str(next_index))
            if page >= 200:
                log_warning("item_kind=" + str(kind) + " text 200 Aborted")
                break

    log_info("getTakeDone:" + str(len(merged)) + " item")
    return {"userItemList": merged}
