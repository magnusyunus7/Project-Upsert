#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
netdelivery. py — ALL. Net DLI(Download Instruction): check / Down. app And. opt updatePackage
================================================================================

[DLI is]
  DLI = **Download Instruction**().
  machine state ALL. Net after, AMDaemon Will ask again"What bag should I order?":

    POST http://at. sys-allnet. cn/net/delivery/instruction
    body = title_id=SDGB&title_ver=<text>&client_id=<Keychip shortValue>

  servertimes:

    result=1&uri=<patch URL>|<option URL>

  isPiece INI(), currentmustDownofPackageat INSTALLn= in:

    [COMMON]  INSTALL1=https://.../SDGB_1.56.00_..._1_1.55.01. app
    [OPTIONAL] INSTALL1=https://.../SDGB_A031_..._0. opt
          INSTALL2=https://.../SDGB_A005_..._0. opt

  - Only INSTALLn= It is. **must Downloaded Package**; EXISTn= is "machine Should Already has of file",
   Just the filename, Not a download.

[Protocol Origin] — source/amdaemon. exe String (number is file Offset)
     http://at. sys-all. cn/net/delivery/instruction   @0x788198
  Library    alw_lite/src/system39/alw_api_netdeliver. c    @0x63bf80
  stage   ALWE_NETDELIVER_PHASE_GET_DLINST_INFO       @0x63bde0
       ALWE_NETDELIVER_PHASE_APP_IMAGE_INFO       @0x63be08
       ALWE_NETDELIVER_PHASE_OPT_IMAGE_INFO       @0x63be30
  log   "Net deliver param - dli uri: %s."        @0x63c3f8
     ALE_ABEX_STAT_DLINSTR_OK / _ERR_DLINSTR_NG...   @0x638600

[Observed Conclusions](2026-10-06)
  title_ver=1.55 -> uri = patch(SDGB_patch_1.56... info) | option(SDGB_option_1.55... A005. info)
  title_ver=1.56 -> uri = | option(A031)   (patch Is Empty = already)
  title_ver<=1.54 -> uri = null        (server No this Piece)
  in of INSTALL Yes Belt Range continue Passing on (returns 206 + Content-Range).
  - History pack that has been suspended, Meetingstimes 504 — this isserver-issued that is not scripted.

[usage]
  python netdelivery. py            # use config. py in of Keychip check, after **Multi-select download**
  python netdelivery. py A63E01E9580      # specified Keychip
  python netdelivery. py --list        # List only, Don't download
  python netdelivery. py --all         # Full Bottom(No interaction)
  python netdelivery. py --only 1,3      # Only the next 1,3 item(No interaction)
  python netdelivery. py --ver 1.55      # specified Escalations (default config. MAI_ENCODING)
  python netdelivery. py --out D:\SDGB2026\update
  python netdelivery. py --insecure      # Turn off TLS(CDN hastimeuse)

  - Interactive Selection Support: text/empty Minutes, Interval (As 1-3), a = Select all, n = Select none, q = out.
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

# For Downloaders UA(Measured Effective)
DOWNLOAD_HEADERS = {"User-Agent": "SDGB; Windows/Lite"}

DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
CHUNK = 1 << 16
PROBE_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60

# Package Type Determination(pressfirst name)
KIND_BY_EXT = {
    ". app": "app",
    ". opt": "opt",
    ". pack": "pack",
}

KIND_TEXT = {
    "app": "text/text",
    "opt": "itemPackage",
    "pack": "packet",
    "?": "not",
}


# =============================================================================
# HTTP
# =============================================================================

def http_get(url, *, headers=None, stream=False, timeout=PROBE_TIMEOUT, insecure=False):
    """
  GET, BeltProcess CDN

  First, calibrate and issue according to normal; If the certificate fails, Automatically bounce again verify=False hairOnce
  (Affects only once request, Don't change global settings).
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
# parse
# =============================================================================

def parse_instruction(text):
    """
  parse INI.

  returns (common, installs):
    common  = {GAME_DESC:..., DOWNLOAD_ID:...,...}([COMMON] )
    installs = [{"section": "COMMON"/"OPTIONAL", "key": "INSTALL1", "url":...},...]
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
    """pressfirst namepacket"""
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
# DLI -> -> Package manifest
# =============================================================================

