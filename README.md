## Current Status: v0

| script | |
|---|---|
| **`upsert. py`** | ✅ **Available** — QR login → Upload an Inning Result → post-upload validation → logout |
| **`buy_ticket. py`** | ✅ **Available** — purchase tickets Tickets |
| **`use_ticket. py`** | ✅ **Available** — consume current tickets |
| **`reincarnate. py`** | 🔧 **Not achieved** — data() |
| **`netdelivery. py`** | ✅ **Available** — check / Down `. app` / `. opt` update Package (Read-only) |
| `api/` Down 40+ Interface modules | 🔧 Achieved and passed zero-network self-test, But **not all in real machine Up** |

**file** at [`docs` Branch](https://git. fragrance. moe/Txiaochen/wahappy/src/branch/docs), text [file](#file).

---

## item

```
RootFolder/
├── config. py      configuration item(machine state / data / log)-
├── config. py. example
├── upsert. py      - Master Script: QR login → Upload Grades → logout
├── buy_ticket. py    Master Script: purchase tickets Tickets
├── use_ticket. py    Master Script: consume current tickets
├── reincarnate. py    Master Script: data()
├── netdelivery. py    Master Script: check / Down. app /. opt updatePackage
├── selftest. py     network(249 item, Criteria = source code + real-machine log)
│
├── api/         - All modules that interact with the server(one interface, one script)
│  ├── __init__. py   central exports + log
│  ├── maimai_net. py  network(AES / deflate / URL obfuscation / Cookie)
│  ├── log_setup. py   log(INFO / DEBUG Dual Mode)
│  ├── upsert_user_all. py   Upload Grades(36 nodes / 110 Field / Differential)
│  ├── get_need_user_data. py  settlement snapshot orchestration + fall data/<userId>. json
│  └──...           40+ Interface Scripts
│
├── data/        eachoneuserdataSnapshot(<userId>. json)- not tracked
├── download/      netdelivery. py Downloaded. app /. opt - not tracked
├── logs/        logout(latest. log + log)- not tracked
└── source/       Decompile source code - not tracked, text
```

**count**: `api/` in each piece script = one interface, Exposure to one **callable function**.
The main script is only responsible for orchestration, logging, and all at `api/` internal.

**Naming conventions**: server API Name side Belt `Get` of, **script First name And Function name Always Belt `get` / `Get`**
(Don't be ambiguous). So the retrieval scripts are all `get_*. py`, The function is `GetXxx`.

---

## Quick Start

### 1.

```bash
pip install requests pycryptodome
```

### 2. - Fill in first `config. py`

Only templates in the warehouse `config. py. example`, Make a copy first:

```bash
cp  config. py. example config. py   # Linux / macOS
copy config. py. example config. py   # Windows
```

after **Required** Fill in **`config. py` number Two "machine state and store"**:

| Variable | Fill in what |
|---|---|
| `CLIENT_ID` | Keychip short Value (15 Bit Keychip Remove hyphen before 11 Bit), Shape like `A63E01ABCDE` |
| `PLACE_ID` | Your store ID |
| `REGION_ID` | Your area ID |
| `PLACE_NAME` | Store Name |
| `REGION_NAME` | Area Name |
| `KEYCHIP_ID` | **by Above Two Value**, Don't manipulate |

> ⚠️ If you fill it out incorrectly, The request sent out carries the identity of someone else's machine, and the server will directly
>
> `config. py` at `. gitignore` in — It's your private configuration, **Don't submit**.

### 3.

```bash
python selftest. py    # network Should 249 item Full (Not dependent on your config)
```

### Main script at a glance

| script | What for? | Side effects | needQR Code |
|---|---|---|---|
| `upsert. py` | Upload an Inning Result | - has | ✅ |
| `buy_ticket. py` | purchase tickets Tickets | - has | ✅ |
| `use_ticket. py` | consume current tickets | - has | ✅ |
| `reincarnate. py` | data() | - has | ✅ (optional) |
| `netdelivery. py` | check / Down `. app` / `. opt` updatePackage | Read-only | ❌ |
| `selftest. py` | network | no | ❌ |

> **All scripts with side effects are not packaged by default**: Do not pass `--send`; construct only packets (dry-run).
> Want to read the message without consequences? Run once without `--send`.

> QR code from the machine's "QR login" get Take, **has 10 Minutes** (Not Measured by Frequency).

---

## upsert. py — Upload an Inning Result

```bash
# login + Snapshot + batch packets, no packet is sent(Side effects, It is recommended to run this first)
python upsert. py "<QR Code>"

# realUpload an Inning Result(- hasSide effects, Irrevocable)
python upsert. py "<QR Code>" --send

# Common switches
python upsert. py "<QR Code>" --send --debug    # login and receive the complete packet
python upsert. py "<QR Code>" --send --cooldown 0  # skip the 60-second cooldown before packaging 60 secondsCooling
python upsert. py "<QR Code>" --send --no-verify  # skipUploadAfterofpost-upload validation
```

**play data/results Only change `config. py` of `PLAY_*`, Don't touch any code.**

### nodes: `--extra-data`

Want to manually overwrite certain nodes (As this game too of KaleidxScope):

```bash
python upsert. py "<QR Code>" --send --extra-data extra. json
```

key Must be `upsertUserAll` of **36 nodes** One, Mistakes will be reported and available node names will be listed.
**JSON Verify before scanning**, Write error and exit directly, Don't waste QR codes.

> ⚠️ At PowerShell / CMD, JSON easily swallows double quotes; **it is recommended to always use documents**.

### - `isNew*` Bitstring: 0 / 1 / 2 of Meaning

each Number group nodes all one item `isNew*` Bitstring, **One corresponds to an entry in the array** (order Must be consistent).

Basis `source/Assembly-CSharp/Net. VO. Mai2/VOExtensions. cs:309-364` of `BuildListData()`:

| Bit | Meaning | serverfor |
|---|---|---|
| `0` | **Inventory update** — data in **Existing** Entries with the same primary key | UPDATE |
| `1` | **added** — data in **none** Entries with the same primary key | INSERT |
| `2` | **no Variation** — Only `userFavoriteList` use, Other nodes will not appear | skip |

Primary Key See `api/upsert_user_all. py` of `DIFF_PRIMARY_KEYS`
(As `userKaleidxScopeList` use `gateId`,`userMusicDetailList` use `musicId`+`level`).

> ⚠️ **Fill in existing entries `1` Meetings HTTP 500** — the server will Go INSERT A duplicate record.
> real-machine in the packet `isNewFavoriteList = "22212"`, Can be seen visually 0/1/2 use of

> **Not sure what to fill in?** Look first `data/<YouruserId>. json` in corresponding nodes:
> Primary key already exists → `0`, Absent → `1`.

---

## buy_ticket. py — purchase tickets Tickets

```bash
python buy_ticket. py "<QR Code>" --list          # Only current tickets and available tickets are listed
python buy_ticket. py "<QR Code>" --charge-id 2       # Messages only
python buy_ticket.py "<QR Code>" --charge-id 2 --send   # real purchase
```

| chargeId | | Escalated `price` |
|---|---|---|
| 2 | 2timesチケット | 1 |
| 3 | 3timesチケット | 2 |
| 5 | 5timesチケット | 4 |

> default `--charge-id 5`. **Tickets on shelves are different from store to store**; before you buy, use `--list`.

### It does security checks.

1. Check before buying `GetGameChargeApi` — noIn the purchasable list**loginallDon't**directlyout
2. Check `GetUserChargeApi` —**buying while feature tickets are held carries a title risk**
3. afterAgaincheckOnce

---

## use_ticket. py — consume current tickets

```bash
python use_ticket. py "<QR Code>" --list         # Only currently held tickets are listed
python use_ticket. py "<QR Code>" --ticket-id 2 --send  # - realconsume
```

**Principle**: `GetUserChargeApi` And `UpsertUserAllApi` inof `userChargeList` **fullrelatedSame**,
Therefore, the target ticket in the node `stock` Subtract 1, Then let playlog Bring on `useTicketId` / `playCredit`,
serverforthisticketsthisone gameuse

> **Typical use**: in time `buy_ticket. py` Will refuse to buy again;
> If you want to buy another one, use this one first.

---

## reincarnate. py —

put One (A) of data to one (B).

```bash
# source data from a QR code(Will network to catch A ofdataand landed on data/<A>. json)
python reincarnate. py --dst-qr "<B QR code>" --src-qr "<A QR code>"

# source data from saved JSON()
python reincarnate. py --dst-qr "<B QR code>" --src-json data/12345678. json --plan
python reincarnate. py --dst-qr "<B QR code>" --src-json data/12345678. json --send
```

**What did it do?**

1. Pick source account A of 19 node data (or read `data/<A>. json`)
2. use B of QR Code login
3. put A of `userMusicDetailList` **Batch** Upload to B — each packet Max. four tracks,
  and automatically avoids **server-side two tracks Package** (`[4,4,2]` → `[4,3,3]`)
4. each packet **wait → Upload → logout(type=1) → continued login**, Loop to end of transfer
5. each packet of playlog Record from track **Reverse Synthesis** (`achievement` / `deluxscore` / `scoreRank` …)

| Parameter | default | description |
|---|---|---|
| `--plan` | — | Only batch plans are listed, no packet is sent(**It is recommended to run this first**) |
| `--limit N` | 0(All) | Only before relocation N first(use) |
| `--per-packet N` | 4 | tracks per packet, **can only be 1 / 3 / 4** |
| `--wait N` | 5.0 | wait time before each upload |
| `--clone-identity` | Off | `userName` / `accessCode` Clone Together(defaultkeep B's) |

> ⚠️ **not** Suggested first `--plan`; again, use `--limit 8` for a small batch trial.

---

## netdelivery. py — check / Down `. app` / `. opt` updatePackage

```bash
python netdelivery. py         # use config. py inofmachine statecheck, after**Multi-select download**
python netdelivery. py A63E01ABCDE   # specified Keychip
python netdelivery. py --list     # List only + Don't download
python netdelivery. py --all      # Full Bottom(No interaction)
python netdelivery. py --only 1,3   # Only the next 1,3 item(No interaction)
python netdelivery. py --ver 1.55   # specifiedEscalations(default config. MAI_ENCODING)
python netdelivery. py --out D:\SDGB2026\update
```

Interactive Selection Support: text/empty Minutes, Interval (`1-3`), `a` = Select all, `n` = Select none, `q` = out.
Download tape **continue Passing on** and progress/default to `download/` (not tracked).

> this is **Read-only**. Don't write any account data.
> need Same directory Down of `authv1. py` For ALL. Net Protocol Layer.

---

## How to write the main script

**Hara Then: Not for every api call use log.** Logging is already at `api/` in

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from api import (setup_logging, teardown_logging,
         ParseQRCode, GetUserPreview, UserLogin, UserLogout, LogoutType,
         UpsertUserAll)
from config import REGION_ID, PLACE_ID

def main() -> int:
  setup_logging("My Scripts")     # ← All you need is this sentence
  session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
  try:
    user_id, token = ParseQRCode(sys. argv[1])
    session. update(user_id=user_id, token=token)

    GetUserPreview(user_id, token)           #
    login = UserLogin(user_id, token,
             region_id=REGION_ID, place_id=PLACE_ID)
    session. update(login_dt=login. loginDateTime, logged_in=True)

    # - A function runs the entire settlement link
    UpsertUserAll(user_id, login. loginId,
           login_date_time=login. loginDateTime,
           auth_date_time=login. dateTime,
           token=token,
           dry_run=False, confirm=True)
    return 0
  finally:
    if session["logged_in"]:              # - Be sure to log out
      UserLogout(session["user_id"], session["token"], session["login_dt"],
            logout_type=LogoutType. Logout,
            region_id=REGION_ID, place_id=PLACE_ID)
    teardown_logging()

if __name__ == "__main__":
  sys. exit(main())
```

The Three Iron Laws:

1. **Do not log** — each Piece api Function will print automatically `=== Function name Get started ===` / `[result]`
2. **Be sure to log out** — at `isLogin=True` time Next Login Meetings `returnCode=100`
3. **The write interface should open the gate explicitly.** — Write only `dry_run=False` Not enough, Must be given at the same time `confirm=True`

For the full guide, see [Master Scripting Guide](https://git. fragrance. moe/Txiaochen/wahappy/src/branch/docs/docs/Master Scripting Guide. md).

---

## Completed / Future

**Completed(v0)**

- ✅ QR login / logout / Heartbeat, Full session link
- ✅ Upload an Inning Result(36 nodes / 110 Field / Differential / post-upload validation)
- ✅ purchase tickets Tickets
- ✅ consumehasoffeature tickets
- ✅ dataSnapshotfall(`data/<userId>. json`)
- ✅ data()
- ✅ check / Down `. app` / `. opt` update Package
- ✅ network 249 item
- ✅ MelonLoader packet Mod(`gamehook/`)

**It may be added in the future**

- **text** — use
- features (Task / Map / receive / ……)
- fullofreal machineoverwrite
- `reincarnate. py` of

---

## Disclaimer

item only For **Learning and Protocol Research** Use. Any consequences arising from the use of this tool are the sole responsibility of the user.
please item Do not use it to undermine game fairness.
