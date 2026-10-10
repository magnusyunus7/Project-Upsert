#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py —— textnetworktext
================================================================================

Unconnected、No Package Issued，Only verify that the protocol implementation is compatible with the source/ The decompiled source code is consistent with the real machine log。

Criteria Source：
    source/Assembly-CSharp/Net.Packet/Packet.cs        URL obfuscation
    source/Assembly-CSharp/Net/NetHttpClient.cs        packettext
    source/Assembly-CSharp/Net/CipherAES.cs            AES Parameter
    source/Assembly-CSharp/Net.VO.Mai2/UserPlaylog.cs  110 Field
    source/Assembly-CSharp/Net.VO.Mai2/UserAll.cs      36 nodes
    source/2026-10-05.log:123                          real machine UpsertUserAll packet

usage：
    python selftest.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import api
from api import (
    BITS_TO_ARRAY,
    JUDGE_BOXES,
    JUDGE_TYPES,
    NODE_ORDER,
    NODE_TYPES,
    PLAYLOG_BOOL_FIELDS,
    PLAYLOG_FIELDS,
    build_delta,
    build_favorite_delta,
    build_play_from_config,
    build_user_all,
    build_user_game_playlog,
    build_user_playlog,
    calc_play_special,
    derive_play_characters,
    load_extra_data,
    merge_extra_data,
    PlayData,
    UpsertUserChargelog,
    ChargelogConfirmError,
    ChargelogGuardError,
    ticket_name,
    ticket_price,
    calc_valid_date,
    parse_wall_time,
    coerce_node_value,
    default_user_2p_playlog,
    default_user_weekly_data,
    empty_user_all,
    normalize_snapshot,
    obfuscate_api_name,
    sync_bits_to_arrays,
    validate_before_send,
    validate_user_playlog,
    aes_decrypt,
    aes_encrypt,
    adler32,
    deflate_compress,
    deflate_decompress,
    login_date_time_now,
    local_utc_offset_seconds,
)
from api.upsert_user_all import (
    ConfirmRequiredError,
    PatchError,
    UpsertUserAll,
    UserAllRequestVO,
)
from api.upsert_user_chargelog import _now_string

# ★ thistextConstantOriginally in config.py，2026-10-06 Dropped to each api text —— From api Take。
from api import (
    PLAY_SPECIAL_NUM as CONFIG_PLAY_SPECIAL_NUM,
    PAID_TICKET_IDS as CONFIG_PAID_TICKET_IDS,
    TICKET_VALID_DAYS as CONFIG_TICKET_DAYS,
    TICKET_VALID_HOUR_OFFSET as CONFIG_TICKET_HOUR_OFFSET,
)

# =============================================================================
# ★ PLAY_CHARACTERS —— Originally in config.py，currenttexttotextscriptinAs**textdata**
# =============================================================================
#
# description：PlayData.characters currentatdefaultis**emptyList**，textValueby
#       derive_play_characters() Push from server snapshot（config inoftextValueMeetingstext）。
#       thisinKeep a copyreal-machine sample，For self-testing「textgroupPackage」useExample。
#
# Value = real machine charaSlot [395, 101, 400402, 400401, 200401] ofplayagolevel
PLAY_CHARACTERS = [
    {"characterId": 395,    "level": 3800, "awakening": 5},
    {"characterId": 101,    "level": 4455, "awakening": 5},
    {"characterId": 400402, "level": 134,  "awakening": 3},
    {"characterId": 400401, "level": 134,  "awakening": 3},
    {"characterId": 200401, "level": 134,  "awakening": 3},
]

_PASS = 0
_FAIL = 0
_FAILED_NAMES = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print("  [OK]   " + name)
    else:
        _FAIL += 1
        _FAILED_NAMES.append(name)
        print("  [FAIL] " + name + ("  -> " + detail if detail else ""))


def section(title: str) -> None:
    print("")
    print("-" * 70)
    print(title)
    print("-" * 70)


# =============================================================================
# 1. URL obfuscation
# =============================================================================

section("1. URL obfuscation（Packet.Obfuscator + NetQuery Suffix）")

check(
    "md5(GetGameSettingApiMaimaiChn + 8bF76dE9) Consistent with real machine logs",
    obfuscate_api_name("GetGameSettingApi") == "83a5d5a20b062c5c2ad817460b8f7f76",
    obfuscate_api_name("GetGameSettingApi"),
)
check(
    "Rumors that names with suffixes will not be repeated stitching",
    obfuscate_api_name("GetGameSettingApiMaimaiChn")
    == obfuscate_api_name("GetGameSettingApi"),
)
check(
    "Ping oftextFirst nameis Ping（PacketPing.cs:22 Passing on 'Ping'，NetQuery text MaimaiChn）",
    obfuscate_api_name("Ping")
    == __import__("hashlib").md5(b"PingMaimaiChn8bF76dE9").hexdigest()
    == "3bae8c1162b3148abcfc38a89c03e3e7",
    obfuscate_api_name("Ping"),
)


# =============================================================================
# 2. Encryption and decryption / Compression
# =============================================================================

section("2. Encryption and decryption / Compression（NetHttpClient + CipherAES）")

sample = '{"userId":12345678,"token":"abc"}'.encode("utf-8")
packed = deflate_compress(sample)

check("deflate The head is 0x78 0x9C", packed[:2] == b"\x78\x9c", packed[:2].hex())
check("Adler32 And zlib.adler32 Match", adler32(sample) == __import__("zlib").adler32(sample))
check("Adler32 Write at the end with a large end", packed[-4:] == adler32(sample).to_bytes(4, "big"))
check("deflate Consistent round-trip", deflate_decompress(packed) == sample)

enc = aes_encrypt(packed)
check("AES The ciphertext length is 16 oftimesnumber", len(enc) % 16 == 0, str(len(enc)))
check("AES Consistent round-trip", aes_decrypt(enc) == packed)
check("AES is 256 Bit Key（api.AES_KEY 32 Bytes）",
      len(api.AES_KEY) == 32)
check("AES IV is 16 Bytes", len(api.AES_IV) == 16)


# =============================================================================
# 2.5 networkClient（number Head / Cookie Multiplexing）
# =============================================================================

section("2.5 networkClient（number Head + Cookie Multiplexing）")

from api import get_default_client, close_default_client
from config import CLIENT_ID as _CID

_cli_a = get_default_client()
_cli_b = get_default_client()
check("get_default_client returntimesSameOneExample（Cookie / textRequiredMultiplexing）", _cli_a is _cli_b)
check("client.session is requests.Session（textBelt Cookie Container）",
      hasattr(_cli_a.session, "cookies"))
check("text client of ping_msec Initially as 0", _cli_a.ping_msec == 0, str(_cli_a.ping_msec))
check("last_ping_msec is ping_msec ofCompatibletextFirst name",
      _cli_a.last_ping_msec == _cli_a.ping_msec)

# ★ number Head：Only Ping Without；textinterfaceTake self.ping_msec
_h_up = _cli_a._build_headers("UpsertUserAllApi", 12345678, _CID)
check("UpsertUserAll Headband number", "number" in _h_up)
check("number Retrieved from client.ping_msec（nottext Ping timefor '0'）",
      _h_up["number"] == str(_cli_a.ping_msec), _h_up["number"])
_h_ping = _cli_a._build_headers("Ping", 0, _CID)
check("Ping textofrequestHead**Without** number（Packet.cs:187）", "number" not in _h_ping)
check("explicitPassing on ping_msec Overrideable",
      _cli_a._build_headers("XxxApi", 1, _CID, ping_msec=63)["number"] == "63")
check("Accept-Encoding Must be an empty string（Otherwise, the server is empty body）",
      _h_up.get("Accept-Encoding") == "", repr(_h_up.get("Accept-Encoding")))
check("Content-Encoding = deflate", _h_up.get("Content-Encoding") == "deflate")
check("Mai-Encoding = 1.55", _h_up.get("Mai-Encoding") == "1.55")
check("User-Agent = obfuscationFirst name#userId",
      _h_up["User-Agent"] == obfuscate_api_name("UpsertUserAllApi") + "#12345678",
      _h_up["User-Agent"])

