# -*- coding: utf-8 -*-
"""
get_user_course.py —— 取用户课题模式成绩（GetUserCourseApi）
================================================================================

取玩家的 COURSE（课题）模式通关记录（真机 16 条）。

对应接口：GetUserCourseApi
请求体  ：UserCourseRequestVO（userId + nextIndex，**没有 maxCount**）
响应    ：{userId, length, nextIndex, userCourseList:[...]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserCourseRequestVO.cs
          source/2026-10-05.log:55  请求体就是 {"userId":..,"nextIndex":0}

调用示例：
    from api import GetUserCourse
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserCourseRequestVO, get_all_pages


def GetUserCourse(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户课题模式成绩（单页，对应 GetUserCourseApi）。

    返回：
        原始响应 dict，含 userCourseList
    """
    log_info("取用户课题成绩：user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserCourseApi",
        UserCourseRequestVO(userId=user_id, nextIndex=next_index),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserCourseAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户课题成绩（自动翻页取全）。

    返回：
        {"userCourseList": [...]}
    """
    log_info("取用户课题成绩（全量）：user_id=" + str(user_id))
    items = get_all_pages(
        "GetUserCourseApi", user_id, "userCourseList",
        body_factory=lambda ni: UserCourseRequestVO(userId=user_id, nextIndex=ni or 0),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("课题成绩获取完成：" + str(len(items)) + " 条")
    return {"userCourseList": items}
