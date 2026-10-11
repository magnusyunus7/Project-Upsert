# -*- coding: utf-8 -*-
"""
get_user_new_item. py — Fetch Added Items (GetUserNewItemListApi)
================================================================================

Upload post-checkout inquiry "added Which" (real machine Response userItemList Is Empty).

Corresponding interface: GetUserNewItemListApi
request body: UserNewItemListRequestVO(userId + version + userData[] + userPlaylogList[])
Response:{userId, userItemList:[...]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserNewItemListRequestVO. cs
     source/2026-10-05. log:121 real machine request Belt userData And userPlaylogList

- this is **settlement After** only call of interface, used for times check this game get of
- request body in of userData / userPlaylogList need Passing on, Content vs. UpsertUserAll Match.

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
    """request VO (Corresponding UserNewItemListRequestVO)."""
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
  Take the new items added this time (Corresponding GetUserNewItemListApi).

  - this is **settlement of Front connector**, real machine at UpsertUserAll Before about 8 seconds call use
   (source/2026-10-05-new. log: 19:22:53 -> 19:23:02).

  -- Incoming user_data Must be **play After** of file Not the old value at login.
    real machine Empirical (source/2026-10-05-new. log of the request):
      userData[0]. playCount = 1258  (logintimeis 1258, this gameAfter 1259)
      userData[0]. point   = 4460  (logintimeis 4110, this gameAfter 4460)
      userData[0]. lastPlayDate = "2026-10-05 19:22:53.0"
    i. e.: **And UpsertUserAll in of userData Exact match**.
    So the correct usage is to run the local calculus first., Then take the arithmetic after userData Incoming.

  Parameter:
    user_id:     user ID(Required)
    version:     ROM number(defaultTake config. PLAY_VERSION_INT)
    user_data:    filenumbergroup(Passing on [playAfterof userData])
    user_playlog_list: this gameResultsnumbergroup(Passing on [playlog])

  Returns:
    Raw Response dict, Contains userItemList.
  """
    log_info("Fetch Added Items: user_id=" + str(user_id) + " version=" + str(version))
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
