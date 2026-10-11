# -*- coding: utf-8 -*-
"""maimai DX achievement rate / DX Minute Calculation Model (press note group).

achievement rate (source/Assembly-CSharp/Manager/GameScoreList. cs:1238-1310 CalcUpdate())::

  Achivement = num / _allPerfectScore * 100 + num2 / _breakBonusScore

where num = Σ score NoteScore. GetJudgeScore (timing, count Categories)
   num2 = Σ critical perfect Reward Points (Only the overwhelmingly acclaimed notes have) NoteScore. GetJudgeScore (timing, BreakBonus)
   _allPerfectScore = Σ each Piece note of weight (NotesReader. calcTotal())
   _breakBonusScore = 100 × critical perfect note number
Minutes = 101.0000%(hascritical perfect)/ 100.0000%(nocritical perfect).

DX Minutes(JudgeResultSt. UpdateScore + NoteJudge. ConvertJudge)::

  DX = 3×CriticalPerfect + 2×Perfect + 1×Great(Good/Miss No extra points)

Not related to note type, theoretical DX = 3 × countMinutesnotenumber.

must
--------
* notepress"group"Divide, Exactly the same scoring behavior within the same group(weight, Optional Determination, Missed Gear, critical perfectRewardsfileBit).
* critical perfect(Break )of Great has 3 fileLost points, Perfect Rewards include 2 file(75 / 50), itemDetermineofcritical perfect
 none Perfect file, holdDetermineofcritical perfectNo Gear Break; EX Determine(ExTap )Only Critical or Miss.
* Therefore,"eachDetermineofnumber"And it's not the only thing that determines the rate of: achievement ratethisDeterminefallatWhich notesUp.
 useMinimum fee streamachievement rateofUpLower Boundary, and can be strictly judged"canNoexactlyoutitemachievement rate".
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

from ma2 import (GROUP_BREAK, GROUP_BREAK_FLAT, GROUP_BREAK_SLIDE, GROUP_EX,
                 GROUP_EX_BREAK, GROUP_HOLD, GROUP_LABEL, GROUP_ORDER,
                 GROUP_SLIDE, GROUP_TAP, GROUP_WEIGHT, Chart)

# ------------------------------------------------------------------ Constant
JUDGMENTS = ("cp", "perfect", "great", "good", "miss")
JUDGE_LABEL = {
    "cp": "Critical Perfect",
    "perfect": "Perfect",
    "great": "Great",
    "good": "Good",
    "miss": "Miss",
}
DX_PER = {"cp": 3, "perfect": 2, "great": 1, "good": 0, "miss": 0}

#: each Piece note group in, Determine actual can Appearance of (Lost points, critical perfect Reward Points) group
#: Lost points = the note weight - actual Score; Reward points are only for praise (count Categories Break) note at.
GROUP_OPTIONS: Dict[str, Dict[str, Tuple[Tuple[int, int], ...]]] = {
    GROUP_TAP: {
        "cp": ((0, 0),),
        "perfect": ((0, 0),),
        "great": ((100, 0),),      # 400
        "good": ((250, 0),),       # 250
        "miss": ((500, 0),),       # 0
    },
    GROUP_HOLD: {
        "cp": ((0, 0),),
        "perfect": ((0, 0),),
        "great": ((200, 0),),      # 800
        "good": ((500, 0),),       # 500
        "miss": ((1000, 0),),      # 0
    },
    GROUP_SLIDE: {
        "cp": ((0, 0),),
        "perfect": ((0, 0),),
        "great": ((300, 0),),      # 1200
        "good": ((750, 0),),       # 750
        "miss": ((1500, 0),),      # 0
    },
    GROUP_BREAK: {
        "cp": ((0, 100),),
        "perfect": ((0, 75), (0, 50)),                 # FastPerfect/LatePerfect And 2nd file
        "great": ((500, 40), (1000, 40), (1250, 40)),  # 2000 / 1500 / 1250
        "good": ((1500, 30),),                         # 1000
        "miss": ((2500, 0),),                          # 0
    },
    GROUP_BREAK_FLAT: {
        "cp": ((0, 100),),
        "perfect": ((0, 75),),                         # holdDeterminenone 2nd file
        "great": ((500, 40),),                         # Only 2000 Grade 1
        "good": ((1500, 30),),
        "miss": ((2500, 0),),
    },
    GROUP_BREAK_SLIDE: {
        "cp": ((0, 100),),
        # itemDeterminenonenon- Critical of Perfect
        "great": ((500, 40), (1000, 40), (1250, 40)),
        "good": ((1500, 30),),
        "miss": ((2500, 0),),
    },
    GROUP_EX: {
        "cp": ((0, 0),),
        "miss": ((500, 0),),       # ExTap Determination table only Critical / TooFast / TooLate
    },
    GROUP_EX_BREAK: {
        "cp": ((0, 100),),
        "miss": ((2500, 0),),
    },
}

_BAD_JUDGMENTS = ("great", "good", "miss")

#: When a bad note falls on this group, present. (Number of accent notes that can appear bad_b, Weighted sum slo) of
#: slo = 2×bad_break + 3×bad_break_flat + 4×bad_break_slide + 4×bad_ex_break,
#: used forHara"critical perfectnotein cp/perfect ofReward PointsPick a value".
_GROUP_BAD_STEP = {
    GROUP_BREAK: (1, 2),
    GROUP_BREAK_FLAT: (1, 3),
    GROUP_BREAK_SLIDE: (1, 4),
    GROUP_EX_BREAK: (1, 4),
}

#: modeofBad notesnumber(Miss+Good+Great Sum). ThenOnlyIntervalDetermine.
EXACT_MAX_BAD = 12          # timeMax. bad notes(Miss+Good+Great)
EXACT_TIME_BUDGET = 8.0     # DP oftimecalculate(seconds), timetimesInterval Mode


# ------------------------------------------------------------------ theoreticalValue
@dataclass
class Theory:
    """Scoring Theoretical Value of a chart."""

    counts: Dict[str, int]              # notegroup -> notenumber
    weights: Dict[str, int]             # notegroup -> Single note full weight
    all_perfect_score: int              # _allPerfectScore
    break_bonus_score: int              # _breakBonusScore = 100 × critical perfectnotenumber
    total_notes: int                    # countMinutesnoteTotal N(Connection slider not included)
    max_dx: int                         # theoretical DX = 3N
    lattice: int                        # Missed all single notes-Maximum common divisor of award combinations

    @property
    def has_break(self) -> bool:
        return self.break_bonus_score > 0

    @property
    def break_notes(self) -> int:
        """critical perfect note Total (count Categories for Break of note)."""
        return sum(self.counts.get(g, 0) for g in _GROUP_BAD_STEP)

    @property
    def denominator(self) -> int:
        """achievement rate of Denominator: 100 - Σc/D in D."""
        if self.break_bonus_score:
            return self.all_perfect_score * self.break_bonus_score
        return self.all_perfect_score

    @property
    def max_achievement(self) -> Fraction:
        return Fraction(101 if self.break_bonus_score else 100)

    @property
    def perfect_capacity(self) -> int:
        """Allow to appear Perfect of critical perfect note number (Break And Break (hold Determine))."""
        return (self.counts.get(GROUP_BREAK, 0)
                + self.counts.get(GROUP_BREAK_FLAT, 0))


def _lattice_of(th: "Theory") -> int:
    g = 0
    for group in GROUP_ORDER:
        for opts in GROUP_OPTIONS[group].values():
            for loss, bonus in opts:
                g = math.gcd(g, _cost(th, loss, bonus))
    return g


def theory_from_counts(counts: Dict[str, int]) -> Theory:
    """by "note group -> note number" construct theoretical Value."""
    clean: Dict[str, int] = {}
    for key, value in (counts or {}).items():
        if key not in GROUP_OPTIONS:
            raise ValueError("cannot obtain note group: %r" % (key,))
        value = int(value or 0)
        if value < 0:
            raise ValueError("note number Cannot be %s=%d" % (key, value))
        if value:
            clean[key] = value
    all_perfect = 0
    break_notes = 0
    total = 0
    for group in GROUP_ORDER:
        n = clean.get(group, 0)
        if not n:
            continue
        weight = GROUP_WEIGHT[group]
        all_perfect += weight * n
        total += n
        if group in _GROUP_BAD_STEP:
            break_notes += n
    th = Theory(
        counts={g: clean.get(g, 0) for g in GROUP_ORDER},
        weights={g: GROUP_WEIGHT[g] for g in GROUP_ORDER},
        all_perfect_score=all_perfect,
        break_bonus_score=100 * break_notes,
        total_notes=total,
        max_dx=3 * total,
        lattice=0,
    )
    th.lattice = _lattice_of(th)
    return th


def theory_from_chart(chart: Chart) -> Theory:
    return theory_from_counts(chart.counts())


# ------------------------------------------------------------------ Single note cost
def _cost(th: Theory, loss: int, bonus: int) -> int:
    """put (Lost points, Reward Points) calculate one number c, Enable Achievement Rate = 100 - Σc / D."""
    if th.break_bonus_score:
        return 100 * th.break_bonus_score * loss - th.all_perfect_score * bonus
    return 100 * loss


def _edge_cost(th: Theory, group: str, judge: str, want_max: bool) -> Optional[int]:
    opts = GROUP_OPTIONS.get(group, {}).get(judge)
    if not opts:
        return None
    values = [_cost(th, loss, bonus) for loss, bonus in opts]
    # want_max "achievement rate", and achievement rate = 100 - Σc/D, So at the least cost..
    return min(values) if want_max else max(values)


def _flex_edge_cost(th: Theory, group: str, judge: str, want_max: bool) -> Optional[int]:
    """And _edge_cost relatedSame, But"Good notes"(CP/Perfect)Available at CP And Perfect Free choice between.

  Use only in the upper and lower bounds of the reverse solution: user CP/Perfect Minutestime, thisPieceMeetingsImpactachievement rate
  (critical perfectof CP Rewards 100, Perfect Only 75/50).
  """
    if judge == "cp":
        # "Remaining notes"thisGrade 1: Yesis Critical Perfect, It can also be Perfect
        # (Perfect can only fall on the overwhelming praise note, Hand over the current to your own choice)
        opts = (tuple(GROUP_OPTIONS.get(group, {}).get("cp", ()))
                + tuple(GROUP_OPTIONS.get(group, {}).get("perfect", ())))
    else:
        opts = GROUP_OPTIONS.get(group, {}).get(judge)
    if not opts:
        return None
    values = [_cost(th, loss, bonus) for loss, bonus in opts]
    return min(values) if want_max else max(values)


# ------------------------------------------------------------------ Minimum fee stream
class _MinCostFlow:
    """continueshort + item(numberFast enough)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.graph: List[List[List[int]]] = [[] for _ in range(n)]

    def add_edge(self, u: int, v: int, cap: int, cost: int) -> None:
        if cap <= 0:
            return
        self.graph[u].append([v, cap, cost, len(self.graph[v])])
        self.graph[v].append([u, 0, -cost, len(self.graph[u]) - 1])

    def min_cost(self, s: int, t: int, need: int) -> Optional[int]:
        if need <= 0:
            return 0
        total = 0
        flow = 0
        INF = float("inf")
        while flow < need:
            dist = [INF] * self.n
            prev_v = [-1] * self.n
            prev_e = [-1] * self.n
            in_queue = [False] * self.n
            dist[s] = 0
            queue = deque([s])
            in_queue[s] = True
            while queue:
                u = queue.popleft()
                in_queue[u] = False
                du = dist[u]
                for i, edge in enumerate(self.graph[u]):
                    v, cap, cost, _rev = edge
                    if cap > 0 and du + cost < dist[v]:
                        dist[v] = du + cost
                        prev_v[v] = u
                        prev_e[v] = i
                        if not in_queue[v]:
                            in_queue[v] = True
                            queue.append(v)
            if dist[t] == INF:
                return None
            add = need - flow
            v = t
            while v != s:
                add = min(add, self.graph[prev_v[v]][prev_e[v]][1])
                v = prev_v[v]
            v = t
            while v != s:
                edge = self.graph[prev_v[v]][prev_e[v]]
                edge[1] -= add
                self.graph[v][edge[3]][1] += add
                v = prev_v[v]
            flow += add
            total += add * dist[t]
        return total


