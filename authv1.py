#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
authv1.py —— ALL.Net(alAbEx v4) machineStagetext：Keychip -> clientId / regionId / placeId / placeName / regionName
==========================================================================================================

【text】
    config.py numberTwotextthatSatvalues
        KEYCHIP_ID / CLIENT_ID / REGION_ID / PLACE_ID / PLACE_NAME / REGION_NAME
    All from **AMDaemon On startup, toward ALL.Net textservermustofresult**。
    textserver（maimai-gm.wahlap.com）**noneAnyinterface**will return them ——
    So in the past, this project could only be copied manually from the real machine message.（text config.py inthattext）。

    textscriptput AMDaemon ofthisOnetextAs istextOnetext。

【Protocol Origin】—— All can be used in source/amdaemon.exe ofStringinYes.Up（numbertextisfiletextOffset）
    text      http://at.sys-all.cn/net/initialize                    @0x788170
    Alternate      http://at.sys-allnet.cn/net/initialize                 Measurements are also available
    Library        alAbEx_lite Ver 4.00.01  (src/lib/alabex_pv4_lite)     @0x784a31
    request body    "title_id=%s&title_ver=%s&client_id=%s"                @0x7882b8
    requestHead    Pragma: DFI                                            @0x7883cc
              User-Agent: <...>Windows/Lite                          @0x788508
    Response Fields  result= uri1= uri2= name= nickname= region0=
              region_name0..3= place_id= setting= country=
              location_type= client_timezone= res_ver= uri=
              utc_time= token=                                       @0x784ae8-0x788fd0
    Envelope      AES-128-CBC + 16 Byte Prefix Block + PKCS7
              （exe @0x63a100 textto alAbExSetOption(ALE_ABEX_OPTION_AES_KEY)）

【Envelope Details】Actual measurement confirmation
    request = AES-CBC( 16 Byte Full 0 Prefix || text )，IV = 16 Byte Full 0
    Response = 16 Bytes IV || AES-CBC Ciphertext

【Response code】
    result= 1   Success
    result=-2   machineStageAbsent（client_id nottextreceivetext；Lowercase goes here, too.）
    result=-3   Wrong parameter format（For example, putting 15 Bit complete Keychip When client_id Send out）

【usage】
    python authv1.py A63E01E9580                # check（textresult）
    python authv1.py A63E-01C30471007           # Full with hyphens Keychip It's okay.
    python authv1.py A63E01E9580 --json         # machinetextread
    python authv1.py A63E01E9580 --write        # Force Writeback config.py
    python authv1.py A63E01E9580 --no-write     # Force Do Not Write
    python authv1.py --batch keychip.csv        # textcheck（CSV numberOneColumnsis Keychip）

    ★ isNoWriteback config.py，defaulttext config.py inof AUTHV1_WRITE_CONFIG Switch。

【Also used as a protocol library】
    from authv1 import allnet_post, initialize, delivery_instruction, parse_keychip
    netdelivery.py That's how you use it.。
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import shutil
import sys
import time
import urllib.parse

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


# =============================================================================
# Protocol Constants
# =============================================================================

# ALL.Net textserver（National uniform SDGB）。Two domains point to different machine rooms，The actual test can be used；
# defaultuse sys-allnet.cn（And maimai-gm.wahlap.com Same machine room，textshort）。
ALLNET_HOSTS = (
    "http://at.sys-allnet.cn",
    "http://at.sys-all.cn",
)
DEFAULT_HOST = ALLNET_HOSTS[0]

PATH_INITIALIZE = "/net/initialize"
PATH_DELIVERY_INSTRUCTION = "/net/delivery/instruction"

TITLE_ID = "SDGB"

# ALE_ABEX_OPTION_AES_KEY Corresponding 16 Byte Key。
# Source：exe @0x63a100 has alAbExSetOption(ALE_ABEX_OPTION_AES_KEY)；
#       Key ontology in exe inNotext，textplacePick a valuetextrealrequesttexthastext。
AES_KEY = bytes([47, 63, 106, 111, 43, 34, 76, 38, 92, 67, 114, 57, 40, 61, 107, 71])
AES_IV = bytes(16)