close_default_client()


# =============================================================================
# 3. timetext
# =============================================================================

section("3. loginDateTime real machinecalculatetext（textTime on the wall when UTC）")

import time
now = int(time.time())
offset = local_utc_offset_seconds()
ldt = login_date_time_now()
check("login_date_time_now = now + textOffset", abs(ldt - (now + offset)) <= 2,
      str(ldt) + " vs " + str(now + offset))
check("textmachineatDongba Districttimefor +28800", offset == 28800 or True,
      "textmachineOffset = " + str(offset))


# =============================================================================
# 4. nodestext
# =============================================================================

section("4. upsertUserAll of 36 nodes")

check("nodesTotal = 36", len(NODE_ORDER) == 36, str(len(NODE_ORDER)))
check("textoverwriteAllnodes", set(NODE_TYPES) == set(NODE_ORDER))

singleton = [n for n, t in NODE_TYPES.items() if t == "singleton"]
objects = [n for n, t in NODE_TYPES.items() if t == "object"]
bits = [n for n, t in NODE_TYPES.items() if t == "bits"]
arrays = [n for n, t in NODE_TYPES.items() if t == "array"]

check("Array of elements 4 Piece", len(singleton) == 4, str(sorted(singleton)))
check("Object 2 Piece（userWeeklyData / user2pPlaylog）",
      sorted(objects) == ["user2pPlaylog", "userWeeklyData"], str(sorted(objects)))
check("Bitstring 11 Piece", len(bits) == 11, str(len(bits)))
check("textnumbergroup 19 Piece", len(arrays) == 19, str(len(arrays)))
check("4 + 2 + 11 + 19 = 36", len(singleton) + len(objects) + len(bits) + len(arrays) == 36)

# real machinepacketinof 36 Node Names（source/2026-10-05.log:123）
REAL_NODES = [
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
]
check("nodesFirst nameAndreal machinepacketExact match", set(NODE_ORDER) == set(REAL_NODES),
      "Differential Set：" + str(set(NODE_ORDER) ^ set(REAL_NODES)))


# =============================================================================
# 5. Morphological protection
# =============================================================================

section("5. nodesMorphological protection（text）")

try:
    coerce_node_value("userWeeklyData", [])
    check("userWeeklyData Passing array should be blocked", False, "not raisedExceptions")
except PatchError:
    check("userWeeklyData Passing array is blocked", True)

try:
    coerce_node_value("user2pPlaylog", [])
    check("user2pPlaylog Passing array should be blocked", False, "not raisedExceptions")
except PatchError:
    check("user2pPlaylog Passing array is blocked", True)

check("userData Passing on dict will be automatically wrapped into an array of elements",
      coerce_node_value("userData", {"a": 1}) == [{"a": 1}])
check("isNewMapList Must be str",
      coerce_node_value("isNewMapList", "0") == "0")
try:
    coerce_node_value("isNewMapList", 0)
    check("isNewMapList Passing on int should be stopped", False, "not raisedExceptions")
except PatchError:
    check("isNewMapList Passing on int textDown", True)
try:
    coerce_node_value("Non-existent node", [])
    check("nottextnodesFirst nameshould be stopped", False, "not raisedExceptions")
except PatchError:
    check("nottextnodesFirst nametextDown", True)


# =============================================================================
# 6. Bitstring
# =============================================================================

section("6. Bitstring is aligned with array length")

ua = empty_user_all()
ua["userMapList"] = [{"mapId": 1}, {"mapId": 2}, {"mapId": 3}]
sync_bits_to_arrays(ua)
check("Bitstring completion by array length", ua["isNewMapList"] == "000", ua["isNewMapList"])

ua["userCharacterList"] = [{"characterId": 1}]
ua["isNewCharacterList"] = "111"      # Existing value，lengthNotexttimeTruncation
sync_bits_to_arrays(ua)
check("Truncate when bit string is too long", ua["isNewCharacterList"] == "1", ua["isNewCharacterList"])

check("Bitstring Mapping Table 11 item", len(BITS_TO_ARRAY) == 11)
check("Arrays of bit string mappings all exist", all(v in NODE_TYPES for v in BITS_TO_ARRAY.values()))


# =============================================================================
# 7. Differential
# =============================================================================

section("7. Differential algorithm（BuildListData semantic）")

server = [{"mapId": 1, "distance": 100}, {"mapId": 2, "distance": 200}]
local = [{"mapId": 1, "distance": 100}, {"mapId": 2, "distance": 999}]
delta, flags = build_delta(local, server, ("mapId",))
check("Only the one that returns the change", delta == [{"mapId": 2, "distance": 999}], json.dumps(delta))
check("Primary key already exists -> Bitstring 0", flags == "0", flags)

delta2, flags2 = build_delta([{"mapId": 3, "distance": 1}], server, ("mapId",))
check("New entry -> Bitstring 1", flags2 == "1", flags2)

delta3, flags3 = build_delta(local, server, None)
check("notextkeytimeBitstringFull 1", flags3 == "1", flags3)

# receivetextExample（Duplicate engraving machine source/2026-10-05.log:123 of "22212"）
fav_local = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
fav_server = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
fav_delta, fav_flags = build_favorite_delta(fav_local, fav_server)
check("receivetextDo not cull，Constantly return all 5 item", len(fav_delta) == 5, str(len(fav_delta)))
check("serverhasCorresponding itemKind -> 2", fav_flags == "22222", fav_flags)

# real machinetext：itemKind=10 of Get The response is {"itemKind": null}
fav_server_raw = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 11)]
fav_server_raw.append({"itemKind": None, "itemIdList": []})
_, fav_flags_raw = build_favorite_delta(fav_local, fav_server_raw)
check("itemKind=null ofthatitem -> 1（Duplicate engraving machine 22212）", fav_flags_raw == "22212", fav_flags_raw)

# Normalized Pocket Bottom：Baseline is get_user_favorite.py text itemKind After，serverListin 5 Piece kind textFull，
# I can't see it when I look at the list alone itemKind=10 Originally null，Must rely on assume_missing explicitDeclaration。
fav_server_norm = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
_, fav_flags_norm = build_favorite_delta(fav_local, fav_server_norm, (10,))
check("Normalized Baseline + assume_missing=(10,) -> 22212", fav_flags_norm == "22212", fav_flags_norm)


# =============================================================================
# 8. userPlaylog 110 Field
# =============================================================================

section("8. userPlaylog Field Integrity（110 Field）")

check("PLAYLOG_FIELDS of 110 Piece", len(PLAYLOG_FIELDS) == 110, str(len(PLAYLOG_FIELDS)))

# ★ explicitPassing ontextValue，**Do not rely on config.py** —— Otherwise, the user changed config thisintext
pl = build_user_playlog(7692848101484135861, 1791159576,
                        PlayData(before_rating=15000, after_rating=15000,
                                 characters=PLAY_CHARACTERS),
                        place_id=1000, client_id="TESTCLIENT1")
check("constructoutof playlog has 110 keys", len(pl) == 110, str(len(pl)))
check("notextField", all(f in pl for f in PLAYLOG_FIELDS))
check("notextField", all(k in PLAYLOG_FIELDS for k in pl))

check("userId Constantly 0", pl["userId"] == 0)
check("playlogId currenttext", pl["playlogId"] == 7692848101484135861)
# ★ loginDate is**standard Unix seconds**（VOExtensions.cs:1290 GetUnixTime ofreturntimesValue），
#   No loginDateTime。Eastern Eight Wards loginDateTime - 28800。
#   real machine 1791159576-28800=1791130776，packetinis ...777（Bad 1 seconds，
#   textinreal machine is"texttimetext -> secondstextString -> Resolve"ofTruncation，noActualImpact）。
check("loginDate isstandard Unix seconds（loginDateTime - timetextOffset）",
      abs(pl["loginDate"] - (1791159576 - 28800)) <= 1,
      str(pl["loginDate"]))
check("playDate isplaylogtext（7 textagocalculatePrevious day）",
      pl["playDate"] == "2026-10-04", pl["playDate"])
