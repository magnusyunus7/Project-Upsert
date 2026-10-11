# chart_achievement — DX chart achievement rate / DX Minutes Calculator

chart (`. ma2`) and number of judgments, calculate out **achievement rate** And **DX Minutes**; Conversely, achievement rate,
Reverse calculate all the decision combinations that can output this achievement rate.

text, standard Library (No internet required, Don't write any game files).

## How to run

```powershell
cd tools/chart_achievement
python chart_achievement. py --help
python chart_achievement. py      # Do not give parameters = Interaction Wizard
```

## chart Where did you come from? (Choose one of the two)

| Parameter | description |
| --- | --- |
| `--chart <text>` | directly `. ma2` file, As `.../music/music000008/000008_03. ma2` |
| `--game <text> --music-id <ID>` | (`Sinmai_Data`,`StreamingAssets`,`A000`,`music` allcan), press `musicid` find chart |

### difficulty(--level)

difficulty use **in of number** text, That is, the surface file name suffix `_00` ~ `_04` of that Number
(Corresponding game master data `musicDifficulty/MusicDifficulty00000X` of `<id>`):

| number | difficulty | chartfileFirst name |
| --- | --- | --- |
| 0 | BASIC | `<id>_00. ma2` |
| 1 | ADVANCED | `<id>_01. ma2` |
| 2 | EXPERT | `<id>_02. ma2` |
| 3 | MASTER | `<id>_03. ma2` |
| 4 | RE: MASTER | `<id>_04. ma2` |

`--level 0` ~ `--level 4` or `--level BASIC` / `ADVANCED` / `EXPERT` / `MASTER` / `RE: MASTER`
(Arbitrary case; `--difficulty` is Same Parameter of First name) all, **default 3(MASTER)**;
When you don't give, you will be stderr usedefaultValue.

note: this in of "level" text **chart difficulty**. chart of number Value level (As `12+`) is One times,
by `Music. xml` readout, For display only.

## currentTowards: Number of known decisions → achievement rate + DX Minutes

```powershell
python chart_achievement. py --chart "<...>\000008_03. ma2" --cp 290 --perfect 8 --great 3 --good 1
python chart_achievement. py --game "<...>\Sinmai_Data" --music-id 8 --level 3 --cp 290 --perfect 8 --great 3 --good 1  # 3 = MASTER
```

- `--cp` / `--perfect` / `--great` / `--good` all Number, `--miss` leave blank time
 (`miss = Total notes - CP - Perfect - Great - Good`).
- out achievement rate of **Interval** (Lower Boundary ~ Upper Realm) and "press Example Minutes" value of:
 When only aggregation decisions are given, achievement rateTakeinthis Great/Good/Miss**fallatWhich notesUp**
 (fallatcritical perfectUp, fallat Tap Fewer buckles on), So it's an interval, not a number..
 Lower Boundary = MinutesfallatweightnoteUp, Upper Realm = Try to land on the low-weight accent.
- DX Points are determined: `3×CP + 2×Perfect + 1×Great`.

## Reverse: Known attainment rate → Determine Combination + DX Minutes

```powershell
python chart_achievement. py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --level 3 --achievement 100.75      # 3 = MASTER
python chart_achievement. py --game "D:\SDGB2026\Package\Sinmai_Data" --music-id 8 --level 2 --achievement 99 --mode range  # 2 = EXPERT
```

Two modes (`--mode`):

| mode | Meaning | When to use |
| --- | --- | --- |
| `exact`(default) | Columns only**ofcanout**theachievement rateof (Miss, Good, Great) group, eachgroupall | data, Want to know the exact answer |
| `range` | Row Completion Rate**Interval Coverage**theValueofgroup(text, text) | The number of judgments is only an estimate / Want to take a quick look at the approximate |

`--limit N` Max. out group (default 200). `--json` out JSON.

out in of `CP+P` is "Critical Perfect + Perfect of Total"; `CP` is where
CP ofcan(Perfect can only fall on the overwhelming praise note, So CP Can't be less than
`CP+P - critical perfectnotenumber`). CP DX The higher the score,, So DX Points are also in this range.

### modeof

use One "Bad Note Backpack DP", Cost increases with number of bad notes, So:

- Strictly verified only `Miss+Good+Great ≤ 12` of group;
- More combinations of bad notes are not verified(outinMeetings"Bad notes over 12 candidate combinations without validation");
- groupFullall 12 bad notes(Example 1000+ critical perfectofExceptionschart), automatically returns to the range mode and explains why;
- DP has 8 seconds time calculate, time Also times Interval Mode.

## countMinutes(Match the game)

achievement rate press **note weight** Weighted, Not average by number:

```
achievement rate = 100 × Σ(Single note score) / theoreticalMinutesW + Σ(critical perfectReward Points) / critical perfecttheoreticalReward PointsB
```

- theoreticalMinutes W = Σ each score notes of weight (Tap/Star/Touch 500, Hold 1000, Slide 1500, Break 2500)
- critical perfect theoretical Reward Points B = 100 × critical perfect note Number (Break / Break (holdDetermine) / BreakSlide / EXBreak)
- Minutes = **101.0000%** (chart has critical perfect) / **100.0000%** (no critical perfect)
- continue item nodes (`CNSI_` etc ConnectSlide) **No score, Do not count towards total**
- DX Minutes = `3×CP + 2×Perfect + 1×Great` (Not related to note type)

### Loss of points for all types of notes / Reward Points

| notegroup(weight) | CP | Perfect | Great | Good | Miss |
| --- | --- | --- | --- | --- | --- |
| Tap / Star / Touch(500) | 0 | 0 | 100 | 250 | 500 |
| Hold(1000) | 0 | 0 | 200 | 500 | 1000 |
| Slide(1500) | 0 | 0 | 300 | 750 | 1500 |
| Break(2500, Staging) | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| Break holdDetermine(2500) | 0 | 0 | 500 | 1500 | 2500 |
| BreakSlide(2500, Staging) | 0 | 0 | 500 / 1000 / 1250 | 1500 | 2500 |
| EX(500) | 0 | — | — | — | 500 |
| EXBreak(2500) | 0 | — | — | — | 2500 |

(in is "Lost points", i. e. `weight - Score`; CP/Perfect of Lost points all is 0, So
**critical perfect, Critical Perfect And Perfect The achievement rate of the addition is exactly the same**.)

critical perfect note has Reward Points:

| Determine | Reward Points |
| --- | --- |
| Critical Perfect | 100 |
| Perfect | 75 (Fast Perfect/Late Perfect) / 50 (Perfect 2nd) |
| Great | 40 |
| Good | 30 |
| Miss | 0 |

this is critical perfect Required Distinguish CP / Perfect of Reason: Minutes Same, But the reward points are different
(CP 100, Perfect 75 or 50).

### notegroup of Classification by (Decompile source code)

- holdsettlement of Break (`BRHLD`) Determine fewer gears (Great Only one tier, Perfect Only 75 file), So individually in groups.
- item (`BRSI_` / `BRSCL`…) SlideOut Determination table, Only Great Third Grade, none Perfect file.
- EX note (`XTP` / `XST` / `BXTAP` / `BXSTR`, i. e. ExTap/ExStar/ExBreakTap/ExBreakStar)
 ExTap Determination table, non- Critical of for 0, So **Can only be judged Critical or Miss**.
- `XHO` / `BXHLD` (ExHold/ExBreakHold) For head ExTap But the results will have to go through holdsettlement,
 etcin Hold / Break(holdDetermine).

## file

| file | Content |
| --- | --- |
| `ma2. py` | `. ma2` parse, text → notegroup, `Music. xml` read Take,|
| `score. py` | countMinutes, currentTowards, Reverse Solve(Interval /) |
| `chart_achievement. py` | Command Line Interface / Interaction Wizard |

## Known limitations

- Calculated by spectral only, actual decision timing distribution at game runtime is not involved(E. g. Top Praise Perfect is 75 is 50 file,
 currentTowardscountcalculateinOnlyInterval).
- ReverseOnlyBad notesnumber ≤ 12 ofgroup(Up).
- `. ma2` inof `T_NUM_ALL` Inconsistent with parsed score notes, will give a warning in the output
 (All 5419 The actual measurement of the game spectrum is consistent).
