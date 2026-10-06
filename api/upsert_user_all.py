# -*- coding: utf-8 -*-
"""
upsert_user_all.py —— 上传成绩（UpsertUserAllApi）
================================================================================

功能：把一局游玩的完整结算数据写进服务器。这是**唯一有副作用**的接口。

对应接口：UpsertUserAllApi
请求体  ：UserAllRequestVO（7 个顶层字段 + upsertUserAll 的 36 个节点）
          source/Assembly-CSharp/Net.VO.Mai2/UserAllRequestVO.cs
          source/Assembly-CSharp/Net.Packet.Mai2/PacketUpsertUserAll.cs:22-35

--------------------------------------------------------------------------------
一、顶层结构（7 字段）
--------------------------------------------------------------------------------
    userId          用户 ID
    playlogId       ★ 必须 == UserLoginApi 的 loginId
    isEventMode     是否活动模式
    isFreePlay      是否免费游玩
    loginDateTime   ★ 必须 == UserLoginApi 的 loginDateTime
    userPlaylogList 本局成绩明细（110 字段 × N 条）
    upsertUserAll   36 个节点的全量用户数据

    playlogId / loginDateTime 都不是本接口产生的，它们来自 UserLoginApi。
    发错登录 ID 服务端会直接拒；中途换了登录会话必须重新登录。

--------------------------------------------------------------------------------
二、upsertUserAll 的 36 个节点（4 种形态）
--------------------------------------------------------------------------------
依据 source/Assembly-CSharp/Net.VO.Mai2/UserAll.cs，并用真机报文
source/2026-10-05.log:123 逐节点核对：

    单元素数组  4 个  userData / userExtend / userOption / userRatingList
    对象        2 个  userWeeklyData / user2pPlaylog      ★ 不是数组
    位串       11 个  isNew*                              长度 == 对应数组条数
    普通数组   19 个  其余

    4 + 2 + 11 + 19 = 36

--------------------------------------------------------------------------------
三、★ 本模块的核心思路：快照基线 + 本局演算 + 差分
--------------------------------------------------------------------------------
真机不是把 Get 下来的整表原样回传，而是「只回传变化的那几条」。
把 source/2026-10-05.log 里同一账号的 Get 侧与 Upsert 侧对照：

    | 节点                  | Get 侧（登录时）      | Upsert 侧（结算时）      |
    |-----------------------|----------------------|--------------------------|
    | userData.playCount    | 1257                 | 1258        (+1)         |
    | userData.currentPlay  | 185                  | 186         (+1)         |
    | userMusicDetailList   | 143/level4 playCount=7 | 143/level4 playCount=8 |
    | userMapList           | 550003 distance=1424000 | distance=1435000 (+11000) |
    | userCharacterList     | 5 只                 | 5 只，每只 level +1      |
    | userItemList          | 1070 条              | []          （无变化）    |
    | userCourseList        | 16 条                | []          （无变化）    |

    ★ 结论：**服务器对 userData 是整表覆盖语义** —— 把 Get 下来的旧值原样发回去，
      写入后「看起来什么都没发生」，这就是「returnCode=1 但没落库」的根因。
      差分节点若为空，服务端也看不出本局有任何变化。

    ⚠ 本工程的默认值与上表（真机）**有意不同**：
      config.PLAY_USER_PLAY_COUNT_GAIN = 0（默认）
        -> userData.playCount / currentPlayCount **保持不变**，不复刻真机的 +1。
        想复刻真机就把它改成 1。
      其它增量同理：PLAY_MUSIC_PLAY_COUNT_GAIN / PLAY_MAP_DISTANCE_GAIN /
      PLAY_CHARACTER_EXP_GAIN 默认都是 0。

所以本模块的流程是：

    1. 从 snapshot（登录后抓的 Get 响应）建立**基线**
    2. 按本局数据（play）演算出**新状态**，并对差分节点算 (新 - 基线)
    3. 用 patch 做精确覆盖
    4. 生成 11 条位串（长度自动对齐对应数组）

--------------------------------------------------------------------------------
四、安全闸门
--------------------------------------------------------------------------------
本接口有副作用，默认**不发包**：

    UpsertUserAll(...)                 -> 抛 ConfirmRequiredError（未发包）
    UpsertUserAll(..., dry_run=True)   -> 只构造并返回报文
    UpsertUserAll(..., confirm=True)   -> 真实发送

全局开关见 config.UPSERT_CONFIRM。

--------------------------------------------------------------------------------
五、调用示例
--------------------------------------------------------------------------------
    from api import (setup_logging, ParseQRCode, GetUserPreview, UserLogin,
                     GetNeedUserData, UpsertUserAll, build_play_from_config)

    setup_logging("结算")
    user_id, token = ParseQRCode(qr)
    GetUserPreview(user_id, token)
    login = UserLogin(user_id, token)

    # 1) 登录后立刻抓基线快照（差分的基准）
    snapshot = GetNeedUserData(user_id, token=token)

    # 2) 组装本局数据（默认读 config.py 的 PLAY_*）
    play = build_play_from_config()

    # 3) 先看报文
    req = UpsertUserAll(user_id, login.loginId,
                        login_date_time=login.loginDateTime,
                        snapshot=snapshot, play=play, dry_run=True)

    # 4) 确认无误后真实上传
    UpsertUserAll(user_id, login.loginId,
                  login_date_time=login.loginDateTime,
                  snapshot=snapshot, play=play, confirm=True)
"""

from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import config
from config import (
    CLIENT_ID,
    PLACE_ID,
    PLACE_NAME,
    REGION_ID,
    PLAY_SPECIAL_NUM,
    REGION_NAME,
    TIMEOUT_LONG_MS,
    UPSERT_CONFIRM,
    UPSERT_SEND_COOLDOWN_SEC,
)

from .log_setup import log_debug, log_error, log_info, log_warning
from .maimai_net import (
    MaimaiNetClient,
    local_utc_offset_seconds,
    login_date_time_now,
    request_dict,
)


# =============================================================================
# 异常
# =============================================================================

class UpsertUserAllError(RuntimeError):
    """服务端返回 returnCode != 1。"""


class ConfirmRequiredError(RuntimeError):
    """有副作用的接口被安全闸门拦下（此时**未发包**）。"""


class PatchError(ValueError):
    """节点名或节点形态不合法。"""


# =============================================================================
# 一、36 个节点的类型表
# =============================================================================
#
#   "singleton" : 数组，恒 1 元素（userData / userExtend / userOption / userRatingList）
#   "object"    : ★ 单个对象，不是数组（userWeeklyData / user2pPlaylog）
#   "array"     : 普通数组
#   "bits"      : 字符串位串，长度 == 对应数组条数
#
NODE_TYPES: Dict[str, str] = {
    # ---- 单元素数组（4）----
    "userData": "singleton",
    "userExtend": "singleton",
    "userOption": "singleton",
    "userRatingList": "singleton",
    # ---- 对象，非数组（2）★ ----
    "userWeeklyData": "object",
    "user2pPlaylog": "object",
    # ---- 普通数组（19）----
    "userCharacterList": "array",
    "userGhost": "array",
    "userMapList": "array",
    "userLoginBonusList": "array",
    "userItemList": "array",
    "userMusicDetailList": "array",
    "userCourseList": "array",
    "userFriendSeasonRankingList": "array",
    "userChargeList": "array",
    "userFavoriteList": "array",
    "userActivityList": "array",
    "userMissionDataList": "array",
    "userGamePlaylogList": "array",
    "userIntimateList": "array",
    "userShopItemStockList": "array",
    "userGetPointList": "array",
    "userTradeItemList": "array",
    "userFavoritemusicList": "array",
    "userKaleidxScopeList": "array",
    # ---- 位串（11）----
    "isNewCharacterList": "bits",
    "isNewMapList": "bits",
    "isNewLoginBonusList": "bits",
    "isNewItemList": "bits",
    "isNewMusicDetailList": "bits",
    "isNewCourseList": "bits",
    "isNewFavoriteList": "bits",
    "isNewFriendSeasonRankingList": "bits",
    "isNewUserIntimateList": "bits",
    "isNewFavoritemusicList": "bits",
    "isNewKaleidxScopeList": "bits",
}

#: 位串 -> 对应数组（依据 UserAll.cs 的字段命名与真机报文核对）
BITS_TO_ARRAY: Dict[str, str] = {
    "isNewCharacterList": "userCharacterList",
    "isNewMapList": "userMapList",
    "isNewLoginBonusList": "userLoginBonusList",
    "isNewItemList": "userItemList",
    "isNewMusicDetailList": "userMusicDetailList",
    "isNewCourseList": "userCourseList",
    "isNewFavoriteList": "userFavoriteList",
    "isNewFriendSeasonRankingList": "userFriendSeasonRankingList",
    "isNewUserIntimateList": "userIntimateList",
    "isNewFavoritemusicList": "userFavoritemusicList",
    "isNewKaleidxScopeList": "userKaleidxScopeList",
}

ARRAY_TO_BITS: Dict[str, str] = {v: k for k, v in BITS_TO_ARRAY.items()}

#: 节点在报文里的顺序（照 UserAll.cs 的字段声明顺序）
NODE_ORDER: Tuple[str, ...] = (
    "userData", "userExtend", "userOption", "userCharacterList", "userGhost",
    "userMapList", "userLoginBonusList", "userRatingList", "userItemList",
    "userMusicDetailList", "userCourseList", "userFriendSeasonRankingList",
    "userChargeList", "userFavoriteList", "userActivityList", "userMissionDataList",
    "userWeeklyData", "userGamePlaylogList", "user2pPlaylog", "userIntimateList",
    "userShopItemStockList", "userGetPointList", "userTradeItemList",
    "userFavoritemusicList", "userKaleidxScopeList",
    "isNewCharacterList", "isNewMapList", "isNewLoginBonusList", "isNewItemList",
    "isNewMusicDetailList", "isNewCourseList", "isNewFavoriteList",
    "isNewFriendSeasonRankingList", "isNewUserIntimateList",
    "isNewFavoritemusicList", "isNewKaleidxScopeList",
)

#: 需要算差分的节点 -> 主键字段（用于生成位串的 "0"/"1"）
#:
#: ★ 判断依据 = 真机 Get 侧与 Upsert 侧的条数对照（source/2026-10-05.log）：
#:
#:     | 节点                | Get 侧 | Upsert 侧 | 是否差分 |
#:     |---------------------|--------|-----------|----------|
#:     | userCharacterList   | 312    | 5         | 是       |
#:     | userMapList         | 104    | 1         | 是       |
#:     | userMusicDetailList | 739    | 1         | 是       |
#:     | userLoginBonusList  | 38     | 0         | 是       |
#:     | userCourseList      | 16     | 0         | 是       |
#:     | userItemList        | 1070   | 0         | 是       |
#:     | userIntimateList    | 2      | 0         | 是       |
#:     | userChargeList      | 3      | **3**     | ★ 否！整表回传 |
#:
#: userChargeList 是**整表回传**（真机原样发了 3 条），不能当差分处理，
#: 否则会被误收敛成空数组。
DIFF_PRIMARY_KEYS: Dict[str, Tuple[str, ...]] = {
    "userCharacterList": ("characterId",),
    "userMapList": ("mapId",),
    "userLoginBonusList": ("bonusId",),   # 本次签到那条 -> 位串 "1"
    "userItemList": ("itemKind", "itemId"),
    "userMusicDetailList": ("musicId", "level"),
    "userCourseList": ("courseId",),
    "userFriendSeasonRankingList": ("seasonId",),
    "userIntimateList": ("partnerId",),
    "userKaleidxScopeList": ("gateId",),
    "userShopItemStockList": ("shopItemId",),
    "userFavoritemusicList": ("musicId",),
}

#: 整表回传、不做差分的节点（真机原样发出全部条目）
FULL_TABLE_NODES: Tuple[str, ...] = (
    "userChargeList",
)

#: 无变化时可以留空的节点
#:   依据：真机报文 source/2026-10-05.log:123 里 userItemList / userCourseList /
#:        userKaleidxScopeList / userIntimateList / userShopItemStockList /
#:        userTradeItemList / userFriendSeasonRankingList / userFavoritemusicList /
#:        userGhost / userLoginBonusList / userGetPointList 全是 []，
#:        服务端照样返回 returnCode=1 —— 空数组是被接受的。
MAY_BE_EMPTY_NODES: Tuple[str, ...] = (
    "userGhost", "userMapList", "userLoginBonusList", "userItemList",
    "userMusicDetailList", "userCourseList", "userFriendSeasonRankingList",
    "userChargeList", "userActivityList", "userMissionDataList",
    "userIntimateList", "userShopItemStockList", "userGetPointList",
    "userTradeItemList", "userFavoritemusicList", "userKaleidxScopeList",
    "userCharacterList", "userRatingList",
)

#: 默认恒空的节点（本局不产生的数据）
#:
#: ★ userGetPointList 与 userLoginBonusList 都在此列 —— 这两个节点是
#:   **登录奖励发放**才会产生的，普通游玩结算不需要回传：
#:
#:   - userGetPointList（里程/点数明细）
#:     真机 39 次 UpsertUserAll 样本里 **25 次为空（64%）**，
#:     只有发生登录奖励/任务奖励时才非空（如 getKind=1 point=200）。
#:     留空 => 服务端不累加 point，账户点数保持不变。
#:
#:   - userLoginBonusList（签到奖励）
#:     同理，只有本次登录触发了新签到才回传那一条（isCurrent=true）。
#:     留空 => isNewLoginBonusList 也是空串。
#:
#:   ★ 连带影响（正常现象）：留空后 userData.point 的增量就无从解释，
#:     所以 point 保持基线值不变。这是「不发放点数」的必然结果。
DEFAULT_EMPTY_NODES: Tuple[str, ...] = (
    "userGhost",            # 源码 VOExtensions.cs:235 只在 NeedSave 时回传
    "userGetPointList",     # 登录奖励才产生；普通结算留空
    "userLoginBonusList",   # 登录奖励才产生；普通结算留空
    "userTradeItemList",    # 无 Get 来源
    "userFriendSeasonRankingList",   # 无 Get 来源
    "userFavoritemusicList",         # 源码是条件回传，真机恒 []
)


