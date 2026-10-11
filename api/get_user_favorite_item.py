# -*- coding: utf-8 -*-
"""
get_user_favorite_item. py — Fetching user favorite tracks / Opponent (GetUserFavoriteItemApi)
================================================================================

Take the player's favorite songs (kind=1) or Collected Opponents (kind=2).

Corresponding interface: GetUserFavoriteItemApi
request body: UserFavoriteItemRequestVO(userId + kind + nextIndex + maxCount=100
                  + isAllFavoriteItem)
Response:{userId, kind, length, nextIndex, userFavoriteItemList:[{orderId, id}]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserFavoriteItemRequestVO. cs
     source/2026-10-05. log:93,107 real machine kind=2 And kind=1 Once each

- Field name is kind(No itemKind), Don't misspell.

Example:
  from api import GetUserFavoriteItem, GetUserFavoriteItemAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserFavoriteItemRequestVO, get_all_pages

#: kind Pick a value
FAVORITE_ITEM_KIND_MUSIC = 1     # receivemusic
FAVORITE_ITEM_KIND_RIVAL = 2     # receiveOpponent


def GetUserFavoriteItem(
    user_id: int,
    kind: int = FAVORITE_ITEM_KIND_MUSIC,
    *,
    next_index: int = 0,
    is_all_favorite_item: bool = False,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch user favorites(Single Page, Corresponding GetUserFavoriteItemApi).

  Parameter:
    user_id: user ID(Required)
    kind:  1=receive music 2=receive Opponent (default 1)

  Returns:
    Raw Response dict, Contains userFavoriteItemList.
  """
    log_info("Fetch user favorites: user_id=" + str(user_id) + " kind=" + str(kind)
             + " next_index=" + str(next_index))
    return _get(
        "GetUserFavoriteItemApi",
        UserFavoriteItemRequestVO(
            userId=user_id, kind=kind, nextIndex=next_index,
            maxCount=100, isAllFavoriteItem=is_all_favorite_item,
        ),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserFavoriteItemAll(
    user_id: int,
    kind: int = FAVORITE_ITEM_KIND_MUSIC,
    *,
    is_all_favorite_item: bool = False,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch user favorites (auto-paging Take Full).

  Returns:
    {"userFavoriteItemList": [...]}
  """
    log_info("Fetch user favorites (Full Amount): user_id=" + str(user_id) + " kind=" + str(kind))
    items = get_all_pages(
        "GetUserFavoriteItemApi", user_id, "userFavoriteItemList",
        body_factory=lambda ni: UserFavoriteItemRequestVO(
            userId=user_id, kind=kind, nextIndex=ni or 0,
            maxCount=100, isAllFavoriteItem=is_all_favorite_item),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("receive item fetch complete: " + str(len(items)) + " item")
    return {"userFavoriteItemList": items}
