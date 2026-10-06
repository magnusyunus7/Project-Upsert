# -*- coding: utf-8 -*-
"""
user_getter_common.py —— 各取数脚本的公共底座
================================================================================

只提供三样东西，取数逻辑都在各自的脚本里：

    1. 各接口的请求 VO（严格对应 source/.../Net.VO.Mai2/*RequestVO.cs）
    2. _get()            发一次请求并返回**原始响应 dict**
    3. get_all_pages() 自动翻页

--------------------------------------------------------------------------------
★ 为什么单独抽出来：各接口的请求体并不统一
--------------------------------------------------------------------------------
权威依据 source/Assembly-CSharp/Net.VO.Mai2/ 下各自的 XxxRequestVO.cs：

    GameKaleidxScopeRequestVO : 空类，一个字段都没有
    UserDetailRequestVO       : 只有 userId
    UserMapRequestVO          : userId + nextIndex + maxCount = 1000
    UserLoginBonusRequestVO   : userId + nextIndex + maxCount = 20
    UserItemRequestVO         : userId + nextIndex + maxCount = 100
    UserMusicRequestVO        : userId + nextIndex + maxCount = 50
    UserFavoriteRequestVO     : userId + itemKind
    UserFavoriteItemRequestVO : userId + kind + nextIndex + maxCount = 100 + isAllFavoriteItem
    UserShopStockRequestVO    : userId + shopItemIdList
    UserRivalMusicRequestVO   : userId + rivalId + nextIndex + userRivalMusicLevelList

发错字段名或漏字段，服务端会返回异常或空数据。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_debug, log_warning
from .maimai_net import MaimaiNetClient, get_default_client


# =============================================================================
# 请求 VO（逐字段对应 C# 的 XxxRequestVO）
# =============================================================================

@dataclass
class EmptyRequestVO:
    """空请求体（对应 GameKaleidxScopeRequestVO —— 它确实没有任何字段）。"""


@dataclass
class UserIdRequestVO:
    """只有 userId（对应 UserDetailRequestVO / UserCharacterRequestVO / UserOptionRequestVO 等）。"""
    userId: int


@dataclass
class UserIdPageRequestVO:
    """通用分页（对应 UserMapRequestVO，maxCount 默认 1000）。"""
    userId: int
    nextIndex: int = 0
    maxCount: int = 1000


@dataclass
class UserLoginBonusRequestVO:
    """对应 UserLoginBonusRequestVO（maxCount 默认 20）。"""
    userId: int
    nextIndex: int = 0
    maxCount: int = 20


@dataclass
class UserItemRequestVO:
    """对应 UserItemRequestVO（maxCount 默认 100）。"""
    userId: int
    nextIndex: int = 0
    maxCount: int = 100


@dataclass
class UserMusicRequestVO:
    """对应 UserMusicRequestVO（maxCount 默认 50）。"""
    userId: int
    nextIndex: int = 0
    maxCount: int = 50


@dataclass
class UserCourseRequestVO:
    """对应 UserCourseRequestVO（只有 userId + nextIndex，**没有** maxCount）。"""
    userId: int
    nextIndex: int = 0


@dataclass
class UserFavoriteRequestVO:
    """对应 UserFavoriteRequestVO（按 itemKind 分次请求）。"""
    userId: int
    itemKind: int = 0


@dataclass
class UserFavoriteItemRequestVO:
    """对应 UserFavoriteItemRequestVO（注意字段名是 kind，不是 itemKind）。"""
    userId: int
    kind: int = 1
    nextIndex: int = 0
    maxCount: int = 100
    isAllFavoriteItem: bool = False


@dataclass
class UserShopStockRequestVO:
    """对应 UserShopStockRequestVO。"""
    userId: int
    shopItemIdList: List[int] = field(default_factory=list)


@dataclass
class UserRivalRequestVO:
    """对应 UserRivalRequestVO。"""
    userId: int
    rivalId: int = 0


@dataclass
class UserRivalMusicRequestVO:
    """对应 UserRivalMusicRequestVO（level 列表固定 6 档）。"""
    userId: int
    rivalId: int = 0
    nextIndex: int = 0
    userRivalMusicLevelList: List[Dict[str, int]] = field(
        default_factory=lambda: [{"level": lv} for lv in (0, 1, 2, 3, 4, 10)]
    )


# =============================================================================
# 常量
# =============================================================================

#: GetUserItemApi 的 itemKind 取值（对应 Net.VO.Mai2/ItemKind.cs）
#: 客户端在 StateUserDownload.cs 里依次下载这些 kind
ITEM_KINDS: tuple = (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 14)

#: ★ GetUserItemApi 首页 nextIndex 的哨兵系数。
#:   依据 source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserItem.cs:17-24
#:        Create(GetNetQuery(userId, itemId * 10000000000L));
#:   传 0 会被服务端拒绝。真机日志 source/2026-10-05.log:32 也是 10000000000。
ITEM_NEXT_INDEX_FACTOR: int = 10000000000

#: GetUserFavoriteApi 的 itemKind（真机顺序固定 3/1/2/10/11，见 source/2026-10-05.log:59-68）
FAVORITE_ITEM_KINDS: tuple = (3, 1, 2, 10, 11)

#: GetUserRivalMusicApi 的 level 档位（真机 source/2026-10-05.log:101）
RIVAL_MUSIC_LEVELS: tuple = (0, 1, 2, 3, 4, 10)


# =============================================================================
# 内部工具
# =============================================================================

def _get(
    api_name: str,
    body: Any,
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    发一次请求，返回**原始响应 dict**（不做 VO 映射，保留服务端全部字段）。

    ★ 取数脚本一律走这里：upsertUserAll 需要响应原文，
      映射成 dataclass 会丢掉服务端多给的字段。
    """
    net = client or get_default_client()
    raw = net.request(
        api_name, body,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS,
    )
    if isinstance(raw, str):
        return json.loads(raw) if raw else {}
    return raw or {}


