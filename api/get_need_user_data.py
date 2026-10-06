# -*- coding: utf-8 -*-
"""
get_need_user_data.py —— 结算快照编排（统一调用各取数脚本）
================================================================================

功能：一键抓取 UpsertUserAll 需要的全部基线数据，整理成「节点字典」。

★ 本模块**只做编排**，取数逻辑都在各自的 api 脚本里（get_user_data.py / get_user_map.py …）。

--------------------------------------------------------------------------------
为什么需要快照
--------------------------------------------------------------------------------
服务器对 userData 是**整表覆盖**语义，对差分节点是**只回传变化项**语义。
要把本局的变化正确表达出来，必须先有一份「登录时的服务器状态」作基线，
再把本局的影响叠加到基线上 —— 这就是快照的作用。

真机对照（source/2026-10-05.log）：

    | 节点                | Get 侧（基线）    | Upsert 侧（本局后）  |
    |---------------------|-------------------|----------------------|
    | userData.playCount  | 1257              | 1258        (+1)     |
    | userMapList         | 104 条            | 仅 1 条（distance 变）|
    | userMusicDetailList | 739 组            | 仅 1 条（playCount+1）|
    | userItemList        | 1070 条           | []（无变化）         |

--------------------------------------------------------------------------------
调用示例
--------------------------------------------------------------------------------
    from api import GetNeedUserData

    snapshot = GetNeedUserData(user_id, token=token)
    # 之后直接传给 UpsertUserAll(snapshot=snapshot, ...)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from config import CLIENT_ID, PLACE_ID, PLAY_SHOP_ITEM_IDS, REGION_ID, TIMEOUT_MS

from .log_setup import log_debug, log_info, log_warning
from .maimai_net import MaimaiNetClient

# 各取数脚本（一个接口一个脚本）
from .get_user_data import GetUserData
from .get_user_extend import GetUserExtend
from .get_user_option import GetUserOption
from .get_user_character import GetUserCharacter
from .get_user_ghost import GetUserGhost
from .get_user_map import GetUserMapAll
from .get_user_login_bonus import GetUserLoginBonusAll
from .get_user_rating import GetUserRating
from .get_user_item import GetUserItemAll
from .get_user_music import GetUserMusicDetailAll
from .get_user_course import GetUserCourseAll
from .get_user_charge import GetUserCharge
from .get_user_favorite import GetUserFavoriteAll
from .get_user_activity import GetUserActivity
from .get_user_mission import GetUserMissionData
from .get_user_intimate import GetUserIntimate
from .get_user_shop_stock import GetUserShopStock
from .get_user_favorite_item import GetUserFavoriteItemAll
from .get_user_kaleidx_scope import GetUserKaleidxScope


# =============================================================================
# 落盘目录：<工程根>/data/<userId>.json
# =============================================================================

#: 工程根目录（本文件在 <root>/api/ 下）
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

#: 用户数据目录：<工程根>/data
DATA_DIR: Path = PROJECT_ROOT / "data"


def user_data_path(user_id: int) -> Path:
    """用户数据的落盘路径：<工程根>/data/<userId>.json"""
    return DATA_DIR / (str(int(user_id)) + ".json")


def save_user_data(snapshot: Dict[str, Any], user_id: int,
                   path: Optional[str] = None) -> str:
    """
    把 GetNeedUserData 抓到的数据写到 <工程根>/data/<userId>.json。

    ★ **新数据总是覆盖老数据**（不是追加、也不是合并）。
    ★ 目录不存在会自动创建。

    参数：
        snapshot: GetNeedUserData 的返回值
        user_id:  用户 ID（决定文件名）
        path:     自定义路径（可选，默认走 data/<userId>.json）

    返回：实际写入的文件路径
    """
    target = Path(path) if path else user_data_path(user_id)
    try:
        os.makedirs(str(target.parent), exist_ok=True)
        with open(str(target), "w", encoding="utf-8") as fp:
            json.dump(snapshot, fp, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        log_warning("用户数据落盘失败（不影响本次运行）：" + str(exc))
        return str(target)
    size = 0
    try:
        size = os.path.getsize(str(target))
    except Exception:
        pass
    log_info("用户数据已保存（覆盖）：" + str(target) + "  " + str(size) + " 字节")
    return str(target)


def load_user_data(user_id: int, path: Optional[str] = None) -> Dict[str, Any]:
    """
    读回 <工程根>/data/<userId>.json。

    找不到文件时抛 FileNotFoundError（调用方自行决定要不要回退到联网抓取）。
    """
    target = Path(path) if path else user_data_path(user_id)
    if not target.exists():
        raise FileNotFoundError("用户数据文件不存在：" + str(target))
    with open(str(target), "r", encoding="utf-8") as fp:
        data = json.load(fp)
    log_info("用户数据已加载：" + str(target))
    return data


def list_saved_user_ids() -> List[int]:
    """列出 data/ 下已保存的全部 userId（按文件名解析，跳过解析失败的）。"""
    if not DATA_DIR.exists():
        return []
    out: List[int] = []
    for name in os.listdir(str(DATA_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            out.append(int(name[:-5]))
        except ValueError:
            continue
    return sorted(out)


#: 默认要抓的节点（顺序即抓取顺序）
#: ★ 只列 UpsertUserAll 真正需要的；纯展示类接口（排行/活动/大会…）不在此列。
DEFAULT_SNAPSHOT_NODES: tuple = (
    "userData",
    "userExtend",
    "userOption",
    "userCharacterList",
    "userMapList",
    "userLoginBonusList",
    "userRatingList",
    "userItemList",
    "userMusicDetailList",
    "userCourseList",
    "userChargeList",
    "userFavoriteList",
    "userActivityList",
    "userMissionDataList",
    "userIntimateList",
    "userShopItemStockList",
    "userFavoritemusicList",
    "userKaleidxScopeList",
    "userGhost",
)


def GetNeedUserData(
    user_id: int,
    *,
    token: str = "",
    client_id: str = CLIENT_ID,
    place_id: int = PLACE_ID,
    region_id: int = REGION_ID,
    shop_item_ids: Optional[Sequence[int]] = None,
    nodes: Optional[Sequence[str]] = None,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
    strict: bool = False,
    save: bool = True,
    save_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    抓取结算所需的全部基线数据。

    参数：
        user_id:       用户 ID（必填）
        token:         会话令牌（可选，多数取数接口不需要）
        client_id:     机台短值
        place_id:      店铺 ID
        region_id:     区域 ID
        shop_item_ids: 商店商品清单（可选，默认 config.PLAY_SHOP_ITEM_IDS）
        nodes:         要抓的节点（可选，默认 DEFAULT_SNAPSHOT_NODES）
        timeout_ms:    超时毫秒
        client:        可复用的 MaimaiNetClient
        strict:        True = 任一接口失败就抛异常；
                       False（默认）= 记录失败并跳过，保证链路不崩
        save:          True（默认）= 抓完自动落盘到 <工程根>/data/<userId>.json
                       （★ 新数据总是覆盖老数据）
        save_path:     自定义落盘路径（可选，给了就忽略 save 的默认路径规则）

    返回：
        {
          "userData":       <GetUserDataApi 原始响应>,
          "userExtend":     <GetUserExtendApi 原始响应>,
          "userMapList":    {"userMapList": [...]},       # 已摊平/翻页
          "userMusicDetailList": {"userMusicList": [...]},# 已摊平成单条
          ...
          "_failed": [ {"node":.., "error":..}, ... ]
        }
        这个结构可以直接传给 UpsertUserAll(snapshot=...)，也可 json 落盘。
    """
    wanted = list(nodes) if nodes else list(DEFAULT_SNAPSHOT_NODES)
    log_info("抓取结算快照：user_id=" + str(user_id) + " 节点数=" + str(len(wanted)))

    raw: Dict[str, Any] = {}
    failed: List[Dict[str, str]] = []

    def _call(node: str, fn, *args, **kwargs):
        """逐节点容错：单个接口失败不影响整体。"""
        try:
            raw[node] = fn(*args, **kwargs)
            return True
        except Exception as exc:
            failed.append({"node": node, "error": type(exc).__name__ + ": " + str(exc)})
            log_warning("节点 " + node + " 抓取失败：" + type(exc).__name__ + ": " + str(exc))
            if strict:
                raise
            return False

    common = dict(client_id=client_id, timeout_ms=timeout_ms, client=client)

    # ---- 逐个抓取（顺序与 DEFAULT_SNAPSHOT_NODES 一致）----
    if "userData" in wanted:
        _call("userData", GetUserData, user_id, **common)

    if "userExtend" in wanted:
        _call("userExtend", GetUserExtend, user_id, **common)

    if "userOption" in wanted:
        _call("userOption", GetUserOption, user_id, **common)

    if "userCharacterList" in wanted:
        _call("userCharacterList", GetUserCharacter, user_id, **common)

    if "userMapList" in wanted:
        _call("userMapList", GetUserMapAll, user_id, **common)

    if "userLoginBonusList" in wanted:
        _call("userLoginBonusList", GetUserLoginBonusAll, user_id, **common)

    if "userRatingList" in wanted:
        _call("userRatingList", GetUserRating, user_id, **common)

    if "userItemList" in wanted:
        _call("userItemList", GetUserItemAll, user_id, **common)

    if "userMusicDetailList" in wanted:
        _call("userMusicDetailList", GetUserMusicDetailAll, user_id, **common)

    if "userCourseList" in wanted:
        _call("userCourseList", GetUserCourseAll, user_id, **common)

    if "userChargeList" in wanted:
        _call("userChargeList", GetUserCharge, user_id, **common)

    if "userFavoriteList" in wanted:
        # ★ 该接口额外带一份**原始** itemKind 副本（_raw），
        #   供 UpsertUserAll 生成 isNewFavoriteList 位串用
        #   —— 真机 itemKind=10 回的是 null，正是它产生了位串里的 "1"。
        if _call("userFavoriteList", GetUserFavoriteAll, user_id, **common):
            fav_raw = (raw.get("userFavoriteList") or {}).get("_raw")
            if fav_raw:
                raw["_raw_favorite"] = fav_raw

    if "userActivityList" in wanted:
        _call("userActivityList", GetUserActivity, user_id, **common)

    if "userMissionDataList" in wanted:
        # ★ 该接口的响应里同时带着 userWeeklyData（周界），
        #   它是 Upsert 侧 userWeeklyData 节点的来源，会被自动提取。
        _call("userMissionDataList", GetUserMissionData, user_id, **common)

    if "userIntimateList" in wanted:
        _call("userIntimateList", GetUserIntimate, user_id, **common)

    if "userShopItemStockList" in wanted:
        ids = list(shop_item_ids) if shop_item_ids is not None else list(PLAY_SHOP_ITEM_IDS)
        if ids:
            _call("userShopItemStockList", GetUserShopStock, user_id,
                  shop_item_id_list=ids, **common)
        else:
            log_debug("未配置 PLAY_SHOP_ITEM_IDS，跳过商店库存节点")

    if "userFavoritemusicList" in wanted:
        _call("userFavoritemusicList", GetUserFavoriteItemAll, user_id, 1, **common)

    if "userKaleidxScopeList" in wanted:
        _call("userKaleidxScopeList", GetUserKaleidxScope, user_id, **common)

    if "userGhost" in wanted:
        _call("userGhost", GetUserGhost, user_id, **common)

    raw["_failed"] = failed
    raw["_userId"] = int(user_id)
    log_info("结算快照抓取完成：成功 " + str(len(raw) - 2) + " 个节点，失败 "
             + str(len(failed)) + " 个")

    # ★ 落盘：<工程根>/data/<userId>.json（覆盖式）
    if save or save_path:
        try:
            save_user_data(raw, user_id, path=save_path)
        except Exception as exc:
            log_warning("用户数据落盘失败（不影响本次运行）：" + str(exc))

    return raw


