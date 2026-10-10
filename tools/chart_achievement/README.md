# chart_achievement —— DX chartachievement rate / DX Minutes Calculator

chart（`.ma2`）and number of judgments，calculateout**achievement rate**And **DX Minutes**；Conversely，achievement rate，
Reverse calculate all the decision combinations that can output this achievement rate。

text、standardLibrary（No internet required、Don't write any game files）。

## How to run

```powershell
cd tools/chart_achievement
python chart_achievement.py --help
python chart_achievement.py            # Do not give parameters = Interaction Wizard
```

## chartWhere did you come from?（Choose one of the two）

| Parameter | description |
| --- | --- |
| `--chart <text>` | directly `.ma2` file，As `.../music/music000008/000008_03.ma2` |
| `--game <text> --music-id <ID>` | text（`Sinmai_Data`、`StreamingAssets`、`A000`、`music` allcan），press `musicid` findchart |

### difficulty（--level）

difficultyuse**inofnumber**text，That is, the surface file name suffix `_00` ~ `_04` ofthatNumber
（Corresponding game master data `musicDifficulty/MusicDifficulty00000X` of `<id>`）：

| number | difficulty | chartfileFirst name |
| --- | --- | --- |
| 0 | BASIC | `<id>_00.ma2` |
| 1 | ADVANCED | `<id>_01.ma2` |
| 2 | EXPERT | `<id>_02.ma2` |
| 3 | MASTER | `<id>_03.ma2` |
| 4 | RE:MASTER | `<id>_04.ma2` |

`--level 0` ~ `--level 4` or `--level BASIC` / `ADVANCED` / `EXPERT` / `MASTER` / `RE:MASTER`
（Arbitrary case；`--difficulty` isSameParameterofFirst name）all，**default 3（MASTER）**；
When you don't give, you will be stderr usedefaultValue。

note：thisinof「level」text**chartdifficulty**。chartofnumberValuelevel（As `12+`）isOnetimes，
by `Music.xml` readout，For display only。

## currentTowards：Number of known decisions → achievement rate + DX Minutes

```powershell
python chart_achievement.py --chart "<...>\000008_03.ma2" --cp 290 --perfect 8 --great 3 --good 1
python chart_achievement.py --game "<...>\Sinmai_Data" --music-id 8 --level 3 --cp 290 --perfect 8 --great 3 --good 1   # 3 = MASTER
```

- `--cp` / `--perfect` / `--great` / `--good` allNumber，`--miss` leave blanktime
  （`miss = Total notes - CP - Perfect - Great - Good`）。
- outachievement rateof**Interval**（Lower Boundary ~ Upper Realm）and「pressExampleMinutes」ofValue：
  When only aggregation decisions are given，achievement rateTakeinthis Great/Good/Miss **fallatWhich notesUp**
  （fallatcritical perfectUp、fallat Tap Fewer buckles on），So it's an interval, not a number.。
  Lower Boundary = MinutesfallatweightnoteUp，Upper Realm = Try to land on the low-weight accent。
- DX Points are determined：`3×CP + 2×Perfect + 1×Great`。

## Reverse：Known attainment rate → Determine Combination + DX Minutes

```powershell
python chart_achievement.py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --level 3 --achievement 100.75            # 3 = MASTER
python chart_achievement.py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --level 2 --achievement 99 --mode range    # 2 = EXPERT
```

Two modes（`--mode`）：

| mode | Meaning | When to use |
| --- | --- | --- |
| `exact`（default） | Columns only**ofcanout**theachievement rateof (Miss, Good, Great) group，eachgroupall | data、Want to know the exact answer |
| `range` | Row Completion Rate**Interval Coverage**theValueofgroup（text、text） | The number of judgments is only an estimate / Want to take a quick look at the approximate |

`--limit N` Max.outgroup（default 200）。`--json` out JSON。

outinof `CP+P` is「Critical Perfect + Perfect ofTotal」；`CP text` iswhere
CP ofcan（Perfect can only fall on the overwhelming praise note，So CP Can't be less than
`CP+P - critical perfectnotenumber`）。CP text DX The higher the score,，So DX Points are also in this range。

### modeof

useOne「Bad Note Backpack DP」，Cost increases with number of bad notes，So：

