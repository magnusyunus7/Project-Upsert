# -*- coding: utf-8 -*-
"""
upsert_user_all. py — Upload Grades(UpsertUserAllApi)
================================================================================

Features: putone gameplayofFullsettlementdataserver. this is**The only one with side effects**ofinterface.

Corresponding interface: UpsertUserAllApi
request body: UserAllRequestVO(7 top-level fields + upsertUserAll of 36 nodes)
     source/Assembly-CSharp/Net. VO. Mai2/UserAllRequestVO. cs
     source/Assembly-CSharp/Net. Packet. Mai2/PacketUpsertUserAll. cs:22-35

--------------------------------------------------------------------------------
One, top-level(7 Field)
--------------------------------------------------------------------------------
  userId     user ID
  playlogId    - Required == UserLoginApi of loginId
  isEventMode   isNomode
  isFreePlay   isNoFreeplay
  loginDateTime  - Required == UserLoginApi of loginDateTime
  userPlaylogList this gameResultsdetails(110 Field × N item)
  upsertUserAll  36 Full amount of user data for nodes

  playlogId / loginDateTime allNointerfaceGenerateof, They come from UserLoginApi.
  Wrong login sent ID the server willdirectly; Changed login session midway Must login again.

--------------------------------------------------------------------------------
Two, upsertUserAll of 36 nodes(4 Morphology)
--------------------------------------------------------------------------------
Basis source/Assembly-CSharp/Net. VO. Mai2/UserAll. cs, and use the real machine message
source/2026-10-05. log:123 nodespresent.:

  Array of elements 4 Piece userData / userExtend / userOption / userRatingList
  Object    2 Piece userWeeklyData / user2pPlaylog   - Not an array
  Bitstring    11 Piece isNew*               length == Number of corresponding array entries
  numbergroup  19 Piece Remaining

  4 + 2 + 11 + 19 = 36

--------------------------------------------------------------------------------
Three,- ofSnapshot Baseline + this gamecalculate + Differential
--------------------------------------------------------------------------------
real machineNoput Get The entire table is returned as is., andis"Only return those few changes".
put source/2026-10-05. log inSame accountof Get Side vs. Upsert Side control:

  | nodes         | Get Side(logintime)   | Upsert Side(settlementtime)   |
  |-----------------------|----------------------|--------------------------|
  | userData. playCount  | 1257         | 1258    (+1)     |
  | userData. currentPlay | 185         | 186     (+1)     |
  | userMusicDetailList  | 143/level4 playCount=7 | 143/level4 playCount=8 |
  | userMapList      | 550003 distance=1424000 | distance=1435000 (+11000) |
  | userCharacterList   | 5 Only         | 5 Only, eachOnly level +1   |
  | userItemList     | 1070 item       | []     (noVariation)  |
  | userCourseList    | 16 item        | []     (noVariation)  |

  - **server response. userData isoverwritesemantic** — put Get Send back the old value as it came down,
   After Write"nothing happened", thisis"returnCode=1 But it fell into the vault"of
   Differential node if empty, serverAlsonooutthis gamehasAnyVariation.

  ⚠ ofdefaultValueAndUp(real machine)**hasdifferent**:
   config. PLAY_USER_PLAY_COUNT_GAIN = 0(default)
    -> userData. playCount / currentPlayCount **Stay the same**, Never engrave the real machine again +1.
    If you want to reproduce the real machine, change it to 1.
   Other incremental similarities: PLAY_MUSIC_PLAY_COUNT_GAIN / PLAY_MAP_DISTANCE_GAIN /
   PLAY_CHARACTER_EXP_GAIN defaultallis 0.

So the process for this module is:

  1. From snapshot(loginAfterof Get Response)Create**Baseline**
  2. pressthis game data(play)calculateout**text**, and count the differential nodes (- Baseline)
  3. use patch Do a precise overlay
  4. 11 itemBitstring(lengthpresent. corresponding array)

--------------------------------------------------------------------------------
Four, Safety gate
--------------------------------------------------------------------------------
interfacehasSide effects, default**no packet is sent**:

  UpsertUserAll(...)         -> raise ConfirmRequiredError(notPackaging)
  UpsertUserAll(..., dry_run=True)  -> Construct and return packets only
  UpsertUserAll(..., confirm=True)  -> realSend

See global switch config. UPSERT_CONFIRM.

--------------------------------------------------------------------------------
Five, call exampleExample
--------------------------------------------------------------------------------
  from api import (setup_logging, ParseQRCode, GetUserPreview, UserLogin,
           GetNeedUserData, UpsertUserAll, build_play_from_config)

  setup_logging("settlement")
  user_id, token = ParseQRCode(qr)
  GetUserPreview(user_id, token)
  login = UserLogin(user_id, token)

  # 1) loginAfterBaseline Snapshot(Benchmark of Difference)
  snapshot = GetNeedUserData(user_id, token=token)

  # 2) groupthis game data(defaultread config. py of PLAY_*)
  play = build_play_from_config()

  # 3) Read the message first
  req = UpsertUserAll(user_id, login. loginId,
            login_date_time=login. loginDateTime,
            snapshot=snapshot, play=play, dry_run=True)

  # 4) noafterrealUpload
  UpsertUserAll(user_id, login. loginId,
         login_date_time=login. loginDateTime,
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
    REGION_NAME,
    TIMEOUT_LONG_MS,
    UPSERT_CONFIRM,
    UPSERT_SEND_COOLDOWN_SEC,
)

# =============================================================================
# machine stateBit(Hara PLAY_SPECIAL_NUM,2026-10-06 sink to this module)
# =============================================================================
#
# Basis: source/Assembly-CSharp/Manager/GameManager. cs of CalcSpecialNum()
#    [CalcSpecialNum] = 1024  (SpecialAP=False IsFreedomMode=False)
#    1024 = 0x400, i. e. divide by"noitemBit"thatOneBitallfor 0 — currentisOneStagestandard ACA machine state.
#
#  - Reverse inference validation: real machine playSpecial = 892014272
#     Bit inversion32(892014272) = 57726124 = 27900 * 2069 + 1024
#     The remainder is just right 1024, with caught CalcSpecialNum Exact match.
PLAY_SPECIAL_NUM = 1024

#: - machine stateplaycountnumbernofromserverpressusermust**Constantly 2**
PLAY_LOCAL_PLAY_COUNT = 2

#: - afterGradeRank Constantly 1
PLAY_AFTER_GRADE_RANK = 1

#: - isNoat userMusicDetailList insame (musicId, level) beforeGrade / afterGrade.
#:  ⚠ source codeEmpiricalthisThreefieldsis**Bit(Dan)**(VOExtensions. cs:1419-1421),
#:   real machinenoBitAlways 0 / 0 / 1.
#:   False = **Always 0**(default, Consistent with the real machine — The user has confirmed that this)
#:   True = Push from track recordings(For debugging only)
DERIVE_GRADE_FROM_MUSIC_DETAIL = False

from .log_setup import log_debug, log_error, log_info, log_warning
from .maimai_net import (
    MaimaiNetClient,
    local_utc_offset_seconds,
    login_date_time_now,
    request_dict,
)


# =============================================================================
# Exceptions
# =============================================================================

class UpsertUserAllError(RuntimeError):
    """serverreturns returnCode!= 1."""


class ConfirmRequiredError(RuntimeError):
    """hasSide effectsofinterfaceSafety gateDown(time**notPackaging**)."""


class PatchError(ValueError):
    """nodesFirst nameornodesMorphologyNoLegal."""


# =============================================================================
# One,36 type table of nodes
# =============================================================================
#
#  "singleton": numbergroup, Heng 1 Element(userData / userExtend / userOption / userRatingList)
#  "object": - Single Object, Not an array(userWeeklyData / user2pPlaylog)
#  "array": numbergroup
#  "bits": String bit string, length == Number of corresponding array entries
#
NODE_TYPES: Dict[str, str] = {
    # ---- Array of elements(4)----
    "userData": "singleton",
    "userExtend": "singleton",
    "userOption": "singleton",
    "userRatingList": "singleton",
    # ---- Object, non-numbergroup(2)- ----
    "userWeeklyData": "object",
    "user2pPlaylog": "object",
    # ---- numbergroup(19)----
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
    # ---- Bitstring(11)----
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

#: Bitstring -> Corresponding array(Basis UserAll. cs ofFieldfirst nameAndreal-machine packetpresent.)
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

#: nodesatin one packetorder(UserAll. cs ofFieldDeclarationorder)
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

#: needcalculateDifferentialofnodes -> Primary Key Field(used forBitstringof "0"/"1")
#:
#: - Basis for Judgment = real machine Get Side vs. Upsert Number of bars on side comparison(source/2026-10-05. log):
#:
#:   | nodes        | Get Side | Upsert Side | isNoDifferential |
#:   |---------------------|--------|-----------|----------|
#:   | userCharacterList  | 312  | 5     | is    |
#:   | userMapList     | 104  | 1     | is    |
#:   | userMusicDetailList | 739  | 1     | is    |
#:   | userLoginBonusList | 38   | 0     | is    |
#:   | userCourseList   | 16   | 0     | is    |
#:   | userItemList    | 1070  | 0     | is    |
#:   | userIntimateList  | 2   | 0     | is    |
#:   | userChargeList   | 3   | **3**   | - No! callback |
#:
#: userChargeList is**callback**(real machineAs ishair 3 item), Cannot be treated as difference,
#: Otherwise, it will be mistakenly converged into an empty array.
DIFF_PRIMARY_KEYS: Dict[str, Tuple[str, ...]] = {
    "userCharacterList": ("characterId",),
    "userMapList": ("mapId",),
    "userLoginBonusList": ("bonusId",),   # tothatitem -> Bitstring "1"
    "userItemList": ("itemKind", "itemId"),
    "userMusicDetailList": ("musicId", "level"),
    "userCourseList": ("courseId",),
    "userFriendSeasonRankingList": ("seasonId",),
    "userIntimateList": ("partnerId",),
    "userKaleidxScopeList": ("gateId",),
    "userShopItemStockList": ("shopItemId",),
    "userFavoritemusicList": ("musicId",),
}

#: callback, Node without difference(real machineAs ishairoutAllitem)
FULL_TABLE_NODES: Tuple[str, ...] = (
    "userChargeList",
)

#: noVariationtimeYesleave blankofnodes
#:  Basis: real-machine packet source/2026-10-05. log:123 in userItemList / userCourseList /
#:    userKaleidxScopeList / userIntimateList / userShopItemStockList /
#:    userTradeItemList / userFriendSeasonRankingList / userFavoritemusicList /
#:    userGhost / userLoginBonusList / userGetPointList Yes to all [],
#:    serverreturns returnCode=1 — emptynumbergroupisof.
MAY_BE_EMPTY_NODES: Tuple[str, ...] = (
    "userGhost", "userMapList", "userLoginBonusList", "userItemList",
    "userMusicDetailList", "userCourseList", "userFriendSeasonRankingList",
    "userChargeList", "userActivityList", "userMissionDataList",
    "userIntimateList", "userShopItemStockList", "userGetPointList",
    "userTradeItemList", "userFavoritemusicList", "userKaleidxScopeList",
    "userCharacterList", "userRatingList",
)

#: defaultHengemptyofnodes(this gameNoGenerateofdata)
#:
#: - userGetPointList And userLoginBonusList allatColumns — thisnodesis
#:  **loginRewardshair**will arise., playsettlementNot requiredCallback:
#:
#:  - userGetPointList(in/numberdetails)
#:   real machine 39 UpsertUserAll in **25 Is Empty(64%)**,
#:   Only login rewards occur/Not empty when rewarding a task(As getKind=1 point=200).
#:   leave blank => serverNoPlus point, numberStay the same.
#:
#:  - userLoginBonusList(toRewards)
#:   Empathy, Only return that one when a new check-in is triggered by this login(isCurrent=true).
#:   leave blank => isNewLoginBonusList is also an empty string.
#:
#:  - BeltImpact(currentcurrent): leave blankAfter userData. point ofIncrementnoFrom
#:   So point Keep baseline value unchanged. this is"Do not issue credits"ofresult.
DEFAULT_EMPTY_NODES: Tuple[str, ...] = (
    "userGhost",            # source code VOExtensions. cs:235 Only in NeedSave timeCallback
    "userGetPointList",     # loginRewardsonlyGenerate; settlementleave blank
    "userLoginBonusList",   # loginRewardsonlyGenerate; settlementleave blank
    "userTradeItemList",    # no Get
    "userFriendSeasonRankingList",   # no Get
    "userFavoritemusicList",         # source codeisitemcallback, real machineHeng []
)


# =============================================================================
# Two, Field crop table(Get Side -> Upsert Fields to be discarded on the side)
# =============================================================================
#
# Basis: putreal machine Get Side response vs. Upsert Side reports are compared by field.

#: userData: Get Side has, Upsert Fields without side
USER_DATA_DROP_KEYS: Tuple[str, ...] = (
    "friendCode", "nameplateId", "trophyId",
    "cmLastEmoneyCredit", "cmLastEmoneyBrand",
)

#: userOption: Upsert Side No tempoVolume
USER_OPTION_DROP_KEYS: Tuple[str, ...] = ("tempoVolume",)

#: userExtend: Upsert Side**Extra**thisfields(Get Side No), Must be supplemented
#:  real machine Upsert Side 16 key vs Get Side 14 key, The difference is these two.
USER_EXTEND_EXTRA_KEYS: Tuple[str, ...] = ("isPhotoAgree", "isGotoCodeRead")

#: - userRating. udemae: server Get There is a batch in the response**firstUppercaseoffield**
#:  (source/2026-10-05. log:87 of Get Responding to npcWinNum And NpcWinNum Coexistence, of 23 key),
#:  But the real machine Upsert in the packet**Lowercase only 16 key**(source/2026-10-05. log:123).
#:  source code Net. VO. Mai2/UserUdemae. cs Lowercase only 16 fields,
#:  So this batch of uppercase fields is the redundant output of the server, Must be truncated on return — Otherwise:
#:   ① in the packetAppearancesource codeAbsentofField
#:   ② request bodyreal machine 119 Bytes
USER_RATING_UDEMAE_DROP_KEYS: Tuple[str, ...] = (
    "MaxLoseNum", "NpcTotalWinNum", "NpcTotalLoseNum",
    "NpcMaxWinNum", "NpcMaxLoseNum", "NpcWinNum", "NpcLoseNum",
)

#: userCharacterList: Keep only this 4 fields
USER_CHARACTER_KEEP_KEYS: Tuple[str, ...] = (
    "characterId", "level", "awakening", "useCount",
)

#: userMusicDetailList: Discard extNum2
USER_MUSIC_DETAIL_DROP_KEYS: Tuple[str, ...] = ("extNum2",)

#: userChargeList: Discard extNum1
USER_CHARGE_DROP_KEYS: Tuple[str, ...] = ("extNum1",)

#: userMissionDataList / userWeeklyData: Discard userId
USER_MISSION_DROP_KEYS: Tuple[str, ...] = ("userId",)


# =============================================================================
# Three, Basic Tools
# =============================================================================

def _strip_keys(item: Any, drop: Sequence[str]) -> Any:
    """From dict inDeletespecifiedField(returns dict)."""
    if not isinstance(item, dict):
        return item
    return {k: v for k, v in item.items() if k not in drop}


def _keep_keys(item: Any, keep: Sequence[str]) -> Any:
    """Keep only specified fields(returns dict)."""
    if not isinstance(item, dict):
        return item
    return {k: v for k, v in item.items() if k in keep}


def empty_node(node: str) -> Any:
    """pressnodesreturnsemptyValue."""
    kind = NODE_TYPES.get(node)
    if kind == "bits":
        return ""
    if kind == "object":
        return {}
    return []


def empty_user_all() -> Dict[str, Any]:
    """constructFullemptyof 36 nodes"""
    return {node: empty_node(node) for node in NODE_ORDER}


def coerce_node_value(node: str, value: Any) -> Any:
    """
  putValuethenodesshouldhasofMorphology; Error transmission direct throwing PatchError.

  - this isofuserWeeklyData / user2pPlaylog Transfer array,
   userData Passing on dict, allischeckof
  """
    kind = NODE_TYPES.get(node)
    if kind is None:
        raise PatchError("notnodesFirst name:" + str(node))

    if value is None:
        return empty_node(node)

    if kind == "bits":
        if not isinstance(value, str):
            raise PatchError("nodes " + node + " isBitstring, Must pass str, receiveto " + type(value).__name__)
        return value

    if kind == "object":
        if not isinstance(value, dict):
            raise PatchError("nodes " + node + " isObject(Not an array), Must pass dict, receiveto "
                             + type(value).__name__)
        return value

    if kind == "singleton":
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return value
        raise PatchError("nodes " + node + " Must be dict or list, receiveto " + type(value).__name__)

    # array
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    raise PatchError("nodes " + node + " Must be list, receiveto " + type(value).__name__)


def sync_bits_to_arrays(user_all: Dict[str, Any]) -> None:
    """
  When the bit string length is inconsistent with the corresponding array number, press "0"/Truncation(In-place modification).

  - lengthNothe server will"Which ones are new".
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
            # Truncate when there are already extra characters; Replenish when insufficient "0"
            user_all[bits] = (cur + "0" * want)[:want] if cur else "0" * want


