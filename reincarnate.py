#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reincarnate.py —— 账号数据迁移（转生）：把账号 A 的数据克隆到账号 B
================================================================================

    ┌─ 源账号 A ─────────────────────────────────────────────┐
    │  二维码 -> ParseQRCode -> UserLogin -> GetNeedUserData  │
    │  或：直接读 data/<userId>.json（离线复用）              │
    └────────────────────────────────────────────────────────┘
                            ↓  节点数据
    ┌─ 目标账号 B ───────────────────────────────────────────┐
    │  二维码 -> ParseQRCode -> UserPreview -> UserLogin      │
    │  循环：                                                  │
    │      等待 -> UpsertUserAll（一包曲目）                  │
    │      -> UserLogout(type=1)                              │
    │      -> UserLogin(isContinue=true) 续关，拿新 loginId   │
    │  收尾：最后一包登出后结束（不再续关）                    │
    └────────────────────────────────────────────────────────┘

--------------------------------------------------------------------------------
★ 每包几首：1 / 3 / 4 可以，**恰好 2 首会被服务端拒绝**
--------------------------------------------------------------------------------
    真机一局（一个 credit）最多打 4 首，所以一条 UpsertUserAll 报文里的
    userPlaylogList / userGamePlaylogList **最多 4 条**。

    ★ 但实测：**每包恰好 2 首会被服务端拒绝**（1 / 3 / 4 首都正常）。
      所以本脚本的分批器会**主动避开 2 首包**：

          10 首 -> [4, 4, 2] -> [4, 3, 3]
           6 首 -> [4, 2]    -> [3, 3]
           2 首 -> [2]       -> [1, 1]

    ★ 每包都必须带**非空**的 userPlaylogList —— 踩坑清单第 2 条实测：
      留空会被服务端当成无效包**静默丢弃**（returnCode=1 但不落库）。

--------------------------------------------------------------------------------
★ 为什么需要「续关登录」
--------------------------------------------------------------------------------
    UpsertUserAll 的 playlogId 必须等于**本次登录**的 loginId
    （PacketUpsertUserAll.cs:31 / UserAllRequestVO）。
    一局结束后这个会话就被消费掉了，要继续上传必须重新登录 ——
    真机走的就是「续关」：

        Process/ContinueProcess.cs:403
            new PacketUserLogin(userID, accessCode, isContinue: true, ...)

    对应本工程：UserLogin(user_id, token, is_continue=True)
    它和普通登录的唯一区别就是 UserLoginRequestVO.isContinue = true，
    会返回**新的 loginId / loginDateTime**，供下一局 UpsertUserAll 使用。

    ★ 登出必须用 **type=1（LogoutType.Logout）**。
      真机抓包实证 UserLogoutApi 就是 type=1（带 delayLog）：
          {"userId":...,"type":1,"delayLog":{...}}
      续关场景下用 4（TestIn）会出问题 —— 那是「测试登入 / 顶号」的语义。

--------------------------------------------------------------------------------
★ playlog 从哪来
--------------------------------------------------------------------------------
    GetNeedUserData 抓不到 userPlaylogList（那是逐局记录，没有对应的 Get 接口），
    所以本脚本**从曲目记录反推合成**：

        UserMusicDetail（9 字段）          ->  UserPlaylog（110 字段）
        ─────────────────────────────         ─────────────────────────
        musicId                                musicId
        level                                  level
        achievement                            achievement
        deluxscoreMax                          deluxscore
        scoreRank                              scoreRank / isClear
        comboStatus                            comboStatus
        syncStatus                             syncStatus
        其余字段                              取自 config.PLAY_*（合理默认值）

