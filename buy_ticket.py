#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buy_ticket.py —— 主脚本范例：扫码登录 → 购买功能票 → 登出
================================================================================

一条完整的「买票」链路：

    ParseQRCode -> GetUserPreview -> UserLogin -> UpsertUserChargelog -> UserLogout

UpsertUserChargelog 内部会自动做这些事（所以主脚本不用管）：
    1. 调 GetUserChargeApi 取当前票券列表（算「购买后库存」）
    2. 调 GetUserDataApi 取 playCount / playerRating
    3. 按 TicketManager.cs:564 算 validDate（现在 -4h +90d，取日期补 04:00:00）
    4. 查 TICKET_CREDIT_NUM（已下沉到 api/upsert_user_chargelog.py）得到
   userChargelog.price（= ticket.creditNum）
    5. 闸门 → 发包

--------------------------------------------------------------------------------
用法
--------------------------------------------------------------------------------
    python buy_ticket.py <二维码>                        # 预检：只看报文，不发包
    python buy_ticket.py <二维码> --list                 # 只列当前票券和可买的票
    python buy_ticket.py <二维码> --charge-id 3          # 指定票（默认 5 = 5倍券）
    python buy_ticket.py <二维码> --charge-id 2 --send   # ★ 真实购买
    python buy_ticket.py <二维码> --charge-id 2 --send --debug
    python buy_ticket.py <二维码> --charge-id 2 --send --skip-entry   # 跳过入场数据下载

付费票（api.PAID_TICKET_IDS）：
    2 = 2倍チケット   creditNum 1
    3 = 3倍チケット   creditNum 2
    4 = 4倍チケット   creditNum 3
    5 = 5倍チケット   creditNum 4
    6 = 6倍チケット   creditNum 5

★ 真实购买会写入一条购买记录（不可撤销）。不传 --send 时只构造报文。

★ 二维码有**时效性**（**有效期 10 分钟**），过期后 aimedb 返回 errorID=2
  —— **不是按次数计量的**，重新生成即可。

★ 购买前会先查一次功能票；**账号已持有功能票时直接拒绝购买**（重复购买有封号风险）。
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
    ★ 调 GetUserChargeApi 打印当前票券状态，并返回 stock > 0 的那些。

    ★★ 为什么跑前跑后都要查：
        真机只在「本局要用这张票」时才购买，买到手会立刻被用掉（stock--），
        所以正常状态 stock 恒为 0。
        **已经持票还去买，服务端看到的是重复购买，有封号风险。**
        所以买之前必须确认没有持票；买之后要确认状态符合预期。
    """
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
        # ---- ★★ 最早的前置检查：这张票当前**上架了吗** ----
        #   ★ GetGameChargeApi 不需要登录（user_id=0），所以放在**扫码之前**，
        #     不满足就直接退出 —— 不浪费二维码，也不产生任何登录会话。
        #   依据 TicketManager.cs:137-150：真机也只买 GetGameChargeApi 列出来的票。
        shop = GetGameCharge().get("gameChargeList") or []
        avail = [int(g.get("chargeId")) for g in shop
                 if isinstance(g, dict) and g.get("chargeId") is not None]
        log_info("当前可购买 chargeId：" + str(avail))
        for g in shop:
            log_info("    chargeId=" + str(g.get("chargeId"))
                     + " " + ticket_name(g.get("chargeId"))
                     + "  money price=" + str(g.get("price"))
                     + "  有效期 " + str(g.get("startDate")) + " ~ " + str(g.get("endDate")))
        if opts["charge_id"] not in avail:
            log_error("chargeId=" + str(opts["charge_id"])
                      + "（" + ticket_name(opts["charge_id"])
                      + "）**不在当前可购买清单里** —— 连登录都不做，直接退出。")
            log_error("  原因：服务端对未上架的票会 returnCode=0（实测过）。")
            log_error("  想买请用清单里的 chargeId：" + str(avail))
            return 4

        # ---- ★ 心跳：决定后续所有请求的 number 头 ----
        #   真机序列里 Ping 在 [11]，紧接着才是 GetUserPreviewApi [12]。
        #   不跑的话 number 恒为 "0"（真机是 75）。
        Ping()

        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        preview = GetUserPreview(user_id, token)
        if preview.isLogin:
            log_error("账号处于已登录状态，请先在机台登出或等待会话超时")
            return 2

        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- ★ 复刻真机的「入场」序列：登录后先把用户数据全量拉一遍 ----
        #   真机 13:19:45 登录 -> 13:19:46~13:19:51 拉 47 个节点
        #        -> 13:20:10 才发 UpsertUserChargelogApi
        #   本脚本原来 login 后直接买，跳过了这一段。
        if not opts["skip_entry"]:
            snap = GetNeedUserData(user_id, token=token,
                                         place_id=PLACE_ID, region_id=REGION_ID)
            _sum = summarize_snapshot(snap)
            log_info("入场数据下载完成：" + str(len(_sum)) + " 个节点，失败 "
                     + str(len(snap.get("_failed") or [])) + " 个")

        # ---- ★★ 跑前：必须确认账号当前**没有**持有功能票 ----
        held_before = show_charges(user_id, "购买前")

        aborted = False
        if held_before:
            log_error("账号当前已持有功能票，**拒绝购买**（重复购买有封号风险）：")
            for c in held_before:
                log_error("    chargeId=" + str(c.get("chargeId"))
                          + " " + ticket_name(c.get("chargeId"))
                          + " stock=" + str(c.get("stock"))
                          + " validDate=" + str(c.get("validDate")))
            log_error("请先在机台把票用掉，或等它过期后再来。")
            aborted = True
        else:
            # ---- ★ 买票前等待（贴近真机节奏：真机 login 13:19:45 -> 买票 13:20:10，间隔 25s）----
            if opts["wait_before"] > 0:
                log_info("买票前等待 " + str(opts["wait_before"]) + " 秒 ...")
                time.sleep(opts["wait_before"])
                log_info("等待结束，开始购买")

            # ---- 购买 ----
            # ★ 一个函数搞定：取当前票券/档案 -> 安全检查 -> 算 validDate/price -> 闸门 -> 发包
            UpsertUserChargelog(
                user_id, opts["charge_id"], login.loginDateTime,
                dry_run=not opts["send"],
                confirm=opts["send"],
                guard_no_stock=True,
                place_id=PLACE_ID, region_id=REGION_ID,
            )

        # ---- ★★ 跑后：无论有没有真发包，都再查一次 ----
        #   （中止时也查，确认状态确实没被动过）
        held_after = show_charges(user_id, "购买后")

        if aborted:
            log_info("已按安全检查中止，**未发包**；上面是中止后的复查结果")
            if len(held_after) == len(held_before):
                log_info("复查确认：票券状态未发生变化 ✅")
            else:
                log_warning("复查发现票券数量变了 —— 请人工确认")
            return 3

        if not opts["send"]:
            log_info("[dry-run] 未发包。想真实购买请加 --send（★ 会写入购买记录）")
            return 0
        if held_after:
            log_info("购买后持有 " + str(len(held_after)) + " 张票（购买成功）")
        else:
            log_warning("购买后没有查到持有中的票 —— 服务端可能没落库，"
                        "或票被立刻消耗了")
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
                log_error("[收尾] 强制登出失败（会话可能需等待服务端超时）：" + str(exc))
        teardown_logging()


if __name__ == "__main__":
    sys.exit(main())