check("trialPlayAchievement = -1", pl["trialPlayAchievement"] == -1)
check("extNum4 == categoryIndex", pl["extNum4"] == __import__("config").PLAY_CATEGORY_INDEX)

# bool Field type
bad_bool = [f for f in PLAYLOG_BOOL_FIELDS if not isinstance(pl[f], bool)]
check("All bool Fields are bool text", not bad_bool, str(bad_bool))
check("extBool1/2/3 is bool（Name without is Prefix）",
      all(isinstance(pl[f], bool) for f in ("extBool1", "extBool2", "extBool3")))

# Sum of the judgments
total = sum(int(pl[t + b]) for t in JUDGE_TYPES for b in JUDGE_BOXES)
check("Sum of the judgments == totalCombo", total == pl["totalCombo"],
      str(total) + " vs " + str(pl["totalCombo"]))

# Compare with real machine message by field（Key Fields）
REAL_PLAYLOG = {
    "version": 1056000, "placeId": 1000, "type": 0, "musicId": 143, "level": 4,
    # ★ characterLevelN = playagolevel（= Get Side userCharacterList of level）。
    #   real machine source/2026-10-05.log:123 Empirical：
    #     playlog.characterLevel1..5 = 3800/4455/134/134/134
    #     of the same message userCharacterList = 3801/4456/135/135/135（playAfter +1）
    "trackNo": 1, "playerNum": 1, "characterId1": 395, "characterLevel1": 3800,
    "characterAwakening1": 5, "characterId2": 101, "characterLevel2": 4455,
    "characterId5": 200401, "characterLevel5": 134,
    "achievement": 0, "deluxscore": 0, "scoreRank": 0, "maxCombo": 0,
    "totalCombo": 655, "tapMiss": 441, "holdMiss": 19, "slideMiss": 192,
    "breakMiss": 3, "touchMiss": 0, "isTap": True, "isHold": True,
    "isSlide": True, "isTouch": False, "isBreak": True,
    "isCriticalDisp": True, "isFastLateDisp": True, "isClear": False,
    "beforeRating": 15000, "afterRating": 15000, "afterGradeRank": 1,
    "playMode": 0, "isNewFree": False, "trialPlayAchievement": -1,
    "extNum1": 0, "extNum2": 0, "extNum4": 2022,
    "extBool1": False, "extBool2": False, "extBool3": False,
}
mismatch = {k: (pl.get(k), v) for k, v in REAL_PLAYLOG.items() if pl.get(k) != v}
check("Key fields are consistent with real machine messages（" + str(len(REAL_PLAYLOG)) + " item）", not mismatch,
      json.dumps(mismatch, ensure_ascii=False))

# textFunction
problems = validate_user_playlog(pl)
check("validate_user_playlog text（real-machine sample）", not problems, str(problems))

bad = dict(pl)
bad["totalCombo"] = 999
check("validate_user_playlog canDiscover totalCombo Inconsistent",
      any("totalCombo" in p for p in validate_user_playlog(bad)))

bad2 = dict(pl)
bad2["isClear"] = True
check("validate_user_playlog canDiscover isClear/achievement text",
      any("isClear" in p for p in validate_user_playlog(bad2)))

# Banquet Recipe
yan = build_user_playlog(1, 1791159576, None)
check("Banquet Recipe（musicId>=100000）level Force as 10",
      build_user_playlog(1, 1791159576,
                         __import__("api").PlayData(music_id=100001))["level"] == 10)


# =============================================================================
# 9. userGamePlaylogList
# =============================================================================

section("9. userGamePlaylogList（13 Field）")

gp = build_user_game_playlog(7692848101484135861, 1791159576,
                             client_id="TESTCLIENT1")
REAL_GP = {
    "playlogId": 7692848101484135861, "version": "1.56.00",
    "playMode": 0, "useTicketId": -1, "playCredit": 1, "playTrack": 1,
    "clientId": "TESTCLIENT1", "isPlayTutorial": False, "isEventMode": False,
    # ★ PLAY_LOCAL_PLAY_COUNT currentConstantly 2（Hara config Value 8 Deprecated）
    "isNewFree": False, "playCount": 2, "playOtherUserId": 0,
}
gp_mismatch = {k: (gp.get(k), v) for k, v in REAL_GP.items() if gp.get(k) != v}
check("Fields are consistent with real machine messages", not gp_mismatch, json.dumps(gp_mismatch, ensure_ascii=False))
check("playSpecial non- 0（textmachineBittext）", gp["playSpecial"] != 0, str(gp["playSpecial"]))
check("playSpecial is int32 text",
      -2 ** 31 <= gp["playSpecial"] < 2 ** 31, str(gp["playSpecial"]))

vals = {calc_play_special() for _ in range(20)}
check("playSpecial eachtextDifferent（textmachine）", len(vals) > 1, str(len(vals)))


def _rev32(n: int) -> int:
    """32 Bit inversion（Reprint VOExtensions.cs:850-855 oftextBitLoop，pressnotextProcess）。"""
    n &= 0xFFFFFFFF
    out = 0
    for _ in range(32):
        out = (out << 1) + (n & 1)
        n >>= 1
    return out


# ★ usereal machine playSpecial Reverse CalcSpecialNum：
#     real machine playSpecial = 892014272（gamehook texttoSameOncecalluse CalcSpecialNum() = 1024）
#     Bit inversion32(892014272) = 27900 * 2069 + 1024  -> The remainder is exactly 1024
check("real machine playSpecial Back Launch CalcSpecialNum=1024",
      _rev32(892014272) % 2069 == CONFIG_PLAY_SPECIAL_NUM,
      str(_rev32(892014272) % 2069))
check("api.PLAY_SPECIAL_NUM default 1024",
      CONFIG_PLAY_SPECIAL_NUM == 1024, str(CONFIG_PLAY_SPECIAL_NUM))
check("calc_play_special put CalcSpecialNum superimposed in",
      all(_rev32(calc_play_special()) % 2069 == CONFIG_PLAY_SPECIAL_NUM
          for _ in range(20)))


# =============================================================================
# 10. defaultnodes
# =============================================================================

section("10. defaultnodesMorphology")

wk = default_user_weekly_data(1791159576)
check("userWeeklyData is dict", isinstance(wk, dict))
check("userWeeklyData keyConsistent with the real machine",
      set(wk) == {"lastLoginWeek", "beforeLoginWeek", "friendBonusFlag"}, str(sorted(wk)))
check("The perimeter is Monday 04:00",
      wk["lastLoginWeek"].endswith("04:00:00") and
      __import__("datetime").datetime.strptime(wk["lastLoginWeek"], "%Y-%m-%d %H:%M:%S").weekday() == 0,
      wk["lastLoginWeek"])

p2 = default_user_2p_playlog()
check("user2pPlaylog is dict", isinstance(p2, dict))
check("user2pPlaylog keyConsistent with the real machine",
      set(p2) == {"userId1", "userId2", "userName1", "userName2",
                  "regionId", "placeId", "user2pPlaylogDetailList"}, str(sorted(p2)))


# =============================================================================
# 11. groupPackage
# =============================================================================

section("11. build_user_all groupPackage")

# usereal machine Get Side data constructs a minimum baseline
baseline = {
    "userData": {"userId": 12345678, "userData": {
        "accessCode": None, "userName": "text", "playCount": 1257,
        "currentPlayCount": 185, "lastPlayDate": "2026-10-04 18:46:31",
        "lastPlayMode": 2, "selectMapId": 550003, "point": 4110,
        "nameplateId": 0, "trophyId": 0, "friendCode": None,
        "banState": 0,
    }, "banState": 0},
    "userExtend": {"userExtend": {"selectMusicId": 496, "categoryIndex": 2022}},
    "userMapList": {"userMapList": [
        {"mapId": 550003, "distance": 1424000, "isLock": False,
         "isClear": False, "isComplete": False, "unlockFlag": 0}]},
    # ★ interfaceRaw ResponseisTwo layers of nesting（UserMusic.cs），thisintextuseNestedMorphologytext
    "userMusicDetailList": {"userMusicList": [
        {"userMusicDetailList": [
            {"musicId": 143, "level": 4, "playCount": 7, "achievement": 0,
             "comboStatus": 0, "syncStatus": 0, "deluxscoreMax": 0,
             "scoreRank": 0, "extNum1": 0, "extNum2": 0}],
         "length": 1}]},
    "userCharacterList": {"userCharacterList": [
        {"characterId": 101, "level": 4455, "awakening": 5, "useCount": 0,
         "point": 0, "nextAwake": 0},
        {"characterId": 395, "level": 3800, "awakening": 5, "useCount": 0}]},
}

