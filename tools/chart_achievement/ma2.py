# -*- coding: utf-8 -*-
"""maimai DX (maimai DX) .ma2 chartparse.

text -> note ofCorrespondingDecompile source code
  source/Assembly-CSharp/Manager/Ma2fileRecordID.cs
  (s_Ma2fileRecord_Data in Ma2Category.MA2_Note of 102 itemrecord)
countCategoriesofDivideReprint
  source/Assembly-CSharp/Manager/GamePlayManager.cs  NoteType2ScoreType()
theoreticalMinutesweight
  source/Assembly-CSharp/Manager/NotesReader.cs  calcTotal()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------- countMinutesweight
WEIGHT_TAP = 500      # TAP / XTP / STR / XST / TTP(Touch And Tap Same as 500)
WEIGHT_HOLD = 1000    # HLD / XHO / THO
WEIGHT_SLIDE = 1500   # SI_ SCL SCR SUL SUR SSL SSR SV_ SXL SXR SLL SLR SF_
WEIGHT_BREAK = 2500   # BRK / BST / BRTAP / BRHLD / BRSTR / BRSI_ ... and ExBreak text
BREAK_BONUS_THEORY = 100   # eachPiececritical perfect(Break)oftheoreticalReward Points

CATEGORY_TAP = "Tap"
CATEGORY_HOLD = "Hold"
CATEGORY_SLIDE = "Slide"
CATEGORY_BREAK = "Break"
CATEGORY_CONNECT = "ConnectSlide"

CATEGORY_ORDER = (CATEGORY_TAP, CATEGORY_HOLD, CATEGORY_SLIDE, CATEGORY_BREAK)
CATEGORY_WEIGHT = {
    CATEGORY_TAP: WEIGHT_TAP,
    CATEGORY_HOLD: WEIGHT_HOLD,
    CATEGORY_SLIDE: WEIGHT_SLIDE,
    CATEGORY_BREAK: WEIGHT_BREAK,
}
CATEGORY_LABEL = {
    CATEGORY_TAP: "Tap/Touch",
    CATEGORY_HOLD: "Hold",
    CATEGORY_SLIDE: "Slide",
    CATEGORY_BREAK: "Break",
}

# ------------------------------------------------- ma2 text -> NotesTypeID.Def
NOTE_COMMAND_TYPES: Dict[str, str] = {
    # --- current ---
    "TAP": "Begin", "BRK": "Break", "XTP": "ExTap", "HLD": "Hold", "XHO": "ExHold",
    "STR": "Star", "BST": "BreakStar", "XST": "ExStar",
    "TTP": "TouchTap", "THO": "TouchHold",
    "SI_": "Slide", "SCL": "Slide", "SCR": "Slide", "SUL": "Slide", "SUR": "Slide",
    "SSL": "Slide", "SSR": "Slide", "SV_": "Slide", "SXL": "Slide", "SXR": "Slide",
    "SLL": "Slide", "SLR": "Slide", "SF_": "Slide",
    # --- first name(datainrealat)---
    "NMTAP": "Begin", "BRTAP": "Break", "EXTAP": "ExTap", "BXTAP": "ExBreakTap",
    "NMHLD": "Hold", "BRHLD": "BreakHold", "EXHLD": "ExHold", "BXHLD": "ExBreakHold",
    "NMSTR": "Star", "BRSTR": "BreakStar", "EXSTR": "ExStar", "BXSTR": "ExBreakStar",
    "NMTTP": "TouchTap", "NMTHO": "TouchHold",
    "NMSI_": "Slide", "BRSI_": "BreakSlide", "EXSI_": "ExSlide", "BXSI_": "ExBreakSlide", "CNSI_": "ConnectSlide",
    "NMSCL": "Slide", "BRSCL": "BreakSlide", "EXSCL": "ExSlide", "BXSCL": "ExBreakSlide", "CNSCL": "ConnectSlide",
    "NMSCR": "Slide", "BRSCR": "BreakSlide", "EXSCR": "ExSlide", "BXSCR": "ExBreakSlide", "CNSCR": "ConnectSlide",
    "NMSUL": "Slide", "BRSUL": "BreakSlide", "EXSUL": "ExSlide", "BXSUL": "ExBreakSlide", "CNSUL": "ConnectSlide",
    "NMSUR": "Slide", "BRSUR": "BreakSlide", "EXSUR": "ExSlide", "BXSUR": "ExBreakSlide", "CNSUR": "ConnectSlide",
    "NMSSL": "Slide", "BRSSL": "BreakSlide", "EXSSL": "ExSlide", "BXSSL": "ExBreakSlide", "CNSSL": "ConnectSlide",
    "NMSSR": "Slide", "BRSSR": "BreakSlide", "EXSSR": "ExSlide", "BXSSR": "ExBreakSlide", "CNSSR": "ConnectSlide",
    "NMSV_": "Slide", "BRSV_": "BreakSlide", "EXSV_": "ExSlide", "BXSV_": "ExBreakSlide", "CNSV_": "ConnectSlide",
    "NMSXL": "Slide", "BRSXL": "BreakSlide", "EXSXL": "ExSlide", "BXSXL": "ExBreakSlide", "CNSXL": "ConnectSlide",
    "NMSXR": "Slide", "BRSXR": "BreakSlide", "EXSXR": "ExSlide", "BXSXR": "ExBreakSlide", "CNSXR": "ConnectSlide",
    "NMSLL": "Slide", "BRSLL": "BreakSlide", "EXSLL": "ExSlide", "BXSLL": "ExBreakSlide", "CNSLL": "ConnectSlide",
    "NMSLR": "Slide", "BRSLR": "BreakSlide", "EXSLR": "ExSlide", "BXSLR": "ExBreakSlide", "CNSLR": "ConnectSlide",
    "NMSF_": "Slide", "BRSF_": "BreakSlide", "EXSF_": "ExSlide", "BXSF_": "ExBreakSlide", "CNSF_": "ConnectSlide",
}

_BREAK_DEFS = frozenset((
    "Break", "BreakHold", "BreakStar", "BreakSlide",
    "ExBreakTap", "ExBreakHold", "ExBreakStar", "ExBreakSlide",
))
_SLIDE_DEFS = frozenset(("Slide", "BreakSlide", "ExSlide", "ExBreakSlide"))
_HOLD_DEFS = frozenset(("Hold", "BreakHold", "ExHold", "ExBreakHold", "TouchHold"))
_TOUCH_DEFS = frozenset(("TouchTap", "TouchHold"))
_CONNECT_DEFS = frozenset(("ConnectSlide",))

# The timing of the decision is only Critical / TooLate of EX note(ExTap/ExStar/ExBreakTap/ExBreakStar)
EX_DEFS = frozenset(("ExTap", "ExStar", "ExBreakTap", "ExBreakStar"))

# ---------------------------------------------------------------- notegroup
# "notegroup"= countMinutesforfullrelatedSameofOnenote:weight,Optional Determination,Missed Gear,critical perfectRewardsfileBitallSame.
# Classification by(Decompile source code):
#   * countCategories NoteScore.EScoreType by GamePlayManager.NoteType2ScoreType() Decision
#     (Break text -> Break,item -> Slide,hold -> Hold,Remaining -> Tap/Touch)
#   * Determine timing table NoteJudge.EJudgeType byEachnoteDecision:
#       TapNote/StarNote   -> Tap(or ExNote time ExTap)
#       HoldNote/BreakHoldNote/TouchHoldC -> holdsettlement JudgeHoldTotal(Irrespective 2nd/3rd file)
#       SlideRoot/SlideFan -> SlideOut(Irrespective 2nd/3rd file,There is also no non- Critical of Perfect)
#       BreakNote/BreakStarNote -> Break text(Great has 1250/1500/2000 Third Grade)
#   * ExTap Determination table [-9,-9,-9,-9,-9,-9,-9,0,9,9,9,9,9,9,9] Make Not Critical offileBitAllNo
#     -> ExTap/ExStar(Contains ExBreak )Only Critical or Miss
#   * ExHold/ExBreakHold ofFor head ExTap But the results will have to go through JudgeHoldTotal
#     Ultimately still available Critical/Perfect/Great/Good/Miss -> vs Normal Hold / BreakHold relatedSame
#   * ExSlide / ExBreakSlide of JudgeType Constantly SlideOut,And isBreak() Excluding ExBreakSlide
#     -> countMinutesvs Normal Slide Exact match(datainthisTwoAppearancecountfor 0)
GROUP_TAP = "tap"                  # TAP NMTAP STR NMSTR TTP NMTTP          weight 500
GROUP_HOLD = "hold"                # HLD NMHLD XHO EXHLD THO NMTHO          weight 1000
GROUP_SLIDE = "slide"              # SI_ SCL SCR SUL SUR SSL SSR SV_ SXL SXR SLL SLR SF_ + NM/EX/CN Variants  weight 1500
GROUP_BREAK = "break"              # BRK BRTAP BST BRSTR                    weight 2500,Great Third Grade,Perfect Reward two tiers
GROUP_BREAK_FLAT = "break_flat"    # BRHLD BXHLD                            weight 2500,holdDetermine,No Gear Break
GROUP_BREAK_SLIDE = "break_slide"  # BRSI_ BRSCL BRSCR BRSUL BRSUR BRSSL BRSSR BRSV_ BRSXL BRSXR BRSLL BRSLR BRSF_
GROUP_EX = "ex"                    # XTP EXTAP XST EXSTR                    weight 500,Only Critical / Miss
GROUP_EX_BREAK = "ex_break"        # BXTAP BXSTR                            weight 2500,Only Critical / Miss

GROUP_ORDER = (GROUP_TAP, GROUP_HOLD, GROUP_SLIDE, GROUP_BREAK,
               GROUP_BREAK_FLAT, GROUP_BREAK_SLIDE, GROUP_EX, GROUP_EX_BREAK)
GROUP_LABEL = {
    GROUP_TAP: "Tap/Star/Touch",
    GROUP_HOLD: "Hold",
    GROUP_SLIDE: "Slide",
    GROUP_BREAK: "Break",
    GROUP_BREAK_FLAT: "Break(holdDetermine)",
    GROUP_BREAK_SLIDE: "Break(itemDetermine)",
    GROUP_EX: "EX Tap/Star",
    GROUP_EX_BREAK: "EX Break",
}
GROUP_WEIGHT = {
    GROUP_TAP: WEIGHT_TAP,
    GROUP_HOLD: WEIGHT_HOLD,
    GROUP_SLIDE: WEIGHT_SLIDE,
    GROUP_BREAK: WEIGHT_BREAK,
    GROUP_BREAK_FLAT: WEIGHT_BREAK,
    GROUP_BREAK_SLIDE: WEIGHT_BREAK,
    GROUP_EX: WEIGHT_TAP,
    GROUP_EX_BREAK: WEIGHT_BREAK,
}
GROUP_IS_BREAK = frozenset((GROUP_BREAK, GROUP_BREAK_FLAT, GROUP_BREAK_SLIDE, GROUP_EX_BREAK))

_GROUP_BY_DEF = {
    "Begin": GROUP_TAP, "Star": GROUP_TAP, "TouchTap": GROUP_TAP,
    "Hold": GROUP_HOLD, "ExHold": GROUP_HOLD, "TouchHold": GROUP_HOLD,
    "Slide": GROUP_SLIDE, "ExSlide": GROUP_SLIDE, "ExBreakSlide": GROUP_SLIDE,
    "Break": GROUP_BREAK, "BreakStar": GROUP_BREAK,
    "BreakHold": GROUP_BREAK_FLAT, "ExBreakHold": GROUP_BREAK_FLAT,
    "BreakSlide": GROUP_BREAK_SLIDE,
    "ExTap": GROUP_EX, "ExStar": GROUP_EX,
    "ExBreakTap": GROUP_EX_BREAK, "ExBreakStar": GROUP_EX_BREAK,
}
_CATEGORY_BY_GROUP = {
    GROUP_TAP: CATEGORY_TAP, GROUP_HOLD: CATEGORY_HOLD, GROUP_SLIDE: CATEGORY_SLIDE,
    GROUP_BREAK: CATEGORY_BREAK, GROUP_BREAK_FLAT: CATEGORY_BREAK,
    GROUP_BREAK_SLIDE: CATEGORY_BREAK, GROUP_EX: CATEGORY_TAP, GROUP_EX_BREAK: CATEGORY_BREAK,
}


def note_group(def_name: str) -> Optional[str]:
    """NotesTypeID.Def First name -> notegroup;continueitemetcNo scorenotereturns None."""
    return _GROUP_BY_DEF.get(def_name)


def score_category(def_name: str) -> Optional[str]:
    """Reprint GamePlayManager.NoteType2ScoreType() ofCategories(Tap/Hold/Slide/Break)."""
    grp = note_group(def_name)
    if grp is None:
        return None
    return _CATEGORY_BY_GROUP[grp]


# ------------------------------------------------------------------ chartObject
@dataclass
class Chart:
    path: str = "<memory>"
    command_counts: Dict[str, int] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    group_counts: Dict[str, int] = field(default_factory=dict)
    connect_count: int = 0
    header: Dict[str, str] = field(default_factory=dict)
    totals: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    # External Supplemental Information(mode)
    music_id: Optional[int] = None
    difficulty_index: Optional[int] = None
    difficulty_name: Optional[str] = None
    song_name: Optional[str] = None
    level_text: Optional[str] = None
    max_notes_xml: Optional[int] = None

    @property
    def total_notes(self) -> int:
        """countMinutesnoteTotal N(Connection slider not included)."""
        return sum(self.group_counts.get(g, 0) for g in GROUP_ORDER)

    @property
    def declared_total(self) -> Optional[int]:
        return self.totals.get("T_NUM_ALL")

    def counts(self) -> Dict[str, int]:
        """pressnotegroupsystemcount(For Scoring Models)."""
        return {g: self.group_counts.get(g, 0) for g in GROUP_ORDER}

    def category_summary(self) -> Dict[str, int]:
        return {c: self.category_counts.get(c, 0) for c in CATEGORY_ORDER}


def parse_ma2(path: str) -> Chart:
    with open(path, "rb") as fp:
        raw = fp.read()
    chart = parse_ma2_bytes(raw, path)
    return chart


def parse_ma2_bytes(raw: bytes, path: str = "<memory>") -> Chart:
    chart = Chart(path=path)
    text = raw.decode("latin1")
    unknown = set()
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) == 1:
            parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        args = parts[1:]

        def_name = NOTE_COMMAND_TYPES.get(cmd)
        if def_name is not None:
            chart.command_counts[cmd] = chart.command_counts.get(cmd, 0) + 1
            grp = note_group(def_name)
            if grp is None:
                chart.connect_count += 1
            else:
                chart.group_counts[grp] = chart.group_counts.get(grp, 0) + 1
                cat = score_category(def_name)
                chart.category_counts[cat] = chart.category_counts.get(cat, 0) + 1
            continue

        if cmd.startswith("T_") or cmd.startswith("TTM_"):
            if args:
                try:
                    chart.totals[cmd] = int(args[0])
                except ValueError:
                    pass
            continue

        if cmd not in chart.header and args:
            chart.header[cmd] = "\t".join(args)
        elif not args and cmd.isupper() and len(cmd) > 2:
            unknown.add(cmd)

    declared = chart.declared_total
    if declared is not None and declared != chart.total_notes:
        chart.warnings.append(
            "T_NUM_ALL=%d Number of scoring notes parsed with %d Inconsistent" % (declared, chart.total_notes)
        )
    return chart


# ------------------------------------------------------------ parse
DIFFICULTY_NAMES = ("Basic", "Advanced", "Expert", "Master", "Re:Master")
_DIFFICULTY_ALIASES = {
    "basic": 0, "bas": 0, "bsc": 0, "0": 0, "00": 0,
    "advanced": 1, "adv": 1, "1": 1, "01": 1,
    "expert": 2, "exp": 2, "2": 2, "02": 2,
    "master": 3, "mas": 3, "mst": 3, "3": 3, "03": 3,
    "remaster": 4, "re:master": 4, "remas": 4, "re": 4, "4": 4, "04": 4,
}


def parse_difficulty(text) -> int:
    if isinstance(text, int):
        if 0 <= text <= 4:
            return text
        raise ValueError("difficultynone.Must be 0~4")
    key = str(text).strip().lower()
    if key in _DIFFICULTY_ALIASES:
        return _DIFFICULTY_ALIASES[key]
    raise ValueError("noofdifficulty:%s(Available 0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER,"
                     "or just write your name)" % text)


def find_music_dir(game_path: str) -> str:
    """put"text / Sinmai_Data / StreamingAssets / A000"allReturnedOneto A000/music."""
    p = os.path.abspath(os.path.expanduser(game_path))
    if not os.path.isdir(p):
        raise FileNotFoundError("Absent:%s" % p)
    if os.path.basename(p).lower() == "music" and os.path.basename(os.path.dirname(p)).upper() == "A000":
        return p
    candidates = [
        p,
        os.path.join(p, "music"),
        os.path.join(p, "A000", "music"),
        os.path.join(p, "StreamingAssets", "A000", "music"),
        os.path.join(p, "Sinmai_Data", "StreamingAssets", "A000", "music"),
        os.path.join(p, "Package", "Sinmai_Data", "StreamingAssets", "A000", "music"),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.basename(c).lower() == "music":
            return c
    raise FileNotFoundError("at %s Not found under A000/music text" % p)


def music_dir_path(music_dir: str, music_id: int) -> str:
    return os.path.join(music_dir, "music%06d" % music_id)


def chart_path(music_dir: str, music_id: int, difficulty: int) -> str:
    return os.path.join(music_dir_path(music_dir, music_id), "%06d_%02d.ma2" % (music_id, difficulty))


def parse_music_xml(path: str) -> Dict[str, object]:
    """readTake Music.xml(Only use standard libraries),Take out song names and difficulty information."""
    import xml.etree.ElementTree as ET

    info: Dict[str, object] = {"notes": []}
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "notes": []}

    def text_of(node, tag):
        child = node.find(tag)
        if child is None:
            return None
        if child.text and child.text.strip():
            return child.text.strip()
        sub = child.find("str")
        if sub is not None and sub.text and sub.text.strip():
            return sub.text.strip()
        return None

    info["name"] = text_of(root, "name")
    info["artist"] = text_of(root, "artistName")
    info["genre"] = text_of(root, "genreName")
    info["bpm"] = text_of(root, "bpm")
    notes_data = root.find("notesData")
    notes = []
    if notes_data is not None:
        for node in notes_data.findall("Notes"):
            f = node.find("file/path")
            notes.append({
                "file": f.text.strip() if f is not None and f.text else None,
                "level": text_of(node, "level"),
                "levelDecimal": text_of(node, "levelDecimal"),
                "musicLevelID": text_of(node, "musicLevelID"),
                "maxNotes": text_of(node, "maxNotes"),
                "designer": text_of(node, "notesDesigner"),
                "isEnable": text_of(node, "isEnable"),
            })
    info["notes"] = notes
    return info


def level_display(level, level_decimal) -> str:
    """12 + levelDecimal 4 -> '12+';10 + 2 -> '10+';7 + 0 -> '7'."""
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return ""
    try:
        dec = int(level_decimal or 0)
    except (TypeError, ValueError):
        dec = 0
    if dec >= 3:
        return "%d+" % lv
    if dec > 0:
        return "%d.%d" % (lv, dec)
    return "%d" % lv
