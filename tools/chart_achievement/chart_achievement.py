#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""舞萌DX 谱面达成率 / DX 分计算器。

正向：给 谱面 + 各判定数量 -> 算达成率与 DX 分
反向：给 谱面 + 目标达成率   -> 倒算所有可行的判定组合与 DX 分

只依赖 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ma2 import (DIFFICULTY_NAMES, GROUP_LABEL, GROUP_ORDER, Chart,
                 chart_path, find_music_dir, level_display, parse_difficulty,
                 parse_ma2, parse_music_xml)
from score import (DX_PER, JUDGE_LABEL, JUDGMENTS, Theory, dx_score,
                   reference_achievement, solve_forward, solve_reverse,
                   theory_from_chart)

try:  # 中文输出到管道时避免 UnicodeEncodeError
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

LINE = "-" * 60


def pct(value) -> str:
    return "%.4f%%" % float(value)


def die(msg: str, code: int = 2) -> "None":
    print("[错误] " + msg, file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------- 载入谱面
def _enrich(chart: Chart, path: str) -> Chart:
    """从同目录的 Music.xml 补全曲名 / 难度 / 等级（拿不到就跳过）。"""
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    if "_" in stem:
        left, right = stem.split("_", 1)
        try:
            chart.music_id = int(left)
            chart.difficulty_index = int(right)
            chart.difficulty_name = DIFFICULTY_NAMES[chart.difficulty_index]
        except (ValueError, IndexError):
            pass
    xml_path = os.path.join(os.path.dirname(path), "Music.xml")
    if os.path.isfile(xml_path):
        info = parse_music_xml(xml_path)
        chart.song_name = info.get("name") or chart.song_name
        notes = info.get("notes") or []
        idx = chart.difficulty_index
        if idx is not None and 0 <= idx < len(notes):
            entry = notes[idx]
            chart.level_text = level_display(entry.get("level"), entry.get("levelDecimal"))
            try:
                chart.max_notes_xml = int(entry.get("maxNotes") or 0)
            except (TypeError, ValueError):
                chart.max_notes_xml = None
    return chart


def load_from_file(path: str) -> Chart:
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        die("谱面文件不存在：%s" % path)
    return _enrich(parse_ma2(path), path)


def load_from_game(game_path: str, music_id: int, difficulty: int) -> Chart:
    music_dir = find_music_dir(game_path)
    path = chart_path(music_dir, music_id, difficulty)
    if not os.path.isfile(path):
        alt = os.path.join(music_dir, "music%06d" % music_id)
        hint = ""
        if os.path.isdir(alt):
            have = sorted(f for f in os.listdir(alt) if f.lower().endswith(".ma2"))
            hint = "；该曲目现有谱面：" + (", ".join(have) if have else "无")
        die("找不到谱面：%s%s" % (path, hint))
    chart = parse_ma2(path)
    chart.music_id = music_id
    chart.difficulty_index = difficulty
    chart.difficulty_name = DIFFICULTY_NAMES[difficulty] if 0 <= difficulty <= 4 else "?"
    chart = _enrich(chart, path)
    chart.difficulty_index = difficulty
    chart.difficulty_name = DIFFICULTY_NAMES[difficulty] if 0 <= difficulty <= 4 else "?"
    return chart


# ------------------------------------------------------------------ 展示
def print_chart(chart: Chart, th: Theory) -> None:
    print(LINE)
    print("谱面")
    print("  文件      %s" % chart.path)
    if chart.song_name:
        print("  曲目      %s" % chart.song_name)
    if chart.music_id is not None:
        print("  编号      %d" % chart.music_id)
    if chart.difficulty_name:
        print("  难度      %s (%d)" % (chart.difficulty_name.upper(),
                                       chart.difficulty_index if chart.difficulty_index is not None else 0))
    if chart.level_text:
        print("  等级      %s" % chart.level_text)
    parts = []
    for g in GROUP_ORDER:
        n = th.counts.get(g, 0)
        if n:
            parts.append("%s %d" % (GROUP_LABEL[g], n))
    print("  音符      %s" % " · ".join(parts))
    print("  合计      %d 个计分音符" % th.total_notes)
    if chart.connect_count:
        print("            （另有 %d 个接续滑条节点，不计分）" % chart.connect_count)
    bonus = "  +  绝赞奖励 %d" % th.break_bonus_score if th.break_bonus_score else ""
    print("  理论分    %d%s" % (th.all_perfect_score, bonus))
    print("  理论DX    %d" % th.max_dx)
    print("  满分      %s" % pct(th.max_achievement))
    for w in chart.warnings:
        print("  [警告]    %s" % w)
    declared = chart.totals.get("TTM_SCR_SS")
    if declared is not None and declared != th.all_perfect_score:
        print("  [警告]    谱面自带 TTM_SCR_SS=%d 与计算出的理论分 %d 不一致"
              % (declared, th.all_perfect_score))


def print_forward(chart: Chart, result) -> None:
    th = result.theory
    print(LINE)
    print("判定输入")
    for j in JUDGMENTS:
        print("  %-18s %d" % (JUDGE_LABEL[j], result.judges.get(j, 0)))
    print("  %-18s %d / %d" % ("合计", sum(result.judges.values()), th.total_notes))
    print(LINE)
    print("结果")
    print("  达成率      %s ~ %s" % (pct(result.achievement_min), pct(result.achievement_max)))
    print("  按比例参考  %s" % pct(result.achievement_ref))
    print("  DX 分       %d / %d  (%.2f%%)"
          % (result.dx, th.max_dx, 100.0 * result.dx / th.max_dx if th.max_dx else 0.0))
    if result.achievement_min != result.achievement_max:
        print()
        print("  说明：只给聚合判定数时，达成率取决于「哪些音符」被判成 Great/Good/Miss——")
        print("        区间下界 = 扣分都落在权重最高的音符上，上界 = 都落在权重最低的音符上。")
    print(LINE)


def print_reverse(chart: Chart, outcome) -> None:
    th = outcome["theory"]
    rows = outcome["rows"]
    mode = outcome.get("mode", "exact")
    print(LINE)
    print("目标达成率 %s   [%s]" % (pct(outcome["target"]),
                                   "精确模式" if mode == "exact" else "区间模式"))
    note = outcome.get("note")
    if note:
        print("  [说明] %s" % note)
    if not rows:
        if mode == "exact":
            cap = outcome.get("exact_cap") or 0
            print("  （在严格验证范围内没有找到解：坏音符 ≤ %d 的组合里没有能精确打出该值的）" % cap)
            if outcome.get("more_unverified"):
                print("  [注意] 坏音符超过 %d 个的候选组合没有验证（不保证那里没有解）" % cap)
        else:
            print("  （无解：该达成率在这个谱面上打不出来）")
        print(LINE)
        return
    if mode == "exact":
        print("  Miss  Good  Great  CP+P   CP 范围      DX 分范围")
    else:
        print("  Miss  Good  Great  CP+P   CP 范围      达成率范围                 DX 分范围")
    for r in rows:
        cp_range = "%d~%d" % (r.cp_min, r.cp_max) if r.cp_min != r.cp_max else str(r.cp_min)
        dx_range = "%d~%d" % (r.dx_min, r.dx_max) if r.dx_min != r.dx_max else str(r.dx_min)
        if mode == "exact":
            print("  %4d  %4d  %5d  %4d   %-11s  %s"
                  % (r.miss, r.good, r.great, r.cp_plus_perfect, cp_range, dx_range))
        else:
            ach = "%s ~ %s" % (pct(r.achievement_min), pct(r.achievement_max))
            print("  %4d  %4d  %5d  %4d   %-11s  %-24s %s"
                  % (r.miss, r.good, r.great, r.cp_plus_perfect, cp_range, ach, dx_range))
    print()
    if mode == "exact":
        print("  共 %d 组能精确打出 %s 的判定组合（CP+P = Critical Perfect 与 Perfect 之和）"
              % (len(rows), pct(outcome["target"])))
        cap = outcome.get("exact_cap") or 0
        print("  已逐个严格验证 Miss+Good+Great ≤ %d 的组合；每个组合都真的能打出该达成率" % cap)
        if outcome.get("unverified"):
            print("  [注意] 另有 %d 组候选（坏音符超过 %d 个）未做精确验证，未列入结果"
                  % (outcome["unverified"], cap))
        if outcome.get("more_unverified"):
            print("  [注意] 坏音符超过 %d 个的候选组合没有验证（不保证那里没有解）" % cap)
    else:
        print("  共 %d 组可行组合（CP+P = Critical Perfect 与 Perfect 之和）" % len(rows))
        print("  区间模式：只保证达成率落在这个范围内，不保证能恰好打出目标值")
    if outcome["truncated"]:
        print("  [注意] 结果被 --limit / 扫描上限截断，可能还有更多组合")
    print("  DX 分 = 3*CP + 2*Perfect + 1*Great；CP 越靠范围上端，DX 分越高")
    print(LINE)


# ------------------------------------------------------------------ JSON
def to_json(chart: Chart, th: Theory, payload: Dict) -> str:
    data = {
        "chart": {
            "path": chart.path,
            "music_id": chart.music_id,
            "song_name": chart.song_name,
            "difficulty": chart.difficulty_name,
            "difficulty_index": chart.difficulty_index,
            "level_text": chart.level_text,
            "notes": th.counts,
            "total_notes": th.total_notes,
            "connect_slide": chart.connect_count,
            "all_perfect_score": th.all_perfect_score,
            "break_bonus_score": th.break_bonus_score,
            "max_dx": th.max_dx,
            "max_achievement": float(th.max_achievement),
            "warnings": chart.warnings,
        },
    }
    data.update(payload)
    return json.dumps(data, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ 交互
def ask(prompt: str, default: str = "") -> str:
    try:
        text = input(prompt).strip()
    except EOFError:
        text = ""
    return text or default


def ask_int(prompt: str, default: Optional[int] = None) -> Optional[int]:
    while True:
        raw = ask(prompt, "" if default is None else str(default))
        if raw == "" and default is None:
            return None
        try:
            return int(raw)
        except ValueError:
            print("  请输入整数")


def interactive(args) -> None:
    print("=" * 60)
    print("舞萌DX 谱面达成率 / DX 分 计算器")
    print("=" * 60)
    chart = None
    while chart is None:
        mode = ask("谱面来源：1) .ma2 文件路径  2) 游戏路径 + musicid  [1]: ", "1")
        if mode.startswith("2"):
            game = ask("游戏路径（Sinmai_Data 目录）: ")
            if not game:
                continue
            mid = ask_int("musicid: ")
            if mid is None:
                continue
            diff = ask("难度 0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER  [3]: ", "3")
            try:
                chart = load_from_game(game, mid, parse_difficulty(diff))
            except SystemExit:
                chart = None
        else:
            path = ask("谱面文件路径: ")
            if not path:
                continue
            try:
                chart = load_from_file(path)
            except SystemExit:
                chart = None
    th = theory_from_chart(chart)
    print_chart(chart, th)

    mode = ask("计算模式：1) 已知判定数算达成率  2) 已知达成率倒算判定数  [1]: ", "1")
    if mode.startswith("2"):
        while True:
            raw = ask("目标达成率（如 99.5 或 100.5）: ")
            if not raw:
                return
            try:
                target = Fraction(raw.rstrip("%"))
                break
            except (ValueError, ZeroDivisionError):
                print("  请输入数字")
        mode = ask("反算方式：1) 精确（只列真能打出该达成率的组合）  2) 区间（判定数只是估算时用）  [1]: ", "1")
        args.mode = "range" if mode.startswith("2") else "exact"
        run_reverse(chart, th, target, args)
    else:
        values = {}
        for j in JUDGMENTS:
            if j == "miss":
                continue
            values[j] = ask_int("  %s 数 [0]: " % JUDGE_LABEL[j], 0) or 0
        values["miss"] = ask_int("  Miss 数（留空 = 总数减去以上判定）: ")
        run_forward(chart, th, values, args)


# ------------------------------------------------------------------ 执行
def normalize_judges(th: Theory, raw: Dict[str, Optional[int]]) -> Dict[str, int]:
    given = {j: int(raw.get(j) or 0) for j in JUDGMENTS}
    if raw.get("miss") is None:
        given["miss"] = th.total_notes - sum(given[j] for j in JUDGMENTS if j != "miss")
    if given["miss"] < 0:
        die("CP+Perfect+Great+Good 合计 %d 超过了音符总数 %d"
            % (sum(given[j] for j in JUDGMENTS if j != "miss"), th.total_notes))
    total = sum(given.values())
    if total != th.total_notes:
        die("判定数之和 %d 与音符总数 %d 不一致（Miss 请留空自动补足）" % (total, th.total_notes))
    return given


def run_forward(chart: Chart, th: Theory,
                raw: Dict[str, Optional[int]], args) -> None:
    judges = normalize_judges(th, raw)
    result = solve_forward(th, judges)
    if args.json:
        print(to_json(chart, th, {
            "mode": "forward",
            "judges": judges,
            "achievement_min": float(result.achievement_min),
            "achievement_max": float(result.achievement_max),
            "achievement_reference": float(result.achievement_ref),
            "dx_score": result.dx,
        }))
        return
    print_chart(chart, th)
    print_forward(chart, result)


def run_reverse(chart: Chart, th: Theory,
                target: Fraction, args) -> None:
    outcome = solve_reverse(th, target, limit=args.limit, mode=args.mode)
    if args.json:
        print(to_json(chart, th, {
            "mode": "reverse",
            "search_mode": outcome["mode"],
            "target": float(target),
            "truncated": outcome["truncated"],
            "exact_cap": outcome.get("exact_cap"),
            "unverified": outcome.get("unverified", 0),
            "more_unverified": outcome.get("more_unverified", False),
            "note": outcome.get("note"),
            "solutions": [{
                "miss": r.miss, "good": r.good, "great": r.great,
                "critical_perfect_plus_perfect": r.cp_plus_perfect,
                "critical_perfect_min": r.cp_min, "critical_perfect_max": r.cp_max,
                "achievement_min": float(r.achievement_min),
                "achievement_max": float(r.achievement_max),
                "dx_min": r.dx_min, "dx_max": r.dx_max,
            } for r in outcome["rows"]],
        }))
        return
    print_chart(chart, th)
    print_reverse(chart, outcome)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chart_achievement.py",
        description="舞萌DX 谱面达成率 / DX 分计算器（正向计算 + 由达成率倒算判定数）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  # 直接给谱面文件，正向计算
  python chart_achievement.py --chart "D:\\SDGB2026\\Package\\Sinmai_Data\\StreamingAssets\\A000\\music\\music000008\\000008_03.ma2" --cp 290 --perfect 10 --great 2

  # 给游戏路径 + musicid + 难度（难度用游戏里的数字：0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER）
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --cp 300 --perfect 2

  # 由达成率倒算判定组合（精确模式：只列真能打出该值的组合）
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --achievement 99.5

  # 判定数只是估算时，用区间模式
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --achievement 99.5 --mode range
""")
    src = p.add_argument_group("谱面来源（二选一）")
    src.add_argument("--chart", metavar="PATH", help=".ma2 谱面文件路径")
    src.add_argument("--game", metavar="PATH", help="游戏目录（Sinmai_Data / StreamingAssets / A000 / music 均可）")
    src.add_argument("--music-id", type=int, metavar="ID", help="曲目编号（配合 --game 使用）")
    src.add_argument("--level", "--difficulty", dest="level", default=None, metavar="D",
                     help="谱面难度，用游戏里的数字：0=BASIC 1=ADVANCED 2=EXPERT "
                          "3=MASTER 4=RE:MASTER（也可直接写名字；默认 3=MASTER）")

    fw = p.add_argument_group("正向计算：已知判定数")
    fw.add_argument("--cp", type=int, metavar="N", help="Critical Perfect 个数")
    fw.add_argument("--perfect", type=int, metavar="N", help="Perfect 个数")
    fw.add_argument("--great", type=int, metavar="N", help="Great 个数")
    fw.add_argument("--good", type=int, metavar="N", help="Good 个数")
    fw.add_argument("--miss", type=int, metavar="N", help="Miss 个数（留空 = 总数减去其它判定）")

    rv = p.add_argument_group("反向计算：已知达成率")
    rv.add_argument("--achievement", metavar="A", help="目标达成率（如 99.5 / 100.5）")
    rv.add_argument("--mode", choices=("exact", "range"), default="exact",
                    help="exact（默认）：只列真的能打出该达成率的组合；"
                         "range：列出达成率区间覆盖该值的组合（更快，输入不精确时用）")
    rv.add_argument("--limit", type=int, default=200, metavar="N",
                    help="反向计算最多输出多少组解（默认 200）")

    p.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.chart and args.game:
        die("--chart 与 --game 只能给一个")
    if not args.chart and not args.game:
        interactive(args)
        return 0
    if args.chart:
        chart = load_from_file(args.chart)
        if args.level is not None:
            try:
                want = parse_difficulty(args.level)
            except ValueError as exc:
                die(str(exc))
            if chart.difficulty_index is not None and want != chart.difficulty_index:
                print("[注意] --level 给的是 %s，但谱面文件名里是 %s，按文件名算"
                      % (DIFFICULTY_NAMES[want], DIFFICULTY_NAMES[chart.difficulty_index]),
                      file=sys.stderr)
    else:
        if args.music_id is None:
            die("使用 --game 时必须同时给 --music-id")
        if args.level is None:
            print("[提示] 没有给 --level，按默认难度 3（MASTER）计算"
                  "（0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER）", file=sys.stderr)
        try:
            difficulty = parse_difficulty(args.level if args.level is not None else "master")
        except ValueError as exc:
            die(str(exc))
        chart = load_from_game(args.game, args.music_id, difficulty)

    th = theory_from_chart(chart)
    if th.total_notes == 0:
        die("谱面里没有解析到任何计分音符：%s" % chart.path)

    if args.achievement:
        try:
            target = Fraction(str(args.achievement).rstrip("%"))
        except (ValueError, ZeroDivisionError):
            die("--achievement 需要是数字，如 99.5")
        if target > th.max_achievement:
            die("目标达成率 %s 超过该谱面上限 %s" % (pct(target), pct(th.max_achievement)))
        if target < 0:
            die("目标达成率不能为负")
        run_reverse(chart, th, target, args)
        return 0

    raw = {"cp": args.cp, "perfect": args.perfect, "great": args.great,
           "good": args.good, "miss": args.miss}
    if all(v is None for v in raw.values()):
        die("请给判定数（--cp/--perfect/--great/--good），或用 --achievement 做反向计算；"
            "两个都不给则进入交互模式（需去掉其它参数）")
    run_forward(chart, th, raw, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