def fetch_instruction_urls(client_id, *, title_ver, host, timeout):
    """DLI, returns (patch_info_url, option_info_url, raw_text)."""
    text = delivery_instruction(client_id, title_ver=title_ver, host=host, timeout=timeout)
    kv = {}
    for part in text.strip().split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v
    result = kv.get("result", "")
    if result != "1":
        raise AllnetError("DLI returns result=%s (Original: %s)" % (result, text.strip()[:200]))

    uri = kv.get("uri", "").strip()
    if uri in ("", "null"):
        raise AllnetError("DLI returns uri=%s: this Piece title_ver none"
                          "(--ver Example 1.55)" % (uri or "(empty)"))

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
  fullitemreturns (items, meta).

  items eachOneitem:
    {"idx":1, "kind":"app", "section":"COMMON", "key":"INSTALL1",
     "url":..., "name":..., "size": int|None, "note":"", "info_name":...}
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
                                         "error": "Fetch failed(Retried 3 )"})
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
    """eachPiecePackageofSize / Availability(Write back in place item)."""
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
                    item["note"] = "HTTP %d (no Available / the Package Already Down)" % status
                else:
                    item["note"] = "HTTP %d" % status
                break
            except Exception as exc:
                item["note"] = "Failed: %s" % exc
                if attempt < 2:
                    time.sleep(1.5)
                    continue


# =============================================================================
# Presentation & Selection
# =============================================================================

def print_packages(items):
    if not items:
        print(" (innoneAny INSTALL item)")
        return
    print("")
    print(" none.  Size     /key       fileFirst name")
    print(" " + "-" * 92)
    for item in items:
        size = human_size(item["size"]) if item["size"] is not None else (item["note"] or "?")
        print(" [%2d] %-4s %-12s %-20s %s" % (
            item["idx"], item["kind"], size,
            item["section"] + "/" + item["key"], item["name"]))
        if item["note"] and item["size"] is None:
            print("    %s" % item["note"])


def prompt_selection(items):
    """
  Interactive Multiple Choice. returnsin 0 Base subscript list; user q outtimereturns None.
  """
    print("")
    print(" Multiple choices available: no., useoremptyMinutes; Interval(As 1-3).")
    print("     a = Select all  n = allNo  q = out")
    while True:
        try:
            raw = input(" please must Downloaded Package > ").strip()
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
        for token in re.split(r"[,,,\s]+", raw):
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
            print(" [x] no %s (is 1-%d)" % (", ".join(bad), len(items)))
            continue

        ordered, seen = [], set()
        for i in picked:
            if i not in seen:
                seen.add(i)
                ordered.append(i)
        if not ordered:
            print(" [x] none Any item")
            continue
        return ordered


# =============================================================================
# Download
# =============================================================================

def download_file(url, dest, *, timeout=DOWNLOAD_TIMEOUT, retries=3, insecure=False):
    """
  Download with breakpoint continuation. returns (ok, description).

  - Write first dest + ". part", Rename after — interrupted the next time you can go on to the next.
  """
    part = dest + ". part"
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
                return False, "Failed: %s" % exc
            time.sleep(2)
            continue

        if resp.status_code not in (200, 206):
            resp.close()
            if resp.status_code in (404, 504):
                return False, "HTTP %d (no Available / the Package Already Down)" % resp.status_code
            if attempt == retries:
                return False, "HTTP %d" % resp.status_code
            time.sleep(2)
            continue

        # serverIgnore Range directlyfull Amount -> Write from scratch
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
                return False, "Write interrupted: %s" % exc
            time.sleep(2)
            continue
        finally:
            resp.close()

        if written == last_shown:
            sys.stdout.write("\n")          # receiveTailone Row
        else:
            show_progress(written, total, max(time.time() - started, 0.001), final=True)

        if total is not None and written != total:
            if attempt == retries:
                return False, "length No %d Bytes, actual %d Bytes" % (total, written)
            time.sleep(2)
            continue

        if os.path.exists(dest):
            os.remove(dest)
        os.replace(part, dest)
        return True, "%s(%s)" % (human_size(written), dest)

    return False, "%d Failed" % retries


def show_progress(done, total, elapsed, final=False):
    speed = done / elapsed if elapsed > 0 else 0
    if total:
        percent = done * 100.0 / total
        line = "  %6.2f%% %s / %s %s/s" % (percent, human_size(done),
                                              human_size(total), human_size(speed))
    else:
        line = "  %s %s/s" % (human_size(done), human_size(speed))
    sys.stdout.write("\r" + line + ("\n" if final else ""))
    sys.stdout.flush()


