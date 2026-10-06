# -*- coding: utf-8 -*-
"""
get_user_new_item.py —— 取新增道具（GetUserNewItemListApi）
================================================================================

上传结算后查询「本次新增了哪些道具」（真机响应 userItemList 为空）。

对应接口：GetUserNewItemListApi
请求体  ：UserNewItemListRequestVO（userId + version + userData[] + userPlaylogList[]）
响应    ：{userId, userItemList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserNewItemListRequestVO.cs
          source/2026-10-05.log:121  真机请求带 userData 与 userPlaylogList

★ 这是**结算之后**才调的接口，用于回查本局获得的新道具。
★ 请求体里的 userData / userPlaylogList 需要传，内容与 UpsertUserAll 一致。

调用示例：
    from api import GetUserNewItemList
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import CLIENT_ID, PLAY_VERSION_INT, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class UserNewItemListRequestVO:
    """请求 VO（对应 UserNewItemListRequestVO）。"""
    userId: int
    version: int = PLAY_VERSION_INT
    userData: List[Any] = field(default_factory=list)
    userPlaylogList: List[Any] = field(default_factory=list)


def GetUserNewItemList(
    user_id: int,
    *,
    version: int = PLAY_VERSION_INT,
    user_data: Optional[List[Any]] = None,
    user_playlog_list: Optional[List[Any]] = None,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取本次新增道具（对应 GetUserNewItemListApi）。

    ★ 这是**结算流程的前置接口**，真机在 UpsertUserAll 之前约 8 秒调用
      （source/2026-10-05-new.log: 19:22:53 -> 19:23:02）。

    ★★ 传入的 user_data 必须是**游玩后**的档案，不是登录时的旧值。
       真机实证（source/2026-10-05-new.log 的该请求）：
           userData[0].playCount = 1258   （登录时是 1258，本局后 1259）
           userData[0].point     = 4460   （登录时是 4110，本局后 4460）
           userData[0].lastPlayDate = "2026-10-05 19:22:53.0"
       即：**与 UpsertUserAll 里的 userData 完全一致**。
       所以正确用法是先把本局演算跑完，再拿演算后的 userData 传进来。

    参数：
        user_id:          用户 ID（必填）
        version:          ROM 版本整数（默认取 config.PLAY_VERSION_INT）
        user_data:        玩家档案数组（通常传 [游玩后的 userData]）
        user_playlog_list: 本局成绩数组（通常传 [playlog]）

    返回：
        原始响应 dict，含 userItemList
    """
    log_info("取新增道具：user_id=" + str(user_id) + " version=" + str(version))
    return request_dict(
        "GetUserNewItemListApi",
        UserNewItemListRequestVO(
            userId=user_id, version=version,
            userData=list(user_data or []),
            userPlaylogList=list(user_playlog_list or []),
        ),
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
