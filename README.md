<h1 align="center">WaHappy</h1>

<p align="center">
  <b>textDX oftext</b><br>
  Purpose：textDXoftextcantextplaytext，gettext。
</p>

<p align="center">AItextoftextusetext</p>

---

## this istext

WaHappy isOneuse **Python textnetworktext**With Mai MoeDX（SDGB National uniform）textserverInteractionofToolstext。

It doesn't modify the game、Do not inject process，Just rewrite what the game client does with the script：
QR login → Fetch Data → Upload Grades → logout。

> The protocol achieves two-way verification from all decompiled source code and real machine network logs，
> eachPieceCriticalConstantatCodetextinalltext**source codetext**。

---

## Current Status：v0

| script | text |
|---|---|
| **`upsert.py`** | ✅ **Available** —— QR login → Upload an Inning Result → fallLibrarytimescheck → logout |
| **`buy_ticket.py`** | ✅ **Available** —— purchaseBuyFeature Tickets |
| **`use_ticket.py`** | ✅ **Available** —— consumeCurrenttexthasofFeature Tickets |
| **`reincarnate.py`** | 🔧 Achieved（**nottext**）—— textdatatext（text） |
| **`netdelivery.py`** | ✅ **Available** —— check / Down `.app` / `.opt` updatePackage（Read-only） |
| `api/` Down 40+ Interface modules | 🔧 Achieved and passed zero network self-test，But**notAll inreal machineUptext** |

