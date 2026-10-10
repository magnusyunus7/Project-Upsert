# -*- coding: utf-8 -*-
r"""
upsert_user_chargelog.py —— purchaseBuyFeature Tickets / Upload purchase history（UpsertUserChargelogApi）
================================================================================

Features：put「Bought a feature ticket」thistextEscalate toserver，and the number of holdings of the ticket +1。

Corresponding interface：UpsertUserChargelogApi
request body  ：UserChargelogRequestVO（4 Field，ordertext C# Declaration）
          source/Assembly-CSharp/Net.VO.Mai2/UserChargelogRequestVO.cs
              public ulong userId;
              public UserChargelog userChargelog;
              public GetUserCharge userCharge;
              public long loginDateTime;
Response    ：{returnCode, apiName}

--------------------------------------------------------------------------------
One、real machineofpurchaseBuytext（source codetextcheck）
--------------------------------------------------------------------------------
    Manager/TicketManager.cs:130  UseTicketPrepare(playerId, ticketId)
        ├─ ticket.ticketKind.id == 1（Paid tickets）
        ├─ From OperationManager.GetGameChargeDataList() findthe chargeId of price
        │     （= GetGameChargeApi ofResponse）
        ├─ TicketManager.cs:207  SetBuyPaidTicketData(playerId, ticketId)
        │     ├─ ChargeList inExistingthe chargeId -> stock++、update purchaseDate / validDate
        │     └─ none                      -> addedOneitem stock=1
        └─ TicketManager.cs:234  RequestUserCharge(playerId)
              ├─ VOExtensions.cs:436  ExportEnableUserCharge(ticketId)
              │     -> Take**purchaseBuyAfter**（stock > 0）ofthatitem GetUserCharge
              ├─ VOExtensions.cs:403  ExportUserChargelog(ticketId)
              │     -> chargeId = ticketId
              │        price    = DataManager.GetTicket(ticketId).creditNum   ★ No money price
              │        purchaseDate = TimeManager.GetNowDateString()
              │        playCount    = textTotal Play Count
              │        playerRating = text Rating
              │        placeId / regionId / clientId = Current machine
              └─ hair UpsertUserChargelogApi

    ★ After successful TicketManager.cs:255 RequestSuccess will take the local stock Again --，
      Because that ticket was used up by this bureau right away.。textOnlytext「Buy」，
      So the default passing is**purchaseBuyAfter**ofInventory（currenthas + 1）。

--------------------------------------------------------------------------------
Two、textofhastextcalculatetext
--------------------------------------------------------------------------------
    Manager/TicketManager.cs:564
        DateTime.Now.AddHours(-4.0).AddDays(90.0).ToString("yyyy-MM-dd 04:00:00")

    real machinetext（source/2026-10-05.log:123 of userChargeList）：
        chargeId=5  purchaseDate="2026-10-04 18:22:10"
                    -> Subtract 4 Hours = 10-04 14:22，Plus 90 days = 2027-01-02
                    -> validDate="2027-01-02 04:00:00"  ✅ Exact match

--------------------------------------------------------------------------------
Three、ticket.creditNum Where did you come from?
--------------------------------------------------------------------------------
    textMaster Data：
        <text>\Sinmai_Data\StreamingAssets\A000\ticket\ticketXXXXXX\Ticket.xml
    copied TICKET_CREDIT_NUM（Paid tickets 2/3/4/5/6 -> creditNum 1/2/3/4/5）。

--------------------------------------------------------------------------------
Four、Safety gate
--------------------------------------------------------------------------------
    textinterfaceMeetings**realWriteA purchase history**，So no packing by default.：
        UpsertUserChargelog(...)                   -> raise ChargelogConfirmError
        UpsertUserChargelog(..., dry_run=True)     -> Construct only packets
        UpsertUserChargelog(..., confirm=True)     -> realSend
    Global Switch：config.UPSERT_CHARGELOG_CONFIRM（default False）

--------------------------------------------------------------------------------
Five、call exampleExample
--------------------------------------------------------------------------------
    from api import setup_logging, ParseQRCode, UserLogin, UserLogout,
                     LogoutType, UpsertUserChargelog

    setup_logging("Buy tickets")
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
    TIMEOUT_MS,
    UPSERT_CHARGELOG_CONFIRM,
)

# =============================================================================
# Feature Tickets（Ticket）Master Data（Originally at config.py，2026-10-06 sink to this module）
# =============================================================================
#
# Basis：textMaster Data
#         Sinmai_Data/StreamingAssets/A000/ticket/ticketXXXXXX/Ticket.xml
#       source codeSide Manager.MaiStudio.TicketData.creditNum
#
# ★ Why you need it：
#     UpsertUserChargelogApi（purchaseBuyFeature Tickets）of userChargelog.price Take is
#     **ticket.creditNum（textoftextusetexttimesnumber）**，No GetGameChargeApi inof money price：
#         source/Assembly-CSharp/Net.VO.Mai2/VOExtensions.cs:410
#             result.price = ticket.creditNum;
#
# ticketKind Meaning：1=Paid(Paid，Can be bought at the machine) 2=Event 3=Free 4=Link 5=ShopWeekly 6=ShopChara

#: chargeId -> creditNum
TICKET_CREDIT_NUM = {
    0: 0,
    2: 1, 3: 2, 4: 3, 5: 4, 6: 5,          # Paid tickets：N Coupon multiplier's creditNum = N-1
    10005: 0, 10105: 0, 10205: 0,           # text
    11001: 0,                               # Free 1.5 Ticket multiplier
    30001: 0, 30002: 0, 30003: 0,           # text / Store Tickets
}

#: textFirst name（For good-looking logs only，Does Not Affect Agreement）
TICKET_NAMES = {
    0: "Useしない",
    2: "2timesチケット", 3: "3timesチケット", 4: "4timesチケット", 5: "5timesチケット", 6: "6timesチケット",
    10005: "イベント5timesチケット_1", 10105: "イベント5timesチケット_2",
    10205: "イベント5timesチケット_3", 11001: "text1.5timesチケット",
    30001: "textチケット", 30002: "eachtextAreaagotext2Multiplier Tickets", 30003: "textleveltext5Multiplier Tickets",
}

#: Paid tickets（ticketKind=1）—— Only these can be purchased at the machine
PAID_TICKET_IDS = (2, 3, 4, 5, 6)

#: texthastextcalculatetextParameter
#:   Basis source/Assembly-CSharp/Manager/TicketManager.cs:564
#:        DateTime.Now.AddHours(-4.0).AddDays(90.0).ToString("yyyy-MM-dd 04:00:00")
#:   real machinetext：chargeId=5 of purchaseDate=2026-10-04 18:22:10
#:             -> Subtract 4 Hours = 10-04 14:22，Plus 90 days = 2027-01-02 -> "2027-01-02 04:00:00"
TICKET_VALID_HOUR_OFFSET = -4
TICKET_VALID_DAYS = 90

from .log_setup import log_debug, log_error, log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict
from .upsert_user_all import UpsertResponseVO, resolve_api_func


class ChargelogConfirmError(RuntimeError):
    """hasSide effectsofinterfacetextSafety gatetextDown（texttime**notPackaging**）。"""


class ChargelogGuardError(RuntimeError):
    """
    Security check failed（texttime**notPackaging**）。

    ★ textagoUniqueoftexthairitemtext：**textCurrentAlready heldFeature Tickets**。

      real machinetextfor：`UseTicketPrepare` Only in「this gamemustusethistickets」timeonlytextpurchaseBuyBranch，
      andOneticketsBuytotextAfterMeetingstextthis gameusetext（`RequestSuccess` in stock--）。
      So under normal conditions, `userChargeList` inof stock Yes to all 0。

      If the account**Already held**A feature ticket also sends a purchase request，
      servertexttoofis「textpurchaseBuy / text」，has**Title Risk**。
      So this module is hard blocked by default。
    """


# =============================================================================
# One、VO（Field order photo source/Assembly-CSharp/Net.VO.Mai2/*.cs Declaration）
# =============================================================================

@dataclass
class UserChargeVO:
    """GetUserCharge —— Holding status of a ticket（GetUserCharge.cs，4 Field）。"""
    chargeId: int = 0
    stock: int = 0
    purchaseDate: str = ""
    validDate: str = ""


@dataclass
class UserChargelogVO:
    """UserChargelog —— A purchase history（UserChargelog.cs，8 Field）。"""
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
    """request VO（UserChargelogRequestVO.cs，4 Field，ordertextDeclaration）。"""
    userId: int
    userChargelog: UserChargelogVO
    userCharge: UserChargeVO
    loginDateTime: int = 0


# =============================================================================
# Two、Tools
# =============================================================================

def ticket_name(charge_id: int) -> str:
    """Ticket Taking Name（For logs only）。"""
    return TICKET_NAMES.get(int(charge_id), "nottext(" + str(charge_id) + ")")


def ticket_price(charge_id: int, override: Optional[int] = None) -> int:
    """
    Take userChargelog.price —— i.e. ticket.creditNum。

    Basis VOExtensions.cs:410  result.price = ticket.creditNum;
    datatext TICKET_CREDIT_NUM（text Ticket.xml）。
    """
    if override is not None:
        return int(override)
    if int(charge_id) not in TICKET_CREDIT_NUM:
        log_warning("TICKET_CREDIT_NUM innone chargeId=" + str(charge_id)
                    + " —— press 0 Process，Recommended Complementary Configuration")
        return 0
    return int(TICKET_CREDIT_NUM[int(charge_id)])


#: Beijing Time（CST = UTC+8）
#:   Basis Manager/TimeManager.cs:9  CSToffset = new TimeSpan(8, 0, 0)
CST = timezone(timedelta(hours=8))


def now_cst(now: Optional[datetime] = None) -> datetime:
    """
    Take「Beijing time now」；Passed on. now Just use it.（textAlreadyisBeijing Time）。

    ★ Why explicitly +8 andNo datetime.now()：
        TimeManager.GetNowTime() returntimes **DateTime.UtcNow**，
        GetDateString() Again Add(CSToffset) —— i.e the date string in the game**Heng is Beijing time**，
        Irrelevant for native time zone。scripttextatnon-Dongba DistrictmachinetextUptime datetime.now() will be wrong。
    """
    if now is not None:
        return now
    return datetime.now(timezone.utc).astimezone(CST)


def _now_string(now: Optional[datetime] = None) -> str:
    """
    TimeManager.GetNowDateString() ofetctext。

    Basis Manager/TimeManager.cs:7,62-70：
        DateTimeFormat = "yyyy-MM-dd HH:mm:ss.f"
        GetDateString(unix) = GetDateTime(unix).ToString("yyyy-MM-dd HH:mm:ss.f")

    ★★ notetextTailthatPiece **.f**（One decimal place）—— real machinepacketlongthistext：
           "purchaseDate":"2026-10-06 13:20:10.0"
       Write less about this ".0" serverMeetingsdirectly returnCode=0（Measured stepped on）。
       ★ and validDate useofistextOnetext（text calc_valid_date），**Without**Decimal。
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
    calculatetextofhastextString。

    Basis TicketManager.cs:562-565：
        DateTime.Now.AddHours(-4.0).AddDays(90.0).ToString("yyyy-MM-dd 04:00:00")

    ★ notethisinuseofis**explicittext**（none .f），So the result is
      "2027-01-04 04:00:00" —— And purchaseDate of "…10.0" Different。
    """
    base = now_cst(now)
    d = (base + timedelta(hours=hour_offset) + timedelta(days=days)).date()
    return d.strftime("%Y-%m-%d") + " 04:00:00"


def parse_wall_time(text: Any) -> Optional[datetime]:
    """
    parseWall Timetext，Compatible with both formats：

        "2026-10-06 13:20:10.0"   ← TimeManager.DateTimeFormat（One decimal place，real machinepacketusethisPiece）
        "2026-10-06 13:20:10"     ← noDecimal（servertimestext GetUserChargeApi ofisthisPiece）

    parseNoouttextreturntimes None。
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
    """at GetUserChargeApi of userChargeList infindspecified chargeId。"""
    if not isinstance(charge_list, list):
        return None
    for c in charge_list:
        if isinstance(c, dict) and int(c.get("chargeId", -1) or -1) == int(charge_id):
            return c
    return None