# =============================================================================
# Four, Differential
# =============================================================================

def _norm(item: Any) -> str:
    """putOneitemrecordofString."""
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)


def _primary_key(item: Any, keys: Sequence[str]) -> Tuple:
    """Take primary key value."""
    if not isinstance(item, dict):
        return (str(item),)
    return tuple(item.get(k) for k in keys)


def build_delta(
    local: Sequence[Any],
    server: Sequence[Any],
    compare_keys: Optional[Sequence[str]] = None,
) -> Tuple[List[Any], str]:
    """
  Reprint VOExtensions. BuildListData ofDifferentialsemantic.

  Then(source/Assembly-CSharp/Net. VO. Mai2/VOExtensions. cs:309-324):
    1. fieldthisitemAndserver**Any**None of them are exactly the same -> calculate"Variation", mustCallback
      (source codeis nsrc. Except(osrc), fullField)
    2. compare_keys Only for**calculateBitstring**, Not involved in culling
    3. Bitstring:"0" = Primary key already exists on the server(update);"1" = New(added)

  Parameter:
    local:    (playAftershouldhasvalue of)
    server:    serverSnapshot(Differential Baseline)
    compare_keys: Primary Key Field Name(used forBitstring)

  Returns:
    (mustCallbackofitemlist, Bitstring)
  """
    server_norm = {_norm(s) for s in server}
    server_keys = set()
    if compare_keys:
        server_keys = {_primary_key(s, compare_keys) for s in server}

    delta: List[Any] = []
    flags: List[str] = []
    for item in local:
        if _norm(item) in server_norm:
            continue                      # Exactly as one of the server entries -> noVariation
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
  receiveuseDifferential(Reprint VOExtensions. cs:345-367).

  - Different from normal difference:**Do not cull, Constantly returns full entries**(real machine is 5 item).

  Bit String Rules(pressreal machine source/2026-10-05. log:123 of "22212" Reverse):
    "2" = serverSide hasCorresponding itemKind(noContentisNoMatch)
    "1" = serverSidecheckNotothe itemKind

  - Critical:**Priority use Get Side most primitive response indexing**, Don't use it first get_user_favorite. py
   of"itemKind"returnedOne — on the real machine itemKind=10 ofThe response is
   {"itemKind": null, "itemIdList":[]}, currentforcheckNotoonlyGenerate "1".

  Parameter:
    local:     receivelist(Made up itemKind,5 item)
    server:     serverreceivelist. Passing on**Original** Get On Response itemKind=null
            ofthatitemMeetingsGenerate "1"(Not required assume_missing).
    assume_missing: "serverHeng Hui null"of itemKind
            - Only if server is**returnedOne**ofList
             (itemKind Completed, nooutOriginal null)timeonlyneedPassing on,
             Otherwise, it will put what should have been "1" ofthatBitcalculate "2".
             calluseatcannot obtainRaw ResponsetimePassing on FAVORITE_MISSING_KINDS,
             getRaw ResponsetimePassing on.
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
        # "1" ofitem(Any Establishment):
        #  a) serverSidenonethe itemKind(In the original response, null)
        #  b) the kind at assume_missing in(Baseline normalized, nooutOriginal null)
        if kind in server_kinds and kind not in missing:
            flags.append("2")
        else:
            flags.append("1")
    return out, "".join(flags)


# =============================================================================
# Five, time
# =============================================================================

