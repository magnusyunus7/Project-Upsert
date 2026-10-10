# -*- coding: utf-8 -*-
"""
get_user_favorite. py — Collect User Favorites(GetUserFavoriteApi)
================================================================================

Collect various types of player favorites(/ Avatar / related / file /…).

Corresponding interface: GetUserFavoriteApi
request body: UserFavoriteRequestVO(userId + itemKind)
Response:{userId, userFavorite:{itemKind, itemIdList:[...]}}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserFavoriteRequestVO. cs
     source/2026-10-05. log:59-68 real machinerequest itemKind = 3,1,2,10,11

- Callback Upsert time userFavoriteList is**Heng 5 item**ofFullnumbergroup(Do not cull),
 Bitstring isNewFavoriteList isThreeValue "0"/"1"/"2".

Example:
  from api import GetUserFavorite, GetUserFavoriteAll
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserFavoriteRequestVO, FAVORITE_ITEM_KINDS


def GetUserFavorite(
    user_id: int,
    item_kind: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetching a certain type of collection from a user(Corresponding GetUserFavoriteApi).

  Parameter:
    user_id:  user ID(Required)
    item_kind: receive(Required):3=Avatar 1=2=Designer Tags 10=file 11=related

  Returns:
    Raw Response dict, Contains userFavorite
  """
    log_info("Collect User Favorites: user_id=" + str(user_id) + " itemKind=" + str(item_kind))
    return _get(
        "GetUserFavoriteApi",
        UserFavoriteRequestVO(userId=user_id, itemKind=item_kind),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserFavoriteAll(
    user_id: int,
    *,
    item_kinds: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch all user favorites(pressreal machineorderrequest 5 categories).

  Parameter:
    item_kinds: list(Optional, default FAVORITE_ITEM_KINDS = (3,1,2,10,11))

  Returns:
    {"userFavoriteList": [{itemKind, itemIdList},...]}, Heng 5 item
  """
    kinds = list(item_kinds) if item_kinds else list(FAVORITE_ITEM_KINDS)
    log_info("Fetch all user favorites: user_id=" + str(user_id) + " kinds=" + str(kinds))

    result: List[Dict[str, Any]] = []
    raw_items: List[Dict[str, Any]] = []
    for kind in kinds:
        resp = _get(
            "GetUserFavoriteApi",
            UserFavoriteRequestVO(userId=user_id, itemKind=kind),
            user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
        )
        fav = resp.get("userFavorite") or {}
        if not fav:
            log_warning("itemKind=" + str(kind) + " notreturns userFavorite, pressemptyProcess")
            fav = {"itemKind": kind, "itemIdList": []}

        # - on the real machine itemKind=10 ofThe response is {"itemKind": null,"itemIdList":[]}(server).
        #  Keep a copy**Original**Copies for Upsert For Differential — In the bit string "1" currentisGenerateof.
        raw_items.append(dict(fav))

        # The copy used for the return is completed according to the requested value itemKind, in the packetAppearance null
        filled = dict(fav)
        if not filled.get("itemKind"):
            filled["itemKind"] = kind
        result.append(filled)

    log_info("receivefetch complete:" + str(len(result)) + "")
    return {"userFavoriteList": result, "_raw": raw_items}
