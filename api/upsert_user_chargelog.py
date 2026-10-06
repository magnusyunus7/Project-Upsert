# -*- coding: utf-8 -*-
r"""
upsert_user_chargelog.py —— 购买功能票 / 上传购买记录（UpsertUserChargelogApi）
================================================================================

功能：把「买了一张功能票」这件事上报给服务器，并把该票的持有数 +1。

对应接口：UpsertUserChargelogApi
请求体  ：UserChargelogRequestVO（4 字段，顺序照 C# 声明）
          source/Assembly-CSharp/Net.VO.Mai2/UserChargelogRequestVO.cs
              public ulong userId;
              public UserChargelog userChargelog;
              public GetUserCharge userCharge;
              public long loginDateTime;
响应    ：{returnCode, apiName}

--------------------------------------------------------------------------------
一、真机的购买流程（源码逐行可查）
--------------------------------------------------------------------------------
    Manager/TicketManager.cs:130  UseTicketPrepare(playerId, ticketId)
        ├─ ticket.ticketKind.id == 1（付费票）
        ├─ 从 OperationManager.GetGameChargeDataList() 找该 chargeId 的 price
        │     （= GetGameChargeApi 的响应）
        ├─ TicketManager.cs:207  SetBuyPaidTicketData(playerId, ticketId)
        │     ├─ ChargeList 里已有该 chargeId -> stock++、更新 purchaseDate / validDate
        │     └─ 没有                      -> 新增一条 stock=1
        └─ TicketManager.cs:234  RequestUserCharge(playerId)
              ├─ VOExtensions.cs:436  ExportEnableUserCharge(ticketId)
              │     -> 取**购买后**（stock > 0）的那条 GetUserCharge
              ├─ VOExtensions.cs:403  ExportUserChargelog(ticketId)
              │     -> chargeId = ticketId
              │        price    = DataManager.GetTicket(ticketId).creditNum   ★ 不是 money price
              │        purchaseDate = TimeManager.GetNowDateString()
              │        playCount    = 玩家总游玩次数
              │        playerRating = 玩家 Rating
              │        placeId / regionId / clientId = 当前机台
              └─ 发 UpsertUserChargelogApi

    ★ 成功后 TicketManager.cs:255 RequestSuccess 会把本地 stock 再 --，
      因为那张票马上就被这一局用掉了。本模块只负责「买」，
      所以默认传的是**购买后**的库存（现有 + 1）。

--------------------------------------------------------------------------------
二、票的有效期算法
--------------------------------------------------------------------------------
    Manager/TicketManager.cs:564
        DateTime.Now.AddHours(-4.0).AddDays(90.0).ToString("yyyy-MM-dd 04:00:00")

    真机验证（source/2026-10-05.log:123 的 userChargeList）：
        chargeId=5  purchaseDate="2026-10-04 18:22:10"
                    -> 减 4 小时 = 10-04 14:22，加 90 天 = 2027-01-02
                    -> validDate="2027-01-02 04:00:00"  ✅ 完全吻合

--------------------------------------------------------------------------------
三、ticket.creditNum 从哪来
--------------------------------------------------------------------------------
    游戏本地主数据：
        <游戏目录>\Sinmai_Data\StreamingAssets\A000\ticket\ticketXXXXXX\Ticket.xml
    已抄进 config.TICKET_CREDIT_NUM（付费票 2/3/4/5/6 -> creditNum 1/2/3/4/5）。

--------------------------------------------------------------------------------
四、安全闸门
--------------------------------------------------------------------------------
    本接口会**真实写入一条购买记录**，所以默认不发包：
        UpsertUserChargelog(...)                   -> 抛 ChargelogConfirmError
        UpsertUserChargelog(..., dry_run=True)     -> 只构造报文
        UpsertUserChargelog(..., confirm=True)     -> 真实发送
    全局开关：config.UPSERT_CHARGELOG_CONFIRM（默认 False）

--------------------------------------------------------------------------------
五、调用示例
--------------------------------------------------------------------------------
    from api import setup_logging, ParseQRCode, UserLogin, UserLogout,
                     LogoutType, UpsertUserChargelog

    setup_logging("买票")
    user_id, token = ParseQRCode(qr)
    login = UserLogin(user_id, token)
    UpsertUserChargelog(user_id, 2, login.loginDateTime, confirm=True)
    UserLogout(user_id, token, login.loginDateTime, logout_type=LogoutType.TestIn)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import config
from config import (
    CLIENT_ID,
    PLACE_ID,
    REGION_ID,
    TICKET_CREDIT_NUM,
    TICKET_NAMES,
    TICKET_VALID_DAYS,
    TICKET_VALID_HOUR_OFFSET,
    TIMEOUT_MS,
    UPSERT_CHARGELOG_CONFIRM,
)

from .log_setup import log_debug, log_error, log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict
from .upsert_user_all import UpsertResponseVO, resolve_api_func


class ChargelogConfirmError(RuntimeError):
    """有副作用的接口被安全闸门拦下（此时**未发包**）。"""


class ChargelogGuardError(RuntimeError):
    """
    安全检查未通过（此时**未发包**）。

    ★ 目前唯一的触发条件：**账号当前已经持有功能票**。

      真机行为：`UseTicketPrepare` 只在「本局要用这张票」时才走购买分支，
      而一张票买到手后会立刻被本局用掉（`RequestSuccess` 里 stock--）。
      所以正常状态下 `userChargeList` 里的 stock 全是 0。

      如果账号**已经持有**一张功能票还去发购买请求，
      服务端看到的是「重复购买 / 状态矛盾」，有**封号风险**。
      所以本模块默认硬拦。
    """


# =============================================================================
# 一、VO（字段顺序照 source/Assembly-CSharp/Net.VO.Mai2/*.cs 声明）
# =============================================================================

@dataclass
class UserChargeVO:
    """GetUserCharge —— 一张票的持有状态（GetUserCharge.cs，4 字段）。"""
    chargeId: int = 0
    stock: int = 0
    purchaseDate: str = ""
    validDate: str = ""


@dataclass
class UserChargelogVO:
    """UserChargelog —— 一条购买记录（UserChargelog.cs，8 字段）。"""
    chargeId: int = 0
    price: int = 0
    purchaseDate: str = ""
    playCount: int = 0
    playerRating: int = 0
    placeId: int = 0
    regionId: int = 0
    clientId: str = ""


@dataclass
class UserChargelogRequestVO:
    """请求 VO（UserChargelogRequestVO.cs，4 字段，顺序照声明）。"""
    userId: int
    userChargelog: UserChargelogVO
    userCharge: UserChargeVO
    loginDateTime: int = 0


# =============================================================================
# 二、工具
# =============================================================================

def ticket_name(charge_id: int) -> str:
    """取票名（只用于日志）。"""
    return TICKET_NAMES.get(int(charge_id), "未知票(" + str(charge_id) + ")")


def ticket_price(charge_id: int, override: Optional[int] = None) -> int:
    """
    取 userChargelog.price —— 即 ticket.creditNum。

    依据 VOExtensions.cs:410  result.price = ticket.creditNum;
    数据来源 config.TICKET_CREDIT_NUM（抄自游戏 Ticket.xml）。
    """
    if override is not None:
        return int(override)
    if int(charge_id) not in TICKET_CREDIT_NUM:
        log_warning("config.TICKET_CREDIT_NUM 里没有 chargeId=" + str(charge_id)
                    + " —— 按 0 处理，建议补进配置")
        return 0
    return int(TICKET_CREDIT_NUM[int(charge_id)])


#: 北京时间（CST = UTC+8）
#:   依据 Manager/TimeManager.cs:9  CSToffset = new TimeSpan(8, 0, 0)
CST = timezone(timedelta(hours=8))


def now_cst(now: Optional[datetime] = None) -> datetime:
    """
    取「北京时间现在」；传了 now 就用它（视作已是北京时间）。

    ★ 为什么要显式 +8 而不是 datetime.now()：
        TimeManager.GetNowTime() 返回 **DateTime.UtcNow**，
        GetDateString() 再 Add(CSToffset) —— 即游戏里的日期串**恒是北京时间**，
        与本机时区无关。脚本跑在非东八区机器上时 datetime.now() 会错。
    """
    if now is not None:
        return now
    return datetime.now(timezone.utc).astimezone(CST)


def _now_string(now: Optional[datetime] = None) -> str:
    """
    TimeManager.GetNowDateString() 的等价物。

    依据 Manager/TimeManager.cs:7,62-70：
        DateTimeFormat = "yyyy-MM-dd HH:mm:ss.f"
        GetDateString(unix) = GetDateTime(unix).ToString("yyyy-MM-dd HH:mm:ss.f")

    ★★ 注意末尾那个 **.f**（一位小数）—— 真机报文长这样：
           "purchaseDate":"2026-10-06 13:20:10.0"
       少写这个 ".0" 服务端会直接 returnCode=0（实测踩过）。
       ★ 而 validDate 用的是另一套格式（见 calc_valid_date），**不带**小数。
    """
    d = now_cst(now)
    return d.strftime("%Y-%m-%d %H:%M:%S") + "." + str(d.microsecond // 100000)


def calc_valid_date(
    now: Optional[datetime] = None,
    *,
    hour_offset: int = TICKET_VALID_HOUR_OFFSET,
    days: int = TICKET_VALID_DAYS,
) -> str:
    """
    算票的有效期字符串。

    依据 TicketManager.cs:562-565：
        DateTime.Now.AddHours(-4.0).AddDays(90.0).ToString("yyyy-MM-dd 04:00:00")

    ★ 注意这里用的是**显式格式串**（没有 .f），所以结果形如
      "2027-01-04 04:00:00" —— 与 purchaseDate 的 "…10.0" 不同。
    """
    base = now_cst(now)
    d = (base + timedelta(hours=hour_offset) + timedelta(days=days)).date()
    return d.strftime("%Y-%m-%d") + " 04:00:00"


def parse_wall_time(text: Any) -> Optional[datetime]:
    """
    解析墙上时间串，兼容两种格式：

        "2026-10-06 13:20:10.0"   ← TimeManager.DateTimeFormat（一位小数，真机报文用这个）
        "2026-10-06 13:20:10"     ← 无小数（服务端回给 GetUserChargeApi 的是这个）

    解析不出来返回 None。
    """
    s = str(text or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _find_charge(charge_list: Any, charge_id: int) -> Optional[Dict[str, Any]]:
    """在 GetUserChargeApi 的 userChargeList 里找指定 chargeId。"""
    if not isinstance(charge_list, list):
        return None
    for c in charge_list:
        if isinstance(c, dict) and int(c.get("chargeId", -1) or -1) == int(charge_id):
            return c
    return None


# =============================================================================
# 三、主函数
# =============================================================================

def UpsertUserChargelog(
    user_id: int,
    charge_id: int,
    login_date_time: int,
    *,
    charge_list: Optional[List[Dict[str, Any]]] = None,
    game_charge_list: Optional[List[Dict[str, Any]]] = None,
    user_data: Optional[Dict[str, Any]] = None,
    stock: Optional[int] = None,
    price: Optional[int] = None,
    purchase_date: Optional[str] = None,
    valid_date: Optional[str] = None,
    play_count: Optional[int] = None,
    player_rating: Optional[int] = None,
    place_id: int = PLACE_ID,
    region_id: int = REGION_ID,
    client_id: str = CLIENT_ID,
    guard_no_stock: bool = True,
    guard_purchasable: bool = True,
    confirm: Optional[bool] = None,
    dry_run: bool = False,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> Union[UserChargelogRequestVO, UpsertResponseVO]:
    """
    购买一张功能票（UpsertUserChargelogApi，★ 有副作用）。

    参数：
        user_id:         用户 ID（必填）
        charge_id:       要买的票 ID（必填，= GetGameChargeApi 里的 chargeId）
                         ★ 付费票是 2/3/4/5/6（config.PAID_TICKET_IDS）
        login_date_time: 登录时刻（必填，★ 必须 == UserLoginApi 的 loginDateTime）
        charge_list:     当前票券列表（可选）。不传则自动调 GetUserChargeApi。
                         用来算「购买后库存」和是否已有该票。
        user_data:       当前 userData（可选）。不传则自动调 GetUserDataApi。
                         用来填 playCount / playerRating。
        stock:           ★ 购买后该票的库存；不传 = 现有 + 1
        price:           ★ userChargelog.price；不传 = config.TICKET_CREDIT_NUM[charge_id]
        purchase_date:   购买时刻字符串；不传 = 现在
        valid_date:      有效期字符串；不传 = 现在-4h+90d（见 calc_valid_date）
        play_count:      覆盖 playCount（不传则取 userData.playCount）
        player_rating:   覆盖 playerRating（不传则取 userData.playerRating）
        guard_purchasable: ★ 默认 True = **只允许买 GetGameChargeApi 列出来的票**
                         （不在清单里就抛 ChargelogGuardError，未发包）。
                         依据 TicketManager.cs:137-150 —— 真机也是先在
                         GetGameChargeDataList() 里找到该 chargeId 才发购买请求，
                         找不到直接 return false。服务端对未上架的票会 returnCode=0。
                         实测：本机台只上架 chargeId=2/3，买 5 会失败。
        game_charge_list: 可购买清单（可选）。不传则自动调 GetGameChargeApi。
        guard_no_stock:  ★ 默认 True = **账号当前若已持有任何功能票就直接拒绝购买**
                         （抛 ChargelogGuardError，未发包）。
                         理由见 ChargelogGuardError 的 docstring —— 有封号风险。
                         确认要强行购买才传 False。
        confirm:         副作用闸门；None 时取 config.UPSERT_CHARGELOG_CONFIRM
        dry_run:         True = 只构造并返回报文，绝不发包

    返回：
        dry_run=True  -> UserChargelogRequestVO
        dry_run=False -> UpsertResponseVO
    """
    if not login_date_time:
        raise ValueError("缺少 login_date_time：必须传 UserLoginApi 的 loginDateTime"
                         "（PacketUploadUserChargelog.cs:23）")

    name = ticket_name(charge_id)
    log_info("购买功能票：user_id=" + str(user_id) + " chargeId=" + str(charge_id)
             + "（" + name + "）dry_run=" + str(dry_run))

    if int(charge_id) not in tuple(config.PAID_TICKET_IDS):
        log_warning("chargeId=" + str(charge_id) + " 不在 config.PAID_TICKET_IDS="
                    + str(tuple(config.PAID_TICKET_IDS)) + " 里 —— 它可能不是可购买的付费票")

    # ---------- 1. 取当前状态 ----------
    if charge_list is None:
        log_info("未传 charge_list，自动抓取当前票券 ...")
        raw = resolve_api_func("GetUserCharge")(
            user_id, client_id=client_id, timeout_ms=timeout_ms, client=client)
        charge_list = (raw.get("userChargeList") if isinstance(raw, dict) else None) or []

    if user_data is None:
        log_info("未传 user_data，自动抓取当前档案 ...")
        raw_ud = resolve_api_func("GetUserData")(
            user_id, client_id=client_id, timeout_ms=timeout_ms, client=client)
        user_data = (raw_ud.get("userData") if isinstance(raw_ud, dict) else None) or {}

    # ---------- 1.4 ★ 安全检查：这张票当前**上架了吗** ----------
    #   依据 TicketManager.cs:137-150：真机先在 GetGameChargeDataList() 里找该
    #   chargeId，找到才 RequestUserCharge，找不到直接 return false（不买）。
    #   服务端对未上架的票会 returnCode=0 —— 实测买 chargeId=5 就是这种情况。
    if guard_purchasable:
        if game_charge_list is None:
            log_info("未传 game_charge_list，自动抓取可购买清单 ...")
            _gc = resolve_api_func("GetGameCharge")(
                client_id=client_id, timeout_ms=timeout_ms, client=client)
            game_charge_list = (_gc.get("gameChargeList")
                                if isinstance(_gc, dict) else None) or []
        avail = [int(g.get("chargeId")) for g in (game_charge_list or [])
                 if isinstance(g, dict) and g.get("chargeId") is not None]
        log_info("当前可购买 chargeId：" + str(avail))
        if int(charge_id) not in avail:
            msg = ("安全检查未通过：chargeId=" + str(charge_id) + "（" + name
                   + "）**不在当前可购买清单里**。\n"
                   "  可购买：" + (str(avail) if avail else "（空）") + "\n"
                   "  依据 TicketManager.cs:137-150 —— 真机也只买 GetGameChargeApi\n"
                   "  列出来的票，找不到就不发购买请求。\n"
                   "  服务端对未上架的票会 returnCode=0（实测过）。\n"
                   "  确需强行购买请传 guard_purchasable=False。")
            log_error(msg)
            raise ChargelogGuardError(msg)
        log_info("安全检查通过：chargeId=" + str(charge_id) + " 在可购买清单里")

    # ---------- 1.5 ★ 安全检查：账号当前是否已持有功能票 ----------
    held = [c for c in (charge_list or [])
            if isinstance(c, dict) and int(c.get("stock", 0) or 0) > 0]
    if held:
        desc = "、".join(
            "chargeId=" + str(c.get("chargeId")) + "(" + ticket_name(c.get("chargeId"))
            + ") stock=" + str(c.get("stock")) + " validDate=" + str(c.get("validDate"))
            for c in held)
        log_warning("★ 账号当前已持有 " + str(len(held)) + " 张功能票：" + desc)
        if guard_no_stock:
            msg = ("安全检查未通过：账号当前**已持有功能票**（" + desc + "），拒绝再次购买。\n"
                   "  原因：真机只在「本局要用这张票」时才购买，且买到手会立刻用掉"
                   "（stock--），正常状态 stock 恒为 0。\n"
                   "  已经持票还发购买请求，服务端看到的是重复购买，有**封号风险**。\n"
                   "  确需强行购买请传 guard_no_stock=False。")
            log_error(msg)
            raise ChargelogGuardError(msg)
        log_warning("guard_no_stock=False —— 已跳过该检查，继续购买")
    else:
        log_info("安全检查通过：账号当前没有持有任何功能票")

    existing = _find_charge(charge_list, charge_id)
    old_stock = int(existing.get("stock", 0) or 0) if existing else 0
    if stock is None:
        stock = old_stock + 1
    stock = int(stock)

    if price is None:
        price = ticket_price(charge_id)
    price = int(price)

    if play_count is None:
        play_count = int(user_data.get("playCount", 0) or 0)
    if player_rating is None:
        player_rating = int(user_data.get("playerRating", 0) or 0)

    now = now_cst()
    if not purchase_date:
        purchase_date = _now_string(now)
    if not valid_date:
        # ★ 真机里 purchaseDate 与 validDate 都来自同一个 DateTime.Now
        #   （TicketManager.cs:216-219 与 :564），所以调用方若显式给了 purchaseDate，
        #   有效期就该从**那个时刻**推，而不是从现在推。
        base = parse_wall_time(purchase_date)
        if base is None:
            log_warning("purchase_date 解析不了（应为 'YYYY-MM-DD HH:MM:SS[.f]'），"
                        "validDate 改按「现在」计算：" + str(purchase_date))
            base = now
        valid_date = calc_valid_date(base)

    log_info("  票名        : " + name)
    log_info("  库存        : " + str(old_stock) + " -> " + str(stock))
    log_info("  price       : " + str(price) + "（= ticket.creditNum）")
    log_info("  purchaseDate: " + purchase_date)
    log_info("  validDate   : " + valid_date)

    # ---------- 2. 构造请求 ----------
    req = UserChargelogRequestVO(
        userId=int(user_id),
        userChargelog=UserChargelogVO(
            chargeId=int(charge_id),
            price=price,
            purchaseDate=purchase_date,
            playCount=int(play_count),
            playerRating=int(player_rating),
            placeId=int(place_id),
            regionId=int(region_id),
            clientId=client_id,
        ),
        userCharge=UserChargeVO(
            chargeId=int(charge_id),
            stock=stock,
            purchaseDate=purchase_date,
            validDate=valid_date,
        ),
        loginDateTime=int(login_date_time),
    )

    # ---------- 3. dry-run ----------
    if dry_run:
        log_info("[dry-run] 已构造购买报文，未发包")
        log_debug("dry-run 报文：" + __import__("json").dumps(
            req, ensure_ascii=False, default=str))
        return req

    # ---------- 4. 副作用闸门 ----------
    effective = UPSERT_CHARGELOG_CONFIRM if confirm is None else bool(confirm)
    if not effective:
        msg = ("UpsertUserChargelogApi 会**真实写入一条购买记录**（不可撤销）。"
               "本脚本默认不放行。确认要发请传 confirm=True，"
               "或改 config.UPSERT_CHARGELOG_CONFIRM = True。"
               "只想看报文请传 dry_run=True。")
        log_error(msg)
        raise ChargelogConfirmError(msg)

    # ---------- 5. 发包 ----------
    log_info("闸门已放行，开始上传购买记录 ...")
    raw = request_dict(
        "UpsertUserChargelogApi", req,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )
    resp = UpsertResponseVO(
        returnCode=int(raw.get("returnCode", 0) or 0),
        apiName=str(raw.get("apiName", "") or ""),
    )
    if resp.returnCode != 1:
        msg = ("购买失败：returnCode=" + str(resp.returnCode)
               + " apiName=" + resp.apiName)
        log_error(msg)
        raise RuntimeError(msg)

    log_info("购买成功：returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName)
    log_info("  票名 " + name + " 库存 " + str(old_stock) + " -> " + str(stock))
    return resp


# =============================================================================
# 四、单独运行（调试）
# =============================================================================

if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("chargelog_test")
        try:
            log_info("构造一张 2 倍券的购买报文（不发包）")
            req = UpsertUserChargelog(
                12345678, 2, 1791159576,
                charge_list=[], user_data={"playCount": 1260, "playerRating": 15000},
                dry_run=True,
            )
            log_info("userChargelog = " + str(req.userChargelog))
            log_info("userCharge    = " + str(req.userCharge))
            log_info("validDate 算法自检：")
            log_info("  2026-10-04 18:22:10 买 5 倍券 -> "
                     + calc_valid_date(datetime(2026, 10, 4, 18, 22, 10))
                     + "（真机是 2027-01-02 04:00:00）")
            return 0
        finally:
            teardown_logging()

    raise SystemExit(_main())
