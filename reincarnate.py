#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reincarnate.py —— textdatatext（text）：puttext A ofdatatexttotext B
================================================================================

    ┌─ text A ─────────────────────────────────────────────┐
    │  QR Code -> ParseQRCode -> UserLogin -> GetNeedUserData  │
    │  or：directlyread data/<userId>.json（textMultiplexing）              │
    └────────────────────────────────────────────────────────┘
                            ↓  nodesdata
    ┌─ text B ───────────────────────────────────────────┐
    │  QR Code -> ParseQRCode -> UserPreview -> UserLogin      │
    │  Loop：                                                  │
    │      wait -> UpsertUserAll（Pack of tracks）                  │
    │      -> UserLogout(type=1)                              │
    │      -> UserLogin(isContinue=true) continueOff，text loginId   │
    │  receiveTail：End after last packet logged out（No more renewals）                    │
    └────────────────────────────────────────────────────────┘

--------------------------------------------------------------------------------
★ eachPackagetextfirst：1 / 3 / 4 Yes，**Just in time 2 firstwill be rejected by the server**
--------------------------------------------------------------------------------
    real machineOnegame（One credit）Up to dozens 4 first，So one UpsertUserAll packetinof
    userPlaylogList / userGamePlaylogList **Max. 4 item**。

    ★ But measured：**eachPackageJust in time 2 firstwill be rejected by the server**（1 / 3 / 4 firstallcurrenttext）。
      So the batch batcher of the script will**Proactively avoid 2 firstPackage**：

          10 first -> [4, 4, 2] -> [4, 3, 3]
           6 first -> [4, 2]    -> [3, 3]
           2 first -> [2]       -> [1, 1]

    ★ eachPackageallRequiredBelt**non-empty**of userPlaylogList —— textPittextnumber 2 itemMeasured：
      leave blankMeetingstextserverWhentextnotextPackage**text**（returnCode=1 But not out of stock.）。

--------------------------------------------------------------------------------
★ Why is it needed「continueOfflogin」
--------------------------------------------------------------------------------
    UpsertUserAll of playlogId Must be equal to**textlogin**of loginId
    （PacketUpsertUserAll.cs:31 / UserAllRequestVO）。
    This session is consumed at the end of a game，musttextcontinueUploadRequiredtextlogin ——
    real machinetextofis「continueOff」：

        Process/ContinueProcess.cs:403
            new PacketUserLogin(userID, accessCode, isContinue: true, ...)

    Corresponding to this project：UserLogin(user_id, token, is_continue=True)
    The only difference between it and a normal login is that UserLoginRequestVO.isContinue = true，
    will return**textof loginId / loginDateTime**，For the next innings UpsertUserAll Use。

    ★ logoutMust use **type=1（LogoutType.Logout）**。
      real machinetextPackageEmpirical UserLogoutApi is type=1（Belt delayLog）：
          {"userId":...,"type":1,"delayLog":{...}}
      continueOfftextDownuse 4（TestIn）Something will go wrong —— thatis「text / text」ofsemantic。

--------------------------------------------------------------------------------
★ playlog Where did you come from?
--------------------------------------------------------------------------------
    GetNeedUserData textNoto userPlaylogList（thatistextgamerecord，noneCorresponding Get interface），
    So the script**Backward compositing from track recordings**：

        UserMusicDetail（9 Field）          ->  UserPlaylog（110 Field）
        ─────────────────────────────         ─────────────────────────
        musicId                                musicId
        level                                  level
        achievement                            achievement
        deluxscoreMax                          deluxscore
        scoreRank                              scoreRank / isClear
        comboStatus                            comboStatus
        syncStatus                             syncStatus
        Remaining fields                              Retrieved from config.PLAY_*（Reasonable default）

--------------------------------------------------------------------------------
usage
--------------------------------------------------------------------------------
    # textdatatextQR Code（Will network to catch A ofdata，and landed on data/<A>.json）
    python reincarnate.py --dst-qr <BofQR Code> --src-qr <AofQR Code>

    # textdatatextAlreadytextof JSON（text，text：No need to consume repeatedly A ofQR Code）
    python reincarnate.py --dst-qr <BofQR Code> --src-json data/12345678.json

    # ★ realUpload
    python reincarnate.py --dst-qr <BofQR Code> --src-json data/12345678.json --send

    # Just look at the plan，No Package Issued
    python reincarnate.py --dst-qr <BofQR Code> --src-json data/12345678.json --plan

    # Common switches
    --limit N          Only before relocation N first（textuse）
    --per-packet N     eachPackagetracknumber，can only be 1/3/4（default 4；★ 2 firstwill be rejected by the server）
    --wait N           eachtextUploadagoofwaitsecondsnumber（default 5.0，0 = Unequal）
    --clone-identity   text userName / accessCode Clone Together（default**Hold B textof**）
    --no-continue      Do not renew the pass（Only send one bag，debuguse）

★ textMeetings**realWrite**text B（Irrevocable）。Do not pass --send timeConstruct only packets。
★ QR Code**hastext 10 Minutes**。
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

