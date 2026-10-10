# -*- coding: utf-8 -*-
"""
user_getter_common.py —— Common base for each fetch script
================================================================================

Only 3 things to offer,The fetching logic is in the respective script:

    1. Requests by Interface VO(Strict correspondence source/.../Net.VO.Mai2/*RequestVO.cs)
    2. _get()            Send a request and go back**Raw Response dict**
    3. get_all_pages() auto-paging

--------------------------------------------------------------------------------
★ Why pull it out alone:The request body of each interface is not uniform
--------------------------------------------------------------------------------
Basis source/Assembly-CSharp/Net.VO.Mai2/ Below each other's XxxRequestVO.cs:

    GameKaleidxScopeRequestVO : emptyNone of the fields
    UserDetailRequestVO       : Only userId
    UserMapRequestVO          : userId + nextIndex + maxCount = 1000
    UserLoginBonusRequestVO   : userId + nextIndex + maxCount = 20
    UserItemRequestVO         : userId + nextIndex + maxCount = 100
    UserMusicRequestVO        : userId + nextIndex + maxCount = 50
    UserFavoriteRequestVO     : userId + itemKind
    UserFavoriteItemRequestVO : userId + kind + nextIndex + maxCount = 100 + isAllFavoriteItem
    UserShopStockRequestVO    : userId + shopItemIdList
    UserRivalMusicRequestVO   : userId + rivalId + nextIndex + userRivalMusicLevelList

Wrong field name or missing field,serverwill returnExceptionsoremptydata.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_debug, log_warning
from .maimai_net import MaimaiNetClient, get_default_client


# =============================================================================
# request VO(fieldCorresponding C# of XxxRequestVO)
# =============================================================================

@dataclass
class EmptyRequestVO:
    """emptyrequest body(Corresponding GameKaleidxScopeRequestVO —— It does not have any fields)."""


@dataclass
class UserIdRequestVO:
    """Only userId(Corresponding UserDetailRequestVO / UserCharacterRequestVO / UserOptionRequestVO etc)."""
    userId: int


@dataclass
class UserIdPageRequestVO:
    """useMinutes(Corresponding UserMapRequestVO,maxCount default 1000)."""
    userId: int
    nextIndex: int = 0
    maxCount: int = 1000


@dataclass
class UserLoginBonusRequestVO:
    """Corresponding UserLoginBonusRequestVO(maxCount default 20)."""
    userId: int
    nextIndex: int = 0
    maxCount: int = 20


@dataclass
class UserItemRequestVO:
    """Corresponding UserItemRequestVO(maxCount default 100)."""
    userId: int
    nextIndex: int = 0
    maxCount: int = 100


@dataclass
class UserMusicRequestVO:
    """Corresponding UserMusicRequestVO(maxCount default 50)."""
    userId: int
    nextIndex: int = 0
    maxCount: int = 50


@dataclass
class UserCourseRequestVO:
    """Corresponding UserCourseRequestVO(Only userId + nextIndex,**none** maxCount)."""
    userId: int
    nextIndex: int = 0


@dataclass
class UserFavoriteRequestVO:
    """Corresponding UserFavoriteRequestVO(press itemKind Split request)."""
    userId: int
    itemKind: int = 0


@dataclass
class UserFavoriteItemRequestVO:
    """Corresponding UserFavoriteItemRequestVO(noteField name is kind,No itemKind)."""
    userId: int
    kind: int = 1
    nextIndex: int = 0
    maxCount: int = 100
    isAllFavoriteItem: bool = False


@dataclass
class UserShopStockRequestVO:
    """Corresponding UserShopStockRequestVO."""
    userId: int
    shopItemIdList: List[int] = field(default_factory=list)


@dataclass
class UserRivalRequestVO:
    """Corresponding UserRivalRequestVO."""
    userId: int
    rivalId: int = 0


@dataclass
class UserRivalMusicRequestVO:
    """Corresponding UserRivalMusicRequestVO(level Fixed list 6 file)."""
    userId: int
    rivalId: int = 0
    nextIndex: int = 0
    userRivalMusicLevelList: List[Dict[str, int]] = field(
        default_factory=lambda: [{"level": lv} for lv in (0, 1, 2, 3, 4, 10)]
    )


# =============================================================================
# Constant
# =============================================================================

#: GetUserItemApi of itemKind Pick a value(Corresponding Net.VO.Mai2/ItemKind.cs)
#: Client at StateUserDownload.cs inDownloadthis kind
ITEM_KINDS: tuple = (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 14)

#: ★ GetUserItemApi first nextIndex ofnumber.
#:   Basis source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserItem.cs:17-24
#:        Create(GetNetQuery(userId, itemId * 10000000000L));
#:   Passing on 0 will be rejected by the server.real machinelog source/2026-10-05.log:32 Also 10000000000.
ITEM_NEXT_INDEX_FACTOR: int = 10000000000

#: GetUserFavoriteApi of itemKind(real machineorder 3/1/2/10/11,text source/2026-10-05.log:59-68)
FAVORITE_ITEM_KINDS: tuple = (3, 1, 2, 10, 11)

#: GetUserRivalMusicApi of level fileBit(real machine source/2026-10-05.log:101)
RIVAL_MUSIC_LEVELS: tuple = (0, 1, 2, 3, 4, 10)


# =============================================================================
# Internal Tools
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
    Send a request,returns**Raw Response dict**(Don't VO Keep all server-side fields).

    ★ Counting scripts always go here:upsertUserAll needResponse original
      text dataclass Will lose the fields given by the server.
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
    auto-pagingfetchitemListinterfaceofAllitem

    Paging conventions(Each Packet of Proc inallisthisPiece):
        nextIndex == 0  -> nonedata
        nextIndex != 0  -> Start index of next page

    Parameter:
        api_name:      interfaceFirst name
        list_key:      The key name of the payload list in the response(As "userMapList")
        body_factory:  Optional;receive next_index returnsrequest VO of
                       ★ firstMeetingsin next_index=None calluse —— this isfor
                         GetUserItemApi this"firsthairmustBeltvalue"ofinterface
                         (firstPackage nextIndex = itemKind * 1e10,Can't be 0).
        max_pages:     Up()

    Returns:
        All merged entries
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
            api_name + " number " + str(page + 1) + " text " + str(len(items))
            + " item,count " + str(len(all_items)) + " item,nextIndex=" + str(next_index)
        )
        if not next_index:
            break
    else:
        log_warning(api_name + " text " + str(max_pages) + " notPage flip aborted")

    return all_items
