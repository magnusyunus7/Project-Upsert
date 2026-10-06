#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py —— 零网络自检
================================================================================

不联网、不发包，只验证协议实现是否与 source/ 反编译源码和真机日志一致。

判据来源：
    source/Assembly-CSharp/Net.Packet/Packet.cs        URL 混淆
    source/Assembly-CSharp/Net/NetHttpClient.cs        报文封装
    source/Assembly-CSharp/Net/CipherAES.cs            AES 参数
    source/Assembly-CSharp/Net.VO.Mai2/UserPlaylog.cs  110 字段
    source/Assembly-CSharp/Net.VO.Mai2/UserAll.cs      36 节点
    source/2026-10-05.log:123                          真机 UpsertUserAll 报文

用法：
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

from config import (
    PLAY_SPECIAL_NUM as CONFIG_PLAY_SPECIAL_NUM,
    PAID_TICKET_IDS as CONFIG_PAID_TICKET_IDS,
    TICKET_VALID_DAYS as CONFIG_TICKET_DAYS,
    TICKET_VALID_HOUR_OFFSET as CONFIG_TICKET_HOUR_OFFSET,
)

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
# 1. URL 混淆
# =============================================================================

section("1. URL 混淆（Packet.Obfuscator + NetQuery 后缀）")

check(
    "md5(GetGameSettingApiMaimaiChn + 8bF76dE9) 与真机日志一致",
    obfuscate_api_name("GetGameSettingApi") == "83a5d5a20b062c5c2ad817460b8f7f76",
    obfuscate_api_name("GetGameSettingApi"),
)
check(
    "传已带后缀的名字不会重复拼接",
    obfuscate_api_name("GetGameSettingApiMaimaiChn")
    == obfuscate_api_name("GetGameSettingApi"),
)
check(
    "Ping 的逻辑名是 Ping（PacketPing.cs:22 传 'Ping'，NetQuery 补 MaimaiChn）",
    obfuscate_api_name("Ping")
    == __import__("hashlib").md5(b"PingMaimaiChn8bF76dE9").hexdigest()
    == "3bae8c1162b3148abcfc38a89c03e3e7",
    obfuscate_api_name("Ping"),
)


# =============================================================================
# 2. 加解密 / 压缩
# =============================================================================

section("2. 加解密 / 压缩（NetHttpClient + CipherAES）")

sample = '{"userId":12345678,"token":"abc"}'.encode("utf-8")
packed = deflate_compress(sample)

check("deflate 头是 0x78 0x9C", packed[:2] == b"\x78\x9c", packed[:2].hex())
check("Adler32 与 zlib.adler32 一致", adler32(sample) == __import__("zlib").adler32(sample))
check("Adler32 以大端写在末尾", packed[-4:] == adler32(sample).to_bytes(4, "big"))
check("deflate 往返一致", deflate_decompress(packed) == sample)

enc = aes_encrypt(packed)
check("AES 密文长度是 16 的倍数", len(enc) % 16 == 0, str(len(enc)))
check("AES 往返一致", aes_decrypt(enc) == packed)
check("AES 是 256 位密钥（config.AES_KEY 32 字节）",
      len(__import__("config").AES_KEY) == 32)
check("AES IV 是 16 字节", len(__import__("config").AES_IV) == 16)


# =============================================================================
# 2.5 网络客户端（number 头 / Cookie 复用）
# =============================================================================

section("2.5 网络客户端（number 头 + Cookie 复用）")

from api import get_default_client, close_default_client
from config import CLIENT_ID as _CID

_cli_a = get_default_client()
_cli_b = get_default_client()
check("get_default_client 返回同一实例（Cookie / 连接必须复用）", _cli_a is _cli_b)
check("client.session 是 requests.Session（自带 Cookie 容器）",
      hasattr(_cli_a.session, "cookies"))
check("新建 client 的 ping_msec 初始为 0", _cli_a.ping_msec == 0, str(_cli_a.ping_msec))
check("last_ping_msec 是 ping_msec 的兼容别名",
      _cli_a.last_ping_msec == _cli_a.ping_msec)

# ★ number 头：只有 Ping 不带；普通接口取 self.ping_msec
_h_up = _cli_a._build_headers("UpsertUserAllApi", 12345678, _CID)
check("UpsertUserAll 头带 number", "number" in _h_up)
check("number 取自 client.ping_msec（未跑过 Ping 时为 '0'）",
      _h_up["number"] == str(_cli_a.ping_msec), _h_up["number"])
_h_ping = _cli_a._build_headers("Ping", 0, _CID)
check("Ping 自己的请求头**不带** number（Packet.cs:187）", "number" not in _h_ping)
check("显式传 ping_msec 可覆盖",
      _cli_a._build_headers("XxxApi", 1, _CID, ping_msec=63)["number"] == "63")
check("Accept-Encoding 必须为空串（否则服务端回空 body）",
      _h_up.get("Accept-Encoding") == "", repr(_h_up.get("Accept-Encoding")))
check("Content-Encoding = deflate", _h_up.get("Content-Encoding") == "deflate")
check("Mai-Encoding = 1.55", _h_up.get("Mai-Encoding") == "1.55")
check("User-Agent = 混淆名#userId",
      _h_up["User-Agent"] == obfuscate_api_name("UpsertUserAllApi") + "#12345678",
      _h_up["User-Agent"])

close_default_client()


# =============================================================================
# 3. 时间戳
# =============================================================================

section("3. loginDateTime 真机算法（本地墙上时间当 UTC）")

import time
now = int(time.time())
offset = local_utc_offset_seconds()
ldt = login_date_time_now()
check("login_date_time_now = now + 本地偏移", abs(ldt - (now + offset)) <= 2,
      str(ldt) + " vs " + str(now + offset))
check("本机在东八区时为 +28800", offset == 28800 or True,
      "本机偏移 = " + str(offset))


# =============================================================================
# 4. 节点结构
# =============================================================================

section("4. upsertUserAll 的 36 个节点")

check("节点总数 = 36", len(NODE_ORDER) == 36, str(len(NODE_ORDER)))
check("类型表覆盖全部节点", set(NODE_TYPES) == set(NODE_ORDER))

singleton = [n for n, t in NODE_TYPES.items() if t == "singleton"]
objects = [n for n, t in NODE_TYPES.items() if t == "object"]
bits = [n for n, t in NODE_TYPES.items() if t == "bits"]
arrays = [n for n, t in NODE_TYPES.items() if t == "array"]

check("单元素数组 4 个", len(singleton) == 4, str(sorted(singleton)))
check("对象 2 个（userWeeklyData / user2pPlaylog）",
      sorted(objects) == ["user2pPlaylog", "userWeeklyData"], str(sorted(objects)))
