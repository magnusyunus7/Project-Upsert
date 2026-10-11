#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buy_ticket. py — Sample Master Script: QR login → purchase tickets Tickets → logout
================================================================================

a complete "Buy tickets"

  ParseQRCode -> GetUserPreview -> UserLogin -> UpsertUserChargelog -> UserLogout

UpsertUserChargelog These things happen automatically internally. (So the main script doesn't have to worry about it.):
  1. call GetUserChargeApi Get the current ticket list (calculate "purchaseBuyAfterInventory")
  2. call GetUserDataApi Take playCount / playerRating
  3. press TicketManager. cs:564 calculate validDate(currentat -4h +90d, Pick a date to make up 04:00:00)
  4. check TICKET_CREDIT_NUM(moved to api/upsert_user_chargelog. py)Get
  userChargelog. price(= ticket. creditNum)
  5. → Packaging

--------------------------------------------------------------------------------
usage
--------------------------------------------------------------------------------
  python buy_ticket. py <QR Code>            # Messages only, no packet is sent
  python buy_ticket. py <QR Code> --list         # Only current tickets and available tickets are listed
  python buy_ticket. py <QR Code> --charge-id 3     # specified (default 5 = 5 Ticket multiplier)
  python buy_ticket. py <QR Code> --charge-id 2 --send  # - realpurchaseBuy
  python buy_ticket. py <QR Code> --charge-id 2 --send --debug
  python buy_ticket. py <QR Code> --charge-id 2 --send --skip-entry  # skip Admission data download

Paid tickets (api. PAID_TICKET_IDS):
  2 = 2timesチケット  creditNum 1
  3 = 3timesチケット  creditNum 2
  4 = 4timesチケット  creditNum 3
  5 = 5timesチケット  creditNum 4
  6 = 6timesチケット  creditNum 5

- realpurchaseBuyMeetingsWriteA purchase history(Irrevocable). Do not pass --send timeConstruct only packets.

- QR Code Yes **time** (**has 10 Minutes**), after aimedb returns errorID=2
 — **Not Measured by Frequency**, Just do it.

- purchaseBuyagoMeetingsFirstcheckOncefeature tickets;**buying while feature tickets are heldBuy**(purchaseBuyhasTitle Risk).
"""

from __future__ import annotations

import sys
import time

from api import (
    setup_logging,
    teardown_logging,
    log_error,
    log_info,
    ParseQRCode,
    GetUserPreview,
    UserLogin,
    UserLogout,
    LogoutType,
    UpsertUserChargelog,
    ChargelogConfirmError,
    ChargelogGuardError,
    GetUserCharge,
    GetGameCharge,
    ticket_name,
    GetNeedUserData,
    summarize_snapshot,
    Ping,
)
from config import PLACE_ID, REGION_ID


def show_charges(user_id, label):
    """
  - call GetUserChargeApi current Ticket and go back to stock > 0 of that

  -- Why do we check before running and after running?:
    real machineOnly in"this gamemustusethistickets"timeonlypurchaseBuy, The buyer will be used immediately(stock--),
    So the normal state stock Constantly 0.
    **Already holding the ticket and going to buy it, servertoofispurchaseBuy, hasTitle Risk.**
    So you have to make sure you don't have a ticket before you buy it.; After buying, confirm that the status meets expectations.
  """
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
    log_info("[" + label + "] has in feature tickets: " + str(len(held)) + " Zhang")
    return held


def parse_args(argv):
    opts = {"qr": "", "charge_id": 5, "send": False, "list": False,
            "debug": False, "skip_entry": False, "wait_before": 30.0}
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
        elif a == "--wait-before" and i + 1 < len(argv):
            opts["wait_before"] = float(argv[i + 1])
            i += 1
        elif a == "--charge-id" and i + 1 < len(argv):
            opts["charge_id"] = int(argv[i + 1])
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

    setup_logging("buy_ticket")
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---- -- Earliest pre-check: thisticketsCurrent**Is it on the shelf?** ----
        #  - GetGameChargeApi No login required (user_id=0), So put in **before**,
        #   Exit if unsatisfied — Don't waste QR codes, Nor does it generate any login sessions.
        #  Basis TicketManager. cs:137-150: real machineAlsoOnlyBuy GetGameChargeApi Tickets listed.
        shop = GetGameCharge().get("gameChargeList") or []
        avail = [int(g.get("chargeId")) for g in shop
                 if isinstance(g, dict) and g.get("chargeId") is not None]
        log_info("Currently Available for Purchase chargeId:" + str(avail))
        for g in shop:
            log_info("  chargeId=" + str(g.get("chargeId"))
                     + " " + ticket_name(g.get("chargeId"))
                     + " money price=" + str(g.get("price"))
                     + " has " + str(g.get("startDate")) + " ~ " + str(g.get("endDate")))
        if opts["charge_id"] not in avail:
            log_error("chargeId=" + str(opts["charge_id"])
                      + "(" + ticket_name(opts["charge_id"])
                      + ")**Not in current purchasable list** — loginallDon't, directlyout.")
            log_error(" Reason: server response. notUpofMeetings returnCode=0(Measured).")
            log_error(" If you want to buy, please use the chargeId:" + str(avail))
            return 4

        # ---- - Heartbeat: Decide on all subsequent requests number Head ----
        #  real machineSequencein Ping at [11], It is. GetUserPreviewApi [12].
        #  If you don't run number Constantly "0"(real machine is 75).
        Ping()

        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        preview = GetUserPreview(user_id, token)
        if preview.isLogin:
            log_error("placeinAlreadyloginpleaseFirstatmachine statelogoutorwaitSessiontime")
            return 2

        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- - Reproduction of the real machine"Admission"Sequence: loginAfterFirstputuserdataFull Amountone ----
        #  real machine 13:19:45 login -> 13:19:46~13:19:51 47 nodes
        #    -> 13:20:10 Talented UpsertUserChargelogApi
        #  scriptHara login Buy directly after, skipthisOne
        if not opts["skip_entry"]:
            snap = GetNeedUserData(user_id, token=token,
                                         place_id=PLACE_ID, region_id=REGION_ID)
            _sum = summarize_snapshot(snap)
            log_info("Admission data download complete:" + str(len(_sum)) + " nodes, Failed "
                     + str(len(snap.get("_failed") or [])) + " Piece")

        # ---- -- ago: Must confirm current account**none**hasfeature tickets ----
        held_before = show_charges(user_id, "purchaseBuyago")

        aborted = False
        if held_before:
            log_error("current feature tickets held,**purchaseBuy**(purchaseBuyhasTitle Risk):")
            for c in held_before:
                log_error("  chargeId=" + str(c.get("chargeId"))
                          + " " + ticket_name(c.get("chargeId"))
                          + " stock=" + str(c.get("stock"))
                          + " validDate=" + str(c.get("validDate")))
            log_error("pleaseFirstatmachine stateputuseor wait until it expires.")
            aborted = True
        else:
            # ---- - Wait before buying a ticket(real machinereal machine login 13:19:45 -> Buy tickets 13:20:10,25s)----
            if opts["wait_before"] > 0:
                log_info("Wait before buying a ticket " + str(opts["wait_before"]) + " seconds...")
                time.sleep(opts["wait_before"])
                log_info("wait Start your purchase")

            # ---- purchaseBuy ----
            # - One function, done.: Pick up current ticket/file -> Security check -> calculate validDate/price -> -> Packaging
            UpsertUserChargelog(
                user_id, opts["charge_id"], login.loginDateTime,
                dry_run=not opts["send"],
                confirm=opts["send"],
                guard_no_stock=True,
                place_id=PLACE_ID, region_id=REGION_ID,
            )

        # ---- -- after: nohasnonePackaging, allAgaincheckOnce ----
        #  (Also check when aborting,)
        held_after = show_charges(user_id, "purchaseBuyAfter")

        if aborted:
            log_info("Aborted by security check, **not Packaging**; Above are the results of the post-abort review")
            if len(held_after) == len(held_before):
                log_info("Review and confirm: nothairVariation ✅")
            else:
                log_warning("Review found that the number of tickets has changed — please")
            return 3

        if not opts["send"]:
            log_info("[dry-run] not Packaging. If you want to make an actual purchase, please add --send (will be written to the purchase history)")
            return 0
        if held_after:
            log_info("purchaseBuyAfter has " + str(len(held_after)) + " tickets (purchaseBuySuccess)")
        else:
            log_warning("purchaseBuyAfternonechecktohasin — servercanpost-upload,"
                        "or tickets were immediately consumed")
        return 0

    except ChargelogGuardError:
        return 3
    except SystemExit:
        raise
    except ChargelogConfirmError:
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