def _local_wall_string(login_date_time: int) -> str:
    """
  put loginDateTime real machinethat "YYYY-MM-DD HH: MM: SS.0" String.

  - loginDateTime semanticsis"Wall TimeWhen UTC time",
   So use utcfromtimestamp HaraoutWall Time, andNo fromtimestamp.
   real machine userData. lastLoginDate = "2026-10-05 00:19:37.0"
   Corresponding loginDateTime = 1791159576.
  """
    try:
        dt = datetime.fromtimestamp(int(login_date_time), tz=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.0")


#: CST Offset(source/Assembly-CSharp/Manager/TimeManager. cs:9 CSToffset = 8 Hours)
CST_OFFSET_SECONDS = 8 * 3600

#: playlogofMinutesHours(source/Assembly-CSharp/Manager/TimeManager. cs:77-85
#:  ToLogDateTime: Hours < 7 timeputtimesonedays)
LOG_DAY_CUTOFF_HOUR = 7


def _local_date_string(login_date_time: int) -> str:
    """
  "YYYY-MM-DD"(Corresponding TimeManager. GetLogDateString).

  - playlognot a natural day: source/Assembly-CSharp/Manager/TimeManager. cs:77-85

    public static DateTime ToLogDateTime(DateTime dateTime, int hour = 0)
    {
      DateTime result = new(dateTime. Year, dateTime. Month, dateTime. Day, hour, 0, 0);
      if (7 > dateTime. Hour) return result. AddDays(-1.0);  // 7 agocalculatePrevious day
      return result;
    }

  real machine(source/2026-10-05. log:123):
    userPlayDate = "2026-10-05 00:20:30.0"(Wall Time 10-05 00:20)
    playDate   = "2026-10-04"     (00:20 < 07:00 -> Fallback to 10-04)
  """
    wall = datetime.fromtimestamp(int(login_date_time), tz=timezone.utc)
    log_day = wall - timedelta(days=1) if wall.hour < LOG_DAY_CUTOFF_HOUR else wall
    return log_day.strftime("%Y-%m-%d")


def _standard_unix(login_date_time: int) -> int:
    """
  put loginDateTime Hara**standard Unix time**.

  - loginDateTime is"Wall TimeWhen UTC time"ofsecondsnumber(login_date_time_now),
   So the standard Unix seconds = loginDateTime - timeOffset(Eastern Eight Wards -28800).

  Corresponding source/Assembly-CSharp/Net. VO. Mai2/VOExtensions. cs:1290
    result. loginDate = TimeManager. GetUnixTime(src. Detail. LastLoginDate);
  and TimeManager. GetUnixTime returnback isstandard Unix seconds.

  real-machine loginDateTime=1791159576 -> 1791159576-28800 = 1791130776,
       real machine loginDate = 1791130777(Bad 1 seconds, inStringtruncate toseconds).
  """
    return int(login_date_time) - local_utc_offset_seconds()


# =============================================================================
# Sat, this game data(play)
# =============================================================================

@dataclass
class PlayData:
    """
  All inputs for one game.

  - defaultValueAll from config. py of PLAY_* Columns(Taken from a real machine source/2026-10-05. log:123).
   Want to change songs/ResultsOnlychange config. py, Don't move the code.
  """
    # track
    music_id: int = field(default_factory=lambda: config.PLAY_MUSIC_ID)
    music_level: int = field(default_factory=lambda: config.PLAY_MUSIC_LEVEL)
    track_no: int = field(default_factory=lambda: config.PLAY_TRACK_NO)
    version_int: int = field(default_factory=lambda: config.PLAY_VERSION_INT)
    version_str: str = field(default_factory=lambda: config.PLAY_VERSION_STR)

    # Results
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

    #
    #: - thisFourPiece**No longer from config** — timeby derive_play_rating() From
    #:  GetUserRatingApi toof userRatingList[0] Fill in(theFunction).
    #:  Passing onSnapshot(batch packets)timeonlyKeep 0.
    before_rating: int = 0
    after_rating: int = 0
    before_delux_rating: int = 0
    after_delux_rating: int = 0
    #: - thisTwoby derive_play_grade() From Snapshot userMusicDetailList in
    #:  same (musicId, level) ofrecordTake scoreRank Get; cannot obtainis 0.
    before_grade: int = 0
    after_grade: int = 0
    #: - Constantly 1
    after_grade_rank: int = PLAY_AFTER_GRADE_RANK

    #
    category_index: int = field(default_factory=lambda: config.PLAY_CATEGORY_INDEX)
    music_index: int = field(default_factory=lambda: config.PLAY_MUSIC_INDEX)
    extra_flag: int = field(default_factory=lambda: config.PLAY_EXTRA_FLAG)

    #(playtimeSnapshot, Inexperienced)
    #: - defaultemptyList — currentvalue ofby derive_play_characters() Push from server snapshot.
    #:  (Hara PLAY_CHARACTERS(currentat selftest. py in) Moved to selftest. py As test data)
    characters: List[Dict[str, int]] = field(default_factory=list)

    # consume
    play_credit: int = field(default_factory=lambda: config.PLAY_CREDIT)
    use_ticket_id: int = field(default_factory=lambda: config.PLAY_USE_TICKET_ID)
    play_mode: int = field(default_factory=lambda: config.PLAY_MODE)
    is_tutorial: bool = field(default_factory=lambda: config.PLAY_IS_TUTORIAL)
    is_event_mode: bool = field(default_factory=lambda: config.PLAY_IS_EVENT_MODE)
    is_new_free: bool = field(default_factory=lambda: config.PLAY_IS_NEW_FREE)
    is_freedom_mode: bool = field(default_factory=lambda: config.PLAY_IS_FREEDOM_MODE)
    #: - Constantly PLAY_LOCAL_PLAY_COUNT(= 2)— machine statecountnumberserverNoreturns
    local_play_count: int = PLAY_LOCAL_PLAY_COUNT

    # calculateIncrement
    #: userTotal Play CountIncrement(0 = userData. playCount / currentPlayCount allUnchanged)
    #: - default 0: No longer auto +1. If you want to repeat the real machine, set it to 1.
    user_play_count_gain: int = field(
        default_factory=lambda: getattr(config, "PLAY_USER_PLAY_COUNT_GAIN", 0))
    #: trackplaycountIncrement(0 = itemPassing onButcountUnchanged)
    music_play_count_gain: int = field(
        default_factory=lambda: config.PLAY_MUSIC_PLAY_COUNT_GAIN)
    map_distance_gain: int = field(default_factory=lambda: config.PLAY_MAP_DISTANCE_GAIN)
    character_exp_gain: int = field(default_factory=lambda: config.PLAY_CHARACTER_EXP_GAIN)

    # ---- in / loginRewards ----
    # - thisTwois**loginRewardshair**Produced by, playsettlementNoCallback(leave blank).
    #  real machine 39 UpsertUserAll in, userGetPointList has 25 Is Empty(64%).
    #  leave blank => userData. point Keep baseline value unchanged(Do not issue credits).


def build_play_from_config() -> PlayData:
    """press config. py of PLAY_* constructthis game data."""
    return PlayData()


def derive_play_rating(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
) -> PlayData:
    """
  Take from server snapshot**real rating**, Fill play ofFourPiece rating Field.

  - Why don't you use it anymore config inofvalue:
    rating will change with each round, Writing death will be incompatible with the server.

  - Value based on(real-machine packet capture confirms,2026-10-06 22:23 thatgame):
    userPlaylog. beforeRating   = 15534
    userPlaylog. afterRating    = 15534
    userPlaylog. beforeDeluxRating = 15534
    userPlaylog. afterDeluxRating = 15534

    userData. playerRating = 15534  ← And beforeRating/afterRating Match
    userData. musicRating = 15534  ← And beforeDeluxRating/afterDeluxRating Match
    userRatingList[0]. rating = 0  ← Measured**No**thisvalues, Don't get it wrong

  Parameter:
    snapshot: GetNeedUserData ofreturnsValue
    play:   mustFill inof PlayData(Do not pass on or create a new one)

  Returns: Completed PlayData(Same object).
  """
    p = play or build_play_from_config()
    snap = normalize_snapshot(snapshot) if snapshot else {}

    ud: Dict[str, Any] = {}
    try:
        data = snap.get("userData") or []
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list) and data and isinstance(data[0], dict):
            ud = data[0]
    except Exception:
        ud = {}

    def _pick(*names):
        for n in names:
            v = ud.get(n)
            if v not in (None, ""):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    continue
        return None

    # playerRating Priority; time userRatingList[0]. rating
    rating = _pick("playerRating")
    if rating is None:
        try:
            rl = snap.get("userRatingList") or []
            if isinstance(rl, dict):
                rl = [rl]
            if rl and isinstance(rl[0], dict) and rl[0].get("rating") not in (None, ""):
                rating = int(rl[0]["rating"])
        except Exception:
            rating = None
    delux = _pick("musicRating")

    if rating is not None:
        p.before_rating = rating
        p.after_rating = rating
    if delux is not None:
        p.before_delux_rating = delux
        p.after_delux_rating = delux

    log_info("rating Taken from server snapshot: playerRating=" + str(p.before_rating)
             + " musicRating=" + str(p.before_delux_rating))
    return p


def find_music_detail(snapshot: Optional[Any], music_id: int, level: int):
    """in the snapshot userMusicDetailList insame (musicId, level) ofthatitemrecord; nonereturns None."""
    snap = normalize_snapshot(snapshot) if snapshot else {}
    items = snap.get("userMusicDetailList") or []
    if isinstance(items, dict):
        items = items.get("userMusicList") or []
    for it in items:
        if not isinstance(it, dict):
            continue
        if int(it.get("musicId", -1) or -1) == int(music_id)                 and int(it.get("level", -1) or -1) == int(level):
            return it
    return None


def derive_play_grade(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
) -> PlayData:
    """
  beforeGrade / afterGrade / afterGradeRank.

  -- must: source codeinthisThreefieldsis**Bit(Dan)**, Not a track rating —
    source/Assembly-CSharp/Net. VO. Mai2/VOExtensions. cs:1419-1421
      result. beforeGrade  = (int)gameScore. PreDanRate;  // beforeofBit rate
      result. afterGrade   = (int)gameScore. DanRate;   // afterofBit rate
      result. afterGradeRank = (int)gameScore. Dan;     // Bitlevel

    real-machine sample(noBit)= beforeGrade 0 / afterGrade 0 / afterGradeRank 1.

  ofTake(pressUsemust):
    before_grade = at userMusicDetailList insame (musicId, level) ofrecord,
            Take it scoreRank; cannot obtain -> 0
    after_grade  = this gameResults(play. achievement)vs. in the record achievement present.,
            Better grades -> Take the rating derived from this bureau, Otherwise, continue to use before_grade
    after_grade_rank = Constantly 1(PLAY_AFTER_GRADE_RANK)

  ⚠ Want to strictly reproduce the real machine(noBitAlways 0)Just put the DERIVE_GRADE_FROM_MUSIC_DETAIL False.
  """
    p = play or build_play_from_config()
    p.after_grade_rank = PLAY_AFTER_GRADE_RANK

    if not DERIVE_GRADE_FROM_MUSIC_DETAIL:
        p.before_grade = 0
        p.after_grade = 0
        log_info("grade: DERIVE_GRADE_FROM_MUSIC_DETAIL=False -> beforeGrade=0 afterGrade=0"
                 " afterGradeRank=" + str(p.after_grade_rank))
        return p

    detail = find_music_detail(snapshot, p.music_id, p.music_level)
    if detail is None:
        p.before_grade = 0
        p.after_grade = 0
        log_info("grade: Not in snapshot musicId=" + str(p.music_id) + " level="
                 + str(p.music_level) + " ofrecord -> beforeGrade=0 afterGrade=0")
        return p

    before = int(detail.get("scoreRank", 0) or 0)
    old_ach = int(detail.get("achievement", 0) or 0)
    p.before_grade = before

    # this gameBetter grades -> usethis gameof(noneResultstimetimes before)
    if int(p.achievement or 0) > old_ach:
        p.after_grade = before
    else:
        p.after_grade = before
    log_info("grade: musicId=" + str(p.music_id) + " level=" + str(p.music_level)
             + " record scoreRank=" + str(before) + " achievement=" + str(old_ach)
             + " / this game achievement=" + str(p.achievement)
             + " -> beforeGrade=" + str(p.before_grade)
             + " afterGrade=" + str(p.after_grade)
             + " afterGradeRank=" + str(p.after_grade_rank))
    return p


def derive_play_characters(
    snapshot: Optional[Any] = None,
    play: Optional[PlayData] = None,
) -> List[Dict[str, int]]:
    """
  From**server-issuedofSnapshot**outthis gameof 5 Roles only(Includes Pre-Play Level).

  - Why you need it:
    PLAY_CHARACTERS(currentat selftest. py in) isFill inofvalue, one;
    usevalueMeetingsGetAnd userCharacterList Not really. characterLevelN.
    The snapshot is the true value of the server taken immediately after logging in, isof.

  data(allat Get Responding to):
    userData. charaSlot     this game 5 of character slots characterId(orderi. e. slot1..5)
                  source/Assembly-CSharp/Net. VO. Mai2/GetUserData. cs
    userCharacterList     eachRoles onlyof level / awakening
                  GetUserCharacterApi Response

  Parameter:
    snapshot: GetNeedUserData ofreturnsValue(or any userData /
         userCharacterList ofDictionary).
    play:   Current PlayData; The slot that cannot be found in the snapshot falls back to its configuration in the same location.

  Returns:
    5 item {"characterId","level","awakening"},**playago**value of(Inexperienced).
    The role does not exist in the snapshot, Neithertime, theBitfor characterId=0.
  """
    p = play or build_play_from_config()
    fallback = list(p.characters or [])[:5]

    snap = normalize_snapshot(snapshot) if snapshot else {}

    slot_ids: List[int] = []
    levels: Dict[int, Dict[str, int]] = {}
    try:
        # userData is singleton nodes(List 1 Element); Nudity is also tolerated dict Morphology
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
  construct**playAfter**of userData(Single dict, Not an array).

  - useGetUserNewItemListApi needPassing on"playAfter"offile
   real machineEmpirical(source/2026-10-05-new. log):
     GetUserNewItemList of userData[0] And UpsertUserAll of userData[0]
     **Exact match**(playCount=1258, point=4460, lastPlayDate=19:22:53.0).

  Returns:
    playAfterof userData Dictionary(Can be inserted directly [ ] Pass to GetUserNewItemList)
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
# Seven, userPlaylogList(110 Field Score Breakdown)
# =============================================================================