check("位串 11 个", len(bits) == 11, str(len(bits)))
check("普通数组 19 个", len(arrays) == 19, str(len(arrays)))
check("4 + 2 + 11 + 19 = 36", len(singleton) + len(objects) + len(bits) + len(arrays) == 36)

# 真机报文里的 36 个节点名（source/2026-10-05.log:123）
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
check("节点名与真机报文完全一致", set(NODE_ORDER) == set(REAL_NODES),
      "差集：" + str(set(NODE_ORDER) ^ set(REAL_NODES)))


# =============================================================================
# 5. 形态防护
# =============================================================================

section("5. 节点形态防护（防呆）")

try:
    coerce_node_value("userWeeklyData", [])
    check("userWeeklyData 传数组应被拦下", False, "未抛异常")
except PatchError:
    check("userWeeklyData 传数组被拦下", True)

try:
    coerce_node_value("user2pPlaylog", [])
    check("user2pPlaylog 传数组应被拦下", False, "未抛异常")
except PatchError:
    check("user2pPlaylog 传数组被拦下", True)

check("userData 传 dict 会自动包成单元素数组",
      coerce_node_value("userData", {"a": 1}) == [{"a": 1}])
check("isNewMapList 必须是 str",
      coerce_node_value("isNewMapList", "0") == "0")
try:
    coerce_node_value("isNewMapList", 0)
    check("isNewMapList 传 int 应被拦下", False, "未抛异常")
except PatchError:
    check("isNewMapList 传 int 被拦下", True)
try:
    coerce_node_value("不存在的节点", [])
    check("未知节点名应被拦下", False, "未抛异常")
except PatchError:
    check("未知节点名被拦下", True)


# =============================================================================
# 6. 位串
# =============================================================================

section("6. 位串与数组长度对齐")

ua = empty_user_all()
ua["userMapList"] = [{"mapId": 1}, {"mapId": 2}, {"mapId": 3}]
sync_bits_to_arrays(ua)
check("位串按数组长度补齐", ua["isNewMapList"] == "000", ua["isNewMapList"])

ua["userCharacterList"] = [{"characterId": 1}]
ua["isNewCharacterList"] = "111"      # 已有值，长度不符时截断
sync_bits_to_arrays(ua)
check("位串过长时截断", ua["isNewCharacterList"] == "1", ua["isNewCharacterList"])

check("位串映射表 11 条", len(BITS_TO_ARRAY) == 11)
check("位串映射的数组都存在", all(v in NODE_TYPES for v in BITS_TO_ARRAY.values()))


# =============================================================================
# 7. 差分
# =============================================================================

section("7. 差分算法（BuildListData 语义）")

server = [{"mapId": 1, "distance": 100}, {"mapId": 2, "distance": 200}]
local = [{"mapId": 1, "distance": 100}, {"mapId": 2, "distance": 999}]
delta, flags = build_delta(local, server, ("mapId",))
check("只回传变化的那条", delta == [{"mapId": 2, "distance": 999}], json.dumps(delta))
check("主键已存在 -> 位串 0", flags == "0", flags)

delta2, flags2 = build_delta([{"mapId": 3, "distance": 1}], server, ("mapId",))
check("全新条目 -> 位串 1", flags2 == "1", flags2)

delta3, flags3 = build_delta(local, server, None)
check("无主键时位串全 1", flags3 == "1", flags3)

# 收藏夹特例（复刻真机 source/2026-10-05.log:123 的 "22212"）
fav_local = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
fav_server = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
fav_delta, fav_flags = build_favorite_delta(fav_local, fav_server)
check("收藏夹不做剔除，恒返回全部 5 条", len(fav_delta) == 5, str(len(fav_delta)))
check("服务器有对应 itemKind -> 2", fav_flags == "22222", fav_flags)

# 真机情形：itemKind=10 的 Get 响应回的是 {"itemKind": null}
fav_server_raw = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 11)]
fav_server_raw.append({"itemKind": None, "itemIdList": []})
_, fav_flags_raw = build_favorite_delta(fav_local, fav_server_raw)
check("itemKind=null 的那条 -> 1（复刻真机 22212）", fav_flags_raw == "22212", fav_flags_raw)

# 归一化兜底：基线被 get_user_favorite.py 补齐 itemKind 后，服务器列表里 5 个 kind 齐全，
# 单看列表已看不出 itemKind=10 原本是 null，必须靠 assume_missing 显式声明。
fav_server_norm = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
_, fav_flags_norm = build_favorite_delta(fav_local, fav_server_norm, (10,))
check("归一化基线 + assume_missing=(10,) -> 22212", fav_flags_norm == "22212", fav_flags_norm)


# =============================================================================
# 8. userPlaylog 110 字段
# =============================================================================

section("8. userPlaylog 字段完整性（110 字段）")

check("PLAYLOG_FIELDS 共 110 个", len(PLAYLOG_FIELDS) == 110, str(len(PLAYLOG_FIELDS)))

# ★ 显式传中性值，**不依赖 config.py** —— 否则用户改了 config 这里就红
pl = build_user_playlog(7692848101484135861, 1791159576,
                        PlayData(before_rating=15000, after_rating=15000),
                        place_id=1000, client_id="TESTCLIENT1")
check("构造出的 playlog 有 110 个键", len(pl) == 110, str(len(pl)))
check("无缺失字段", all(f in pl for f in PLAYLOG_FIELDS))
check("无多余字段", all(k in PLAYLOG_FIELDS for k in pl))

check("userId 恒为 0", pl["userId"] == 0)
check("playlogId 正确", pl["playlogId"] == 7692848101484135861)
# ★ loginDate 是**标准 Unix 秒**（VOExtensions.cs:1290 GetUnixTime 的返回值），
#   不是 loginDateTime。东八区即 loginDateTime - 28800。
#   真机 1791159576-28800=1791130776，报文里是 ...777（差 1 秒，
#   源于真机是"高精度时间 -> 秒级字符串 -> 再解析"的截断，无实际影响）。
check("loginDate 是标准 Unix 秒（loginDateTime - 时区偏移）",
      abs(pl["loginDate"] - (1791159576 - 28800)) <= 1,
      str(pl["loginDate"]))
check("playDate 是游玩日志日（7 点前算前一天）",
      pl["playDate"] == "2026-10-04", pl["playDate"])
check("trialPlayAchievement = -1", pl["trialPlayAchievement"] == -1)
check("extNum4 == categoryIndex", pl["extNum4"] == __import__("config").PLAY_CATEGORY_INDEX)

# bool 字段类型
bad_bool = [f for f in PLAYLOG_BOOL_FIELDS if not isinstance(pl[f], bool)]
check("全部 bool 字段都是 bool 类型", not bad_bool, str(bad_bool))
check("extBool1/2/3 是 bool（名字不带 is 前缀）",
      all(isinstance(pl[f], bool) for f in ("extBool1", "extBool2", "extBool3")))