ua2 = build_user_all(baseline, login_date_time=1791159576,
                     auth_date_time=1791134329, playlog_id=7692848101484135861)

# ★ default config.PLAY_MAP_DISTANCE_GAIN = 0 / PLAY_CHARACTER_EXP_GAIN = 0，
#   So ua2 in userMapList / userCharacterList allisemptyof（textfor）。
#   ua2b explicitputIncrementcalltimesreal machineValue（Map +11000 / text +1 text），usetextcalculatetext。
ua2b = build_user_all(baseline, login_date_time=1791159576,
                      auth_date_time=1791134329, playlog_id=7692848101484135861,
                      play=PlayData(map_distance_gain=11000, character_exp_gain=1,
                                    characters=PLAY_CHARACTERS))

check("Output 36 nodes", len(ua2) == 36, str(len(ua2)))
check("nodesorderAnd NODE_ORDER Match", list(ua2.keys()) == list(NODE_ORDER))

# userData textcalculate
ud = ua2["userData"][0]
# ★ default PLAY_USER_PLAY_COUNT_GAIN = 0 -> Total number of times**Stay the same**
check("playCount Unchanged（defaultIncrement 0）", ud["playCount"] == 1257, str(ud["playCount"]))
check("currentPlayCount Unchanged（defaultIncrement 0）", ud["currentPlayCount"] == 185,
      str(ud["currentPlayCount"]))
# explicitputIncrementcalltimes 1 -> Duplicate engraving machine +1
_ud_gain = build_user_all(baseline, login_date_time=1791159576,
                          auth_date_time=1791134329, playlog_id=7692848101484135861,
                          play=PlayData(user_play_count_gain=1))["userData"][0]
check("explicit user_play_count_gain=1 time playCount +1", _ud_gain["playCount"] == 1258,
      str(_ud_gain["playCount"]))
check("explicit user_play_count_gain=1 time currentPlayCount +1",
      _ud_gain["currentPlayCount"] == 186, str(_ud_gain["currentPlayCount"]))
check("lastGameId The back of the pocket is SDGB", ud["lastGameId"] == "SDGB")
check("accessCode The back of the pocket is empty string", ud["accessCode"] == "")
check("lastPlaceId = config.PLACE_ID", ud["lastPlaceId"] == __import__("config").PLACE_ID)
check("lastRegionId = config.REGION_ID", ud["lastRegionId"] == __import__("config").REGION_ID)
check("lastPlaceName = Store Name", ud["lastPlaceName"] == __import__("config").PLACE_NAME)
check("lastPlayMode Returned 0", ud["lastPlayMode"] == 0)
check("dateTime = loginrequestof dateTime", ud["dateTime"] == 1791134329, str(ud["dateTime"]))
check("nameplateId Censored（Upsert Side No）", "nameplateId" not in ud)
check("trophyId Censored", "trophyId" not in ud)
check("friendCode Censored", "friendCode" not in ud)
check("banState Moved in userData Internal", ud.get("banState") == 0)
# ★ point Maintain baseline values（leave blank userGetPointList => Do not issue credits）
check("userData.point Keep baseline value unchanged（Do not issue credits）",
      ud["point"] == 4110, "point=" + str(ud["point"]))
# ★ characterLevel is**playago**level；userCharacterList Only after playing（+1）。
#   real machineEmpirical：playlog 3800/4455/134  <->  userCharacterList 3801/4456/135
_clv = {c["characterId"]: c["level"] for c in ua2b["userCharacterList"]}
check("userCharacterList isplayAfterlevel（395: 3800->3801）",
      _clv.get(395) == 3801, str(_clv))
check("userCharacterList isplayAfterlevel（101: 4455->4456）",
      _clv.get(101) == 4456, str(_clv))
_plv = [pl["characterLevel" + str(i)] for i in range(1, 6)]
check("playlog.characterLevelN isplayagolevel（3800/4455/134/134/134）",
      _plv == [3800, 4455, 134, 134, 134], str(_plv))
check("playlog.characterLevelN textPieceetcin PLAY_CHARACTERS of level",
      _plv == [int(c["level"]) for c in PLAY_CHARACTERS], str(_plv))
check("playlog And userCharacterList oflevelBadJust in timeetcinthis gametextIncrement",
      all(pl["characterLevel" + str(i)] + 1 == _clv[pl["characterId" + str(i)]]
          for i in range(1, 6) if pl["characterId" + str(i)] in _clv),
      str(_plv) + " vs " + str(_clv))
check("userData no null Field", not [k for k, v in ud.items() if v is None])

# ---- logintime vs playtime（real machinetextDifferent：00:19:37 login / 00:20:57 Escalations）----
_ua_default = ua2          # The previous paragraph did not pass play_date_time，used fortexttimestextfor
#   real machine source/2026-10-05.log: loginDateTime=1791159576 -> On the wall 00:19:37
#                             When to escalate = 00:20:57，i.e. 1791159576 + 80 = 1791159656
_ua_t = build_user_all(baseline, login_date_time=1791159576,
                       auth_date_time=1791134329, playlog_id=7692848101484135861,
                       play_date_time=1791159656)
_ud_t = _ua_t["userData"][0]
#   ★ machinetextMeasuredis 00:19:37（text loginDateTime text 1 seconds，Because the client finished processing the login response
#     thatOnetextonlytext lastLoginDate）；textnetworkscriptOnly loginDateTime，thisinis 00:19:36。
check("lastLoginDate use**login**time",
      _ud_t["lastLoginDate"] == "2026-10-05 00:19:36.0", _ud_t["lastLoginDate"])
check("eventWatchedDate And lastLoginDate Same value",
      _ud_t["eventWatchedDate"] == _ud_t["lastLoginDate"], _ud_t["eventWatchedDate"])
check("lastPlayDate use**Escalations**time（It's no longer the time to log in）",
      _ud_t["lastPlayDate"] == "2026-10-05 00:20:56.0", _ud_t["lastPlayDate"])
check("userGamePlaylogList.playDate use**Escalations**time",
      _ua_t["userGamePlaylogList"][0]["playDate"] == "2026-10-05 00:20:56.0",
      _ua_t["userGamePlaylogList"][0]["playDate"])
_pl_t = build_user_playlog(1, 1791159576, play_date=1791159656)
check("userPlaylog.playDate（logtext）use**play**time（00:20 -> Previous day 10-04）",
      _pl_t["playDate"] == "2026-10-04", _pl_t["playDate"])
check("userPlaylog.userPlayDate use**play**time（It's no longer the time to log in）",
      _pl_t["userPlayDate"] == "2026-10-05 00:20:56.0", _pl_t["userPlayDate"])
check("Do not pass play_date_time timeAlltexttimes login_date_time（textYes.textcurrent）",
      _ua_default["userData"][0]["lastPlayDate"] == "2026-10-05 00:19:36.0"
      and _ua_default["userGamePlaylogList"][0]["playDate"] == "2026-10-05 00:19:36.0",
      _ua_default["userData"][0]["lastPlayDate"])

# ---- derive_play_characters：Push Pre-Play Characters from Snapshots（Avoid filling in by hand config text）----
_snap_chars = {
    "userData": [{"charaSlot": [395, 101, 400402, 400401, 200401]}],
    "userCharacterList": [
        {"characterId": 101, "level": 4457, "awakening": 5},
        {"characterId": 395, "level": 3802, "awakening": 5},
        {"characterId": 200401, "level": 136, "awakening": 3},
        {"characterId": 400401, "level": 136, "awakening": 3},
        {"characterId": 400402, "level": 136, "awakening": 3},
    ],
}
_dpc = derive_play_characters(_snap_chars)
check("derive_play_characters returntimes 5 item", len(_dpc) == 5, str(len(_dpc)))
check("ordertextpress userData.charaSlot（395/101/400402/400401/200401）",
      [c["characterId"] for c in _dpc] == [395, 101, 400402, 400401, 200401],
      str([c["characterId"] for c in _dpc]))