#: UserPlaylog of**All**Field, order source/Assembly-CSharp/Net. VO. Mai2/UserPlaylog. cs
#: - None of them can be saved: putreal-machine packetAnd C# Declare for collection comparison, Both directions 0 Difference.
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

#: - is string ofField(defaultValueMust beemptyNo 0)
PLAYLOG_STRING_FIELDS: Tuple[str, ...] = (
    "placeName", "playDate", "userPlayDate",
    "vsUserName", "playedUserName1", "playedUserName2", "playedUserName3",
)

#: - Name without is Prefix but type is bool ofField(currentuse startswith("is") Judgment will be missed)
PLAYLOG_BOOL_FIELDS: Tuple[str, ...] = (
    "isTap", "isHold", "isSlide", "isTouch", "isBreak",
    "isCriticalDisp", "isFastLateDisp",
    "isAchieveNewRecord", "isDeluxscoreNewRecord", "isClear",
    "isPlayTutorial", "isEventMode", "isFreedomMode", "isNewFree",
    "extBool1", "extBool2", "extBool3",
)

#: Determination Type and Determination Positioning(order)
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
  constructOneitem 110 Field userPlaylog.

  Parameter:
    playlog_id:  - Required == UserLoginApi of loginId
    play_date:   - this game**playtime**(loginDateTime Same Format, i. e. now + timeOffset).
            used for playDate(log)And userPlayDate(String on the wall).
            Return without passing login_date(present.).
            - Why Separate: real machine playDate / userPlayDate is"thatOne",
             and loginDateTime is"The moment you swipe your card to log in", The time difference between the two is one game
             (source/2026-10-05. log: login 00:19:37 -> play 00:20:30).
    login_date:  loginSessiontime(used for loginDate).
            - on the real machine userPlaylog. loginDate is**playSessionoftime**
             (source/2026-10-05. log:123 is 1791130777,
             UserLoginApi of loginDateTime=1791159576 8 Hours,
             This is actually the session time of the last game), network scriptnonethisvalues,
             thisinuseIncomingValueJust do it; serverNoinfor
    play:     this game data(Optional, defaultpress config. PLAY_* construct)
    place_id:   Store ID
    place_name:  Store Name
    client_id:   machine stateshortValue
    user_play_date: playtimeString(Optional, defaultby login_date )

  Returns:
    110 Field dict

  ofThen(Basis source/.../Net. VO. Mai2/VOExtensions. cs):
    userId      Constantly 0(VOExtensions. cs:1289)
    musicId >= 100000(Banquet Recipe) -> level = 10(VOExtensions. cs:1300-1303)
    isTap/isHold/... bythetotal number of judgmentsisNofor 0(VOExtensions. cs:1403-1407)
    trialPlayAchievement = -1(this gamenone)(VOExtensions. cs:1441-1445)
    extNum4 =(And userExtend. categoryIndex Redundancy)
  """
    p = play or build_play_from_config()

    level = 10 if p.music_id >= 100000 else p.music_level
    play_moment = int(play_date) if play_date else int(login_date)
    user_play_date = user_play_date or _local_wall_string(play_moment)

    # - String field default empty string, Remaining defaults 0(real-machine in the packet vsUserName/playedUserNameN allis "")
    row: Dict[str, Any] = {
        name: ("" if name in PLAYLOG_STRING_FIELDS else 0)
        for name in PLAYLOG_FIELDS
    }

    # ---- Foundation ----
    row["userId"] = 0                       # VOExtensions. cs:1289
    row["orderId"] = 0
    row["playlogId"] = playlog_id
    row["version"] = p.version_int
    row["placeId"] = place_id
    row["placeName"] = place_name
    # - loginDate is**standard Unix seconds**(VOExtensions. cs:1290 GetUnixTime ofreturnsValue),
    #  No loginDateTime(The latter is"Time on the wall when UTC").
    row["loginDate"] = _standard_unix(login_date)
    # - playDate isplay**log**(7 agocalculatePrevious day), Not a natural day;
    #  Take is**playtime**, Not at login time.
    row["playDate"] = _local_date_string(play_moment)
    row["userPlayDate"] = user_play_date
    row["type"] = 0
    row["musicId"] = p.music_id
    row["level"] = level
    row["trackNo"] = p.track_no

    # ---- Match(Single Player Global 0)----
    row["playerNum"] = 1

    # ---- Snapshot 1..5 ----
    # - characterLevelN is**playago**oflevel, Do not add the experience of this bureau — thisOne
    #   source/Assembly-CSharp/Net. VO. Mai2/VOExtensions. cs:1361
    #     result. characterLevel1 = (int)gameScore. CharaLevel[0];
    #  gameScore. CharaLevel is**playtime**GoofSnapshot, gameNoAgainChange;
    #  playAfteroflevelOnlyAppearanceat upsertUserAll. userCharacterList in.
    #
    #  - Two Real Opportunity Dialogues Empirical(Get Side / playlog / upsertUserCharacterList Triple control):
    #
    #   source/2026-10-05-new. log:31,123(19:21 Session)
    #    GetUserCharacterApi: 395=3801 101=4456 135 135 135
    #    userPlaylogList[0]: 3801 4456 135 135 135  ← And Get Same side = playago
    #    userCharacterList: 395=3802 101=4457 136 136 136 ← playAfter(+1)
    #
    #   MaimaiNetSpy 2026-10-05_222919(22:31 Session)
    #    GetUserCharacterApi: 395=3802 101=4457 136 136 136
    #    userPlaylogList[0]: 3802 4457 136 136 136  ← And Get Same side = playago
    #    userCharacterList: 395=3803 101=4458 137 137 137 ← playAfter(+1)
    #
    #  So p. characters inofMust be**playago**value of
    #  (PLAY_CHARACTERS(currentat selftest. py in) ofAlsothisof), thisinTransparent as isJust do it.
    #  Practice: use derive_play_characters(snapshot) directlyFromserver-issuedof
    #  userData. charaSlot + userCharacterList outFill in
    chars = list(p.characters or [])[:5]
    for i in range(5):
        c = chars[i] if i < len(chars) else {}
        row["characterId" + str(i + 1)] = int(c.get("characterId", 0) or 0)
        # playagolevel(Inexperienced; onlycurrentat userCharacterList)
        row["characterLevel" + str(i + 1)] = int(c.get("level", 0) or 0)
        row["characterAwakening" + str(i + 1)] = int(c.get("awakening", 0) or 0)

    # ---- Results ----
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

    # ---- Determination Details(5 × 5 Judgment positioning)----
    for jtype in JUDGE_TYPES:
        counts = (p.judge_counts or {}).get(jtype, {}) or {}
        total = 0
        for box in JUDGE_BOXES:
            value = int(counts.get(box, 0) or 0)
            row[jtype + box] = value
            total += value
        # isTap / isHold /... bytheisNohas note
        flag_name = "is" + jtype.capitalize()
        if flag_name in row:
            row[flag_name] = (total > 0)

    # ---- Switch(real machinefor true)----
    row["isCriticalDisp"] = True
    row["isFastLateDisp"] = True

    # ---- ----
    row["beforeRating"] = p.before_rating
    row["afterRating"] = p.after_rating
    row["beforeGrade"] = p.before_grade
    row["afterGrade"] = p.after_grade
    row["afterGradeRank"] = p.after_grade_rank
    row["beforeDeluxRating"] = p.before_delux_rating
    row["afterDeluxRating"] = p.after_delux_rating

    # ---- mode ----
    row["isPlayTutorial"] = bool(p.is_tutorial)
    row["isEventMode"] = bool(p.is_event_mode)
    row["isFreedomMode"] = bool(p.is_freedom_mode)
    row["playMode"] = p.play_mode
    row["isNewFree"] = bool(p.is_new_free)

    # ----(this gamenone)----
    row["trialPlayAchievement"] = -1

    # ---- Bit ----
    row["extNum1"] = 0
    row["extNum2"] = 0
    row["extNum4"] = p.category_index      # And userExtend. categoryIndex Redundancy
    row["extBool1"] = False
    row["extBool2"] = False
    row["extBool3"] = False

    # bool Field must be bool
    for name in PLAYLOG_BOOL_FIELDS:
        row[name] = bool(row.get(name, False))

    return row


def validate_user_playlog(playlog: Dict[str, Any]) -> List[str]:
    """
  presssource codecheckOneitem playlog, returnslist(empty = Compliance).

  Fields filled in incorrectly will not report errors, But it will be treated as an abnormal result by the server. checkitem:
    1. Number of fields == 110
    2. Sum of each type of judgment number == totalCombo
    3. maxCombo <= Total number of judgments
    4. achievement > 0 timeNoshouldYes to all Miss
    5. isClear=True time achievement Cannot be 0
    6. comboStatus=1(Quan Lian)time maxCombo == Total number of judgments
    7. extNum4 == userExtend. categoryIndex(bycallusepresent., thisinOnlynon- 0)
  """
    problems: List[str] = []

    missing = [f for f in PLAYLOG_FIELDS if f not in playlog]
    if missing:
        problems.append("field:" + ", ".join(missing[:10])
                        + ("..." if len(missing) > 10 else ""))
    extra = [k for k in playlog if k not in PLAYLOG_FIELDS]
    if extra:
        problems.append("Extra Fields:" + ", ".join(extra[:10]))

    total_notes = 0
    for jtype in JUDGE_TYPES:
        for box in JUDGE_BOXES:
            total_notes += int(playlog.get(jtype + box, 0) or 0)

    total_combo = int(playlog.get("totalCombo", 0) or 0)
    if total_combo and total_notes != total_combo:
        problems.append("Sum of each type of judgment number " + str(total_notes)
                        + "!= totalCombo " + str(total_combo))

    max_combo = int(playlog.get("maxCombo", 0) or 0)
    if total_notes and max_combo > total_notes:
        problems.append("maxCombo " + str(max_combo) + " > Total number of judgments " + str(total_notes))

    achievement = int(playlog.get("achievement", 0) or 0)
    if achievement > 0:
        miss = sum(int(playlog.get(jtype + "Miss", 0) or 0) for jtype in JUDGE_TYPES)
        if total_notes and miss == total_notes:
            problems.append("achievement>0 But it's all Miss, numberValue")

    if bool(playlog.get("isClear")) and achievement == 0:
        problems.append("isClear=True But achievement=0, numberValue")

    if int(playlog.get("comboStatus", 0) or 0) == 1 and max_combo != total_notes:
        problems.append("comboStatus=1(Quan Lian)But maxCombo!= Total number of judgments")

    if int(playlog.get("extNum4", 0) or 0) == 0:
        problems.append("extNum4()for 0, should be equal to userExtend. categoryIndex")

    if not playlog.get("placeName"):
        problems.append("placeName Is Empty(Store name needs to be in config. PLACE_NAME )")

    return problems


# =============================================================================
# Eight, userGamePlaylogList
# =============================================================================

def calc_play_special(calc_special_num: Optional[int] = None) -> int:
    """
  Reprint VOExtensions. cs:846-855 of playSpecial calculate

  source code:
    int max = 1037933;
    int num2 = Random. Range(1, max) * 2069;
    num2 += GameManager. CalcSpecialNum();
    int num3 = 0;
    for (int i = 0; i < 32; i++) { num3 <<= 1; num3 += num2 % 2; num2 >>= 1; }
    playSpecial = num3;

  Parameter:
    calc_special_num: machine stateBit(GameManager. CalcSpecialNum).
             defaultTake PLAY_SPECIAL_NUM = 1024.

  Returns:
    int32 of playSpecial.

  - About CalcSpecialNum ofPick a value(source code GameManager. cs:332-378):
    It is a bitwise or outgoing machine feature mask, where 0x400 noitemBit,
    Also 0x40 / 0x80 / 0x100 The condition for the third place is"**No**Contains a characteristic"—
    real machine isOneStagestandard ACA + GTX + i3-8100 machine state, thisThreeBitexactlyallfor 0,
    So CalcSpecialNum Constant equals 0x400 = 1024.

   - Reverse inference validation: real machine playSpecial = 892014272
      Bit inversion32(892014272) = 57726124 = 27900 * 2069 + 1024
      The remainder is exactly 1024, And gamehook toof CalcSpecialNum Exact match.
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
    # truncate to int32
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
  construct userGamePlaylogList ofOneitem(13 Field).

  - playDate useofis**At the moment of reporting**ofWall Time(real machineEmpirical:
   source/2026-10-05. log in userGamePlaylogList[0]. playDate = "00:20:57.0",
   And UpsertUserAllApi requesthairoutoftimeMatch, Also with userData. lastPlayDate relatedSame).
   Do not pass play_date timetimes login_date.

  real-machine sample(source/2026-10-05. log:123):
    {"playlogId":..,"version":"1.56.00","playDate":"2026-10-05 00:20:57.0",
     "playMode":0,"useTicketId":-1,"playCredit":1,"playTrack":1,
     "clientId":"TESTCLIENT1","isPlayTutorial": false,"isEventMode": false,
     "isNewFree": false,"playCount":8,"playSpecial":55951502,"playOtherUserId":0}
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
# nine, defaultnodesconstruct
# =============================================================================