def _extreme(th: Theory, judges: Dict[str, int], want_max: bool,
             flex_good: bool = False) -> Optional[Fraction]:
    """Given the total number of each decision,, achievement rateofvalue / value.

  flex_good=True time,"good"thisOneinof CP/Perfect Minutesby
  (Reverse solving with: Only for Miss/Good/Great time, CP And Perfect ofMinutesisbyof).
  """
    total = sum(int(judges.get(j, 0)) for j in JUDGMENTS)
    if total != th.total_notes:
        raise ValueError("Total number of judgments %d with number of notes on the musical surface %d Inconsistent" % (total, th.total_notes))
    if total == 0:
        return Fraction(0)
    groups = [g for g in GROUP_ORDER if th.counts.get(g, 0)]
    src = 0
    gbase = 1
    jbase = gbase + len(groups)
    sink = jbase + len(JUDGMENTS)
    mcf = _MinCostFlow(sink + 1)
    for i, group in enumerate(groups):
        mcf.add_edge(src, gbase + i, th.counts[group], 0)
    for j, judge in enumerate(JUDGMENTS):
        count = int(judges.get(judge, 0))
        if count:
            mcf.add_edge(jbase + j, sink, count, 0)
    for i, group in enumerate(groups):
        for j, judge in enumerate(JUDGMENTS):
            count = int(judges.get(judge, 0))
            if not count:
                continue
            cost = (_flex_edge_cost(th, group, judge, want_max) if flex_good
                    else _edge_cost(th, group, judge, want_max))
            if cost is None:
                continue     # theDetermineNocanfallatthisnoteUp: Unconnected, Leave it to the flow to determine the feasibility
            # Minimum fee flow will only minimize the total cost: achievement ratetimeputfetchLast flip back.
            mcf.add_edge(gbase + i, jbase + j, min(th.counts[group], count),
                         cost if want_max else -cost)
    total_cost = mcf.min_cost(src, sink, total)
    if total_cost is None:
        return None
    if not want_max:
        total_cost = -total_cost
    return Fraction(100) - Fraction(total_cost, th.denominator)