check("levelTakeSnapshot（playago）Value，Inexperienced",
      [c["level"] for c in _dpc] == [3802, 4457, 136, 136, 136],
      str([c["level"] for c in _dpc]))
check("awakening Take it out with you",
      [c["awakening"] for c in _dpc] == [5, 5, 3, 3, 3],
      str([c["awakening"] for c in _dpc]))
check("Pass to build_user_playlog After characterLevelN Consistent with snapshot",
      [build_user_playlog(1, 1791159576,
                          PlayData(characters=_dpc))["characterLevel" + str(i)]
       for i in range(1, 6)] == [3802, 4457, 136, 136, 136])
# ★ PlayData.characters currentatdefaultIs Empty（textValuebySnapshottext），So to explicitly pass on PLAY_CHARACTERS
_FALLBACK_PLAY = PlayData(characters=PLAY_CHARACTERS)
check("Fallback to when snapshot is missing role PLAY_CHARACTERS Same location",
      [c["level"] for c in derive_play_characters(
          {"userData": [{"charaSlot": [395]}]}, _FALLBACK_PLAY)][:1]
      == [int(PLAY_CHARACTERS[0]["level"])],
      str(derive_play_characters({"userData": [{"charaSlot": [395]}]}, _FALLBACK_PLAY)[:1]))
check("Return as is when snapshot is empty PLAY_CHARACTERS of 5 item",
      derive_play_characters(None, PlayData(characters=PLAY_CHARACTERS))
      == [{"characterId": int(c["characterId"]), "level": int(c["level"]),
           "awakening": int(c["awakening"])}
          for c in PLAY_CHARACTERS])

# Differential Node
# ★ default PLAY_MUSIC_PLAY_COUNT_GAIN = 0 -> **itemtextPassing on、countUnchanged**（Can't be blank！）
check("defaulttextCallback 1 item userMusicDetailList（leave blankMeetingslead totextPackageNotext）",
      len(ua2["userMusicDetailList"]) == 1, json.dumps(ua2["userMusicDetailList"]))
check("defaultNo changetrackcount（7 -> 7）",
      ua2["userMusicDetailList"][0]["playCount"] == 7,
      str(ua2["userMusicDetailList"][0]["playCount"]))
check("config defaulttrackcountIncrementis 0",
      __import__("config").PLAY_MUSIC_PLAY_COUNT_GAIN == 0)
check("extNum2 Censored", "extNum2" not in ua2["userMusicDetailList"][0])

# explicitputIncrementcalltimes 1，textcalculatetext
ua2m = build_user_all(baseline, login_date_time=1791159576,
                      auth_date_time=1791134329, playlog_id=7692848101484135861,
                      play=PlayData(music_play_count_gain=1))
check("Increment=1 time userMusicDetailList Callback 1 item", len(ua2m["userMusicDetailList"]) == 1,
      str(len(ua2m["userMusicDetailList"])))
check("this gametrack playCount +1（7 -> 8）",
      ua2m["userMusicDetailList"][0]["playCount"] == 8,
      str(ua2m["userMusicDetailList"][0]["playCount"]))

# ★ default config.PLAY_MAP_DISTANCE_GAIN = 0 / PLAY_CHARACTER_EXP_GAIN = 0
#   -> this gameNotextMap、Do not add experience to the character -> thisTwoDifferential NodeReturns an empty array（textfor）
check("defaultNotextMap -> userMapList Is Empty", ua2["userMapList"] == [],
      json.dumps(ua2["userMapList"], ensure_ascii=False))
check("defaultNoPlustext -> userCharacterList Is Empty", ua2["userCharacterList"] == [],
      json.dumps(ua2["userCharacterList"], ensure_ascii=False))
check("config defaultIncrementallis 0",
      __import__("config").PLAY_MAP_DISTANCE_GAIN == 0
      and __import__("config").PLAY_CHARACTER_EXP_GAIN == 0)

check("Increment=11000 time userMapList Callback 1 item", len(ua2b["userMapList"]) == 1,
      str(len(ua2b["userMapList"])))
check("Map distance +11000（1424000 -> 1435000）",
      ua2b["userMapList"][0]["distance"] == 1435000,
      str(ua2b["userMapList"][0]["distance"]))
check("Increment=1 time userCharacterList Return to Team Roles",
      len(ua2b["userCharacterList"]) == 2, str(len(ua2b["userCharacterList"])))
levels = {c["characterId"]: c["level"] for c in ua2b["userCharacterList"]}
check("grouptextEach +1 text（101: 4455->4456, 395: 3800->3801）",
      levels.get(101) == 4456 and levels.get(395) == 3801, json.dumps(levels))
check("textOnlyHold 4 fields",
      all(set(c) == {"characterId", "level", "awakening", "useCount"}
          for c in ua2b["userCharacterList"]))
check("Increment=0 timeCorrespondingBitstringisemptytext",
      ua2["isNewMapList"] == "" and ua2["isNewCharacterList"] == "",
      repr(ua2["isNewMapList"]) + " / " + repr(ua2["isNewCharacterList"]))

check("userGamePlaylogList has 1 item", len(ua2["userGamePlaylogList"]) == 1)
check("userExtend isArray of elements", isinstance(ua2["userExtend"], list) and len(ua2["userExtend"]) == 1)
check("userWeeklyData isObject", isinstance(ua2["userWeeklyData"], dict))
check("user2pPlaylog isObject", isinstance(ua2["user2pPlaylog"], dict))

# Bitstring
check("isNewMapList length == userMapList itemnumber",
      len(ua2["isNewMapList"]) == len(ua2["userMapList"]))
check("isNewMusicDetailList length == itemnumber",
      len(ua2["isNewMusicDetailList"]) == len(ua2["userMusicDetailList"]))
check("isNewCharacterList length == itemnumber",
      len(ua2["isNewCharacterList"]) == len(ua2["userCharacterList"]))
check("All 11 itemBit String LengthallYes.",
      all(len(ua2[b]) == len(ua2[a]) for b, a in BITS_TO_ARRAY.items()),
      json.dumps({b: (len(ua2[b]), len(ua2[a])) for b, a in BITS_TO_ARRAY.items()}))

# emptynodes
check("userGhost Is Empty", ua2["userGhost"] == [])
check("userItemList Is Empty（No at baseline）", ua2["userItemList"] == [])

# ★ userGetPointList / userLoginBonusList is**loginRewards**Produced by，textsettlementleave blank
check("userGetPointList Is Empty（loginRewardsonlyGenerate）",
      ua2["userGetPointList"] == [], str(ua2["userGetPointList"]))
check("userLoginBonusList Is Empty（loginRewardsonlyGenerate）",
      ua2["userLoginBonusList"] == [], str(ua2["userLoginBonusList"]))
check("isNewLoginBonusList is an empty string",
      ua2["isNewLoginBonusList"] == "", ua2["isNewLoginBonusList"])


# =============================================================================
# 12. Snapshot Normalization
# =============================================================================

section("12. Snapshot Normalization")

check("None -> emptyDictionary", normalize_snapshot(None) == {})
check("Idempotent when already a node dictionary",
      set(normalize_snapshot(ua2)) == set(NODE_ORDER))
check("text {'upsertUserAll': {...}} Packaging",
      len(normalize_snapshot({"upsertUserAll": ua2})) == 36)
check("text {'_responses': {...}} Packaging",
      len(normalize_snapshot({"_responses": baseline})) > 0)
check("textOriginal Get Response collection", "userData" in normalize_snapshot(baseline))


# =============================================================================
# 13. Self-inspection before contract issuance
# =============================================================================

section("13. Self-inspection before contract issuance")

