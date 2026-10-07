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

## 当前状态：v0

| 脚本 | 状态 |
|---|---|
| **`upsert.py`** | ✅ **可用** —— 扫码登录 → 上传一局成绩 → 落库回查 → 登出 |
| **`buy_ticket.py`** | ✅ **可用** —— 购买功能票 |
| **`use_ticket.py`** | ✅ **可用** —— 消耗当前持有的功能票 |
| **`reincarnate.py`** | 🔧 已实现（**未实跑**）—— 账号数据迁移（转生） |
| **`netdelivery.py`** | ✅ **可用** —— 查 / 下 `.app` / `.opt` 更新包（只读） |
| `api/` 下 40+ 个接口模块 | 🔧 已实现并通过零网络自检，但**未全部在真机上验证过** |

**文档**在 [`docs` 分支](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)，见文末[文档索引](#文档索引)。

---

## 一个教训：别把一件事分段交给 AI

v0 的开发过程中，我反复把同一个目标拆成小段丢给 AI，结果：

| 项目 | Token 消耗 |
|---|---|
| **v0 有效开发** | **473M+** |
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
├── config.py            运行时可配置项（机台标识 / 歌曲数据 / 日志级别）★ 需自建
├── config.py.example    配置模板
├── upsert.py            ★ 主脚本：扫码登录 → 上传成绩 → 登出
├── buy_ticket.py        主脚本：购买功能票
├── use_ticket.py        主脚本：消耗当前持有的功能票
├── reincarnate.py       主脚本：账号数据迁移（转生）
├── netdelivery.py       主脚本：查 / 下 .app / .opt 更新包
├── selftest.py          零网络自检（249 项，判据 = 源码 + 真机日志）
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
├── download/            netdelivery.py 下载的 .app / .opt ★ 不入库
├── logs/                日志输出（latest.log + 日期.log）★ 不入库
└── source/              反编译源码 ★ 不入库，需自备
```

**设计约定**：`api/` 里每个脚本 = 一个接口，对外暴露一个**能传参的函数**。
主脚本只负责编排，日志和协议细节都在 `api/` 内部。

**命名约定**：服务端 API 名里带 `Get` 的，**脚本名与函数名一律带 `get` / `Get`**
（不要模棱两可）。所以取数脚本全是 `get_*.py`，函数是 `GetXxx`。

### 分支说明

| 分支 | 内容 |
|---|---|
| **`mai`** | 主分支 —— 代码 |
| **`docs`** | 孤儿分支 —— 只有 `docs/`，开发文档与踩坑记录 |

两个分支**没有共同的提交历史**，各自独立。
`source/` 是反编译源码，**需要自备**。

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

然后**必须**填好 **`config.py` 第二节「机台与店铺标识」**：

| 变量 | 填什么 |
|---|---|
| `CLIENT_ID` | Keychip 短值（15 位 Keychip 去掉连字符取前 11 位），形如 `A63E01ABCDE` |
| `PLACE_ID` | 你所在店铺 ID |
| `REGION_ID` | 你所在区域 ID |
| `PLACE_NAME` | 店铺名 |
| `REGION_NAME` | 区域名 |
| `KEYCHIP_ID` | **由上面两个值自动推导**，不要手改 |

> ⚠️ 填错的话，发出去的请求带的就是别人的机台身份，服务端会直接拒绝。
>
> `config.py` 已在 `.gitignore` 里 —— 它是你的私有配置，**不要提交**。

### 3. 跑自检

```bash
python selftest.py        # 零网络自检，应该 249 项全绿（不依赖你的 config）
```

### 主脚本一览

| 脚本 | 干什么 | 副作用 | 需要二维码 |
|---|---|---|---|
| `upsert.py` | 上传一局成绩 | ★ 有 | ✅ |
| `buy_ticket.py` | 购买功能票 | ★ 有 | ✅ |
| `use_ticket.py` | 消耗当前持有的功能票 | ★ 有 | ✅ |
| `reincarnate.py` | 账号数据迁移（转生） | ★ 有 | ✅（目标号；源号可选） |
| `netdelivery.py` | 查 / 下 `.app` / `.opt` 更新包 | 只读 | ❌ |
| `selftest.py` | 零网络自检 | 无 | ❌ |

> **所有有副作用的脚本默认都不发包**：不传 `--send` 时只构造报文（dry-run）。
> 想看报文而不产生任何后果，先跑一次不带 `--send` 的。

> 二维码从机台的「扫码登录」界面获取，**有效期 10 分钟**（不是按次数计量的）。

---

## upsert.py —— 上传一局成绩

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

### 额外塞节点：`--extra-data`

想手工覆盖某几个节点（比如本局拿到的新 KaleidxScope 门）：

```bash
python upsert.py "<二维码>" --send --extra-data extra.json
```

键必须是 `upsertUserAll` 的 **36 个节点**之一，写错会报错并列出可用节点名。
**JSON 在扫码之前就校验**，写错直接退出，不浪费二维码。

> ⚠️ 在 PowerShell / CMD 里写内联 JSON 很容易被吞掉双引号，**建议一律用文件**。

---

## buy_ticket.py —— 购买功能票

```bash
python buy_ticket.py "<二维码>" --list                    # 只列当前票券和可买的票
python buy_ticket.py "<二维码>" --charge-id 2             # 预检：只看报文
python buy_ticket.py "<二维码>" --charge-id 2 --send      # ★ 真实购买
```

| chargeId | 票 | 上报的 `price` |
|---|---|---|
| 2 | 2倍チケット | 1 |
| 3 | 3倍チケット | 2 |
| 5 | 5倍チケット | 4 |

> 默认 `--charge-id 5`。**不同店铺上架的票不一样**，买之前先 `--list`。

### 它做的安全检查

1. 买之前查 `GetGameChargeApi` —— 目标票不在可购买清单里就**连登录都不做**直接退出
2. 跑前查 `GetUserChargeApi` —— **账号已持有功能票时直接拒绝购买**（重复购买有封号风险）
3. 跑后再查一次确认状态

---

## use_ticket.py —— 消耗当前持有的功能票

```bash
python use_ticket.py "<二维码>" --list                  # 只列当前持有的票
python use_ticket.py "<二维码>" --ticket-id 2 --send    # ★ 真实消耗
```

**原理**：`GetUserChargeApi` 与 `UpsertUserAllApi` 里的 `userChargeList` **格式完全相同**，
所以把该节点里目标票的 `stock` 减 1，再让 playlog 带上 `useTicketId` / `playCredit`，
服务端就认为这张票被这一局用掉了。

> **典型用途**：账号手里挂着票时 `buy_ticket.py` 会拒绝再买；
> 想再买一张就先用这个把它用掉。

详细原理与报文依据见 [功能票使用说明](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/功能票使用说明.md)。

---

## reincarnate.py —— 账号转生

把一个账号（源 A）的数据克隆到另一个账号（目标 B）。

```bash
# 源数据来自二维码（会联网抓 A 的数据并落盘到 data/<A>.json）
python reincarnate.py --dst-qr "<B的二维码>" --src-qr "<A的二维码>"

# 源数据来自已保存的 JSON（离线，推荐）
python reincarnate.py --dst-qr "<B的二维码>" --src-json data/12345678.json --plan
python reincarnate.py --dst-qr "<B的二维码>" --src-json data/12345678.json --send
```

**它干了什么**：

1. 取源账号 A 的 19 个节点数据（联网抓或读 `data/<A>.json`）
2. 用目标账号 B 的二维码登录
3. 把 A 的 `userMusicDetailList` **分批**上传到 B —— 每包最多 4 首，
   并自动避开**被服务端禁止的 2 首包**（`[4,4,2]` → `[4,3,3]`）
4. 每包之间：**等待 → 上传 → 登出（type=1）→ 续关登录**，循环到传完
5. 每包的 playlog 从曲目记录**反推合成**（`achievement` / `deluxscore` / `scoreRank` …）

| 参数 | 默认 | 说明 |
|---|---|---|
| `--plan` | — | 只列分批计划，不发包（**建议先跑这个**） |
| `--limit N` | 0（全部） | 只迁前 N 首（试跑用） |
| `--per-packet N` | 4 | 每包曲目数，**只能是 1 / 3 / 4** |
| `--wait N` | 5.0 | 每次上传前的等待秒数 |
| `--clone-identity` | 关 | 连 `userName` / `accessCode` 一起克隆（默认保留 B 自己的） |

> ⚠️ **未实跑过。** 建议先 `--plan`，再 `--limit 8` 小批量试。

完整流程、分批规则、续关与登出类型的依据见 [账号转生说明](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/账号转生说明.md)。

---

## netdelivery.py —— 查 / 下 `.app` / `.opt` 更新包

```bash
python netdelivery.py                 # 用 config.py 里的机台查，然后**多选下载**
python netdelivery.py A63E01ABCDE     # 指定 Keychip
python netdelivery.py --list          # 只列清单 + 直链，不下载
python netdelivery.py --all           # 全下（不交互）
python netdelivery.py --only 1,3      # 只下第 1、3 项（不交互）
python netdelivery.py --ver 1.55      # 指定上报版本（默认 config.MAI_ENCODING）
python netdelivery.py --out D:\SDGB2026\update
```

交互选择支持：逗号/空格分隔、区间（`1-3`）、`a`=全选、`n`=全不选、`q`=退出。
下载带**断点续传**与进度/速率显示，默认存到 `download/`（不入库）。

> 这是**只读**操作，不写任何账号数据。
> 需要同目录下的 `authv1.py` 提供 ALL.Net 协议层。

---

## 主脚本怎么写

**核心原则：不要为每个 api 调用写日志。** 日志已经在 `api/` 里了。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from api import (setup_logging, teardown_logging,
                 ParseQRCode, GetUserPreview, UserLogin, UserLogout, LogoutType,
                 UpsertUserAll)
from config import REGION_ID, PLACE_ID

def main() -> int:
    setup_logging("我的脚本")          # ← 只需要这一句
    session = {"user_id": 0, "token": "", "login_dt": 0, "logged_in": False}
    try:
        user_id, token = ParseQRCode(sys.argv[1])
        session.update(user_id=user_id, token=token)

        GetUserPreview(user_id, token)                     # 顶号保护
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
                       logout_type=LogoutType.Logout,
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

## 已完成 / 将来

**已完成（v0）**

- ✅ 扫码登录 / 登出 / 心跳，完整会话链路
- ✅ 上传一局成绩（36 节点 / 110 字段 / 差分 / 落库回查）
- ✅ 购买功能票
- ✅ 消耗持有的功能票
- ✅ 账号数据快照落盘（`data/<userId>.json`）
- ✅ 账号数据迁移（转生）
- ✅ 查 / 下 `.app` / `.opt` 更新包
- ✅ 零网络自检 249 项
- ✅ MelonLoader 抓包 Mod（`gamehook/`）

**将来可能会加**

- **网页控制** —— 用浏览器代替命令行操作
- 更多游戏功能（任务 / 地图 / 收藏夹 / 排行榜……）
- 更完整的真机验证覆盖
- `reincarnate.py` 的实跑验证

---

## 文档索引

全部在 [`docs` 分支](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)：

| 文档 | 内容 |
|---|---|
| [项目总览](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/项目总览.md) | 开发向主文档，该放哪 / 该怎么写 |
| [主脚本编写指南](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/主脚本编写指南.md) | 写新主脚本的规范 |
| [上传成绩开发文档](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/上传成绩开发文档.md) | `UpsertUserAll` 的 36 节点 / 110 字段 |
| [UpsertUserAll踩坑清单](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/UpsertUserAll踩坑清单.md) | 28 条踩坑记录 |
| [功能票使用说明](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/功能票使用说明.md) | 买票 / 用票的完整原理与报文依据 |
| [账号转生说明](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/账号转生说明.md) | `reincarnate.py` 完整流程 |
| [netdelivery说明](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/netdelivery说明.md) | DLI 协议与运行原理 |
| [常见坑与注意事项](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/常见坑与注意事项.md) | 二维码 / 账号状态 / 副作用 / 日志 / 网络 |
| [购买功能票流程](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/购买功能票流程.md) | 买票接口的完整排查过程 |
| [购买功能票_存档与交接](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/购买功能票_存档与交接.md) | 排查存档 |
| [真机Hook对照报告](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/真机Hook对照报告.md) | 抓包 Mod 对照 |
| [实跑验证记录](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/实跑验证记录.md) | 每次实跑的结果 |
| [舞萌DX_扫码登录协议技术规范](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/舞萌DX_扫码登录协议技术规范.md) | aimedb 扫码协议 |
| [日志与主脚本指南](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/日志与主脚本指南.md) | 日志系统说明 |

---

## 特别鸣谢

- **志成🍥** —— 提供脱壳 DLL
- **WorkBuddyAI**（[workbuddy.ai](https://www.workbuddy.ai/)）—— 提供 AI 模型
- **DeepSeek V4.1 Flash** —— 主要代码编写
- [**NVIDIA NIM**](https://build.nvidia.com/models)、
  [**AMD**](https://developer.amd.com.cn/radeon/tokenfactory)、
  [**Kilo**](https://kilo.ai/)—— 提供 AI 模型
- **eaquira**（[git.fragrance.moe/Fragrance/eaquira](https://git.fragrance.moe/Fragrance/eaquira)）—— 思路启发
- **神秘群U** —— 私有科技的 Web 启发（暂无）
- **香水所有群友** —— 和谐帮助

*（还有什么以后补充）*

---

## 免责声明

本项目仅供**学习与协议研究**使用。使用本工具产生的任何后果由使用者自行承担。
请遵守游戏服务条款，不要用于破坏游戏公平性。