def achievement_bounds(th: Theory, judges: Dict[str, int]) -> Tuple[Fraction, Fraction]:
    """returns (achievement rateLower Boundary, achievement rateUpper Realm)."""
    lo = _extreme(th, judges, want_max=False)
    hi = _extreme(th, judges, want_max=True)
    if lo is None or hi is None:
        raise ValueError("thisDeterminenumbernofallatthechartUp(For example, putting Perfect EX note)")
    return lo, hi


def reference_achievement(th: Theory, judges: Dict[str, int]) -> Fraction:
    """pressexampleMinutesofachievement rate: Each decision is apportioned to each note group in proportion to the total number, fileBitTakevalue."""
    n = th.total_notes
    if n == 0:
        return Fraction(0)
    loss = Fraction(0)
    bonus = Fraction(0)
    for group in GROUP_ORDER:
        count = th.counts.get(group, 0)
        if not count:
            continue
        for judge in JUDGMENTS:
            given = int(judges.get(judge, 0))
            if not given:
                continue
            opts = GROUP_OPTIONS[group].get(judge)
            if not opts:
                continue
            losses = sorted({o[0] for o in opts})
            bonuses = sorted({o[1] for o in opts})
            share = Fraction(given * count, n)
            loss += share * Fraction(losses[0] + losses[-1], 2)
            bonus += share * Fraction(bonuses[0] + bonuses[-1], 2)
    result = Fraction(100) - 100 * loss / th.all_perfect_score
    if th.break_bonus_score:
        result += bonus / th.break_bonus_score
    return result


