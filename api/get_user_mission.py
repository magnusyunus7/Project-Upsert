# -*- coding: utf-8 -*-
"""
get_user_mission.py —— 取用户任务与周数据（GetUserMissionDataApi）
================================================================================

取玩家的任务进度与周常数据（真机 6 条任务）。

对应接口：GetUserMissionDataApi
请求体  ：UserIdRequestVO
响应    ：{userId, userWeeklyData:{...}, userMissionDataList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserMissionRequestVO.cs

★ 一个接口同时下发两个 Upsert 节点：
    userMissionDataList  任务列表
    userWeeklyData       周常数据（★ 是**对象**不是数组）
★ 两者回传 Upsert 时都要丢掉各自的 userId 字段。

调用示例：
    from api import GetUserMissionData
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserIdRequestVO


def GetUserMissionData(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户任务与周数据（对应 GetUserMissionDataApi）。

    返回：
        原始响应 dict：{"userId":.., "userWeeklyData":{..}, "userMissionDataList":[..]}
    """
    log_info("取用户任务与周数据：user_id=" + str(user_id))
    return _get("GetUserMissionDataApi", UserIdRequestVO(userId=user_id), user_id,
                client_id=client_id, timeout_ms=timeout_ms, client=client)