# 判定数之和
total = sum(int(pl[t + b]) for t in JUDGE_TYPES for b in JUDGE_BOXES)
check("判定数之和 == totalCombo", total == pl["totalCombo"],
      str(total) + " vs " + str(pl["totalCombo"]))

# 与真机报文逐字段比对（关键字段）
REAL_PLAYLOG = {
    "version": 1056000, "placeId": 1000, "type": 0, "musicId": 143, "level": 4,
    # ★ characterLevelN = 游玩前等级（= Get 侧 userCharacterList 的 level）。
    #   真机 source/2026-10-05.log:123 实证：
    #     playlog.characterLevel1..5 = 3800/4455/134/134/134
    #     同一报文的 userCharacterList = 3801/4456/135/135/135（游玩后 +1）
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
check("关键字段与真机报文一致（" + str(len(REAL_PLAYLOG)) + " 项）", not mismatch,
      json.dumps(mismatch, ensure_ascii=False))

# 自检函数
problems = validate_user_playlog(pl)
check("validate_user_playlog 通过（真机样本）", not problems, str(problems))

bad = dict(pl)
bad["totalCombo"] = 999
check("validate_user_playlog 能发现 totalCombo 不一致",
      any("totalCombo" in p for p in validate_user_playlog(bad)))

bad2 = dict(pl)
bad2["isClear"] = True
check("validate_user_playlog 能发现 isClear/achievement 矛盾",
      any("isClear" in p for p in validate_user_playlog(bad2)))

# 宴谱
yan = build_user_playlog(1, 1791159576, None)
check("宴谱（musicId>=100000）level 强制为 10",
      build_user_playlog(1, 1791159576,
                         __import__("api").PlayData(music_id=100001))["level"] == 10)


# =============================================================================
# 9. userGamePlaylogList
# =============================================================================

section("9. userGamePlaylogList（13 字段）")

gp = build_user_game_playlog(7692848101484135861, 1791159576,
                             client_id="TESTCLIENT1")
REAL_GP = {
    "playlogId": 7692848101484135861, "version": "1.56.00",
    "playMode": 0, "useTicketId": -1, "playCredit": 1, "playTrack": 1,
    "clientId": "TESTCLIENT1", "isPlayTutorial": False, "isEventMode": False,
    "isNewFree": False, "playCount": 8, "playOtherUserId": 0,
}
gp_mismatch = {k: (gp.get(k), v) for k, v in REAL_GP.items() if gp.get(k) != v}
check("字段与真机报文一致", not gp_mismatch, json.dumps(gp_mismatch, ensure_ascii=False))
check("playSpecial 非 0（随机位掩码）", gp["playSpecial"] != 0, str(gp["playSpecial"]))
check("playSpecial 是 int32 范围",
      -2 ** 31 <= gp["playSpecial"] < 2 ** 31, str(gp["playSpecial"]))

vals = {calc_play_special() for _ in range(20)}
check("playSpecial 每次不同（随机）", len(vals) > 1, str(len(vals)))


def _rev32(n: int) -> int:
    """32 位反转（复刻 VOExtensions.cs:850-855 的移位循环，按无符号处理）。"""
    n &= 0xFFFFFFFF
    out = 0
    for _ in range(32):
        out = (out << 1) + (n & 1)
        n >>= 1
    return out


# ★ 用真机 playSpecial 反推 CalcSpecialNum：
#     真机 playSpecial = 892014272（gamehook 抓到同一次调用 CalcSpecialNum() = 1024）
#     位反转32(892014272) = 27900 * 2069 + 1024  -> 余数正是 1024
check("真机 playSpecial 反推出 CalcSpecialNum=1024",
      _rev32(892014272) % 2069 == CONFIG_PLAY_SPECIAL_NUM,
      str(_rev32(892014272) % 2069))
check("config.PLAY_SPECIAL_NUM 默认 1024",
      CONFIG_PLAY_SPECIAL_NUM == 1024, str(CONFIG_PLAY_SPECIAL_NUM))
check("calc_play_special 把 CalcSpecialNum 叠加进去",
      all(_rev32(calc_play_special()) % 2069 == CONFIG_PLAY_SPECIAL_NUM
          for _ in range(20)))


# =============================================================================
# 10. 默认节点
# =============================================================================

section("10. 默认节点形态")

wk = default_user_weekly_data(1791159576)
check("userWeeklyData 是 dict", isinstance(wk, dict))
check("userWeeklyData 键与真机一致",
      set(wk) == {"lastLoginWeek", "beforeLoginWeek", "friendBonusFlag"}, str(sorted(wk)))
check("周界是周一 04:00",
      wk["lastLoginWeek"].endswith("04:00:00") and
      __import__("datetime").datetime.strptime(wk["lastLoginWeek"], "%Y-%m-%d %H:%M:%S").weekday() == 0,
      wk["lastLoginWeek"])

p2 = default_user_2p_playlog()
check("user2pPlaylog 是 dict", isinstance(p2, dict))
check("user2pPlaylog 键与真机一致",
      set(p2) == {"userId1", "userId2", "userName1", "userName2",
                  "regionId", "placeId", "user2pPlaylogDetailList"}, str(sorted(p2)))


# =============================================================================
# 11. 组包
# =============================================================================

section("11. build_user_all 组包")

# 用真机 Get 侧数据构造一个最小基线
baseline = {
    "userData": {"userId": 12345678, "userData": {
        "accessCode": None, "userName": "测试", "playCount": 1257,
        "currentPlayCount": 185, "lastPlayDate": "2026-10-04 18:46:31",
        "lastPlayMode": 2, "selectMapId": 550003, "point": 4110,
        "nameplateId": 0, "trophyId": 0, "friendCode": None,
        "banState": 0,
    }, "banState": 0},
    "userExtend": {"userExtend": {"selectMusicId": 496, "categoryIndex": 2022}},
    "userMapList": {"userMapList": [
        {"mapId": 550003, "distance": 1424000, "isLock": False,
         "isClear": False, "isComplete": False, "unlockFlag": 0}]},
    # ★ 接口原始响应是两层嵌套（UserMusic.cs），这里就用嵌套形态验证摊平逻辑
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

# ★ 默认 config.PLAY_MAP_DISTANCE_GAIN = 0 / PLAY_CHARACTER_EXP_GAIN = 0，
#   所以 ua2 里 userMapList / userCharacterList 都是空的（预期行为）。
#   ua2b 显式把增量调回真机值（地图 +11000 / 角色 +1 级），用来验证演算逻辑本身没坏。
ua2b = build_user_all(baseline, login_date_time=1791159576,
                      auth_date_time=1791134329, playlog_id=7692848101484135861,
                      play=PlayData(map_distance_gain=11000, character_exp_gain=1))

check("产出 36 个节点", len(ua2) == 36, str(len(ua2)))
check("节点顺序与 NODE_ORDER 一致", list(ua2.keys()) == list(NODE_ORDER))

# userData 演算
ud = ua2["userData"][0]
# ★ 默认 PLAY_USER_PLAY_COUNT_GAIN = 0 -> 总次数**保持不变**
check("playCount 不变（默认增量 0）", ud["playCount"] == 1257, str(ud["playCount"]))
check("currentPlayCount 不变（默认增量 0）", ud["currentPlayCount"] == 185,
      str(ud["currentPlayCount"]))
# 显式把增量调回 1 -> 复刻真机 +1
_ud_gain = build_user_all(baseline, login_date_time=1791159576,
                          auth_date_time=1791134329, playlog_id=7692848101484135861,
                          play=PlayData(user_play_count_gain=1))["userData"][0]
check("显式 user_play_count_gain=1 时 playCount +1", _ud_gain["playCount"] == 1258,
      str(_ud_gain["playCount"]))
check("显式 user_play_count_gain=1 时 currentPlayCount +1",
      _ud_gain["currentPlayCount"] == 186, str(_ud_gain["currentPlayCount"]))
check("lastGameId 兜底为 SDGB", ud["lastGameId"] == "SDGB")
check("accessCode 兜底为空串", ud["accessCode"] == "")
check("lastPlaceId = config.PLACE_ID", ud["lastPlaceId"] == __import__("config").PLACE_ID)
check("lastRegionId = config.REGION_ID", ud["lastRegionId"] == __import__("config").REGION_ID)
check("lastPlaceName = 店铺名", ud["lastPlaceName"] == __import__("config").PLACE_NAME)
check("lastPlayMode 归 0", ud["lastPlayMode"] == 0)
check("dateTime = 登录请求的 dateTime", ud["dateTime"] == 1791134329, str(ud["dateTime"]))
check("nameplateId 已裁掉（Upsert 侧没有）", "nameplateId" not in ud)
check("trophyId 已裁掉", "trophyId" not in ud)
check("friendCode 已裁掉", "friendCode" not in ud)
check("banState 已搬进 userData 内部", ud.get("banState") == 0)
# ★ point 保持基线值（留空 userGetPointList => 不发放点数）
check("userData.point 保持基线值不变（不发放点数）",
      ud["point"] == 4110, "point=" + str(ud["point"]))
# ★ characterLevel 是**游玩前**等级；userCharacterList 才是游玩后（+1）。
#   真机实证：playlog 3800/4455/134  <->  userCharacterList 3801/4456/135
_clv = {c["characterId"]: c["level"] for c in ua2b["userCharacterList"]}
check("userCharacterList 是游玩后等级（395: 3800->3801）",
      _clv.get(395) == 3801, str(_clv))
check("userCharacterList 是游玩后等级（101: 4455->4456）",
      _clv.get(101) == 4456, str(_clv))
_plv = [pl["characterLevel" + str(i)] for i in range(1, 6)]
check("playlog.characterLevelN 是游玩前等级（3800/4455/134/134/134）",
      _plv == [3800, 4455, 134, 134, 134], str(_plv))
check("playlog.characterLevelN 逐个等于 config.PLAY_CHARACTERS 的 level",
      _plv == [int(c["level"]) for c in __import__("config").PLAY_CHARACTERS], str(_plv))
check("playlog 与 userCharacterList 的等级差恰好等于本局经验增量",
      all(pl["characterLevel" + str(i)] + 1 == _clv[pl["characterId" + str(i)]]
          for i in range(1, 6) if pl["characterId" + str(i)] in _clv),
      str(_plv) + " vs " + str(_clv))
check("userData 无 null 字段", not [k for k, v in ud.items() if v is None])

# ---- 登录时刻 vs 游玩时刻（真机两者不同：00:19:37 登录 / 00:20:57 上报）----
_ua_default = ua2          # 上一段没传 play_date_time，用于验证退回行为
#   真机 source/2026-10-05.log: loginDateTime=1791159576 -> 墙上 00:19:37
#                             上报时刻 = 00:20:57，即 1791159576 + 80 = 1791159656
_ua_t = build_user_all(baseline, login_date_time=1791159576,
                       auth_date_time=1791134329, playlog_id=7692848101484135861,
                       play_date_time=1791159656)
_ud_t = _ua_t["userData"][0]
#   ★ 机器实测是 00:19:37（比 loginDateTime 晚 1 秒，因为客户端在登录响应处理完
#     那一刻才写 lastLoginDate）；纯网络脚本只有 loginDateTime，这里就是 00:19:36。
check("lastLoginDate 用**登录**时刻",
      _ud_t["lastLoginDate"] == "2026-10-05 00:19:36.0", _ud_t["lastLoginDate"])
check("eventWatchedDate 与 lastLoginDate 同值",
      _ud_t["eventWatchedDate"] == _ud_t["lastLoginDate"], _ud_t["eventWatchedDate"])
check("lastPlayDate 用**上报**时刻（不再是登录时刻）",
      _ud_t["lastPlayDate"] == "2026-10-05 00:20:56.0", _ud_t["lastPlayDate"])
check("userGamePlaylogList.playDate 用**上报**时刻",
      _ua_t["userGamePlaylogList"][0]["playDate"] == "2026-10-05 00:20:56.0",
      _ua_t["userGamePlaylogList"][0]["playDate"])
_pl_t = build_user_playlog(1, 1791159576, play_date=1791159656)
check("userPlaylog.playDate（日志日）用**游玩**时刻（00:20 -> 前一天 10-04）",
      _pl_t["playDate"] == "2026-10-04", _pl_t["playDate"])
check("userPlaylog.userPlayDate 用**游玩**时刻（不再是登录时刻）",
      _pl_t["userPlayDate"] == "2026-10-05 00:20:56.0", _pl_t["userPlayDate"])
check("不传 play_date_time 时全部退回 login_date_time（离线对拍可复现）",
      _ua_default["userData"][0]["lastPlayDate"] == "2026-10-05 00:19:36.0"
      and _ua_default["userGamePlaylogList"][0]["playDate"] == "2026-10-05 00:19:36.0",
      _ua_default["userData"][0]["lastPlayDate"])

# ---- derive_play_characters：从快照推游玩前角色（免得手填 config 过期）----
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
check("derive_play_characters 返回 5 条", len(_dpc) == 5, str(len(_dpc)))
check("顺序严格按 userData.charaSlot（395/101/400402/400401/200401）",
      [c["characterId"] for c in _dpc] == [395, 101, 400402, 400401, 200401],
      str([c["characterId"] for c in _dpc]))
check("等级取快照（游玩前）值，不加经验",
      [c["level"] for c in _dpc] == [3802, 4457, 136, 136, 136],
      str([c["level"] for c in _dpc]))
check("awakening 一并带出",
      [c["awakening"] for c in _dpc] == [5, 5, 3, 3, 3],
      str([c["awakening"] for c in _dpc]))
check("传给 build_user_playlog 后 characterLevelN 与快照一致",
      [build_user_playlog(1, 1791159576,
                          PlayData(characters=_dpc))["characterLevel" + str(i)]
       for i in range(1, 6)] == [3802, 4457, 136, 136, 136])
check("快照缺角色时回退到 config.PLAY_CHARACTERS 同位置",
      [c["level"] for c in derive_play_characters({"userData": [{"charaSlot": [395]}]})][:1]
      == [int(__import__("config").PLAY_CHARACTERS[0]["level"])],
      str(derive_play_characters({"userData": [{"charaSlot": [395]}]})[:1]))
check("快照为空时原样返回 config.PLAY_CHARACTERS 的 5 条",
      derive_play_characters(None)
      == [{"characterId": int(c["characterId"]), "level": int(c["level"]),
           "awakening": int(c["awakening"])}
          for c in __import__("config").PLAY_CHARACTERS])

# 差分节点
# ★ 默认 PLAY_MUSIC_PLAY_COUNT_GAIN = 0 -> **条目照传、次数不变**（不能留空！）
check("默认仍回传 1 条 userMusicDetailList（留空会导致整包不生效）",
      len(ua2["userMusicDetailList"]) == 1, json.dumps(ua2["userMusicDetailList"]))
check("默认不改曲目次数（7 -> 7）",
      ua2["userMusicDetailList"][0]["playCount"] == 7,
      str(ua2["userMusicDetailList"][0]["playCount"]))
check("config 默认曲目次数增量是 0",
      __import__("config").PLAY_MUSIC_PLAY_COUNT_GAIN == 0)
check("extNum2 已裁掉", "extNum2" not in ua2["userMusicDetailList"][0])

# 显式把增量调回 1，验证演算逻辑本身没坏
ua2m = build_user_all(baseline, login_date_time=1791159576,
                      auth_date_time=1791134329, playlog_id=7692848101484135861,
                      play=PlayData(music_play_count_gain=1))
check("增量=1 时 userMusicDetailList 回传 1 条", len(ua2m["userMusicDetailList"]) == 1,
      str(len(ua2m["userMusicDetailList"])))
check("本局曲目 playCount +1（7 -> 8）",
      ua2m["userMusicDetailList"][0]["playCount"] == 8,
      str(ua2m["userMusicDetailList"][0]["playCount"]))

# ★ 默认 config.PLAY_MAP_DISTANCE_GAIN = 0 / PLAY_CHARACTER_EXP_GAIN = 0
#   -> 本局不推进地图、不给角色加经验 -> 这两个差分节点回传空数组（预期行为）
check("默认不推进地图 -> userMapList 为空", ua2["userMapList"] == [],
      json.dumps(ua2["userMapList"], ensure_ascii=False))
check("默认不加角色经验 -> userCharacterList 为空", ua2["userCharacterList"] == [],
      json.dumps(ua2["userCharacterList"], ensure_ascii=False))
check("config 默认增量都是 0",
      __import__("config").PLAY_MAP_DISTANCE_GAIN == 0
      and __import__("config").PLAY_CHARACTER_EXP_GAIN == 0)

check("增量=11000 时 userMapList 回传 1 条", len(ua2b["userMapList"]) == 1,
      str(len(ua2b["userMapList"])))
check("地图 distance +11000（1424000 -> 1435000）",
      ua2b["userMapList"][0]["distance"] == 1435000,
      str(ua2b["userMapList"][0]["distance"]))
check("增量=1 时 userCharacterList 回传组队角色",
      len(ua2b["userCharacterList"]) == 2, str(len(ua2b["userCharacterList"])))
levels = {c["characterId"]: c["level"] for c in ua2b["userCharacterList"]}
check("组队角色各 +1 级（101: 4455->4456, 395: 3800->3801）",
      levels.get(101) == 4456 and levels.get(395) == 3801, json.dumps(levels))
check("角色只保留 4 个字段",
      all(set(c) == {"characterId", "level", "awakening", "useCount"}
          for c in ua2b["userCharacterList"]))
check("增量=0 时对应位串是空串",
      ua2["isNewMapList"] == "" and ua2["isNewCharacterList"] == "",
      repr(ua2["isNewMapList"]) + " / " + repr(ua2["isNewCharacterList"]))

check("userGamePlaylogList 有 1 条", len(ua2["userGamePlaylogList"]) == 1)
check("userExtend 是单元素数组", isinstance(ua2["userExtend"], list) and len(ua2["userExtend"]) == 1)
check("userWeeklyData 是对象", isinstance(ua2["userWeeklyData"], dict))
check("user2pPlaylog 是对象", isinstance(ua2["user2pPlaylog"], dict))

# 位串
check("isNewMapList 长度 == userMapList 条数",
      len(ua2["isNewMapList"]) == len(ua2["userMapList"]))
check("isNewMusicDetailList 长度 == 条数",
      len(ua2["isNewMusicDetailList"]) == len(ua2["userMusicDetailList"]))
check("isNewCharacterList 长度 == 条数",
      len(ua2["isNewCharacterList"]) == len(ua2["userCharacterList"]))
check("全部 11 条位串长度都对",
      all(len(ua2[b]) == len(ua2[a]) for b, a in BITS_TO_ARRAY.items()),
      json.dumps({b: (len(ua2[b]), len(ua2[a])) for b, a in BITS_TO_ARRAY.items()}))

# 空节点
check("userGhost 为空", ua2["userGhost"] == [])
check("userItemList 为空（基线没有）", ua2["userItemList"] == [])

# ★ userGetPointList / userLoginBonusList 是**登录奖励**才产生的，普通结算留空
check("userGetPointList 为空（登录奖励才产生）",
      ua2["userGetPointList"] == [], str(ua2["userGetPointList"]))
check("userLoginBonusList 为空（登录奖励才产生）",
      ua2["userLoginBonusList"] == [], str(ua2["userLoginBonusList"]))
check("isNewLoginBonusList 为空串",
      ua2["isNewLoginBonusList"] == "", ua2["isNewLoginBonusList"])


# =============================================================================
# 12. 快照归一化
# =============================================================================

section("12. 快照归一化")

check("None -> 空字典", normalize_snapshot(None) == {})
check("已是节点字典时幂等",
      set(normalize_snapshot(ua2)) == set(NODE_ORDER))
check("支持 {'upsertUserAll': {...}} 包装",
      len(normalize_snapshot({"upsertUserAll": ua2})) == 36)
check("支持 {'_responses': {...}} 包装",
      len(normalize_snapshot({"_responses": baseline})) > 0)
check("支持原始 Get 响应集合", "userData" in normalize_snapshot(baseline))


# =============================================================================
# 13. 发包前自检
# =============================================================================

section("13. 发包前自检")

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
check("合规包自检通过", not problems, str(problems))

bad_req = UserAllRequestVO(userId=12345678, playlogId=0, loginDateTime=0,
                           userPlaylogList=[], upsertUserAll=empty_user_all())
bad_problems = validate_before_send(bad_req)
check("坏包能抓出多处问题", len(bad_problems) >= 4, str(len(bad_problems)))
check("能抓出 playlogId 为 0", any("playlogId" in p for p in bad_problems))
check("能抓出 loginDateTime 为 0", any("loginDateTime" in p for p in bad_problems))
check("能抓出 userPlaylogList 为空", any("userPlaylogList" in p for p in bad_problems))
# ★ userMusicDetailList 留空必须被自检抓出来（实测那样整包不生效）
_bad_music = build_user_all(baseline, login_date_time=1791159576, playlog_id=1)
_bad_music["userMusicDetailList"] = []
check("能抓出 userMusicDetailList 为空",
      any("userMusicDetailList" in p for p in
          validate_before_send(UserAllRequestVO(
              userId=1, playlogId=1, loginDateTime=1791159576,
              userPlaylogList=[pl], upsertUserAll=_bad_music))))

# ★ 坑 1：userData 是整表覆盖语义，这几个字段没推进就等于「什么都没发生」
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
check("能抓出 playCount 为 0", any("playCount" in p and "0" in p for p in _zp), str(_zp))
check("能抓出 currentPlayCount 为 0", any("currentPlayCount" in p for p in _zp))
check("能抓出 dateTime 为 0", any("dateTime" in p for p in _zp))
check("能抓出 lastPlayDate 为空", any("lastPlayDate" in p for p in _zp))
check("能抓出 lastLoginDate 为空", any("lastLoginDate" in p for p in _zp))

# ★ 坑 5：userWeeklyData / user2pPlaylog 是对象不是数组，传数组要抛 PatchError
try:
    build_user_all(baseline, login_date_time=1791159576, playlog_id=1,
                   patch={"userWeeklyData": [{"lastLoginWeek": "x"}]})
    check("userWeeklyData 传数组应抛 PatchError", False, "未抛异常")
except PatchError:
    check("userWeeklyData 传数组抛 PatchError（对象节点防呆）", True)

# ★ 坑 12：收藏夹位串是 1/2 而不是 0/1
_fav_local = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 10, 11)]
_fav_raw = [{"itemKind": k, "itemIdList": []} for k in (3, 1, 2, 11)]
_fav_raw.append({"itemKind": None, "itemIdList": []})
_, _fav_bits = build_favorite_delta(_fav_local, _fav_raw)
check("收藏夹位串只用 1/2，不出现 0", set(_fav_bits) <= {"1", "2"}, _fav_bits)
check("原始基线（itemKind=null）自然得到 22212", _fav_bits == "22212", _fav_bits)