- Strictly verified only `Miss+Good+Great ≤ 12` ofgroup；
- More combinations of bad notes are not verified（outinMeetings「Bad notes over 12 candidate combinations without validation」）；
- groupFullall 12 bad notes（Example 1000+ critical perfectofExceptionschart），automatically returns to the range mode and explains why；
- DP has 8 secondstimecalculate，timeAlsotimesInterval Mode。

## countMinutes（Match the game）

achievement ratepress**noteweight**Weighted，Not average by number：

```
achievement rate = 100 × Σ(Single note score) / theoreticalMinutesW  +  Σ(critical perfectReward Points) / critical perfecttheoreticalReward PointsB
```

- theoreticalMinutes W = Σ eachscore notesofweight（Tap/Star/Touch 500、Hold text 1000、Slide text 1500、Break text 2500）
- critical perfecttheoreticalReward Points B = 100 × critical perfectnoteNumber（Break / Break(holdDetermine) / BreakSlide / EXBreak）
- Minutes = **101.0000%**（charthascritical perfect）/ **100.0000%**（nocritical perfect）
- continueitemnodes（`CNSI_` etc ConnectSlide）**No score、Do not count towards total**
- DX Minutes = `3×CP + 2×Perfect + 1×Great`（Not related to note type）

### Loss of points for all types of notes / Reward Points

| notegroup（weight） | CP | Perfect | Great | Good | Miss |
| --- | --- | --- | --- | --- | --- |
| Tap / Star / Touch（500） | 0 | 0 | 100 | 250 | 500 |
| Hold text（1000） | 0 | 0 | 200 | 500 | 1000 |
| Slide text（1500） | 0 | 0 | 300 | 750 | 1500 |
| Break（2500，Staging） | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| Break holdDetermine（2500） | 0 | 0 | 500 | 1500 | 2500 |
| BreakSlide（2500，Staging） | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| EX（500） | 0 | — | — | — | 500 |
| EXBreak（2500） | 0 | — | — | — | 2500 |

（inis「Lost points」，i.e. `weight - Score`；CP/Perfect ofLost pointsallis 0，So
**critical perfect，Critical Perfect And Perfect The achievement rate of the addition is exactly the same**。）

critical perfectnotehasReward Points：

| Determine | Reward Points |
| --- | --- |
| Critical Perfect | 100 |
| Perfect | 75（FastPerfect/LatePerfect）/ 50（Perfect2nd） |
| Great | 40 |
| Good | 30 |
| Miss | 0 |

thisiscritical perfectRequiredDistinguish CP / Perfect ofReason：MinutesSame，But the reward points are different
（CP 100、Perfect 75 or 50）。

### notegroupofClassification by（Decompile source code）

- holdsettlementof Break（`BRHLD`）Determine fewer gears（Great Only one tier、Perfect Only 75 file），So individually in groups。
- item（`BRSI_`/`BRSCL`…）text SlideOut Determination table，Only Great Third Grade、none Perfect file。
- EX note（`XTP`/`XST`/`BXTAP`/`BXSTR`，i.e. ExTap/ExStar/ExBreakTap/ExBreakStar）
  text ExTap Determination table，non- Critical offor 0，So**Can only be judged Critical or Miss**。
- `XHO`/`BXHLD`（ExHold/ExBreakHold）For head ExTap But the results will have to go throughholdsettlement，
  etcin Hold / Break(holdDetermine)。

## file

| file | Content |
| --- | --- |
| `ma2.py` | `.ma2` parse、text→notegroup、`Music.xml` readTake、text |
| `score.py` | countMinutes、currentTowards、Reverse Solve（Interval / text） |
| `chart_achievement.py` | Command Line Interface / Interaction Wizard |

## Known limitations

- Calculated by spectral text only，Actual decision timing distribution at game runtime is not involved（E.g. Top Praise Perfect is 75 is 50 file，
  currentTowardscountcalculateinOnlyInterval）。
- ReverseOnlyBad notesnumber ≤ 12 ofgroup（Up）。
- text `.ma2` inof `T_NUM_ALL` Inconsistent with parsed score notes，will give a warning in the output
  （All 5419 The actual measurement of the game spectrum is consistent）。