**textfile**at [`docs` Branch](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)，text[textfiletext](#textfiletext)。

---

## A Lesson：Don't give one thing in a paragraph AI

v0 oftexthairtext，I repeatedly split the same target into small segments and threw them AI，result：

| itemtext | Token consume |
|---|---|
| **v0 hastexthair** | **473M+** |
| Branch projects with abandoned mid-course | **1137.5M** |

**this 1137.5M inhasOnetextistextof。**

textcurrentoftextis：

> **Don't give something in segments AI，andisdirectlytextOnetext，textAftertext。**

A piecemeal handover would allow AI Repeated loss of context、text、Spin on a solved issue ——
andOnetextoftext + textlongoftext，On the contrary, it's faster and cheaper。

---

## itemtext

```
WaHappy/
├── config.py            texttimetextitem（machineStagetext / textdata / logtext）★ text
├── config.py.example    text
├── upsert.py            ★ Master Script：QR login → Upload Grades → logout
├── buy_ticket.py        Master Script：purchaseBuyFeature Tickets
├── use_ticket.py        Master Script：consumeCurrenttexthasofFeature Tickets
├── reincarnate.py       Master Script：textdatatext（text）
├── netdelivery.py       Master Script：check / Down .app / .opt updatePackage
├── selftest.py          textnetworktext（249 item，Criteria = source code + real machinelog）
│
├── api/                 ★ All modules that interact with the server（One interface, one script）
│   ├── __init__.py      systemOneExport + logtext
│   ├── maimai_net.py    networktext（AES / deflate / URL obfuscation / Cookie）
│   ├── log_setup.py     log（INFO / DEBUG Dual Mode）
│   ├── upsert_user_all.py      Upload Grades（36 nodes / 110 Field / Differential）
│   ├── get_need_user_data.py   settlementSnapshot orchestration + falltext data/<userId>.json
│   └── ...                     40+ Interface Scripts
│
├── data/                eachtextOnetextuserdataSnapshot（<userId>.json）★ No warehousing
├── download/            netdelivery.py Downloaded .app / .opt ★ No warehousing
├── logs/                logtextout（latest.log + text.log）★ No warehousing
└── source/              Decompile source code ★ No warehousing，text
```

**textcounttext**：`api/` ineachPiecescript = One interface，Exposure to one**canPassing ontextofFunction**。
The main script is only responsible for orchestration，logandtextallat `api/` Internal。

**Naming conventions**：server API Nameside Belt `Get` of，**scriptFirst nameAndFunction nameAlwaysBelt `get` / `Get`**
（Don't be ambiguous）。So the retrieval scripts are all `get_*.py`，The function is `GetXxx`。

### Branch description

| Branch | Content |
|---|---|
| **`mai`** | Main Branch —— Code |
| **`docs`** | Orphan Branch —— Only `docs/`，Development documentation and pitfalls logging |

Two branches**noneofSameoftext**，Individually。
`source/` isDecompile source code，**needtext**。

---

## Quick Start

### 1. text

```bash
pip install requests pycryptodome
```

### 2. ★ Fill in first `config.py`

Only templates in the warehouse `config.py.example`，Make a copy first：

```bash
cp   config.py.example config.py      # Linux / macOS
copy config.py.example config.py      # Windows
```

textAfter**Required**Fill in **`config.py` numberTwotext「machineStageAndStoretext」**：

| Variable | Fill in what |
|---|---|
| `CLIENT_ID` | Keychip shortValue（15 Bit Keychip Remove hyphen before 11 Bit），Shape like `A63E01ABCDE` |
| `PLACE_ID` | Your store ID |
| `REGION_ID` | Your area ID |
| `PLACE_NAME` | Store Name |
| `REGION_NAME` | Area Name |
| `KEYCHIP_ID` | **byAboveTwoValuetext**，Don't manipulate |

> ⚠️ If you fill it out incorrect，The request sent out carries the identity of someone else's machine，serverMeetingsdirectlytext。
>
> `config.py` at `.gitignore` in —— It's your private configuration，**Don't submit**。

### 3. text

```bash
python selftest.py        # textnetworktext，Should 249 itemFulltext（Not dependent on you config）
```

### Main script at a glance

| script | What for? | Side effects | needQR Code |
|---|---|---|---|
| `upsert.py` | Upload an Inning Result | ★ has | ✅ |
| `buy_ticket.py` | purchaseBuyFeature Tickets | ★ has | ✅ |
| `use_ticket.py` | consumeCurrenttexthasofFeature Tickets | ★ has | ✅ |
| `reincarnate.py` | textdatatext（text） | ★ has | ✅（text；textOptional） |
| `netdelivery.py` | check / Down `.app` / `.opt` updatePackage | Read-only | ❌ |
| `selftest.py` | textnetworktext | no | ❌ |

> **All scripts with side effects are not packaged by default**：Do not pass `--send` timeConstruct only packets（dry-run）。
> Want to read the message without consequences，Run once without `--send` of。

> QR code from the machine's「QR login」textgetTake，**hastext 10 Minutes**（Not Measured by Frequency）。

---

## upsert.py —— Upload an Inning Result

```bash
# text：login + textSnapshot + groupPackage，No Package Issued（textSide effects，It is recommended to run this first）
python upsert.py "<QR Code>"

# realUpload an Inning Result（★ hasSide effects，Irrevocable）
python upsert.py "<QR Code>" --send

# Common switches
python upsert.py "<QR Code>" --send --debug        # loginBeltFullreceivehairpacket
python upsert.py "<QR Code>" --send --cooldown 0   # skipPackagingago 60 secondsCooling
python upsert.py "<QR Code>" --send --no-verify    # skipUploadAfteroffallLibrarytimescheck
```

**text / textResultsOnlychange `config.py` of `PLAY_*`，Don't touch any code。**

### textnodes：`--extra-data`

Want to manually overwrite certain nodes（textAsthis gametexttooftext KaleidxScope text）：

```bash
python upsert.py "<QR Code>" --send --extra-data extra.json
```

keyMust be `upsertUserAll` of **36 nodes**One，Mistakes will be reported and available node names will be listed。
**JSON Verify before scanning**，Write error and exit directly，Don't waste QR codes。

> ⚠️ at PowerShell / CMD intext JSON Easily swallowed double quotes，**It is recommended to always use documents**。

### ★ `isNew*` Bitstring：0 / 1 / 2 ofMeaning

eachNumbergroupnodesalltextOneitem `isNew*` Bitstring，**One corresponds to an entry in the array**（orderMust be consistent）。

Basis `source/Assembly-CSharp/Net.VO.Mai2/VOExtensions.cs:309-364` of `BuildListData()`：

| Bit | Meaning | servertextfor |
|---|---|---|
| `0` | **Inventory update** —— textdatain**Existing**Entries with the same primary key | UPDATE |
| `1` | **added** —— textdatain**none**Entries with the same primary key | INSERT |
| `2` | **noVariation** —— Only `userFavoriteList` use，Other nodes will not appear | skip |

Primary Key See `api/upsert_user_all.py` of `DIFF_PRIMARY_KEYS`
（As `userKaleidxScopeList` use `gateId`、`userMusicDetailList` use `musicId`+`level`）。

> ⚠️ **Fill in existing entries `1` Meetings HTTP 500** —— serverMeetingsGo INSERT A duplicate record。
> real machinetextPackagetextin `isNewFavoriteList = "22212"`，Can be seen visually 0/1/2 textuseoftext。

> **Not sure what to fill in？** Look first `data/<YouruserId>.json` inCorrespondingnodes：
> Primary key already exists → `0`，Absent → `1`。

---

## buy_ticket.py —— purchaseBuyFeature Tickets

```bash
python buy_ticket.py "<QR Code>" --list                    # Only current tickets and available tickets are listed
python buy_ticket.py "<QR Code>" --charge-id 2             # text：Messages only
python buy_ticket.py "<QR Code>" --charge-id 2 --send      # ★ realpurchaseBuy
```

| chargeId | text | Escalated `price` |
|---|---|---|
| 2 | 2timesチケット | 1 |
| 3 | 3timesチケット | 2 |
| 5 | 5timesチケット | 4 |

> default `--charge-id 5`。**Tickets on shelves are different from store to store**，Before you buy `--list`。

### It does security checks.

1. Check before buying `GetGameChargeApi` —— textNoIn the purchasable listtext**textloginallDon't**directlytextout
2. textagocheck `GetUserChargeApi` —— **textFeature tickets heldtimedirectlytextpurchaseBuy**（textpurchaseBuyhasTitle Risk）
3. textAfterAgaincheckOncetext

---

## use_ticket.py —— consumeCurrenttexthasofFeature Tickets

```bash
python use_ticket.py "<QR Code>" --list                  # Only currently held tickets are listed
python use_ticket.py "<QR Code>" --ticket-id 2 --send    # ★ realconsume
```

**Principle**：`GetUserChargeApi` And `UpsertUserAllApi` inof `userChargeList` **textFullrelatedSame**，
Therefore, the target ticket in the node `stock` Subtract 1，Then let playlog Bring on `useTicketId` / `playCredit`，
servertextforthisticketstextthisOnegameusetext。

> **Typical use**：textintexttime `buy_ticket.py` Will refuse to buy again；
> If you want to buy another one, use this one first。

textPrincipleAndpacketBasistext [Instructions for using the feature ticket](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Instructions for using the feature ticket.md)。

---

## reincarnate.py —— text

putOnetext（text A）ofdatatexttotextOnetext（text B）。

```bash
# textdatatextQR Code（Will network to catch A ofdataand landed on data/<A>.json）
python reincarnate.py --dst-qr "<BofQR Code>" --src-qr "<AofQR Code>"

# textdatatextAlreadytextof JSON（text，text）
python reincarnate.py --dst-qr "<BofQR Code>" --src-json data/12345678.json --plan
python reincarnate.py --dst-qr "<BofQR Code>" --src-json data/12345678.json --send
```

**What did it do?**：

1. Pick source account A of 19 node data（textorread `data/<A>.json`）
2. usetext B ofQR Codelogin
3. put A of `userMusicDetailList` **Batch**Upload to B —— eachPackageMax. 4 first，
   and automatically avoids**textservertextof 2 firstPackage**（`[4,4,2]` → `[4,3,3]`）
4. eachPackagetext：**wait → Upload → logout（type=1）→ continueOfflogin**，Loop to end of transfer
5. eachPackageof playlog Record from track**Reverse Synthesis**（`achievement` / `deluxscore` / `scoreRank` …）

| Parameter | default | description |
|---|---|---|
| `--plan` | — | Only batch plans are listed，No Package Issued（**It is recommended to run this first**） |
| `--limit N` | 0（All） | Only before relocation N first（textuse） |
| `--per-packet N` | 4 | eachPackagetracknumber，**can only be 1 / 3 / 4** |
| `--wait N` | 5.0 | eachtextUploadagoofwaitsecondsnumber |
| `--clone-identity` | Off | text `userName` / `accessCode` Clone Together（defaultHold B textof） |

> ⚠️ **nottext。** Suggested first `--plan`，Again `--limit 8` Small Batch Trial。

Complete process、Batch Rules、continueOffAndlogouttextofBasistext [textdescription](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/textdescription.md)。

---

## netdelivery.py —— check / Down `.app` / `.opt` updatePackage

```bash
python netdelivery.py                 # use config.py inofmachineStagecheck，textAfter**Multi-select download**
python netdelivery.py A63E01ABCDE     # specified Keychip
python netdelivery.py --list          # List only + text，Don't download
python netdelivery.py --all           # Full Bottom（No interaction）
python netdelivery.py --only 1,3      # Only the next 1、3 item（No interaction）
python netdelivery.py --ver 1.55      # specifiedEscalationstext（default config.MAI_ENCODING）
python netdelivery.py --out D:\SDGB2026\update
```

Interactive Selection Support：text/emptytextMinutestext、Interval（`1-3`）、`a`=Select all、`n`=Select none、`q`=textout。
Download tape**textcontinuePassing on**and progress/text，defaulttextto `download/`（No warehousing）。

> this is**Read-only**text，Don't write any account data。
> needSame directoryDownof `authv1.py` textFor ALL.Net Protocol Layer。

---

## How to write the main script

**textHaraThen：Not for every api callusetextlog。** logAlreadytextat `api/` intext。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from api import (setup_logging, teardown_logging,
                 ParseQRCode, GetUserPreview, UserLogin, UserLogout, LogoutType,
                 UpsertUserAll)
from config import REGION_ID, PLACE_ID

def main() -> int:
    setup_logging("My Scripts")          # ← All you need is this sentence
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        user_id, token = ParseQRCode(sys.argv[1])
        session.update(user_id=user_id, token=token)

        GetUserPreview(user_id, token)                     # text
        login = UserLogin(user_id, token,
                          region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ★ A function runs the entire settlement link
        UpsertUserAll(user_id, login.loginId,
                      login_date_time=login.loginDateTime,
                      auth_date_time=login.dateTime,
                      token=token,
                      dry_run=False, confirm=True)
        return 0
    finally:
        if session["logged_in"]:                           # ★ Be sure to log out
            UserLogout(session["user_id"], session["token"], session["login_dt"],
                       logout_type=LogoutType.Logout,
                       region_id=REGION_ID, place_id=PLACE_ID)
        teardown_logging()

if __name__ == "__main__":
    sys.exit(main())
```

The Three Iron Laws：

1. **Do not log** —— eachPiece api Function will print automatically `=== Function name Get started ===` / `[textresult]`
2. **Be sure to log out** —— textat `isLogin=True` timeNext LoginMeetings `returnCode=100`
3. **The write interface should open the gate explicitly.** —— Write only `dry_run=False` Not enough，Must be given at the same time `confirm=True`

For the full guide, see [Master Scripting Guide](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Master Scripting Guide.md)。

---

## Completed / Future

**Completed（v0）**

- ✅ QR login / logout / Heartbeat，Full session link
- ✅ Upload an Inning Result（36 nodes / 110 Field / Differential / fallLibrarytimescheck）
- ✅ purchaseBuyFeature Tickets
- ✅ consumetexthasofFeature Tickets
- ✅ textdataSnapshotfalltext（`data/<userId>.json`）
- ✅ textdatatext（text）
- ✅ check / Down `.app` / `.opt` updatePackage
- ✅ textnetworktext 249 item
- ✅ MelonLoader textPackage Mod（`gamehook/`）

**It may be added in the future**

- **text** —— usetext
- textFeatures（Task / Map / receivetext / text……）
- textFullofreal machinetextoverwrite
- `reincarnate.py` oftext

---

## textfiletext

All in [`docs` Branch](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)：

| textfile | Content |
|---|---|
| [itemtext](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/itemtext.md) | Development to Master Documentation，thetext / thetext |
| [Master Scripting Guide](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Master Scripting Guide.md) | Specification for writing a new master script |
| [Upload Score Development Document](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Upload Score Development Document.md) | `UpsertUserAll` of 36 nodes / 110 Field |
| [UpsertUserAlltextPittext](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/UpsertUserAlltextPittext.md) | 28 itemtextPitrecord |
| [Instructions for using the feature ticket](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Instructions for using the feature ticket.md) | Buy tickets / usetextofFullPrincipleAndpacketBasis |
| [textdescription](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/textdescription.md) | `reincarnate.py` Complete process |
| [netdeliverydescription](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/netdeliverydescription.md) | DLI Protocols and Operating Principles |
| [Common pits and precautions](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Common pits and precautions.md) | QR Code / text / Side effects / log / network |
| [purchaseBuyFeature Ticketstext](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/purchaseBuyFeature Ticketstext.md) | Complete ticketing interface troubleshooting process |
| [purchaseBuyFeature Tickets_Archiving & Handoff](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/purchaseBuyFeature Tickets_Archiving & Handoff.md) | textchecktextfile |
| [real machineHookControlled Report](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/real machineHookControlled Report.md) | textPackage Mod Control |
| [Experimental Run Validation Record](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/Experimental Run Validation Record.md) | eachtextofresult |
| [textDX_QR logintext](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/textDX_QR logintext.md) | aimedb text |
| [logAndMaster Scripttext](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/logAndMaster Scripttext.md) | logtextsystemdescription |

---

## text

- **Zhicheng🍥** —— textFortext DLL
- [**WorkBuddy AI**](https://www.workbuddy.ai/)—— textFor AI text
- **DeepSeek V4.1 Flash** —— Main Code Writing
- [**NVIDIA NIM**](https://build.nvidia.com/models)、
  [**AMD**](https://developer.amd.com.cn/radeon/tokenfactory)、
  [**Kilo**](https://kilo.ai/)—— textFor AI text
- [**eaquira**](https://git.fragrance.moe/Fragrance/eaquira)—— Thought Inspiration
- **textU** —— texthastextof Web Inspiration（textno）
- **texthastext** —— Harmony Help

*（texthastextinAftertext）*

---

## Disclaimer

textitemtextOnlyFor**Learning and Protocol Research**Use。Any consequences arising from the use of this tool are the sole responsibility of the user。
pleasetextitemtext，Do not use it to undermine game fairness。
