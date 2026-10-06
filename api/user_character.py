# -*- coding: utf-8 -*-
"""
user_character.py —— 取用户角色列表（GetUserCharacterApi）
================================================================================

取玩家所有角色的等级与觉醒度（真机 312 条）。

对应接口：GetUserCharacterApi
请求体  ：UserIdRequestVO
响应    ：{userId, length, userCharacterList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserCharacterRequestVO.cs

    ★ 回传 Upsert 时只保留 characterId / level / awakening / useCount 四个字段
      （真机 source/2026-10-05.log:123 的 userCharacterList 就是这 4 个键）。

调用示例：
    from api import UserCharacter
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def UserCharacter(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户角色列表（对应 GetUserCharacterApi）。

    返回：
        原始响应 dict，含 userCharacterList
    """
    log_info("取用户角色列表：user_id=" + str(user_id))
    return _get("GetUserCharacterApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