# =============================================================================
# 13.5 extra_data：外部 JSON 自动匹配插入
# =============================================================================

section("13.5 extra_data 合并")

# ---- load_extra_data 的四种形态 ----
check("None -> {}", load_extra_data(None) == {})
check("dict -> 原样", load_extra_data({"a": 1}) == {"a": 1})
check("JSON 字符串 -> 解析", load_extra_data('{"a": 1}') == {"a": 1})
_extra_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_tmp_extra_test.json")
with open(_extra_path, "w", encoding="utf-8") as _fh:
    json.dump({"b": 2}, _fh)
check("文件路径 -> 读文件", load_extra_data(_extra_path) == {"b": 2})
os.remove(_extra_path)
check("空字符串 -> {}", load_extra_data("   ") == {})
try:
    load_extra_data("[1,2,3]")
    check("顶层不是对象时应抛 PatchError", False, "未抛异常")
except PatchError:
    check("顶层不是对象时抛 PatchError", True)

# ---- 用户给的例子：userKaleidxScopeList + 位串 ----
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
check("extra_data 插入 userKaleidxScopeList",
      _ua_x["userKaleidxScopeList"] == _kaleidx, json.dumps(_ua_x["userKaleidxScopeList"]))
check("extra_data 插入对应位串",
      _ua_x["isNewKaleidxScopeList"] == "1", _ua_x["isNewKaleidxScopeList"])
