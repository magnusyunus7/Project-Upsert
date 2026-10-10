# -*- coding: utf-8 -*-
"""
get_user_new_item.py —— Fetch Added Items(GetUserNewItemListApi)
================================================================================

Upload post-checkout inquiry"addedWhich"(real machineResponse userItemList Is Empty).

Corresponding interface:GetUserNewItemListApi
request body  :UserNewItemListRequestVO(userId + version + userData[] + userPlaylogList[])
Response:{userId, userItemList:[...]}
Basis    :source/Assembly-CSharp/Net.VO.Mai2/UserNewItemListRequestVO.cs
          source/2026-10-05.log:121  real machinerequestBelt userData And userPlaylogList

★ this is**settlementAfter**onlycallofinterface,used fortimescheckthis gamegetof
★ request bodyinof userData / userPlaylogList needPassing on,Content vs. UpsertUserAll Match.

Example:
    from api import GetUserNewItemList
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLAY_VERSION_INT, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class UserNewItemListRequestVO:
    """request VO(Corresponding UserNewItemListRequestVO)."""
    userId: int
    version: int = PLAY_VERSION_INT
    userData: List[Any] = field(default_factory=list)
    userPlaylogList: List[Any] = field(default_factory=list)


def GetUserNewItemList(
    user_id: int,
    *,
    version: int = PLAY_VERSION_INT,
    user_data: Optional[List[Any]] = None,
    user_playlog_list: Optional[List[Any]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    Take the new items added this time(Corresponding GetUserNewItemListApi).

    ★ this is**settlementofFront connector**,real machineat UpsertUserAll Before about 8 secondscalluse
      (source/2026-10-05-new.log: 19:22:53 -> 19:23:02).

    ★★ Incoming user_data Must be**playAfter**offileNot the old value at login.
       real machineEmpirical(source/2026-10-05-new.log oftherequest):
           userData[0].playCount = 1258   (logintimeis 1258,this gameAfter 1259)
           userData[0].point     = 4460   (logintimeis 4110,this gameAfter 4460)
           userData[0].lastPlayDate = "2026-10-05 19:22:53.0"
       i.e.:**And UpsertUserAll inof userData Exact match**.
       So the correct usage is to run the local calculus first.,Then take the arithmetic after userData Incoming.

    Parameter:
        user_id:          user ID(Required)
        version:          ROM number(defaultTake config.PLAY_VERSION_INT)
        user_data:        filenumbergroup(Passing on [playAfterof userData])
        user_playlog_list: this gameResultsnumbergroup(Passing on [playlog])

    Returns:
        Raw Response dict,Contains userItemList
    """
    log_info("Fetch Added Items:user_id=" + str(user_id) + " version=" + str(version))
    return request_dict(
        "GetUserNewItemListApi",
        UserNewItemListRequestVO(
            userId=user_id, version=version,
            userData=list(user_data or []),
            userPlaylogList=list(user_playlog_list or []),
        ),
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
