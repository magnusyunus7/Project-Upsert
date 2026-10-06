# -*- coding: utf-8 -*-
"""
user_favorite_item.py —— 取用户收藏曲目/对手（GetUserFavoriteItemApi）
================================================================================

取玩家收藏的乐曲（kind=1）或收藏的对手（kind=2）。

对应接口：GetUserFavoriteItemApi
请求体  ：UserFavoriteItemRequestVO（userId + kind + nextIndex + maxCount=100
                                    + isAllFavoriteItem）
响应    ：{userId, kind, length, nextIndex, userFavoriteItemList:[{orderId,id}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserFavoriteItemRequestVO.cs
          source/2026-10-05.log:93,107  真机 kind=2 与 kind=1 各一次

★ 字段名是 kind（不是 itemKind），别写错。

调用示例：
    from api import UserFavoriteItem, UserFavoriteItemAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserFavoriteItemRequestVO, fetch_all_pages

#: kind 取值
FAVORITE_ITEM_KIND_MUSIC = 1     # 收藏乐曲
FAVORITE_ITEM_KIND_RIVAL = 2     # 收藏对手


def UserFavoriteItem(
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
    取用户收藏项（单页，对应 GetUserFavoriteItemApi）。

    参数：
        user_id: 用户 ID（必填）
        kind:    1=收藏乐曲 2=收藏对手（默认 1）

    返回：
        原始响应 dict，含 userFavoriteItemList
    """
    log_info("取用户收藏项：user_id=" + str(user_id) + " kind=" + str(kind)
             + " next_index=" + str(next_index))
    return _get(
        "GetUserFavoriteItemApi",
        UserFavoriteItemRequestVO(
            userId=user_id, kind=kind, nextIndex=next_index,
            maxCount=100, isAllFavoriteItem=is_all_favorite_item,
        ),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def UserFavoriteItemAll(
    user_id: int,
    kind: int = FAVORITE_ITEM_KIND_MUSIC,
    *,
    is_all_favorite_item: bool = False,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户收藏项（自动翻页取全）。

    返回：
        {"userFavoriteItemList": [...]}
    """
    log_info("取用户收藏项（全量）：user_id=" + str(user_id) + " kind=" + str(kind))
    items = fetch_all_pages(
        "GetUserFavoriteItemApi", user_id, "userFavoriteItemList",
        body_factory=lambda ni: UserFavoriteItemRequestVO(
            userId=user_id, kind=kind, nextIndex=ni or 0,
            maxCount=100, isAllFavoriteItem=is_all_favorite_item),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("收藏项获取完成：" + str(len(items)) + " 条")
    return {"userFavoriteItemList": items}