#: real machineOnegameMax. 4 first
MAX_TRACKS_PER_CREDIT = 4

#: ★ textservertextofeachPackagetracknumber（Measured：**Just in time 2 firstMeetingstext**）
#:   1 / 3 / 4 firstallcurrenttext，Only 2 firstNotext —— So avoid it when batching.。
FORBIDDEN_TRACK_COUNTS = (2,)

#: Allowed --per-packet Pick a value
ALLOWED_PER_PACKET = (1, 3, 4)


def split_batches(total, per):
    """
    put total firstCuttext「eachPackage <= per」oftext，**and does not produce proscribed 2 firstPackage**。

    Practice：First greedy press per Cut，Then correct the size to 2 oftext：

        ① Previous batch >= 4 -> Borrow from it 1 firsttext（Previous batch change >=3，textChange 3）
        ② Can't borrow（Previous batch only 3，or the first ones themselves.）-> putthisPiece 2 text 1 + 1

    ★ Borrowing is not enough —— The previous batch was 3 timetextChange 2，etcinput 2 textPieceBittext。

    Example：
        10 first per=4 -> [4, 4, 2]    -> [4, 3, 3]
         6 first per=4 -> [4, 2]       -> [3, 3]
         2 first per=4 -> [2]          -> [1, 1]
         5 first per=3 -> [3, 2]       -> [3, 1, 1]
         8 first per=3 -> [3, 3, 2]    -> [3, 3, 1, 1]
         5 first per=4 -> [4, 1]       （textLegal，immovable）
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
        # ① Previous batch >= 4 onlycantext（Finished borrowing the previous batch >= 3，text = 3）
        if i > 0 and out[i - 1] >= 4:
            out[i - 1] -= 1
            out[i] += 1
            i += 1
            continue
        # ② Can't borrow -> putthisPiece 2 text 1 + 1
        out[i] = 1
        out.insert(i + 1, 1)
        i += 2
    return out

#: defaultHoldtextoftextField（Do not clone past，textput B changeFirst name）
IDENTITY_KEYS = ("userName", "accessCode")

#: texttime**No**textitemPassing onofnodes（musttextisBitstring、musttextby UpsertUserAll textcalculate）
SKIP_NODES = (
    "userMusicDetailList",     # Separate batches
    "userGamePlaylogList",     # bytextscriptpresstrackSynthesis
    "user2pPlaylog",           # 2P record，textnotext
    "userGetPointList",        # intext/Rewards，textMeetingstextemptyhairtext
    "userTradeItemList",       # no Get text
    "userFriendSeasonRankingList",   # no Get text
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
# Tools
# =============================================================================

def _bits_for(node, items, base_items):
    """
    presstext B ofBaselinecalculate isNew* Bitstring：
        B innonetheitemtext -> "1"（added）
        B inExisting       -> "0"（update）
    Primary key table in upsert_user_all.DIFF_PRIMARY_KEYS。
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
    From one UserMusicDetail（9 Field）Push back one PlayData，usetextSynthesis userPlaylog。

    Keep fields on config.PLAY_* ofdefaultValue（They're not in the track record.）。
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
    """puttext A ofnodestext extra_data（track/2P/Excluding awards）。"""
    out = {}
    for node in NODE_ORDER:
        if node in SKIP_NODES:
            continue
        if node.startswith("isNew"):
            continue          # Bitstring alone
        kind = NODE_TYPES.get(node)
        if kind not in ("singleton", "array", "object"):
            continue
        val = src_nodes.get(node)
        if val in (None, [], {}):
            continue
        out[node] = json.loads(json.dumps(val))     # text
    # textField：defaultHold B textof
    if not clone_identity and out.get("userData"):
        for item in out["userData"]:
            if isinstance(item, dict):
                for k in IDENTITY_KEYS:
                    item.pop(k, None)
    # Bitstring：press B ofBaselinecalculate
    for arr, bits in ARRAY_TO_BITS.items():
        if arr not in out:
            continue
        b = _bits_for(arr, out[arr], base_nodes.get(arr))
        if b:
            out[bits] = b
    return out


# =============================================================================
# Mainstream
# =============================================================================