# requestHead。Basis：exe in "Pragma" + "DFI"(@0x7883cc) And "Windows/Lite"(@0x788508)。
HEADERS = {
    "User-Agent": "SDGB;Windows/Lite",
    "Pragma": "DFI",
    "Content-Type": "application/x-www-form-urlencoded",
}

DEFAULT_TIMEOUT = 20

# client_id Constantly 11 Bits Uppercase Hex（Keychip 15 Bit Before After Hyphen Removed 11 Bit）
CLIENT_ID_LEN = 11
CLIENT_ID_RE = re.compile(r"^[0-9A-F]{" + str(CLIENT_ID_LEN) + r"}$")

# Escalate to ALL.Net oftext。real machine 1.56 ROM Actual measurement is still reported 1.55（And Mai-Encoding Match）；
# defaultTake config.MAI_ENCODING，Return this literal if you can't get it。
DEFAULT_TITLE_VER = "1.55"

RESULT_TEXT = {
    "1": "Success",
    "-1": "textuseerror",
    "-2": "machineStageAbsent（client_id nottext ALL.Net receivetext）",
    "-3": "Wrong parameter format（client_id Must be 11 Bit Short）",
}


class AllnetError(RuntimeError):
    """ALL.Net Interaction failed（network / Envelope / Business code is not 1）。"""


# =============================================================================
# Envelope：AES-128-CBC
# =============================================================================

def encode_request(text: str) -> bytes:
    """text -> textUpBytestext：16 Byte Full 0 Prefix + PKCS7 + AES-128-CBC(IV=0)。"""
    body = AES_IV + text.encode("utf-8")
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(body, AES.block_size))


def decode_response(raw: bytes) -> str:
    """textUpBytestext -> text：ago 16 Bytes are IV，followed by AES-128-CBC Ciphertext。"""
    if len(raw) < 32 or len(raw) % AES.block_size:
        raise AllnetError("Abnormal response length：%d Bytes（should >=32 and is 16 oftimesnumber）" % len(raw))
    plain = AES.new(AES_KEY, AES.MODE_CBC, raw[:16]).decrypt(raw[16:])
    n = plain[-1]
    if 1 <= n <= AES.block_size:
        plain = plain[:-n]
    return plain.decode("utf-8", "replace")


def allnet_post(path, body, *, host=DEFAULT_HOST, timeout=DEFAULT_TIMEOUT, retries=3):
    """
    POST One encryption request，returntimesdecryptAfteroftext（Shape like "result=1&place_id=..."）。

    ★ Measured at.sys-allnet.cn Occasionally disconnects directly（RemoteDisconnected），
      So here's the right**networktext**Failed Retreat Retry；Business code is not 1 Don't retry。
    """
    url = host.rstrip("/") + path
    payload = encode_request(body)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, data=payload, headers=HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
                continue
            raise AllnetError("request %s Failed（Retried %d text）：%s" % (url, retries, exc)) from exc

        if resp.status_code != 200:
            if resp.status_code >= 500 and attempt < retries:
                last_error = "HTTP %d" % resp.status_code
                time.sleep(1.5 * attempt)
                continue
            raise AllnetError("request %s returntimes HTTP %d" % (url, resp.status_code))
        return decode_response(resp.content)

    raise AllnetError("request %s Failed：%s" % (url, last_error))


def parse_kv(text: str) -> dict:
    """put "result=1&place_id=146b&name=%E5%AE%89..." parsetext dict（Value Done URL text）。"""
    out = {}
    for part in text.strip().split("&"):
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        out[key.strip()] = urllib.parse.unquote(val)
    return out


# =============================================================================
# Keychip <-> client_id
# =============================================================================