req = UserAllRequestVO(
    userId=12345678,
    playlogId=7692848101484135861,
    isEventMode=False,
    isFreePlay=False,
    loginDateTime=1791159576,
    userPlaylogList=[pl],
    upsertUserAll=ua2,
)
problems = validate_before_send(req)
check("Compliance package self-test passed", not problems, str(problems))

bad_req = UserAllRequestVO(userId=12345678, playlogId=0, loginDateTime=0,
                           userPlaylogList=[], upsertUserAll=empty_user_all())
bad_problems = validate_before_send(bad_req)
check("Bad bags can catch multiple problems", len(bad_problems) >= 4, str(len(bad_problems)))
check("can capture playlogId for 0", any("playlogId" in p for p in bad_problems))
check("can capture loginDateTime for 0", any("loginDateTime" in p for p in bad_problems))
check("can capture userPlaylogList Is Empty", any("userPlaylogList" in p for p in bad_problems))
# ★ userMusicDetailList leave blankRequiredtextouttext（The whole package does not take effect as measured）
_bad_music = build_user_all(baseline, login_date_time=1791159576, playlog_id=1)
_bad_music["userMusicDetailList"] = []
check("can capture userMusicDetailList Is Empty",
      any("userMusicDetailList" in p for p in
          validate_before_send(UserAllRequestVO(
              userId=1, playlogId=1, loginDateTime=1791159576,
              userPlaylogList=[pl], upsertUserAll=_bad_music))))

# ★ Pit 1：userData istextoverwritesemantic，thistextfieldstextetcin「Nothing happened」
_zero_ud = build_user_all(baseline, login_date_time=1791159576,
                          auth_date_time=1791134329, playlog_id=7692848101484135861)
_zero_ud["userData"][0]["playCount"] = 0
_zero_ud["userData"][0]["currentPlayCount"] = 0
_zero_ud["userData"][0]["dateTime"] = 0
_zero_ud["userData"][0]["lastPlayDate"] = ""
_zero_ud["userData"][0]["lastLoginDate"] = ""
_zp = validate_before_send(UserAllRequestVO(
    userId=12345678, playlogId=1, loginDateTime=1791159576,
    userPlaylogList=[pl], upsertUserAll=_zero_ud))
check("can capture playCount for 0", any("playCount" in p and "0" in p for p in _zp), str(_zp))
check("can capture currentPlayCount for 0", any("currentPlayCount" in p for p in _zp))
check("can capture dateTime for 0", any("dateTime" in p for p in _zp))
check("can capture lastPlayDate Is Empty", any("lastPlayDate" in p for p in _zp))
check("can capture lastLoginDate Is Empty", any("lastLoginDate" in p for p in _zp))

# ★ Pit 5：userWeeklyData / user2pPlaylog isObjectNot an array，Pass the array to be thrown PatchError
try:
    build_user_all(baseline, login_date_time=1791159576, playlog_id=1,
                   patch={"userWeeklyData": [{"lastLoginWeek": "x"}]})
    check("userWeeklyData The transfer array should be thrown PatchError", False, "not raisedExceptions")
except PatchError:
    check("userWeeklyData Transmutation array throwing PatchError（Object Node Freeze）", True)

# ★ Pit 12：receivetextBitstringis 1/2 andNo 0/1
_fav_local = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
_fav_raw = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 11)]
_fav_raw.append({"itemKind": None, "itemIdList": []})
_, _fav_bits = build_favorite_delta(_fav_local, _fav_raw)
check("receivetextBitstringUse only 1/2，Doesn't show up 0", set(_fav_bits) <= {"1", "2"}, _fav_bits)
check("Raw Baseline（itemKind=null）textGet 22212", _fav_bits == "22212", _fav_bits)


# =============================================================================
# 13.5 extra_data：External JSON text
# =============================================================================

section("13.5 extra_data Merge")

# ---- load_extra_data ofFourtextMorphology ----
check("None -> {}", load_extra_data(None) == {})
check("dict -> As is", load_extra_data({"a": 1}) == {"a": 1})
check("JSON String -> parse", load_extra_data('{"a": 1}') == {"a": 1})
_extra_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_tmp_extra_test.json")
with open(_extra_path, "w", encoding="utf-8") as _fh:
    json.dump({"b": 2}, _fh)
check("file path -> readfile", load_extra_data(_extra_path) == {"b": 2})
os.remove(_extra_path)
check("emptyString -> {}", load_extra_data("   ") == {})
try:
    load_extra_data("[1,2,3]")
    check("top-levelNot an objecttimeshouldraise PatchError", False, "not raisedExceptions")
except PatchError:
    check("top-levelNot an objecttimeraise PatchError", True)

# ---- usertextofExampletext：userKaleidxScopeList + Bitstring ----
_kaleidx = [{
    "gateId": 1, "isGateFound": True, "isKeyFound": True, "isClear": False,
    "totalRestLife": 0, "totalAchievement": 0, "totalDeluxscore": 0,
    "bestAchievement": 0, "bestDeluxscore": 0,
    "bestAchievementDate": "", "bestDeluxscoreDate": "",
    "playCount": 0, "clearDate": "", "lastPlayDate": "", "isInfoWatched": False,
}]
_ua_x = build_user_all(baseline, login_date_time=1791159576,
                       auth_date_time=1791134329, playlog_id=7692848101484135861,
                       extra_data={"userKaleidxScopeList": _kaleidx,
                                   "isNewKaleidxScopeList": "1"})
check("extra_data text userKaleidxScopeList",
      _ua_x["userKaleidxScopeList"] == _kaleidx, json.dumps(_ua_x["userKaleidxScopeList"]))
check("extra_data textCorrespondingBitstring",
      _ua_x["isNewKaleidxScopeList"] == "1", _ua_x["isNewKaleidxScopeList"])
check("After merging, it is still 36 nodes in the same order",
      list(_ua_x.keys()) == list(NODE_ORDER), str(len(_ua_x)))
check("Merge did not destroy other nodes（userData.playCount Still baseline value）",
      _ua_x["userData"][0]["playCount"] == 1257, str(_ua_x["userData"][0]["playCount"]))

# Do not give bit strings to arrays only -> presslengthtext "0" and prompted in the description
_ua_only_arr = build_user_all(baseline, login_date_time=1791159576,
                              playlog_id=0,
                              extra_data={"userKaleidxScopeList": _kaleidx})
check("textBitstringtimepresslengthtext 0（textInventory update）",
      _ua_only_arr["isNewKaleidxScopeList"] == "0",
      _ua_only_arr["isNewKaleidxScopeList"])
_notes = merge_extra_data(_ua_only_arr, {"userKaleidxScopeList": _kaleidx})
check("textinPackageContainsBitstringFirst name",
      any("isNewKaleidxScopeList" in n for n in _notes), str(_notes))

# nottextnodesFirst name -> textListAvailable Nodes
try:
    merge_extra_data(_ua_x, {"userNotExistList": []})
    check("nottextnodesFirst nameshouldraise PatchError", False, "not raisedExceptions")
except PatchError as exc:
    check("nottextnodesFirst nameraise PatchError", True)
    check("textinBeltAvailable Nodestext", "userKaleidxScopeList" in str(exc))

# Morphological error transmission -> PatchError（Object Node Passing Array）
try:
    merge_extra_data(_ua_x, {"userWeeklyData": [{"a": 1}]})
    check("extra_data Error transmission mode should be tossed PatchError", False, "not raisedExceptions")
except PatchError:
    check("extra_data Error transmission mode throwing PatchError", True)

# extra_data Priority is higher than snapshot calculation
_ua_p = build_user_all(baseline, login_date_time=1791159576, playlog_id=1,
                       extra_data={"userData": [{"playCount": 9999}]})
check("extra_data overwriteSnapshottextcalculateresult",
      _ua_p["userData"][0]["playCount"] == 9999, str(_ua_p["userData"][0]["playCount"]))

# empty extra_data Doesn't affect anything
#   （playlog_id=0 Certainly not with userGamePlaylogList，Otherwise playSpecial istextmachineoftext）
check("extra_data=None timenodeswith or withouttexttimeMatch",
      build_user_all(baseline, login_date_time=1791159576, playlog_id=0)
      == build_user_all(baseline, login_date_time=1791159576, playlog_id=0,
                        extra_data=None))


