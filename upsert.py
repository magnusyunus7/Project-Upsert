#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upsert.py —— 主脚本：扫码登录 → 上传成绩 → 登出
================================================================================

整条流程只有四步，而且**一行日志都不用自己写** ——
每个 api 函数被调用时会自动打印：

    === UserLogin 开始运行 ===
      [接口说明] 用户正式登录（开启本次登录会话）。
      [位置参数] 12345678, 'iUfgRmjr...'
      [关键字参数] region_id=1, place_id=1000
    === UserLogin 运行结束 ===

日志模式改 config.py 一行：

    LOG_LEVEL = "info"     只展示 api 脚本的运行情况和结果
    LOG_LEVEL = "debug"    额外展示向 api 发送的数据与 api 返回的数据

日志文件（两种同时写）：

    logs/latest.log        只含**当次**主脚本运行（下次覆盖）
    logs/YYYY-MM-DD.log    存放**当日**产生的所有日志（追加）

--------------------------------------------------------------------------------
用法
--------------------------------------------------------------------------------
    python upsert.py <二维码>                       # 预检：登录 + 抓快照 + 组包，不发包
    python upsert.py <二维码> --send                # 真实上传成绩（★ 有副作用，不可撤销）
    python upsert.py <二维码> --send --debug        # 同上，日志里带完整收发报文
    python upsert.py <二维码> --send --cooldown 0   # 跳过发包前的 60 秒冷却
    python upsert.py <二维码> --send --no-verify    # 跳过上传后的落库回查

--------------------------------------------------------------------------------
★ UpsertUserAll 一个函数就把整条结算链路跑完了
--------------------------------------------------------------------------------
    1. 抓基线快照（没传 snapshot 时自动抓，用 token）
    2. 从快照推本局 5 只角色（游玩前等级）
    3. 构造本局成绩明细 userPlaylogList
    4. 调前置接口 GetUserNewItemListApi
    5. 组装 upsertUserAll 的 36 个节点（快照基线 + 本局演算 + 差分）
    6. 合并 extra_data 里的外部 JSON
    7. 发包前自检
    8. 冷却 -> 真实发包
    9. 落库回查（重新拉服务器数据，确认真的写进去了）

想额外塞几个节点（比如本局拿到的新 KaleidxScope 门）就传 extra_data：

    UpsertUserAll(
        user_id, login.loginId,
        login_date_time=login.loginDateTime,
        auth_date_time=login.dateTime,
        token=token,
        extra_data={
            "userKaleidxScopeList": [{"gateId": 1, "isGateFound": True, ...}],
            "isNewKaleidxScopeList": "1",
        },
        confirm=True,
    )

extra_data 接受 dict / JSON 字符串 / JSON 文件路径；
键必须是 36 个节点之一，没给位串时会按数组长度自动补并给出提示。
"""

from __future__ import annotations

import sys

from api import (
    setup_logging,
    teardown_logging,
    log_error,
    ParseQRCode,
    UserPreview,
    UserLogin,
    UserLogout,
    LogoutType,
    UpsertUserAll,
    ConfirmRequiredError,
)
from config import PLACE_ID, REGION_ID


def parse_args(argv):
    """极简命令行解析：第一个非 -- 开头的参数是二维码。"""
    opts = {"qr": "", "send": False, "debug": False, "no_verify": False, "cooldown": None}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--send":
            opts["send"] = True
        elif a == "--debug":
            opts["debug"] = True
        elif a == "--no-verify":
            opts["no_verify"] = True
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

    # --debug 只影响本次运行，不改 config.py
    if opts["debug"]:
        import config as _cfg
        _cfg.LOG_LEVEL = "debug"

    # 日志会话：开头一句。之后每次 api 调用都会自动记录，主脚本不用再写日志
    setup_logging("upsert")

    # 会话状态：保证异常时也能登出（否则账号会卡在 isLogin=True，下次登录 returnCode=100）
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        # ---- 扫码：二维码 -> userId + token ----
        user_id, token = ParseQRCode(opts["qr"])
        session.update(user_id=user_id, token=token)

        # ---- 预览：顺便挡住「账号已在游戏中」的情况，避免顶号 ----
        preview = UserPreview(user_id, token)
        if preview.isLogin:
            log_error("账号处于已登录状态，请先在机台登出或等待会话超时")
            return 2

        # ---- 登录：拿到 playlogId 与 loginDateTime（结算上报要用）----
        login = UserLogin(user_id, token, region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ---- 结算：★ 一个函数搞定构造 + 发包 + 落库回查 ----
        UpsertUserAll(
            user_id, login.loginId,
            login_date_time=login.loginDateTime,
            auth_date_time=login.dateTime,
            token=token,
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
        # 兜底登出：登录过且还没登出就释放会话，否则账号卡在 isLogin=True
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