def dx_score(judges: Dict[str, int]) -> int:
    return sum(DX_PER[j] * int(judges.get(j, 0)) for j in JUDGMENTS)


# ------------------------------------------------------------------ currentTowards
@dataclass
class ForwardResult:
    theory: Theory
    judges: Dict[str, int]
    achievement_min: Fraction
    achievement_max: Fraction
    achievement_ref: Fraction
    dx: int

    @property
    def exact(self) -> bool:
        return self.achievement_min == self.achievement_max

    @property
    def achievement(self) -> Fraction:
        return self.achievement_min


def solve_forward(th: Theory, judges: Dict[str, int]) -> ForwardResult:
    clean = {j: int(judges.get(j, 0) or 0) for j in JUDGMENTS}
    total = sum(clean.values())
    if total != th.total_notes:
        raise ValueError("Total number of judgments %d with number of notes on the musical surface %d Inconsistent" % (total, th.total_notes))
    lo, hi = achievement_bounds(th, clean)
    return ForwardResult(
        theory=th,
        judges=clean,
        achievement_min=lo,
        achievement_max=hi,
        achievement_ref=reference_achievement(th, clean),
        dx=dx_score(clean),
    )


# ------------------------------------------------------------------ Reverse: Tool Functions
def _judges_for(th: Theory, miss: int, good: int, great: int,
                cp: int, perfect: int) -> Dict[str, int]:
    return {"cp": cp, "perfect": perfect, "great": great, "good": good, "miss": miss}


