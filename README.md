<h1 align="center">WaHappy</h1>

<p align="center">
  <b>舞萌DX 的游戏助手</b><br>
  宗旨：让舞萌DX的玩家能够更好地游玩游戏，获得快乐。
</p>

<p align="center">AI真的很好用你知道吗</p>

---

## 这是什么

WaHappy 是一个用 **Python 纯网络方式**与舞萌DX（SDGB 国服）游戏服务器交互的工具集。

它不修改游戏、不注入进程，只是把游戏客户端做的事用脚本重做一遍：
扫码登录 → 取数据 → 上传成绩 → 登出。

> 协议实现全部来自反编译源码与真机网络日志的双向验证，
> 每个关键常量在代码注释里都标了**源码行号**。

---

## 当前状态：v0，**未完工**

**v0 目前只是一个占位版本，请以「能不能用」而不是「有多少代码」来判断它。**

| 脚本 | 状态 |
|---|---|
| **`upsert.py`** | ✅ **可用** —— 扫码登录 → 上传一局成绩 → 落库回查 → 登出 |
| **`buy_ticket.py`** | ✅ **可用** —— 购买功能票（2026-10-06 真机验证通过） |
| **`use_ticket.py`** | ✅ **可用** —— 读取当前持有的功能票并用 `UpsertUserAll` 消耗掉 |
| **`reincarnate.py`** | 🔧 已实现（未实跑）—— 账号数据迁移（转生），每包 ≤4 首 + 续关登录 |
| `api/` 下 40+ 个接口模块 | 🔧 已实现并通过零网络自检，但**未全部在真机上验证过** |
| **文档** | 📄 在 **`docs` 分支**（`mai` 分支不含）—— 开发过程、踩坑记录、实跑验证，内容比代码本身还多 |

### 关于购买功能票（已解决）

`UpsertUserChargelogApi` 曾经一直返回 `returnCode=0`。根因是 **请求头多发了
`Accept` 与 `Connection`** —— 真机（Unity Mono 的 `HttpWebRequest`）**不发这两个头**：

```
number / Content-Type / User-Agent / charset / Mai-Encoding / Content-Encoding / Cookie
```

删掉之后一次通过（`stock` 0 → 1，落库确认）。完整排查过程见
[购买功能票流程](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/购买功能票流程.md)。

---

## 一个教训：别把一件事分段交给 AI

v0 的开发过程中，我反复把同一个目标拆成小段丢给 AI，结果：

| 项目 | Token 消耗 |
|---|---|
| **v0 有效开发** | **384M+** |
| 含中途废弃的分支项目 | **1137.5M** |

**这 1137.5M 里有一大半是浪费掉的。**

真正的教训是：

> **不要把一个东西分段交给 AI，而是直接设定一个目标，然后让它自己跑完。**

分段交接会让 AI 反复丢失上下文、重复劳动、在已经解决的问题上打转 ——
而一个清晰的目标 + 足够长的执行窗口，反而更快也更省。

---

## 项目框架

```
WaHappy/
├── config.py            运行时可配置项（密钥 / 机台 / 歌曲数据 / 日志级别）★ 需自建
├── config.py.example    配置模板（机台与店铺标识留空待填）
├── upsert.py            ★ 主脚本：扫码登录 → 上传成绩 → 登出
├── buy_ticket.py        主脚本：购买功能票
├── use_ticket.py        主脚本：消耗当前持有的功能票
├── reincarnate.py       主脚本：账号数据迁移（转生）
├── selftest.py          零网络自检（238 项，判据 = 源码 + 真机日志）
│
├── api/                 ★ 所有与服务器交互的模块（一个接口一个脚本）
│   ├── __init__.py      统一导出 + 日志自动跟踪
│   ├── maimai_net.py    网络核心（AES / deflate / URL 混淆 / Cookie）
│   ├── log_setup.py     日志（INFO / DEBUG 双模式）
│   ├── upsert_user_all.py      上传成绩（36 节点 / 110 字段 / 差分）
│   ├── get_need_user_data.py   结算快照编排 + 落盘 data/<userId>.json
│   └── ...                     40+ 个接口脚本
│
├── data/                每账号一份用户数据快照（<userId>.json）★ 不入库
├── logs/                日志输出（latest.log + 日期.log）★ 不入库
└── source/              反编译源码 ★ 不入库，需自备
```

**设计约定**：`api/` 里每个脚本 = 一个接口，对外暴露一个**能传参的函数**。
主脚本只负责编排，日志和协议细节都在 `api/` 内部。

**命名约定**：服务端 API 名里带 `Get` 的，**脚本名与函数名一律带 `get` / `Get`**
（不要模棱两可）。所以取数脚本全是 `get_*.py`，函数是 `GetXxx`。

> **`docs/` 在 [`docs` 分支](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)，`source/` 与 `logs/` 不入库。**
>
> `source/` 是反编译源码，**需要自备**。

### 分支说明

