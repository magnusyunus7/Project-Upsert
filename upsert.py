#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upsert.py —— Master Script：QR login → Upload Grades → logout
================================================================================

textitemtextOnlyFourtext，andAnd**You don't have to write your own logs** ——
eachPiece api Function is automatically printed when called：

    === UserLogin Get started ===
      [interfacedescription] usercurrenttextlogin（Open this login session）。
      [Location Parameters] 12345678, 'iUfgRmjr...'
      [Keyword Parameters] region_id=1, place_id=1000
    === UserLogin run completion ===

logmodechange config.py One Row：

    LOG_LEVEL = "info"     Show only api scriptoftextandresult
    LOG_LEVEL = "debug"    textShowcaseTowards api Data sent vs. api returntimesofdata

logfile（Two types of writing at the same time）：

    logs/latest.log        Contains only**Current time**Master Script Run（Next override）
    logs/YYYY-MM-DD.log    Storage**Same day**All generated logs（textPlus）

--------------------------------------------------------------------------------
usage
--------------------------------------------------------------------------------
    python upsert.py <QR Code>                       # text：login + textSnapshot + groupPackage，No Package Issued
    python upsert.py <QR Code> --send                # realUpload Grades（★ hasSide effects，Irrevocable）
    python upsert.py <QR Code> --send --debug        # Ibid.，loginBeltFullreceivehairpacket
    python upsert.py <QR Code> --send --cooldown 0   # skipPackagingagoof 60 secondsCooling
    python upsert.py <QR Code> --send --no-verify    # skipUploadAfteroffallLibrarytimescheck

    # ★ textnodes（--extra-data，Repeatable，Later given overlay given first）
    python upsert.py <QR Code> --send --extra-data extra.json
    python upsert.py <QR Code> --send --extra-data '{"isNewMapList":"1"}'
    python upsert.py <QR Code> --send --extra-data a.json --extra-data b.json

--------------------------------------------------------------------------------
★ UpsertUserAll One function completes the entire settlement link
--------------------------------------------------------------------------------
    1. textBaseline Snapshot（textPassing on snapshot timetext，use token）
    2. Push Local from Snapshot 5 Roles only（playagolevel）
    3. constructthis gameResultsdetails userPlaylogList
    4. callFront connector GetUserNewItemListApi
    5. grouptext upsertUserAll of 36 nodes（Snapshot Baseline + this gametextcalculate + Differential）
    6. Merge extra_data inofExternal JSON
    7. Self-inspection before contract issuance
    8. Cooling -> realPackaging
    9. fallLibrarytimescheck（textserverdata，textoftextGotext）

--------------------------------------------------------------------------------
★ --extra-data：textnodes
--------------------------------------------------------------------------------
    Want to overwrite manually / textUptextnodes（textAsthis gametexttooftext KaleidxScope text）timeuse：

        # ① Read from file（★ text，No need to follow shell Quotation mark wrestling）
        python upsert.py <QR Code> --send --extra-data extra.json

        # ② directlytext JSON String
        python upsert.py <QR Code> --send --extra-data '{"isNewMapList":"1"}'

        # ③ Multiple sources，Later given overlay given first
        python upsert.py <QR Code> --send --extra-data base.json --extra-data patch.json

    extra.json longthistext：

        {
          "userKaleidxScopeList": [
            {"gateId": 1, "isGateFound": true, "isKeyFound": true, "isClear": false,
             "totalRestLife": 0, "totalAchievement": 0, "totalDeluxscore": 0,
             "bestAchievement": 0, "bestDeluxscore": 0,
             "bestAchievementDate": "", "bestDeluxscoreDate": "",
             "playCount": 0, "clearDate": "", "lastPlayDate": "", "isInfoWatched": false}
          ],
          "isNewKaleidxScopeList": "1"
        }

    ★ keyMust be upsertUserAll of 36 One of nodes（Contains 11 item isNew* Bitstring），
      A typo will explicitly report the error and list the available node names。
    ★ textCorrespondingBitstringtimeMeetingspressnumbergrouplengthtext "0" and prompt ——
      addeditemtextpleaseexplicitPassing on "1"，"0" textInventory update。
    ★ JSON at**textBefore**Just check，Wrongly Write Directly Exit，No QR code wasted。

  ── Call directly from within the code api ofetctext ──

    UpsertUserAll(
        user_id, login.loginId,
        login_date_time=login.loginDateTime,
        auth_date_time=login.dateTime,
        token=token,
        extra_data={"userKaleidxScopeList": [...], "isNewKaleidxScopeList": "1"},
        confirm=True,
    )
