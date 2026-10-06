# -*- coding: utf-8 -*-
"""
get_user_option.py —— 取用户游戏设置（GetUserOptionApi）
================================================================================

取玩家的音符速度、判定显示、音量等游戏内设置（48 个字段）。

对应接口：GetUserOptionApi
请求体  ：UserIdRequestVO
响应    ：userOption 的字段直接平铺在响应顶层
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserOptionRequestVO.cs

    ★ 形态提醒：Get 侧响应是**平铺**的（顶层直接就是 optionKind/noteSpeed/...），
      而回传 Upsert 时要包成单元素数组 userOption:[{...}]。
      裁剪时要丢掉 tempoVolume（真机 Upsert 报文里没有这个字段）。

调用示例：
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
    取用户游戏设置（对应 GetUserOptionApi）。

    返回：
        原始响应 dict，设置字段平铺在顶层
    """
    log_info("取用户游戏设置：user_id=" + str(user_id))
    return _get("GetUserOptionApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
