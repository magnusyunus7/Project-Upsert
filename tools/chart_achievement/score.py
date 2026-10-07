# -*- coding: utf-8 -*-
"""舞萌DX 达成率 / DX 分计算模型（按音符组精确建模）。

达成率（source/Assembly-CSharp/Manager/GameScoreList.cs:1238-1310 CalcUpdate()）::

    Achivement = num / _allPerfectScore * 100 + num2 / _breakBonusScore

其中 num  = Σ 普通得分 NoteScore.GetJudgeScore(timing, 计分类型)
     num2 = Σ 绝赞奖励分（只有绝赞音符有）NoteScore.GetJudgeScore(timing, BreakBonus)
     _allPerfectScore  = Σ 每个音符的满权重（NotesReader.calcTotal()）
     _breakBonusScore  = 100 × 绝赞音符数
满分 = 101.0000%（有绝赞）/ 100.0000%（无绝赞）。

DX 分（JudgeResultSt.UpdateScore + NoteJudge.ConvertJudge）::

    DX = 3×CriticalPerfect + 2×Perfect + 1×Great（Good/Miss 不加分）

与音符类型无关，理论 DX = 3 × 计分音符数。

模型要点
--------
* 音符按「组」划分，同一组内计分行为完全一致（权重、可选判定、失分档位、绝赞奖励档位）。
* 绝赞（Break 类）的 Great 有 3 档失分、Perfect 奖励有 2 档（75 / 50），滑条判定的绝赞
  没有 Perfect 档，长按判定的绝赞不分档；EX 判定（ExTap 表）只能 Critical 或 Miss。
* 因此「给定各判定的总个数」并不能唯一确定达成率：达成率依赖这些判定落在哪些音符上。
  本模块用最小费用流求达成率的精确上下界，并可严格判定「能否恰好打出某个达成率」。
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

# ------------------------------------------------------------------ 常量
JUDGMENTS = ("cp", "perfect", "great", "good", "miss")
JUDGE_LABEL = {
    "cp": "Critical Perfect",
    "perfect": "Perfect",
    "great": "Great",
    "good": "Good",
    "miss": "Miss",
}
DX_PER = {"cp": 3, "perfect": 2, "great": 1, "good": 0, "miss": 0}

#: 每个音符组里，某判定实际可能出现的 (失分, 绝赞奖励分) 组合。
#: 失分 = 该音符满权重 - 实际得分；奖励分只对绝赞（计分类型 Break）音符存在。
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
        "perfect": ((0, 75), (0, 50)),                 # FastPerfect/LatePerfect 与 2nd 档
        "great": ((500, 40), (1000, 40), (1250, 40)),  # 2000 / 1500 / 1250
        "good": ((1500, 30),),                         # 1000
        "miss": ((2500, 0),),                          # 0
    },
    GROUP_BREAK_FLAT: {
        "cp": ((0, 100),),
        "perfect": ((0, 75),),                         # 长按判定没有 2nd 档
        "great": ((500, 40),),                         # 只有 2000 一档
        "good": ((1500, 30),),
        "miss": ((2500, 0),),
    },
    GROUP_BREAK_SLIDE: {
        "cp": ((0, 100),),
        # 滑条判定没有非 Critical 的 Perfect
        "great": ((500, 40), (1000, 40), (1250, 40)),
        "good": ((1500, 30),),
        "miss": ((2500, 0),),
    },
    GROUP_EX: {
        "cp": ((0, 0),),
        "miss": ((500, 0),),       # ExTap 判定表只有 Critical / TooFast / TooLate
    },
    GROUP_EX_BREAK: {
        "cp": ((0, 100),),
        "miss": ((2500, 0),),
    },
}

_BAD_JUDGMENTS = ("great", "good", "miss")

#: 坏音符落在该组时，对 (可出现的绝赞音符数 bad_b, 加权和 slo) 的贡献。
#: slo = 2×bad_break + 3×bad_break_flat + 4×bad_break_slide + 4×bad_ex_break，
#: 用于还原「绝赞音符里 cp/perfect 的奖励分取值范围」。
_GROUP_BAD_STEP = {
    GROUP_BREAK: (1, 2),
    GROUP_BREAK_FLAT: (1, 3),
    GROUP_BREAK_SLIDE: (1, 4),
    GROUP_EX_BREAK: (1, 4),
}

#: 精确模式严格验证的最大坏音符数（Miss+Good+Great 总和）。超过则只做区间判定。
EXACT_MAX_BAD = 12          # 精确验证时最多考虑多少个坏音符（Miss+Good+Great）
EXACT_TIME_BUDGET = 8.0     # 精确验证 DP 的时间预算（秒），超时退回区间模式


# ------------------------------------------------------------------ 理论值
@dataclass
class Theory:
    """一个谱面的计分理论值。"""

    counts: Dict[str, int]              # 音符组 -> 音符数
    weights: Dict[str, int]             # 音符组 -> 单音符满权重
    all_perfect_score: int              # _allPerfectScore
    break_bonus_score: int              # _breakBonusScore = 100 × 绝赞音符数
    total_notes: int                    # 计分音符总数 N（不含接续滑条）
    max_dx: int                         # 理论 DX = 3N
    lattice: int                        # 所有单音符失分-奖励组合的最大公约数

    @property
    def has_break(self) -> bool:
        return self.break_bonus_score > 0

    @property
    def break_notes(self) -> int:
        """绝赞音符总数（计分类型为 Break 的音符）。"""
        return sum(self.counts.get(g, 0) for g in _GROUP_BAD_STEP)

    @property
    def denominator(self) -> int:
        """达成率公式的分母：100 - Σc/D 中的 D。"""
        if self.break_bonus_score:
            return self.all_perfect_score * self.break_bonus_score
        return self.all_perfect_score

    @property
    def max_achievement(self) -> Fraction:
        return Fraction(101 if self.break_bonus_score else 100)

    @property
    def perfect_capacity(self) -> int:
        """允许出现 Perfect 的绝赞音符数（Break 与 Break(长按判定)）。"""
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
    """由「音符组 -> 音符数」构造理论值。"""
    clean: Dict[str, int] = {}
    for key, value in (counts or {}).items():
        if key not in GROUP_OPTIONS:
            raise ValueError("未知的音符组：%r" % (key,))
        value = int(value or 0)
        if value < 0:
            raise ValueError("音符数不能为负：%s=%d" % (key, value))
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


# ------------------------------------------------------------------ 单音符代价
def _cost(th: Theory, loss: int, bonus: int) -> int:
    """把 (失分, 奖励分) 折算成一个整数代价 c，使达成率 = 100 - Σc / D。"""
    if th.break_bonus_score:
        return 100 * th.break_bonus_score * loss - th.all_perfect_score * bonus
    return 100 * loss


def _edge_cost(th: Theory, group: str, judge: str, want_max: bool) -> Optional[int]:
    opts = GROUP_OPTIONS.get(group, {}).get(judge)
    if not opts:
        return None
    values = [_cost(th, loss, bonus) for loss, bonus in opts]
    # want_max 表示「追求最大达成率」，而达成率 = 100 - Σc/D，所以要取最小代价。
    return min(values) if want_max else max(values)


def _flex_edge_cost(th: Theory, group: str, judge: str, want_max: bool) -> Optional[int]:
    """与 _edge_cost 相同，但「好音符」（CP/Perfect）可以在 CP 与 Perfect 之间自由选择。

    只在反向求解的上下界里用：用户没给 CP/Perfect 拆分时，这个选择会影响达成率
    （绝赞的 CP 奖励 100、Perfect 只有 75/50）。
    """
    if judge == "cp":
        # 「其余音符」这一档：既可以是 Critical Perfect，也可以是 Perfect
        # （Perfect 只能落在绝赞音符上，交给流自己挑）
        opts = (tuple(GROUP_OPTIONS.get(group, {}).get("cp", ()))
                + tuple(GROUP_OPTIONS.get(group, {}).get("perfect", ())))
    else:
        opts = GROUP_OPTIONS.get(group, {}).get(judge)
    if not opts:
        return None
    values = [_cost(th, loss, bonus) for loss, bonus in opts]
    return min(values) if want_max else max(values)


# ------------------------------------------------------------------ 最小费用流
class _MinCostFlow:
    """连续最短路 + 整条增广（边数很少，够快）。"""

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
    """在给定各判定总数的前提下，求达成率的极大值 / 极小值。

    flex_good=True 时，「good」这一类里的 CP/Perfect 拆分由流自己挑
    （反向求解用：只给 Miss/Good/Great 时，CP 与 Perfect 的拆分是自由的）。
    """
    total = sum(int(judges.get(j, 0)) for j in JUDGMENTS)
    if total != th.total_notes:
        raise ValueError("判定总数 %d 与谱面音符数 %d 不一致" % (total, th.total_notes))
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
                continue     # 该判定不可能落在这类音符上：不连边，交给流去判定可行性
            # 最小费用流只会最小化总代价：求最小达成率时把代价取负，最后再翻回来。
            mcf.add_edge(gbase + i, jbase + j, min(th.counts[group], count),
                         cost if want_max else -cost)
    total_cost = mcf.min_cost(src, sink, total)
    if total_cost is None:
        return None
    if not want_max:
        total_cost = -total_cost
    return Fraction(100) - Fraction(total_cost, th.denominator)


def achievement_bounds(th: Theory, judges: Dict[str, int]) -> Tuple[Fraction, Fraction]:
    """返回 (达成率下界, 达成率上界)。"""
    lo = _extreme(th, judges, want_max=False)
    hi = _extreme(th, judges, want_max=True)
    if lo is None or hi is None:
        raise ValueError("这些判定数无法落在该谱面上（例如把 Perfect 给了 EX 音符）")
    return lo, hi


def reference_achievement(th: Theory, judges: Dict[str, int]) -> Fraction:
    """按比例分摊的参考达成率：各判定按总数比例摊到每个音符组，档位取中值。"""
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


# ------------------------------------------------------------------ 正向
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
        raise ValueError("判定总数 %d 与谱面音符数 %d 不一致" % (total, th.total_notes))
    lo, hi = achievement_bounds(th, clean)
    return ForwardResult(
        theory=th,
        judges=clean,
        achievement_min=lo,
        achievement_max=hi,
        achievement_ref=reference_achievement(th, clean),
        dx=dx_score(clean),
    )


# ------------------------------------------------------------------ 反向：工具函数
def _judges_for(th: Theory, miss: int, good: int, great: int,
                cp: int, perfect: int) -> Dict[str, int]:
    return {"cp": cp, "perfect": perfect, "great": great, "good": good, "miss": miss}


def _best(th: Theory, miss: int, good: int, great: int) -> Optional[Fraction]:
    """给定 Miss/Good/Great 数时，达成率能达到的最大值（CP/Perfect 拆分自由）。"""
    s = th.total_notes - miss - good - great
    if s < 0:
        return None
    return _extreme(th, _judges_for(th, miss, good, great, s, 0), want_max=True,
                    flex_good=True)


def _worst(th: Theory, miss: int, good: int, great: int) -> Optional[Fraction]:
    """给定 Miss/Good/Great 数时，达成率能达到的最小值（CP/Perfect 拆分自由）。"""
    s = th.total_notes - miss - good - great
    if s < 0:
        return None
    return _extreme(th, _judges_for(th, miss, good, great, s, 0), want_max=False,
                    flex_good=True)


def _max_true(lo: int, hi: int, pred) -> int:
    """pred 在 [lo, hi] 上单调不增时，求满足 pred 的最大值（无则返回 lo-1）。"""
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
    """pred 在 [lo, hi] 上单调不增时，求满足 pred 的最小值（无则返回 hi+1）。"""
    best = hi + 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if pred(mid):
            best = mid
            hi = mid - 1
        else:
            lo = mid + 1
    return best


# ------------------------------------------------------------------ 反向：候选行
def _candidate_rows(th: Theory, target: Fraction, max_scan: int,
                   bad_limit: Optional[int] = None, stats: Optional[Dict] = None):
    """生成「可能覆盖 target」的 (miss, good, great) 组合，顺序由少到多。

    bad_limit 非空时只产出 Miss+Good+Great <= bad_limit 的组合，
    并在 stats["clipped"] 里记下「还有更多（坏音符更多的）组合没产出」。
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

            # 先求「Great 放得下」的最大个数：超过它整行不可行（例如 EX 音符不能判 Great），
            # 否则不可行的高端会让 worst_gr 不再单调，二分就会找错。
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
    verified: bool = True       # 精确模式下是否已严格验证
    exact: bool = False         # 是否恰好等于目标达成率

    def summary(self) -> str:
        return ("miss %d · good %d · great %d · cp+perfect %d"
                % (self.miss, self.good, self.great, self.cp_plus_perfect))