# =============================================================================
# 二、字段裁剪表（Get 侧 -> Upsert 侧要丢掉的字段）
# =============================================================================
#
# 依据：把真机 Get 侧响应与 Upsert 侧报文逐字段比对得出。

#: userData：Get 侧有、Upsert 侧没有的字段
USER_DATA_DROP_KEYS: Tuple[str, ...] = (
    "friendCode", "nameplateId", "trophyId",
    "cmLastEmoneyCredit", "cmLastEmoneyBrand",
)

#: userOption：Upsert 侧没有 tempoVolume
USER_OPTION_DROP_KEYS: Tuple[str, ...] = ("tempoVolume",)

#: userExtend：Upsert 侧**多出**这两个字段（Get 侧没有），必须补上
#:   真机 Upsert 侧 16 键 vs Get 侧 14 键，差的就是这两个
USER_EXTEND_EXTRA_KEYS: Tuple[str, ...] = ("isPhotoAgree", "isGotoCodeRead")

#: ★ userRating.udemae：服务端 Get 响应里有一批**首字母大写的重复字段**
#:   （source/2026-10-05.log:87 的 Get 响应里 npcWinNum 与 NpcWinNum 并存，共 23 键），
#:   但真机 Upsert 报文里**只有小写的 16 键**（source/2026-10-05.log:123）。
#:   源码 Net.VO.Mai2/UserUdemae.cs 只声明了小写的 16 个字段，
#:   所以这批大写字段是服务端的冗余输出，回传时必须裁掉 —— 否则：
#:     ① 报文里出现源码不存在的字段
#:     ② 请求体比真机大 119 字节
USER_RATING_UDEMAE_DROP_KEYS: Tuple[str, ...] = (
    "MaxLoseNum", "NpcTotalWinNum", "NpcTotalLoseNum",
    "NpcMaxWinNum", "NpcMaxLoseNum", "NpcWinNum", "NpcLoseNum",
)

#: userCharacterList：只保留这 4 个字段
USER_CHARACTER_KEEP_KEYS: Tuple[str, ...] = (
    "characterId", "level", "awakening", "useCount",
)

#: userMusicDetailList：丢掉 extNum2
USER_MUSIC_DETAIL_DROP_KEYS: Tuple[str, ...] = ("extNum2",)

#: userChargeList：丢掉 extNum1
USER_CHARGE_DROP_KEYS: Tuple[str, ...] = ("extNum1",)

#: userMissionDataList / userWeeklyData：丢掉 userId
USER_MISSION_DROP_KEYS: Tuple[str, ...] = ("userId",)


# =============================================================================
# 三、基础工具
# =============================================================================

def _strip_keys(item: Any, drop: Sequence[str]) -> Any:
    """从 dict 里删掉指定字段（返回新 dict）。"""
    if not isinstance(item, dict):
        return item
    return {k: v for k, v in item.items() if k not in drop}


def _keep_keys(item: Any, keep: Sequence[str]) -> Any:
    """只保留指定字段（返回新 dict）。"""
    if not isinstance(item, dict):
        return item
    return {k: v for k, v in item.items() if k in keep}


def empty_node(node: str) -> Any:
    """按节点类型返回空值。"""
    kind = NODE_TYPES.get(node)
    if kind == "bits":
        return ""
    if kind == "object":
        return {}
    return []


def empty_user_all() -> Dict[str, Any]:
    """构造全空的 36 节点骨架。"""
    return {node: empty_node(node) for node in NODE_ORDER}


def coerce_node_value(node: str, value: Any) -> Any:
    """
    把值强制成该节点应有的形态；传错直接抛 PatchError。

    ★ 这是刻意的防呆：userWeeklyData / user2pPlaylog 传数组、
      userData 传 dict，都是很容易犯又很难查的错。
    """
    kind = NODE_TYPES.get(node)
    if kind is None:
        raise PatchError("未知节点名：" + str(node))

    if value is None:
        return empty_node(node)

    if kind == "bits":
        if not isinstance(value, str):
            raise PatchError("节点 " + node + " 是位串，必须传 str，收到 " + type(value).__name__)
        return value

    if kind == "object":
        if not isinstance(value, dict):
            raise PatchError("节点 " + node + " 是对象（不是数组），必须传 dict，收到 "
                             + type(value).__name__)
        return value

    if kind == "singleton":
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return value
        raise PatchError("节点 " + node + " 必须是 dict 或 list，收到 " + type(value).__name__)

    # array
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    raise PatchError("节点 " + node + " 必须是 list，收到 " + type(value).__name__)


def sync_bits_to_arrays(user_all: Dict[str, Any]) -> None:
    """
    位串长度与对应数组条数不一致时，按 "0" 补齐/截断（就地修改）。

    ★ 长度不符服务端会误判「哪些是新增」。
    """
    for bits, arr in BITS_TO_ARRAY.items():
        items = user_all.get(arr)
        if not isinstance(items, list):
            continue
        want = len(items)
        cur = user_all.get(bits)
        if not isinstance(cur, str):
            cur = ""
        if len(cur) != want:
            # 已有多余字符时截断；不足时补 "0"
            user_all[bits] = (cur + "0" * want)[:want] if cur else "0" * want


# =============================================================================
# 四、差分
# =============================================================================

def _norm(item: Any) -> str:
    """把一条记录规范化成可比较的字符串。"""
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)


def _primary_key(item: Any, keys: Sequence[str]) -> Tuple:
    """取主键值。"""
    if not isinstance(item, dict):
        return (str(item),)
    return tuple(item.get(k) for k in keys)


def build_delta(
    local: Sequence[Any],
    server: Sequence[Any],
    compare_keys: Optional[Sequence[str]] = None,
) -> Tuple[List[Any], str]:
    """
    复刻 VOExtensions.BuildListData 的差分语义。

    规则（source/Assembly-CSharp/Net.VO.Mai2/VOExtensions.cs:309-324）：
        1. 逐字段比较：本地这条与服务器**任何**一条都不完全相同 -> 算「变化」，要回传
           （源码是 nsrc.Except(osrc)，退化成全字段比较）
        2. compare_keys 只用于**算位串**，不参与剔除
        3. 位串："0" = 主键在服务器已存在（更新）；"1" = 全新（新增）

    参数：
        local:        本地新状态（游玩后应有的值）
        server:       服务器旧快照（差分基线）
        compare_keys: 主键字段名（用于生成位串）

    返回：
        (要回传的条目列表, 位串)
    """
    server_norm = {_norm(s) for s in server}
    server_keys = set()
    if compare_keys:
        server_keys = {_primary_key(s, compare_keys) for s in server}

    delta: List[Any] = []
    flags: List[str] = []
    for item in local:
        if _norm(item) in server_norm:
            continue                      # 与服务器某条完全一致 -> 无变化
        delta.append(item)
        if compare_keys:
            flags.append("0" if _primary_key(item, compare_keys) in server_keys else "1")
        else:
            flags.append("1")
    return delta, "".join(flags)


def build_favorite_delta(
    local: Sequence[Any],
    server: Sequence[Any],
    assume_missing: Sequence[int] = (),
) -> Tuple[List[Any], str]:
    """
    收藏夹专用差分（复刻 VOExtensions.cs:345-367）。

    ★ 与普通差分不同：**不做剔除，恒返回完整条目**（真机是 5 条）。

    位串规则（按真机 source/2026-10-05.log:123 的 "22212" 反推）：
        "2" = 服务器侧有对应 itemKind（无论内容是否一致）
        "1" = 服务器侧查不到该 itemKind

    ★ 关键：**优先用 Get 侧最原始的响应建索引**，不要先用 get_user_favorite.py
      的「补 itemKind」逻辑归一化 —— 真机里 itemKind=10 的响应回的是
      {"itemKind":null, "itemIdList":[]}，正因为查不到才自然产生 "1"。

    参数：
        local:          本地收藏列表（已补 itemKind，5 条）
        server:         服务器收藏列表。传**原始** Get 响应时 itemKind=null
                        的那条会自然产生 "1"（不需要 assume_missing）。
        assume_missing: 「服务端恒回 null」的 itemKind 集合。
                        ★ 仅当 server 是**被归一化过**的列表
                          （itemKind 已被补齐、看不出原始 null）时才需要传，
                          否则会把本该是 "1" 的那位算成 "2"。
                          调用方在拿不到原始响应时传 FAVORITE_MISSING_KINDS，
                          拿得到原始响应时就别传。
    """
    server_kinds = set()
    for s in server:
        if isinstance(s, dict):
            server_kinds.add(s.get("itemKind"))
    missing = set(assume_missing)

    out: List[Any] = []
    flags: List[str] = []
    for item in local:
        out.append(item)
        kind = item.get("itemKind") if isinstance(item, dict) else None
        # "1" 的条件（任一成立）：
        #   a) 服务器侧确实没有该 itemKind（原始响应里是 null）
        #   b) 该 kind 在 assume_missing 里（基线被归一化过，看不出原始 null）
        if kind in server_kinds and kind not in missing:
            flags.append("2")
        else:
            flags.append("1")
    return out, "".join(flags)


# =============================================================================
# 五、时间格式化
# =============================================================================

def _local_wall_string(login_date_time: int) -> str:
    """
    把 loginDateTime 渲染成真机那种 "YYYY-MM-DD HH:MM:SS.0" 字符串。

    ★ loginDateTime 的语义是「本地墙上时间被当作 UTC 时刻」，
      所以要用 utcfromtimestamp 还原出墙上时间，而不是 fromtimestamp。
      真机 userData.lastLoginDate = "2026-10-05 00:19:37.0"
      对应 loginDateTime = 1791159576。
    """
    try:
        dt = datetime.fromtimestamp(int(login_date_time), tz=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.0")


#: CST 偏移（source/Assembly-CSharp/Manager/TimeManager.cs:9  CSToffset = 8 小时）
CST_OFFSET_SECONDS = 8 * 3600

#: 游玩日志日的分界小时（source/Assembly-CSharp/Manager/TimeManager.cs:77-85
#:   ToLogDateTime：小时 < 7 时把日期回退一天）
LOG_DAY_CUTOFF_HOUR = 7


def _local_date_string(login_date_time: int) -> str:
    """
    渲染成 "YYYY-MM-DD"（对应 TimeManager.GetLogDateString）。

    ★ 游玩日志日不是自然日：source/Assembly-CSharp/Manager/TimeManager.cs:77-85

        public static DateTime ToLogDateTime(DateTime dateTime, int hour = 0)
        {
            DateTime result = new(dateTime.Year, dateTime.Month, dateTime.Day, hour, 0, 0);
            if (7 > dateTime.Hour) return result.AddDays(-1.0);   // 7 点前算前一天
            return result;
        }

    真机佐证（source/2026-10-05.log:123）：
        userPlayDate = "2026-10-05 00:20:30.0"（墙上时间 10-05 00:20）
        playDate     = "2026-10-04"          （00:20 < 07:00 -> 回退到 10-04）
    """
    wall = datetime.fromtimestamp(int(login_date_time), tz=timezone.utc)
    log_day = wall - timedelta(days=1) if wall.hour < LOG_DAY_CUTOFF_HOUR else wall
    return log_day.strftime("%Y-%m-%d")


def _standard_unix(login_date_time: int) -> int:
    """
    把 loginDateTime 还原成**标准 Unix 时间戳**。

    ★ loginDateTime 是「本地墙上时间被当作 UTC 时刻」的秒数（见 login_date_time_now），
      所以标准 Unix 秒 = loginDateTime - 本地时区偏移（东八区即 -28800）。

    对应 source/Assembly-CSharp/Net.VO.Mai2/VOExtensions.cs:1290
        result.loginDate = TimeManager.GetUnixTime(src.Detail.LastLoginDate);
    而 TimeManager.GetUnixTime 返回的是标准 Unix 秒。

    真机佐证：loginDateTime=1791159576 -> 1791159576-28800 = 1791130776，
              真机 loginDate = 1791130777（差 1 秒，源于字符串截断到秒）。
    """
    return int(login_date_time) - local_utc_offset_seconds()


# =============================================================================
# 六、本局数据（play）
# =============================================================================

@dataclass
class PlayData:
    """
    一局游玩的全部输入。

    ★ 默认值全部来自 config.py 的 PLAY_* 系列（取自真机 source/2026-10-05.log:123）。
      想换歌/换成绩只改 config.py，不用动代码。
    """
    # 曲目
    music_id: int = field(default_factory=lambda: config.PLAY_MUSIC_ID)
    music_level: int = field(default_factory=lambda: config.PLAY_MUSIC_LEVEL)
    track_no: int = field(default_factory=lambda: config.PLAY_TRACK_NO)
    version_int: int = field(default_factory=lambda: config.PLAY_VERSION_INT)
    version_str: str = field(default_factory=lambda: config.PLAY_VERSION_STR)

    # 成绩
    achievement: int = field(default_factory=lambda: config.PLAY_ACHIEVEMENT)
    deluxscore: int = field(default_factory=lambda: config.PLAY_DELUXSCORE)
    score_rank: int = field(default_factory=lambda: config.PLAY_SCORE_RANK)
    is_clear: bool = field(default_factory=lambda: config.PLAY_IS_CLEAR)
    max_combo: int = field(default_factory=lambda: config.PLAY_MAX_COMBO)
    total_combo: int = field(default_factory=lambda: config.PLAY_TOTAL_COMBO)
    max_sync: int = field(default_factory=lambda: config.PLAY_MAX_SYNC)
    total_sync: int = field(default_factory=lambda: config.PLAY_TOTAL_SYNC)
    combo_status: int = field(default_factory=lambda: config.PLAY_COMBO_STATUS)
    sync_status: int = field(default_factory=lambda: config.PLAY_SYNC_STATUS)
    fast_count: int = field(default_factory=lambda: config.PLAY_FAST_COUNT)
    late_count: int = field(default_factory=lambda: config.PLAY_LATE_COUNT)
    judge_counts: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: copy.deepcopy(config.PLAY_JUDGE_COUNTS))

    # 评级
    before_rating: int = field(default_factory=lambda: config.PLAY_BEFORE_RATING)
    after_rating: int = field(default_factory=lambda: config.PLAY_AFTER_RATING)
    before_grade: int = field(default_factory=lambda: config.PLAY_BEFORE_GRADE)
    after_grade: int = field(default_factory=lambda: config.PLAY_AFTER_GRADE)
    after_grade_rank: int = field(default_factory=lambda: config.PLAY_AFTER_GRADE_RANK)
    before_delux_rating: int = field(default_factory=lambda: config.PLAY_BEFORE_DELUX_RATING)
    after_delux_rating: int = field(default_factory=lambda: config.PLAY_AFTER_DELUX_RATING)

    # 曲种
    category_index: int = field(default_factory=lambda: config.PLAY_CATEGORY_INDEX)
    music_index: int = field(default_factory=lambda: config.PLAY_MUSIC_INDEX)
    extra_flag: int = field(default_factory=lambda: config.PLAY_EXTRA_FLAG)

    # 角色（游玩时快照，不加经验）
    characters: List[Dict[str, int]] = field(
        default_factory=lambda: copy.deepcopy(config.PLAY_CHARACTERS))

    # 消耗
    play_credit: int = field(default_factory=lambda: config.PLAY_CREDIT)
    use_ticket_id: int = field(default_factory=lambda: config.PLAY_USE_TICKET_ID)
    play_mode: int = field(default_factory=lambda: config.PLAY_MODE)
    is_tutorial: bool = field(default_factory=lambda: config.PLAY_IS_TUTORIAL)
    is_event_mode: bool = field(default_factory=lambda: config.PLAY_IS_EVENT_MODE)
    is_new_free: bool = field(default_factory=lambda: config.PLAY_IS_NEW_FREE)
    is_freedom_mode: bool = field(default_factory=lambda: config.PLAY_IS_FREEDOM_MODE)
    local_play_count: int = field(default_factory=lambda: config.PLAY_LOCAL_PLAY_COUNT)

    # 演算增量
    #: 用户总游玩次数增量（0 = userData.playCount / currentPlayCount 都不变）
    #: ★ 默认 0：不再自动 +1。想复刻真机就设成 1。
    user_play_count_gain: int = field(
        default_factory=lambda: getattr(config, "PLAY_USER_PLAY_COUNT_GAIN", 0))
    #: 曲目历史游玩次数增量（0 = 条目照传但次数不变）
    music_play_count_gain: int = field(
        default_factory=lambda: config.PLAY_MUSIC_PLAY_COUNT_GAIN)
    map_distance_gain: int = field(default_factory=lambda: config.PLAY_MAP_DISTANCE_GAIN)
    character_exp_gain: int = field(default_factory=lambda: config.PLAY_CHARACTER_EXP_GAIN)

    # ---- 里程 / 登录奖励 ----
    # ★ 这两个是**登录奖励发放**才产生的，普通游玩结算不回传（留空）。
    #   真机 39 次 UpsertUserAll 样本里，userGetPointList 有 25 次为空（64%）。
    #   留空 => userData.point 保持基线值不变（不发放点数）。