def _best(th: Theory, miss: int, good: int, great: int) -> Optional[Fraction]:
    """Miss/Good/Great numbertime, achievement ratecantoofvalue(CP/Perfect Minutesby)."""
    s = th.total_notes - miss - good - great
    if s < 0:
        return None
    return _extreme(th, _judges_for(th, miss, good, great, s, 0), want_max=True,
                    flex_good=True)


def _worst(th: Theory, miss: int, good: int, great: int) -> Optional[Fraction]:
    """Miss/Good/Great numbertime, achievement ratecantoofvalue(CP/Perfect Minutesby)."""
    s = th.total_notes - miss - good - great
    if s < 0:
        return None
    return _extreme(th, _judges_for(th, miss, good, great, s, 0), want_max=False,
                    flex_good=True)


def _max_true(lo: int, hi: int, pred) -> int:
    """pred at [lo, hi] When mocannot obtainnous does not increase, pred ofvalue(noThenreturns lo-1)."""
    best = lo - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if pred(mid):
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _min_true(lo: int, hi: int, pred) -> int:
    """pred at [lo, hi] When mocannot obtainnous does not increase, pred ofvalue(noThenreturns hi+1)."""
    best = hi + 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if pred(mid):
            best = mid
            hi = mid - 1
        else:
            lo = mid + 1
    return best


# ------------------------------------------------------------------ Reverse: Candidate Rows
def _candidate_rows(th: Theory, target: Fraction, max_scan: int,
                   bad_limit: Optional[int] = None, stats: Optional[Dict] = None):
    """text"Possible overrides target"of (miss, good, great) grouporderbyto

  bad_limit non-emptytimeOnlyOutput Miss+Good+Great <= bad_limit ofgroup
  and in the stats["clipped"] inDown"has(Bad notes more)groupoutput".
  """
    n = th.total_notes
    scanned = 0

    def best_m(m):
        v = _best(th, m, 0, 0)
        return v is not None and v >= target

    miss_max = _max_true(0, n, best_m)
    if miss_max < 0:
        return
    if bad_limit is not None and miss_max > bad_limit and stats is not None:
        stats["clipped"] = True
    miss_hi = miss_max if bad_limit is None else min(miss_max, bad_limit)
    for miss in range(miss_hi + 1):
        def best_g(g):
            v = _best(th, miss, g, 0)
            return v is not None and v >= target

        good_max = _max_true(0, n - miss, best_g)
        if good_max < 0:
            continue
        if bad_limit is not None and good_max > bad_limit - miss:
            if stats is not None:
                stats["clipped"] = True
            good_max = bad_limit - miss
        for good in range(good_max + 1):
            room = n - miss - good

            def best_gr(gr):
                v = _best(th, miss, good, gr)
                return v is not None and v >= target

            def worst_gr(gr):
                v = _worst(th, miss, good, gr)
                return v is not None and v <= target

            # Seek first"Great Down"ofnumber: no(Example EX noteNocan Great),
            # Otherwise, the infeasible high-end will make worst_gr No longer mocannot obtainnous, The two points will be wrong..
            feasible_hi = _max_true(0, room, lambda gr: _worst(th, miss, good, gr) is not None)
            if feasible_hi < 0:
                continue
            g_high = _max_true(0, feasible_hi, best_gr)
            g_low = _min_true(0, feasible_hi, worst_gr)
            if bad_limit is not None and g_high > bad_limit - miss - good:
                if stats is not None:
                    stats["clipped"] = True
                g_high = bad_limit - miss - good
            if g_low > g_high:
                continue
            for great in range(g_low, g_high + 1):
                scanned += 1
                if scanned > max_scan:
                    if stats is not None:
                        stats["clipped"] = True
                    return
                yield miss, good, great