| 分支 | 内容 |
|---|---|
| **`mai`** | 主分支 —— 代码（`api/` / `upsert.py` / `config.py` / `selftest.py` / `gamehook/`） |
| **`docs`** | 孤儿分支 —— 只有 `docs/`，开发文档与踩坑记录 |

两个分支**没有共同的提交历史**，各自独立。

---

## 快速开始

### 1. 装依赖

```bash
pip install requests pycryptodome
```

### 2. ★ 先填 `config.py`

仓库里只有模板 `config.py.example`，先复制一份：

```bash
cp   config.py.example config.py      # Linux / macOS
copy config.py.example config.py      # Windows
```

然后**必须**填好 **`config.py` 第二节「机台与店铺标识」的 6 个值**：

| 变量 | 填什么 |
|---|---|
| `KEYCHIP_ID` | 你的机台 Keychip（**完整形式**，带连字符，形如 `XXXX-XXXXXXXXXXX`） |
| `CLIENT_ID` | Keychip **短值**（去掉连字符取前 11 位） |
| `REGION_ID` | 你所在区域 ID |
| `PLACE_ID` | 你所在店铺 ID |
| `PLACE_NAME` | 店铺名（游戏服务器不返回，只能手填） |
| `REGION_NAME` | 区域名 |

> ⚠️ **这 6 个值留空或填错，发出去的请求带的就是别人的机台身份，服务端会直接拒绝。**
>
> `config.py` 已在 `.gitignore` 里 —— 它是你的私有配置，**不要提交**。

### 3. 跑自检

```bash
python selftest.py        # 零网络自检，应该 236 项全绿（不依赖你的 config）
```

### upsert.py 用法

```bash
# 预检：登录 + 抓快照 + 组包，不发包（零副作用，建议先跑这个）
python upsert.py "<二维码>"

# 真实上传一局成绩（★ 有副作用，不可撤销）
python upsert.py "<二维码>" --send

# 常用开关
python upsert.py "<二维码>" --send --debug        # 日志里带完整收发报文
python upsert.py "<二维码>" --send --cooldown 0   # 跳过发包前 60 秒冷却
python upsert.py "<二维码>" --send --no-verify    # 跳过上传后的落库回查
```

**换歌 / 换成绩只改 `config.py` 的 `PLAY_*`，不用动任何代码。**

> 二维码从机台的「扫码登录」界面获取，**有效期 10 分钟**。

### buy_ticket.py 用法

```bash
python buy_ticket.py "<二维码>" --list                    # 只列当前票券和可买的票
python buy_ticket.py "<二维码>" --charge-id 2             # 预检：只看报文
python buy_ticket.py "<二维码>" --charge-id 2 --send      # ★ 真实购买
```

| chargeId | 票 | 上报的 price |
|---|---|---|
| 2 | 2倍チケット | 1 |
| 3 | 3倍チケット | 2 |
| 4 | 4倍チケット | 3 |
| 5 | 5倍チケット | 4 |
| 6 | 6倍チケット | 5 |

> ⚠️ **账号已经持有功能票时，本脚本会直接拒绝购买**（重复购买有封号风险）。
> 想清掉手里的票，用下面的 `use_ticket.py`。

### use_ticket.py 用法

读取账号当前**持有**的功能票，然后用 `UpsertUserAll` 表达「用这张票打了一局」把它消耗掉。

```bash
python use_ticket.py "<二维码>" --list                  # 只列当前持有的票
python use_ticket.py "<二维码>" --ticket-id 2           # 预检：只看报文
python use_ticket.py "<二维码>" --ticket-id 2 --send    # ★ 真实消耗
```

原理：`GetUserChargeApi` 与 `UpsertUserAllApi` 里的 `userChargeList`
**格式完全相同**，所以只要把该节点里目标票的 `stock` 减 1，
再让 playlog 带上 `useTicketId` / `playCredit`，服务端就认为这张票被这一局用掉了。

`playCredit` 的算法（`VOExtensions.cs:838-845`）：

```
playCredit = 投币数（普通局 = 1） + 票的 creditNum
```

### reincarnate.py 用法（账号数据迁移）

把一个账号的数据克隆到另一个账号。**每包最多 4 首**（真机一局最多 4 首），
每包之间用**续关登录**（`UserLogin(is_continue=True)`）换新的 `loginId`。

```bash
# 源数据来自二维码（会联网抓 A 的数据并落盘到 data/<A>.json）
python reincarnate.py --dst-qr "<B的二维码>" --src-qr "<A的二维码>"

# 源数据来自已保存的 JSON（离线，推荐）
python reincarnate.py --dst-qr "<B的二维码>" --src-json data/12345678.json --plan
python reincarnate.py --dst-qr "<B的二维码>" --src-json data/12345678.json --send

# 试跑
--limit 20          # 只迁前 20 首
--clone-identity    # 连 userName / accessCode 一起克隆（默认保留 B 自己的）
```

### 额外塞节点：`--extra-data`

真机报文的 36 个节点绝大多数能由快照 + 本局演算自动推出来，
但偶尔想手工覆盖某几个（比如本局拿到的新 KaleidxScope 门），就用 `--extra-data`：

