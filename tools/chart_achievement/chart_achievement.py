#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""textDX chartachievement rate / DX Minutes Calculator。

currentTowards：text chart + Number of each decision -> calculateachievement rateAnd DX Minutes
Reverse：text chart + textachievement rate   -> Reverse all feasible decision combinations vs. DX Minutes

Depends only Python standardLibrary。
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

try:  # Avoid when exporting Chinese to the pipeline UnicodeEncodeError
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

LINE = "-" * 60


def pct(value) -> str:
    return "%.4f%%" % float(value)


def die(msg: str, code: int = 2) -> "None":
    print("[error] " + msg, file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------- textchart
def _enrich(chart: Chart, path: str) -> Chart:
    """From the same directory as Music.xml textFulltextFirst name / difficulty / level（textNototextskip）。"""
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
        die("chartfileAbsent：%s" % path)
    return _enrich(parse_ma2(path), path)


def load_from_game(game_path: str, music_id: int, difficulty: int) -> Chart:
    music_dir = find_music_dir(game_path)
    path = chart_path(music_dir, music_id, difficulty)
    if not os.path.isfile(path):
        alt = os.path.join(music_dir, "music%06d" % music_id)
        hint = ""
        if os.path.isdir(alt):
            have = sorted(f for f in os.listdir(alt) if f.lower().endswith(".ma2"))
            hint = "；thetrackcurrenthaschart：" + (", ".join(have) if have else "no")
        die("findNotochart：%s%s" % (path, hint))
    chart = parse_ma2(path)
    chart.music_id = music_id
    chart.difficulty_index = difficulty
    chart.difficulty_name = DIFFICULTY_NAMES[difficulty] if 0 <= difficulty <= 4 else "?"
    chart = _enrich(chart, path)
    chart.difficulty_index = difficulty
    chart.difficulty_name = DIFFICULTY_NAMES[difficulty] if 0 <= difficulty <= 4 else "?"
    return chart


# ------------------------------------------------------------------ Showcase
def print_chart(chart: Chart, th: Theory) -> None:
    print(LINE)
    print("chart")
    print("  file      %s" % chart.path)
    if chart.song_name:
        print("  track      %s" % chart.song_name)
    if chart.music_id is not None:
        print("  text      %d" % chart.music_id)
    if chart.difficulty_name:
        print("  difficulty      %s (%d)" % (chart.difficulty_name.upper(),
                                       chart.difficulty_index if chart.difficulty_index is not None else 0))
    if chart.level_text:
        print("  level      %s" % chart.level_text)
    parts = []
    for g in GROUP_ORDER:
        n = th.counts.get(g, 0)
        if n:
            parts.append("%s %d" % (GROUP_LABEL[g], n))
    print("  note      %s" % " · ".join(parts))
    print("  Total      %d score notes" % th.total_notes)
    if chart.connect_count:
        print("            （There is another %d connected slider nodes，No score）" % chart.connect_count)
    bonus = "  +  critical perfectRewards %d" % th.break_bonus_score if th.break_bonus_score else ""
    print("  theoreticalMinutes    %d%s" % (th.all_perfect_score, bonus))
    print("  theoreticalDX    %d" % th.max_dx)
    print("  textMinutes      %s" % pct(th.max_achievement))
    for w in chart.warnings:
        print("  [text]    %s" % w)
    declared = chart.totals.get("TTM_SCR_SS")
    if declared is not None and declared != th.all_perfect_score:
        print("  [text]    charttextBelt TTM_SCR_SS=%d and the calculated theoretical score %d Inconsistent"
              % (declared, th.all_perfect_score))


def print_forward(chart: Chart, result) -> None:
    th = result.theory
    print(LINE)
    print("Decision input")
    for j in JUDGMENTS:
        print("  %-18s %d" % (JUDGE_LABEL[j], result.judges.get(j, 0)))
    print("  %-18s %d / %d" % ("Total", sum(result.judges.values()), th.total_notes))
    print(LINE)
    print("result")
    print("  achievement rate      %s ~ %s" % (pct(result.achievement_min), pct(result.achievement_max)))
    print("  presstextExampletext  %s" % pct(result.achievement_ref))
    print("  DX Minutes       %d / %d  (%.2f%%)"
          % (result.dx, th.max_dx, 100.0 * result.dx / th.max_dx if th.max_dx else 0.0))
    if result.achievement_min != result.achievement_max:
        print()
        print("  description：When only aggregation decisions are given，achievement rateTaketextin「Which notes」text Great/Good/Miss——")
        print("        Lower bound of interval = textMinutesallfallatweighttextofnoteUp，Upper Realm = allfallatweighttextofnoteUp。")
    print(LINE)


def print_reverse(chart: Chart, outcome) -> None:
    th = outcome["theory"]
    rows = outcome["rows"]
    mode = outcome.get("mode", "exact")
    print(LINE)
    print("textachievement rate %s   [%s]" % (pct(outcome["target"]),
                                   "textmode" if mode == "exact" else "Interval Mode"))
    note = outcome.get("note")
    if note:
        print("  [description] %s" % note)
    if not rows:
        if mode == "exact":
            cap = outcome.get("exact_cap") or 0
            print("  （No solution found in strict validation scope：Bad notes ≤ %d ofgrouptextinnonecantextouttheValueof）" % cap)
            if outcome.get("more_unverified"):
                print("  [note] Bad notes over %d candidate combinations without validation（There's no guarantee there's no solution.）" % cap)
        else:
            print("  （notext：theachievement rateatthisPiecechartUptextNoouttext）")
        print(LINE)
        return
    if mode == "exact":
        print("  Miss  Good  Great  CP+P   CP text      DX Minute Range")
    else:
        print("  Miss  Good  Great  CP+P   CP text      achievement ratetext                 DX Minute Range")
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
        print("  of %d groupcantextout %s ofDetermine Combination（CP+P = Critical Perfect And Perfect Sum）"
              % (len(rows), pct(outcome["target"])))
        cap = outcome.get("exact_cap") or 0
        print("  Strictly verified on a case-by-c Miss+Good+Great ≤ %d ofgrouptext；eachPiecegrouptextalltextofcantextouttheachievement rate" % cap)
        if outcome.get("unverified"):
            print("  [note] There is another %d grouptext（Bad notes over %d Piece）nottext，notColumnstextresult"
                  % (outcome["unverified"], cap))
        if outcome.get("more_unverified"):
            print("  [note] Bad notes over %d candidate combinations without validation（There's no guarantee there's no solution.）" % cap)
    else:
        print("  of %d grouptextgrouptext（CP+P = Critical Perfect And Perfect Sum）" % len(rows))
        print("  Interval Mode：Only guarantee that the achievement rate falls within this range，It is not guaranteed that the target value will be hit exactly")
    if outcome["truncated"]:
        print("  [note] resulttext --limit / textUptextTruncation，There may be more combinations")
    print("  DX Minutes = 3*CP + 2*Perfect + 1*Great；CP textUptext，DX The higher the score,")
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


# ------------------------------------------------------------------ Interaction
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
            print("  pleasetextnumber")


def interactive(args) -> None:
    print("=" * 60)
    print("textDX chartachievement rate / DX Minutes countcalculatetext")
    print("=" * 60)
    chart = None
    while chart is None:
        mode = ask("charttext：1) .ma2 file path  2) text + musicid  [1]: ", "1")
        if mode.startswith("2"):
            game = ask("text（Sinmai_Data text）: ")
            if not game:
                continue
            mid = ask_int("musicid: ")
            if mid is None:
                continue
            diff = ask("difficulty 0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER  [3]: ", "3")
            try:
                chart = load_from_game(game, mid, parse_difficulty(diff))
            except SystemExit:
                chart = None
        else:
            path = ask("chartfile path: ")
            if not path:
                continue
            try:
                chart = load_from_file(path)
            except SystemExit:
                chart = None
    th = theory_from_chart(chart)
    print_chart(chart, th)

    mode = ask("countcalculatemode：1) Known decision number calculation achievement rate  2) Known Achievement Rate Recalculation Judgments  [1]: ", "1")
    if mode.startswith("2"):
        while True:
            raw = ask("textachievement rate（As 99.5 or 100.5）: ")
            if not raw:
                return
            try:
                target = Fraction(raw.rstrip("%"))
                break
            except (ValueError, ZeroDivisionError):
                print("  pleasetextnumbertext")
        mode = ask("Inverse calculation method：1) text（Only the combination that can really play the completion rate can be listed）  2) Interval（The number of judgments is only used for estimation）  [1]: ", "1")
        args.mode = "range" if mode.startswith("2") else "exact"
        run_reverse(chart, th, target, args)
    else:
        values = {}
        for j in JUDGMENTS:
            if j == "miss":
                continue
            values[j] = ask_int("  %s number [0]: " % JUDGE_LABEL[j], 0) or 0
        values["miss"] = ask_int("  Miss number（leave blank = Total minus the above decision）: ")
        run_forward(chart, th, values, args)


# ------------------------------------------------------------------ text
def normalize_judges(th: Theory, raw: Dict[str, Optional[int]]) -> Dict[str, int]:
    given = {j: int(raw.get(j) or 0) for j in JUDGMENTS}
    if raw.get("miss") is None:
        given["miss"] = th.total_notes - sum(given[j] for j in JUDGMENTS if j != "miss")
    if given["miss"] < 0:
        die("CP+Perfect+Great+Good Total %d textnoteTotal %d"
            % (sum(given[j] for j in JUDGMENTS if j != "miss"), th.total_notes))
    total = sum(given.values())
    if total != th.total_notes:
        die("Sum of the judgments %d and total number of notes %d Inconsistent（Miss pleaseleave blanktext）" % (total, th.total_notes))
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
        description="textDX chartachievement rate / DX Minutes Calculator（currentTowardscountcalculate + byachievement ratetextcalculateDeterminenumber）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""textExample:
  # directlytextchartfile，currentTowardscountcalculate
  python chart_achievement.py --chart "D:\\SDGB2026\\Package\\Sinmai_Data\\StreamingAssets\\A000\\music\\music000008\\000008_03.ma2" --cp 290 --perfect 10 --great 2

  # text + musicid + difficulty（difficultyusetextinofnumbertext：0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER）
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --cp 300 --perfect 2

  # byachievement ratetextcalculateDetermine Combination（textmode：Only columns can really print the combination of values）
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --achievement 99.5

  # When the number of judgments is only estimated，useInterval Mode
  python chart_achievement.py --game "D:\\SDGB2026\\Package\\Sinmai_Data" --music-id 8 --level 3 --achievement 99.5 --mode range
""")
    src = p.add_argument_group("charttext（Choose one of the two）")
    src.add_argument("--chart", metavar="PATH", help=".ma2 chartfile path")
    src.add_argument("--game", metavar="PATH", help="text（Sinmai_Data / StreamingAssets / A000 / music Both）")
    src.add_argument("--music-id", type=int, metavar="ID", help="tracktext（text --game Use）")
    src.add_argument("--level", "--difficulty", dest="level", default=None, metavar="D",
                     help="chartdifficulty，usetextinofnumbertext：0=BASIC 1=ADVANCED 2=EXPERT "
                          "3=MASTER 4=RE:MASTER（You can also write your name directly；default 3=MASTER）")

    fw = p.add_argument_group("currentTowardscountcalculate：Number of known decisions")
    fw.add_argument("--cp", type=int, metavar="N", help="Critical Perfect Number")
    fw.add_argument("--perfect", type=int, metavar="N", help="Perfect Number")
    fw.add_argument("--great", type=int, metavar="N", help="Great Number")
    fw.add_argument("--good", type=int, metavar="N", help="Good Number")
    fw.add_argument("--miss", type=int, metavar="N", help="Miss Number（leave blank = Total minus other judgments）")

    rv = p.add_argument_group("Reverse calculation：Known attainment rate")
    rv.add_argument("--achievement", metavar="A", help="textachievement rate（As 99.5 / 100.5）")
    rv.add_argument("--mode", choices=("exact", "range"), default="exact",
                    help="exact（default）：Only the combination that can really play the completion rate is listed；"
                         "range：List the combinations of attainment intervals that cover this value（text，textNotexttimeuse）")
    rv.add_argument("--limit", type=int, default=200, metavar="N",
                    help="Reverse calculate how many sets of solutions to output at most（default 200）")

    p.add_argument("--json", action="store_true", help="in JSON textoutresult")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.chart and args.game:
        die("--chart And --game Only one can be given")
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
                print("[note] --level textofis %s，But in the spectrum file name is %s，pressfileFirst namecalculate"
                      % (DIFFICULTY_NAMES[want], DIFFICULTY_NAMES[chart.difficulty_index]),
                      file=sys.stderr)
    else:
        if args.music_id is None:
            die("Use --game timeMust be given at the same time --music-id")
        if args.level is None:
            print("[text] nonetext --level，pressdefaultdifficulty 3（MASTER）countcalculate"
                  "（0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER）", file=sys.stderr)
        try:
            difficulty = parse_difficulty(args.level if args.level is not None else "master")
        except ValueError as exc:
            die(str(exc))
        chart = load_from_game(args.game, args.music_id, difficulty)

    th = theory_from_chart(chart)
    if th.total_notes == 0:
        die("chartinnoneparsetoAnycountMinutesnote：%s" % chart.path)

    if args.achievement:
        try:
            target = Fraction(str(args.achievement).rstrip("%"))
        except (ValueError, ZeroDivisionError):
            die("--achievement needisnumbertext，As 99.5")
        if target > th.max_achievement:
            die("textachievement rate %s textthechartUptext %s" % (pct(target), pct(th.max_achievement)))
        if target < 0:
            die("textachievement rateCannot betext")
        run_reverse(chart, th, target, args)
        return 0

    raw = {"cp": args.cp, "perfect": args.perfect, "great": args.great,
           "good": args.good, "miss": args.miss}
    if all(v is None for v in raw.values()):
        die("pleasetextDeterminenumber（--cp/--perfect/--great/--good），or with --achievement Do the reverse calculation；"
            "If neither is given, enter interactive mode（textRemovetextParameter）")
    run_forward(chart, th, raw, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