@dataclass
class ReverseRow:
    miss: int
    good: int
    great: int
    cp_plus_perfect: int
    cp_min: int
    cp_max: int
    achievement_min: Fraction
    achievement_max: Fraction
    dx_min: int = 0
    dx_max: int = 0
    verified: bool = True       # modeDownisNoAlready
    exact: bool = False         # isNoexactlyetcinachievement rate

    def summary(self) -> str:
        return ("miss %d · good %d · great %d · cp+perfect %d"
                % (self.miss, self.good, self.great, self.cp_plus_perfect))


def _row_dx_bounds(th: Theory, row: ReverseRow) -> None:
    base = 2 * row.cp_plus_perfect + row.great
    row.dx_min = base + row.cp_min
    row.dx_max = base + row.cp_max


def _cp_bounds_simple(th: Theory, s: int) -> Tuple[int, int]:
    """cp ofPick a valuePerfect can only appear in Break / Break(holdDetermine) Up."""
    cp_min = max(0, s - th.perfect_capacity)
    return cp_min, s


# ------------------------------------------------------------------ Reverse: Interval Mode
def solve_reverse_range(th: Theory, target: Fraction, limit: int = 300,
                        max_scan: int = 200000) -> Dict[str, object]:
    rows: List[ReverseRow] = []
    scanned = 0
    truncated = False
    for miss, good, great in _candidate_rows(th, target, max_scan):
        scanned += 1
        lo = _worst(th, miss, good, great)
        hi = _best(th, miss, good, great)
        if lo is None or hi is None:
            continue
        s = th.total_notes - miss - good - great
        cp_min, cp_max = _cp_bounds_simple(th, s)
        row = ReverseRow(
            miss=miss, good=good, great=great, cp_plus_perfect=s,
            cp_min=cp_min, cp_max=cp_max,
            achievement_min=lo, achievement_max=hi,
        )
        _row_dx_bounds(th, row)
        rows.append(row)
        if len(rows) >= limit:
            truncated = True
            break
    return {
        "target": target,
        "mode": "range",
        "theory": th,
        "rows": rows,
        "truncated": truncated,
        "scanned": scanned,
        "exact_cap": EXACT_MAX_BAD,
        "unverified": 0,
    }


# ------------------------------------------------------------------ Reverse: mode
def _bad_options(group: str) -> Dict[str, Tuple[Tuple[int, int], ...]]:
    return {j: GROUP_OPTIONS[group][j] for j in _BAD_JUDGMENTS
            if j in GROUP_OPTIONS[group]}


def _dx_delta(th: Theory, loss: int, bonus: int) -> int:
    """a bad note pair"X"of; X = rhs etcinachievement rateetcin"""
    if th.break_bonus_score:
        return 100 * th.break_bonus_score * loss - th.all_perfect_score * bonus
    return 100 * loss


def _exact_suffix(th: Theory, groups: List[str]) -> List[Tuple[int, int, int, int]]:
    """eachPieceSuffix(Contains Own)of (dX towardsLower Boundary, dX Upper Realm, slo Upper Realm, bad Upper Realm), used for

  note dX The lower bound must be pressed"At most these are the only notes that are bad., It can also be 0 Piece"calculate,
  So only the cumulative negative contribution(min(0,...)·Number), Otherwise, the legal solution will be cut off by mistake.
  """
    suf: List[Tuple[int, int, int, int]] = [(0, 0, 0, 0)] * (len(groups) + 1)
    for i in range(len(groups) - 1, -1, -1):
        group = groups[i]
        n = th.counts.get(group, 0)
        opts = _bad_options(group)
        dxs = [_dx_delta(th, dl, db)
               for choices in opts.values() for dl, db in choices]
        d_bad, d_slo = _GROUP_BAD_STEP.get(group, (0, 0))
        pl, ph, ps, pn = suf[i + 1]
        suf[i] = (pl + n * min(0, min(dxs)), ph + n * max(dxs), ps + n * d_slo,
                  pn + n * (1 if d_bad else 0))
    return suf