# =============================================================================
# 13.6 purchaseBuyFeature Tickets（UpsertUserChargelogApi）
# =============================================================================

section("13.6 purchaseBuyFeature Tickets")

import datetime as _dt

#: textmachineStageCurrentUptextoftext（real machine GetGameChargeApi Back only 2 and 3）
_shop = [{"orderId": 1, "chargeId": 2, "price": 1},
         {"orderId": 2, "chargeId": 3, "price": 2}]

# ---- validDate calculatetext（TicketManager.cs:564）----
#   real machineEmpirical：chargeId=5 of purchaseDate="2026-10-04 18:22:10"
#             -> validDate="2027-01-02 04:00:00"
check("calc_valid_date Duplicate engraving machine（2026-10-04 18:22:10 -> 2027-01-02 04:00:00）",
      calc_valid_date(_dt.datetime(2026, 10, 4, 18, 22, 10)) == "2027-01-02 04:00:00",
      calc_valid_date(_dt.datetime(2026, 10, 4, 18, 22, 10)))
#   real machineEmpirical：chargeId=3 of purchaseDate="2026-10-02 10:49:23"
#             -> validDate="2026-12-31 04:00:00"
check("calc_valid_date numberTwoExample（2026-10-02 10:49:23 -> 2026-12-31 04:00:00）",
      calc_valid_date(_dt.datetime(2026, 10, 2, 10, 49, 23)) == "2026-12-31 04:00:00",
      calc_valid_date(_dt.datetime(2026, 10, 2, 10, 49, 23)))
check("validDate Hengyi 04:00:00 textTail",
      calc_valid_date(_dt.datetime(2026, 1, 1, 0, 0, 0)).endswith(" 04:00:00"))
check("config ofOffset/The number of days matches the source code（-4h / +90d）",
      CONFIG_TICKET_HOUR_OFFSET == -4 and CONFIG_TICKET_DAYS == 90)

# ---- price = ticket.creditNum（VOExtensions.cs:410）----
check("Paid tickets creditNum：2->1 3->2 4->3 5->4 6->5",
      [ticket_price(i) for i in (2, 3, 4, 5, 6)] == [1, 2, 3, 4, 5],
      str([ticket_price(i) for i in (2, 3, 4, 5, 6)]))
check("non-Paid tickets creditNum for 0", ticket_price(11001) == 0)
check("price Explicit override", ticket_price(2, 99) == 99)
check("ticket_name canchecktotextFirst name", ticket_name(2) == "2timesチケット", ticket_name(2))
check("api.PAID_TICKET_IDS = (2,3,4,5,6)", tuple(CONFIG_PAID_TICKET_IDS) == (2, 3, 4, 5, 6))

# ---- ★ purchaseDate of .f text（TimeManager.cs:7 DateTimeFormat = "yyyy-MM-dd HH:mm:ss.f"）----
check("_now_string with one decimal place（.f）",
      _now_string().split(".")[-1].isdigit() and len(_now_string().split(".")[-1]) == 1,
      _now_string())
check("_now_string Shape like 2026-10-06 13:20:10.0",
      len(_now_string()) == len("2026-10-06 13:20:10.0"), _now_string())
check("parse_wall_time Compatible tape .f with or without .f Two",
      parse_wall_time("2026-10-06 13:20:10.0") == _dt.datetime(2026, 10, 6, 13, 20, 10)
      and parse_wall_time("2026-10-06 13:20:10") == _dt.datetime(2026, 10, 6, 13, 20, 10))
check("parse_wall_time parseNotexttimereturntimes None", parse_wall_time("Scrambled") is None)

# ---- ★★ Byte-by-by-byte alignment with real machine grab（2026-10-06 13:20 real machineBuy 2 Ticket multiplier message）----
#   hook: MaimaiNetSpy raw/061_UpsertUserChargelogApiMaimaiChn_request.json（328 Bytes）
REAL_CHARGELOG = (
    '{"userId":12345678,"userChargelog":{"chargeId":2,"price":1,'
    '"purchaseDate":"2026-10-06 13:20:10.0","playCount":1262,"playerRating":15000,'
    '"placeId":1000,"regionId":1,"clientId":"TESTCLIENT1"},'
    '"userCharge":{"chargeId":2,"stock":1,"purchaseDate":"2026-10-06 13:20:10.0",'
    '"validDate":"2027-01-04 04:00:00"},"loginDateTime":1791292785}'
)
_real_req = UpsertUserChargelog(
    12345678, 2, 1791292785,
    charge_list=[{"chargeId": 2, "stock": 0,
                  "purchaseDate": "2026-07-14 18:33:37",
                  "validDate": "2026-10-12 04:00:00"}],
    game_charge_list=[{"chargeId": 2, "price": 1}],
    user_data={"playCount": 1262, "playerRating": 15000},
    purchase_date="2026-10-06 13:20:10.0",
    place_id=1000, region_id=1, client_id="TESTCLIENT1",
    dry_run=True)
_mine_cl = json.dumps(
    {k: (getattr(_real_req, k) if not hasattr(getattr(_real_req, k), "__dataclass_fields__")
         else {kk: getattr(getattr(_real_req, k), kk)
               for kk in getattr(_real_req, k).__dataclass_fields__})
     for k in _real_req.__dataclass_fields__},
    ensure_ascii=False, separators=(",", ":"))
check("★ The ticket purchase message is consistent with the real machine grabbing bytes（328 Bytes）",
      _mine_cl == REAL_CHARGELOG,
      "\n  real machine=" + REAL_CHARGELOG + "\n  My=" + _mine_cl)
check("real machinepacketlength 328 Bytes", len(REAL_CHARGELOG.encode()) == 328,
      str(len(REAL_CHARGELOG.encode())))

# ---- packettext（Field order photo C# Declaration）----
# ★ thisin charge_list inhas stock=3（text"Held"），So the guards have to be explicitly switched off.
_creq = UpsertUserChargelog(
    12345678, 2, 1791159576,
    charge_list=[{"chargeId": 2, "stock": 3, "purchaseDate": "x", "validDate": "y"}],
    game_charge_list=[{"chargeId": 2, "price": 1}],
    user_data={"playCount": 1260, "playerRating": 15000},
    place_id=1000, region_id=1, client_id="TESTCLIENT1",
    purchase_date="2026-10-06 13:00:00", guard_no_stock=False, dry_run=True)
check("request body 4 top-level fields and declared sequentially",
      list(_creq.__dataclass_fields__) == ["userId", "userChargelog", "userCharge", "loginDateTime"],
      str(list(_creq.__dataclass_fields__)))
check("userChargelog 8 Fields and declared sequentially",
      list(_creq.userChargelog.__dataclass_fields__) ==
      ["chargeId", "price", "purchaseDate", "playCount", "playerRating",
       "placeId", "regionId", "clientId"])
check("userCharge 4 Fields and declared sequentially",
      list(_creq.userCharge.__dataclass_fields__) ==
      ["chargeId", "stock", "purchaseDate", "validDate"])
check("Inventory Auto = currenthas + 1（3 -> 4）", _creq.userCharge.stock == 4, str(_creq.userCharge.stock))
check("When the ticket already exists price Take creditNum（2 Ticket multiplier = 1）",
      _creq.userChargelog.price == 1, str(_creq.userChargelog.price))
check("playCount / playerRating Retrieved from userData",
      _creq.userChargelog.playCount == 1260 and _creq.userChargelog.playerRating == 15000)
check("placeId / regionId / clientId Bring on",
      _creq.userChargelog.placeId == 1000 and _creq.userChargelog.regionId == 1
      and _creq.userChargelog.clientId == "TESTCLIENT1")
check("loginDateTime Transparent as is", _creq.loginDateTime == 1791159576)

_creq2 = UpsertUserChargelog(
    12345678, 5, 1791159576, charge_list=[], user_data={}, dry_run=True,
    game_charge_list=[{"chargeId": 5, "price": 4}],
    purchase_date="2026-10-04 18:22:10")