def default_user_weekly_data(login_date: int) -> Dict[str, Any]:
    """
  construct userWeeklyData(- Object, Not an array).

  real-machine sample:
    {"lastLoginWeek":"2026-09-28 04:00:00","beforeLoginWeek":"2026-09-21 04:00:00",
     "friendBonusFlag": true}
  Perimeter is**Monday 04:00**(real machine updateDate is 2026-09-28 04:00:00, thatdaysisMonday).
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
  construct user2pPlaylog(- Object, Not an array).

  real-machine sample:
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
# ten, Snapshot Normalization
# =============================================================================

def _extract_from_get_responses(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
  put"Each Get interfaceofRaw Response"nodesDictionary(With Field Crop).

  Parameter:
    raw: Shape like
       {
        "userData":    <GetUserDataApi ofResponse>,
        "userExtend":   <GetUserExtendApi ofResponse>,
        "userMapList":  <GetUserMapApi ofResponse>,
...
       }
       Also Accept GetNeedUserData() Node dictionary already organized(Idempotent).

  Returns:
    nodesFirst name -> nodesValue(Cropped)
  """
    out: Dict[str, Any] = {}

    # ---- Array of elements ----
    if "userData" in raw:
        src = raw["userData"]
        ud = src.get("userData") if isinstance(src, dict) and "userData" in src else src
        if isinstance(ud, dict):
            ud = _strip_keys(ud, USER_DATA_DROP_KEYS)
            # banState at Get The side is the top level field, Move in when returning userData Internal
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
            # - udemae inserverRedundancyofUppercasefield(real machine Upsert Side No)
            udemae = ur.get("udemae")
            if isinstance(udemae, dict):
                ur["udemae"] = _strip_keys(udemae, USER_RATING_UDEMAE_DROP_KEYS)
            out["userRatingList"] = [ur]

    # ---- Object ----
    if "userWeeklyData" in raw:
        src = raw["userWeeklyData"]
        uw = src.get("userWeeklyData") if isinstance(src, dict) and "userWeeklyData" in src else src
        if isinstance(uw, dict):
            out["userWeeklyData"] = _strip_keys(uw, USER_MISSION_DROP_KEYS)

    # - userWeeklyData ofoneGetUserMissionDataApi ofResponding toBelt
    #  (UserMissionResponseVO. cs:10 public UserWeeklyData userWeeklyData;)
    #  real machineValue = server-issuedofPerimeter,**Not counted locally**:
    #    GetGameWeeklyDataApi. updateDate  = "2026-09-28 04:00:00"
    #    Upsert Side lastLoginWeek      = "2026-09-28 04:00:00"  ← Exact match
    #  Basis source/Assembly-CSharp/Manager/GetUserData. cs:1040-1049
    #    WeeklyData. LastLoginWeek = gameWeeklyData. updateDate;
    #  So give priority to the values in the snapshot.; Return to local derivation only if you don't get it.
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

    # ---- numbergroup(keyFirst name -> List key name in response)----
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
                # - trackResultshasTwo Forms, allmust
                #  a) interfaceRaw Response: Two layers of nesting(UserMusic. cs Outer layers are grouped by song,
                #   Inner layer userMusicDetailList It is. (musicId, level) item)
                #  b) GetUserMusicDetailAll() ofFlattened into single strips
                #  Criteria: Elemental Inner Belt "userMusicDetailList" key -> Nested; Otherwise, it has been spread evenly.
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
                # - Pocket back: The dictionary returned by the retrieval script is sometimes used**nodesFirst name**Keying
                #  (As GetUserFavoriteAll -> {"userFavoriteList": [...], "_raw": [...]},
                #  and GetUserFavoriteApi ofRaw Responseis {"userFavorite": {...}}).
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

    # - receiveof**Original**Baseline(Non-complimentary itemKind): real machine itemKind=10 ofThe response is
    #  {"itemKind": null}, In the bit string "1" comes from it.. Keep a separate copy for the difference.
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


#: real machine isNewFavoriteList in"serverSidecheckNotothe itemKind"ofPick a value.
#: Measured two samples:
#:  source/2026-10-05. log:123     -> "22212"(itemKind=10 thatitemis null)
#:  MaimaiNetSpy of 22:32:21 that   -> "22212"(Ibid.)
#: That is, the first 4 Bit(itemKind=10, file)**for "1"** — server response. the kind Heng Hui null.
FAVORITE_MISSING_KINDS: Tuple[int, ...] = (10,)


def normalize_snapshot(snapshot: Optional[Any]) -> Dict[str, Any]:
    """
  putEachMorphologyofSnapshotsystemOne"nodesDictionary".


    None             -> {}
    nodesDictionary(36 nodesFirst name)     -> As is(Do a form coercion)
    {"upsertUserAll": {...}}   -> Take the inner layer
    {"_responses": {...}}     -> Take _responses
    Each Get interfaceofRaw ResponseDictionary   -> _extract_from_get_responses
  """
    if snapshot is None:
        return {}

    if isinstance(snapshot, str):
        with open(snapshot, "r", encoding="utf-8") as fp:
            snapshot = json.load(fp)

    if not isinstance(snapshot, dict):
        raise PatchError("snapshot Unrecognized form:" + type(snapshot).__name__)

    if "upsertUserAll" in snapshot and isinstance(snapshot["upsertUserAll"], dict):
        snapshot = snapshot["upsertUserAll"]
    if "_responses" in snapshot and isinstance(snapshot["_responses"], dict):
        snapshot = snapshot["_responses"]

    # - Judge Yes"Already a node dictionary"is"Raw Response Collection".
    #  The two key names are highly overlapping(userData / userExtend / userMapList … allisnodesFirst name,
    #  Also Get Responsive outer key), So**Can only be in the form of a value**Distinguish:
    #    nodesDictionary   userData -> list(Array of elements), userMapList -> list
    #    Raw Response Collection userData -> dict(Contains userId/userData/banState)
    #          userMapList -> dict(Contains userMapList List)
    if _looks_like_node_dict(snapshot):
        out: Dict[str, Any] = {}
        for k, v in snapshot.items():
            if k in NODE_TYPES:
                out[k] = coerce_node_value(k, v)
            elif k.startswith("_"):
                out[k] = v            # Hold _raw_favorite thisInternalkey
        return out

    return _extract_from_get_responses(snapshot)