def _exact_table(th: Theory, max_bad: int, rhs: Fraction,
                 set_cap: int = 20000, total_cap: int = 1500000,
                 deadline: Optional[float] = None):
    """DP:(miss, good, great) -> Reachable (X, bad_b, slo)

  X = 100*B*Loss of points and - W*Bad Note Reward Points(nocritical perfecttime X = 100*Loss of points and), One-to-one correspondence with the achievement rate;
  Stats only"Bad notes"(Great/Good/Miss); critical perfectnotein cp/perfect ofReward Pointsuse slo HaraInterval.
  eachPieceTuplesalluse"Max notes remaining/Minimum Contribution"Make target pruning(Only for current rhs has).
  outcalculatetimereturns None(callusetimesIntervalDetermine).
  """
    groups = [g for g in GROUP_ORDER if th.counts.get(g, 0) and _bad_options(g)]
    suf = _exact_suffix(th, groups)
    w = th.all_perfect_score
    b = th.break_bonus_score
    klo_const = (2 * th.counts.get(GROUP_BREAK, 0)
                 + 3 * th.counts.get(GROUP_BREAK_FLAT, 0)
                 + 4 * th.counts.get(GROUP_BREAK_SLIDE, 0)
                 + 4 * th.counts.get(GROUP_EX_BREAK, 0))
    break_notes = sum(th.counts.get(g, 0) for g in _GROUP_BAD_STEP)

    table: Dict[Tuple[int, int, int], set] = {(0, 0, 0): {(0, 0, 0)}}
    for gi, group in enumerate(groups):
        n = th.counts.get(group, 0)
        opts = _bad_options(group)
        d_bad, d_slo = _GROUP_BAD_STEP.get(group, (0, 0))
        deltas = {j: [_dx_delta(th, dl, db) for dl, db in choices]
                  for j, choices in opts.items()}
        dxmin_g = min(v for vs in deltas.values() for v in vs)
        dxmax_g = max(v for vs in deltas.values() for v in vs)
        rest_after = suf[gi + 1]
        slots = min(n, max_bad)
        for k in range(slots):
            if deadline is not None and time.monotonic() > deadline:
                return None
            new: Dict[Tuple[int, int, int], set] = {}
            for state, tset in table.items():
                carried = new.setdefault(state, set())
                carried.update(tset)
                if len(carried) > set_cap:
                    return None
                if state[0] + state[1] + state[2] >= max_bad:
                    continue
                for judge, vs in deltas.items():
                    nxt = (state[0] + (1 if judge == "miss" else 0),
                           state[1] + (1 if judge == "good" else 0),
                           state[2] + (1 if judge == "great" else 0))
                    bucket = new.setdefault(nxt, set())
                    rem = min(slots - k - 1, max_bad - sum(nxt))
                    dmin = rem * min(0, dxmin_g) + rest_after[0]
                    dmax = rem * dxmax_g + rest_after[1]
                    slomax = rem * d_slo + rest_after[2]
                    if b:
                        need_lo = rhs + 25 * w * (klo_const - slomax)
                        need_hi = rhs + 25 * w * 4 * break_notes
                    for x, bad_b, slo in tset:
                        cbb = bad_b + d_bad
                        cs = slo + d_slo
                        for dx in vs:
                            cx = x + dx
                            if b:
                                if cx + dmax < need_lo - 25 * w * cs:
                                    continue
                                if cx + dmin > need_hi - 25 * w * 4 * cbb:
                                    continue
                            else:
                                if cx + dmax < rhs or cx + dmin > rhs:
                                    continue
                            bucket.add((cx, cbb, cs))
                    if len(bucket) > set_cap:
                        return None
            table = new
            if sum(len(s) for s in table.values()) > total_cap:
                return None
    return table


def _exact_row_ok(th: Theory, table, miss: int, good: int, great: int,
                  rhs: Fraction) -> bool:
    """Strict Judgment: canNoput (miss, good, great) Determine that the hit rate is just right target."""
    tset = table.get((miss, good, great))
    if not tset:
        return False
    w = th.all_perfect_score
    b = th.break_bonus_score
    klo_const = (2 * th.counts.get(GROUP_BREAK, 0)
                 + 3 * th.counts.get(GROUP_BREAK_FLAT, 0)
                 + 4 * th.counts.get(GROUP_BREAK_SLIDE, 0)
                 + 4 * th.counts.get(GROUP_EX_BREAK, 0))
    break_notes = sum(th.counts.get(g, 0) for g in _GROUP_BAD_STEP)
    if not b:
        # nonecritical perfect: achievement rateOnly byLost pointsDecision,100 * Loss of points and == Denominator * (100 - )
        for x, _bad_b, _slo in tset:
            if x == rhs:
                return True
        return False
    for x, bad_b, slo in tset:
        num = x - rhs
        if num % (25 * w):
            continue
        k = num // (25 * w)
        if klo_const - slo <= k <= 4 * (break_notes - bad_b):
            return True
    return False


