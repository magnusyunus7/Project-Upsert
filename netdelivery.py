#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
netdelivery.py —— ALL.Net DLI(Download Instruction)：查 / 下 .app 与 .opt 更新包
================================================================================

【DLI 是什么】
    DLI = **Download Instruction**（配信指示書）。
    机台做完 ALL.Net 认证后，AMDaemon 会再问一次「我该下什么包」：

        POST http://at.sys-allnet.cn/net/delivery/instruction
        body = title_id=SDGB&title_ver=<版本>&client_id=<Keychip 短值>

    服务器回：

        result=1&uri=<patch 指示書 URL>|<option 指示書 URL>

    指示書本身是个 INI（日文注释），真正要下的包写在 INSTALLn= 里：

        [COMMON]    INSTALL1=https://.../SDGB_1.56.00_..._1_1.55.01.app
        [OPTIONAL]  INSTALL1=https://.../SDGB_A031_..._0.opt
                    INSTALL2=https://.../SDGB_A005_..._0.opt

    ★ 只有 INSTALLn= 才是**要下载的包**；EXISTn= 是「本机应该已经有的文件」，
      只是文件名，不是下载项。

【协议出处】—— source/amdaemon.exe 字符串（数字是文件内偏移）
    端点      http://at.sys-all.cn/net/delivery/instruction      @0x788198
    库        alw_lite/src/system39/alw_api_netdeliver.c        @0x63bf80
    阶段      ALWE_NETDELIVER_PHASE_GET_DLINST_INFO             @0x63bde0
              ALWE_NETDELIVER_PHASE_APP_IMAGE_INFO              @0x63be08
              ALWE_NETDELIVER_PHASE_OPT_IMAGE_INFO              @0x63be30
    日志      "Net deliver param - dli uri : %s."                @0x63c3f8
    状态      ALE_ABEX_STAT_DLINSTR_OK / _ERR_DLINSTR_NG ...     @0x638600

【实测结论】（2026-10-06）
    title_ver=1.55  -> uri = patch(SDGB_patch_1.56...info) | option(SDGB_option_1.55...A005.info)
    title_ver=1.56  -> uri = | option(A031)      （patch 槽为空 = 本体已最新）
    title_ver<=1.54 -> uri = null                （服务器不认这个版本）
    指示書里的 INSTALL 直链可以带 Range 断点续传（返回 206 + Content-Range）。
    ★ 已被下架的历史包，源站会回 504 —— 这是服务器状态，不是脚本的问题。

【用法】
    python netdelivery.py                       # 用 config.py 里的 Keychip 查，然后**多选下载**
    python netdelivery.py A63E01E9580           # 指定 Keychip
    python netdelivery.py --list                # 只列清单，不下载
    python netdelivery.py --all                 # 全下（不交互）
    python netdelivery.py --only 1,3            # 只下第 1、3 项（不交互）
    python netdelivery.py --ver 1.55            # 指定上报版本（默认 config.MAI_ENCODING）
    python netdelivery.py --out D:\SDGB2026\update
    python netdelivery.py --insecure            # 关掉 TLS 校验（CDN 证书有问题时用）

    ★ 交互选择支持：逗号/空格分隔、区间（如 1-3）、a=全选、n=全不选、q=退出。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import requests
import urllib3