# =============================================================================
# CLI
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        prog="netdelivery. py",
        description="ALL. Net DLI: check / Down. app And. opt updatePackage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "example:\n"
            " python netdelivery. py         # check\n"
            " python netdelivery. py --list     # List only\n"
            " python netdelivery. py --all      # Full Bottom\n"
            " python netdelivery. py --only 1,3   # Only the next 1,3 item\n"
            " python netdelivery. py --ver 1.55   # specifiedEscalations\n"
        ),
    )
    p.add_argument("keychip", nargs="?",
                   help="Keychip (default Take config. py of KEYCHIP_ID)")
    p.add_argument("--ver", default=None,
                   help="Escalate to ALL. Net of (default Take config. MAI_ENCODING)")
    p.add_argument("--host", default=DEFAULT_HOST,
                   help="ALL. Net server(default %s)" % DEFAULT_HOST)
    p.add_argument("--out", default=DEFAULT_OUT_DIR,
                   help="Download catalog(default <script>/download)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="interface time seconds number")
    p.add_argument("--list", action="store_true", help="Column Only List with Straight Chain, Don't download")
    p.add_argument("--all", action="store_true", help="Select all(No interaction)")
    p.add_argument("--only", default=None, help="Specify only the serial number, As 1,3 or 1-3(No interaction)")
    p.add_argument("--no-probe", action="store_true", help="skipPackageSize()")
    p.add_argument("--insecure", action="store_true", help="Turn off TLS")
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
    """put --only ofparse 0 Base subscript list."""
    picked, seen = [], set()
    for token in re.split(r"[,,,\s]+", text or ""):
        if not token:
            continue
        span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if span:
            low_i, high_i = sorted((int(span.group(1)), int(span.group(2))))
            candidates = range(low_i, high_i + 1)
        elif token.isdigit():
            candidates = [int(token)]
        else:
            raise ValueError("--only inhasnoitem:%r" % token)
        for i in candidates:
            if not (1 <= i <= count):
                raise ValueError("--only none. %d out(1-%d)" % (i, count))
            if i - 1 not in seen:
                seen.add(i - 1)
                picked.append(i - 1)
    return picked


def save_instructions(meta, out_dir):
    """putAs isoneConvenient for post-checking."""
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
        print("error: Keychip, config. py in of KEYCHIP_ID is also empty.")
        print("   Run once first python authv1. py <YourKeychip> put config. py Fill in.")
        return 2
    try:
        client_id = parse_keychip(raw_keychip)
    except ValueError as exc:
        print("Keychip parse Failed: %s" % exc)
        return 2

    print("=== netdelivery (ALL. Net DLI) ===")
    print(" clientId: %s" % client_id)
    print(" title_ver: %s" % title_ver)
    print(" server: %s" % args.host)
    print(" current at check...")

    try:
        items, meta = collect_packages(client_id, title_ver=title_ver, host=args.host,
                                       timeout=args.timeout, insecure=args.insecure)
    except (AllnetError, ValueError) as exc:
        print("check Failed: %s" % exc)
        return 1

    for entry in meta["instructions"]:
        if entry.get("status") == 200:
            common = entry.get("common", {})
            print(" %s" % entry["name"])
            for key in ("GAME_DESC", "DLFORMAT", "GAME_ID", "DOWNLOAD_ID",
                        "RELEASE_TIME", "RELEASE_TYPE"):
                if key in common:
                    print("   %-14s %s" % (key + ":", common[key]))
        else:
            print(" %s -> %s" % (entry["url"], entry.get("error", "?")))

    if not items:
        print("none Downloaded Package.")
        return 0

    if not args.no_probe:
        print(" current at packet Size...")
        probe_all(items, insecure=args.insecure)

    print_packages(items)

    if args.list:
        print("")
        print(" ")
        for item in items:
            print("  [%2d] %s" % (item["idx"], item["url"]))
        return 0

    # ---- Decide which ----
    if args.only:
        try:
            chosen = parse_only(args.only, len(items))
        except ValueError as exc:
            print("Parameter error:%s" % exc)
            return 2
    elif args.all:
        chosen = list(range(len(items)))
    elif not sys.stdin or not sys.stdin.isatty():
        print("")
        print(" Currently not an interactive terminal, not specified --all / --only, Listed only.")
        return 0
    else:
        chosen = prompt_selection(items)
        if chosen is None:
            print(" Canceled.")
            return 0
        if not chosen:
            print(" none Any item, out.")
            return 0

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    for path in save_instructions(meta, out_dir):
        print(" [text] %s" % path)

    print("")
    print(" Download catalog:%s" % out_dir)
    failed = []
    for index in chosen:
        item = items[index]
        dest = os.path.join(out_dir, item["name"])
        print("")
        print(" [%d/%d] %s(%s)" % (chosen.index(index) + 1, len(chosen),
                                      item["name"], KIND_TEXT.get(item["kind"], "?")))
        if item["size"] is None and item["note"]:
            print("   skip:%s" % item["note"])
            failed.append((item, item["note"]))
            continue
        started = time.time()
        ok, message = download_file(item["url"], dest, insecure=args.insecure)
        if ok:
            print("   Done, use time %.1f seconds -> %s" % (time.time() - started, message))
        else:
            print("   Failed: %s" % message)
            failed.append((item, message))

    print("")
    if failed:
        print(" --- %d successes, %d failures ---" % (len(chosen) - len(failed), len(failed)))
        for item, message in failed:
            print("   [%2d] %s -> %s" % (item["idx"], item["name"], message))
        return 1
    print(" --- %d All succeeded ---" % len(chosen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