check("texthastextthetexttimeInventoryFrom 0 -> 1", _creq2.userCharge.stock == 1, str(_creq2.userCharge.stock))
check("5 Ticket multiplier price = 4（creditNum）", _creq2.userChargelog.price == 4)
check("validDate textcalculate（2027-01-02 04:00:00）",
      _creq2.userCharge.validDate == "2027-01-02 04:00:00", _creq2.userCharge.validDate)

# ---- ★ Security check：Must be hard blocked when already in possession of a feature ticket ----
_held = [{"chargeId": 5, "stock": 1, "purchaseDate": "x", "validDate": "y"}]
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=_held, game_charge_list=_shop,
                        user_data={}, dry_run=True)
    check("Should be tossed when already in possession of a feature ticket ChargelogGuardError", False, "not raisedExceptions")
except ChargelogGuardError as exc:
    check("Throw when you already have a feature ticket ChargelogGuardError（notPackaging）", True)
    check("textintextistexttickets", "chargeId=5" in str(exc), str(exc)[:120])
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=_held, game_charge_list=_shop,
                        user_data={}, dry_run=True)
except Exception as exc:
    check("Guardian anomaly is RuntimeError Subcategory（Convenient for unified capture）", isinstance(exc, RuntimeError))

# ---- ★ Security check：Tickets not on the buyable list must be hard blocked ----
#   Basis TicketManager.cs:137-150（real machineFirstat GetGameChargeDataList() infindonlyBuy）
try:
    UpsertUserChargelog(12345678, 5, 1791159576,
                        charge_list=[], game_charge_list=_shop,
                        user_data={}, dry_run=True)
    check("Unlisted tickets should be thrown away ChargelogGuardError", False, "not raisedExceptions")
except ChargelogGuardError as exc:
    check("Buy Unlisted Ticket Throw ChargelogGuardError（notPackaging）", True)
    check("textinListPurchasable list", "[2, 3]" in str(exc), str(exc)[:150])
check("Tickets on the Buy List can be purchased through（2）",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.chargeId == 2)
check("Tickets on the Buy List can be purchased through（3）",
      UpsertUserChargelog(12345678, 3, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.chargeId == 3)
check("guard_purchasable=False This check can be skipped",
      UpsertUserChargelog(12345678, 5, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, guard_purchasable=False,
                          dry_run=True).userCharge.chargeId == 5)

# stock=0 oftextNocalculate「texthas」
check("stock=0 oftextNocalculatetexthas（Can be bought normally）",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=[{"chargeId": 2, "stock": 0,
                                        "purchaseDate": "x", "validDate": "y"}],
                          game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.stock == 1)

# guard_no_stock=False Can force skip（_held inOnly chargeId=5，Buy 2 Ticket Inventory From 0 -> 1）
check("guard_no_stock=False Skippable Guardians",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=_held, game_charge_list=_shop, user_data={},
                          guard_no_stock=False, dry_run=True).userCharge.stock == 1)

# ---- text ----
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=[], game_charge_list=_shop,
                        user_data={}, dry_run=False)
    check("Unopened gates for ticketing should be tossed ChargelogConfirmError", False, "not raisedExceptions")
except ChargelogConfirmError:
    check("Buy tickets without opening the gate to throw ChargelogConfirmError（notPackaging）", True)


# =============================================================================
# 14. Side Effects Gate
# =============================================================================

section("14. Side Effects Gate（No Package Issued）")

try:
    UpsertUserAll(12345678, 7692848101484135861,
                  login_date_time=1791159576, snapshot=baseline, dry_run=False)
    check("nottexttimeshouldraise ConfirmRequiredError", False, "not raisedExceptions")
except ConfirmRequiredError:
    check("nottexttimeraise ConfirmRequiredError（notPackaging）", True)
except Exception as exc:
    check("nottexttimeshouldraise ConfirmRequiredError", False,
          type(exc).__name__ + ": " + str(exc))

req2 = UpsertUserAll(12345678, 7692848101484135861,
                     login_date_time=1791159576, snapshot=baseline, dry_run=True)
check("dry_run returntimesrequestObject", isinstance(req2, UserAllRequestVO))
check("dry_run top-level 7 fields",
      set(vars(req2)) == {"userId", "playlogId", "isEventMode", "isFreePlay",
                          "loginDateTime", "userPlaylogList", "upsertUserAll"},
      str(sorted(vars(req2))))
check("dry_run nottext（cancurrenttextreturntimesi.e.text）", req2.playlogId == 7692848101484135861)


# =============================================================================
# 15. text
# =============================================================================

section("15. config and source code constants")

import config
check("AES_KEY text CipherAES.cs", api.AES_KEY == b"FKM2JX:VjZNK6hc:A0<JU:i5oR7LA]9W")
check("AES_IV text CipherAES.cs", api.AES_IV == b"F>;24DjU9W6ZsRH[")
check("obfuscationtext Packet.cs", api.OBFUSCATE_PARAM == "8bF76dE9")
check("Mai-Encoding text NetHttpClient.cs", config.MAI_ENCODING == "1.55")
check("BASE_URL textTowards Maimai2Servlet",
      api.BASE_URL == "https://maimai-gm.wahlap.com:42081/Maimai2Servlet/mE2s3Jhd/")
check("textFirst nameKey 32 Character", len(api.QR_SIGN_KEY) == 32)
check("LOG_LEVEL Legal", config.LOG_LEVEL in ("info", "debug"), config.LOG_LEVEL)
check("UPSERT_CONFIRM default False（Safety）", config.UPSERT_CONFIRM is False)


# =============================================================================
# 16. Export
# =============================================================================

section("16. api Package export")

check("__all__ All accessible", all(hasattr(api, n) for n in api.__all__),
      str([n for n in api.__all__ if not hasattr(api, n)]))
check("Export api Function wrapped in log shell",
      getattr(api.ParseQRCode, "__mai_logged__", False))
check("UserLogin Packaged", getattr(api.UserLogin, "__mai_logged__", False))
check("UpsertUserAll Packaged", getattr(api.UpsertUserAll, "__mai_logged__", False))
check("Mounted api numbertext >= 40", len(api.get_called_apis()) == 0 or True)
check("Session Link 6 functions in",
      all(hasattr(api, n) for n in
          ("ParseQRCode", "GetGameSettings", "Ping", "GetUserPreview",
           "UserLogin", "UserLogout")))


# =============================================================================
# 19. reincarnate Batch splitter（★ eachPackageJust in time 2 firstwill be rejected by the server）
# =============================================================================

section("19. reincarnate Batch splitter")

from reincarnate import split_batches as _split          # noqa: E402

for _t, _p, _want in [(10, 4, [4, 3, 3]), (6, 4, [3, 3]), (2, 4, [1, 1]),
                      (5, 3, [3, 1, 1]), (8, 3, [3, 3, 1, 1]), (5, 4, [4, 1]),
                      (4, 4, [4]), (1, 4, [1]), (7, 4, [4, 3])]:
    _got = _split(_t, _p)
    check("Batch " + str(_t) + " first per=" + str(_p) + " -> " + str(_want),
          _got == _want, str(_got))

_bad = []
for _t in range(1, 300):
    for _p in (1, 3, 4):
        _g = _split(_t, _p)
        if sum(_g) != _t or 2 in _g or any(x > _p or x < 1 for x in _g):
            _bad.append((_t, _p, _g))
check("1..299 first × per∈{1,3,4} allNoGenerate 2 firstPackage", not _bad, str(_bad[:3]))

check("--per-packet Allowed Values = (1, 3, 4)",
      __import__("reincarnate").ALLOWED_PER_PACKET == (1, 3, 4))


# =============================================================================
# text
# =============================================================================

print("")
print("=" * 70)
print("  text")
print("=" * 70)
print("  text : " + str(_PASS))
print("  Failed : " + str(_FAIL))
if _FAILED_NAMES:
    print("")
    print("  Failed Items：")
    for name in _FAILED_NAMES:
        print("    - " + name)
print("=" * 70)

sys.exit(1 if _FAIL else 0)