def build_play_from_config() -> PlayData:
    """按 config.py 的 PLAY_* 构造本局数据。"""
    return PlayData()


def derive_play_characters(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
) -> List[Dict[str, int]]:
    """
    从**服务器刚下发的快照**推出本局的 5 只角色（含游玩前等级）。

    ★ 为什么需要它：
        config.PLAY_CHARACTERS 是手填的静态值，账号一升级就过期；
        用过期值会得到与 userCharacterList 对不上的 characterLevelN。
        快照是登录后立刻抓的服务器真值，永远是最新的。

    数据来源（都在 Get 响应里）：
        userData.charaSlot         本局 5 个角色槽的 characterId（顺序即 slot1..5）
                                   source/Assembly-CSharp/Net.VO.Mai2/GetUserData.cs
        userCharacterList          每只角色的 level / awakening
                                   GetUserCharacterApi 响应

    参数：
        snapshot: GetNeedUserData 的返回值（或任何含 userData /
                  userCharacterList 的字典）。
        play:     当前的 PlayData；快照里查不到的槽位回退到它同位置的配置。

    返回：
        5 条 {"characterId","level","awakening"}，**游玩前**的值（不加经验）。
        快照里既没有该角色、配置也没有时，该槽位为 characterId=0。
    """
    p = play or build_play_from_config()
    fallback = list(p.characters or [])[:5]

    snap = normalize_snapshot(snapshot) if snapshot else {}

    slot_ids: List[int] = []
    levels: Dict[int, Dict[str, int]] = {}
    try:
        # userData 是 singleton 节点（列表 1 元素）；也容忍裸 dict 形态
        data = snap.get("userData") or []
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list) and data and isinstance(data[0], dict):
            raw_slots = data[0].get("charaSlot") or []
            if isinstance(raw_slots, (list, tuple)):
                slot_ids = [int(x or 0) for x in raw_slots[:5]]
        chars = snap.get("userCharacterList") or []
        if isinstance(chars, dict):
            chars = [chars]
        if isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict) and c.get("characterId") is not None:
                    levels[int(c["characterId"])] = c
    except Exception:
        slot_ids = []
        levels = {}

    out: List[Dict[str, int]] = []
    for i in range(5):
        cid = slot_ids[i] if i < len(slot_ids) else 0
        src = levels.get(cid)
        if src is not None:
            out.append({
                "characterId": cid,
                "level": int(src.get("level", 0) or 0),
                "awakening": int(src.get("awakening", 0) or 0),
            })
            continue
        fb = fallback[i] if i < len(fallback) and isinstance(fallback[i], dict) else {}
        out.append({
            "characterId": int(fb.get("characterId", 0) or 0),
            "level": int(fb.get("level", 0) or 0),
            "awakening": int(fb.get("awakening", 0) or 0),
        })
    return out


