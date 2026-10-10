# tools/ —— Tools

thisPiece**Separate gadgets unrelated to the game protocol**：countcalculate、fileProcess。
They**Unconnected**、**Don't touch the game server**、Also**Do not rely on `api/` And `config.py`**。

## text

| text | description |
|---|---|
| One tool, one subdirectory | `tools/<Tool name>/` |
| PackageContains | Tools are not interdependent，You can also run away by handcuffing alone |
| text | Unconnected、Do Not Write Game Servers；Max Read Native Files |
| nonumberThree | Use only Python standardLibrary（non-Toolsof README in） |
| text | addedToolstime，Below「Existing Tools」inPlusOne Row |

## Existing Tools

| Tools | text | What for? |
|---|---|---|
| chartachievement ratecountcalculate | [`chart_achievement/`](chart_achievement/) | pressDeterminenumbercalculatechartachievement rateAnd DX Minutes；The combination can also be determined by the reverse calculation of the achievement rate |

## How to run

```bash
# Tools，directly python text（The parameters of each tool are described in its own）
cd tools/chart_achievement
python chart_achievement.py --help
```

---