--------------------------------------------------------------------------------
用法
--------------------------------------------------------------------------------
    # 源数据来自二维码（会联网抓 A 的数据，并落盘到 data/<A>.json）
    python reincarnate.py --dst-qr <B的二维码> --src-qr <A的二维码>

    # 源数据来自已保存的 JSON（离线，推荐：不用反复消耗 A 的二维码）
    python reincarnate.py --dst-qr <B的二维码> --src-json data/12345678.json

    # ★ 真实上传
    python reincarnate.py --dst-qr <B的二维码> --src-json data/12345678.json --send

    # 只看计划，不发包
    python reincarnate.py --dst-qr <B的二维码> --src-json data/12345678.json --plan

    # 常用开关
    --limit N          只迁前 N 首（试跑用）
    --per-packet N     每包曲目数，只能是 1/3/4（默认 4；★ 2 首会被服务端拒绝）
    --wait N           每次上传前的等待秒数（默认 5.0，0 = 不等）
    --clone-identity   连 userName / accessCode 一起克隆（默认**保留 B 自己的**）
    --no-continue      不续关（只发一包，调试用）

★ 迁移会**真实写入**账号 B（不可撤销）。不传 --send 时只构造报文。
★ 二维码**有效期 10 分钟**。
"""

from __future__ import annotations

import json
import sys
import time

from api import (
    setup_logging,
    teardown_logging,
    log_error,
    log_info,
    log_warning,
    ParseQRCode,
    GetUserPreview,
    UserLogin,
    UserLogout,
    LogoutType,
    GetNeedUserData,
    normalize_snapshot,
    NODE_ORDER,
    NODE_TYPES,
    ARRAY_TO_BITS,
    DIFF_PRIMARY_KEYS,
    PlayData,
    build_user_playlog,
    build_user_game_playlog,
    UpsertUserAll,
    ConfirmRequiredError,
    Ping,
    load_user_data,
    list_saved_user_ids,
    DATA_DIR,
)
from config import PLACE_ID, REGION_ID

#: 真机一局最多 4 首
MAX_TRACKS_PER_CREDIT = 4

#: ★ 被服务端禁止的每包曲目数（实测：**恰好 2 首会被拒**）
#:   1 / 3 / 4 首都正常，只有 2 首不行 —— 所以分批时要避开它。
FORBIDDEN_TRACK_COUNTS = (2,)

#: 允许的 --per-packet 取值
ALLOWED_PER_PACKET = (1, 3, 4)


def split_batches(total, per):
    """
    把 total 首切成「每包 <= per」的批次，**并且不产生被禁止的 2 首包**。

    做法：先贪心按 per 切，再修正大小为 2 的批次：

        ① 前一批 >= 4 -> 从它借 1 首过来（前一批变 >=3，本批变 3）
        ② 借不到（前一批只有 3，或自己就是第一批）-> 把这个 2 拆成 1 + 1

    ★ 只借位是不够的 —— 前一批是 3 时借完自己变 2，等于把 2 挪了个位置。

    例：
        10 首 per=4 -> [4, 4, 2]    -> [4, 3, 3]
         6 首 per=4 -> [4, 2]       -> [3, 3]
         2 首 per=4 -> [2]          -> [1, 1]
         5 首 per=3 -> [3, 2]       -> [3, 1, 1]
         8 首 per=3 -> [3, 3, 2]    -> [3, 3, 1, 1]
         5 首 per=4 -> [4, 1]       （本来就合法，不动）
    """
    if total <= 0:
        return []
    per = max(1, int(per))
    out = []
    left = total
    while left > 0:
        n = min(per, left)
        out.append(n)
        left -= n

    i = 0
    while i < len(out):
        if out[i] not in FORBIDDEN_TRACK_COUNTS:
            i += 1
            continue
        # ① 前一批 >= 4 才能借（借完前一批 >= 3，本批 = 3）
        if i > 0 and out[i - 1] >= 4:
            out[i - 1] -= 1
            out[i] += 1
            i += 1
            continue
        # ② 借不到 -> 把这个 2 拆成 1 + 1
        out[i] = 1
        out.insert(i + 1, 1)
        i += 2
    return out

#: 默认保留目标账号自己的身份字段（不克隆过去，避免把 B 改名）
IDENTITY_KEYS = ("userName", "accessCode")

#: 迁移时**不**逐条传的节点（要么是位串、要么由 UpsertUserAll 自己算）
SKIP_NODES = (
    "userMusicDetailList",     # 单独分批
    "userGamePlaylogList",     # 由本脚本按曲目合成
    "user2pPlaylog",           # 2P 记录，迁移无意义
    "userGetPointList",        # 里程/奖励，迁移会凭空发点
    "userTradeItemList",       # 无 Get 来源
    "userFriendSeasonRankingList",   # 无 Get 来源
)


def parse_args(argv):
    opts = {"dst_qr": "", "src_qr": "", "src_json": "", "send": False,
            "plan": False, "debug": False, "limit": 0,
            "per_packet": MAX_TRACKS_PER_CREDIT,
            "clone_identity": False, "no_continue": False,
            "wait": 5.0}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--send":
            opts["send"] = True
        elif a == "--plan":
            opts["plan"] = True
        elif a == "--debug":
            opts["debug"] = True
        elif a == "--clone-identity":
            opts["clone_identity"] = True
        elif a == "--no-continue":
            opts["no_continue"] = True
        elif a in ("--dst-qr", "--src-qr", "--src-json", "--limit",
                    "--per-packet", "--wait") and i + 1 < len(argv):
            key = a[2:].replace("-", "_")
            opts[key] = (float(argv[i + 1]) if key == "wait"
                         else int(argv[i + 1]) if key in ("limit", "per_packet")
                         else argv[i + 1])
            i += 1
        i += 1
    return opts


# =============================================================================
# 工具
# =============================================================================

def _bits_for(node, items, base_items):
    """
    按目标账号 B 的基线算 isNew* 位串：
        B 里没有该条目 -> "1"（新增）
        B 里已有       -> "0"（更新）
    主键表见 upsert_user_all.DIFF_PRIMARY_KEYS。
    """
    keys = DIFF_PRIMARY_KEYS.get(node)
    if not keys:
        return None
    have = set()
    for b in (base_items or []):
        if isinstance(b, dict):
            have.add(tuple(str(b.get(k)) for k in keys))
    return "".join(
        "0" if tuple(str(it.get(k)) for k in keys) in have else "1"
        for it in (items or []) if isinstance(it, dict)
    )


def play_from_detail(detail, base_play=None):
    """
    从一条 UserMusicDetail（9 字段）反推一份 PlayData，用来合成 userPlaylog。

    对不上的字段保留 config.PLAY_* 的默认值（它们不在曲目记录里）。
    """
    p = PlayData() if base_play is None else base_play
    p.music_id = int(detail.get("musicId", p.music_id) or 0)
    p.music_level = int(detail.get("level", p.music_level) or 0)
    p.achievement = int(detail.get("achievement", p.achievement) or 0)
    p.deluxscore = int(detail.get("deluxscoreMax", p.deluxscore) or 0)
    rank = int(detail.get("scoreRank", 0) or 0)
    p.score_rank = rank
    p.is_clear = rank > 0
    p.combo_status = int(detail.get("comboStatus", p.combo_status) or 0)
    p.sync_status = int(detail.get("syncStatus", p.sync_status) or 0)
    return p


def collect_nodes(src_nodes, base_nodes, clone_identity):
    """把源账号 A 的节点整理成 extra_data（曲目/2P/奖励类除外）。"""
    out = {}
    for node in NODE_ORDER:
        if node in SKIP_NODES:
            continue
        if node.startswith("isNew"):
            continue          # 位串单独算
        kind = NODE_TYPES.get(node)
        if kind not in ("singleton", "array", "object"):
            continue
        val = src_nodes.get(node)
        if val in (None, [], {}):
            continue
        out[node] = json.loads(json.dumps(val))     # 深拷贝
    # 身份字段：默认保留 B 自己的
    if not clone_identity and out.get("userData"):
        for item in out["userData"]:
            if isinstance(item, dict):
                for k in IDENTITY_KEYS:
                    item.pop(k, None)
    # 位串：按 B 的基线算
    for arr, bits in ARRAY_TO_BITS.items():
        if arr not in out:
            continue
        b = _bits_for(arr, out[arr], base_nodes.get(arr))
        if b:
            out[bits] = b
    return out


# =============================================================================
# 主流程
# =============================================================================

def fetch_source_by_qr(qr):
    """用源账号 A 的二维码联网抓一份数据（并自动落盘到 data/<A>.json）。"""
    log_info("=== 源账号：联网抓取 ===")
    uid, token = ParseQRCode(qr)
    preview = GetUserPreview(uid, token)
    if preview.isLogin:
        raise RuntimeError("源账号处于已登录状态，请先在机台登出")
    login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
    try:
        raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
    finally:
        try:
            UserLogout(uid, token, login.loginDateTime, logout_type=LogoutType.TestIn,
                       region_id=REGION_ID, place_id=PLACE_ID)
        except Exception as exc:
            log_warning("源账号登出失败：" + str(exc))
    return raw


def main() -> int:
    opts = parse_args(sys.argv[1:])
    if not opts["dst_qr"] or not (opts["src_qr"] or opts["src_json"]):
        print(__doc__)
        return 1

    if opts["debug"]:
        import config as _cfg
        _cfg.LOG_LEVEL = "debug"

    if opts["per_packet"] not in ALLOWED_PER_PACKET:
        print("--per-packet 只能是 " + str(list(ALLOWED_PER_PACKET))
              + " 之一（真机一局最多 4 首；★ 实测恰好 2 首会被服务端拒绝）")
        return 1

    setup_logging("reincarnate")
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---------------- 1. 源数据 ----------------
        if opts["src_json"]:
            src_raw = json.load(open(opts["src_json"], "r", encoding="utf-8"))
            log_info("=== 源账号：从文件读取 " + opts["src_json"] + " ===")
        else:
            src_raw = fetch_source_by_qr(opts["src_qr"])

        src_nodes = normalize_snapshot(src_raw)
        musics = src_nodes.get("userMusicDetailList") or []
        if opts["limit"] > 0:
            musics = musics[:opts["limit"]]
        log_info("源数据：节点 " + str(len(src_nodes)) + " 个，曲目记录 " + str(len(musics)) + " 条")

        if not musics:
            log_error("源数据里没有 userMusicDetailList，没什么可迁的。")
            return 4

        # ---------------- 2. 目标账号 ----------------
        Ping()
        uid, token = ParseQRCode(opts["dst_qr"])
        session.update(user_id=uid, token=token)
        preview = GetUserPreview(uid, token)
        if preview.isLogin:
            log_error("目标账号处于已登录状态，请先在机台登出或等待会话超时")
            return 2
        login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        base_raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
        base_nodes = normalize_snapshot(base_raw)
        log_info("目标账号基线已抓取")

        # ---------------- 3. 分批 ----------------
        per = int(opts["per_packet"])
        sizes = split_batches(len(musics), per)
        batches = []
        _pos = 0
        for _n in sizes:
            batches.append(musics[_pos:_pos + _n])
            _pos += _n
        log_info("计划：共 " + str(len(musics)) + " 首 -> " + str(len(batches))
                 + " 包，每包 " + "/".join(str(n) for n in sizes[:12])
                 + ("..." if len(sizes) > 12 else "") + " 首")
        log_info("  ★ 已避开 2 首包（实测恰好 2 首会被服务端拒绝；1/3/4 首都正常）")

        if opts["plan"]:
            for i, b in enumerate(batches):
                log_info("    第 " + str(i + 1) + " 包（" + str(len(b)) + " 首）：" + ", ".join(
                    str(x.get("musicId")) + "/L" + str(x.get("level")) for x in b))
            log_info("--plan：只列计划，不发包")
            return 0

        # 第一包才带非曲目节点（整账号克隆）
        shared_nodes = collect_nodes(src_nodes, base_nodes, opts["clone_identity"])
        log_info("非曲目节点 " + str(len([k for k in shared_nodes if not k.startswith('isNew')]))
                 + " 个将在第 1 包上传")

        # ---------------- 4. 逐包上传 ----------------
        # ★ 流程（按使用方口径）：
        #     登录 -> 等待 -> 上传 -> 登出(type=1) -> 续关登录 -> 等待 -> 上传 -> 登出 -> ...
        #
        # ★ 登出必须用 type=1（LogoutType.Logout）。
        #   真机抓包实证 UserLogoutApi 就是 type=1（带 delayLog）；
        #   续关场景下用 4（TestIn）会出问题 —— 那是「测试登入/顶号」的语义。
        sent = 0
        for idx, batch in enumerate(batches):
            log_info("")
            log_info("========== 第 " + str(idx + 1) + "/" + str(len(batches))
                     + " 包（" + str(len(batch)) + " 首）==========")

            # ---- 等待 ----
            if opts["wait"] > 0:
                log_info("上传前等待 " + str(opts["wait"]) + " 秒 ...")
                time.sleep(opts["wait"])

            nodes = {}
            if idx == 0:
                nodes.update(json.loads(json.dumps(shared_nodes)))
            nodes["userMusicDetailList"] = json.loads(json.dumps(batch))
            b = _bits_for("userMusicDetailList", batch,
                          base_nodes.get("userMusicDetailList"))
            if b:
                nodes["isNewMusicDetailList"] = b
                log_info("    isNewMusicDetailList = " + b)

            # 合成 playlog（每首一条）与 game playlog
            playlogs = []
            game_playlogs = []
            for d in batch:
                p = play_from_detail(d)
                playlogs.append(build_user_playlog(
                    login.loginId, login.loginDateTime, p, place_id=PLACE_ID))
                game_playlogs.append(build_user_game_playlog(
                    login.loginId, login.loginDateTime, p))
            nodes["userGamePlaylogList"] = game_playlogs

            UpsertUserAll(
                uid, login.loginId,
                login_date_time=login.loginDateTime,
                auth_date_time=login.dateTime,
                token=token,
                snapshot=base_raw,
                auto_characters=False,
                play=play_from_detail(batch[0]),
                extra_data=nodes,
                user_playlog_list=playlogs,
                pre_new_item_list=False,
                verify_landing=False,
                dry_run=not opts["send"],
                confirm=opts["send"],
                place_id=PLACE_ID, region_id=REGION_ID,
            )
            sent += 1

            # ---- ★ 登出（type=1 Logout）----
            log_info("--- 登出（type=1 Logout）---")
            try:
                UserLogout(uid, token, login.loginDateTime,
                           logout_type=LogoutType.Logout,
                           region_id=REGION_ID, place_id=PLACE_ID)
            except Exception as exc:
                log_warning("登出失败（继续下一包）：" + str(exc))
            session["logged_in"] = False

            # ---- ★ 续关登录：拿下一包的 loginId ----
            if idx < len(batches) - 1:
                if opts["no_continue"]:
                    log_warning("--no-continue：不再续关，提前结束（只发了 1 包）")
                    break
                log_info("--- 续关登录（isContinue=true）---")
                login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID,
                                  is_continue=True)
                session.update(login_dt=login.loginDateTime, logged_in=True)

        if not opts["send"]:
            log_info("")
            log_info("[dry-run] 未发包。想真实迁移请加 --send（★ 会写入账号 B）")
            return 0

        log_info("")
        log_info("★ 迁移完成：共上传 " + str(sent) + " 包 / "
                 + str(min(len(musics), sent * per)) + " 首")
        return 0

    except ConfirmRequiredError:
        return 5
    except Exception as exc:
        log_error(type(exc).__name__ + ": " + str(exc))
        return 1
    finally:
        if session["logged_in"]:
            try:
                UserLogout(session["user_id"], session["token"], session["login_dt"],
                           logout_type=LogoutType.TestIn,
                           region_id=REGION_ID, place_id=PLACE_ID)
            except Exception as exc:
                log_error("[收尾] 强制登出失败（会话可能需等待服务端超时）：" + str(exc))
        teardown_logging()


if __name__ == "__main__":
    sys.exit(main())