from authv1 import (
    DEFAULT_HOST,
    DEFAULT_TIMEOUT,
    AllnetError,
    delivery_instruction,
    parse_keychip,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 下载器用的 UA（实测有效）
DOWNLOAD_HEADERS = {"User-Agent": "SDGB;Windows/Lite"}

DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
CHUNK = 1 << 16
PROBE_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60

# 包类型判定（按扩展名）
KIND_BY_EXT = {
    ".app": "app",
    ".opt": "opt",
    ".pack": "pack",
}

KIND_TEXT = {
    "app": "本体/补丁",
    "opt": "选项包",
    "pack": "资源包",
    "?": "未知",
}


# =============================================================================
# HTTP
# =============================================================================

def http_get(url, *, headers=None, stream=False, timeout=PROBE_TIMEOUT, insecure=False):
    """
    GET，顺带处理 CDN 证书问题。

    先按正常校验发；如果因为证书失败，再自动退回 verify=False 重发一次
    （只影响这一次请求，不改变全局设置）。
    """
    merged = dict(DOWNLOAD_HEADERS)
    if headers:
        merged.update(headers)
    try:
        return requests.get(url, headers=merged, stream=stream, timeout=timeout,
                            verify=not insecure)
    except requests.exceptions.SSLError:
        if insecure:
            raise
        return requests.get(url, headers=merged, stream=stream, timeout=timeout,
                            verify=False)


# =============================================================================
# 配信指示書解析
# =============================================================================

def parse_instruction(text):
    """
    解析配信指示書 INI。

    返回 (common, installs)：
        common   = {GAME_DESC: ..., DOWNLOAD_ID: ..., ...}（[COMMON] 段）
        installs = [{"section": "COMMON"/"OPTIONAL", "key": "INSTALL1", "url": ...}, ...]
    """
    common = {}
    installs = []
    section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().upper()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip().strip('"')
        if section in ("", "COMMON"):
            common.setdefault(key, value)
        if key.startswith("INSTALL") and value:
            installs.append({"section": section or "COMMON", "key": key, "url": value})
    return common, installs


def guess_kind(url):
    """按扩展名猜包类型。"""
    name = url.split("?")[0].rsplit("/", 1)[-1]
    ext = os.path.splitext(name)[1].lower()
    return KIND_BY_EXT.get(ext, "?")


def package_name(url):
    return url.split("?")[0].rsplit("/", 1)[-1]


def human_size(num):
    if num is None:
        return "?"
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return ("%d B" % int(value)) if unit == "B" else ("%.2f %s" % (value, unit))
        value /= 1024.0
    return "?"


# =============================================================================
# 采集：DLI -> 指示書 -> 包清单
# =============================================================================

def fetch_instruction_urls(client_id, *, title_ver, host, timeout):
    """问 DLI，返回 (patch_info_url, option_info_url, raw_text)。"""
    text = delivery_instruction(client_id, title_ver=title_ver, host=host, timeout=timeout)
    kv = {}
    for part in text.strip().split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v
    result = kv.get("result", "")
    if result != "1":
        raise AllnetError("DLI 返回 result=%s（原始：%s）" % (result, text.strip()[:200]))

    uri = kv.get("uri", "").strip()
    if uri in ("", "null"):
        raise AllnetError("DLI 返回 uri=%s：这个 title_ver 没有配信指示書"
                          "（换 --ver 试试，例如 1.55）" % (uri or "(空)"))

    parts = uri.split("|")
    patch_url = parts[0].strip() if len(parts) > 0 else ""
    option_url = parts[1].strip() if len(parts) > 1 else ""
    for bad in ("null", "none"):
        if patch_url.lower() == bad:
            patch_url = ""
        if option_url.lower() == bad:
            option_url = ""
    return patch_url, option_url, text.strip()


def collect_packages(client_id, *, title_ver, host, timeout, insecure=False):
    """
    走完整条链路，返回 (items, meta)。

    items 每一项：
        {"idx":1, "kind":"app", "section":"COMMON", "key":"INSTALL1",
         "url":..., "name":..., "size":int|None, "note":"", "info_name":...}
    """
    patch_url, option_url, dli_raw = fetch_instruction_urls(
        client_id, title_ver=title_ver, host=host, timeout=timeout)

    items = []
    meta = {"dli_raw": dli_raw, "title_ver": title_ver, "client_id": client_id,
            "instructions": [], "infos": {}}

    for info_url in (patch_url, option_url):
        if not info_url:
            continue
        info_name = package_name(info_url)
        resp = None
        for attempt in range(1, 4):
            try:
                resp = http_get(info_url, timeout=timeout, insecure=insecure)
                if resp.status_code < 500:
                    break
            except Exception:
                resp = None
            time.sleep(1.5 * attempt)
        if resp is None:
            meta["instructions"].append({"url": info_url,
                                         "error": "拉取失败（已重试 3 次）"})
            continue
        if resp.status_code != 200:
            meta["instructions"].append({"url": info_url, "status": resp.status_code,
                                         "error": "HTTP %d" % resp.status_code})
            continue
        text = resp.content.decode("utf-8", "replace")
        common, installs = parse_instruction(text)
        meta["instructions"].append({"url": info_url, "status": 200,
                                     "name": info_name, "common": common})
        meta["infos"][info_name] = text

        seen = set()
        for entry in installs:
            if entry["url"] in seen:
                continue
            seen.add(entry["url"])
            items.append({
                "kind": guess_kind(entry["url"]),
                "section": entry["section"],
                "key": entry["key"],
                "url": entry["url"],
                "name": package_name(entry["url"]),
                "size": None,
                "note": "",
                "info_name": info_name,
            })

    for i, item in enumerate(items, 1):
        item["idx"] = i
    return items, meta


def probe_all(items, *, timeout=PROBE_TIMEOUT, insecure=False):
    """探每个包的大小 / 可用性（就地写回 item）。"""
    for item in items:
        for attempt in range(1, 3):
            try:
                resp = http_get(item["url"], headers={"Range": "bytes=0-0"},
                                stream=True, timeout=timeout, insecure=insecure)
                status = resp.status_code
                content_range = resp.headers.get("Content-Range", "")
                content_length = resp.headers.get("Content-Length")
                resp.close()
                if status == 206 and "/" in content_range:
                    item["size"] = int(content_range.rsplit("/", 1)[-1])
                    item["note"] = ""
                elif status == 200 and content_length and content_length.isdigit():
                    item["size"] = int(content_length)
                    item["note"] = ""
                elif status in (404, 504):
                    item["note"] = "HTTP %d（源站不可用 / 该包已下架）" % status
                else:
                    item["note"] = "HTTP %d" % status
                break
            except Exception as exc:
                item["note"] = "探测失败：%s" % exc
                if attempt < 2:
                    time.sleep(1.5)
                    continue


# =============================================================================
# 展示与选择
# =============================================================================

def print_packages(items):
    if not items:
        print("  （指示書里没有任何 INSTALL 项）")
        return
    print("")
    print("  序号  类型  大小          来源段/键              文件名")
    print("  " + "-" * 92)
    for item in items:
        size = human_size(item["size"]) if item["size"] is not None else (item["note"] or "?")
        print("  [%2d]  %-4s  %-12s  %-20s  %s" % (
            item["idx"], item["kind"], size,
            item["section"] + "/" + item["key"], item["name"]))
        if item["note"] and item["size"] is None:
            print("        %s" % item["note"])


def prompt_selection(items):
    """
    交互多选。返回选中的 0 基下标列表；用户 q 退出时返回 None。
    """
    print("")
    print("  可多选：输入序号，用逗号或空格分隔；支持区间（如 1-3）。")
    print("          a = 全选    n = 都不选    q = 退出")
    while True:
        try:
            raw = input("  请选择要下载的包 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return None
        if not raw:
            continue
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            return None
        if low in ("a", "all"):
            return list(range(len(items)))
        if low in ("n", "none"):
            return []

        picked, bad = [], []
        for token in re.split(r"[,，、\s]+", raw):
            if not token:
                continue
            span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
            if span:
                low_i, high_i = sorted((int(span.group(1)), int(span.group(2))))
                for i in range(low_i, high_i + 1):
                    if 1 <= i <= len(items):
                        picked.append(i - 1)
                    else:
                        bad.append(str(i))
                continue
            if token.isdigit():
                i = int(token)
                if 1 <= i <= len(items):
                    picked.append(i - 1)
                else:
                    bad.append(token)
            else:
                bad.append(token)

        if bad:
            print("  [x] 无效输入：%s（范围是 1-%d）" % (", ".join(bad), len(items)))
            continue

        ordered, seen = [], set()
        for i in picked:
            if i not in seen:
                seen.add(i)
                ordered.append(i)
        if not ordered:
            print("  [x] 没有选中任何项")
            continue
        return ordered


# =============================================================================
# 下载
# =============================================================================

def download_file(url, dest, *, timeout=DOWNLOAD_TIMEOUT, retries=3, insecure=False):
    """
    带断点续传的下载。返回 (ok, 说明)。

    ★ 先写 dest + ".part"，下完再改名 —— 中断了下次能接着下。
    """
    part = dest + ".part"
    total = None

    for attempt in range(1, retries + 1):
        done = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {}
        if done:
            headers["Range"] = "bytes=%d-" % done
        try:
            resp = http_get(url, headers=headers, stream=True, timeout=timeout,
                            insecure=insecure)
        except Exception as exc:
            if attempt == retries:
                return False, "连接失败：%s" % exc
            time.sleep(2)
            continue

        if resp.status_code not in (200, 206):
            resp.close()
            if resp.status_code in (404, 504):
                return False, "HTTP %d（源站不可用 / 该包已下架）" % resp.status_code
            if attempt == retries:
                return False, "HTTP %d" % resp.status_code
            time.sleep(2)
            continue

        # 服务器忽略 Range 直接给了全量 -> 从头写
        if done and resp.status_code == 200:
            done = 0

        content_range = resp.headers.get("Content-Range", "")
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[-1])
            except ValueError:
                total = None
        elif resp.headers.get("Content-Length", "").isdigit():
            total = done + int(resp.headers["Content-Length"])

        mode = "ab" if done else "wb"
        started = time.time()
        written = done
        last_tick = 0.0
        last_shown = -1
        try:
            with open(part, mode) as fp:
                for chunk in resp.iter_content(CHUNK):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    written += len(chunk)
                    now = time.time()
                    if now - last_tick >= 0.3:
                        last_tick = now
                        last_shown = written
                        show_progress(written, total, now - started)
        except Exception as exc:
            resp.close()
            if attempt == retries:
                return False, "写入中断：%s" % exc
            time.sleep(2)
            continue
        finally:
            resp.close()

        if written == last_shown:
            sys.stdout.write("\n")          # 收尾换行，避免重复打一行
        else:
            show_progress(written, total, max(time.time() - started, 0.001), final=True)

        if total is not None and written != total:
            if attempt == retries:
                return False, "长度不符：期望 %d 字节，实际 %d 字节" % (total, written)
            time.sleep(2)
            continue

        if os.path.exists(dest):
            os.remove(dest)
        os.replace(part, dest)
        return True, "%s（%s）" % (human_size(written), dest)

    return False, "重试 %d 次仍失败" % retries


def show_progress(done, total, elapsed, final=False):
    speed = done / elapsed if elapsed > 0 else 0
    if total:
        percent = done * 100.0 / total
        line = "    %6.2f%%  %s / %s  %s/s" % (percent, human_size(done),
                                              human_size(total), human_size(speed))
    else:
        line = "    %s  %s/s" % (human_size(done), human_size(speed))
    sys.stdout.write("\r" + line + ("\n" if final else ""))
    sys.stdout.flush()


# =============================================================================
# CLI
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        prog="netdelivery.py",
        description="ALL.Net DLI：查 / 下 .app 与 .opt 更新包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python netdelivery.py                 # 查完让你多选\n"
            "  python netdelivery.py --list          # 只列清单\n"
            "  python netdelivery.py --all           # 全下\n"
            "  python netdelivery.py --only 1,3      # 只下第 1、3 项\n"
            "  python netdelivery.py --ver 1.55      # 指定上报版本\n"
        ),
    )
    p.add_argument("keychip", nargs="?",
                   help="Keychip（默认取 config.py 的 KEYCHIP_ID）")
    p.add_argument("--ver", default=None,
                   help="上报给 ALL.Net 的版本号（默认取 config.MAI_ENCODING）")
    p.add_argument("--host", default=DEFAULT_HOST,
                   help="ALL.Net 认证服务器（默认 %s）" % DEFAULT_HOST)
    p.add_argument("--out", default=DEFAULT_OUT_DIR,
                   help="下载目录（默认 <脚本目录>/download）")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="接口超时秒数")
    p.add_argument("--list", action="store_true", help="只列清单与直链，不下载")
    p.add_argument("--all", action="store_true", help="全选（不交互）")
    p.add_argument("--only", default=None, help="只下指定序号，如 1,3 或 1-3（不交互）")
    p.add_argument("--no-probe", action="store_true", help="跳过包大小探测（更快）")
    p.add_argument("--insecure", action="store_true", help="关掉 TLS 校验")
    return p