def _looks_like_node_dict(snapshot: Dict[str, Any]) -> bool:
    """
  press**Morphology of the value**Judgment snapshot isNo"Node dictionary already organized".

  Criteria: nodesFirst nameCorrespondingValue NODE_TYPES The morphology of the declaration is measured 1 Minutes, Count the reverse -1 Minutes.
     Total Score > 0 fornodesDictionary.
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
# eleven, this gamecalculate(putBaselineto"playAfter")
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
  pressreal machineforputBaselineto"this gameplayAfter", and calculate the differential nodes.

  - this isCriticalofOnereal machineControl(source/2026-10-05. log):

    userData. playCount    1257 -> 1258      (+1) ← real machine
    userData. currentPlayCount 185 -> 186       (+1) ← real machine
    - default PLAY_USER_PLAY_COUNT_GAIN = 0, thisTwo**Unchanged**.
    userData. lastPlayDate    -> this gametime
    userData. lastPlayMode   2  -> 0
    userData. lastLoginDate   -> logintime
    userData. eventWatchedDate  -> logintime
    userData. lastPlaceId   0  -> 1000
    userData. lastRegionId   11  -> 5
    userData. dateTime     null -> loginrequestof dateTime
    userData. lastGameId    null -> "SDGB"
    userData. accessCode    null -> ""
    userData. lastPlaceName  null -> Store Name
    userMusicDetailList    7  -> 8        (playCount +1)
    userMapList. distance   1424000 -> 1435000   (+11000)
    userCharacterList[]. level Each +1

  Parameter(In-place modification user_all):
    user_all:    nodesDictionary(will be modified)
    play:      this game data
    login_date_time: UserLoginApi of loginDateTime
    auth_date_time: UserLoginApi requestinof dateTime(Auth. AuthTime)
    play_date_time: - this gameWhen to escalate(Same loginDateTime ).
             real machine userData. lastPlayDate is"text/At the moment of reporting",
             And lastLoginDate(loginthatOne)**Not the same value**:
               lastLoginDate = "2026-10-05 22:31:23.0" ← login
               lastPlayDate  = "2026-10-05 22:32:21.0" ← Escalations
             If not, return both login_date_time(Convenient for offline matchmaking).

  Returns:
    Same user_all(Convenient Chain Calls)
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
        # - defaultIncrement 0: playCount / currentPlayCount Stay the same
        #  (config. PLAY_USER_PLAY_COUNT_GAIN, Want to re-engrave the real machine +1 Change to 1)
        _pc_gain = int(getattr(play, "user_play_count_gain", 0) or 0)
        ud["playCount"] = int(ud.get("playCount", 0) or 0) + _pc_gain
        ud["currentPlayCount"] = int(ud.get("currentPlayCount", 0) or 0) + _pc_gain
        ud["lastPlayDate"] = wall                # this gameWhen to escalate
        ud["lastPlayMode"] = play.play_mode
        ud["lastLoginDate"] = login_wall         # logintime
        ud["eventWatchedDate"] = login_wall      # And lastLoginDate Same value(real machineMatch)
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
        # real machine Upsert inthisTwoisemptynumbergroup(Get Placeholder elements on the side)
        ue["selectedCardList"] = []
        ue["encountMapNpcList"] = []
        # - thisfieldsOnlyAppearanceat Upsert Side, Get Side No
        #  (real machine source/2026-10-05. log:123 of userExtend has 16 keys,
        #   Get Side source/2026-10-05. log:85 Only 14 Piece).
        #  source code VOExtensions. cs:270 is Export timeofSwitchBit.
        #  TheyMeetingslead to userExtend Number of fields does not match, servercanreceive.
        ue.setdefault("isPhotoAgree", False)
        ue.setdefault("isGotoCodeRead", False)

    # ---------------- userMusicDetailList(Differential: this gamethatitemtrack)----------------
    # -- thisnodes**Must send back the one from this bureau**, Can't be blank — actual testimonial:
    #   Same code, Same account, The only difference is that leave it blank here vs Callback 1 item:
    #    Callback 1 item -> returnCode=1 and the server does write(At that time, shit playCount +1 to)
    #    leave blank   -> returnCode=1 But nothing has changed.(**post-upload**)
    #   i. e."this gamehas playlog without any track details."will be silently discarded by the server as an invalid packet.
    #  - currentat playCount defaultNoAgain +1, post-uploadCriteriachange lastPlayDate(verify_upsert_landing).
    #
    # - But playCount of**Increment**Can be freely controlled:
    #   config. PLAY_MUSIC_PLAY_COUNT_GAIN = 0(default)-> itemPassing on, countUnchanged
    #                     = 1    -> Reproduction of the real machine +1
    #  So"I don't want the music playCount Increase"ofcurrentPracticeisputIncrement 0,
    #  **andNo**putnodesempty.
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
        # this gameResultsintimeonlyupdatevalue
        if play.achievement > int(target.get("achievement", 0) or 0):
            target["achievement"] = play.achievement
            target["scoreRank"] = play.score_rank
            target["comboStatus"] = play.combo_status
            target["syncStatus"] = play.sync_status
        if play.deluxscore > int(target.get("deluxscoreMax", 0) or 0):
            target["deluxscoreMax"] = play.deluxscore
        user_all["userMusicDetailList"] = [target]
        # - one"this gamethatitem", For differential convergence behind the pocket(build_user_all)
        user_all["_played_music_entry"] = copy.deepcopy(target)

    # ---------------- userMapList(Differential: map distance Increase)----------------
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

    # ---------------- userCharacterList(Differential: group)----------------
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
            # - press characterId Ascending(use Get Side order)
            #  real machine source/2026-10-05. log:123 of userCharacterList is [101,395,200401,400401,400402],
            #  and charaSlot is [395,101,400402,400401,200401] — The two are in different order,
            #  descriptionCallbacktimepress characterId instead of pressing charaSlot order.
            grown.sort(key=lambda c: int(c.get("characterId", 0) or 0))
            user_all["userCharacterList"] = grown
        else:
            user_all["userCharacterList"] = []

    # ---------------- userGetPointList / userLoginBonusList ----------------
    #  - thisnodesis**loginRewardshair**Produced by, playsettlementleave blankJust do it:
    #   - userGetPointList: real machine 39 in 25 Is Empty(64%)
    #   - userLoginBonusList: Only return if this login triggers a new check-in
    #  Both DEFAULT_EMPTY_NODES in, byDownsystemOneempty.
    #  point and therefore leave the baseline unchanged.(The inevitable consequence of not issuing points).

    # ---------------- userGamePlaylogList(Client Newly Created)----------------
    user_all["userGamePlaylogList"] = []   # by build_user_all Fill in(need playlog_id)

    # ---------------- userWeeklyData / user2pPlaylog ----------------
    if not user_all.get("userWeeklyData"):
        user_all["userWeeklyData"] = default_user_weekly_data(login_date_time)
    if not user_all.get("user2pPlaylog"):
        user_all["user2pPlaylog"] = default_user_2p_playlog()

    # ---------------- defaultemptynodes ----------------
    for node in DEFAULT_EMPTY_NODES:
        if node in user_all:
            user_all[node] = empty_node(node)

    return user_all


# =============================================================================
# Twelve, group upsertUserAll
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
  group upsertUserAll of 36 nodes.


    1. From snapshot Establish baseline(Cropped)
    2. apply_play_effects toplayAfter, and calculate the difference nodes
    3. Fill userGamePlaylogList
    4. patch overwrite
    5. 11 itemBitstring

  Parameter:
    snapshot:    Baseline Snapshot(normalize_snapshot)
    play:      this game data(defaultpress config. PLAY_*)
    patch:      overwrite, key=nodesFirst name, Highest priority
    login_date_time: UserLoginApi of loginDateTime
    auth_date_time: UserLoginApi requestinof dateTime
    play_date_time: - this gameWhen to escalate(Same loginDateTime );
             used for lastPlayDate / userGamePlaylogList. playDate.
             Return without passing login_date_time.
    playlog_id:   UserLoginApi of loginId(used for userGamePlaylogList)
    extra_data:   - JSON(dict / JSON String / file path),
             36 nodes,**Priority is higher than patch**. merge_extra_data.

  Returns:
    36 nodesof dict
  """
    p = play or build_play_from_config()
    base = normalize_snapshot(snapshot)

    # Keep a copy of the baseline, For differential calculation
    user_all: Dict[str, Any] = empty_user_all()
    for node in NODE_ORDER:
        if node in base:
            user_all[node] = copy.deepcopy(base[node])
    user_all["_baseline_music"] = copy.deepcopy(base.get("userMusicDetailList") or [])
    user_all["_baseline_map"] = copy.deepcopy(base.get("userMapList") or [])
    user_all["_baseline_character"] = copy.deepcopy(base.get("userCharacterList") or [])
    # - receiveofRaw Baseline(not itemKind), For build_favorite_delta Generate "1"
    if base.get("_raw_favorite"):
        user_all["_raw_favorite"] = copy.deepcopy(base["_raw_favorite"])

    # toplayAfter
    apply_play_effects(
        user_all, p,
        login_date_time=login_date_time, auth_date_time=auth_date_time,
        place_id=place_id, place_name=place_name,
        region_id=region_id, region_name=region_name, client_id=client_id,
        play_date_time=play_date_time,
    )

    # userGamePlaylogList(Client Newly Created, need playlog_id)
    if playlog_id:
        user_all["userGamePlaylogList"] = [
            build_user_game_playlog(playlog_id, login_date_time, p, client_id=client_id,
                                    play_date=play_date_time)
        ]

    # ---- - Differential: puthas DELTA_NODES receive (- Baseline) ----
    #  real machineOnly send back**The changed ones**:
    #    Get Side 104 itemMap -> Upsert Side 1 item(distance The one that changed)
    #    Get Side 38 itemloginRewards -> Upsert Side 0 item(noVariation)
    #  apply_play_effects have put together"this gameMeetingsChange"ofnodesto
    #  thisinsystemOneOnce (- Baseline), noVariationofreceiveemptynumbergroup.
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

    # ---- - userMusicDetailList example: countchangeAlsoMust send back the one from this bureau ----
    #  Why: The difference above will put"Exactly the same as the baseline"ofitemWhen
    #  PLAY_MUSIC_PLAY_COUNT_GAIN = 0(this gameNo changecount)And when the results are not refreshed,
    #  this gamethatitemMeetings -> nodesChangeempty.
    #  - Measured(Same code, Same account, The only difference is this node):
    #    Callback 1 item -> returnCode=1 and the server does write
    #    leave blank   -> returnCode=1 But nothing has changed.(**packet**)
    #  So here's the bottom of the pocket.: As long as the Bureau does play a song,, Just be sure to send back that one of it.
    #  Bitstring to "0" = serverSideExistingthe (musicId, level), Belongs to updates, not additions.
    if not (user_all.get("userMusicDetailList") or []):
        _played = user_all.get("_played_music_entry")
        if isinstance(_played, dict):
            user_all["userMusicDetailList"] = [copy.deepcopy(_played)]
            user_all["isNewMusicDetailList"] = "0"

    # ---- Differential: receiveisexample(Do not cull, Constantly returns full entries)----
    #  - Baseline to use**notreturnedOne**ofOriginal Get Response: real machine itemKind=10 ofthatitemback is
    #   {"itemKind": null}, currentisGenerateIn the bit string "1".
    #   The original response was passed by the caller snapshot of _raw_favorite Incoming;
    #   cannot obtaintimeonlytimesAlreadyReturnedOneofBaseline, and explicitly declare"Which kind serverHeng Hui null",
    #   Otherwise itemKind afterBitstringMeetingsYes to all "2".
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
            log_debug("receiveBaselinenoRaw Response, pressAlreadyHengempty kind Pocket back:"
                      + str(tuple(fav_assume_missing)))
        user_all["userFavoriteList"] = fav_delta
        user_all["isNewFavoriteList"] = fav_bits

    # ---- patch overwrite ----
    if patch:
        for node, value in patch.items():
            if node not in NODE_TYPES:
                raise PatchError(
                    "patch inhasnotnodesFirst name:" + str(node)
                    + "(Available Nodes:" + ", ".join(NODE_ORDER) + ")"
                )
            user_all[node] = coerce_node_value(node, value)

    # ---- extra_data overwrite(- Highest priority)----
    if load_extra_data(extra_data):
        for note in merge_extra_data(user_all, extra_data):
            log_info(note)

    # ---- InternalField ----
    for key in list(user_all.keys()):
        if key.startswith("_"):
            del user_all[key]

    # ---- Bit String Completion ----
    sync_bits_to_arrays(user_all)

    # ---- press NODE_ORDER ----
    return {node: user_all.get(node, empty_node(node)) for node in NODE_ORDER}


# =============================================================================
# Thirteen, request / Response VO
# =============================================================================

@dataclass
class UserAllRequestVO:
    """request VO(Corresponding Net. VO. Mai2/UserAllRequestVO, Field order photo C# Declaration)."""
    userId: int
    playlogId: int = 0
    isEventMode: bool = False
    isFreePlay: bool = False
    loginDateTime: int = 0
    userPlaylogList: List[Any] = field(default_factory=list)
    upsertUserAll: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpsertResponseVO:
    """Response VO(Corresponding Net. VO. Mai2/UpsertResponseVO)."""
    returnCode: int = 0
    apiName: str = ""


# =============================================================================
# Fourteen, Self-inspection before contract issuance
# =============================================================================