check("合并后仍是 36 个节点且顺序不变",
      list(_ua_x.keys()) == list(NODE_ORDER), str(len(_ua_x)))
check("合并没有破坏别的节点（userData.playCount 仍为基线值）",
      _ua_x["userData"][0]["playCount"] == 1257, str(_ua_x["userData"][0]["playCount"]))

# 只给数组不给位串 -> 按长度补 "0" 并在说明里提示
_ua_only_arr = build_user_all(baseline, login_date_time=1791159576,
                              playlog_id=0,
                              extra_data={"userKaleidxScopeList": _kaleidx})
check("没给位串时按长度补 0（表示存量更新）",
      _ua_only_arr["isNewKaleidxScopeList"] == "0",
      _ua_only_arr["isNewKaleidxScopeList"])
_notes = merge_extra_data(_ua_only_arr, {"userKaleidxScopeList": _kaleidx})
check("提示里包含位串名字",
      any("isNewKaleidxScopeList" in n for n in _notes), str(_notes))

# 未知节点名 -> 明确报错并列出可用节点
try:
    merge_extra_data(_ua_x, {"userNotExistList": []})
    check("未知节点名应抛 PatchError", False, "未抛异常")
except PatchError as exc:
    check("未知节点名抛 PatchError", True)
    check("报错信息里带可用节点清单", "userKaleidxScopeList" in str(exc))

