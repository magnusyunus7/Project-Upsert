#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
use_ticket.py —— 消耗账号当前持有的功能券（用 UpsertUserAll 表达「用票打了一局」）
================================================================================

一条完整的「用票」链路：

    ParseQRCode -> GetUserPreview -> UserLogin -> GetUserCharge
      -> GetNeedUserData（基线快照）-> UpsertUserAll -> GetUserCharge（复查）-> UserLogout

--------------------------------------------------------------------------------
★ 为什么可以用 UpsertUserAll 消耗票券
--------------------------------------------------------------------------------
    GetUserChargeApi 与 UpsertUserAllApi 里的 userChargeList **格式完全相同**
    （UserCharge.cs：chargeId / stock / purchaseDate / validDate），
    所以只要把 UpsertUserAll 的 userChargeList 节点改成「该票 stock - 1」，
    服务端就会认为这张票被这一局用掉了。

    真机实证（gamehook 抓包 2026-10-06 22:23 那一局，正好用了 2 倍券）：

        userChargeList: [
          {"chargeId":2,"stock":0,...},   <- 买来时是 1，本局用掉变成 0
          {"chargeId":3,"stock":0,...},
          {"chargeId":5,"stock":0,...}
        ]
        userGamePlaylogList[0].useTicketId = 2      <- ★ 用了哪张票
        userGamePlaylogList[0].playCredit  = 2      <- ★ 本局消耗的 credit
        userPlaylogList[0].playCredit      = 2
        userData.lastPlayCredit            = 2

    ★ playCredit 的算法（source/.../Net.VO.Mai2/VOExtensions.cs:838-845）：

        playCredit = Credit.GameCostEnoughPlay()          // 投币数，普通局 = 1
                   + TicketManager.GetTicketCredit(ticketId)  // 票的 creditNum

      2 倍券的 creditNum = 1 -> playCredit = 1 + 1 = 2  （与真机抓包一致）
      creditNum 表见 config.TICKET_CREDIT_NUM。

    ★ 真机报文里**没有** isNewChargeList 这个节点（它不在 36 个节点里），
      所以这里也不需要给位串。

--------------------------------------------------------------------------------
用法
--------------------------------------------------------------------------------
    python use_ticket.py <二维码>                          # 预检：只看报文，不发包
    python use_ticket.py <二维码> --list                   # 只列当前持有的票，不消耗
    python use_ticket.py <二维码> --ticket-id 2            # 指定要消耗哪张（默认第一张持有的）
    python use_ticket.py <二维码> --ticket-id 2 --send     # ★ 真实消耗
    python use_ticket.py <二维码> --send --music-id 143 --level 4
    python use_ticket.py <二维码> --send --skip-entry      # 跳过入场数据下载

★ 消耗会写入服务器（不可撤销）。不传 --send 时只构造报文。
★ 二维码**有效期 10 分钟**。
★ 账号当前**没有**持有功能票时直接拒绝（没有可消耗的东西）。
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
)
from config import (
    PLACE_ID,
    REGION_ID,
    PLAY_MUSIC_ID,
    PLAY_MUSIC_LEVEL,
    PLAY_CREDIT,
    TICKET_CREDIT_NUM,
)


