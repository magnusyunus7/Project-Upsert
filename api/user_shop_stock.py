# -*- coding: utf-8 -*-
"""
user_shop_stock.py —— 取用户商店库存（GetUserShopStockApi）
================================================================================

取玩家在各商店商品的已兑换次数。

对应接口：GetUserShopStockApi
请求体  ：UserShopStockRequestVO（userId + shopItemIdList）
响应    ：{userId, userShopStockList:[{shopItemId,tradeCount}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserShopStockRequestVO.cs
          source/2026-10-05.log:117  真机请求体带 100+ 个 shopItemId

★ shopItemIdList 需要调用方提供（来自游戏 Master 数据，脚本无法自行推导）。
  不传时按空列表发送，服务端返回空 userShopStockList —— 这是合法的。

调用示例：
    from api import UserShopStock
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLAY_SHOP_ITEM_IDS, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserShopStockRequestVO


def UserShopStock(
    user_id: int,
    *,
    shop_item_id_list: Optional[List[int]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户商店库存（对应 GetUserShopStockApi）。

    参数：
        user_id:           用户 ID（必填）
        shop_item_id_list: 商品 ID 清单（可选，默认取 config.PLAY_SHOP_ITEM_IDS）

    返回：
        原始响应 dict，含 userShopStockList
    """
    ids = list(shop_item_id_list) if shop_item_id_list is not None \
        else list(PLAY_SHOP_ITEM_IDS)

    log_info("取用户商店库存：user_id=" + str(user_id) + " 商品数=" + str(len(ids)))
    return _get(
        "GetUserShopStockApi",
        UserShopStockRequestVO(userId=user_id, shopItemIdList=ids),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