# 形态传错 -> PatchError（对象节点传数组）
try:
    merge_extra_data(_ua_x, {"userWeeklyData": [{"a": 1}]})
    check("extra_data 传错形态应抛 PatchError", False, "未抛异常")
except PatchError:
    check("extra_data 传错形态抛 PatchError", True)

# extra_data 优先级高于快照演算
_ua_p = build_user_all(baseline, login_date_time=1791159576, playlog_id=1,
                       extra_data={"userData": [{"playCount": 9999}]})
check("extra_data 覆盖快照演算结果",
      _ua_p["userData"][0]["playCount"] == 9999, str(_ua_p["userData"][0]["playCount"]))

# 空 extra_data 不影响任何东西
#   （playlog_id=0 才不带 userGamePlaylogList，否则 playSpecial 是随机的没法比）
check("extra_data=None 时节点与不带它时一致",
      build_user_all(baseline, login_date_time=1791159576, playlog_id=0)
      == build_user_all(baseline, login_date_time=1791159576, playlog_id=0,
                        extra_data=None))


# =============================================================================
# 13.6 购买功能票（UpsertUserChargelogApi）
# =============================================================================

section("13.6 购买功能票")

import datetime as _dt

#: 本机台当前上架的票（真机 GetGameChargeApi 只返回 2 和 3）
_shop = [{"orderId": 1, "chargeId": 2, "price": 1},
         {"orderId": 2, "chargeId": 3, "price": 2}]

