# -*- coding: utf-8 -*-
"""
get_user_course.py —— Take the results of the user's topic mode（GetUserCourseApi）
================================================================================

Take Player COURSE（text）modetextOffrecord（real machine 16 item）。

Corresponding interface：GetUserCourseApi
request body  ：UserCourseRequestVO（userId + nextIndex，**none maxCount**）
Response    ：{userId, length, nextIndex, userCourseList:[...]}
Basis    ：source/Assembly-CSharp/Net.VO.Mai2/UserCourseRequestVO.cs
          source/2026-10-05.log:55  request bodyis {"userId":..,"nextIndex":0}

call exampleExample：
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
    Take the results of the user's topic mode（Single Page，Corresponding GetUserCourseApi）。

    returntimes：
        Raw Response dict，Contains userCourseList
    """
    log_info("Take the user's subject score：user_id=" + str(user_id) + " next_index=" + str(next_index))
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
    Take the user's subject score（auto-pagingTakeFull）。

    returntimes：
        {"userCourseList": [...]}
    """
    log_info("Take the user's subject score（Full Amount）：user_id=" + str(user_id))
    items = get_all_pages(
        "GetUserCourseApi", user_id, "userCourseList",
        body_factory=lambda ni: UserCourseRequestVO(userId=user_id, nextIndex=ni or 0),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    log_info("textResultsgetTakeDone：" + str(len(items)) + " item")
    return {"userCourseList": items}