def read_charges(user_id, label):
    """调 GetUserChargeApi，打印票券状态并返回 (全部, 持有的)。"""
    raw = GetUserCharge(user_id)
    lst = (raw.get("userChargeList") if isinstance(raw, dict) else None) or []
    log_info("[" + label + "] 当前票券 " + str(len(lst)) + " 条：")
    if not lst:
        log_info("    （空）")
    for c in lst:
        cid = c.get("chargeId")
        stock = int(c.get("stock", 0) or 0)
        log_info("    chargeId=" + str(cid) + " " + ticket_name(cid)
                 + "  stock=" + str(stock)
                 + "  purchaseDate=" + str(c.get("purchaseDate"))
                 + "  validDate=" + str(c.get("validDate"))
                 + ("   ← ★ 持有中" if stock > 0 else ""))
    held = [c for c in lst if isinstance(c, dict) and int(c.get("stock", 0) or 0) > 0]
    log_info("[" + label + "] 持有中的功能票：" + str(len(held)) + " 张")
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
        # ---- 心跳：决定后续所有请求的 number 头 ----
        Ping()

        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        preview = GetUserPreview(user_id, token)
        if preview.isLogin:
            log_error("账号处于已登录状态，请先在机台登出或等待会话超时")
            return 2

        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- ★ 读当前持有的功能券 ----
        all_charges, held = read_charges(user_id, "消耗前")

        if opts["list"]:
            log_info("--list：只列票券，不做任何写操作")
            return 0

        if not held:
            log_error("账号当前**没有持有任何功能票**，没有可消耗的东西。")
            log_error("  想买票请用 buy_ticket.py；已持有的票会在 userChargeList 里 stock > 0。")
            return 4

        # ---- 选定目标票 ----
        target = None
        if opts["ticket_id"] is not None:
            for c in held:
                if int(c.get("chargeId", -1)) == int(opts["ticket_id"]):
                    target = c
                    break
            if target is None:
                log_error("指定的 chargeId=" + str(opts["ticket_id"])
                          + " 当前并不持有；持有的有："
                          + ", ".join(str(c.get("chargeId")) for c in held))
                return 4
        else:
            target = held[0]

        ticket_id = int(target.get("chargeId"))
        credit_num = int(TICKET_CREDIT_NUM.get(ticket_id, 0) or 0)
        play_credit = int(PLAY_CREDIT) + credit_num

        log_info("选定要消耗的票：chargeId=" + str(ticket_id) + " " + ticket_name(ticket_id)
                 + "  stock=" + str(target.get("stock"))
                 + "  creditNum=" + str(credit_num)
                 + "  -> playCredit=" + str(PLAY_CREDIT) + "+" + str(credit_num)
                 + "=" + str(play_credit))

        # ---- ★ 构造新的 userChargeList：目标票 stock - 1，其余原样 ----
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
                log_info("    userChargeList 里 chargeId=" + str(ticket_id)
                         + " 的 stock：" + str(target.get("stock")) + " -> " + str(new_stock))
            new_list.append(item)

        # ---- 入场数据下载（贴近真机节奏，同时也是 UpsertUserAll 的基线快照）----
        snapshot = None
        if not opts["skip_entry"]:
            snapshot = GetNeedUserData(user_id, token=token,
                                       place_id=PLACE_ID, region_id=REGION_ID)
            _sum = summarize_snapshot(snapshot)
            log_info("入场数据下载完成：" + str(len(_sum)) + " 个节点，失败 "
                     + str(len(snapshot.get("_failed") or [])) + " 个")

        # ---- ★ 用 UpsertUserAll 表达「用这张票打了一局」----
        #   play.use_ticket_id -> userGamePlaylogList[0].useTicketId
        #   play.play_credit   -> userGamePlaylogList[0].playCredit / userPlaylogList[].playCredit
        #                         / userData.lastPlayCredit
        #   extra_data.userChargeList -> 覆盖节点，把票的 stock 减 1
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

        # ---- ★ 复查：票券 stock 应该减 1 ----
        _, held_after = read_charges(user_id, "消耗后")
        if not opts["send"]:
            log_info("[dry-run] 未发包。想真实消耗请加 --send（★ 会写入服务器）")
            return 0

        still = [c for c in held_after if int(c.get("chargeId", -1)) == ticket_id]
        if still:
            log_warning("chargeId=" + str(ticket_id) + " 仍然持有（stock="
                        + str(still[0].get("stock")) + "）—— 服务端可能没落库")
            return 6
        log_info("★ 票券已消耗：chargeId=" + str(ticket_id) + " 不再持有 ✅")
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
