# -*- coding: utf-8 -*-
"""
get_user_data. py — Fetch full user data (GetUserDataApi)
================================================================================

Retrieve Player Profile (86 large objects for fields), is upsertUserAll. userData of **The only correct source**.

Corresponding interface: GetUserDataApi
request body: UserIdRequestVO (Only userId)
Response:{userId, userData:{86 key}, banState}
Basis: source/Assembly-CSharp/Net. Packet. Mai2/PacketGetUserData. cs:17
     source/Assembly-CSharp/Net. VO. Mai2/UserDetailResponseVO. cs

  - banState at Get Side is **top-level** Field (UserDetailResponseVO. cs:15),
   Callback Upsert time must userData Internal (real machine source/2026-10-05. log:123 of userData has banState).

  ⚠ Common Misconceptions: hasfor userData by GetGameKaleidxScopeApi Issue.
   But GameKaleidxScopeResponseVO. cs inOnly gameKaleidxScopeList Field, none userData.
   real-machine loginthatOnce"GetGameKaleidxScope ofResponseBelt userData", ispacketToolspresstimerelated
   recordof(Two responses are merged).

Example:
  from api import GetUserData
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserData(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch full user data (Corresponding GetUserDataApi).

  Parameter:
    user_id:  user ID(Required)
    client_id: machine state short Value (Optional)
    timeout_ms: timeout milliseconds(Optional)
    client:   Reusable MaimaiNetClient(Optional)

  Returns:
    Raw Response dict: {"userId":.., "userData":{..}, "banState":..}
  """
    log_info("Fetch full user data: user_id=" + str(user_id))
    return _get("GetUserDataApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