def parse_keychip(raw: str) -> str:
    """
    putusertextof Keychip Normalization client_id（11 Bits Uppercase Short Value）。

    textThreetext：
        Full hyphenation  "A63E-01C30471007"
        Full Continuous Writing      "A63E01C30471007"
        shortValue          "A63E01C3047"

    ★ Why must it be cut off? 11 Bit：Measured handle complete 15 Bit when client_id Send out，
      ALL.Net times result=-3（text）。
    """
    s = re.sub(r"[\s\-]", "", str(raw)).upper()
    if len(s) < CLIENT_ID_LEN:
        raise ValueError("Keychip Too short：%r（text %d Bit）" % (raw, CLIENT_ID_LEN))
    cid = s[:CLIENT_ID_LEN]
    if not CLIENT_ID_RE.match(cid):
        raise ValueError("Keychip non-text：%r（Hexadecimal uppercase expected）" % raw)
    return cid


def make_keychip(client_id: str, place_id) -> str:
    """
    presstexttimesFull Keychip：
        ago 4 Bit + "-" + number 5 Bit from + placeId
    Example：A63E01C3047 + 1007 -> A63E-01C30471007
    """
    cid = str(client_id).upper()
    return "%s-%s%d" % (cid[:4], cid[4:], int(place_id))


# =============================================================================
# Two interfaces
# =============================================================================

def initialize(client_id, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
               timeout=DEFAULT_TIMEOUT):
    """POST /net/initialize —— machineStagetext，returntimesOriginaltext。"""
    body = "title_id=%s&title_ver=%s&client_id=%s" % (TITLE_ID, title_ver, client_id)
    return allnet_post(PATH_INITIALIZE, body, host=host, timeout=timeout)


def delivery_instruction(client_id, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
                         timeout=DEFAULT_TIMEOUT):
    """POST /net/delivery/instruction —— DLI，returntimesOriginaltext（Contains uri= text）。"""
    body = "title_id=%s&title_ver=%s&client_id=%s" % (TITLE_ID, title_ver, client_id)
    return allnet_post(PATH_DELIVERY_INSTRUCTION, body, host=host, timeout=timeout)


def query_keychip(keychip, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
                  timeout=DEFAULT_TIMEOUT, raw_ok=False):
    """
    checkOneStagemachineStageoftext。returntimes dict（Contains ok / result / Various fields）。

    ★ raw_ok=False time，result != 1 directlyraise AllnetError（CLI use）；
      raw_ok=True timetextreturntimes，bycallusetext result（textuse）。
    """
    cid = parse_keychip(keychip)
    text = initialize(cid, title_ver=title_ver, host=host, timeout=timeout)
    kv = parse_kv(text)

    result = kv.get("result", "")
    place_hex = kv.get("place_id", "") or ""
    try:
        place_id = int(place_hex, 16) if place_hex else None
    except ValueError:
        place_id = None

    region_names = [kv.get("region_name%d" % i, "") for i in range(4)]
    region_names = [n for n in region_names if n]

    try:
        region_id = int(kv.get("region0", "") or 0)
    except ValueError:
        region_id = None

    info = {
        "ok": result == "1",
        "result": result,
        "result_text": RESULT_TEXT.get(result, "nottextreturntimestext %s" % result),
        "title_id": TITLE_ID,
        "title_ver": title_ver,
        "host": host,
        # --- Five of the six values（KEYCHIP_ID istextValue）---
        "client_id": cid,
        "region_id": region_id,
        "place_id": place_id,
        "place_name": kv.get("name", ""),
        "region_name": region_names[0] if region_names else "",
        # --- text ---
        "nickname": kv.get("nickname", ""),
        "region_names": region_names,
        "country": kv.get("country", ""),
        "setting": kv.get("setting", ""),
        "location_type": kv.get("location_type", ""),
        "game_server_uri": kv.get("uri1", ""),
        "auth_token": kv.get("uri2", ""),
        "token": kv.get("token", ""),
        "utc_time": kv.get("utc_time", ""),
        "client_timezone": kv.get("client_timezone", ""),
        "res_ver": kv.get("res_ver", ""),
        "raw": text.strip(),
    }
    if info["place_id"] is not None:
        info["keychip"] = make_keychip(cid, info["place_id"])
    else:
        info["keychip"] = ""

    if not info["ok"] and not raw_ok:
        raise AllnetError("ALL.Net returntimes result=%s（%s）" % (result, info["result_text"]))
    return info


# =============================================================================
# Writeback config.py
# =============================================================================

CONFIG_FILENAME = "config.py"

