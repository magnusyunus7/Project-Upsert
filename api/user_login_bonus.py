# -*- coding: utf-8 -*-
"""
user_login_bonus.py —— 取用户登录奖励（GetUserLoginBonusApi）
================================================================================

取玩家的登录奖励领取进度（真机 38 条，分两页）。

对应接口：GetUserLoginBonusApi
请求体  ：UserLoginBonusRequestVO（userId + nextIndex + maxCount=20）
响应    ：{userId, length, nextIndex, userLoginBonusList:[{bonusId,point,isCurrent,isComplete}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserLoginBonusRequestVO.cs

★ 回传 Upsert 时只回传 isCurrent=true 的那一条（本次签到的那条）。

调用示例：
    from api import UserLoginBonus, UserLoginBonusAll
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserLoginBonusRequestVO, fetch_all_pages


def UserLoginBonus(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户登录奖励（单页，对应 GetUserLoginBonusApi）。

    参数：
        next_index: 分页起始索引（0 = 首页）

    返回：
        原始响应 dict，含 userLoginBonusList
    """
    log_info("取用户登录奖励：user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserLoginBonusApi",
        UserLoginBonusRequestVO(userId=user_id, nextIndex=next_index, maxCount=20),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def UserLoginBonusAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户登录奖励（自动翻页取全）。

    返回：
        {"userLoginBonusList": [...]}
    """
    log_info("取用户登录奖励（全量）：user_id=" + str(user_id))
    items = fetch_all_pages(
        "GetUserLoginBonusApi", user_id, "userLoginBonusList",
        body_factory=lambda ni: UserLoginBonusRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=20),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("登录奖励获取完成：" + str(len(items)) + " 条")
    return {"userLoginBonusList": items}