# =============================================================================
# Three、Main Function
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
    purchaseBuyOnefeature tickets（UpsertUserChargelogApi，★ hasSide effects）。

    Parameter：
        user_id:         user ID（Required）
        charge_id:       mustBuyoftext ID（Required，= GetGameChargeApi inof chargeId）
                         ★ Paid tickets are 2/3/4/5/6（PAID_TICKET_IDS）
        login_date_time: logintime（Required，★ Required == UserLoginApi of loginDateTime）
        charge_list:     Current Ticket List（Optional）。Auto-adjust without passing GetUserChargeApi。
                         usetextcalculate「purchaseBuyAfterInventory」and if the ticket already exists。
        user_data:       Current userData（Optional）。Auto-adjust without passing GetUserDataApi。
                         usetextFill in playCount / playerRating。
        stock:           ★ purchaseBuyAfterthetextofInventory；Do not pass = currenthas + 1
        price:           ★ userChargelog.price；Do not pass = TICKET_CREDIT_NUM[charge_id]
        purchase_date:   purchaseBuytimeString；Do not pass = currentat
        valid_date:      hastextString；Do not pass = currentat-4h+90d（text calc_valid_date）
        play_count:      overwrite playCount（Take without passing userData.playCount）
        player_rating:   overwrite playerRating（Take without passing userData.playerRating）
        guard_purchasable: ★ default True = **Only allow to buy GetGameChargeApi Tickets listed**
                         （Throw it away if it's not in the list ChargelogGuardError，notPackaging）。
                         Basis TicketManager.cs:137-150 —— real machineAlsoFirstat
                         GetGameChargeDataList() infindtothe chargeId Just issued a purchase request，
                         findNotodirectly return false。serverYes.notUptextoftextMeetings returnCode=0。
                         Measured：textmachineStageOnlyUptext chargeId=2/3，Buy 5 will fail。
        game_charge_list: Purchasable list（Optional）。Auto-adjust without passing GetGameChargeApi。
        guard_no_stock:  ★ default True = **textCurrenttextHeldAnyFeature TicketstextdirectlytextpurchaseBuy**
                         （raise ChargelogGuardError，notPackaging）。
                         textbytext ChargelogGuardError of docstring —— hasTitle Risk。
                         textmusttextpurchaseBuyonlyPassing on False。
        confirm:         Side Effects Gate；None timeTake config.UPSERT_CHARGELOG_CONFIRM
        dry_run:         True = Construct and return packets only，textNo Package Issued

    returntimes：
        dry_run=True  -> UserChargelogRequestVO
        dry_run=False -> UpsertResponseVO
    """
    if not login_date_time:
        raise ValueError("text login_date_time：Must pass UserLoginApi of loginDateTime"
                         "（PacketUploadUserChargelog.cs:23）")

    name = ticket_name(charge_id)
    log_info("purchaseBuyFeature Tickets：user_id=" + str(user_id) + " chargeId=" + str(charge_id)
             + "（" + name + "）dry_run=" + str(dry_run))

    if int(charge_id) not in tuple(PAID_TICKET_IDS):
        log_warning("chargeId=" + str(charge_id) + " Not in PAID_TICKET_IDS="
                    + str(tuple(PAID_TICKET_IDS)) + " in —— It may not be a paid ticket that can be purchased")

    # ---------- 1. Take current state ----------
    if charge_list is None:
        log_info("notPassing on charge_list，textPick up current ticket ...")
        raw = resolve_api_func("GetUserCharge")(
            user_id, client_id=client_id, timeout_ms=timeout_ms, client=client)
        charge_list = (raw.get("userChargeList") if isinstance(raw, dict) else None) or []

    if user_data is None:
        log_info("notPassing on user_data，textTakeCurrentfiletext ...")
        raw_ud = resolve_api_func("GetUserData")(
            user_id, client_id=client_id, timeout_ms=timeout_ms, client=client)
        user_data = (raw_ud.get("userData") if isinstance(raw_ud, dict) else None) or {}

    # ---------- 1.4 ★ Security check：thisticketsCurrent**Is it on the shelf?** ----------
    #   Basis TicketManager.cs:137-150：real machineFirstat GetGameChargeDataList() infindthe
    #   chargeId，findtoonly RequestUserCharge，findNotodirectly return false（Don't buy）。
    #   serverYes.notUptextoftextMeetings returnCode=0 —— Measured Buy chargeId=5 That's the situation.。
    if guard_purchasable:
        if game_charge_list is None:
            log_info("notPassing on game_charge_list，textTakePurchasable list ...")
            _gc = resolve_api_func("GetGameCharge")(
                client_id=client_id, timeout_ms=timeout_ms, client=client)
            game_charge_list = (_gc.get("gameChargeList")
                                if isinstance(_gc, dict) else None) or []
        avail = [int(g.get("chargeId")) for g in (game_charge_list or [])
                 if isinstance(g, dict) and g.get("chargeId") is not None]
        log_info("Currently Available for Purchase chargeId：" + str(avail))
        if int(charge_id) not in avail:
            msg = ("Security check failed：chargeId=" + str(charge_id) + "（" + name
                   + "）**Not in current purchasable list**。\n"
                   "  Available for purchase：" + (str(avail) if avail else "（empty）") + "\n"
                   "  Basis TicketManager.cs:137-150 —— real machineAlsoOnlyBuy GetGameChargeApi\n"
                   "  Tickets listed，findNototextDo not sendpurchaseBuyrequest。\n"
                   "  serverYes.notUptextoftextMeetings returnCode=0（Measured）。\n"
                   "  textpurchaseBuypleasePassing on guard_purchasable=False。")
            log_error(msg)
            raise ChargelogGuardError(msg)
        log_info("Security check passed：chargeId=" + str(charge_id) + " In the purchasable list")

    # ---------- 1.5 ★ Security check：textIs it currentlyFeature tickets held ----------
    held = [c for c in (charge_list or [])
            if isinstance(c, dict) and int(c.get("stock", 0) or 0) > 0]
    if held:
        desc = "、".join(
            "chargeId=" + str(c.get("chargeId")) + "(" + ticket_name(c.get("chargeId"))
            + ") stock=" + str(c.get("stock")) + " validDate=" + str(c.get("validDate"))
            for c in held)
        log_warning("★ textCurrentHeld " + str(len(held)) + " feature tickets：" + desc)
        if guard_no_stock:
            msg = ("Security check failed：textCurrent**Feature tickets held**（" + desc + "），textAgaintextpurchaseBuy。\n"
                   "  Reason：real machineOnly in「this gamemustusethistickets」timeonlypurchaseBuy，And if you buy it, it will be used immediately."
                   "（stock--），currenttext stock Constantly 0。\n"
                   "  Purchase request has been issued with a ticket，servertexttoofistextpurchaseBuy，has**Title Risk**。\n"
                   "  textpurchaseBuypleasePassing on guard_no_stock=False。")
            log_error(msg)
            raise ChargelogGuardError(msg)
        log_warning("guard_no_stock=False —— This check has been skipped，textcontinuepurchaseBuy")
    else:
        log_info("Security check passed：textCurrentnonetexthasAnyFeature Tickets")

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
        # ★ real machinein purchaseDate And validDate alltextSame DateTime.Now
        #   （TicketManager.cs:216-219 And :564），So if the caller explicitly gives purchaseDate，
        #   hastexttheFrom**thatPiecetime**text，andNoFromcurrentattext。
        base = parse_wall_time(purchase_date)
        if base is None:
            log_warning("purchase_date parseNotext（should be 'YYYY-MM-DD HH:MM:SS[.f]'），"
                        "validDate changepress「currentat」countcalculate：" + str(purchase_date))
            base = now
        valid_date = calc_valid_date(base)

    log_info("  textFirst name        : " + name)
    log_info("  Inventory        : " + str(old_stock) + " -> " + str(stock))
    log_info("  price       : " + str(price) + "（= ticket.creditNum）")
    log_info("  purchaseDate: " + purchase_date)
    log_info("  validDate   : " + valid_date)

    # ---------- 2. constructrequest ----------
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
        log_info("[dry-run] Purchase message constructed，notPackaging")
        log_debug("dry-run packet：" + __import__("json").dumps(
            req, ensure_ascii=False, default=str))
        return req

    # ---------- 4. Side Effects Gate ----------
    effective = UPSERT_CHARGELOG_CONFIRM if confirm is None else bool(confirm)
    if not effective:
        msg = ("UpsertUserChargelogApi Meetings**realWriteA purchase history**（Irrevocable）。"
               "textscriptdefaultNotext。textmusthairpleasePassing on confirm=True，"
               "or change config.UPSERT_CHARGELOG_CONFIRM = True。"
               "I just want to see the message, please send it dry_run=True。")
        log_error(msg)
        raise ChargelogConfirmError(msg)

    # ---------- 5. Packaging ----------
    log_info("textAlreadytext，Start uploading purchase history ...")
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
        msg = ("purchaseBuyFailed：returnCode=" + str(resp.returnCode)
               + " apiName=" + resp.apiName)
        log_error(msg)
        raise RuntimeError(msg)

    log_info("purchaseBuySuccess：returnCode=" + str(resp.returnCode) + " apiName=" + resp.apiName)
    log_info("  textFirst name " + name + " Inventory " + str(old_stock) + " -> " + str(stock))
    return resp


# =============================================================================
# Four、Run separately（debug）
# =============================================================================

if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("chargelog_test")
        try:
            log_info("constructOneZhang 2 Ticket multiplier purchase message（No Package Issued）")
            req = UpsertUserChargelog(
                12345678, 2, 1791159576,
                charge_list=[], user_data={"playCount": 1260, "playerRating": 15000},
                dry_run=True,
            )
            log_info("userChargelog = " + str(req.userChargelog))
            log_info("userCharge    = " + str(req.userCharge))
            log_info("validDate calculatetext：")
            log_info("  2026-10-04 18:22:10 Buy 5 Ticket multiplier -> "
                     + calc_valid_date(datetime(2026, 10, 4, 18, 22, 10))
                     + "（real machine is 2027-01-02 04:00:00）")
            return 0
        finally:
            teardown_logging()

    raise SystemExit(_main())