def get_all_pages(
    api_name: str,
    user_id: int,
    list_key: str,
    *,
    body_factory: Optional[Callable[[Optional[int]], Any]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
    max_pages: int = 200,
) -> List[Any]:
    """
    自动翻页抓取某个列表接口的全部条目。

    分页约定（各 Packet 的 Proc 里都是这个逻辑）：
        nextIndex == 0  -> 没有更多数据
        nextIndex != 0  -> 下一页的起始索引

    参数：
        api_name:      逻辑接口名
        list_key:      响应里承载列表的键名（如 "userMapList"）
        body_factory:  可选；接收 next_index 返回请求 VO 的工厂。
                       ★ 首页会以 next_index=None 调用它 —— 这是为了支持
                         GetUserItemApi 这类「首发要带哨兵值」的接口
                         （首包 nextIndex = itemKind * 1e10，不能是 0）。
        max_pages:     翻页上限（防御性）

    返回：
        合并后的全部条目
    """
    all_items: List[Any] = []
    next_index: Optional[int] = None
    for page in range(max_pages):
        if body_factory is not None:
            body = body_factory(next_index)
        else:
            body = UserIdPageRequestVO(userId=user_id, nextIndex=next_index or 0)

        resp = _get(api_name, body, user_id,
                    client_id=client_id, timeout_ms=timeout_ms, client=client)
        items = resp.get(list_key) or []
        if isinstance(items, dict):
            items = [items]
        all_items.extend(items)

        next_index = int(resp.get("nextIndex") or 0)
        log_debug(
            api_name + " 第 " + str(page + 1) + " 页：本页 " + str(len(items))
            + " 条，累计 " + str(len(all_items)) + " 条，nextIndex=" + str(next_index)
        )
        if not next_index:
            break
    else:
        log_warning(api_name + " 超过 " + str(max_pages) + " 页仍未结束，已中止翻页")

    return all_items
