#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
authv1.py —— ALL.Net(alAbEx v4) 机台认证：Keychip -> clientId / regionId / placeId / placeName / regionName
==========================================================================================================

【解决什么问题】
    config.py 第二节那六个值
        KEYCHIP_ID / CLIENT_ID / REGION_ID / PLACE_ID / PLACE_NAME / REGION_NAME
    全部来自 **AMDaemon 开机时向 ALL.Net 认证服务器要的结果**。
    游戏服务器（maimai-gm.wahlap.com）**没有任何接口**会返回它们 ——
    所以本工程此前只能手工从真机报文里抄（见 config.py 里那段吐槽）。

    本脚本把 AMDaemon 的这一步原样重做了一遍。

【协议出处】—— 全部能在 source/amdaemon.exe 的字符串里对上（数字是文件内偏移）
    端点      http://at.sys-all.cn/net/initialize                    @0x788170
    备用      http://at.sys-allnet.cn/net/initialize                 实测同样可用
    库        alAbEx_lite Ver 4.00.01  (src/lib/alabex_pv4_lite)     @0x784a31
    请求体    "title_id=%s&title_ver=%s&client_id=%s"                @0x7882b8
    请求头    Pragma: DFI                                            @0x7883cc
              User-Agent: <...>Windows/Lite                          @0x788508
    响应字段  result= uri1= uri2= name= nickname= region0=
              region_name0..3= place_id= setting= country=
              location_type= client_timezone= res_ver= uri=
              utc_time= token=                                       @0x784ae8-0x788fd0
    信封      AES-128-CBC + 16 字节前缀块 + PKCS7
              （exe @0x63a100 提到 alAbExSetOption(ALE_ABEX_OPTION_AES_KEY)）

【信封细节】实测确认
    请求 = AES-CBC( 16 字节全 0 前缀 || 明文 )，IV = 16 字节全 0
    响应 = 16 字节 IV || AES-CBC 密文

【响应码】
    result= 1   成功
    result=-2   机台不存在（client_id 未被收录；小写也会走到这里）
    result=-3   参数格式错（例如把 15 位完整 Keychip 当 client_id 发出去）

【用法】
    python authv1.py A63E01E9580                # 查（打印结果）
    python authv1.py A63E-01C30471007           # 带连字符的完整 Keychip 也行
    python authv1.py A63E01E9580 --json         # 机器可读
    python authv1.py A63E01E9580 --write        # 强制写回 config.py
    python authv1.py A63E01E9580 --no-write     # 强制不写
    python authv1.py --batch keychip.csv        # 批量查（CSV 第一列是 Keychip）

    ★ 是否写回 config.py，默认看 config.py 里的 AUTHV1_WRITE_CONFIG 开关。

【也当协议库用】
    from authv1 import allnet_post, initialize, delivery_instruction, parse_keychip
    netdelivery.py 就是这么用它的。
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
# 协议常量
# =============================================================================

# ALL.Net 认证服务器（国服 SDGB）。两个域名指向不同机房，实测都能用；
# 默认用 sys-allnet.cn（与 maimai-gm.wahlap.com 同机房，链路更短）。
ALLNET_HOSTS = (
    "http://at.sys-allnet.cn",
    "http://at.sys-all.cn",
)
DEFAULT_HOST = ALLNET_HOSTS[0]

PATH_INITIALIZE = "/net/initialize"
PATH_DELIVERY_INSTRUCTION = "/net/delivery/instruction"

TITLE_ID = "SDGB"

# ALE_ABEX_OPTION_AES_KEY 对应的 16 字节密钥。
# 出处：exe @0x63a100 有 alAbExSetOption(ALE_ABEX_OPTION_AES_KEY)；
#       密钥本体在 exe 里不是明文串，此处取值经真实请求验证有效。
AES_KEY = bytes([47, 63, 106, 111, 43, 34, 76, 38, 92, 67, 114, 57, 40, 61, 107, 71])
AES_IV = bytes(16)

