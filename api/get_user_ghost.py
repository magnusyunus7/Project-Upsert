# -*- coding: utf-8 -*-
"""
get_user_ghost.py —— 取用户幽灵数据（GetUserGhostApi）
================================================================================

取玩家的「幽灵」对战记录（真机 15 条）。

对应接口：GetUserGhostApi
请求体  ：UserIdRequestVO
响应    ：{length, userGhostList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserGhostRequestVO.cs

    ★ Upsert 侧 userGhost 默认留空：源码 VOExtensions.cs:235 是
        dst.userGhost = (!src.MyGhost.NeedSave) ? null : new GetUserGhost[1] {...};
      只有「本局产生了幽灵」才回传，纯网络脚本复刻不出幽灵数据。

调用示例：
    from api import GetUserGhost
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserGhost(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户幽灵数据（对应 GetUserGhostApi）。

    返回：
        原始响应 dict，含 userGhostList
    """
    log_info("取用户幽灵数据：user_id=" + str(user_id))
    return _get("GetUserGhostApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
