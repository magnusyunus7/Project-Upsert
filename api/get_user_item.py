# -*- coding: utf-8 -*-
"""
get_user_item.py —— 取用户道具（GetUserItemApi）
================================================================================

取玩家各类道具的库存（真机按 kind 分 12 次请求）。

对应接口：GetUserItemApi
请求体  ：UserItemRequestVO（userId + nextIndex + maxCount=100）
响应    ：{userId, length, nextIndex, itemKind, userItemList:[{itemKind,itemId,stock,isValid}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserItemRequestVO.cs

--------------------------------------------------------------------------------
★★ 首发 nextIndex 必须带哨兵值（最容易踩的坑）
--------------------------------------------------------------------------------
source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserItem.cs:17-24

    public PacketGetUserItem(ulong userId, long itemId, ...)
    {
        Create(GetNetQuery(userId, itemId * 10000000000L));   // <- 首包哨兵
    }
    // Proc(): nextIndex != 0 时继续翻页

真机日志 source/2026-10-05.log:32 也是 nextIndex=10000000000。
传 0 会被服务端拒绝（HTTP 500）。

★ 请求体里**没有 itemKind 字段** —— 类别是靠 nextIndex 的哨兵值表达的：
    第 1 页 nextIndex = kind * 1e10
    后续翻页沿用响应回的 nextIndex

调用示例：
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
    取用户某一类道具（对应 GetUserItemApi）。

    参数：
        user_id:   用户 ID（必填）
        item_kind: 道具类别（必填）：1=名牌 2=称号 3=头像 4=礼物 5=乐曲 …
        next_index: 分页索引；**None（默认）表示首页**，会自动换算成
                    item_kind * 10000000000 的哨兵值。

    返回：
        原始响应 dict，含 userItemList
    """
    if next_index is None:
        next_index = item_kind * ITEM_NEXT_INDEX_FACTOR

    log_info("取用户道具：user_id=" + str(user_id) + " item_kind=" + str(item_kind)
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
    取用户全部道具（按 ITEM_KINDS 逐个类别抓取，并自动翻页）。

    参数：
        item_kinds: 类别列表（可选，默认 ITEM_KINDS）

    返回：
        {"userItemList": [...]}，已合并所有类别与分页
    """
    kinds = list(item_kinds) if item_kinds else list(ITEM_KINDS)
    log_info("取用户全部道具：user_id=" + str(user_id) + " kinds=" + str(kinds))

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
            log_debug("item_kind=" + str(kind) + " 第 " + str(page) + " 页："
                      + str(len(items)) + " 条，nextIndex=" + str(next_index))
            if page >= 200:
                log_warning("item_kind=" + str(kind) + " 翻页超过 200 页，已中止")
                break

    log_info("道具获取完成：" + str(len(merged)) + " 条")
    return {"userItemList": merged}