# 请求头。依据：exe 里 "Pragma" + "DFI"(@0x7883cc) 与 "Windows/Lite"(@0x788508)。
HEADERS = {
    "User-Agent": "SDGB;Windows/Lite",
    "Pragma": "DFI",
    "Content-Type": "application/x-www-form-urlencoded",
}

DEFAULT_TIMEOUT = 20

# client_id 恒为 11 位大写十六进制（Keychip 15 位去掉连字符后的前 11 位）
CLIENT_ID_LEN = 11
CLIENT_ID_RE = re.compile(r"^[0-9A-F]{" + str(CLIENT_ID_LEN) + r"}$")

# 上报给 ALL.Net 的版本号。真机 1.56 ROM 实测仍报 1.55（与 Mai-Encoding 一致）；
# 默认取 config.MAI_ENCODING，取不到就退回这个字面量。
DEFAULT_TITLE_VER = "1.55"

RESULT_TEXT = {
    "1": "成功",
    "-1": "通用错误",
    "-2": "机台不存在（client_id 未被 ALL.Net 收录）",
    "-3": "参数格式错误（client_id 必须是 11 位短值）",
}


class AllnetError(RuntimeError):
    """ALL.Net 交互失败（网络 / 信封 / 业务码非 1）。"""


# =============================================================================
# 信封：AES-128-CBC
# =============================================================================

def encode_request(text: str) -> bytes:
    """明文 -> 线上字节流：16 字节全 0 前缀 + PKCS7 + AES-128-CBC(IV=0)。"""
    body = AES_IV + text.encode("utf-8")
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(body, AES.block_size))


def decode_response(raw: bytes) -> str:
    """线上字节流 -> 明文：前 16 字节是 IV，其后是 AES-128-CBC 密文。"""
    if len(raw) < 32 or len(raw) % AES.block_size:
        raise AllnetError("响应长度异常：%d 字节（应 >=32 且为 16 的倍数）" % len(raw))
    plain = AES.new(AES_KEY, AES.MODE_CBC, raw[:16]).decrypt(raw[16:])
    n = plain[-1]
    if 1 <= n <= AES.block_size:
        plain = plain[:-n]
    return plain.decode("utf-8", "replace")


def allnet_post(path, body, *, host=DEFAULT_HOST, timeout=DEFAULT_TIMEOUT, retries=3):
    """
    POST 一条加密请求，返回解密后的明文（形如 "result=1&place_id=..."）。

    ★ 实测 at.sys-allnet.cn 偶尔会直接掐断连接（RemoteDisconnected），
      所以这里对**网络层**失败做退避重试；业务码非 1 不重试。
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
            raise AllnetError("请求 %s 失败（已重试 %d 次）：%s" % (url, retries, exc)) from exc

        if resp.status_code != 200:
            if resp.status_code >= 500 and attempt < retries:
                last_error = "HTTP %d" % resp.status_code
                time.sleep(1.5 * attempt)
                continue
            raise AllnetError("请求 %s 返回 HTTP %d" % (url, resp.status_code))
        return decode_response(resp.content)

    raise AllnetError("请求 %s 失败：%s" % (url, last_error))


def parse_kv(text: str) -> dict:
    """把 "result=1&place_id=146b&name=%E5%AE%89..." 解析成 dict（值做 URL 解码）。"""
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
    把用户给的 Keychip 归一化成 client_id（11 位大写短值）。

    接受三种写法：
        完整带连字符  "A63E-01C30471007"
        完整连写      "A63E01C30471007"
        短值          "A63E01C3047"

    ★ 为什么一定要截前 11 位：实测把完整 15 位当 client_id 发出去，
      ALL.Net 回 result=-3（格式错）。
    """
    s = re.sub(r"[\s\-]", "", str(raw)).upper()
    if len(s) < CLIENT_ID_LEN:
        raise ValueError("Keychip 太短：%r（至少 %d 位）" % (raw, CLIENT_ID_LEN))
    cid = s[:CLIENT_ID_LEN]
    if not CLIENT_ID_RE.match(cid):
        raise ValueError("Keychip 非法：%r（应为十六进制大写）" % raw)
    return cid


