# -*- coding: utf-8 -*-
"""
get_user_shop_stock. py — Retrieve user store inventory (GetUserShopStockApi)
================================================================================

Take the number of times a player has redeemed an item in each store.

Corresponding interface: GetUserShopStockApi
request body: UserShopStockRequestVO(userId + shopItemIdList)
Response:{userId, userShopStockList:[{shopItemId, tradeCount}]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserShopStockRequestVO. cs
     source/2026-10-05. log:117 real machine request body Belt 100+ Piece shopItemId

- shopItemIdList need call use For (Master data, script no).
 Send as empty list when not passing, server returns empty userShopStockList — this is Legal of.

Example:
  from api import GetUserShopStock
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLAY_SHOP_ITEM_IDS, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserShopStockRequestVO


def GetUserShopStock(
    user_id: int,
    *,
    shop_item_id_list: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Retrieve user store inventory (Corresponding GetUserShopStockApi).

  Parameter:
    user_id:      user ID(Required)
    shop_item_id_list: Product ID (Optional, default Take config. PLAY_SHOP_ITEM_IDS)

  Returns:
    Raw Response dict, Contains userShopStockList.
  """
    ids = list(shop_item_id_list) if shop_item_id_list is not None \
        else list(PLAY_SHOP_ITEM_IDS)

    log_info("Retrieve user store inventory: user_id=" + str(user_id) + " Number of items=" + str(len(ids)))
    return _get(
        "GetUserShopStockApi",
        UserShopStockRequestVO(userId=user_id, shopItemIdList=ids),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
