#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reincarnate. py — data(): put A of data to B
================================================================================

  ┌─ A ─────────────────────────────────────────────┐
  │ QR Code -> ParseQRCode -> UserLogin -> GetNeedUserData │
  │ or: directly read data/<userId>. json (Multiplexing)       │
  └────────────────────────────────────────────────────────┘
              ↓ node data
  ┌─ B ───────────────────────────────────────────┐
  │ QR Code -> ParseQRCode -> UserPreview -> UserLogin   │
  │ Loop:                         │
  │   wait -> UpsertUserAll(Pack of tracks)         │
  │   -> UserLogout(type=1)               │
  │   -> UserLogin(isContinue=true) continued, loginId  │
  │ receiveTail: End after last packet logged out(No more renewals)          │
  └────────────────────────────────────────────────────────┘

--------------------------------------------------------------------------------
- each packet count: 1 / 3 / 4 Yes, **exactly two will be rejected by the server**
--------------------------------------------------------------------------------
  one real-machine game(one credit)Up to dozens four tracks, So one UpsertUserAll in one packet
  userPlaylogList / userGamePlaylogList **Max. 4 item**.

  - But measured: **each packet exactly two will be rejected by the server** (1 / 3 / 4 all current).
   So the batch batcher of the script will **Proactively avoid two tracks Package**:

     10 first -> [4, 4, 2] -> [4, 3, 3]
      6 first -> [4, 2]  -> [3, 3]
      two tracks -> [2]    -> [1, 1]

  - each packet all must contain **non-empty** of userPlaylogList — pitfall number 2 item Measured:
   leaving it blank causes server When no packet **text** (returnCode=1 But not out of stock.).

--------------------------------------------------------------------------------
- Why is it needed "continued login"
--------------------------------------------------------------------------------
  UpsertUserAll of playlogId Must be equal to**login**of loginId
  (PacketUpsertUserAll. cs:31 / UserAllRequestVO).
  This session is consumed at the end of a game, must continued login is required for uploads —
  the real machine uses"continued":

    Process/ContinueProcess. cs:403
      new PacketUserLogin(userID, accessCode, isContinue: true,...)

  Corresponding to this project: UserLogin(user_id, token, is_continue=True)
  The only difference between it and a normal login is that UserLoginRequestVO. isContinue = true,
  will return **of loginId / loginDateTime**, For the next innings UpsertUserAll Use.

  - logout Must use **type=1 (LogoutType. Logout)**.
   real-machine packet capture confirms UserLogoutApi is type=1(Belt delayLog):
     {"userId":...,"type":1,"delayLog":{...}}
   using continued login with 4 (TestIn) will fail — that is "/" semantics.

--------------------------------------------------------------------------------
- playlog Where did you come from?
--------------------------------------------------------------------------------
  GetNeedUserData cannot obtain userPlaylogList(these are game records, with no corresponding Get interface),
  So the script **reconstructing from track recordings**:

    UserMusicDetail(9 Field)     -> UserPlaylog(110 Field)
    ─────────────────────────────     ─────────────────────────
    musicId                musicId
    level                 level
    achievement              achievement
    deluxscoreMax             deluxscore
    scoreRank               scoreRank / isClear
    comboStatus              comboStatus
    syncStatus               syncStatus
    Remaining fields               Retrieved from config. PLAY_*(Reasonable default)