def validate_before_send(
    req: UserAllRequestVO,
    play: Optional[PlayData] = None,
) -> List[str]:
    """
  Check yourself according to the hard constraints of the source code before issuing the contract(returnslist, empty = Compliance).

  - Even if the server returns returnCode=1, It may also be silent;
   thisinFirstputcancheckofallcheckOnehas

  Parameter:
    req: musthairofrequest
    play: this game data(Optional).- useJudgment"Differential node is empty"Is it a problem or not?:
       config. PLAY_MAP_DISTANCE_GAIN / PLAY_CHARACTER_EXP_GAIN defaultis 0,
       time userMapList / userCharacterList Empty Yes**for**, No alarms.
  """
    problems: List[str] = []

    if not req.playlogId:
        problems.append("top-level playlogId for 0(Required == UserLoginApi of loginId)")
    if not req.loginDateTime:
        problems.append("top-level loginDateTime for 0(Required == UserLoginApi of loginDateTime)")

    ua = req.upsertUserAll or {}

    ud_list = ua.get("userData") or []
    if not ud_list:
        problems.append("userData Is Empty(server response. It isoverwritesemantic, emptyPackageetcin)")
    else:
        ud = ud_list[0] if isinstance(ud_list[0], dict) else {}
        # - accessCode real machineisempty(source/2026-10-05. log:123), Requirements only"Exists and is not null"
        for key in ("lastGameId", "accessCode", "lastPlaceName", "lastRegionName"):
            if key not in ud or ud.get(key) is None:
                problems.append("userData." + key + " orfor null")
        nulls = [k for k, v in ud.items() if v is None]
        if nulls:
            problems.append("userData inhas null Field:" + ", ".join(nulls[:8]))
        # - userData isoverwritesemantic: thisitem"this gameRequired"ofFieldisvalue/0,
        #  the server willfullreceiveetcinNothing happened(docs/UpsertUserAllPitmd Pit 1)
        if not int(ud.get("playCount") or 0):
            problems.append("userData. playCount for 0(should >= Baseline value)")
        if not int(ud.get("currentPlayCount") or 0):
            problems.append("userData. currentPlayCount for 0(should >= Baseline value)")
        if not int(ud.get("dateTime") or 0):
            problems.append("userData. dateTime for 0(should be UserLoginApi requestinof dateTime)")
        if not ud.get("lastPlayDate"):
            problems.append("userData. lastPlayDate Is Empty(It should be the time of reporting by this bureau)")
        if not ud.get("lastLoginDate"):
            problems.append("userData. lastLoginDate Is Empty(This should be the time of login)")

    if not req.userPlaylogList:
        problems.append("userPlaylogList Is Empty(thatisthis gameResultsdetails, serverdirectlyreceive)")
    else:
        for i, pl in enumerate(req.userPlaylogList):
            if isinstance(pl, dict) and pl.get("playlogId") != req.playlogId:
                problems.append("userPlaylogList[" + str(i) + "]. playlogId!= top-level playlogId")
            if isinstance(pl, dict) and not pl.get("playSpecial"):
                pass  # playSpecial Belongs to userGamePlaylogList, Not here

    for gp in ua.get("userGamePlaylogList") or []:
        if isinstance(gp, dict) and not gp.get("playSpecial"):
            problems.append("userGamePlaylogList[]. playSpecial for 0(real machine ismachineBit)")

    # Bit String Length
    for bits, arr in BITS_TO_ARRAY.items():
        items = ua.get(arr) or []
        s = ua.get(bits) or ""
        if isinstance(items, list) and len(s) != len(items):
            problems.append("Bitstring " + bits + " length " + str(len(s))
                            + "!= numbergroup " + arr + " itemnumber " + str(len(items)))

    # Whether there is a change in the differential node
    #  - Only in"mustthis gamehasVariation"timeonly
    #   PLAY_MAP_DISTANCE_GAIN / PLAY_CHARACTER_EXP_GAIN defaultis 0,
    #   time userMapList / userCharacterList Empty Yes**of**, Not a mistake.
    p = play or build_play_from_config()
    if not (ua.get("userMusicDetailList") or []):
        problems.append("Differential Node userMusicDetailList Is Empty — - Measured so the whole package does not take effect"
                        "(has playlog But no track details will be silently discarded by the server)")
    if p.map_distance_gain and not (ua.get("userMapList") or []):
        problems.append("Differential Node userMapList Is Empty, But PLAY_MAP_DISTANCE_GAIN="
                        + str(p.map_distance_gain) + " — servercanforMapnoVariation")
    if p.character_exp_gain and not (ua.get("userCharacterList") or []):
        problems.append("Differential Node userCharacterList Is Empty, But PLAY_CHARACTER_EXP_GAIN="
                        + str(p.character_exp_gain) + " — servercanfornoVariation")

    return problems


# =============================================================================
# Fifteen, Cooling Wait
# =============================================================================

def wait_send_cooldown(seconds: float, *, label: str = "settlementEscalations") -> float:
    """
  realPackagingagowaitseconds(Includes first time), Escalationsreal machine.

  - Acts only on authentic transmissions; dry_run Don't wait.
  """
    seconds = float(seconds or 0)
    if seconds <= 0:
        return 0.0

    log_info(label + "Cooling: wait " + str(seconds) + " secondsAfterAgainSend(real machine)...")
    start = time.monotonic()
    remain = seconds
    while remain > 0:
        step = min(10.0, remain)
        time.sleep(step)
        remain -= step
        if remain > 0:
            log_info("  Cooling down... Waiting " + str(int(seconds - remain)) + "s / Remaining "
                     + str(int(remain)) + "s")
    elapsed = time.monotonic() - start
    log_info("End of cooldown(Waiting for total " + str(round(elapsed, 1)) + " seconds)")
    return elapsed


# =============================================================================
# sixteen, extra_data: puernal JSON Merge Into upsertUserAll
# =============================================================================
#
# usereal-machine packetof 36 out of nodes, numberallcanbySnapshot + this gamecalculateout;
#    But occasionally I want to manually stuff a few nodes(Asthis gametooneof KaleidxScope ).
#    Instead of changing it, build_user_all ofCode, Why don't you just put that paragraph JSON Incoming.
#
#  UpsertUserAll(user_id, playlog_id,...,
#         extra_data={
#           "userKaleidxScopeList": [{...}],
#           "isNewKaleidxScopeList": "1",
#         })
#
# - Consolidation Rules:
#   1. keyMust be 36 One of nodes(Contains 11 item isNew* Bitstring), Otherwise, explicitly report the error and list the available names
#   2. Values are cast according to the node's morphology(coerce_node_value), Error transmission mode immediately throws PatchError
#   3. Highest priority — overwriteSnapshotcalculateoutofSameFirst name
#   4. numbergroupbut did not giveCorrespondingBitstring -> presslength "0" and give a hint("0" = Inventory update)

def load_extra_data(extra: Any) -> Dict[str, Any]:
    """
  put"JSON"dict.

  FourMorphology:
    None           -> {}
    dict           -> Return As Is
    JSON String        -> json. loads
    file path(. json /. txt)  -> readfileAfter json. loads

  - Judgment Sequence: Let's see first, shall we? dict, Let's see if the string is"Existing file path",
   Only as a last resort JSON parse — thistwoStringallcanuse.
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
        # like a path and the file exists -> readfile
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
            raise PatchError("extra_data noLegal JSON It's also not a readable file:"
                             + str(exc)) from exc
        if not isinstance(data, dict):
            raise PatchError("extra_data parseoutmust be JSON Object({...}),"
                             "actually, " + type(data).__name__)
        return data
    raise PatchError("extra_data Supported only dict / JSON String / JSON file path,"
                     "receiveto " + type(extra).__name__)


def merge_extra_data(
    user_all: Dict[str, Any],
    extra_data: Optional[Any] = None,
) -> List[str]:
    """
  puernal JSON Merge Into upsertUserAll of 36 nodes(In-place modification).

  Parameter:
    user_all:  build_user_all() of
    extra_data: load_extra_data

  Returns:
    Merge Instructions(eachitemOne Row, For Log Printing)

  Exceptions:
    PatchError: Unknown node name occurred / Incorrect value morphology
  """
    data = load_extra_data(extra_data)
    if not data:
        return []

    notes: List[str] = []

    # ---- 1. Verify the key name as a whole first, changeoneonlyDiscover ----
    unknown = [k for k in data if k not in NODE_TYPES]
    if unknown:
        raise PatchError(
            "extra_data inhasnotnodesFirst name:" + ", ".join(map(str, unknown))
            + "\n Available Nodes(36 Piece):" + ", ".join(NODE_ORDER)
        )

    # ---- 2. itemWrite(coerce will correct the form., If the shape is wrong, throw it away)----
    for node, value in data.items():
        coerced = coerce_node_value(node, value)
        user_all[node] = coerced
        kind = NODE_TYPES.get(node)
        if kind == "bits":
            notes.append("extra_data Write bit strings " + node + " = " + repr(coerced))
        elif isinstance(coerced, list):
            notes.append("extra_data Write " + node + "(" + str(len(coerced)) + " item)")
        else:
            notes.append("extra_data Write " + node)

    # ---- 3. numbergroupButcorrespondingBitstring -> lengthand prompt ----
    for bits, arr in BITS_TO_ARRAY.items():
        if arr in data and bits not in data:
            items = user_all.get(arr) or []
            notes.append(" ⚠ " + arr + " but did not give " + bits
                         + " — Made up by length \"" + "0" * len(items) + "\""
                         + "(\"0\" = Inventory update; is**added**itempleaseexplicitPassing on \"1\")")

    # ---- 4. The bit string length must be equal to the number of arrays(real machine)----
    sync_bits_to_arrays(user_all)

    # ---- 5. Keep NODE_ORDER order ----
    for node in NODE_ORDER:
        if node not in user_all:
            user_all[node] = empty_node(node)

    return notes


# =============================================================================
# Seventeen, Internal orchestration: Snapshot / Front connector / post-upload validation
# =============================================================================

def _resolve_api_func(name: str, fallback: Any = None) -> Any:
    """
  Priority Pickup api The one in the bag**Logged Shells**ofFunction.

  - Why go around this?:
    autowrap() Replace only api/__init__. py Name in namespace
    (log_setup. autowrap of), InternalofdirectlyusetoofisOriginalFunction.
    UpsertUserAll Internal to be adjusted GetNeedUserData / GetUserNewItemList / GetUserData,
    thisOneDownTheyonlyMeetingsuserdirectlycallusethat"=== xxx Get started ===",
    The main script doesn't have to log itself at all.
  """
    try:
        import api as _pkg                       # Lazy Import, Loop
        fn = getattr(_pkg, name, None)
        if callable(fn):
            return fn
    except Exception:
        pass
    return fallback


def _lazy(name: str) -> Any:
    """pressFirst namefetch api Raw functions in sub-modules(_resolve_api_func ofPocket back)."""
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
    raise PatchError("cannot obtainfInternal api:" + str(name))


def resolve_api_func(name: str) -> Any:
    """
  Take"Preferred with Log Shell, Raw function back pocket"ofcalluseObject.

  - For internal and other api(As upsert_user_chargelog)Multiplexing:
   thisInternalcalluseAlsoMeetingsuserdirectlycallusethat"=== xxx Get started ===".
  """
    fn = _resolve_api_func(name)
    return fn if callable(fn) else _lazy(name)


#: first name, Stay compatible
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
  Repull server data after outsourcing, text**ofGo**.

  - Why don't you look? returnCode Just done.:
    server response. userData isoverwritesemantic — packetNopresent. timetimes returnCode=1,
    But the old values are still written in.. The only reliable criterion is to pull the data again to see if the numbers are moving.

  Parameter:
    user_id: user ID
    snapshot: Baseline snapshot before contract release(usepresent.)
    play:   this game data(useBitmustcheckoftrack)

  Returns:
    True = Determined as drop-off success
  """
    p = play or build_play_from_config()
    base = normalize_snapshot(snapshot)
    before_ud = (base.get("userData") or [{}])[0] if base.get("userData") else {}

    try:
        after_raw = _api("GetUserData")(user_id, client_id=client_id,
                                     timeout_ms=timeout_ms, client=client)
        after_ud = (after_raw.get("userData") or {}) if isinstance(after_raw, dict) else {}
    except Exception as exc:
        log_warning("post-upload validationFailed(Doesn't affect upload results):" + str(exc))
        return False

    log_info(" playCount    "
             + str(before_ud.get("playCount")) + " -> " + str(after_ud.get("playCount")))
    log_info(" currentPlayCount "
             + str(before_ud.get("currentPlayCount")) + " -> "
             + str(after_ud.get("currentPlayCount")))
    log_info(" lastPlayDate   "
             + str(before_ud.get("lastPlayDate")) + " -> "
             + str(after_ud.get("lastPlayDate")))

    # this gametrackof playCount
    try:
        music_raw = _api("GetUserMusicDetailAll")(user_id, client_id=client_id,
                                               timeout_ms=timeout_ms, client=client)
        rows = music_raw.get("userMusicList") or [] if isinstance(music_raw, dict) else []
        hit = [m for m in rows
               if m.get("musicId") == p.music_id and m.get("level") == p.music_level]
        log_info(" musicId=" + str(p.music_id) + " level=" + str(p.music_level)
                 + " playCount -> " + (str(hit[0].get("playCount")) if hit else "(checkNoto)"))
    except Exception as exc:
        log_warning(" trackdetailstimescheckFailed:" + str(exc))

    # - Judgment is based on walking with increment:
    #  Increment > 0 -> playCount Should be bigger(Original Criteria)
    #  Increment = 0 -> playCount notheChange, changeuse lastPlayDate isNoupdateJudgment
    _pc_gain = int(getattr(p, "user_play_count_gain", 0) or 0)
    if _pc_gain:
        ok = (int(after_ud.get("playCount") or 0)
              > int(before_ud.get("playCount") or 0))
        detail = "userData. playCount Already +" + str(_pc_gain)
    else:
        _b_lpd = str(before_ud.get("lastPlayDate") or "")
        _a_lpd = str(after_ud.get("lastPlayDate") or "")
        ok = bool(_a_lpd) and _a_lpd != _b_lpd
        detail = "userData. lastPlayDate " + _b_lpd + " -> " + _a_lpd

    if ok:
        log_info("[post-uploadSuccess]" + detail)
    else:
        log_error("[notpost-upload]" + detail + ","
                  "pleaseControl docs/UpsertUserAllPitmd check")
        if not _pc_gain:
            log_warning(" PLAY_USER_PLAY_COUNT_GAIN=0 time playCount Unchanged is normal,"
                        "placeofis lastPlayDate; uploadofisSameone game,"
                        "lastPlayDate canrelatedetc(False Negative)")
    return ok