def resolve_keychip(cli_value):
    if cli_value:
        return cli_value
    try:
        import config  # noqa: F401
        value = getattr(config, "KEYCHIP_ID", "")
        if value:
            return value
    except Exception:
        pass
    return ""


def resolve_title_ver(cli_value):
    if cli_value:
        return str(cli_value)
    try:
        import config  # noqa: F401
        return str(getattr(config, "MAI_ENCODING", "1.55"))
    except Exception:
        return "1.55"


def parse_only(text, count):
    """把 --only 的文本解析成 0 基下标列表。"""
    picked, seen = [], set()
    for token in re.split(r"[,，、\s]+", text or ""):
        if not token:
            continue
        span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if span:
            low_i, high_i = sorted((int(span.group(1)), int(span.group(2))))
            candidates = range(low_i, high_i + 1)
        elif token.isdigit():
            candidates = [int(token)]
        else:
            raise ValueError("--only 里有无效项：%r" % token)
        for i in candidates:
            if not (1 <= i <= count):
                raise ValueError("--only 序号 %d 超出范围（1-%d）" % (i, count))
            if i - 1 not in seen:
                seen.add(i - 1)
                picked.append(i - 1)
    return picked


def save_instructions(meta, out_dir):
    """把配信指示書原样存一份，便于事后核对。"""
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for name, text in meta["infos"].items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="") as fp:
            fp.write(text)
        saved.append(path)
    return saved


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    args = build_parser().parse_args(argv)
    title_ver = resolve_title_ver(args.ver)

    raw_keychip = resolve_keychip(args.keychip)
    if not raw_keychip:
        print("错误：没给 Keychip，config.py 里的 KEYCHIP_ID 也是空的。")
        print("      先跑一次 python authv1.py <你的Keychip> 把 config.py 填好。")
        return 2
    try:
        client_id = parse_keychip(raw_keychip)
    except ValueError as exc:
        print("Keychip 解析失败：%s" % exc)
        return 2

    print("=== netdelivery (ALL.Net DLI) ===")
    print("  clientId   : %s" % client_id)
    print("  title_ver  : %s" % title_ver)
    print("  server     : %s" % args.host)
    print("  正在查询配信指示書 ...")

    try:
        items, meta = collect_packages(client_id, title_ver=title_ver, host=args.host,
                                       timeout=args.timeout, insecure=args.insecure)
    except (AllnetError, ValueError) as exc:
        print("查询失败：%s" % exc)
        return 1

    for entry in meta["instructions"]:
        if entry.get("status") == 200:
            common = entry.get("common", {})
            print("  指示書 %s" % entry["name"])
            for key in ("GAME_DESC", "DLFORMAT", "GAME_ID", "DOWNLOAD_ID",
                        "RELEASE_TIME", "RELEASE_TYPE"):
                if key in common:
                    print("      %-14s %s" % (key + ":", common[key]))
        else:
            print("  指示書 %s -> %s" % (entry["url"], entry.get("error", "?")))

    if not items:
        print("没有可下载的包。")
        return 0

    if not args.no_probe:
        print("  正在探测包大小 ...")
        probe_all(items, insecure=args.insecure)

    print_packages(items)

    if args.list:
        print("")
        print("  直链：")
        for item in items:
            print("    [%2d] %s" % (item["idx"], item["url"]))
        return 0

    # ---- 决定下哪些 ----
    if args.only:
        try:
            chosen = parse_only(args.only, len(items))
        except ValueError as exc:
            print("参数错误：%s" % exc)
            return 2
    elif args.all:
        chosen = list(range(len(items)))
    elif not sys.stdin or not sys.stdin.isatty():
        print("")
        print("  当前不是交互终端，未指定 --all / --only，已只列清单。")
        return 0
    else:
        chosen = prompt_selection(items)
        if chosen is None:
            print("  已取消。")
            return 0
        if not chosen:
            print("  没有选中任何项，退出。")
            return 0

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    for path in save_instructions(meta, out_dir):
        print("  [指示書] %s" % path)

    print("")
    print("  下载目录：%s" % out_dir)
    failed = []
    for index in chosen:
        item = items[index]
        dest = os.path.join(out_dir, item["name"])
        print("")
        print("  [%d/%d] %s（%s）" % (chosen.index(index) + 1, len(chosen),
                                      item["name"], KIND_TEXT.get(item["kind"], "?")))
        if item["size"] is None and item["note"]:
            print("      跳过：%s" % item["note"])
            failed.append((item, item["note"]))
            continue
        started = time.time()
        ok, message = download_file(item["url"], dest, insecure=args.insecure)
        if ok:
            print("      完成，用时 %.1f 秒 -> %s" % (time.time() - started, message))
        else:
            print("      失败：%s" % message)
            failed.append((item, message))

    print("")
    if failed:
        print("  --- 结束：%d 个成功，%d 个失败 ---" % (len(chosen) - len(failed), len(failed)))
        for item, message in failed:
            print("      [%2d] %s -> %s" % (item["idx"], item["name"], message))
        return 1
    print("  --- 结束：%d 个全部成功 ---" % len(chosen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
