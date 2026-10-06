# -*- coding: utf-8 -*-
"""
get_user_preview.py —— 用户预览（GetUserPreviewApi）
================================================================================

功能：刷卡后欢迎界面的数据（昵称、Rating、是否已登录、封禁状态…）。

对应接口：GetUserPreviewApi
请求体  ：{"userId":.., "segaIdAuthKey":"", "token":"..", "clientId":".."}
          source/Assembly-CSharp/Net.VO.Mai2/UserPreviewRequestVO.cs
          source/Assembly-CSharp/Net.Packet.Mai2/PacketGetUserPreview.cs:20-25
响应    ：见 UserPreviewResponseVO（23 字段，含 errorId）

★ 真机调用时机：扫码拿到 userId/token 之后、UserLoginApi 之前
   （source/2026-10-05.log:23）。
★ 客户端行为：isLogin=True 时拒绝继续登录，避免顶号
   （source/Assembly-CSharp/Process.Entry.State/ConfirmPlay.cs:151）。

调用示例：
    from api import GetUserPreview
    pv = GetUserPreview(12345678, "TESTTOKEN0000000000")
    print(pv.userName, pv.playerRating)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import CLIENT_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict


@dataclass
class UserPreviewRequestVO:
    """请求 VO（对应 UserPreviewRequestVO）。"""
    userId: int
    segaIdAuthKey: str = ""
    token: str = ""
    clientId: str = ""


@dataclass
class UserPreviewResponseVO:
    """
    响应 VO（对应 UserPreviewResponseVO + 真机响应字段）。

    ★ 字段顺序按 source/Assembly-CSharp/Net.VO.Mai2/UserPreviewResponseVO.cs
      与 source/2026-10-05.log:24 的真机响应合并。
    """
    userId: int = 0
    userName: str = ""
    isLogin: bool = False
    lastGameId: Optional[str] = None
    lastRomVersion: str = ""
    lastDataVersion: str = ""
    lastLoginDate: str = ""
    lastPlayDate: str = ""
    playerRating: int = 0
    nameplateId: int = 0
    iconId: int = 0
    trophyId: int = 0
    partnerId: int = 0
    frameId: int = 0
    dispRate: int = 0
    totalAwake: int = 0
    isNetMember: int = 0
    dailyBonusDate: str = ""
    headPhoneVolume: Optional[int] = None
    isInherit: bool = False
    banState: int = 0
    errorId: int = 0


def GetUserPreview(
    user_id: int,
    token: str,
    *,
    client_id: str = CLIENT_ID,
    sega_id_auth_key: str = "",
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> UserPreviewResponseVO:
    """
    获取用户预览信息。

    参数：
        user_id:          用户 ID（必填）
        token:            会话令牌（必填，来自 ParseQRCode）
        client_id:        机台短值（可选）
        sega_id_auth_key: SEGA ID 鉴权 key（可选，通常为空）
        timeout_ms:       超时毫秒（可选）
        client:           可复用的 MaimaiNetClient（可选）

    返回：
        UserPreviewResponseVO
    """
    log_info("获取用户预览：user_id=" + str(user_id) + " client_id=" + client_id)

    raw = request_dict(
        "GetUserPreviewApi",
        UserPreviewRequestVO(
            userId=user_id,
            segaIdAuthKey=sega_id_auth_key,
            token=token,
            clientId=client_id,
        ),
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    known = {f for f in UserPreviewResponseVO.__dataclass_fields__}
    resp = UserPreviewResponseVO(**{k: v for k, v in raw.items() if k in known})

    if resp.errorId != 0:
        log_warning("服务器返回 errorId=" + str(resp.errorId))
    if resp.banState != 0:
        log_warning("账号可能被封禁：banState=" + str(resp.banState))
    if resp.isLogin:
        log_warning("账号处于已登录状态（isLogin=True），继续登录会顶号")

    log_info(
        "用户预览获取完成：userName=" + resp.userName
        + " playerRating=" + str(resp.playerRating)
        + " isLogin=" + str(resp.isLogin)
        + " isNetMember=" + str(resp.isNetMember)
    )
    return resp


if __name__ == "__main__":
    import sys

    from .log_setup import log_error, setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("userpreview_test")
        try:
            if len(sys.argv) < 3:
                print("用法: python -m api.get_user_preview <user_id> <token> [client_id]")
                return 1
            cid = sys.argv[3] if len(sys.argv) > 3 else CLIENT_ID
            pv = GetUserPreview(int(sys.argv[1]), sys.argv[2], client_id=cid)
            print("")
            for name in UserPreviewResponseVO.__dataclass_fields__:
                print("   " + name.ljust(18) + "= " + str(getattr(pv, name)))
            return 0
        except Exception as exc:
            log_error("获取用户预览失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
