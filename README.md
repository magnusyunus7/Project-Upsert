# WaHappy

> **舞萌DX 的游戏助手**
>
> 宗旨：让舞萌DX的玩家能够更好地游玩游戏，获得快乐。

---

## 这是什么

WaHappy 是一个用 **Python 纯网络方式**与舞萌DX（SDGB 国服）游戏服务器交互的工具集。

它不修改游戏、不注入进程，只是把游戏客户端做的事用脚本重做一遍：
扫码登录 → 取数据 → 上传成绩 → 登出。

> 协议实现全部来自反编译源码 `source/Assembly-CSharp/` 与真机网络日志的双向验证，
> 每个关键常量在代码注释里都标了**源码行号**。

---

## 当前状态：v0，**未完工**

**v0 目前只是一个占位版本，请以「能不能用」而不是「有多少代码」来判断它。**

| 模块 | 状态 |
|---|---|
| **`upsert.py`** | ✅ **可用** —— 扫码登录 → 上传一局成绩 → 落库回查 → 登出 |
| `buy_ticket.py` | ⚠️ **不可用** —— 购买功能票接口疑似已被服务端拉黑，见下方警告 |
| `api/` 下 40+ 个接口模块 | 🔧 已实现并通过零网络自检，但**未全部在真机上验证过** |
| **文档** | 📄 在 **`docs` 分支**（主分支不含）—— 开发过程、踩坑记录、实跑验证，内容比代码本身还多 |

### ⚠️ 关于购买功能票

`buy_ticket.py`（`UpsertUserChargelogApi`）在**报文与真机逐字节一致**的情况下
仍被服务端拒绝（`returnCode=0`），之后该账号**疑似被拉黑，暂时无法再购买功能票**。

**请勿轻易重试该接口。** 完整排查过程见
[购买功能票流程](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs/docs/购买功能票流程.md) 第六节。

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
├── config.py            运行时可配置项（密钥 / 机台 / 歌曲数据 / 日志级别）
├── upsert.py            ★ 主脚本：扫码登录 → 上传成绩 → 登出
├── buy_ticket.py        主脚本：购买功能票（★ 当前不可用）
├── selftest.py          零网络自检（236 项，判据 = 源码 + 真机日志）
│
├── api/                 ★ 所有与服务器交互的模块（一个接口一个脚本）
│   ├── __init__.py      统一导出 + 日志自动跟踪
│   ├── maimai_net.py    网络核心（AES / deflate / URL 混淆 / Cookie）
│   ├── log_setup.py     日志（INFO / DEBUG 双模式）
│   ├── upsert_user_all.py      上传成绩（36 节点 / 110 字段 / 差分）
│   ├── upsert_snapshot.py      结算基线快照
│   └── ...                     40+ 个接口脚本
│
├── logs/                日志输出（latest.log + 日期.log）★ 不入库
└── source/              反编译源码 + 真机日志 ★ 不入库（版权 + 隐私）
```

**设计约定**：`api/` 里每个脚本 = 一个接口，对外暴露一个**能传参的函数**。
主脚本只负责编排，日志和协议细节都在 `api/` 内部。

> **`docs/` 在 [`docs` 分支](https://git.fragrance.moe/Txiaochen/wahappy/src/branch/docs)，`source/` 与 `logs/` 不入库。**
>
> `source/` 是本地查证用的反编译源码（含 SEGA 二进制与真机日志），
> 代码注释里写的 `source/Assembly-CSharp/xxx.cs:123` 都是**引用出处**，
> 需要自己准备一份才能逐行核对。

---

## 快速开始

### 环境

```bash
pip install requests pycryptodome
python selftest.py        # 零网络自检，应该 236 项全绿
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

> 内容暂时不写太多，等真正做出来再说。

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