```bash
# ① 从文件读（★ 推荐 —— 不用跟 shell 引号搏斗）
python upsert.py "<二维码>" --send --extra-data extra.json

# ② 直接写 JSON 字符串
python upsert.py "<二维码>" --send --extra-data '{"isNewMapList":"1"}'

# ③ 多个来源，后给的覆盖先给的
python upsert.py "<二维码>" --send --extra-data base.json --extra-data patch.json
```

`extra.json` 长这样：

```json
{
  "userKaleidxScopeList": [
    {"gateId": 1, "isGateFound": true, "isKeyFound": true, "isClear": false,
     "totalRestLife": 0, "totalAchievement": 0, "totalDeluxscore": 0,
     "bestAchievement": 0, "bestDeluxscore": 0,
     "bestAchievementDate": "", "bestDeluxscoreDate": "",
     "playCount": 0, "clearDate": "", "lastPlayDate": "", "isInfoWatched": false}
  ],
  "isNewKaleidxScopeList": "1"
}
```

| 规则 | 说明 |
|---|---|
| 键 | 必须是 `upsertUserAll` 的 **36 个节点**之一（含 11 条 `isNew*` 位串），写错会报错并列出可用节点名 |
| 值形态 | 按节点形态强制转换，传错立刻报错 |
| 位串 | 给了数组没给位串 → 按长度补 `"0"` 并提示。**新增条目请显式传 `"1"`**（`"0"` = 存量更新） |
| 优先级 | 最高，覆盖快照演算结果 |
| 校验时机 | ★ **扫码之前**就校验 —— JSON 写错直接退出，不浪费二维码 |

> ⚠ 在 PowerShell / CMD 里写内联 JSON 很容易被吞掉双引号，
> **建议一律用文件**（`--extra-data extra.json`）。

---

## 主脚本怎么写

**核心原则：不要为每个 api 调用写日志。** 日志已经在 `api/` 里了。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from api import (setup_logging, teardown_logging,
                 ParseQRCode, UserPreview, UserLogin, UserLogout, LogoutType,
                 UpsertUserAll)
from config import REGION_ID, PLACE_ID

def main() -> int:
    setup_logging("我的脚本")          # ← 只需要这一句
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        user_id, token = ParseQRCode(sys.argv[1])
        session.update(user_id=user_id, token=token)

        UserPreview(user_id, token)                        # 顶号保护
        login = UserLogin(user_id, token,
                          region_id=REGION_ID, place_id=PLACE_ID)
        session.update(login_dt=login.loginDateTime, logged_in=True)

        # ★ 一个函数跑完整条结算链路
        UpsertUserAll(user_id, login.loginId,
                      login_date_time=login.loginDateTime,
                      auth_date_time=login.dateTime,
                      token=token,
                      dry_run=False, confirm=True)
        return 0
    finally:
        if session["logged_in"]:                           # ★ 一定要保证登出
            UserLogout(session["user_id"], session["token"], session["login_dt"],
                       logout_type=LogoutType.TestIn,
                       region_id=REGION_ID, place_id=PLACE_ID)
        teardown_logging()

if __name__ == "__main__":
    sys.exit(main())
```

三条铁律：

1. **不要写日志** —— 每个 api 函数会自动打印 `=== 函数名 开始运行 ===` / `[运行结果]`
2. **一定要登出** —— 账号卡在 `isLogin=True` 时下次登录会 `returnCode=100`
3. **写接口要显式开闸门** —— 只写 `dry_run=False` 不够，必须同时给 `confirm=True`

完整指南见 [主脚本编写指南](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/主脚本编写指南.md)。

---

## 将来

v0 只是起点，后续可能会加：

- **网页控制** —— 用浏览器代替命令行操作
- 更多游戏功能（任务 / 地图 / 收藏夹 / 排行榜……）
- 更完整的真机验证覆盖

---

## 特别鸣谢

- **志成🍥** —— 提供脱壳 DLL
- **WorkBuddyAI**（[workbuddy.ai](https://www.workbuddy.ai/)）—— 提供 AI 模型
- **DeepSeek V4.1 Flash** —— 主要代码编写
- **NVIDIA NIM**（[build.nvidia.com/models](https://build.nvidia.com/models)）、
  **AMD**（[developer.amd.com.cn/radeon/tokenfactory](https://developer.amd.com.cn/radeon/tokenfactory)）、
  **Kilo**（[kilo.ai](https://kilo.ai/)）—— 提供 AI 模型
- **eaquira**（[git.fragrance.moe/Fragrance/eaquira](https://git.fragrance.moe/Fragrance/eaquira)）—— 思路启发
- **神秘群U** —— 私有科技的 Web 启发（暂无）
- **香水所有群友** —— 和谐帮助

*（还有什么以后补充）*

---

## 免责声明

本项目仅供**学习与协议研究**使用。使用本工具产生的任何后果由使用者自行承担。
请遵守游戏服务条款，不要用于破坏游戏公平性。
