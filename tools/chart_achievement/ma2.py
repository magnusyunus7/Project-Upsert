# -*- coding: utf-8 -*-
"""舞萌DX (maimai DX) .ma2 谱面解析。

指令 -> 音符类型 的对应表来自反编译源码
  source/Assembly-CSharp/Manager/Ma2fileRecordID.cs
  （s_Ma2fileRecord_Data 里 Ma2Category.MA2_Note 的 102 条记录）
计分类别的划分复刻
  source/Assembly-CSharp/Manager/GamePlayManager.cs  NoteType2ScoreType()
理论分权重来自
  source/Assembly-CSharp/Manager/NotesReader.cs  calcTotal()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------- 计分权重
WEIGHT_TAP = 500      # TAP / XTP / STR / XST / TTP（Touch 与 Tap 同为 500）
WEIGHT_HOLD = 1000    # HLD / XHO / THO
WEIGHT_SLIDE = 1500   # SI_ SCL SCR SUL SUR SSL SSR SV_ SXL SXR SLL SLR SF_
WEIGHT_BREAK = 2500   # BRK / BST / BRTAP / BRHLD / BRSTR / BRSI_ ... 以及 ExBreak 系
BREAK_BONUS_THEORY = 100   # 每个绝赞(Break)的理论奖励分

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

# ------------------------------------------------- ma2 指令 -> NotesTypeID.Def
NOTE_COMMAND_TYPES: Dict[str, str] = {
    # --- 现行指令 ---
    "TAP": "Begin", "BRK": "Break", "XTP": "ExTap", "HLD": "Hold", "XHO": "ExHold",
    "STR": "Star", "BST": "BreakStar", "XST": "ExStar",
    "TTP": "TouchTap", "THO": "TouchHold",
    "SI_": "Slide", "SCL": "Slide", "SCR": "Slide", "SUL": "Slide", "SUR": "Slide",
    "SSL": "Slide", "SSR": "Slide", "SV_": "Slide", "SXL": "Slide", "SXR": "Slide",
    "SLL": "Slide", "SLR": "Slide", "SF_": "Slide",
    # --- 旧式别名（游戏数据里真实存在）---
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

# 判定时机只有 Critical / TooLate 的 EX 音符（ExTap/ExStar/ExBreakTap/ExBreakStar）
EX_DEFS = frozenset(("ExTap", "ExStar", "ExBreakTap", "ExBreakStar"))

# ---------------------------------------------------------------- 音符组
# 「音符组」= 计分行为完全相同的一类音符：权重、可选判定、失分档位、绝赞奖励档位都一样。
# 划分依据（反编译源码）：
#   * 计分类型 NoteScore.EScoreType 由 GamePlayManager.NoteType2ScoreType() 决定
#     （Break 系 -> Break，滑条 -> Slide，长按 -> Hold，其余 -> Tap/Touch）
#   * 判定时机表 NoteJudge.EJudgeType 由各音符类决定：
#       TapNote/StarNote   -> Tap（或 ExNote 时 ExTap）
#       HoldNote/BreakHoldNote/TouchHoldC -> 长按结算 JudgeHoldTotal（不分 2nd/3rd 档）
#       SlideRoot/SlideFan -> SlideOut（不分 2nd/3rd 档，也没有非 Critical 的 Perfect）
#       BreakNote/BreakStarNote -> Break 表（Great 有 1250/1500/2000 三档）
#   * ExTap 判定表 [-9,-9,-9,-9,-9,-9,-9,0,9,9,9,9,9,9,9] 使非 Critical 的档位全部不可达
#     -> ExTap/ExStar（含 ExBreak 版）只能 Critical 或 Miss
#   * ExHold/ExBreakHold 的头部用 ExTap 表，但结果还要过 JudgeHoldTotal 重映射，
#     最终仍可得到 Critical/Perfect/Great/Good/Miss -> 与普通 Hold / BreakHold 相同
#   * ExSlide / ExBreakSlide 的 JudgeType 恒为 SlideOut，且 isBreak() 不含 ExBreakSlide
#     -> 计分与普通 Slide 完全一致（游戏数据里这两种指令出现次数为 0）
GROUP_TAP = "tap"                  # TAP NMTAP STR NMSTR TTP NMTTP          权重 500
GROUP_HOLD = "hold"                # HLD NMHLD XHO EXHLD THO NMTHO          权重 1000
GROUP_SLIDE = "slide"              # SI_ SCL SCR SUL SUR SSL SSR SV_ SXL SXR SLL SLR SF_ + NM/EX/CN 变体  权重 1500
GROUP_BREAK = "break"              # BRK BRTAP BST BRSTR                    权重 2500，Great 三档、Perfect 奖励两档
GROUP_BREAK_FLAT = "break_flat"    # BRHLD BXHLD                            权重 2500，长按判定，不分档
GROUP_BREAK_SLIDE = "break_slide"  # BRSI_ BRSCL BRSCR BRSUL BRSUR BRSSL BRSSR BRSV_ BRSXL BRSXR BRSLL BRSLR BRSF_
GROUP_EX = "ex"                    # XTP EXTAP XST EXSTR                    权重 500，只能 Critical / Miss
GROUP_EX_BREAK = "ex_break"        # BXTAP BXSTR                            权重 2500，只能 Critical / Miss

GROUP_ORDER = (GROUP_TAP, GROUP_HOLD, GROUP_SLIDE, GROUP_BREAK,
               GROUP_BREAK_FLAT, GROUP_BREAK_SLIDE, GROUP_EX, GROUP_EX_BREAK)
GROUP_LABEL = {
    GROUP_TAP: "Tap/Star/Touch",
    GROUP_HOLD: "Hold",
    GROUP_SLIDE: "Slide",
    GROUP_BREAK: "Break",
    GROUP_BREAK_FLAT: "Break(长按判定)",
    GROUP_BREAK_SLIDE: "Break(滑条判定)",
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
    """NotesTypeID.Def 名 -> 音符组；接续滑条等不计分音符返回 None。"""
    return _GROUP_BY_DEF.get(def_name)


def score_category(def_name: str) -> Optional[str]:
    """复刻 GamePlayManager.NoteType2ScoreType() 的粗分类（Tap/Hold/Slide/Break）。"""
    grp = note_group(def_name)
    if grp is None:
        return None
    return _CATEGORY_BY_GROUP[grp]


# ------------------------------------------------------------------ 谱面对象
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
    # 外部补充的信息（游戏路径模式）
    music_id: Optional[int] = None
    difficulty_index: Optional[int] = None
    difficulty_name: Optional[str] = None
    song_name: Optional[str] = None
    level_text: Optional[str] = None
    max_notes_xml: Optional[int] = None

    @property
    def total_notes(self) -> int:
        """计分音符总数 N（不含接续滑条）。"""
        return sum(self.group_counts.get(g, 0) for g in GROUP_ORDER)

    @property
    def declared_total(self) -> Optional[int]:
        return self.totals.get("T_NUM_ALL")

    def counts(self) -> Dict[str, int]:
        """按音符组统计（供计分模型使用）。"""
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
            "T_NUM_ALL=%d 与解析出的计分音符数 %d 不一致" % (declared, chart.total_notes)
        )
    return chart


# ------------------------------------------------------------ 游戏路径解析
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
        raise ValueError("难度序号必须是 0~4")
    key = str(text).strip().lower()
    if key in _DIFFICULTY_ALIASES:
        return _DIFFICULTY_ALIASES[key]
    raise ValueError("无法识别的难度：%s（可用 0=BASIC 1=ADVANCED 2=EXPERT 3=MASTER 4=RE:MASTER，"
                     "或直接写名字）" % text)


def find_music_dir(game_path: str) -> str:
    """把「游戏根目录 / Sinmai_Data / StreamingAssets / A000」都归一化到 A000/music。"""
    p = os.path.abspath(os.path.expanduser(game_path))
    if not os.path.isdir(p):
        raise FileNotFoundError("路径不存在：%s" % p)
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
    raise FileNotFoundError("在 %s 下找不到 A000/music 目录" % p)


def music_dir_path(music_dir: str, music_id: int) -> str:
    return os.path.join(music_dir, "music%06d" % music_id)


def chart_path(music_dir: str, music_id: int, difficulty: int) -> str:
    return os.path.join(music_dir_path(music_dir, music_id), "%06d_%02d.ma2" % (music_id, difficulty))


def parse_music_xml(path: str) -> Dict[str, object]:
    """读取 Music.xml（只用标准库），取出曲名与各难度信息。"""
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
    """12 + levelDecimal 4 -> '12+'；10 + 2 -> '10+'；7 + 0 -> '7'。"""
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
