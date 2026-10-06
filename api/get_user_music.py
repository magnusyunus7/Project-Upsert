# -*- coding: utf-8 -*-
"""
get_user_music.py —— 取用户曲目成绩（GetUserMusicApi）
================================================================================

取玩家全部曲目的历史成绩归档（真机 739 组）。

对应接口：GetUserMusicApi
请求体  ：UserMusicRequestVO（userId + nextIndex + maxCount=50）
响应    ：{userId, nextIndex, userMusicList:[{userMusicDetailList:[...], length}]}
依据    ：source/Assembly-CSharp/Net.VO.Mai2/UserMusicRequestVO.cs
          source/Assembly-CSharp/Net.VO.Mai2/UserMusic.cs（外层按曲分组）
          source/Assembly-CSharp/Net.VO.Mai2/GetUserMusicDetail.cs（内层按难度）

★ 响应是**两层嵌套**：外层每元素是一首歌，内层的 userMusicDetailList 才是
  按 (musicId, level) 的成绩条目。取数时要摊平。

★ 回传 Upsert 时只回传本局玩的那一条（playCount +1），其余不动。

调用示例：
    from api import GetUserMusicDetail, UserMusicDetailFlat
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info
from .maimai_net import MaimaiNetClient
from .user_getter_common import _get, UserMusicRequestVO, get_all_pages


def GetUserMusicDetail(
    user_id: int,
    *,
    next_index: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户曲目成绩（单页，对应 GetUserMusicApi）。

    参数：
        next_index: 分页起始索引（0 = 首页）

    返回：
        原始响应 dict，含 userMusicList（两层嵌套）
    """
    log_info("取用户曲目成绩：user_id=" + str(user_id) + " next_index=" + str(next_index))
    return _get(
        "GetUserMusicApi",
        UserMusicRequestVO(userId=user_id, nextIndex=next_index, maxCount=50),
        user_id, client_id=client_id, timeout_ms=timeout_ms, client=client,
    )


def GetUserMusicDetailAll(
    user_id: int,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Dict[str, Any]:
    """
    取用户曲目成绩（自动翻页取全，已摊平成单层）。

    返回：
        {"userMusicList": [ {"musicId":..,"level":..,"playCount":..}, ... ]}
        每元素是**单条 (musicId, level) 成绩**，不是按曲分组的嵌套结构。
    """
    log_info("取用户曲目成绩（全量）：user_id=" + str(user_id))
    groups = get_all_pages(
        "GetUserMusicApi", user_id, "userMusicList",
        body_factory=lambda ni: UserMusicRequestVO(
            userId=user_id, nextIndex=ni or 0, maxCount=50),
        client_id=client_id, timeout_ms=timeout_ms, client=client,
    )
    flat: List[Dict[str, Any]] = []
    for group in groups:
        if isinstance(group, dict):
            details = group.get("userMusicDetailList") or []
            if isinstance(details, dict):
                details = [details]
            flat.extend(details)
    log_info("曲目成绩获取完成：" + str(len(flat)) + " 条（原始 "
             + str(len(groups)) + " 组）")
    return {"userMusicList": flat}
