# -*- coding: utf-8 -*-
"""
get_user_favorite.py —— 取用户收藏（GetUserFavoriteApi）
================================================================================

取玩家各类收藏夹（称号 / 头像 / 相框 / 搭档 / 背景…）。

对应接口：GetUserFavoriteApi
请求体  ：UserFavoriteRequestVO（userId + itemKind）
响应    ：{userId, userFavorite:{itemKind, itemIdList:[...]}}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserFavoriteRequestVO.cs
          source/2026-10-05.log:59-68  真机依次请求 itemKind = 3,1,2,10,11

★ 回传 Upsert 时 userFavoriteList 是**恒 5 条**的完整数组（不做剔除），
  位串 isNewFavoriteList 是三值 "0"/"1"/"2"。

调用示例：
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
    取用户某一类收藏（对应 GetUserFavoriteApi）。

    参数：
        user_id:   用户 ID（必填）
        item_kind: 收藏类别（必填）：3=头像 1=称号 2=名牌 10=搭档 11=相框

    返回：
        原始响应 dict，含 userFavorite
    """
    log_info("取用户收藏：user_id=" + str(user_id) + " itemKind=" + str(item_kind))
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
    取用户全部收藏（按真机顺序请求 5 个类别）。

    参数：
        item_kinds: 类别列表（可选，默认 FAVORITE_ITEM_KINDS = (3,1,2,10,11)）

    返回：
        {"userFavoriteList": [{itemKind, itemIdList}, ...]}，恒 5 条
    """
    kinds = list(item_kinds) if item_kinds else list(FAVORITE_ITEM_KINDS)
    log_info("取用户全部收藏：user_id=" + str(user_id) + " kinds=" + str(kinds))

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
            log_warning("itemKind=" + str(kind) + " 未返回 userFavorite，按空处理")
            fav = {"itemKind": kind, "itemIdList": []}

        # ★ 真机里 itemKind=10 的响应回的是 {"itemKind":null,"itemIdList":[]}（服务端怪癖）。
        #   保留一份**原始**副本供 Upsert 差分用 —— 位串里的 "1" 正是它产生的。
        raw_items.append(dict(fav))

        # 回传用的副本按请求值补齐 itemKind，避免报文里出现 null
        filled = dict(fav)
        if not filled.get("itemKind"):
            filled["itemKind"] = kind
        result.append(filled)

    log_info("收藏获取完成：" + str(len(result)) + " 类")
    return {"userFavoriteList": result, "_raw": raw_items}