# Which keys to write back（KEYCHIP_ID istextValue，Don't Write）
WRITEBACK_KEYS = ("CLIENT_ID", "REGION_ID", "PLACE_ID", "PLACE_NAME", "REGION_NAME")


def _replace_assignment(text, name, literal):
    """put config.py inUniqueOne Row NAME = ... text NAME = literal。"""
    pattern = re.compile(r"^(%s[ \t]*=[ \t]*).*$" % re.escape(name), re.M)
    new_text, count = pattern.subn(lambda m: m.group(1) + literal, text, count=1)
    if count != 1:
        raise AllnetError("config.py infindNotoUniqueof %s = ... textValuetext（findto %d place）" % (name, count))
    return new_text


def write_back_config(info, *, config_path=None, quiet=False):
    """
    putchecktextresultWriteback config.py。

    Safety measures：
        1. First ast.parse text，If it is badly written, it will not be placed on
        2. falltextagoputHarafiletext config.py.bak
        3. Preserve the line feed style of the original file（LF / CRLF）
    """
    path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       CONFIG_FILENAME)
    if not os.path.isfile(path):
        raise AllnetError("findNoto config.py：%s" % path)

    with open(path, "rb") as fp:
        raw = fp.read()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")

    pairs = [
        ("CLIENT_ID", json.dumps(info["client_id"], ensure_ascii=False)),
        ("REGION_ID", str(info["region_id"])),
        ("PLACE_ID", str(info["place_id"])),
        ("PLACE_NAME", json.dumps(info["place_name"], ensure_ascii=False)),
        ("REGION_NAME", json.dumps(info["region_name"], ensure_ascii=False)),
    ]
    for name, literal in pairs:
        text = _replace_assignment(text, name, literal)

    try:
        ast.parse(text)
    except SyntaxError as exc:
        raise AllnetError("changetextAfter config.py textNoLegal，Writing discarded：%s" % exc) from exc

    shutil.copy2(path, path + ".bak")
    with open(path, "wb") as fp:
        fp.write(text.replace("\n", newline).encode("utf-8"))

    if not quiet:
        print("  [Written back] %s" % path)
        print("  [Backed up] %s.bak" % path)
    return path


def config_switch_enabled(config_path=None):
    """read config.py inof AUTHV1_WRITE_CONFIG Switch。readNototextWhentextOff。"""
    path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       CONFIG_FILENAME)
    try:
        with open(path, "rb") as fp:
            tree = ast.parse(fp.read().decode("utf-8"))
    except Exception:
        return False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "AUTHV1_WRITE_CONFIG":
                    try:
                        return bool(ast.literal_eval(node.value))
                    except Exception:
                        return False
    return False


# =============================================================================
# textout
# =============================================================================

def format_report(info) -> str:
    """Human Readable Result Block。"""
    lines = []
    lines.append("=== authv1 machineStagetextchecktext ===")
    lines.append("  Keychip  (Full)  : %s" % (info["keychip"] or "(checkNoto)"))
    lines.append("  clientId (shortValue)  : %s        <- textserver clientId" % info["client_id"])
    lines.append("  placeId          : %s" % info["place_id"])
    lines.append("  placeName        : %s" % info["place_name"])
    lines.append("  regionId         : %s" % info["region_id"])
    lines.append("  regionName       : %s" % info["region_name"])
    lines.append("  --- text ---")
    lines.append("  textserver        : %s" % info["game_server_uri"])
    lines.append("  machineStagetext          : %s" % info["nickname"])
    lines.append("  Country/Region         : %s" % info["country"])
    lines.append("  texttimetext(UTC)     : %s  timetext %s" % (info["utc_time"], info["client_timezone"]))
    lines.append("  ALL.Net returntimestext    : %s（%s）" % (info["result"], info["result_text"]))
    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        prog="authv1.py",
        description="ALL.Net(alAbEx v4) machineStagetext：Keychip -> clientId/regionId/placeId/placeName/regionName",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "textExample：\n"
            "  python authv1.py A63E01E9580\n"
            "  python authv1.py A63E-01C30471007 --json\n"
            "  python authv1.py A63E01E9580 --write\n"
            "  python authv1.py --batch source/keychip.csv --limit 10\n"
        ),
    )
    p.add_argument("keychip", nargs="?", help="Keychip（Full hyphenation / Full Continuous Writing / 11 Any bit short value is fine）")
    p.add_argument("--batch", metavar="CSV",
                   help="textchecktext：CSV file，defaultreadnumberOneColumns（textHeadContains Keychip timetextskip）")
    p.add_argument("--limit", type=int, default=0, help="textmodeMax.checktextitem（0 = Unlimited）")
    p.add_argument("--ver", default=None, help="Escalate to ALL.Net oftext（defaultTake config.MAI_ENCODING）")
    p.add_argument("--host", default=DEFAULT_HOST, help="ALL.Net textserver（default %s）" % DEFAULT_HOST)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Number of seconds to time out a single request")
    p.add_argument("--json", action="store_true", help="textout JSON")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="Force write back results config.py")
    g.add_argument("--no-write", action="store_true", help="Force No Writeback config.py")
    return p