--------------------------------------------------------------------------------
usage
--------------------------------------------------------------------------------
  # source data from a QR code(Will network to catch A ofdata, and landed on data/<A>. json)
  python reincarnate. py --dst-qr <B QR code> --src-qr <A QR code>

  # source data from saved JSON(No need to consume repeatedly A ofQR Code)
  python reincarnate. py --dst-qr <B QR code> --src-json data/12345678. json

  # - real Upload
  python reincarnate. py --dst-qr <B QR code> --src-json data/12345678. json --send

  # Just look at the plan, no packet is sent
  python reincarnate. py --dst-qr <B QR code> --src-json data/12345678. json --plan

  # Common switches
  --limit N     Only before relocation N first(use)
  --per-packet N   tracks per packet, can only be 1/3/4(default 4;- 2 will be rejected by the server)
  --wait N      wait time before each upload(default 5.0,0 = Unequal)
  --clone identity: userName / accessCode Clone Together(default**keep B's**)
  --no-continue   Do not renew the pass(Only send one bag, for debugging)

- Meetings **write to** B (Irrevocable). Do not pass --send time Construct only packets.
- QR Code**has 10 Minutes**.
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

#: one real-machine gameMax. four tracks
MAX_TRACKS_PER_CREDIT = 4

#: - server-side tracks per packet (Measured: **exactly two first Meetings**)
#:  1 / 3 / 4 allcurrentOnly two tracksNo — So avoid it when batching..
FORBIDDEN_TRACK_COUNTS = (2,)

#: Allowed --per-packet Pick a value
ALLOWED_PER_PACKET = (1, 3, 4)


def split_batches(total, per):
    """
  put total first Cut "each packet <= per" of **and does not produce proscribed two tracks Package**.

  Practice: First greedy press per Cut, Then correct the size to 2 of

    ① Previous batch >= 4 -> Borrow from it one track(Previous batch change >=3, change 3)
    ② Can't borrow(Previous batch only 3, or the first ones themselves.)-> putthisPiece 2 1 + 1

  - Borrowing is not enough — The previous batch was 3 timechange 2, etcinput 2 itemBit

  Example:
    10 first per=4 -> [4, 4, 2]  -> [4, 3, 3]
     6 first per=4 -> [4, 2]    -> [3, 3]
     two tracks per=4 -> [2]     -> [1, 1]
     5 first per=3 -> [3, 2]    -> [3, 1, 1]
     8 first per=3 -> [3, 3, 2]  -> [3, 3, 1, 1]
     5 first per=4 -> [4, 1]    (Legal, immovable)
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
        # ① Previous batch >= 4 onlycan(Finished borrowing the previous batch >= 3,= 3)
        if i > 0 and out[i - 1] >= 4:
            out[i - 1] -= 1
            out[i] += 1
            i += 1
            continue
        # ② Can't borrow -> putthisPiece 2 1 + 1
        out[i] = 1
        out.insert(i + 1, 1)
        i += 2
    return out

#: defaultHoldoffield(Do not clone past, put B changeFirst name)
IDENTITY_KEYS = ("userName", "accessCode")

#: time**No**itemPassing onofnodes(mustisBitstring, mustby UpsertUserAll calculate)
SKIP_NODES = (
    "userMusicDetailList",     # Separate batches
    "userGamePlaylogList",     # byscriptpresstrackSynthesis
    "user2pPlaylog",           # 2P record, no
    "userGetPointList",        # in/Rewards, Meetingsemptyhair
    "userTradeItemList",       # no Get
    "userFriendSeasonRankingList",   # no Get
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
  press B ofBaselinecalculate isNew* Bitstring:
    B innonetheitem -> "1"(added)
    B inExisting    -> "0"(update)
  Primary key table in upsert_user_all. DIFF_PRIMARY_KEYS.
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
  From one UserMusicDetail(9 Field)Push back one PlayData, useSynthesis userPlaylog.

  Keep fields on config. PLAY_* ofdefaultValue(They're not in the track record.).
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
    """put A ofnodes extra_data(track/2P/Excluding awards)."""
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
        out[node] = json.loads(json.dumps(val))     #
    # field: defaultkeep B's
    if not clone_identity and out.get("userData"):
        for item in out["userData"]:
            if isinstance(item, dict):
                for k in IDENTITY_KEYS:
                    item.pop(k, None)
    # Bitstring: press B ofBaselinecalculate
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
    """use A ofQR Codeonedata(and automatically drops to data/<A>. json)."""
    log_info("=== fetch ===")
    uid, token = ParseQRCode(qr)
    preview = GetUserPreview(uid, token)
    if preview.isLogin:
        raise RuntimeError("placeinAlreadyloginpleaseFirstatmachine statelogout")
    login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
    try:
        raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
    finally:
        try:
            UserLogout(uid, token, login.loginDateTime, logout_type=LogoutType.TestIn,
                       region_id=REGION_ID, place_id=PLACE_ID)
        except Exception as exc:
            log_warning("logoutFailed:" + str(exc))
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
              + " One(one real-machine gameMax. four tracks;- Measured just right 2 will be rejected by the server)")
        return 1

    setup_logging("reincarnate")
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---------------- 1. data ----------------
        if opts["src_json"]:
            src_raw = json.load(open(opts["src_json"], "r", encoding="utf-8"))
            log_info("=== Read from file " + opts["src_json"] + " ===")
        else:
            src_raw = fetch_source_by_qr(opts["src_qr"])

        src_nodes = normalize_snapshot(src_raw)
        musics = src_nodes.get("userMusicDetailList") or []
        if opts["limit"] > 0:
            musics = musics[:opts["limit"]]
        log_info("data: nodes " + str(len(src_nodes)) + " Piece, trackrecord " + str(len(musics)) + " item")

        if not musics:
            log_error("datainnone userMusicDetailList, of.")
            return 4

        # ---------------- 2. ----------------
        Ping()
        uid, token = ParseQRCode(opts["dst_qr"])
        session.update(user_id=uid, token=token)
        preview = GetUserPreview(uid, token)
        if preview.isLogin:
            log_error("placeinAlreadyloginpleaseFirstatmachine statelogoutorwaitSessiontime")
            return 2
        login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        base_raw = GetNeedUserData(uid, token=token, place_id=PLACE_ID, region_id=REGION_ID)
        base_nodes = normalize_snapshot(base_raw)
        log_info("Baseline Already fetch")

        # ---------------- 3. Batch ----------------
        per = int(opts["per_packet"])
        sizes = split_batches(len(musics), per)
        batches = []
        _pos = 0
        for _n in sizes:
            batches.append(musics[_pos:_pos + _n])
            _pos += _n
        log_info("count of " + str(len(musics)) + " first -> " + str(len(batches))
                 + " Package, each packet " + "/".join(str(n) for n in sizes[:12])
                 + ("..." if len(sizes) > 12 else "") + " first")
        log_info(" - Avoided two tracks Package (Measured just right 2 will be rejected by the server; 1/3/4 all current)")

        if opts["plan"]:
            for i, b in enumerate(batches):
                log_info("  number " + str(i + 1) + " Package(" + str(len(b)) + " first):" + ", ".join(
                    str(x.get("musicId")) + "/L" + str(x.get("level")) for x in b))
            log_info("--plan: Column Only Plans, no packet is sent")
            return 0

        # number One Package only Belt non-track nodes()
        shared_nodes = collect_nodes(src_nodes, base_nodes, opts["clone_identity"])
        log_info("non-track nodes " + str(len([k for k in shared_nodes if not k.startswith('isNew')]))
                 + " will take place on the 1 Package upload")

        # ---------------- 4. packet upload ----------------
        # -(pressUse):
        #   login -> wait -> Upload -> logout(type=1) -> continued login -> wait -> Upload -> logout ->...
        #
        # - logout Must use type=1 (LogoutType. Logout).
        #  real-machine packet capture confirms UserLogoutApi is type=1(Belt delayLog);
        #  using continued login with 4 (TestIn) will fail — that is "text/text" semantics.
        sent = 0
        for idx, batch in enumerate(batches):
            log_info("")
            log_info("========== number " + str(idx + 1) + "/" + str(len(batches))
                     + " Package(" + str(len(batch)) + " first)==========")

            # ---- wait ----
            if opts["wait"] > 0:
                log_info("Wait before uploading " + str(opts["wait"]) + " seconds...")
                time.sleep(opts["wait"])

            nodes = {}
            if idx == 0:
                nodes.update(json.loads(json.dumps(shared_nodes)))
            nodes["userMusicDetailList"] = json.loads(json.dumps(batch))
            b = _bits_for("userMusicDetailList", batch,
                          base_nodes.get("userMusicDetailList"))
            if b:
                nodes["isNewMusicDetailList"] = b
                log_info("  isNewMusicDetailList = " + b)

            # Synthesis playlog(eachoneitem)And game playlog
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

            # ---- - logout(type=1 Logout)----
            log_info("--- logout(type=1 Logout)---")
            try:
                UserLogout(uid, token, login.loginDateTime,
                           logout_type=LogoutType.Logout,
                           region_id=REGION_ID, place_id=PLACE_ID)
            except Exception as exc:
                log_warning("logout Failed (continue Down One Package): " + str(exc))
            session["logged_in"] = False

            # ---- - continued login: DownOnePackageof loginId ----
            if idx < len(batches) - 1:
                if opts["no_continue"]:
                    log_warning("--no-continue: No more renewals, ago(Sent only 1 Package)")
                    break
                log_info("--- continued login(isContinue=true)---")
                login = UserLogin(uid, token, region_id=REGION_ID, place_id=PLACE_ID,
                                  is_continue=True)
                session.update(login_dt=login.loginDateTime, logged_in=True)

        if not opts["send"]:
            log_info("")
            log_info("[dry-run] not Packaging. For real migration, please add --send (will be added to your account B)")
            return 0

        log_info("")
        log_info("- Done: Total Uploads " + str(sent) + " Package / "
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
                log_error("[receiveTail] Force Logout Failed(Session may need to wait for server timeout):" + str(exc))
        teardown_logging()


if __name__ == "__main__":
    sys.exit(main())