def _row_dx_bounds(th: Theory, row: ReverseRow) -> None:
    base = 2 * row.cp_plus_perfect + row.great
    row.dx_min = base + row.cp_min
    row.dx_max = base + row.cp_max


def _cp_bounds_simple(th: Theory, s: int) -> Tuple[int, int]:
    """cp 的物理取值范围：Perfect 只能出现在 Break / Break(长按判定) 上。"""
    cp_min = max(0, s - th.perfect_capacity)
    return cp_min, s


# ------------------------------------------------------------------ 反向：区间模式
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


# ------------------------------------------------------------------ 反向：精确模式
def _bad_options(group: str) -> Dict[str, Tuple[Tuple[int, int], ...]]:
    return {j: GROUP_OPTIONS[group][j] for j in _BAD_JUDGMENTS
            if j in GROUP_OPTIONS[group]}


def _dx_delta(th: Theory, loss: int, bonus: int) -> int:
    """一个坏音符对「目标量 X」的贡献；X = rhs 等价于达成率等于目标。"""
    if th.break_bonus_score:
        return 100 * th.break_bonus_score * loss - th.all_perfect_score * bonus
    return 100 * loss


def _exact_suffix(th: Theory, groups: List[str]) -> List[Tuple[int, int, int, int]]:
    """每个后缀（含自身）的 (dX 负向下界, dX 上界, slo 上界, bad 上界)，用于剪枝。

    注意 dX 下界必须按「最多只有这些音符是坏音符、也可以是 0 个」来算，
    所以只累计负的贡献（min(0, ...)·个数），否则会错误剪掉合法解。
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
    """DP：状态 (miss, good, great) -> 可达的 (X, bad_b, slo) 集合。

    X = 100*B*失分和 - W*坏音符奖励分（无绝赞时 X = 100*失分和），与达成率一一对应；
    只统计「坏音符」（Great/Good/Miss）；绝赞音符里 cp/perfect 的奖励分用 slo 还原成区间。
    每个候选元组都用「剩余音符最大/最小贡献」做目标剪枝（只对当前 rhs 有效）。
    超出预算时返回 None（调用方退回区间判定）。
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
    """严格判定：能否把 (miss, good, great) 判定恰好打出达成率 target。"""
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
        # 没有绝赞：达成率只由失分决定，100 * 失分和 == 分母 * (100 - 目标)
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
        note = ("该达成率不是本谱面能精确打出的值（达成率只能取 100 - 整数/分母 的形式），"
                "下面给出区间判定结果。")
    elif th.lattice and rhs.numerator % th.lattice:
        note = ("该达成率不满足谱面的失分格点（失分只能是 %d 的倍数），"
                "下面给出区间判定结果。" % th.lattice)
    stats: Dict[str, bool] = {}
    if note is None:
        # 只枚举「坏音符不超过 EXACT_MAX_BAD」的组合：超出的组合没法精确验证，
        # 全枚举它们会白花很多时间（大谱面可能有几十万组）。
        for miss, good, great in _candidate_rows(th, target, max_scan,
                                                 EXACT_MAX_BAD, stats):
            scanned += 1
            pending.append((miss, good, great))
        if pending:
            max_bad_used = min(max(sum(p) for p in pending), EXACT_MAX_BAD)
            table = _exact_table(th, max_bad_used, rhs,
                                 deadline=time.monotonic() + EXACT_TIME_BUDGET)
            if table is None:
                note = ("判定数较大，超出精确验证的预算（最多 %d 个 Miss+Good+Great），"
                        "下面给出区间判定结果。" % EXACT_MAX_BAD)
    if note is not None:
        fallback = solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
        fallback["note"] = note
        fallback["exact_cap"] = max_bad_used or EXACT_MAX_BAD
        fallback["more_unverified"] = bool(stats.get("clipped"))
        return fallback

    if not pending and stats.get("clipped"):
        # 一组候选都没法精确验证（坏音符都超过上限），退回区间模式并说明原因
        fallback = solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
        fallback["note"] = ("这个谱面/达成率下，坏音符（Miss+Good+Great）超过 %d 个的组合太多，"
                            "精确验证代价过高，下面给出区间模式结果。" % EXACT_MAX_BAD)
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
        raise ValueError("目标达成率 %s 超过该谱面上限 %s"
                         % (target, th.max_achievement))
    if mode == "range":
        return solve_reverse_range(th, target, limit=limit, max_scan=max_scan)
    if mode != "exact":
        raise ValueError("mode 只能是 exact 或 range")
    return solve_reverse_exact(th, target, limit=limit, max_scan=max_scan)
