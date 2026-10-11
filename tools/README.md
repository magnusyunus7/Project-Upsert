# tools/ — Tools

this piece **Separate gadgets unrelated to the game protocol**: count calculate, file Process.
They **Unconnected**, **Don't touch the game server**, Also **Do not rely on `api/` And `config. py`**.

##

| | description |
|---|---|
| One tool, one subdirectory | `tools/<Tool name>/` |
| Package Contains | Tools are not interdependent, You can also run away by handcuffing alone |
| | Unconnected, Do Not Write Game Servers; Max Read Native Files |
| no number Three | Use only Python standard Library (non-Tools of README in) |
| | added Tools time, Below "Existing Tools" in Plus One Row |

## Existing Tools

| Tools | | What for? |
|---|---|---|
| chart achievement rate count calculate | [`chart_achievement/`](chart_achievement/) | press Determine number calculate chart achievement rate And DX Minutes; The combination can also be determined by the reverse calculation of the achievement rate |

## How to run

```bash
# Tools, directly python(The parameters of each tool are described in its own)
cd tools/chart_achievement
python chart_achievement. py --help
```

---
