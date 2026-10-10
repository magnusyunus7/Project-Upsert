# tools/ —— textTools

thisPiecetext**Separate gadgets unrelated to the game protocol**：textcountcalculate、textfileProcess。
They**Unconnected**、**Don't touch the game server**、Also**Do not rely on `api/` And `config.py`**。

## text

| text | description |
|---|---|
| One tool, one subdirectory | `tools/<Tool name>/` |
| textPackageContains | Tools are not interdependent，You can also run away by handcuffing alone |
| text | Unconnected、Do Not Write Game Servers；Max Read Native Files |
| nonumberThreetext | Use only Python standardLibrary（textnon-Toolstextof README intext） |
| text | addedToolstime，Below「Existing Tools」textinPlusOne Row |

## Existing Tools

| Tools | text | What for? |
|---|---|---|
| chartachievement ratecountcalculatetext | [`chart_achievement/`](chart_achievement/) | pressDeterminenumbercalculatechartachievement rateAnd DX Minutes；The combination can also be determined by the reverse calculation of the achievement rate |

## How to run

```bash
# textToolstext，directly python text（The parameters of each tool are described in its own）
cd tools/chart_achievement
python chart_achievement.py --help
```

---
