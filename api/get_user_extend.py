# -*- coding: utf-8 -*-
"""
get_user_extend.py —— 取用户扩展设置（GetUserExtendApi）
================================================================================

取玩家上次的选曲 / 分类 / 卡片槽等扩展状态。

对应接口：GetUserExtendApi
请求体  ：UserIdRequestVO
响应    ：{userId, userExtend:{...}}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserExtendRequestVO.cs

    ★ 其中 categoryIndex（曲种索引）与 userPlaylog 的 extNum4 必须一致
      （真机两处都是 2022），组包时要注意。

调用示例：
    from api import GetUserExtend
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserExtend(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户扩展设置（对应 GetUserExtendApi）。

    返回：
        原始响应 dict，含 userExtend 子对象
    """
    log_info("取用户扩展设置：user_id=" + str(user_id))
    return _get("GetUserExtendApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