def solve_reverse_exact(th: Theory, target: Fraction, limit: int = 300,
                        max_scan: int = 200000) -> Dict[str, object]:
    d = th.denominator
    rhs = Fraction(d) * (100 - target)
    note = None
    table = None
    max_bad_used = 0
    pending: List[Tuple[int, int, int]] = []
    scanned = 0

    if rhs.denominator != 1:
        note = ("theachievement rateNochartcanoutvalue of(achievement rateOnlyTake 100 - number/Denominator of),"
                "Interval judgment results are given below.")
    elif th.lattice and rhs.numerator % th.lattice:
        note = ("theachievement rateNochartofLost points(Losing points can only be %d oftimesnumber),"
                "Interval judgment results are given below." % th.lattice)
    stats: Dict[str, bool] = {}
    if note is None:
        # Enumeration only"Bad notes no more than EXACT_MAX_BAD"ofgroupoutofgroup
        # Full enumeration. They will spend a lot of time in vain.(Large spectra may have hundreds of thousands of groups).
        for miss, good, great in _candidate_rows(th, target, max_scan,
                                                 EXACT_MAX_BAD, stats):
            scanned += 1
            pending.append((miss, good, great))
        if pending:
            max_bad_used = min(max(sum(p) for p in pending), EXACT_MAX_BAD)
            table = _exact_table(th, max_bad_used, rhs,
                                 deadline=time.monotonic() + EXACT_TIME_BUDGET)
            if table is None:
                note = ("Large number of judgments, outofcalculate(Max. %d Piece Miss+Good+Great),"
                        "Interval judgment results are given below." % EXACT_MAX_BAD)
    if note is not None:
        fallback = solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
        fallback["note"] = note
        fallback["exact_cap"] = max_bad_used or EXACT_MAX_BAD
        fallback["more_unverified"] = bool(stats.get("clipped"))
        return fallback

    if not pending and stats.get("clipped"):
        # Neither set of candidates can be accurately verified(All bad notes exceed the upper limit), timesInterval ModedescriptionReason
        fallback = solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
        fallback["note"] = ("thisPiecechart/achievement rateDown, Bad notes(Miss+Good+Great)%d Too many combinations,"
                            "Interval mode results are given below." % EXACT_MAX_BAD)
        fallback["exact_cap"] = EXACT_MAX_BAD
        fallback["more_unverified"] = True
        return fallback

    rows: List[ReverseRow] = []
    truncated = False
    unverified = 0
    for miss, good, great in pending:
        bad = miss + good + great
        if bad > max_bad_used:
            unverified += 1
            continue
        if not _exact_row_ok(th, table, miss, good, great, rhs):
            continue
        s = th.total_notes - bad
        cp_min, cp_max = _cp_bounds_simple(th, s)
        row = ReverseRow(
            miss=miss, good=good, great=great, cp_plus_perfect=s,
            cp_min=cp_min, cp_max=cp_max,
            achievement_min=target, achievement_max=target,
            verified=True, exact=True,
        )
        _row_dx_bounds(th, row)
        rows.append(row)
        if len(rows) >= limit:
            truncated = True
            break
    return {
        "target": target,
        "mode": "exact",
        "theory": th,
        "rows": rows,
        "truncated": truncated,
        "scanned": scanned,
        "exact_cap": max_bad_used,
        "unverified": unverified,
        "more_unverified": bool(stats.get("clipped")),
        "note": None,
    }


def solve_reverse(th: Theory, target: Fraction, limit: int = 300,
                  max_scan: int = 200000, mode: str = "exact") -> Dict[str, object]:
    target = Fraction(target)
    if target > th.max_achievement:
        raise ValueError("achievement rate %s thechartUp %s"
                         % (target, th.max_achievement))
    if mode == "range":
        return solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
    if mode != "exact":
        raise ValueError("mode can only be exact or range")
    return solve_reverse_exact(th, target, limit=limit, max_scan=max_scan)
