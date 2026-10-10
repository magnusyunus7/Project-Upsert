# -*- coding: utf-8 -*-
"""
get_need_user_data. py — settlement snapshot orchestration(systemOnecalluseScripts for each fetch)
================================================================================

Features: One-click grab UpsertUserAll needofAllBaselinedata, text"nodesDictionary".

-**Choreography only**, The fetching logic is all in their own api scriptin(get_user_data. py / get_user_map. py …).

--------------------------------------------------------------------------------
Why snapshots are needed
--------------------------------------------------------------------------------
server response. userData is**overwrite**semantic, Pair differential nodes are**Only return variations**semantic.
mustputthis gameofVariationcurrentoutMust have one first"logintimeofserver"As baseline,
and then superimpose the impact of the game on the baseline. — thisisSnapshotofuse.

real machineControl(source/2026-10-05. log):

  | nodes        | Get Side(Baseline)  | Upsert Side(this gameAfter) |
  |---------------------|-------------------|----------------------|
  | userData. playCount | 1257       | 1258    (+1)   |
  | userMapList     | 104 item      | Only 1 item(distance Change)|
  | userMusicDetailList | 739 group      | Only 1 item(playCount+1)|
  | userItemList    | 1070 item      | [](noVariation)     |

--------------------------------------------------------------------------------
call exampleExample
--------------------------------------------------------------------------------
  from api import GetNeedUserData

  snapshot = GetNeedUserData(user_id, token=token)
  # Then pass it directly to UpsertUserAll(snapshot=snapshot,...)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from config import CLIENT_ID, PLACE_ID, PLAY_SHOP_ITEM_IDS, REGION_ID, TIMEOUT_MS

from .log_setup import log_debug, log_info, log_warning
from .maimai_net import MaimaiNetClient

# Scripts for each fetch(one interface, one script)
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
# fall<Engineering Root>/data/<userId>. json
# =============================================================================

#: Engineering Root Directory(fileat <root>/api/ Down)
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

#: userdata<Engineering Root>/data
DATA_DIR: Path = PROJECT_ROOT / "data"


def user_data_path(user_id: int) -> Path:
    """userdataoffall<Engineering Root>/data/<userId>. json"""
    return DATA_DIR / (str(int(user_id)) + ". json")


def save_user_data(snapshot: Dict[str, Any], user_id: int,
                   path: Optional[str] = None) -> str:
    """
  put GetNeedUserData toofdatato <Engineering Root>/data/<userId>. json.

  - **dataisoverwritedata**(Not Append, It's not a merger).
  - AbsentMeetings

  Parameter:
    snapshot: GetNeedUserData ofreturnsValue
    user_id: user ID(Decide file name)
    path:  (Optional, default data/<userId>. json)

  Returns: File path actually written
  """
    target = Path(path) if path else user_data_path(user_id)
    try:
        os.makedirs(str(target.parent), exist_ok=True)
        with open(str(target), "w", encoding="utf-8") as fp:
            json.dump(snapshot, fp, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        log_warning("userdatafallFailed(Does not affect this run):" + str(exc))
        return str(target)
    size = 0
    try:
        size = os.path.getsize(str(target))
    except Exception:
        pass
    log_info("userdataAlready(overwrite):" + str(target) + " " + str(size) + " Bytes")
    return str(target)


def load_user_data(user_id: int, path: Optional[str] = None) -> Dict[str, Any]:
    """
  readtimes <Engineering Root>/data/<userId>. json.

  findNotofiletimeraise FileNotFoundError(calluseDecisionmustDon'tFallback tofetch).
  """
    target = Path(path) if path else user_data_path(user_id)
    if not target.exists():
        raise FileNotFoundError("userdatafileAbsent:" + str(target))
    with open(str(target), "r", encoding="utf-8") as fp:
        data = json.load(fp)
    log_info("userdataLoaded:" + str(target))
    return data


def list_saved_user_ids() -> List[int]:
    """List data/ All saved under userId(pressfileFirst nameparse, skipparseFailedof)."""
    if not DATA_DIR.exists():
        return []
    out: List[int] = []
    for name in os.listdir(str(DATA_DIR)):
        if not name.endswith(". json"):
            continue
        try:
            out.append(int(name[:-5]))
        except ValueError:
            continue
    return sorted(out)


#: defaultmustofnodes(orderi. e. fetchorder)
#: - Columns only UpsertUserAll currentneedof; Showcaseinterface(text/text/Competition…)Not in this column.
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
  fetchsettlementallBaselinedata.

  Parameter:
    user_id:    user ID(Required)
    token:     Session Token(Optional, Most fetch interfaces do not require)
    client_id:   machine stateshortValue
    place_id:   Store ID
    region_id:   Area ID
    shop_item_ids: Store Product List(Optional, default config. PLAY_SHOP_ITEM_IDS)
    nodes:     mustofnodes(Optional, default DEFAULT_SNAPSHOT_NODES)
    timeout_ms:  timeout milliseconds
    client:    Reusable MaimaiNetClient
    strict:    True = Exception thrown if either interface fails;
            False(default)= recordFailedskip, Ensure that the link does not collapse
    save:     True(default)= fallto <Engineering Root>/data/<userId>. json
            (- dataisoverwritedata)
    save_path:   fall(Optional, Ignore save ofdefaultThen)

  Returns:
    {
     "userData":    <GetUserDataApi Raw Response>,
     "userExtend":   <GetUserExtendApi Raw Response>,
     "userMapList":  {"userMapList": [...]},    # Flattened/text
     "userMusicDetailList": {"userMusicList": [...]},# Flattened into single strips
...
     "_failed": [ {"node":.., "error":..},... ]
    }
    thisPieceYesdirectlyPass to UpsertUserAll(snapshot=...), Alternatively json fall
  """
    wanted = list(nodes) if nodes else list(DEFAULT_SNAPSHOT_NODES)
    log_info("fetchsettlement snapshot: user_id=" + str(user_id) + " nodesnumber=" + str(len(wanted)))

    raw: Dict[str, Any] = {}
    failed: List[Dict[str, str]] = []

    def _call(node: str, fn, *args, **kwargs):
        """nodesFailure of a single interface does not affect the overall."""
        try:
            raw[node] = fn(*args, **kwargs)
            return True
        except Exception as exc:
            failed.append({"node": node, "error": type(exc).__name__ + ": " + str(exc)})
            log_warning("nodes " + node + " Fetch failed:" + type(exc).__name__ + ": " + str(exc))
            if strict:
                raise
            return False

    common = dict(client_id=client_id, timeout_ms=timeout_ms, client=client)

    # ---- itemfetch(orderAnd DEFAULT_SNAPSHOT_NODES Match)----
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
        # - theinterfaceBeltOne**Original** itemKind Copy(_raw),
        #  For UpsertUserAll isNewFavoriteList For bit strings
        #  — real machine itemKind=10 back is null, currentisGenerateIn the bit string "1".
        if _call("userFavoriteList", GetUserFavoriteAll, user_id, **common):
            fav_raw = (raw.get("userFavoriteList") or {}).get("_raw")
            if fav_raw:
                raw["_raw_favorite"] = fav_raw

    if "userActivityList" in wanted:
        _call("userActivityList", GetUserActivity, user_id, **common)

    if "userMissionDataList" in wanted:
        # - theinterfaceofResponding toSametimeBelt userWeeklyData(Perimeter),
        #  It is Upsert Side userWeeklyData nodesofwill be automatically extracted.
        _call("userMissionDataList", GetUserMissionData, user_id, **common)

    if "userIntimateList" in wanted:
        _call("userIntimateList", GetUserIntimate, user_id, **common)

    if "userShopItemStockList" in wanted:
        ids = list(shop_item_ids) if shop_item_ids is not None else list(PLAY_SHOP_ITEM_IDS)
        if ids:
            _call("userShopItemStockList", GetUserShopStock, user_id,
                  shop_item_id_list=ids, **common)
        else:
            log_debug("not PLAY_SHOP_ITEM_IDS, skipInventorynodes")

    if "userFavoritemusicList" in wanted:
        _call("userFavoritemusicList", GetUserFavoriteItemAll, user_id, 1, **common)

    if "userKaleidxScopeList" in wanted:
        _call("userKaleidxScopeList", GetUserKaleidxScope, user_id, **common)

    if "userGhost" in wanted:
        _call("userGhost", GetUserGhost, user_id, **common)

    raw["_failed"] = failed
    raw["_userId"] = int(user_id)
    log_info("settlement snapshotfetchDone: Success " + str(len(raw) - 2) + " nodes, Failed "
             + str(len(failed)) + " Piece")

    # - fall<Engineering Root>/data/<userId>. json(overwrite)
    if save or save_path:
        try:
            save_user_data(raw, user_id, path=save_path)
        except Exception as exc:
            log_warning("userdatafallFailed(Does not affect this run):" + str(exc))

    return raw


def save_snapshot(snapshot: Dict[str, Any], path: str) -> str:
    """putSnapshotto JSON file(Easy to reuse offline / Manual Reconciliation)."""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(snapshot, fp, ensure_ascii=False, indent=2, default=str)
    log_info("Snapshot saved:" + path)
    return path


def load_snapshot(path: str) -> Dict[str, Any]:
    """From JSON filereadtimesSnapshot."""
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    log_info("Snapshot loaded:" + path)
    return data


def summarize_snapshot(snapshot: Dict[str, Any]) -> Dict[str, int]:
    """
  systemcountSnapshotEachnodesofitemnumber, Convenient for quick checks(returns {nodesFirst name: itemnumber}).

  itemnumberMeaning:
    userData thisArray of elements -> 1
    userMusicDetailList thislist -> afterofitemnumber
  """
    out: Dict[str, int] = {}
    for node, value in (snapshot or {}).items():
        if node.startswith("_"):
            continue
        if isinstance(value, list):
            out[node] = len(value)
        elif isinstance(value, dict):
            # Pick list from response
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
# Run separately(debug)
# =============================================================================

if __name__ == "__main__":
    import sys

    from .log_setup import log_error, setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("get_need_user_data_test")
        try:
            if len(sys.argv) < 2:
                print("usage: python -m api. get_need_user_data <user_id> [--token TOKEN] [--save]")
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
                print("  " + node.ljust(28) + "= " + str(count) + " item")
            if save_path:
                save_snapshot(snap, save_path)
            return 0
        except Exception as exc:
            log_error("fetchSnapshotFailed:" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