def build_post_play_user_data(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
    *,
    login_date_time: int,
    auth_date_time: Optional[int] = None,
    place_id: int = PLACE_ID,
    place_name: str = PLACE_NAME,
    region_id: int = REGION_ID,
    region_name: str = REGION_NAME,
    client_id: str = CLIENT_ID,
    play_date_time: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构造**游玩后**的 userData（单个 dict，不是数组）。

    ★ 用途：GetUserNewItemListApi 需要传「游玩后」的档案。
      真机实证（source/2026-10-05-new.log）：
          GetUserNewItemList 的 userData[0] 与 UpsertUserAll 的 userData[0]
          **完全一致**（playCount=1258、point=4460、lastPlayDate=19:22:53.0）。

    返回：
        游玩后的 userData 字典（可直接放进 [ ] 传给 GetUserNewItemList）
    """
    p = play or build_play_from_config()
    ua = build_user_all(
        snapshot=snapshot, play=p,
        login_date_time=login_date_time, auth_date_time=auth_date_time,
        place_id=place_id, place_name=place_name,
        region_id=region_id, region_name=region_name, client_id=client_id,
        play_date_time=play_date_time,
    )
    data = ua.get("userData") or []
    return dict(data[0]) if data else {}


# =============================================================================
# 七、userPlaylogList（110 字段成绩明细）
# =============================================================================

#: UserPlaylog 的**全部**字段，顺序照 source/Assembly-CSharp/Net.VO.Mai2/UserPlaylog.cs
#: ★ 一个都不能省：把真机报文与 C# 声明做集合比对，两个方向都是 0 差异。
PLAYLOG_FIELDS: Tuple[str, ...] = (
    "userId", "orderId", "playlogId", "version", "placeId", "placeName",
    "loginDate", "playDate", "userPlayDate", "type", "musicId", "level",
    "trackNo", "vsMode", "vsUserName", "vsStatus", "vsUserRating",
    "vsUserAchievement", "vsUserGradeRank", "vsRank", "playerNum",
    "playedUserId1", "playedUserName1", "playedMusicLevel1",
    "playedUserId2", "playedUserName2", "playedMusicLevel2",
    "playedUserId3", "playedUserName3", "playedMusicLevel3",
    "characterId1", "characterLevel1", "characterAwakening1",
    "characterId2", "characterLevel2", "characterAwakening2",
    "characterId3", "characterLevel3", "characterAwakening3",
    "characterId4", "characterLevel4", "characterAwakening4",
    "characterId5", "characterLevel5", "characterAwakening5",
    "achievement", "deluxscore", "scoreRank", "maxCombo", "totalCombo",
    "maxSync", "totalSync",
    "tapCriticalPerfect", "tapPerfect", "tapGreat", "tapGood", "tapMiss",
    "holdCriticalPerfect", "holdPerfect", "holdGreat", "holdGood", "holdMiss",
    "slideCriticalPerfect", "slidePerfect", "slideGreat", "slideGood", "slideMiss",
    "touchCriticalPerfect", "touchPerfect", "touchGreat", "touchGood", "touchMiss",
    "breakCriticalPerfect", "breakPerfect", "breakGreat", "breakGood", "breakMiss",
    "isTap", "isHold", "isSlide", "isTouch", "isBreak",
    "isCriticalDisp", "isFastLateDisp", "fastCount", "lateCount",
    "isAchieveNewRecord", "isDeluxscoreNewRecord", "comboStatus", "syncStatus",
    "isClear", "beforeRating", "afterRating", "beforeGrade", "afterGrade",
    "afterGradeRank", "beforeDeluxRating", "afterDeluxRating",
    "isPlayTutorial", "isEventMode", "isFreedomMode", "playMode", "isNewFree",
    "trialPlayAchievement", "extNum1", "extNum2", "extNum4",
    "extBool1", "extBool2", "extBool3",
)

#: ★ 类型是 string 的字段（默认值必须是空串，不是 0）
PLAYLOG_STRING_FIELDS: Tuple[str, ...] = (
    "placeName", "playDate", "userPlayDate",
    "vsUserName", "playedUserName1", "playedUserName2", "playedUserName3",
)

#: ★ 名字不带 is 前缀但类型是 bool 的字段（早期实现用 startswith("is") 判断会漏掉）
PLAYLOG_BOOL_FIELDS: Tuple[str, ...] = (
    "isTap", "isHold", "isSlide", "isTouch", "isBreak",
    "isCriticalDisp", "isFastLateDisp",
    "isAchieveNewRecord", "isDeluxscoreNewRecord", "isClear",
    "isPlayTutorial", "isEventMode", "isFreedomMode", "isNewFree",
    "extBool1", "extBool2", "extBool3",
)

#: 判定类型与判定位（顺序固定）
JUDGE_TYPES: Tuple[str, ...] = ("tap", "hold", "slide", "touch", "break")
JUDGE_BOXES: Tuple[str, ...] = ("CriticalPerfect", "Perfect", "Great", "Good", "Miss")


def build_user_playlog(
    playlog_id: int,
    login_date: int,
    play: Optional[PlayData] = None,
    *,
    place_id: int = PLACE_ID,
    place_name: str = PLACE_NAME,
    client_id: str = CLIENT_ID,
    user_play_date: Optional[str] = None,
    play_date: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构造一条 110 字段的 userPlaylog。

    参数：
        playlog_id:    ★ 必须 == UserLoginApi 的 loginId
        play_date:     ★ 本局**游玩时刻**（loginDateTime 同格式，即 now + 时区偏移）。
                       用于 playDate（日志日）与 userPlayDate（墙上串）。
                       不传则退回 login_date（确定性更强，适合离线对拍）。
                       ★ 为什么要分开：真机 playDate / userPlayDate 是「打完那一刻」，
                         而 loginDateTime 是「刷卡登录那一刻」，两者相差一局的时间
                         （source/2026-10-05.log: 登录 00:19:37 -> 游玩 00:20:30）。
        login_date:    登录会话时刻（用于推导 loginDate）。
                       ★ 真机里 userPlaylog.loginDate 是**游玩会话的开始时刻**
                         （source/2026-10-05.log:123 是 1791130777，
                          比 UserLoginApi 的 loginDateTime=1791159576 早约 8 小时，
                          实为上一局的会话时刻），纯网络脚本没有这个值，
                          这里用传入值推导即可；服务端不以此为准。
        play:          本局数据（可选，默认按 config.PLAY_* 构造）
        place_id:      店铺 ID
        place_name:    店铺名
        client_id:     机台短值
        user_play_date: 游玩时刻字符串（可选，默认由 login_date 推导）

    返回：
        110 字段的 dict

    自动推导的规则（依据 source/.../Net.VO.Mai2/VOExtensions.cs）：
        userId           恒为 0（VOExtensions.cs:1289）
        musicId >= 100000（宴谱） -> level = 10（VOExtensions.cs:1300-1303）
        isTap/isHold/... 由该类型判定总数是否为 0 推导（VOExtensions.cs:1403-1407）
        trialPlayAchievement = -1（本局没有试玩谱）（VOExtensions.cs:1441-1445）
        extNum4 = 曲种索引（与 userExtend.categoryIndex 冗余）
    """
    p = play or build_play_from_config()

    level = 10 if p.music_id >= 100000 else p.music_level
    play_moment = int(play_date) if play_date else int(login_date)
    user_play_date = user_play_date or _local_wall_string(play_moment)

    # ★ 字符串字段默认空串、其余默认 0（真机报文里 vsUserName/playedUserNameN 都是 ""）
    row: Dict[str, Any] = {
        name: ("" if name in PLAYLOG_STRING_FIELDS else 0)
        for name in PLAYLOG_FIELDS
    }

    # ---- 基础 ----
    row["userId"] = 0                       # VOExtensions.cs:1289
    row["orderId"] = 0
    row["playlogId"] = playlog_id
    row["version"] = p.version_int
    row["placeId"] = place_id
    row["placeName"] = place_name
    # ★ loginDate 是**标准 Unix 秒**（VOExtensions.cs:1290 GetUnixTime 的返回值），
    #   不是 loginDateTime（后者是「墙上时间当 UTC」）。
    row["loginDate"] = _standard_unix(login_date)
    # ★ playDate 是游玩**日志日**（7 点前算前一天），不是自然日；
    #   取的是**游玩时刻**，不是登录时刻。
    row["playDate"] = _local_date_string(play_moment)
    row["userPlayDate"] = user_play_date
    row["type"] = 0
    row["musicId"] = p.music_id
    row["level"] = level
    row["trackNo"] = p.track_no

    # ---- 对战（单人局全 0）----
    row["playerNum"] = 1

    # ---- 角色快照 1..5 ----
    # ★ characterLevelN 是**游玩前**的等级，不要加本局经验 —— 这一点极容易搞错：
    #     source/Assembly-CSharp/Net.VO.Mai2/VOExtensions.cs:1361
    #         result.characterLevel1 = (int)gameScore.CharaLevel[0];
    #   gameScore.CharaLevel 是**本次开始游玩时**灌进去的快照，整局不再变；
    #   游玩后的等级只出现在 upsertUserAll.userCharacterList 里。
    #
    #   ★ 两个真机会话实证（Get 侧 / playlog / upsertUserCharacterList 三者对照）：
    #
    #     source/2026-10-05-new.log:31,123（19:21 会话）
    #       GetUserCharacterApi  : 395=3801 101=4456 135 135 135
    #       userPlaylogList[0]   : 3801 4456 135 135 135   ← 与 Get 侧相同 = 游玩前
    #       userCharacterList    : 395=3802 101=4457 136 136 136  ← 游玩后（+1）
    #
    #     MaimaiNetSpy 2026-10-05_222919（22:31 会话）
    #       GetUserCharacterApi  : 395=3802 101=4457 136 136 136
    #       userPlaylogList[0]   : 3802 4457 136 136 136   ← 与 Get 侧相同 = 游玩前
    #       userCharacterList    : 395=3803 101=4458 137 137 137  ← 游玩后（+1）
    #
    #   所以 p.characters 里放的必须是**游玩前**的值
    #   （config.PLAY_CHARACTERS 的注释也是这么写的），这里原样透传即可。
    #   推荐做法：用 derive_play_characters(snapshot) 直接从服务器刚下发的
    #   userData.charaSlot + userCharacterList 推出来，省得手填过期。
    chars = list(p.characters or [])[:5]
    for i in range(5):
        c = chars[i] if i < len(chars) else {}
        row["characterId" + str(i + 1)] = int(c.get("characterId", 0) or 0)
        # 游玩前等级（不加经验；经验只体现在 userCharacterList）
        row["characterLevel" + str(i + 1)] = int(c.get("level", 0) or 0)
        row["characterAwakening" + str(i + 1)] = int(c.get("awakening", 0) or 0)

    # ---- 成绩 ----
    row["achievement"] = p.achievement
    row["deluxscore"] = p.deluxscore
    row["scoreRank"] = p.score_rank
    row["maxCombo"] = p.max_combo
    row["totalCombo"] = p.total_combo
    row["maxSync"] = p.max_sync
    row["totalSync"] = p.total_sync
    row["comboStatus"] = p.combo_status
    row["syncStatus"] = p.sync_status
    row["isClear"] = bool(p.is_clear)
    row["fastCount"] = p.fast_count
    row["lateCount"] = p.late_count

    # ---- 判定明细（5 类型 × 5 判定位）----
    for jtype in JUDGE_TYPES:
        counts = (p.judge_counts or {}).get(jtype, {}) or {}
        total = 0
        for box in JUDGE_BOXES:
            value = int(counts.get(box, 0) or 0)
            row[jtype + box] = value
            total += value
        # isTap / isHold / ... 由该类型是否有 note 推导
        flag_name = "is" + jtype.capitalize()
        if flag_name in row:
            row[flag_name] = (total > 0)

    # ---- 显示开关（真机均为 true）----
    row["isCriticalDisp"] = True
    row["isFastLateDisp"] = True

    # ---- 评级 ----
    row["beforeRating"] = p.before_rating
    row["afterRating"] = p.after_rating
    row["beforeGrade"] = p.before_grade
    row["afterGrade"] = p.after_grade
    row["afterGradeRank"] = p.after_grade_rank
    row["beforeDeluxRating"] = p.before_delux_rating
    row["afterDeluxRating"] = p.after_delux_rating

    # ---- 模式 ----
    row["isPlayTutorial"] = bool(p.is_tutorial)
    row["isEventMode"] = bool(p.is_event_mode)
    row["isFreedomMode"] = bool(p.is_freedom_mode)
    row["playMode"] = p.play_mode
    row["isNewFree"] = bool(p.is_new_free)

    # ---- 试玩（本局没有试玩谱）----
    row["trialPlayAchievement"] = -1

    # ---- 扩展位 ----
    row["extNum1"] = 0
    row["extNum2"] = 0
    row["extNum4"] = p.category_index      # 与 userExtend.categoryIndex 冗余
    row["extBool1"] = False
    row["extBool2"] = False
    row["extBool3"] = False

    # 类型自检：bool 字段必须是 bool
    for name in PLAYLOG_BOOL_FIELDS:
        row[name] = bool(row.get(name, False))

    return row


def validate_user_playlog(playlog: Dict[str, Any]) -> List[str]:
    """
    按源码硬约束自查一条 playlog，返回问题列表（空 = 合规）。

    字段填错不会报错，却会被服务端当成异常成绩。检查项：
        1. 字段数量 == 110
        2. 各类型判定数之和 == totalCombo
        3. maxCombo <= 判定总数
        4. achievement > 0 时不应全是 Miss
        5. isClear=True 时 achievement 不能为 0
        6. comboStatus=1（全连）时 maxCombo == 判定总数
        7. extNum4 == userExtend.categoryIndex（由调用方核对，这里只提示非 0）
    """
    problems: List[str] = []

    missing = [f for f in PLAYLOG_FIELDS if f not in playlog]
    if missing:
        problems.append("缺少字段：" + ", ".join(missing[:10])
                        + ("..." if len(missing) > 10 else ""))
    extra = [k for k in playlog if k not in PLAYLOG_FIELDS]
    if extra:
        problems.append("多出字段：" + ", ".join(extra[:10]))

    total_notes = 0
    for jtype in JUDGE_TYPES:
        for box in JUDGE_BOXES:
            total_notes += int(playlog.get(jtype + box, 0) or 0)

    total_combo = int(playlog.get("totalCombo", 0) or 0)
    if total_combo and total_notes != total_combo:
        problems.append("各类型判定数之和 " + str(total_notes)
                        + " != totalCombo " + str(total_combo))

    max_combo = int(playlog.get("maxCombo", 0) or 0)
    if total_notes and max_combo > total_notes:
        problems.append("maxCombo " + str(max_combo) + " > 判定总数 " + str(total_notes))

    achievement = int(playlog.get("achievement", 0) or 0)
    if achievement > 0:
        miss = sum(int(playlog.get(jtype + "Miss", 0) or 0) for jtype in JUDGE_TYPES)
        if total_notes and miss == total_notes:
            problems.append("achievement>0 但全是 Miss，数值矛盾")

    if bool(playlog.get("isClear")) and achievement == 0:
        problems.append("isClear=True 但 achievement=0，数值矛盾")

    if int(playlog.get("comboStatus", 0) or 0) == 1 and max_combo != total_notes:
        problems.append("comboStatus=1（全连）但 maxCombo != 判定总数")

    if int(playlog.get("extNum4", 0) or 0) == 0:
        problems.append("extNum4（曲种索引）为 0，应等于 userExtend.categoryIndex")

    if not playlog.get("placeName"):
        problems.append("placeName 为空（店铺名需在 config.PLACE_NAME 配置）")

    return problems


# =============================================================================
# 八、userGamePlaylogList
# =============================================================================

def calc_play_special(calc_special_num: Optional[int] = None) -> int:
    """
    复刻 VOExtensions.cs:846-855 的 playSpecial 算法。

    源码：
        int max  = 1037933;
        int num2 = Random.Range(1, max) * 2069;
        num2 += GameManager.CalcSpecialNum();
        int num3 = 0;
        for (int i = 0; i < 32; i++) { num3 <<= 1; num3 += num2 % 2; num2 >>= 1; }
        playSpecial = num3;

    参数：
        calc_special_num: 机台硬件标志位掩码（GameManager.CalcSpecialNum）。
                          默认取 config.PLAY_SPECIAL_NUM = 1024。

    返回：
        int32 范围的 playSpecial。

    ★ 关于 CalcSpecialNum 的取值（源码 GameManager.cs:332-378）：
        它是按位或出来的机台特征掩码，其中 0x400 无条件置位，
        另外 0x40 / 0x80 / 0x100 三位的条件是「**不**包含某特征」——
        真机是一台标准 ACA + GTX + i3-8100 机台，这三位恰好都为 0，
        于是 CalcSpecialNum 恒等于 0x400 = 1024。

      ★ 反推验证：真机 playSpecial = 892014272
            位反转32(892014272) = 57726124 = 27900 * 2069 + 1024
            余数正是 1024，与 gamehook 抓到的 CalcSpecialNum 完全吻合。
    """
    import random
    special = PLAY_SPECIAL_NUM if calc_special_num is None else int(calc_special_num)
    num2 = random.randint(1, 1037932) * 2069
    num2 += special
    num3 = 0
    for _ in range(32):
        num3 <<= 1
        num3 += num2 % 2
        num2 >>= 1
    # 截断到 int32
    if num3 >= 2 ** 31:
        num3 -= 2 ** 32
    return num3


def build_user_game_playlog(
    playlog_id: int,
    login_date: int,
    play: Optional[PlayData] = None,
    *,
    client_id: str = CLIENT_ID,
    play_special: Optional[int] = None,
    play_date: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构造 userGamePlaylogList 的一条（13 字段）。

    ★ playDate 用的是**上报那一刻**的墙上时间（真机实证：
      source/2026-10-05.log 里 userGamePlaylogList[0].playDate = "00:20:57.0"，
      与 UpsertUserAllApi 请求发出的时刻一致，也和 userData.lastPlayDate 相同）。
      不传 play_date 时退回 login_date。

    真机样本（source/2026-10-05.log:123）：
        {"playlogId":..,"version":"1.56.00","playDate":"2026-10-05 00:20:57.0",
         "playMode":0,"useTicketId":-1,"playCredit":1,"playTrack":1,
         "clientId":"TESTCLIENT1","isPlayTutorial":false,"isEventMode":false,
         "isNewFree":false,"playCount":8,"playSpecial":55951502,"playOtherUserId":0}
    """
    p = play or build_play_from_config()
    return {
        "playlogId": playlog_id,
        "version": p.version_str,
        "playDate": _local_wall_string(play_date or login_date),
        "playMode": p.play_mode,
        "useTicketId": p.use_ticket_id,
        "playCredit": p.play_credit,
        "playTrack": p.track_no,
        "clientId": client_id,
        "isPlayTutorial": bool(p.is_tutorial),
        "isEventMode": bool(p.is_event_mode),
        "isNewFree": bool(p.is_new_free),
        "playCount": p.local_play_count,
        "playSpecial": calc_play_special() if play_special is None else int(play_special),
        "playOtherUserId": 0,
    }


# =============================================================================
# 九、默认节点构造
# =============================================================================

def default_user_weekly_data(login_date: int) -> Dict[str, Any]:
    """
    构造 userWeeklyData（★ 对象，不是数组）。

    真机样本：
        {"lastLoginWeek":"2026-09-28 04:00:00","beforeLoginWeek":"2026-09-21 04:00:00",
         "friendBonusFlag":true}
    周界为**周一 04:00**（真机 updateDate 就是 2026-09-28 04:00:00，那天是周一）。
    """
    def week_start(unix_seconds: int) -> str:
        dt = datetime.fromtimestamp(int(unix_seconds), tz=timezone.utc) - timedelta(hours=4)
        dt = dt - timedelta(days=dt.weekday())
        return dt.strftime("%Y-%m-%d") + " 04:00:00"

    this_week = week_start(login_date)
    prev_week = week_start(login_date - 7 * 86400)
    return {
        "lastLoginWeek": this_week,
        "beforeLoginWeek": prev_week,
        "friendBonusFlag": True,
    }


def default_user_2p_playlog() -> Dict[str, Any]:
    """
    构造 user2pPlaylog（★ 对象，不是数组）。

    真机样本：
        {"userId1":0,"userId2":0,"userName1":"","userName2":"",
         "regionId":0,"placeId":0,"user2pPlaylogDetailList":[]}
    """
    return {
        "userId1": 0,
        "userId2": 0,
        "userName1": "",
        "userName2": "",
        "regionId": 0,
        "placeId": 0,
        "user2pPlaylogDetailList": [],
    }


# =============================================================================
# 十、快照归一化
# =============================================================================

def _extract_from_get_responses(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    把「各 Get 接口的原始响应」整理成节点字典（含字段裁剪）。

    参数：
        raw: 形如
             {
               "userData":       <GetUserDataApi 的响应>,
               "userExtend":     <GetUserExtendApi 的响应>,
               "userMapList":    <GetUserMapApi 的响应>,
               ...
             }
             也接受 GetNeedUserData() 已经整理好的节点字典（幂等）。

    返回：
        节点名 -> 节点值（已裁剪）
    """
    out: Dict[str, Any] = {}

    # ---- 单元素数组 ----
    if "userData" in raw:
        src = raw["userData"]
        ud = src.get("userData") if isinstance(src, dict) and "userData" in src else src
        if isinstance(ud, dict):
            ud = _strip_keys(ud, USER_DATA_DROP_KEYS)
            # banState 在 Get 侧是顶层字段，回传时要搬进 userData 内部
            if isinstance(src, dict) and "banState" in src and "banState" not in ud:
                ud["banState"] = src.get("banState")
            out["userData"] = [ud]

    if "userExtend" in raw:
        src = raw["userExtend"]
        ue = src.get("userExtend") if isinstance(src, dict) and "userExtend" in src else src
        if isinstance(ue, dict):
            out["userExtend"] = [ue]

    if "userOption" in raw:
        src = raw["userOption"]
        uo = src.get("userOption") if isinstance(src, dict) and "userOption" in src else src
        if isinstance(uo, dict):
            out["userOption"] = [_strip_keys(uo, USER_OPTION_DROP_KEYS)]

    if "userRatingList" in raw:
        src = raw["userRatingList"]
        ur = src.get("userRating") if isinstance(src, dict) and "userRating" in src else src
        if isinstance(ur, dict):
            ur = copy.deepcopy(ur)
            # ★ 裁掉 udemae 里服务端冗余的大写重复字段（真机 Upsert 侧没有）
            udemae = ur.get("udemae")
            if isinstance(udemae, dict):
                ur["udemae"] = _strip_keys(udemae, USER_RATING_UDEMAE_DROP_KEYS)
            out["userRatingList"] = [ur]

    # ---- 对象 ----
    if "userWeeklyData" in raw:
        src = raw["userWeeklyData"]
        uw = src.get("userWeeklyData") if isinstance(src, dict) and "userWeeklyData" in src else src
        if isinstance(uw, dict):
            out["userWeeklyData"] = _strip_keys(uw, USER_MISSION_DROP_KEYS)

    # ★ userWeeklyData 的另一个来源：GetUserMissionDataApi 的响应里就带着它
    #   （UserMissionResponseVO.cs:10  public UserWeeklyData userWeeklyData;）
    #   真机值 = 服务器下发的周界，**不是本地算的**：
    #       GetGameWeeklyDataApi.updateDate   = "2026-09-28 04:00:00"
    #       Upsert 侧 lastLoginWeek           = "2026-09-28 04:00:00"   ← 完全一致
    #   依据 source/Assembly-CSharp/Manager/GetUserData.cs:1040-1049
    #       WeeklyData.LastLoginWeek = gameWeeklyData.updateDate;
    #   所以优先用快照里的值；只有拿不到时才退回本地推导。
    if "userWeeklyData" not in out and "userMissionDataList" in raw:
        src = raw["userMissionDataList"]
        if isinstance(src, dict):
            uw = src.get("userWeeklyData")
            if isinstance(uw, dict) and uw:
                out["userWeeklyData"] = _strip_keys(uw, USER_MISSION_DROP_KEYS)

    if "user2pPlaylog" in raw:
        src = raw["user2pPlaylog"]
        u2 = src.get("user2pPlaylog") if isinstance(src, dict) and "user2pPlaylog" in src else src
        if isinstance(u2, dict):
            out["user2pPlaylog"] = u2

    # ---- 普通数组（键名 -> 响应里的列表键名）----
    array_map = {
        "userCharacterList": "userCharacterList",
        "userGhost": "userGhostList",
        "userMapList": "userMapList",
        "userLoginBonusList": "userLoginBonusList",
        "userItemList": "userItemList",
        "userMusicDetailList": "userMusicList",
        "userCourseList": "userCourseList",
        "userChargeList": "userChargeList",
        "userFavoriteList": "userFavorite",
        "userActivityList": "userActivity",
        "userMissionDataList": "userMissionDataList",
        "userIntimateList": "userIntimateList",
        "userShopItemStockList": "userShopStockList",
        "userFavoritemusicList": "userFavoriteItemList",
        "userKaleidxScopeList": "userKaleidxScopeList",
        "userFriendSeasonRankingList": "userFriendSeasonRankingList",
    }
    for node, list_key in array_map.items():
        if node not in raw:
            continue
        src = raw[node]
        if isinstance(src, list):
            items = src
        elif isinstance(src, dict):
            if list_key == "userMusicList":
                # ★ 曲目成绩有两种形态，都要支持：
                #   a) 接口原始响应：两层嵌套（UserMusic.cs 外层按曲分组，
                #      内层 userMusicDetailList 才是 (musicId, level) 条目）
                #   b) GetUserMusicDetailAll() 的产物：已摊平成单条
                #   判据：元素里带 "userMusicDetailList" 键 -> 嵌套；否则已摊平。
                groups = src.get("userMusicList") or []
                nested = any(
                    isinstance(g, dict) and "userMusicDetailList" in g for g in groups
                )
                if nested:
                    items = []
                    for g in groups:
                        if isinstance(g, dict):
                            items.extend(g.get("userMusicDetailList") or [])
                        elif isinstance(g, list):
                            items.extend(g)
                else:
                    items = list(groups)
            else:
                items = src.get(list_key)
                # ★ 兜底：取数脚本返回的字典有时用**节点名**作键
                #   （如 GetUserFavoriteAll -> {"userFavoriteList": [...], "_raw": [...]}，
                #    而 GetUserFavoriteApi 的原始响应是 {"userFavorite": {...}}）。
                if items is None:
                    items = src.get(node)
            if items is None:
                items = []
            if isinstance(items, dict):
                items = [items]
        else:
            continue

        if node == "userCharacterList":
            items = [_keep_keys(i, USER_CHARACTER_KEEP_KEYS) for i in items]
        elif node == "userMusicDetailList":
            items = [_strip_keys(i, USER_MUSIC_DETAIL_DROP_KEYS) for i in items]
        elif node == "userChargeList":
            items = [_strip_keys(i, USER_CHARGE_DROP_KEYS) for i in items]
        elif node == "userMissionDataList":
            items = [_strip_keys(i, USER_MISSION_DROP_KEYS) for i in items]
        out[node] = list(items)

    # ★ 收藏夹的**原始**基线（不补 itemKind）：真机 itemKind=10 的响应回的是
    #   {"itemKind":null}，位串里的 "1" 就来自它。单独存一份供差分用。
    if isinstance(raw.get("_raw_favorite"), list):
        out["_raw_favorite"] = list(raw["_raw_favorite"])
    else:
        fav_src = raw.get("userFavoriteList")
        if isinstance(fav_src, dict):
            if isinstance(fav_src.get("_raw"), list):
                out["_raw_favorite"] = list(fav_src["_raw"])
            elif isinstance(fav_src.get("userFavoriteList"), list):
                out["_raw_favorite"] = list(fav_src["userFavoriteList"])
        elif isinstance(fav_src, list):
            out["_raw_favorite"] = list(fav_src)

    return out


#: 真机 isNewFavoriteList 里代表「服务器侧查不到该 itemKind」的取值。
#: 实测两个样本：
#:   source/2026-10-05.log:123          -> "22212"（itemKind=10 那条是 null）
#:   MaimaiNetSpy 抓的 22:32:21 那次     -> "22212"（同上）
#: 即第 4 位（itemKind=10，搭档）**稳定为 "1"** —— 服务端对该 kind 恒回 null。
FAVORITE_MISSING_KINDS: Tuple[int, ...] = (10,)


def normalize_snapshot(snapshot: Optional[Any]) -> Dict[str, Any]:
    """
    把各种形态的快照统一成「节点字典」。

    接受：
        None                          -> {}
        节点字典（36 节点名）          -> 原样（做一次形态强制）
        {"upsertUserAll": {...}}      -> 取内层
        {"_responses": {...}}         -> 取 _responses
        各 Get 接口的原始响应字典      -> 走 _extract_from_get_responses
    """
    if snapshot is None:
        return {}

    if isinstance(snapshot, str):
        with open(snapshot, "r", encoding="utf-8") as fp:
            snapshot = json.load(fp)

    if not isinstance(snapshot, dict):
        raise PatchError("snapshot 形态不认识：" + type(snapshot).__name__)

    if "upsertUserAll" in snapshot and isinstance(snapshot["upsertUserAll"], dict):
        snapshot = snapshot["upsertUserAll"]
    if "_responses" in snapshot and isinstance(snapshot["_responses"], dict):
        snapshot = snapshot["_responses"]

    # ★ 判断是「已是节点字典」还是「原始响应集合」。
    #   两者键名高度重叠（userData / userExtend / userMapList … 都既是节点名，
    #   也是 Get 响应的外层键），所以**只能按值的形态**区分：
    #       节点字典     userData -> list（单元素数组）、userMapList -> list
    #       原始响应集合 userData -> dict（含 userId/userData/banState）
    #                    userMapList -> dict（含 userMapList 列表）
    if _looks_like_node_dict(snapshot):
        out: Dict[str, Any] = {}
        for k, v in snapshot.items():
            if k in NODE_TYPES:
                out[k] = coerce_node_value(k, v)
            elif k.startswith("_"):
                out[k] = v            # 保留 _raw_favorite 这类内部键
        return out

    return _extract_from_get_responses(snapshot)


def _looks_like_node_dict(snapshot: Dict[str, Any]) -> bool:
    """
    按**值的形态**判断 snapshot 是不是「已经整理好的节点字典」。

    判据：节点名对应的值若符合 NODE_TYPES 声明的形态则计 1 分，反之计 -1 分。
          总分 > 0 视为节点字典。
    """
    score = 0
    for key, value in snapshot.items():
        kind = NODE_TYPES.get(key)
        if kind is None:
            continue
        if kind in ("singleton", "array"):
            score += 1 if isinstance(value, list) else -1
        elif kind == "object":
            score += 1 if isinstance(value, dict) else -1
        elif kind == "bits":
            score += 1 if isinstance(value, str) else -1
    return score > 0


# =============================================================================
# 十一、本局演算（把基线推进到「游玩后」）
# =============================================================================

def apply_play_effects(
    user_all: Dict[str, Any],
    play: PlayData,
    *,
    login_date_time: int,
    auth_date_time: Optional[int] = None,
    place_id: int = PLACE_ID,
    place_name: str = PLACE_NAME,
    region_id: int = REGION_ID,
    region_name: str = REGION_NAME,
    client_id: str = CLIENT_ID,
    play_date_time: Optional[int] = None,
) -> Dict[str, Any]:
    """
    按真机行为把基线推进到「本局游玩后」，并算出各差分节点。

    ★ 这是本模块最关键的一步。真机对照（source/2026-10-05.log）：

        userData.playCount        1257 -> 1258            (+1)  ← 真机
        userData.currentPlayCount 185  -> 186             (+1)  ← 真机
        ★ 本工程默认 PLAY_USER_PLAY_COUNT_GAIN = 0，这两个**不变**。
        userData.lastPlayDate     旧   -> 本局时刻
        userData.lastPlayMode     2    -> 0
        userData.lastLoginDate    旧   -> 本次登录时刻
        userData.eventWatchedDate 旧   -> 本次登录时刻
        userData.lastPlaceId      0    -> 1000
        userData.lastRegionId     11   -> 5
        userData.dateTime         null -> 登录请求的 dateTime
        userData.lastGameId       null -> "SDGB"
        userData.accessCode       null -> ""
        userData.lastPlaceName    null -> 店铺名
        userMusicDetailList       7    -> 8               (playCount +1)
        userMapList.distance      1424000 -> 1435000      (+11000)
        userCharacterList[].level 各 +1

    参数（就地修改 user_all）：
        user_all:        节点字典（会被修改）
        play:            本局数据
        login_date_time: UserLoginApi 的 loginDateTime
        auth_date_time:  UserLoginApi 请求里的 dateTime（Auth.AuthTime）
        play_date_time:  ★ 本局上报时刻（同 loginDateTime 格式）。
                         真机 userData.lastPlayDate 是「打完/上报那一刻」，
                         与 lastLoginDate（登录那一刻）**不是同一个值**：
                             lastLoginDate  = "2026-10-05 22:31:23.0"  ← 登录
                             lastPlayDate   = "2026-10-05 22:32:21.0"  ← 上报
                         不传则两者都退回 login_date_time（便于离线对拍）。

    返回：
        同一个 user_all（便于链式调用）
    """
    login_wall = _local_wall_string(login_date_time)
    wall = _local_wall_string(play_date_time or login_date_time)

    # ---------------- userData ----------------
    data_list = user_all.get("userData") or []
    if data_list and isinstance(data_list[0], dict):
        ud = data_list[0]
        ud["accessCode"] = ud.get("accessCode") or ""
        ud["lastGameId"] = ud.get("lastGameId") or "SDGB"
        ud["lastPlaceName"] = place_name
        ud["lastPlaceId"] = place_id
        ud["lastRegionName"] = region_name
        ud["lastRegionId"] = region_id
        ud["lastClientId"] = client_id
        ud["lastCountryCode"] = ud.get("lastCountryCode") or "CHN"
        # ★ 默认增量 0：playCount / currentPlayCount 保持不变
        #   （config.PLAY_USER_PLAY_COUNT_GAIN，想复刻真机 +1 就改成 1）
        _pc_gain = int(getattr(play, "user_play_count_gain", 0) or 0)
        ud["playCount"] = int(ud.get("playCount", 0) or 0) + _pc_gain
        ud["currentPlayCount"] = int(ud.get("currentPlayCount", 0) or 0) + _pc_gain
        ud["lastPlayDate"] = wall                # 本局上报时刻
        ud["lastPlayMode"] = play.play_mode
        ud["lastLoginDate"] = login_wall         # 本次登录时刻
        ud["eventWatchedDate"] = login_wall      # 与 lastLoginDate 同值（真机一致）
        ud["lastPlayCredit"] = play.play_credit
        if auth_date_time:
            ud["dateTime"] = int(auth_date_time)
        if ud.get("banState") is None:
            ud["banState"] = 0

    # ---------------- userExtend ----------------
    ext_list = user_all.get("userExtend") or []
    if ext_list and isinstance(ext_list[0], dict):
        ue = ext_list[0]
        ue["selectMusicId"] = play.music_id
        ue["selectDifficultyId"] = play.music_level
        ue["categoryIndex"] = play.category_index
        ue["musicIndex"] = play.music_index
        ue["extraFlag"] = play.extra_flag
        # 真机 Upsert 里这两个是空数组（Get 侧有占位元素）
        ue["selectedCardList"] = []
        ue["encountMapNpcList"] = []
        # ★ 这两个字段只出现在 Upsert 侧、Get 侧没有
        #   （真机 source/2026-10-05.log:123 的 userExtend 有 16 个键，
        #     Get 侧 source/2026-10-05.log:85 只有 14 个）。
        #   源码 VOExtensions.cs:270 附近是 Export 时补的开关位。
        #   缺了它们会导致 userExtend 字段数不符，服务端可能整体拒收。
        ue.setdefault("isPhotoAgree", False)
        ue.setdefault("isGotoCodeRead", False)

    # ---------------- userMusicDetailList（差分：本局那条曲目）----------------
    # ★★ 这个节点**必须回传本局那条**，不能留空 —— 实测证明：
    #     同一份代码、同一账号，唯一差别是这里留空 vs 回传 1 条：
    #       回传 1 条 -> returnCode=1 且服务端确实写入（当时靠 playCount +1 观察到）
    #       留空     -> returnCode=1 但什么都没变（**没落库**）
    #     即「本局有 playlog 却没有任何曲目明细」会被服务端当成无效包静默丢弃。
    #   ★ 现在 playCount 默认不再 +1，落库判据改看 lastPlayDate（见 verify_upsert_landing）。
    #
    # ★ 但 playCount 的**增量**可以自由控制：
    #     config.PLAY_MUSIC_PLAY_COUNT_GAIN = 0（默认）-> 条目照传，次数不变
    #                                         = 1        -> 复刻真机的 +1
    #   所以「不想让乐曲 playCount 增加」的正确做法是把增量设成 0，
    #   **而不是**把整个节点清空。
    if "userMusicDetailList" in user_all:
        baseline = user_all.get("_baseline_music") or []
        target = None
        for item in baseline:
            if (isinstance(item, dict)
                    and item.get("musicId") == play.music_id
                    and item.get("level") == play.music_level):
                target = copy.deepcopy(item)
                break
        if target is None:
            target = {
                "musicId": play.music_id, "level": play.music_level,
                "playCount": 0, "achievement": 0, "comboStatus": 0,
                "syncStatus": 0, "deluxscoreMax": 0, "scoreRank": 0, "extNum1": 0,
            }
        target["playCount"] = (int(target.get("playCount", 0) or 0)
                               + play.music_play_count_gain)
        # 本局成绩优于历史时才更新最佳值
        if play.achievement > int(target.get("achievement", 0) or 0):
            target["achievement"] = play.achievement
            target["scoreRank"] = play.score_rank
            target["comboStatus"] = play.combo_status
            target["syncStatus"] = play.sync_status
        if play.deluxscore > int(target.get("deluxscoreMax", 0) or 0):
            target["deluxscoreMax"] = play.deluxscore
        user_all["userMusicDetailList"] = [target]
        # ★ 留一份「本局那条」，供后面的差分收敛做兜底（见 build_user_all）
        user_all["_played_music_entry"] = copy.deepcopy(target)

    # ---------------- userMapList（差分：选中地图 distance 增加）----------------
    if "userMapList" in user_all:
        if play.map_distance_gain:
            baseline = user_all.get("_baseline_map") or []
            map_id = None
            ud = (user_all.get("userData") or [{}])[0]
            if isinstance(ud, dict):
                map_id = ud.get("selectMapId")
            target = None
            for item in baseline:
                if isinstance(item, dict) and item.get("mapId") == map_id:
                    target = copy.deepcopy(item)
                    break
            if target is None and baseline and isinstance(baseline[0], dict):
                target = copy.deepcopy(baseline[0])
            if target is not None:
                target["distance"] = int(target.get("distance", 0) or 0) + play.map_distance_gain
                user_all["userMapList"] = [target]
            else:
                user_all["userMapList"] = []
        else:
            user_all["userMapList"] = []

    # ---------------- userCharacterList（差分：组队角色升级）----------------
    if "userCharacterList" in user_all:
        if play.character_exp_gain:
            baseline = user_all.get("_baseline_character") or []
            by_id = {c.get("characterId"): c for c in baseline if isinstance(c, dict)}
            grown = []
            for slot in (play.characters or [])[:5]:
                cid = slot.get("characterId")
                src = by_id.get(cid)
                if src is None:
                    continue
                item = copy.deepcopy(src)
                item["level"] = int(item.get("level", 0) or 0) + play.character_exp_gain
                grown.append(item)
            # ★ 按 characterId 升序（沿用 Get 侧顺序）
            #   真机 source/2026-10-05.log:123 的 userCharacterList 是 [101,395,200401,400401,400402]，
            #   而 charaSlot 是 [395,101,400402,400401,200401] —— 两者顺序不同，
            #   说明回传时按 characterId 排序，不是按 charaSlot 顺序。
            grown.sort(key=lambda c: int(c.get("characterId", 0) or 0))
            user_all["userCharacterList"] = grown
        else:
            user_all["userCharacterList"] = []

    # ---------------- userGetPointList / userLoginBonusList ----------------
    #   ★ 这两个节点是**登录奖励发放**才产生的，普通游玩结算留空即可：
    #     - userGetPointList   ：真机 39 次样本里 25 次为空（64%）
    #     - userLoginBonusList ：只有本次登录触发新签到才回传
    #   两者都在 DEFAULT_EMPTY_NODES 里，由下方统一清空。
    #   point 也因此保持基线值不变（不发放点数的必然结果）。

    # ---------------- userGamePlaylogList（客户端新造）----------------
    user_all["userGamePlaylogList"] = []   # 由 build_user_all 填（需要 playlog_id）

    # ---------------- userWeeklyData / user2pPlaylog ----------------
    if not user_all.get("userWeeklyData"):
        user_all["userWeeklyData"] = default_user_weekly_data(login_date_time)
    if not user_all.get("user2pPlaylog"):
        user_all["user2pPlaylog"] = default_user_2p_playlog()

    # ---------------- 默认空节点 ----------------
    for node in DEFAULT_EMPTY_NODES:
        if node in user_all:
            user_all[node] = empty_node(node)

    return user_all


# =============================================================================
# 十二、组装 upsertUserAll
# =============================================================================

def build_user_all(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
    patch: Optional[Dict[str, Any]] = None,
    *,
    login_date_time: int = 0,
    auth_date_time: Optional[int] = None,
    place_id: int = PLACE_ID,
    place_name: str = PLACE_NAME,
    region_id: int = REGION_ID,
    region_name: str = REGION_NAME,
    client_id: str = CLIENT_ID,
    playlog_id: int = 0,
    play_date_time: Optional[int] = None,
    extra_data: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    组装 upsertUserAll 的 36 个节点。

    流程：
        1. 从 snapshot 建立基线（已裁剪）
        2. apply_play_effects 推进到游玩后，并算出差分节点
        3. 填入 userGamePlaylogList
        4. patch 精确覆盖
        5. 生成 11 条位串

    参数：
        snapshot:        基线快照（见 normalize_snapshot）
        play:            本局数据（默认按 config.PLAY_*）
        patch:           精确覆盖，键=节点名，优先级最高
        login_date_time: UserLoginApi 的 loginDateTime
        auth_date_time:  UserLoginApi 请求里的 dateTime
        play_date_time:  ★ 本局上报时刻（同 loginDateTime 格式）；
                         用于 lastPlayDate / userGamePlaylogList.playDate。
                         不传则退回 login_date_time。
        playlog_id:      UserLoginApi 的 loginId（用于 userGamePlaylogList）
        extra_data:      ★ 额外 JSON（dict / JSON 字符串 / 文件路径），
                         自动匹配插入 36 节点，**优先级高于 patch**。见 merge_extra_data。

    返回：
        36 节点的 dict
    """
    p = play or build_play_from_config()
    base = normalize_snapshot(snapshot)

    # 保留基线副本，供差分计算用
    user_all: Dict[str, Any] = empty_user_all()
    for node in NODE_ORDER:
        if node in base:
            user_all[node] = copy.deepcopy(base[node])
    user_all["_baseline_music"] = copy.deepcopy(base.get("userMusicDetailList") or [])
    user_all["_baseline_map"] = copy.deepcopy(base.get("userMapList") or [])
    user_all["_baseline_character"] = copy.deepcopy(base.get("userCharacterList") or [])
    # ★ 收藏夹的原始基线（未补 itemKind），供 build_favorite_delta 产生 "1"
    if base.get("_raw_favorite"):
        user_all["_raw_favorite"] = copy.deepcopy(base["_raw_favorite"])

    # 推进到游玩后
    apply_play_effects(
        user_all, p,
        login_date_time=login_date_time, auth_date_time=auth_date_time,
        place_id=place_id, place_name=place_name,
        region_id=region_id, region_name=region_name, client_id=client_id,
        play_date_time=play_date_time,
    )

    # userGamePlaylogList（客户端新造，需要 playlog_id）
    if playlog_id:
        user_all["userGamePlaylogList"] = [
            build_user_game_playlog(playlog_id, login_date_time, p, client_id=client_id,
                                    play_date=play_date_time)
        ]

    # ---- ★ 差分：把所有 DELTA_NODES 收敛成 (新状态 - 基线) ----
    #   真机只回传**变化的那几条**：
    #       Get 侧 104 条地图 -> Upsert 侧 1 条（distance 变的那条）
    #       Get 侧 38 条登录奖励 -> Upsert 侧 0 条（本次无变化）
    #   apply_play_effects 已经把「本局会变」的节点推到了新状态，
    #   这里统一做一次 (新 - 基线)，无变化的自然收敛成空数组。
    for node, keys in DIFF_PRIMARY_KEYS.items():
        if node not in NODE_TYPES or NODE_TYPES[node] != "array":
            continue
        current = user_all.get(node) or []
        baseline_items = base.get(node) or []
        if not isinstance(current, list) or not isinstance(baseline_items, list):
            continue
        delta, flags = build_delta(current, baseline_items, keys)
        user_all[node] = delta
        bits = ARRAY_TO_BITS.get(node)
        if bits:
            user_all[bits] = flags

    # ---- ★ userMusicDetailList 特例：次数没变也必须回传本局那条 ----
    #   为什么：上面的差分会把「和基线完全相同」的条目剔掉。当
    #   PLAY_MUSIC_PLAY_COUNT_GAIN = 0（本局不改次数）且成绩也没刷新时，
    #   本局那条会被剔光 -> 节点变空。
    #   ★ 实测（同一份代码、同一账号，唯一差别就是这个节点）：
    #       回传 1 条 -> returnCode=1 且服务端确实写入
    #       留空     -> returnCode=1 但什么都没变（**整包没生效**）
    #   所以这里兜底：只要本局确实打了一首歌，就一定回传它那一条。
    #   位串给 "0" = 服务器侧已有该 (musicId, level)，属于更新而非新增。
    if not (user_all.get("userMusicDetailList") or []):
        _played = user_all.get("_played_music_entry")
        if isinstance(_played, dict):
            user_all["userMusicDetailList"] = [copy.deepcopy(_played)]
            user_all["isNewMusicDetailList"] = "0"

    # ---- 差分：收藏夹是特例（不做剔除，恒返回完整条目）----
    #   ★ 基线要用**未经归一化**的原始 Get 响应：真机 itemKind=10 的那条回的是
    #     {"itemKind":null}，正是它产生了位串里的 "1"。
    #     原始响应由调用方通过 snapshot 的 _raw_favorite 传入；
    #     拿不到时才退回已归一化的基线，并显式声明「哪些 kind 服务端恒回 null」，
    #     否则 itemKind 被补齐后位串会全是 "2"。
    fav_local = user_all.get("userFavoriteList") or base.get("userFavoriteList") or []
    if fav_local:
        raw_fav = base.get("_raw_favorite")
        if raw_fav:
            fav_baseline = raw_fav
            fav_assume_missing: Tuple[int, ...] = ()
        else:
            fav_baseline = base.get("userFavoriteList") or []
            fav_assume_missing = FAVORITE_MISSING_KINDS
        fav_delta, fav_bits = build_favorite_delta(
            fav_local, fav_baseline, fav_assume_missing)
        if fav_assume_missing:
            log_debug("收藏夹基线无原始响应，按已知恒空 kind 兜底："
                      + str(tuple(fav_assume_missing)))
        user_all["userFavoriteList"] = fav_delta
        user_all["isNewFavoriteList"] = fav_bits

    # ---- patch 覆盖 ----
    if patch:
        for node, value in patch.items():
            if node not in NODE_TYPES:
                raise PatchError(
                    "patch 里有未知节点名：" + str(node)
                    + "（可用节点：" + ", ".join(NODE_ORDER) + "）"
                )
            user_all[node] = coerce_node_value(node, value)

    # ---- extra_data 覆盖（★ 最高优先级）----
    if load_extra_data(extra_data):
        for note in merge_extra_data(user_all, extra_data):
            log_info(note)

    # ---- 清理内部字段 ----
    for key in list(user_all.keys()):
        if key.startswith("_"):
            del user_all[key]

    # ---- 位串补齐 ----
    sync_bits_to_arrays(user_all)

    # ---- 按 NODE_ORDER 排序 ----
    return {node: user_all.get(node, empty_node(node)) for node in NODE_ORDER}


# =============================================================================
# 十三、请求 / 响应 VO
# =============================================================================

@dataclass
class UserAllRequestVO:
    """请求 VO（对应 Net.VO.Mai2/UserAllRequestVO，字段顺序照 C# 声明）。"""
    userId: int
    playlogId: int = 0
    isEventMode: bool = False
    isFreePlay: bool = False
    loginDateTime: int = 0
    userPlaylogList: List[Any] = field(default_factory=list)
    upsertUserAll: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpsertResponseVO:
    """响应 VO（对应 Net.VO.Mai2/UpsertResponseVO）。"""
    returnCode: int = 0
    apiName: str = ""


# =============================================================================
# 十四、发包前自检
# =============================================================================

def validate_before_send(
    req: UserAllRequestVO,
    play: Optional[PlayData] = None,
) -> List[str]:
    """
    发包前按源码硬约束自查（返回问题列表，空 = 合规）。

    ★ 即便服务端返回 returnCode=1，也可能静默不落库；
      这里先把能查的都查一遍，有问题就明确告警。

    参数：
        req:  要发的请求
        play: 本局数据（可选）。★ 用来判断「差分节点为空」到底是不是问题：
              config.PLAY_MAP_DISTANCE_GAIN / PLAY_CHARACTER_EXP_GAIN 默认是 0，
              此时 userMapList / userCharacterList 为空是**预期行为**，不该告警。
    """
    problems: List[str] = []

    if not req.playlogId:
        problems.append("顶层 playlogId 为 0（必须 == UserLoginApi 的 loginId）")
    if not req.loginDateTime:
        problems.append("顶层 loginDateTime 为 0（必须 == UserLoginApi 的 loginDateTime）")

    ua = req.upsertUserAll or {}

    ud_list = ua.get("userData") or []
    if not ud_list:
        problems.append("userData 为空（服务端对它是整表覆盖语义，空包等于没提交）")
    else:
        ud = ud_list[0] if isinstance(ud_list[0], dict) else {}
        # ★ accessCode 真机就是空串（source/2026-10-05.log:123），只要求"存在且非 null"
        for key in ("lastGameId", "accessCode", "lastPlaceName", "lastRegionName"):
            if key not in ud or ud.get(key) is None:
                problems.append("userData." + key + " 缺失或为 null")
        nulls = [k for k, v in ud.items() if v is None]
        if nulls:
            problems.append("userData 里有 null 字段：" + ", ".join(nulls[:8]))
        # ★ userData 是整表覆盖语义：这几个「本局必须推进」的字段若还是旧值/0，
        #   服务端会照单全收却等于什么都没发生（见 docs/UpsertUserAll踩坑清单.md 坑 1）
        if not int(ud.get("playCount") or 0):
            problems.append("userData.playCount 为 0（应 >= 基线值）")
        if not int(ud.get("currentPlayCount") or 0):
            problems.append("userData.currentPlayCount 为 0（应 >= 基线值）")
        if not int(ud.get("dateTime") or 0):
            problems.append("userData.dateTime 为 0（应为 UserLoginApi 请求里的 dateTime）")
        if not ud.get("lastPlayDate"):
            problems.append("userData.lastPlayDate 为空（应为本局上报时刻）")
        if not ud.get("lastLoginDate"):
            problems.append("userData.lastLoginDate 为空（应为本次登录时刻）")

    if not req.userPlaylogList:
        problems.append("userPlaylogList 为空（那是本局成绩明细，服务端大概率直接拒收）")
    else:
        for i, pl in enumerate(req.userPlaylogList):
            if isinstance(pl, dict) and pl.get("playlogId") != req.playlogId:
                problems.append("userPlaylogList[" + str(i) + "].playlogId != 顶层 playlogId")
            if isinstance(pl, dict) and not pl.get("playSpecial"):
                pass  # playSpecial 属于 userGamePlaylogList，不是这里

    for gp in ua.get("userGamePlaylogList") or []:
        if isinstance(gp, dict) and not gp.get("playSpecial"):
            problems.append("userGamePlaylogList[].playSpecial 为 0（真机是随机位掩码）")

    # 位串长度
    for bits, arr in BITS_TO_ARRAY.items():
        items = ua.get(arr) or []
        s = ua.get(bits) or ""
        if isinstance(items, list) and len(s) != len(items):
            problems.append("位串 " + bits + " 长度 " + str(len(s))
                            + " != 数组 " + arr + " 条数 " + str(len(items)))

    # 差分节点是否有变化
    #   ★ 只在「配置要求本局有变化」时才告警：
    #     PLAY_MAP_DISTANCE_GAIN / PLAY_CHARACTER_EXP_GAIN 默认是 0，
    #     此时 userMapList / userCharacterList 为空是**预期的**，不是错误。
    p = play or build_play_from_config()
    if not (ua.get("userMusicDetailList") or []):
        problems.append("差分节点 userMusicDetailList 为空 —— ★ 实测这样整包不生效"
                        "（有 playlog 却没有曲目明细会被服务端静默丢弃）")
    if p.map_distance_gain and not (ua.get("userMapList") or []):
        problems.append("差分节点 userMapList 为空，但 PLAY_MAP_DISTANCE_GAIN="
                        + str(p.map_distance_gain) + " —— 服务端可能认为地图无变化")
    if p.character_exp_gain and not (ua.get("userCharacterList") or []):
        problems.append("差分节点 userCharacterList 为空，但 PLAY_CHARACTER_EXP_GAIN="
                        + str(p.character_exp_gain) + " —— 服务端可能认为角色无变化")

    return problems


# =============================================================================
# 十五、冷却等待
# =============================================================================

def wait_send_cooldown(seconds: float, *, label: str = "结算上报") -> float:
    """
    真实发包前固定等待若干秒（含首次），让上报节奏贴近真机。

    ★ 只作用于真实发送；dry_run 不等待。
    """
    seconds = float(seconds or 0)
    if seconds <= 0:
        return 0.0

    log_info(label + "冷却：等待 " + str(seconds) + " 秒后再发送（模拟真机节奏）...")
    start = time.monotonic()
    remain = seconds
    while remain > 0:
        step = min(10.0, remain)
        time.sleep(step)
        remain -= step
        if remain > 0:
            log_info("    冷却中 ... 已等待 " + str(int(seconds - remain)) + "s / 剩 "
                     + str(int(remain)) + "s")
    elapsed = time.monotonic() - start
    log_info("冷却结束（共等待 " + str(round(elapsed, 1)) + " 秒）")
    return elapsed


# =============================================================================
# 十六、extra_data：把外部 JSON 合并进 upsertUserAll
# =============================================================================
#
# 用途：真机报文的 36 个节点里，绝大多数都能由快照 + 本局演算自动推出来；
#       但偶尔会想手工塞几个节点（比如本局拿到了一个新的 KaleidxScope 门）。
#       与其去改 build_user_all 的代码，不如直接把那段 JSON 传进来。
#
#   UpsertUserAll(user_id, playlog_id, ...,
#                 extra_data={
#                     "userKaleidxScopeList": [{...}],
#                     "isNewKaleidxScopeList": "1",
#                 })
#
# ★ 合并规则：
#     1. 键必须是 36 个节点之一（含 11 条 isNew* 位串），否则明确报错并列出可用名
#     2. 值按该节点的形态强制转换（coerce_node_value），传错形态立刻抛 PatchError
#     3. 优先级最高 —— 覆盖快照演算出来的同名字段
#     4. 给了数组却没给对应位串 -> 按长度补 "0" 并给出提示（"0" = 存量更新）

def load_extra_data(extra: Any) -> Dict[str, Any]:
    """
    把「额外 JSON」规整成 dict。

    接受四种形态：
        None                      -> {}
        dict                      -> 原样返回
        JSON 字符串               -> json.loads
        文件路径（.json / .txt）   -> 读文件后 json.loads

    ★ 判断顺序：先看是不是 dict，再看字符串是不是「存在的文件路径」，
      最后才当作 JSON 文本解析 —— 这样两种字符串写法都能用。
    """
    if extra is None:
        return {}
    if isinstance(extra, dict):
        return extra
    if isinstance(extra, (bytes, bytearray)):
        extra = extra.decode("utf-8")
    if isinstance(extra, str):
        text = extra.strip()
        if not text:
            return {}
        # 像路径且文件存在 -> 读文件
        if len(text) < 4096 and "\n" not in text and "{" not in text:
            try:
                if os.path.isfile(text):
                    with open(text, "r", encoding="utf-8") as fh:
                        text = fh.read()
            except (OSError, ValueError):
                pass
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise PatchError("extra_data 既不是合法 JSON 也不是可读文件："
                             + str(exc)) from exc
        if not isinstance(data, dict):
            raise PatchError("extra_data 解析出来必须是 JSON 对象（{...}），"
                             "实际是 " + type(data).__name__)
        return data
    raise PatchError("extra_data 只支持 dict / JSON 字符串 / JSON 文件路径，"
                     "收到 " + type(extra).__name__)


def merge_extra_data(
    user_all: Dict[str, Any],
    extra_data: Optional[Any] = None,
) -> List[str]:
    """
    把外部 JSON 合并进 upsertUserAll 的 36 节点（就地修改）。

    参数：
        user_all:    build_user_all() 的产物
        extra_data:  见 load_extra_data

    返回：
        合并说明（每条一行，供日志打印）

    异常：
        PatchError: 出现未知节点名 / 值形态不对
    """
    data = load_extra_data(extra_data)
    if not data:
        return []

    notes: List[str] = []

    # ---- 1. 先整体校验键名，避免改了一半才发现写错 ----
    unknown = [k for k in data if k not in NODE_TYPES]
    if unknown:
        raise PatchError(
            "extra_data 里有未知节点名：" + ", ".join(map(str, unknown))
            + "\n  可用节点（36 个）：" + ", ".join(NODE_ORDER)
        )

    # ---- 2. 逐个写入（coerce 会把形态掰正，形态不对就抛）----
    for node, value in data.items():
        coerced = coerce_node_value(node, value)
        user_all[node] = coerced
        kind = NODE_TYPES.get(node)
        if kind == "bits":
            notes.append("extra_data 写入位串 " + node + " = " + repr(coerced))
        elif isinstance(coerced, list):
            notes.append("extra_data 写入 " + node + "（" + str(len(coerced)) + " 条）")
        else:
            notes.append("extra_data 写入 " + node)

    # ---- 3. 给了数组但没给对应位串 -> 补长度并提示 ----
    for bits, arr in BITS_TO_ARRAY.items():
        if arr in data and bits not in data:
            items = user_all.get(arr) or []
            notes.append("  ⚠ 给了 " + arr + " 却没给 " + bits
                         + " —— 已按长度补 \"" + "0" * len(items) + "\""
                         + "（\"0\" = 存量更新；若是**新增**条目请显式传 \"1\"）")

    # ---- 4. 位串长度必须等于数组条数（真机硬约束）----
    sync_bits_to_arrays(user_all)

    # ---- 5. 保持 NODE_ORDER 顺序 ----
    for node in NODE_ORDER:
        if node not in user_all:
            user_all[node] = empty_node(node)

    return notes


# =============================================================================
# 十七、内部编排：抓快照 / 前置接口 / 落库回查
# =============================================================================

def _resolve_api_func(name: str, fallback: Any = None) -> Any:
    """
    优先取 api 包里那个**已套日志外壳**的函数。

    ★ 为什么要绕这一下：
        autowrap() 只替换 api/__init__.py 命名空间里的名字
        （见 log_setup.autowrap 的注释），模块内部的直接引用拿到的还是原始函数。
        UpsertUserAll 内部要调 GetNeedUserData / GetUserNewItemList / GetUserData，
        绕这一下它们才会像用户直接调用那样打印「=== xxx 开始运行 ===」，
        主脚本就完全不用自己写日志了。
    """
    try:
        import api as _pkg                       # 延迟导入，避免模块级循环
        fn = getattr(_pkg, name, None)
        if callable(fn):
            return fn
    except Exception:
        pass
    return fallback


def _lazy(name: str) -> Any:
    """按名字延迟取 api 子模块里的原始函数（_resolve_api_func 的兜底）。"""
    if name == "GetNeedUserData":
        from .get_need_user_data import GetNeedUserData
        return GetNeedUserData
    if name == "GetUserNewItemList":
        from .get_user_new_item import GetUserNewItemList
        return GetUserNewItemList
    if name == "GetUserData":
        from .get_user_data import GetUserData
        return GetUserData
    if name == "GetUserMusicDetailAll":
        from .get_user_music import GetUserMusicDetailAll
        return GetUserMusicDetailAll
    raise PatchError("未知的内部 api：" + str(name))


def resolve_api_func(name: str) -> Any:
    """
    取「带日志外壳的优先、原始函数兜底」的可调用对象。

    ★ 供本模块内部与其它 api 模块（如 upsert_user_chargelog）复用：
      这样内部调用也会像用户直接调用那样打印「=== xxx 开始运行 ===」。
    """
    fn = _resolve_api_func(name)
    return fn if callable(fn) else _lazy(name)


#: 模块内旧名，保持兼容
_api = resolve_api_func


def verify_upsert_landing(
    user_id: int,
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
    *,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> bool:
    """
    发包后重新拉服务器数据，确认**真的写进去了**。

    ★ 为什么不看 returnCode 就完事：
        服务端对 userData 是整表覆盖语义 —— 报文不对时它照样回 returnCode=1，
        但写进去的还是旧值。唯一可靠的判据是重新拉一次数据看数字有没有动。

    参数：
        user_id:  用户 ID
        snapshot: 发包前的基线快照（用来对比）
        play:     本局数据（用来定位要检查的曲目）

    返回：
        True = 判定为落库成功
    """
    p = play or build_play_from_config()
    base = normalize_snapshot(snapshot)
    before_ud = (base.get("userData") or [{}])[0] if base.get("userData") else {}

    try:
        after_raw = _api("GetUserData")(user_id, client_id=client_id,
                                     timeout_ms=timeout_ms, client=client)
        after_ud = (after_raw.get("userData") or {}) if isinstance(after_raw, dict) else {}
    except Exception as exc:
        log_warning("落库回查失败（不影响上传结果）：" + str(exc))
        return False

    log_info("  playCount        "
             + str(before_ud.get("playCount")) + " -> " + str(after_ud.get("playCount")))
    log_info("  currentPlayCount "
             + str(before_ud.get("currentPlayCount")) + " -> "
             + str(after_ud.get("currentPlayCount")))
    log_info("  lastPlayDate     "
             + str(before_ud.get("lastPlayDate")) + " -> "
             + str(after_ud.get("lastPlayDate")))

    # 本局曲目的 playCount
    try:
        music_raw = _api("GetUserMusicDetailAll")(user_id, client_id=client_id,
                                               timeout_ms=timeout_ms, client=client)
        rows = music_raw.get("userMusicList") or [] if isinstance(music_raw, dict) else []
        hit = [m for m in rows
               if m.get("musicId") == p.music_id and m.get("level") == p.music_level]
        log_info("  musicId=" + str(p.music_id) + " level=" + str(p.music_level)
                 + " playCount -> " + (str(hit[0].get("playCount")) if hit else "(查不到)"))
    except Exception as exc:
        log_warning("  曲目明细回查失败：" + str(exc))

    # ★ 判定依据随增量走：
    #   增量 > 0 -> playCount 应当变大（原来的判据）
    #   增量 = 0 -> playCount 本来就不该变，改用 lastPlayDate 是否更新来判断
    _pc_gain = int(getattr(p, "user_play_count_gain", 0) or 0)
    if _pc_gain:
        ok = (int(after_ud.get("playCount") or 0)
              > int(before_ud.get("playCount") or 0))
        detail = "userData.playCount 已 +" + str(_pc_gain)
    else:
        _b_lpd = str(before_ud.get("lastPlayDate") or "")
        _a_lpd = str(after_ud.get("lastPlayDate") or "")
        ok = bool(_a_lpd) and _a_lpd != _b_lpd
        detail = "userData.lastPlayDate " + _b_lpd + " -> " + _a_lpd

    if ok:
        log_info("【落库成功】" + detail)
    else:
        log_error("【疑似未落库】" + detail + "，"
                  "请对照 docs/UpsertUserAll踩坑清单.md 排查")
        if not _pc_gain:
            log_warning("  提示：PLAY_USER_PLAY_COUNT_GAIN=0 时 playCount 不变属正常，"
                        "此处看的是 lastPlayDate；若刚上传的就是同一局，"
                        "lastPlayDate 本来就可能相等（假阴性）")
    return ok


# =============================================================================
# 十八、主函数
# =============================================================================

def UpsertUserAll(
    user_id: int,
    playlog_id: int,
    *,
    login_date_time: int,
    auth_date_time: Optional[int] = None,
    token: str = "",
    snapshot: Optional[Any] = None,
    auto_snapshot: bool = True,
    auto_characters: bool = True,
    play: Optional[PlayData] = None,
    extra_data: Optional[Any] = None,
    patch: Optional[Dict[str, Any]] = None,
    user_playlog_list: Optional[List[Any]] = None,
    pre_new_item_list: bool = True,
    verify_landing: bool = True,
    is_event_mode: bool = False,
    is_free_play: bool = False,
    confirm: Optional[bool] = None,
    dry_run: bool = False,
    cooldown_sec: Optional[float] = None,
    place_id: int = PLACE_ID,
    place_name: str = PLACE_NAME,
    region_id: int = REGION_ID,
    region_name: str = REGION_NAME,
    client_id: str = CLIENT_ID,
    play_date_time: Optional[int] = None,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Union[UserAllRequestVO, UpsertResponseVO]:
    """
    上传一局成绩（UpsertUserAllApi，★ 有副作用）—— **一个函数跑完整条结算链路**。

    ★ 内部依次做这些事，主脚本只调它一次就行：
        1. 抓基线快照（没传 snapshot 时自动抓，需要 token）
        2. 从快照推本局 5 只角色（auto_characters）
        3. 构造本局成绩明细 userPlaylogList
        4. 调前置接口 GetUserNewItemListApi（pre_new_item_list）
        5. 组装 upsertUserAll 的 36 节点（快照基线 + 本局演算 + 差分）
        6. 合并 extra_data 里的外部 JSON
        7. 发包前自检
        8. 冷却 → 真实发包
        9. 落库回查（verify_landing）

    参数：
        user_id:         用户 ID（必填）
        playlog_id:      本次登录 ID（必填，★ 必须 == UserLoginApi 的 loginId）
        login_date_time: 登录时刻（必填，★ 必须 == UserLoginApi 的 loginDateTime）
        auth_date_time:  UserLoginApi 请求里的 dateTime（可选；
                         userData.dateTime 要用它，真机实测两处一致）
        token:           会话令牌（可选）。★ 只在「没传 snapshot 且 auto_snapshot=True」
                         时需要 —— 内部用它自动调 GetNeedUserData。
        snapshot:        基线快照（可选，见 normalize_snapshot）。
                         传了就用它；不传则按 auto_snapshot 自动抓。
                         ★ 服务器对 userData 是整表覆盖、对差分节点是「只回传变化项」，
                           没有基线快照就等于告诉服务端「本局什么都没变」。
        auto_snapshot:   True（默认）= 没传 snapshot 时自动抓一份。
        auto_characters: True（默认）= 从快照的 userData.charaSlot +
                         userCharacterList 推出本局 5 只角色（**游玩前**等级）。
                         这样 config.PLAY_CHARACTERS 过期也不影响。
        play:            本局数据（可选，默认按 config.PLAY_*）
        extra_data:      ★ 额外 JSON，自动匹配插入 upsertUserAll 的 36 个节点。
                         接受 dict / JSON 字符串 / JSON 文件路径，例如：
                             extra_data={"userKaleidxScopeList": [{...}],
                                         "isNewKaleidxScopeList": "1"}
                         优先级最高（覆盖快照演算出的同名字段）。
                         没给位串时会按数组长度补 "0" 并给出提示。
        patch:           同 extra_data 的旧接口（只收 dict，不补位串提示）。
        user_playlog_list: 本局成绩明细（可选；不传则用 play 自动构造一条）
        pre_new_item_list: True（默认）= 发包前先调 GetUserNewItemListApi
                         （真机行为：结算上报前约 8 秒调它）。失败不阻断。
        verify_landing:  True（默认）= 发包后重新拉服务器数据，确认真的写进去了。
                         ★ 服务端返回 returnCode=1 不代表数据被应用，这一步才是验收标准。
        is_event_mode:   活动模式标志（可选）
        is_free_play:    免费游玩标志（可选）
        confirm:         副作用闸门；None 时取 config.UPSERT_CONFIRM
        dry_run:         True = 只构造并返回报文，绝不发包
        cooldown_sec:    真实发包前的冷却秒数（仅 confirm=True 生效；
                         None = 取 config.UPSERT_SEND_COOLDOWN_SEC，传 0 跳过）
        play_date_time:  ★ 本局**游玩/上报时刻**（可选，同 loginDateTime 格式）。
                         真机里 userData.lastPlayDate / userGamePlaylogList.playDate /
                         userPlaylogList.userPlayDate 都是「打完那一刻」，与登录时刻不同。
                         **不传就自动取「现在」**（login_date_time_now()）。
        timeout_ms:      超时毫秒（默认 60 秒）
        client:          可复用的 MaimaiNetClient（可选）

    返回：
        dry_run=True  -> UserAllRequestVO
        dry_run=False -> UpsertResponseVO
    """
    log_info("上传成绩：user_id=" + str(user_id) + " playlog_id=" + str(playlog_id)
             + " dry_run=" + str(dry_run))

    if not login_date_time:
        raise ValueError("缺少 login_date_time：必须传 UserLoginApi 的 loginDateTime"
                         "（PacketUpsertUserAll.cs:31）")

    # ---------- 阶段 1：基线快照（差分的前提）----------
    if snapshot is None and auto_snapshot:
        if not token:
            log_warning("既没传 snapshot 也没传 token —— 无法自动抓基线快照。"
                        "差分节点会是空的，服务端可能认为本局无变化。"
                        "推荐传 token=...（自动抓）或 snapshot=...（自己抓好传进来）")
        else:
            log_info("未传 snapshot，自动抓取结算基线快照 ...")
            snapshot = _api("GetNeedUserData")(
                user_id, token=token, client_id=client_id,
                place_id=place_id, region_id=region_id, client=client,
            )

    # ---------- 阶段 2：本局数据 ----------
    p = play or build_play_from_config()
    if auto_characters:
        derived = derive_play_characters(snapshot, p)
        if derived and any(c.get("characterId") for c in derived):
            p.characters = derived
            log_info("角色快照取自服务器快照："
                     + " / ".join(str(c["characterId"]) + ":" + str(c["level"])
                                  for c in derived))

    # 游玩/上报时刻：不传就取「现在」
    play_now = int(play_date_time) if play_date_time else login_date_time_now()

    # ---------- 阶段 3：本局成绩明细 ----------
    if user_playlog_list is None:
        user_playlog_list = [
            build_user_playlog(playlog_id, login_date_time, p,
                               place_id=place_id, place_name=place_name,
                               client_id=client_id, play_date=play_now)
        ]

    # ---------- 阶段 4：前置 GetUserNewItemListApi ----------
    if pre_new_item_list:
        try:
            post_user_data = build_post_play_user_data(
                snapshot=snapshot, play=p,
                login_date_time=login_date_time, auth_date_time=auth_date_time,
                place_id=place_id, place_name=place_name,
                region_id=region_id, region_name=region_name, client_id=client_id,
                play_date_time=play_now,
            )
            _api("GetUserNewItemList")(
                user_id, version=p.version_int,
                user_data=[post_user_data],
                user_playlog_list=list(user_playlog_list),
                client_id=client_id, timeout_ms=timeout_ms, client=client,
            )
        except Exception as exc:
            log_warning("GetUserNewItemListApi 失败（不阻断结算）：" + str(exc))

    # ---------- 阶段 5：组装 upsertUserAll（快照基线 + 本局演算 + 差分）----------
    user_all = build_user_all(
        snapshot=snapshot, play=p, patch=patch, extra_data=extra_data,
        login_date_time=login_date_time, auth_date_time=auth_date_time,
        place_id=place_id, place_name=place_name,
        region_id=region_id, region_name=region_name, client_id=client_id,
        playlog_id=playlog_id, play_date_time=play_now,
    )

    # ---------- 阶段 7：构造请求 ----------
    req = UserAllRequestVO(
        userId=user_id,
        playlogId=playlog_id,
        isEventMode=bool(is_event_mode or p.is_event_mode),
        isFreePlay=bool(is_free_play),
        loginDateTime=int(login_date_time),
        userPlaylogList=list(user_playlog_list),
        upsertUserAll=user_all,
    )

    # ---------- 阶段 8：自检 ----------
    for pl in req.userPlaylogList:
        if isinstance(pl, dict):
            for problem in validate_user_playlog(pl):
                log_warning("[成绩自检] " + problem)

    problems = validate_before_send(req, play=p)
    if problems:
        log_warning("【发包前自检】发现 " + str(len(problems)) + " 处可能不符合源码逻辑：")
        for item in problems:
            log_warning("    - " + item)
        log_warning("服务端可能返回 returnCode=1 但**不真正落库**，请逐条核对")
    else:
        log_info("发包前自检通过")

    # ---------- 阶段 9：dry-run ----------
    if dry_run:
        log_info("[dry-run] 已构造请求报文，未发包")
        log_debug("dry-run 报文：" + json.dumps(req, ensure_ascii=False, default=str))
        return req

    # ---------- 阶段 10：副作用闸门 ----------
    effective = UPSERT_CONFIRM if confirm is None else bool(confirm)
    if not effective:
        msg = ("UpsertUserAllApi 是**有副作用**的接口（会把本局成绩真实写进服务器，不可撤销）。"
               "本脚本默认不放行。确认要发请传 confirm=True，"
               "或改 config.UPSERT_CONFIRM = True。只想看报文请传 dry_run=True。")
        log_error(msg)
        raise ConfirmRequiredError(msg)

    # ---------- 阶段 11：冷却 ----------
    wait_send_cooldown(
        UPSERT_SEND_COOLDOWN_SEC if cooldown_sec is None else cooldown_sec,
        label="上传成绩",
    )

    # ---------- 阶段 12：发包 ----------
    log_info("闸门已放行，开始上传成绩 ...")
    raw = request_dict(
        "UpsertUserAllApi", req,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_LONG_MS, client=client,
    )

    resp = UpsertResponseVO(
        returnCode=int(raw.get("returnCode", 0) or 0),
        apiName=str(raw.get("apiName", "") or ""),
    )
    if resp.returnCode != 1:
        msg = "上传成绩失败：returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName
        log_error(msg)
        raise UpsertUserAllError(msg)

    log_info("上传成绩成功：returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName)

    # ---------- 阶段 13：落库回查（★ 真正的验收标准）----------
    if verify_landing:
        verify_upsert_landing(user_id, snapshot, p,
                              client_id=client_id, timeout_ms=timeout_ms, client=client)

    return resp


# =============================================================================
# 十九、单独运行（调试）
# =============================================================================

if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("upsert_user_all_test")
        try:
            log_info("构造一条 playlog 并做自检（不发包）")
            pl = build_user_playlog(7692848101484135861, 1791159576)
            problems = validate_user_playlog(pl)
            if problems:
                for item in problems:
                    log_warning("  - " + item)
            else:
                log_info("playlog 自检通过（110 字段齐全）")

            log_info("字段数：" + str(len(pl)) + " / 期望 " + str(len(PLAYLOG_FIELDS)))
            log_info("判定总数：" + str(sum(
                int(pl.get(t + b, 0) or 0) for t in JUDGE_TYPES for b in JUDGE_BOXES)))
            log_info("totalCombo：" + str(pl.get("totalCombo")))
            return 0
        finally:
            teardown_logging()

    raise SystemExit(_main())