def save_snapshot(snapshot: Dict[str, Any], path: str) -> str:
    """把快照写到 JSON 文件（便于离线复用 / 人工核对）。"""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snapshot, fp, ensure_ascii=False, indent=2, default=str)
    log_info("快照已保存：" + path)
    return path


def load_snapshot(path: str) -> Dict[str, Any]:
    """从 JSON 文件读回快照。"""
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    log_info("快照已加载：" + path)
    return data


def summarize_snapshot(snapshot: Dict[str, Any]) -> Dict[str, int]:
    """
    统计快照各节点的条数，便于快速核对（返回 {节点名: 条数}）。

    条数含义：
        userData 这类单元素数组 -> 1
        userMusicDetailList 这类列表 -> 摊平后的条数
    """
    out: Dict[str, int] = {}
    for node, value in (snapshot or {}).items():
        if node.startswith("_"):
            continue
        if isinstance(value, list):
            out[node] = len(value)
        elif isinstance(value, dict):
            # 从响应里挑出列表
            found = False
            for key, sub in value.items():
                if isinstance(sub, list):
                    out[node] = len(sub)
                    found = True
                    break
            if not found:
                out[node] = 1
        else:
            out[node] = 0
    return out


# =============================================================================
# 单独运行（调试）
# =============================================================================

if __name__ == "__main__":
    import sys

    from .log_setup import log_error, setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("get_need_user_data_test")
        try:
            if len(sys.argv) < 2:
                print("用法: python -m api.get_need_user_data <user_id> [--token TOKEN] [--save 路径]")
                return 1

            user_id = int(sys.argv[1])
            token = ""
            save_path = ""
            args = sys.argv[2:]
            i = 0
            while i < len(args):
                if args[i] == "--token" and i + 1 < len(args):
                    token = args[i + 1]
                    i += 2
                elif args[i] == "--save" and i + 1 < len(args):
                    save_path = args[i + 1]
                    i += 2
                else:
                    i += 1

            snap = GetNeedUserData(user_id, token=token)
            summary = summarize_snapshot(snap)
            print("")
            for node, count in summary.items():
                print("   " + node.ljust(28) + "= " + str(count) + " 条")
            if save_path:
                save_snapshot(snap, save_path)
            return 0
        except Exception as exc:
            log_error("抓取快照失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