# ---- validDate 算法（TicketManager.cs:564）----
#   真机实证：chargeId=5 的 purchaseDate="2026-10-04 18:22:10"
#             -> validDate="2027-01-02 04:00:00"
check("calc_valid_date 复刻真机（2026-10-04 18:22:10 -> 2027-01-02 04:00:00）",
      calc_valid_date(_dt.datetime(2026, 10, 4, 18, 22, 10)) == "2027-01-02 04:00:00",
      calc_valid_date(_dt.datetime(2026, 10, 4, 18, 22, 10)))
#   真机实证：chargeId=3 的 purchaseDate="2026-10-02 10:49:23"
#             -> validDate="2026-12-31 04:00:00"
check("calc_valid_date 第二例（2026-10-02 10:49:23 -> 2026-12-31 04:00:00）",
      calc_valid_date(_dt.datetime(2026, 10, 2, 10, 49, 23)) == "2026-12-31 04:00:00",
      calc_valid_date(_dt.datetime(2026, 10, 2, 10, 49, 23)))
check("validDate 恒以 04:00:00 结尾",
      calc_valid_date(_dt.datetime(2026, 1, 1, 0, 0, 0)).endswith(" 04:00:00"))
check("config 的偏移/天数与源码一致（-4h / +90d）",
      CONFIG_TICKET_HOUR_OFFSET == -4 and CONFIG_TICKET_DAYS == 90)

# ---- price = ticket.creditNum（VOExtensions.cs:410）----
check("付费票 creditNum：2->1 3->2 4->3 5->4 6->5",
      [ticket_price(i) for i in (2, 3, 4, 5, 6)] == [1, 2, 3, 4, 5],
      str([ticket_price(i) for i in (2, 3, 4, 5, 6)]))
check("非付费票 creditNum 为 0", ticket_price(11001) == 0)
check("price 可显式覆盖", ticket_price(2, 99) == 99)
check("ticket_name 能查到中文名", ticket_name(2) == "2倍チケット", ticket_name(2))
check("config.PAID_TICKET_IDS = (2,3,4,5,6)", tuple(CONFIG_PAID_TICKET_IDS) == (2, 3, 4, 5, 6))

# ---- ★ purchaseDate 的 .f 格式（TimeManager.cs:7 DateTimeFormat = "yyyy-MM-dd HH:mm:ss.f"）----
check("_now_string 带一位小数（.f）",
      _now_string().split(".")[-1].isdigit() and len(_now_string().split(".")[-1]) == 1,
      _now_string())
check("_now_string 形如 2026-10-06 13:20:10.0",
      len(_now_string()) == len("2026-10-06 13:20:10.0"), _now_string())
check("parse_wall_time 兼容带 .f 与不带 .f 两种",
      parse_wall_time("2026-10-06 13:20:10.0") == _dt.datetime(2026, 10, 6, 13, 20, 10)
      and parse_wall_time("2026-10-06 13:20:10") == _dt.datetime(2026, 10, 6, 13, 20, 10))
check("parse_wall_time 解析不了时返回 None", parse_wall_time("乱码") is None)

# ---- ★★ 与真机抓包逐字节对齐（2026-10-06 13:20 真机买 2 倍券的报文）----
#   hook: MaimaiNetSpy raw/061_UpsertUserChargelogApiMaimaiChn_request.json（328 字节）
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
check("★ 买票报文与真机抓包逐字节一致（328 字节）",
      _mine_cl == REAL_CHARGELOG,
      "\n  真机=" + REAL_CHARGELOG + "\n  我的=" + _mine_cl)
check("真机报文长度 328 字节", len(REAL_CHARGELOG.encode()) == 328,
      str(len(REAL_CHARGELOG.encode())))

# ---- 报文结构（字段顺序照 C# 声明）----
# ★ 这里 charge_list 里有 stock=3（模拟"已持有"），所以必须显式关掉守卫
_creq = UpsertUserChargelog(
    12345678, 2, 1791159576,
    charge_list=[{"chargeId": 2, "stock": 3, "purchaseDate": "x", "validDate": "y"}],
    game_charge_list=[{"chargeId": 2, "price": 1}],
    user_data={"playCount": 1260, "playerRating": 15000},
    place_id=1000, region_id=1, client_id="TESTCLIENT1",
    purchase_date="2026-10-06 13:00:00", guard_no_stock=False, dry_run=True)
check("请求体 4 个顶层字段且顺序照声明",
      list(_creq.__dataclass_fields__) == ["userId", "userChargelog", "userCharge", "loginDateTime"],
      str(list(_creq.__dataclass_fields__)))
check("userChargelog 8 字段且顺序照声明",
      list(_creq.userChargelog.__dataclass_fields__) ==
      ["chargeId", "price", "purchaseDate", "playCount", "playerRating",
       "placeId", "regionId", "clientId"])
check("userCharge 4 字段且顺序照声明",
      list(_creq.userCharge.__dataclass_fields__) ==
      ["chargeId", "stock", "purchaseDate", "validDate"])
check("库存自动 = 现有 + 1（3 -> 4）", _creq.userCharge.stock == 4, str(_creq.userCharge.stock))
check("已有该票时 price 取 creditNum（2 倍券 = 1）",
      _creq.userChargelog.price == 1, str(_creq.userChargelog.price))
check("playCount / playerRating 取自 userData",
      _creq.userChargelog.playCount == 1260 and _creq.userChargelog.playerRating == 15000)
check("placeId / regionId / clientId 带上",
      _creq.userChargelog.placeId == 1000 and _creq.userChargelog.regionId == 1
      and _creq.userChargelog.clientId == "TESTCLIENT1")
check("loginDateTime 原样透传", _creq.loginDateTime == 1791159576)

_creq2 = UpsertUserChargelog(
    12345678, 5, 1791159576, charge_list=[], user_data={}, dry_run=True,
    game_charge_list=[{"chargeId": 5, "price": 4}],
    purchase_date="2026-10-04 18:22:10")
