# chart_achievement —— 舞萌DX 谱面达成率 / DX 分计算器

给定谱面（`.ma2`）和判定数，算出**达成率**与 **DX 分**；反过来，给定目标达成率，
倒算出所有能打出该达成率的判定组合。

纯本地、纯标准库（不需要联网、不写任何游戏文件）。

## 怎么跑

```powershell
cd tools/chart_achievement
python chart_achievement.py --help
python chart_achievement.py            # 不给参数 = 交互向导
```

## 谱面从哪来（二选一）

| 参数 | 说明 |
| --- | --- |
| `--chart <路径>` | 直接给 `.ma2` 文件，如 `.../music/music000008/000008_03.ma2` |
| `--game <目录> --music-id <ID>` | 给游戏目录（`Sinmai_Data`、`StreamingAssets`、`A000`、`music` 都能认），按 `musicid` 自动找谱面 |

`--difficulty basic|advanced|expert|master|remaster`（也接受 0~4），默认 **master**。
`--level` 只用于显示（如 `12+`），不参与计算。

## 正向：已知判定数 → 达成率 + DX 分

```powershell
python chart_achievement.py --chart "<...>\000008_03.ma2" --level 12+ --cp 290 --perfect 8 --great 3 --good 1
```

- `--cp` / `--perfect` / `--great` / `--good` 都给个数，`--miss` 留空时自动补足
  （`miss = 总音符数 - CP - Perfect - Great - Good`）。
- 输出达成率的**区间**（下界 ~ 上界）和「按比例分摊」的参考值：
  只给聚合判定数时，达成率取决于这些 Great/Good/Miss **落在哪些音符上**
  （落在绝赞上扣得多、落在 Tap 上扣得少），所以是一个区间而不是一个数。
  下界 = 扣分尽量落在高权重音符上，上界 = 尽量落在低权重音符上。
- DX 分是确定的：`3×CP + 2×Perfect + 1×Great`。

## 反向：已知达成率 → 判定组合 + DX 分

```powershell
python chart_achievement.py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --achievement 100.75
python chart_achievement.py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --achievement 99 --mode range
```

两种模式（`--mode`）：

| 模式 | 含义 | 什么时候用 |
| --- | --- | --- |
| `exact`（默认） | 只列**真的能打出**该达成率的 (Miss, Good, Great) 组合，每组都做过严格验证 | 数据可信、想知道精确答案 |
| `range` | 列达成率**区间覆盖**该值的组合（更快、更宽松） | 判定数只是估算 / 想快速看个大概 |

`--limit N` 限制最多输出多少组（默认 200）。`--json` 输出 JSON。

输出里的 `CP+P` 是「Critical Perfect + Perfect 的总数」；`CP 范围` 是其中
CP 的物理可能范围（Perfect 只能落在绝赞音符上，所以 CP 不能少于
`CP+P - 绝赞音符数`）。CP 越多 DX 分越高，所以 DX 分也是这个范围。

### 精确模式的限制

精确验证用一个「坏音符背包 DP」，代价随坏音符个数增长，所以：

- 只严格验证 `Miss+Good+Great ≤ 12` 的组合；
- 坏音符更多的组合不验证（输出里会提示「坏音符超过 12 个的候选组合没有验证」）；
- 若候选组合全都超过 12 个坏音符（例如 1000+ 绝赞的异常谱面），会自动退回区间模式并说明原因；
- DP 有 8 秒时间预算，超时也退回区间模式。

## 计分模型（与游戏一致）

达成率按**音符权重**加权，不是按个数平均：

```
达成率 = 100 × Σ(单音符得分) / 理论分W  +  Σ(绝赞奖励分) / 绝赞理论奖励分B
```

- 理论分 W = Σ 每个计分音符的权重（Tap/Star/Touch 500、Hold 系 1000、Slide 系 1500、Break 系 2500）
- 绝赞理论奖励分 B = 100 × 绝赞音符个数（Break / Break(长按判定) / BreakSlide / EXBreak）
- 满分 = **101.0000%**（谱面有绝赞）/ **100.0000%**（无绝赞）
- 接续滑条节点（`CNSI_` 等 ConnectSlide）**不计分、不计入总数**
- DX 分 = `3×CP + 2×Perfect + 1×Great`（与音符类型无关）

### 各类音符的失分 / 奖励分

| 音符组（权重） | CP | Perfect | Great | Good | Miss |
| --- | --- | --- | --- | --- | --- |
| Tap / Star / Touch（500） | 0 | 0 | 100 | 250 | 500 |
| Hold 系（1000） | 0 | 0 | 200 | 500 | 1000 |
| Slide 系（1500） | 0 | 0 | 300 | 750 | 1500 |
| Break（2500，分档） | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| Break 长按判定（2500） | 0 | 0 | 500 | 1500 | 2500 |
| BreakSlide（2500，分档） | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| EX（500） | 0 | — | — | — | 500 |
| EXBreak（2500） | 0 | — | — | — | 2500 |

（表里是「失分」，即 `权重 - 得分`；CP/Perfect 的失分都是 0，所以
**除绝赞外，Critical Perfect 与 Perfect 加的达成率完全一样**。）

绝赞音符额外有奖励分：

| 判定 | 奖励分 |
| --- | --- |
| Critical Perfect | 100 |
| Perfect | 75（FastPerfect/LatePerfect）/ 50（Perfect2nd） |
| Great | 40 |
| Good | 30 |
| Miss | 0 |

这就是绝赞必须区分 CP / Perfect 的原因：普通分一样，但奖励分不同
（CP 100、Perfect 75 或 50）。

### 音符组的划分依据（反编译源码）

- 走长按结算的 Break（`BRHLD`）判定档位更少（Great 只有一档、Perfect 只有 75 档），所以单独成组。
- 滑条系（`BRSI_`/`BRSCL`…）走 SlideOut 判定表，只有 Great 三档、没有 Perfect 档。
- EX 音符（`XTP`/`XST`/`BXTAP`/`BXSTR`，即 ExTap/ExStar/ExBreakTap/ExBreakStar）
  走 ExTap 判定表，非 Critical 的窗口宽度为 0，所以**只能判 Critical 或 Miss**。
- `XHO`/`BXHLD`（ExHold/ExBreakHold）头部用 ExTap 表但结果还要过长按结算，
  等价于普通 Hold / Break(长按判定)。

## 文件

| 文件 | 内容 |
| --- | --- |
| `ma2.py` | `.ma2` 解析、指令→音符组映射、`Music.xml` 读取、路径拼接 |
| `score.py` | 计分模型、正向求解、反向求解（区间 / 精确） |
| `chart_achievement.py` | 命令行界面 / 交互向导 |

## 已知局限

- 只按谱面文本计算，不涉及游戏运行时的实际判定时机分布（例如绝赞 Perfect 是 75 还是 50 档，
  正向计算里只能给区间）。
- 精确反向只验证坏音符数 ≤ 12 的组合（见上文）。
- 若 `.ma2` 里的 `T_NUM_ALL` 与解析出的计分音符数不一致，会在输出里给警告
  （全部 5419 个游戏谱面实测一致）。