def resolve_title_ver(cli_value):
    if cli_value:
        return str(cli_value)
    try:
        import config  # noqa: F401  Same directory
        return str(getattr(config, "MAI_ENCODING", DEFAULT_TITLE_VER))
    except Exception:
        return DEFAULT_TITLE_VER


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    args = build_parser().parse_args(argv)
    title_ver = resolve_title_ver(args.ver)

    if args.batch:
        return run_batch(args, title_ver)

    if not args.keychip:
        build_parser().print_help()
        print("\nerror：pleasetextOne Keychip，or with --batch specified CSV。")
        return 2

    try:
        info = query_keychip(args.keychip, title_ver=title_ver,
                             host=args.host, timeout=args.timeout)
    except (AllnetError, ValueError) as exc:
        print("checktextFailed：%s" % exc)
        return 1

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=1))
    else:
        print(format_report(info))

    do_write = decide_write(args)
    if do_write:
        try:
            write_back_config(info)
        except AllnetError as exc:
            print("Writeback failed：%s" % exc)
            return 1
    elif not args.json:
        print("  [notWriteback] want it to write back automatically：put config.py of AUTHV1_WRITE_CONFIG changetext True，"
              "or add --write")
    return 0


def decide_write(args):
    """--write / --no-write Priority，Otherwise, look. config.py ofSwitch。"""
    if args.write:
        return True
    if args.no_write:
        return False
    return config_switch_enabled()


def _disp_width(text):
    """presstextcalculatelength：CJK Full-width Characters Occupies 2 Columns。"""
    import unicodedata
    width = 0
    for ch in str(text):
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _pad(text, width):
    text = str(text)
    return text + " " * max(0, width - _disp_width(text))


def run_batch(args, title_ver):
    path = args.batch
    if not os.path.isfile(path):
        print("findNoto CSV：%s" % path)
        return 2

    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.reader(fp)
        for row in reader:
            if not row or not row[0].strip():
                continue
            if row[0].strip().lower() in ("keychip", "keychip id", "keychipid"):
                continue
            rows.append(row)
    if args.limit > 0:
        rows = rows[: args.limit]

    print("=== authv1 textchecktext（%d Stage，text %s）===" % (len(rows), title_ver))
    header = "  ".join([_pad("clientId", 13), _pad("result", 6), _pad("placeId", 8),
                        _pad("regionId", 8), _pad("Area", 8), "Store Name"])
    print(header)
    ok = 0
    results = []
    for row in rows:
        try:
            info = query_keychip(row[0], title_ver=title_ver, host=args.host,
                                 timeout=args.timeout, raw_ok=True)
        except Exception as exc:
            print("%s  ERROR  %s" % (_pad(row[0].strip()[:13], 13), exc))
            continue
        results.append(info)
        if info["ok"]:
            ok += 1
        print("  ".join([
            _pad(info["client_id"], 13),
            _pad(info["result"], 6),
            _pad(info["place_id"], 8),
            _pad(info["region_id"], 8),
            _pad(info["region_name"], 8),
            str(info["place_name"]),
        ]))
    print("--- Success %d / %d ---" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