def make_keychip(client_id: str, place_id) -> str:
    """
    按本工程约定拼回完整 Keychip：
        前 4 位 + "-" + 第 5 位起 + placeId
    例：A63E01C3047 + 1007 -> A63E-01C30471007
    """
    cid = str(client_id).upper()
    return "%s-%s%d" % (cid[:4], cid[4:], int(place_id))


# =============================================================================
# 两个接口
# =============================================================================

def initialize(client_id, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
               timeout=DEFAULT_TIMEOUT):
    """POST /net/initialize —— 机台认证，返回原始明文。"""
    body = "title_id=%s&title_ver=%s&client_id=%s" % (TITLE_ID, title_ver, client_id)
    return allnet_post(PATH_INITIALIZE, body, host=host, timeout=timeout)


def delivery_instruction(client_id, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
                         timeout=DEFAULT_TIMEOUT):
    """POST /net/delivery/instruction —— DLI，返回原始明文（含 uri= 配信指示書地址）。"""
    body = "title_id=%s&title_ver=%s&client_id=%s" % (TITLE_ID, title_ver, client_id)
    return allnet_post(PATH_DELIVERY_INSTRUCTION, body, host=host, timeout=timeout)


def query_keychip(keychip, *, title_ver=DEFAULT_TITLE_VER, host=DEFAULT_HOST,
                  timeout=DEFAULT_TIMEOUT, raw_ok=False):
    """
    查一台机台的身份。返回 dict（含 ok / result / 各字段）。

    ★ raw_ok=False 时，result != 1 直接抛 AllnetError（CLI 用）；
      raw_ok=True 时照样返回，由调用方自己看 result（批量用）。
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
        "result_text": RESULT_TEXT.get(result, "未知返回码 %s" % result),
        "title_id": TITLE_ID,
        "title_ver": title_ver,
        "host": host,
        # --- 六个值里的五个（KEYCHIP_ID 是推导值）---
        "client_id": cid,
        "region_id": region_id,
        "place_id": place_id,
        "place_name": kv.get("name", ""),
        "region_name": region_names[0] if region_names else "",
        # --- 附送 ---
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
        raise AllnetError("ALL.Net 返回 result=%s（%s）" % (result, info["result_text"]))
    return info


# =============================================================================
# 写回 config.py
# =============================================================================

CONFIG_FILENAME = "config.py"

# 写回哪些键（KEYCHIP_ID 是推导值，不写）
WRITEBACK_KEYS = ("CLIENT_ID", "REGION_ID", "PLACE_ID", "PLACE_NAME", "REGION_NAME")


def _replace_assignment(text, name, literal):
    """把 config.py 里唯一一行 NAME = ... 换成 NAME = literal。"""
    pattern = re.compile(r"^(%s[ \t]*=[ \t]*).*$" % re.escape(name), re.M)
    new_text, count = pattern.subn(lambda m: m.group(1) + literal, text, count=1)
    if count != 1:
        raise AllnetError("config.py 里找不到唯一的 %s = ... 赋值行（找到 %d 处）" % (name, count))
    return new_text


def write_back_config(info, *, config_path=None, quiet=False):
    """
    把查询结果写回 config.py。

    安全措施：
        1. 先 ast.parse 语法自检，写坏了就不落盘
        2. 落盘前把原文件备份成 config.py.bak
        3. 保留原文件的换行风格（LF / CRLF）
    """
    path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       CONFIG_FILENAME)
    if not os.path.isfile(path):
        raise AllnetError("找不到 config.py：%s" % path)

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
        raise AllnetError("改写后 config.py 语法不合法，已放弃写入：%s" % exc) from exc

    shutil.copy2(path, path + ".bak")
    with open(path, "wb") as fp:
        fp.write(text.replace("\n", newline).encode("utf-8"))

    if not quiet:
        print("  [已写回] %s" % path)
        print("  [已备份] %s.bak" % path)
    return path


def config_switch_enabled(config_path=None):
    """读 config.py 里的 AUTHV1_WRITE_CONFIG 开关。读不到就当作关。"""
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
# 输出
# =============================================================================

def format_report(info) -> str:
    """人类可读的结果块。"""
    lines = []
    lines.append("=== authv1 机台身份查询 ===")
    lines.append("  Keychip  (完整)  : %s" % (info["keychip"] or "(查不到)"))
    lines.append("  clientId (短值)  : %s        <- 游戏服务器 clientId" % info["client_id"])
    lines.append("  placeId          : %s" % info["place_id"])
    lines.append("  placeName        : %s" % info["place_name"])
    lines.append("  regionId         : %s" % info["region_id"])
    lines.append("  regionName       : %s" % info["region_name"])
    lines.append("  --- 附送 ---")
    lines.append("  游戏服务器        : %s" % info["game_server_uri"])
    lines.append("  机台昵称          : %s" % info["nickname"])
    lines.append("  国家/地区         : %s" % info["country"])
    lines.append("  认证时间(UTC)     : %s  时区 %s" % (info["utc_time"], info["client_timezone"]))
    lines.append("  ALL.Net 返回码    : %s（%s）" % (info["result"], info["result_text"]))
    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        prog="authv1.py",
        description="ALL.Net(alAbEx v4) 机台认证：Keychip -> clientId/regionId/placeId/placeName/regionName",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python authv1.py A63E01E9580\n"
            "  python authv1.py A63E-01C30471007 --json\n"
            "  python authv1.py A63E01E9580 --write\n"
            "  python authv1.py --batch source/keychip.csv --limit 10\n"
        ),
    )
    p.add_argument("keychip", nargs="?", help="Keychip（完整带连字符 / 完整连写 / 11 位短值都行）")
    p.add_argument("--batch", metavar="CSV",
                   help="批量查询：CSV 文件，默认读第一列（表头含 Keychip 时自动跳过）")
    p.add_argument("--limit", type=int, default=0, help="批量模式最多查多少条（0 = 不限）")
    p.add_argument("--ver", default=None, help="上报给 ALL.Net 的版本号（默认取 config.MAI_ENCODING）")
    p.add_argument("--host", default=DEFAULT_HOST, help="ALL.Net 认证服务器（默认 %s）" % DEFAULT_HOST)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单次请求超时秒数")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="强制把结果写回 config.py")
    g.add_argument("--no-write", action="store_true", help="强制不写回 config.py")
    return p


def resolve_title_ver(cli_value):
    if cli_value:
        return str(cli_value)
    try:
        import config  # noqa: F401  同目录
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
        print("\n错误：请给一个 Keychip，或用 --batch 指定 CSV。")
        return 2

    try:
        info = query_keychip(args.keychip, title_ver=title_ver,
                             host=args.host, timeout=args.timeout)
    except (AllnetError, ValueError) as exc:
        print("查询失败：%s" % exc)
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
            print("写回失败：%s" % exc)
            return 1
    elif not args.json:
        print("  [未写回] 想让它自动写回：把 config.py 的 AUTHV1_WRITE_CONFIG 改成 True，"
              "或加 --write")
    return 0


def decide_write(args):
    """--write / --no-write 优先，否则看 config.py 的开关。"""
    if args.write:
        return True
    if args.no_write:
        return False
    return config_switch_enabled()


def _disp_width(text):
    """按终端显示宽度算长度：中日韩全角字符占 2 列。"""
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
        print("找不到 CSV：%s" % path)
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

    print("=== authv1 批量查询（%d 台，版本 %s）===" % (len(rows), title_ver))
    header = "  ".join([_pad("clientId", 13), _pad("result", 6), _pad("placeId", 8),
                        _pad("regionId", 8), _pad("区域", 8), "店铺名"])
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
    print("--- 成功 %d / %d ---" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