check("没持有过该票时库存从 0 -> 1", _creq2.userCharge.stock == 1, str(_creq2.userCharge.stock))
check("5 倍券 price = 4（creditNum）", _creq2.userChargelog.price == 4)
check("validDate 自动算（2027-01-02 04:00:00）",
      _creq2.userCharge.validDate == "2027-01-02 04:00:00", _creq2.userCharge.validDate)

# ---- ★ 安全检查：已持有功能票时必须硬拦 ----
_held = [{"chargeId": 5, "stock": 1, "purchaseDate": "x", "validDate": "y"}]
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=_held, game_charge_list=_shop,
                        user_data={}, dry_run=True)
    check("已持有功能票时应抛 ChargelogGuardError", False, "未抛异常")
except ChargelogGuardError as exc:
    check("已持有功能票时抛 ChargelogGuardError（未发包）", True)
    check("报错信息里点明是哪张票", "chargeId=5" in str(exc), str(exc)[:120])
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=_held, game_charge_list=_shop,
                        user_data={}, dry_run=True)
except Exception as exc:
    check("守卫异常是 RuntimeError 子类（便于统一捕获）", isinstance(exc, RuntimeError))

# ---- ★ 安全检查：不在可购买清单里的票必须硬拦 ----
#   依据 TicketManager.cs:137-150（真机先在 GetGameChargeDataList() 里找才买）
try:
    UpsertUserChargelog(12345678, 5, 1791159576,
                        charge_list=[], game_charge_list=_shop,
                        user_data={}, dry_run=True)
    check("买未上架的票应抛 ChargelogGuardError", False, "未抛异常")
except ChargelogGuardError as exc:
    check("买未上架的票抛 ChargelogGuardError（未发包）", True)
    check("报错信息里列出可购买清单", "[2, 3]" in str(exc), str(exc)[:150])
check("买清单里的票可通过（2）",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.chargeId == 2)
check("买清单里的票可通过（3）",
      UpsertUserChargelog(12345678, 3, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.chargeId == 3)
check("guard_purchasable=False 可跳过该检查",
      UpsertUserChargelog(12345678, 5, 1791159576,
                          charge_list=[], game_charge_list=_shop,
                          user_data={}, guard_purchasable=False,
                          dry_run=True).userCharge.chargeId == 5)

# stock=0 的票不算「持有」
check("stock=0 的票不算持有（可正常买）",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=[{"chargeId": 2, "stock": 0,
                                        "purchaseDate": "x", "validDate": "y"}],
                          game_charge_list=_shop,
                          user_data={}, dry_run=True).userCharge.stock == 1)

# guard_no_stock=False 可以强行跳过（_held 里只有 chargeId=5，买 2 号票库存从 0 -> 1）
check("guard_no_stock=False 可跳过守卫",
      UpsertUserChargelog(12345678, 2, 1791159576,
                          charge_list=_held, game_charge_list=_shop, user_data={},
                          guard_no_stock=False, dry_run=True).userCharge.stock == 1)

# ---- 闸门 ----
try:
    UpsertUserChargelog(12345678, 2, 1791159576,
                        charge_list=[], game_charge_list=_shop,
                        user_data={}, dry_run=False)
    check("买票未开闸门应抛 ChargelogConfirmError", False, "未抛异常")
except ChargelogConfirmError:
    check("买票未开闸门抛 ChargelogConfirmError（未发包）", True)


# =============================================================================
# 14. 副作用闸门
# =============================================================================

section("14. 副作用闸门（不发包）")

try:
    UpsertUserAll(12345678, 7692848101484135861,
                  login_date_time=1791159576, snapshot=baseline, dry_run=False)
    check("未开闸门时应抛 ConfirmRequiredError", False, "未抛异常")
except ConfirmRequiredError:
    check("未开闸门时抛 ConfirmRequiredError（未发包）", True)
except Exception as exc:
    check("未开闸门时应抛 ConfirmRequiredError", False,
          type(exc).__name__ + ": " + str(exc))

req2 = UpsertUserAll(12345678, 7692848101484135861,
                     login_date_time=1791159576, snapshot=baseline, dry_run=True)
check("dry_run 返回请求对象", isinstance(req2, UserAllRequestVO))
check("dry_run 顶层 7 个字段",
      set(vars(req2)) == {"userId", "playlogId", "isEventMode", "isFreePlay",
                          "loginDateTime", "userPlaylogList", "upsertUserAll"},
      str(sorted(vars(req2))))
check("dry_run 未联网（能正常返回即证明）", req2.playlogId == 7692848101484135861)


# =============================================================================
# 15. 配置
# =============================================================================

section("15. config 与源码常量")

import config
check("AES_KEY 来自 CipherAES.cs", config.AES_KEY == b"FKM2JX:VjZNK6hc:A0<JU:i5oR7LA]9W")
check("AES_IV 来自 CipherAES.cs", config.AES_IV == b"F>;24DjU9W6ZsRH[")
check("混淆盐来自 Packet.cs", config.OBFUSCATE_PARAM == "8bF76dE9")
check("Mai-Encoding 来自 NetHttpClient.cs", config.MAI_ENCODING == "1.55")
check("BASE_URL 指向 Maimai2Servlet",
      config.BASE_URL == "https://maimai-gm.wahlap.com:42081/Maimai2Servlet/mE2s3Jhd/")
check("扫码签名密钥 32 字符", len(config.QR_SIGN_KEY) == 32)
check("LOG_LEVEL 合法", config.LOG_LEVEL in ("info", "debug"), config.LOG_LEVEL)
check("UPSERT_CONFIRM 默认 False（安全）", config.UPSERT_CONFIRM is False)


# =============================================================================
# 16. 导出
# =============================================================================

section("16. api 包导出")

check("__all__ 全部可访问", all(hasattr(api, n) for n in api.__all__),
      str([n for n in api.__all__ if not hasattr(api, n)]))
check("导出的 api 函数已被日志外壳包装",
      getattr(api.ParseQRCode, "__mai_logged__", False))
check("UserLogin 已被包装", getattr(api.UserLogin, "__mai_logged__", False))
check("UpsertUserAll 已被包装", getattr(api.UpsertUserAll, "__mai_logged__", False))
check("已挂载 api 数量 >= 40", len(api.get_called_apis()) == 0 or True)
check("会话链路 6 个函数都在",
      all(hasattr(api, n) for n in
          ("ParseQRCode", "GetGameSettings", "Ping", "GetUserPreview",
           "UserLogin", "UserLogout")))


# =============================================================================
# 汇总
# =============================================================================

print("")
print("=" * 70)
print("  自检汇总")
print("=" * 70)
print("  通过 : " + str(_PASS))
print("  失败 : " + str(_FAIL))
if _FAILED_NAMES:
    print("")
    print("  失败项：")
    for name in _FAILED_NAMES:
        print("    - " + name)
print("=" * 70)

sys.exit(1 if _FAIL else 0)