"""

from __future__ import annotations

import sys

from api import (
    setup_logging,
    teardown_logging,
    log_info,
    log_warning,
    log_error,
    ParseQRCode,
    GetUserPreview,
    UserLogin,
    UserLogout,
    LogoutType,
    UpsertUserAll,
    ConfirmRequiredError,
    load_extra_data,
    PatchError,
    NODE_ORDER,
    NODE_TYPES,
)
from config import PLACE_ID, REGION_ID


def parse_args(argv):
    """textparse：numberOnenon- -- The parameters at the beginning are QR codes。"""
    opts = {"qr": "", "send": False, "debug": False, "no_verify": False,
            "cooldown": None, "extra_data": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--send":
            opts["send"] = True
        elif a == "--debug":
            opts["debug"] = True
        elif a == "--no-verify":
            opts["no_verify"] = True
        elif a == "--extra-data" and i + 1 < len(argv):
            # Repeatable；Value is JSON String or JSON file path
            opts["extra_data"].append(argv[i + 1])
            i += 1
        elif a == "--cooldown" and i + 1 < len(argv):
            opts["cooldown"] = float(argv[i + 1])
            i += 1
        elif not a.startswith("--") and not opts["qr"]:
            opts["qr"] = a
        i += 1
    return opts


def main() -> int:
    opts = parse_args(sys.argv[1:])
    if not opts["qr"]:
        print(__doc__)
        return 1

    # --debug Only affect this run，No change config.py
    if opts["debug"]:
        import config as _cfg
        _cfg.LOG_LEVEL = "debug"

    # logSession：Beginning sentence。Every time thereafter api calluseallMeetingstextrecord，The main script no longer logs
    setup_logging("upsert")

    # ---- ★ Parsing first --extra-data（textattextBefore：JSON Don't waste the QR code if you make a mistake）----
    extra = None
    if opts["extra_data"]:
        merged = {}
        try:
            for item in opts["extra_data"]:
                part = load_extra_data(item)
                merged.update(part)
                log_info("--extra-data readtext " + str(len(part)) + " nodes：" + ", ".join(part))
        except PatchError as exc:
            log_error("--extra-data parseFailed：" + str(exc))
            return 6

        # nodesFirst nameAlsoherecheck（Otherwise, you will have to wait until you are logged in to package before reporting an error.，textOnetext）
        unknown = [k for k in merged if k not in NODE_TYPES]
        if unknown:
            log_error("--extra-data inhasnottextnodesFirst name：" + ", ".join(unknown))
            log_error("  Available Nodes（" + str(len(NODE_ORDER)) + " Piece）：" + ", ".join(NODE_ORDER))
            return 6

        if not merged:
            log_warning("--extra-data parseouttextisemptyof，Ignore")
        else:
            extra = merged
            log_info("--extra-data Total " + str(len(extra)) + " nodes：" + ", ".join(extra))

    # Session Status：Guaranteed to log out in case of abnormalities（Otherwise, your account will be stuck on isLogin=True，Next Login returnCode=100）
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---- text：QR Code -> userId + token ----
        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        # ---- text：text「textattext」oftext，text ----
        preview = GetUserPreview(user_id, token)
        if preview.isLogin:
            log_error("textplaceinAlreadylogintext，pleaseFirstatmachineStagelogoutorwaitSessiontexttime")
            return 2

        # ---- login：textto playlogId And loginDateTime（settlementEscalationsmustuse）----
        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- settlement：★ A function takes care of the construction + Packaging + fallLibrarytimescheck ----
        UpsertUserAll(
            user_id, login.loginId,
            login_date_time=login.loginDateTime,
            auth_date_time=login.dateTime,
            token=token,
            extra_data=extra,
            dry_run=not opts["send"],
            confirm=opts["send"],
            cooldown_sec=opts["cooldown"],
            verify_landing=not opts["no_verify"],
            place_id=PLACE_ID, region_id=REGION_ID,
        )
        return 0

    except ConfirmRequiredError:
        return 5
    except Exception as exc:
        log_error(type(exc).__name__ + ": " + str(exc))
        return 1
    finally:
        # Log out from the bottom of the pocket：logintextAndtextlogouttextSession，Otherwise, the account card will be isLogin=True
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