def fetch_source_by_qr(qr):
    """usetext A ofQR CodetextOnetextdata（and automatically drops to data/<A>.json）。"""
    log_info("=== text：textTake ===")
    uid, token = ParseQRCode(qr)
    preview = GetUserPreview(uid, token)
    if preview.isLogin:
        raise RuntimeError("textplaceinAlreadylogintext，pleaseFirstatmachineStagelogout")
    login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
    try:
        raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
    finally:
        try:
            UserLogout(uid, token, login.loginDateTime, logout_type=LogoutType.TestIn,
                       region_id=REGION_ID, place_id=PLACE_ID)
        except Exception as exc:
            log_warning("textlogoutFailed：" + str(exc))
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
        print("--per-packet can only be " + str(list(ALLOWED_PER_PACKET))
              + " One（real machineOnegameMax. 4 first；★ Measured just right 2 firstwill be rejected by the server）")
        return 1

    setup_logging("reincarnate")
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---------------- 1. textdata ----------------
        if opts["src_json"]:
            src_raw = json.load(open(opts["src_json"], "r", encoding="utf-8"))
            log_info("=== text：Read from file " + opts["src_json"] + " ===")
        else:
            src_raw = fetch_source_by_qr(opts["src_qr"])

        src_nodes = normalize_snapshot(src_raw)
        musics = src_nodes.get("userMusicDetailList") or []
        if opts["limit"] > 0:
            musics = musics[:opts["limit"]]
        log_info("textdata：nodes " + str(len(src_nodes)) + " Piece，trackrecord " + str(len(musics)) + " item")

        if not musics:
            log_error("textdatainnone userMusicDetailList，textof。")
            return 4

        # ---------------- 2. text ----------------
        Ping()
        uid, token = ParseQRCode(opts["dst_qr"])
        session.update(user_id=uid, token=token)
        preview = GetUserPreview(uid, token)
        if preview.isLogin:
            log_error("textplaceinAlreadylogintext，pleaseFirstatmachineStagelogoutorwaitSessiontexttime")
            return 2
        login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        base_raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
        base_nodes = normalize_snapshot(base_raw)
        log_info("textBaselineAlreadytextTake")

        # ---------------- 3. Batch ----------------
        per = int(opts["per_packet"])
        sizes = split_batches(len(musics), per)
        batches = []
        _pos = 0
        for _n in sizes:
            batches.append(musics[_pos:_pos + _n])
            _pos += _n
        log_info("counttext：of " + str(len(musics)) + " first -> " + str(len(batches))
                 + " Package，eachPackage " + "/".join(str(n) for n in sizes[:12])
                 + ("..." if len(sizes) > 12 else "") + " first")
        log_info("  ★ Avoided 2 firstPackage（Measured just right 2 firstwill be rejected by the server；1/3/4 firstallcurrenttext）")

        if opts["plan"]:
            for i, b in enumerate(batches):
                log_info("    number " + str(i + 1) + " Package（" + str(len(b)) + " first）：" + ", ".join(
                    str(x.get("musicId")) + "/L" + str(x.get("level")) for x in b))
            log_info("--plan：Column Only Plans，No Package Issued")
            return 0

        # numberOnePackageonlyBeltnon-tracknodes（text）
        shared_nodes = collect_nodes(src_nodes, base_nodes, opts["clone_identity"])
        log_info("non-tracknodes " + str(len([k for k in shared_nodes if not k.startswith('isNew')]))
                 + " will take place on the 1 Package upload")

        # ---------------- 4. textPackage upload ----------------
        # ★ text（pressUsetext）：
        #     login -> wait -> Upload -> logout(type=1) -> continueOfflogin -> wait -> Upload -> logout -> ...
        #
        # ★ logoutMust use type=1（LogoutType.Logout）。
        #   real machinetextPackageEmpirical UserLogoutApi is type=1（Belt delayLog）；
        #   continueOfftextDownuse 4（TestIn）Something will go wrong —— thatis「text/text」ofsemantic。
        sent = 0
        for idx, batch in enumerate(batches):
            log_info("")
            log_info("========== number " + str(idx + 1) + "/" + str(len(batches))
                     + " Package（" + str(len(batch)) + " first）==========")

            # ---- wait ----
            if opts["wait"] > 0:
                log_info("Wait before uploading " + str(opts["wait"]) + " seconds ...")
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

            # Synthesis playlog（eachfirstOneitem）And game playlog
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

            # ---- ★ logout（type=1 Logout）----
            log_info("--- logout（type=1 Logout）---")
            try:
                UserLogout(uid, token, login.loginDateTime,
                           logout_type=LogoutType.Logout,
                           region_id=REGION_ID, place_id=PLACE_ID)
            except Exception as exc:
                log_warning("logoutFailed（textcontinueDownOnePackage）：" + str(exc))
            session["logged_in"] = False

            # ---- ★ continueOfflogin：textDownOnePackageof loginId ----
            if idx < len(batches) - 1:
                if opts["no_continue"]:
                    log_warning("--no-continue：No more renewals，textagotext（Sent only 1 Package）")
                    break
                log_info("--- continueOfflogin（isContinue=true）---")
                login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID,
                                  is_continue=True)
                session.update(login_dt=login.loginDateTime, logged_in=True)

        if not opts["send"]:
            log_info("")
            log_info("[dry-run] notPackaging。For real migration, please add --send（★ will be added to your account B）")
            return 0

        log_info("")
        log_info("★ textDone：Total Uploads " + str(sent) + " Package / "
                 + str(min(len(musics), sent * per)) + " first")
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
                log_error("[receiveTail] Force Logout Failed（Session may need to wait for server timeout）：" + str(exc))
        teardown_logging()


if __name__ == "__main__":
    sys.exit(main())
