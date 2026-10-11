# -*- coding: utf-8 -*-
"""
get_user_region. py — Fetch user area play statistics (GetUserRegionApi)
================================================================================

Take the number of times players play in each region.

Corresponding interface: GetUserRegionApi
request body: UserIdRequestVO
Response:{userId, length, userRegionList:[{regionId, playCount, created}]}
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserRegionRequestVO. cs
     source/2026-10-05. log:77

Example:
  from api import GetUserRegion
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserRegion(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch user area play statistics (Corresponding GetUserRegionApi).

  Returns:
    Raw Response dict, Contains userRegionList.
  """
    log_info("Fetch user area statistics: user_id=" + str(user_id))
    return _get("GetUserRegionApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
