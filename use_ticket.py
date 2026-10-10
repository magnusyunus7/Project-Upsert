#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
use_ticket. py — consumecurrenthasofFeatures(use UpsertUserAll"useone game")
================================================================================

a complete"use"

  ParseQRCode -> GetUserPreview -> UserLogin -> GetUserCharge
   -> GetNeedUserData(Baseline Snapshot)-> UpsertUserAll -> GetUserCharge(Review)-> UserLogout

--------------------------------------------------------------------------------
- Why you can use UpsertUserAll consume
--------------------------------------------------------------------------------
  GetUserChargeApi And UpsertUserAllApi inof userChargeList **fullrelatedSame**
  (UserCharge. cs: chargeId / stock / purchaseDate / validDate),
  So just put the UpsertUserAll of userChargeList nodeschange"the stock - 1",
  the server willforthisticketsthisone gameuse

  real machineEmpirical(gamehook packet 2026-10-06 22:23 thatone game, currentuse 2 Ticket multiplier):

    userChargeList: [
     {"chargeId":2,"stock":0,...},  <- When I bought it, it was 1, this gameusechange 0
     {"chargeId":3,"stock":0,...},
     {"chargeId":5,"stock":0,...}
    ]
    userGamePlaylogList[0]. useTicketId = 2   <- - usetickets
    userGamePlaylogList[0]. playCredit = 2   <- - this gameconsumeof credit
    userPlaylogList[0]. playCredit   = 2
    userData. lastPlayCredit      = 2

  - playCredit ofcalculate(source/.../Net. VO. Mai2/VOExtensions. cs:838-845):

    playCredit = Credit. GameCostEnoughPlay()     // number, game = 1
          + TicketManager. GetTicketCredit(ticketId) // of creditNum

   2 Coupon multiplier's creditNum = 1 -> playCredit = 1 + 1 = 2 (Consistent with real machine grab bag)
   creditNum TICKET_CREDIT_NUM.

  - real-machine in the packet**none** isNewChargeList thisnodes(It's not in 36 out of nodes),
   So there's no need to give bit strings here either..

--------------------------------------------------------------------------------
usage
--------------------------------------------------------------------------------
  python use_ticket. py <QR Code>             # Messages only, no packet is sent
  python use_ticket. py <QR Code> --list          # Only currently held tickets are listed, Does not consume
  python use_ticket. py <QR Code> --ticket-id 2      # specifiedmustconsumeZhang(defaultnumberOneZhanghasof)
  python use_ticket. py <QR Code> --ticket-id 2 --send   # - realconsume
  python use_ticket. py <QR Code> --send --music-id 143 --level 4
  python use_ticket. py <QR Code> --send --skip-entry   # skipAdmission data download

- consumewill be written to the server(Irrevocable). Do not pass --send timeConstruct only packets.
- QR Code**has 10 Minutes**.
- current**none**hasfeature ticketstimedirectly(noneconsumeof).
"""

from __future__ import annotations

import sys

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
    GetUserCharge,
    GetNeedUserData,
    summarize_snapshot,
    UpsertUserAll,
    PlayData,
    ConfirmRequiredError,
    ticket_name,
    Ping,
    # - Originally in config. py, moved to api/upsert_user_chargelog. py
    TICKET_CREDIT_NUM,
)
from config import (
    PLACE_ID,
    REGION_ID,
    PLAY_MUSIC_ID,
    PLAY_MUSIC_LEVEL,
    PLAY_CREDIT,
)


def read_charges(user_id, label):
    """call GetUserChargeApi, and go back to (All, hasof)."""
    raw = GetUserCharge(user_id)
    lst = (raw.get("userChargeList") if isinstance(raw, dict) else None) or []
    log_info("[" + label + "] Current Ticket " + str(len(lst)) + " item:")
    if not lst:
        log_info("  (empty)")
    for c in lst:
        cid = c.get("chargeId")
        stock = int(c.get("stock", 0) or 0)
        log_info("  chargeId=" + str(cid) + " " + ticket_name(cid)
                 + " stock=" + str(stock)
                 + " purchaseDate=" + str(c.get("purchaseDate"))
                 + " validDate=" + str(c.get("validDate"))
                 + ("  ← - has" if stock > 0 else ""))
    held = [c for c in lst if isinstance(c, dict) and int(c.get("stock", 0) or 0) > 0]
    log_info("[" + label + "] hasinfeature tickets:" + str(len(held)) + " Zhang")
    return lst, held


def parse_args(argv):
    opts = {"qr": "", "ticket_id": None, "send": False, "list": False,
            "debug": False, "skip_entry": False,
            "music_id": PLAY_MUSIC_ID, "level": PLAY_MUSIC_LEVEL}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--send":
            opts["send"] = True
        elif a == "--list":
            opts["list"] = True
        elif a == "--debug":
            opts["debug"] = True
        elif a == "--skip-entry":
            opts["skip_entry"] = True
        elif a == "--ticket-id" and i + 1 < len(argv):
            opts["ticket_id"] = int(argv[i + 1])
            i += 1
        elif a == "--music-id" and i + 1 < len(argv):
            opts["music_id"] = int(argv[i + 1])
            i += 1
        elif a == "--level" and i + 1 < len(argv):
            opts["level"] = int(argv[i + 1])
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

    if opts["debug"]:
        import config as _cfg
        _cfg.LOG_LEVEL = "debug"

    setup_logging("use_ticket")
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---- Heartbeat: Decide on all subsequent requests number Head ----
        Ping()

        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        preview = GetUserPreview(user_id, token)
        if preview.isLogin:
            log_error("placeinAlreadyloginpleaseFirstatmachine statelogoutorwaitSessiontime")
            return 2

        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- - readcurrent features ----
        all_charges, held = read_charges(user_id, "consumeago")

        if opts["list"]:
            log_info("--list: Tickets only, Do nothing to write")
            return 0

        if not held:
            log_error("current**nonehasAnyfeature tickets**, noneconsumeof")
            log_error(" Please use if you want to buy tickets buy_ticket. py; Tickets already in your possession will be sent to userChargeList in stock > 0.")
            return 4

        # ---- ----
        target = None
        if opts["ticket_id"] is not None:
            for c in held:
                if int(c.get("chargeId", -1)) == int(opts["ticket_id"]):
                    target = c
                    break
            if target is None:
                log_error("specifiedof chargeId=" + str(opts["ticket_id"])
                          + " Not currently in possession; hasofhas:"
                          + ", ".join(str(c.get("chargeId")) for c in held))
                return 4
        else:
            target = held[0]

        ticket_id = int(target.get("chargeId"))
        credit_num = int(TICKET_CREDIT_NUM.get(ticket_id, 0) or 0)
        play_credit = int(PLAY_CREDIT) + credit_num

        log_info("mustconsumeofchargeId=" + str(ticket_id) + " " + ticket_name(ticket_id)
                 + " stock=" + str(target.get("stock"))
                 + " creditNum=" + str(credit_num)
                 + " -> playCredit=" + str(PLAY_CREDIT) + "+" + str(credit_num)
                 + "=" + str(play_credit))

        # ---- - constructof userChargeList: stock - 1, Rest as is ----
        new_stock = int(target.get("stock", 0) or 0) - 1
        if new_stock < 0:
            new_stock = 0
        new_list = []
        for c in all_charges:
            if not isinstance(c, dict):
                continue
            item = dict(c)
            if int(item.get("chargeId", -1)) == ticket_id:
                item["stock"] = new_stock
                log_info("  userChargeList in chargeId=" + str(ticket_id)
                         + " of stock:" + str(target.get("stock")) + " -> " + str(new_stock))
            new_list.append(item)

        # ---- Admission data download(real machineAt the same time, it UpsertUserAll ofBaseline Snapshot)----
        snapshot = None
        if not opts["skip_entry"]:
            snapshot = GetNeedUserData(user_id, token=token,
                                       place_id=PLACE_ID, region_id=REGION_ID)
            _sum = summarize_snapshot(snapshot)
            log_info("Admission data download complete:" + str(len(_sum)) + " nodes, Failed "
                     + str(len(snapshot.get("_failed") or [])) + " Piece")

        # ---- - use UpsertUserAll"usethisticketsone game"----
        #  play. use_ticket_id -> userGamePlaylogList[0]. useTicketId
        #  play. play_credit  -> userGamePlaylogList[0]. playCredit / userPlaylogList[]. playCredit
        #             / userData. lastPlayCredit
        #  extra_data. userChargeList -> overwritenodes, putof stock Subtract 1
        play = PlayData(
            music_id=opts["music_id"],
            music_level=opts["level"],
            use_ticket_id=ticket_id,
            play_credit=play_credit,
        )
        UpsertUserAll(
            user_id, login.loginId,
            login_date_time=login.loginDateTime,
            auth_date_time=login.dateTime,
            token=token,
            snapshot=snapshot,
            play=play,
            extra_data={"userChargeList": new_list},
            dry_run=not opts["send"],
            confirm=opts["send"],
            verify_landing=bool(opts["send"]),
            place_id=PLACE_ID, region_id=REGION_ID,
        )

        # ---- - Review: stock Should be subtracted 1 ----
        _, held_after = read_charges(user_id, "consumeAfter")
        if not opts["send"]:
            log_info("[dry-run] notPackaging. If you want to really consume, please add --send(- will be written to the server)")
            return 0

        still = [c for c in held_after if int(c.get("chargeId", -1)) == ticket_id]
        if still:
            log_warning("chargeId=" + str(ticket_id) + " Still in possession(stock="
                        + str(still[0].get("stock")) + ")— servercanpost-upload")
            return 6
        log_info("- already consumed: chargeId=" + str(ticket_id) + " No longer in possession ✅")
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