# =============================================================================
# Eighteen, Main Function
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
  Upload an Inning Result(UpsertUserAllApi,- hasSide effects)— **A function runs the entire settlement link**.

  - Do these things internally in turn, The main script only calls it once:
    1. Baseline Snapshot(Passing on snapshot timeneed token)
    2. Push Local from Snapshot 5 Roles only(auto_characters)
    3. constructthis gameResultsdetails userPlaylogList
    4. callFront connector GetUserNewItemListApi(pre_new_item_list)
    5. group upsertUserAll of 36 nodes(Snapshot Baseline + this gamecalculate + Differential)
    6. Merge extra_data inofExternal JSON
    7. Self-inspection before contract issuance
    8. Cooling → realPackaging
    9. post-upload validation(verify_landing)

  Parameter:
    user_id:     user ID(Required)
    playlog_id:   login ID(Required,- Required == UserLoginApi of loginId)
    login_date_time: logintime(Required,- Required == UserLoginApi of loginDateTime)
    auth_date_time: UserLoginApi requestinof dateTime(Optional;
             userData. dateTime mustusereal machineMeasuredplaceMatch)
    token:      Session Token(Optional).- Only in"Passing on snapshot And auto_snapshot=True"
             timeneed — Auto-tuning with it internally GetNeedUserData.
    snapshot:    Baseline Snapshot(Optional, normalize_snapshot).
             Pass it and use it; If it is not passed on, press auto_snapshot
             - server response. userData isoverwrite, Pair differential nodes are"Only return variations",
              noneBaseline Snapshotetcinserver"this gameallchange".
    auto_snapshot:  True(default)= Passing on snapshot timeone
    auto_characters: True(default)= From Snapshot userData. charaSlot +
             userCharacterList outthis game 5 Roles only(**playago**level).
             this PLAY_CHARACTERS(currentat selftest. py in) AlsoNoImpact.
    play:      this game data(Optional, defaultpress config. PLAY_*)
    extra_data:   - JSON, upsertUserAll of 36 nodes.
             dict / JSON String / JSON file path, Example:
               extra_data={"userKaleidxScopeList": [{...}],
                     "isNewKaleidxScopeList": "1"}
             Highest priority(overwriteSnapshotcalculateoutofSameFirst name).
             BitstringtimeMeetingspressnumbergrouplength "0" and give a hint.
    patch:      Same extra_data ofinterface(Accepts only dict, No Matching String Prompt).
    user_playlog_list: this gameResultsdetails(Optional; Don't pass it on, use it play constructOneitem)
    pre_new_item_list: True(default)= Adjust before releasing the package GetUserNewItemListApi
             (real machinefor: settlementEscalationsago 8 secondscall). Failure does not block.
    verify_landing: True(default)= Repull server data after outsourcing, ofGo
             - serverreturns returnCode=1 Doesn't mean the data is applied, thisOneIt is. receivestandard.
    is_event_mode:  mode(Optional)
    is_free_play:  Free Play Logo(Optional)
    confirm:     Side Effects Gate; None timeTake config. UPSERT_CONFIRM
    dry_run:     True = Construct and return packets only, no packet is sent
    cooldown_sec:  realPackagingagoofCoolingsecondsnumber(Only confirm=True;
             None = Take config. UPSERT_SEND_COOLDOWN_SEC, Passing on 0 skip)
    play_date_time: - this game**play/When to escalate**(Optional, Same loginDateTime ).
             on the real machine userData. lastPlayDate / userGamePlaylogList. playDate /
             userPlaylogList. userPlayDate allis"thatOne", Different from login time.
             **Automatically take without passing"currentat"**(login_date_time_now()).
    timeout_ms:   timeout milliseconds(default 60 seconds)
    client:     Reusable MaimaiNetClient(Optional)

  Returns:
    dry_run=True -> UserAllRequestVO
    dry_run=False -> UpsertResponseVO
  """
    log_info("Upload Grades: user_id=" + str(user_id) + " playlog_id=" + str(playlog_id)
             + " dry_run=" + str(dry_run))

    if not login_date_time:
        raise ValueError("login_date_time: Must pass UserLoginApi of loginDateTime"
                         "(PacketUpsertUserAll. cs:31)")

    # ---------- stage 1: Baseline Snapshot(Premise of Difference)----------
    if snapshot is None and auto_snapshot:
        if not token:
            log_warning("Passing on snapshot Also did not pass token — noBaseline Snapshot."
                        "Differential nodes will be empty, servercanforthis gamenoVariation."
                        "Passing on token=...()or snapshot=...(Incoming)")
        else:
            log_info("notPassing on snapshot, fetchsettlementBaseline Snapshot...")
            snapshot = _api("GetNeedUserData")(
                user_id, token=token, client_id=client_id,
                place_id=place_id, region_id=region_id, client=client,
            )

    # ---------- stage 2: this game data ----------
    p = play or build_play_from_config()
    if auto_characters:
        derived = derive_play_characters(snapshot, p)
        if derived and any(c.get("characterId") for c in derived):
            p.characters = derived
            log_info("SnapshotTaken from server snapshot:"
                     + " / ".join(str(c["characterId"]) + ":" + str(c["level"])
                                  for c in derived))

    # - rating / grade Always push from server snapshot(Don't read again config ofvalue)
    if snapshot:
        derive_play_rating(snapshot, p)
        derive_play_grade(snapshot, p)

    # play/When to escalate: Take without passing"currentat"
    play_now = int(play_date_time) if play_date_time else login_date_time_now()

    # ---------- stage 3: this gameResultsdetails ----------
    if user_playlog_list is None:
        user_playlog_list = [
            build_user_playlog(playlog_id, login_date_time, p,
                               place_id=place_id, place_name=place_name,
                               client_id=client_id, play_date=play_now)
        ]

    # ---------- stage 4: Front GetUserNewItemListApi ----------
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
            log_warning("GetUserNewItemListApi Failed(Unblock checkout):" + str(exc))

    # ---------- stage 5: group upsertUserAll(Snapshot Baseline + this gamecalculate + Differential)----------
    user_all = build_user_all(
        snapshot=snapshot, play=p, patch=patch, extra_data=extra_data,
        login_date_time=login_date_time, auth_date_time=auth_date_time,
        place_id=place_id, place_name=place_name,
        region_id=region_id, region_name=region_name, client_id=client_id,
        playlog_id=playlog_id, play_date_time=play_now,
    )

    # ---------- stage 7: constructrequest ----------
    req = UserAllRequestVO(
        userId=user_id,
        playlogId=playlog_id,
        isEventMode=bool(is_event_mode or p.is_event_mode),
        isFreePlay=bool(is_free_play),
        loginDateTime=int(login_date_time),
        userPlaylogList=list(user_playlog_list),
        upsertUserAll=user_all,
    )

    # ---------- stage 8:----------
    for pl in req.userPlaylogList:
        if isinstance(pl, dict):
            for problem in validate_user_playlog(pl):
                log_warning("[Grade Self-Test] " + problem)

    problems = validate_before_send(req, play=p)
    if problems:
        log_warning("[Self-inspection before contract issuance]Discover " + str(len(problems)) + " may not conform to source code logic:")
        for item in problems:
            log_warning("  - " + item)
        log_warning("servercanreturns returnCode=1 But**Not really dropped off**, pleaseitempresent.")
    else:
        log_info("Self-test passed before contract issuance")

    # ---------- stage 9: dry-run ----------
    if dry_run:
        log_info("[dry-run] Request message constructed, notPackaging")
        log_debug("dry-run packet:" + json.dumps(req, ensure_ascii=False, default=str))
        return req

    # ---------- stage 10: Side Effects Gate ----------
    effective = UPSERT_CONFIRM if confirm is None else bool(confirm)
    if not effective:
        msg = ("UpsertUserAllApi is**hasSide effects**ofinterface(will write the actual results of this bureau into the server, Irrevocable)."
               "scriptdefaultNomusthairpleasePassing on confirm=True,"
               "or change config. UPSERT_CONFIRM = True. I just want to see the message, please send it dry_run=True.")
        log_error(msg)
        raise ConfirmRequiredError(msg)

    # ---------- stage 11: Cooling ----------
    wait_send_cooldown(
        UPSERT_SEND_COOLDOWN_SEC if cooldown_sec is None else cooldown_sec,
        label="Upload Grades",
    )

    # ---------- stage 12: Packaging ----------
    log_info("alreadyStart uploading grades...")
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
        msg = "Failed to upload grades: returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName
        log_error(msg)
        raise UpsertUserAllError(msg)

    log_info("Uploaded grades successfully: returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName)

    # ---------- stage 13: post-upload validation(- currentofreceivestandard)----------
    if verify_landing:
        verify_upsert_landing(user_id, snapshot, p,
                              client_id=client_id, timeout_ms=timeout_ms, client=client)

    return resp


# =============================================================================
# Nineteen, Run separately(debug)
# =============================================================================

if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("upsert_user_all_test")
        try:
            log_info("constructOneitem playlog and do a self-test.(no packet is sent)")
            pl = build_user_playlog(7692848101484135861, 1791159576)
            problems = validate_user_playlog(pl)
            if problems:
                for item in problems:
                    log_warning(" - " + item)
            else:
                log_info("playlog(110 Fully fielded)")

            log_info("Number of fields:" + str(len(pl)) + " / " + str(len(PLAYLOG_FIELDS)))
            log_info("Total number of judgments:" + str(sum(
                int(pl.get(t + b, 0) or 0) for t in JUDGE_TYPES for b in JUDGE_BOXES)))
            log_info("totalCombo:" + str(pl.get("totalCombo")))
            return 0
        finally:
            teardown_logging()

    raise SystemExit(_main())
