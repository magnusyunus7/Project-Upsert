# -*- coding: utf-8 -*-
"""
get_user_option. py — Fetch User Game Settings (GetUserOptionApi)
================================================================================

Take player's note speed, Decision Display, etc. (48 fields).

Corresponding interface: GetUserOptionApi
request body: UserIdRequestVO
Response: userOption of Field directly Tile at Response top-level
Basis: source/Assembly-CSharp/Net. VO. Mai2/UserOptionRequestVO. cs

  - Form Alerts: Get The side response is **Tile** of (top-level directly is optionKind/noteSpeed/...),
   andCallback Upsert timemustPackageArray of elements userOption:[{...}].
   time must Discard tempoVolume (real machine Upsert in the packet none this fields).

Example:
  from api import GetUserOption
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserOption(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
  Fetch User Game Settings (Corresponding GetUserOptionApi).

  Returns:
    Raw Response dict, field Tile at top-level.
  """
    log_info("Fetch User Game Settings: user_id=" + str(user_id))
    return _get("GetUserOptionApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
