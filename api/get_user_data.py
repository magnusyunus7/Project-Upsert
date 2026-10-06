# -*- coding: utf-8 -*-
"""
get_user_data.py —— 取用户全量数据（GetUserDataApi）
================================================================================

取玩家档案（86 个字段的大对象），是 upsertUserAll.userData 的**唯一正确来源**。

对应接口：GetUserDataApi
请求体  ：UserIdRequestVO（只有 userId）
响应    ：{userId, userData:{86 键}, banState}
依据    ：source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserData.cs:17
          source/Assembly-CSharp/Net.VO.Mai2/UserDetailResponseVO.cs

    ★ banState 在 Get 侧是**顶层**字段（UserDetailResponseVO.cs:15），
      回传 Upsert 时要搬进 userData 内部（真机 source/2026-10-05.log:123 的 userData 里有 banState）。

    ⚠ 常见误区：有资料认为 userData 由 GetGameKaleidxScopeApi 下发。
      但 GameKaleidxScopeResponseVO.cs 里只有 gameKaleidxScopeList 字段，根本没有 userData。
      真机日志里那一次「GetGameKaleidxScope 的响应带 userData」，是抓包工具按时间相邻
      记录造成的假象（两条响应被合并显示）。

调用示例：
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
    取用户全量数据（对应 GetUserDataApi）。

    参数：
        user_id:    用户 ID（必填）
        client_id:  机台短值（可选）
        timeout_ms: 超时毫秒（可选）
        client:     可复用的 MaimaiNetClient（可选）

    返回：
        原始响应 dict：{"userId":.., "userData":{..}, "banState":..}
    """
    log_info("取用户全量数据：user_id=" + str(user_id))
    return _get("GetUserDataApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
