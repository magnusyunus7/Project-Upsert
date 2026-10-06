# -*- coding: utf-8 -*-
"""
user_kaleidx_scope.py —— 取 KALEIDX 门进度（GetUserKaleidxScopeApi / GetGameKaleidxScopeApi）
================================================================================

对应接口：
    GetUserKaleidxScopeApi  请求体 UserIdRequestVO（userId）
                            响应   {userId, userKaleidxScopeList:[...]}
    GetGameKaleidxScopeApi  请求体 **空对象 {}**（GameKaleidxScopeRequestVO 没有任何字段）
                            响应   {gameKaleidxScopeList:[{gateId, phaseId}]}
依据：
    source/Assembly-CSharp/Net.VO.Mai2/UserKaleidxScopeRequestVO.cs
    source/Assembly-CSharp/Net.VO.Mai2/GameKaleidxScopeRequestVO.cs（空类）
    source/Assembly-CSharp/Net.VO.Mai2/GameKaleidxScopeResponseVO.cs
    source/2026-10-05.log:15,119

★★ 重要区分（曾导致 userData 取空）
--------------------------------------------------------------------------------
GameKaleidxScopeResponseVO 里**只有** gameKaleidxScopeList 字段，没有 userData。
玩家档案 userData 的正确来源是 GetUserDataApi（见 userdata.py）。

真机日志里「GetGameKaleidxScope 的响应带 userData」是抓包工具把时间相邻的
两条响应合并显示造成的假象 —— 不要据此给 GetGameKaleidxScopeApi 发 userId，
多发字段会让服务端返回空内容。

调用示例：
    from api import UserKaleidxScope, GameKaleidxScope
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, EmptyRequestVO, UserIdRequestVO


def UserKaleidxScope(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取玩家 KALEIDX 门进度（对应 GetUserKaleidxScopeApi）。

    返回：
        原始响应 dict，含 userKaleidxScopeList
    """
    log_info("取玩家 KALEIDX 门进度：user_id=" + str(user_id))
    return _get("GetUserKaleidxScopeApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)


def GameKaleidxScope(
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取全服 KALEIDX 门开放进度（对应 GetGameKaleidxScopeApi）。

    ★ 请求体是空对象 {} —— 该 RequestVO 一个字段都没有，**不要传 userId**。

    返回：
        原始响应 dict，含 gameKaleidxScopeList
    """
    log_info("取全服 KALEIDX 门进度")
    return _get("GetGameKaleidxScopeApi", EmptyRequestVO(), 0,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
