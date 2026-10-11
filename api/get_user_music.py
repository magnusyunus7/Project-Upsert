# -*- coding: utf-8 -*-
"""
get_user_music. py — Take user track scores (GetUserMusicApi)
================================================================================

Take an archive of the player's historical results for all tracks (real machine 739 group).

Corresponding interface: GetUserMusicApi
request body: UserMusicRequestVO(userId + nextIndex + maxCount=50)
Response:{userId, nextIndex, userMusicList:[{userMusicDetailList:[...], length}]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserMusicRequestVO. cs
     source/Assembly-CSharp/Net. VO. Mai2/UserMusic. cs(Outer layers are grouped by song)
     source/Assembly-CSharp/Net. VO. Mai2/GetUserMusicDetail. cs(Inner layer by difficulty)

- Response is **Two layers of nesting**: Outer layer per element is a song, Inner layer userMusicDetailList It is.
 press (musicId, level) of Results item Flatten when picking.

- Callback Upsert time Only send back this game of that One item (playCount +1), Remaining immovable.

Example:
  from api import GetUserMusicDetail, UserMusicDetailFlat
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserMusicRequestVO, get_all_pages


def GetUserMusicDetail(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take user track scores (Single Page, Corresponding GetUserMusicApi).

  Parameter:
    next_index: Pagination Start Index(0 = first)

  Returns:
    Raw Response dict, Contains userMusicList (Two layers of nesting).
  """
    log_info("Take user track scores: user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserMusicApi",
        UserMusicRequestVO(userId=user_id, nextIndex=next_index, maxCount=50),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserMusicDetailAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Take user track scores (auto-paging Take Full, Flattened into a single layer).

  Returns:
    {"userMusicList": [ {"musicId":..,"level":..,"playCount":..},... ]}
    each Element is **Single Bar (musicId, level) Results**, Not a nested structure grouped by song.
  """
    log_info("Take user track scores (Full Amount): user_id=" + str(user_id))
    groups = get_all_pages(
        "GetUserMusicApi", user_id, "userMusicList",
        body_factory=lambda ni: UserMusicRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=50),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    flat: List[Dict[str, Any]] = []
    for group in groups:
        if isinstance(group, dict):
            details = group.get("userMusicDetailList") or []
            if isinstance(details, dict):
                details = [details]
            flat.extend(details)
    log_info("track Results fetch complete: " + str(len(flat)) + " item (Original "
             + str(len(groups)) + " group)")
    return {"userMusicList": flat}
