# -*- coding: utf-8 -*-
"""
get_game_settings.py —— 获取游戏设置（GetGameSettingApi）
================================================================================

功能：取服务器下发的运行时配置（维护窗口、心跳间隔、包超时、各类上限）。

对应接口：GetGameSettingApi
请求体  ：{"placeId": <店铺ID>, "clientId": "<机台短值>"}
          source/Assembly-CSharp/Net.VO.Mai2/GameSettingRequestVO.cs
          source/Assembly-CSharp/Net.Packet.Mai2/PacketGetGameSetting.cs:21-24

★ 真机调用时机：会话最开始、Ping 之前（source/2026-10-05.log:1）。

调用示例：
    from api import GetGameSettings
    resp = GetGameSettings()
    print(resp.gameSetting.isMaintenance, resp.gameSetting.requestInterval)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config import CLIENT_ID, PLACE_ID, TIMEOUT_MS

from .log_setup import log_info, log_warning
from .maimai_net import MaimaiNetClient, request_dict


# =============================================================================
# VO（字段对照 source/Assembly-CSharp/Net.VO.Mai2/GameSetting.cs 与真机响应）
# =============================================================================

@dataclass
class GameSetting:
    """游戏运行时配置（对应 Net.VO.Mai2.GameSetting）。"""
    isMaintenance: bool = False
    requestInterval: int = 0
    rebootStartTime: str = ""
    rebootEndTime: str = ""
    rebootInterval: int = 0
    movieUploadLimit: int = 0
    movieStatus: int = 0
    movieServerUri: str = ""
    deliverServerUri: str = ""
    oldServerUri: str = ""
    usbDlServerUri: str = ""
    maxCountRivalMusic: int = 0
    replicationDelayLimit: int = 0
    exclusionStartTime: str = ""
    exclusionEndTime: str = ""
    pingDisable: bool = False
    packetTimeout: int = 0
    packetTimeoutLong: int = 0
    packetRetryCount: int = 0
    userDataDlErrTimeout: int = 0
    userDataDlErrRetryCount: int = 0
    userDataDlErrSamePacketRetryCount: int = 0
    userDataUpSkipTimeout: int = 0
    userDataUpSkipRetryCount: int = 0
    iconPhotoDisable: bool = False
    uploadPhotoDisable: bool = False
    photoDisableArea: Optional[str] = None
    collectDelayInfoDisable: bool = False
    maxCountMusic: int = 0
    maxCountItem: int = 0
    nameEntryDisable: bool = False
    packetRecreateCount: int = 0


@dataclass
class GameSettingRequestVO:
    """请求 VO（对应 GameSettingRequestVO）。"""
    placeId: int = 0
    clientId: str = ""


@dataclass
class GameSettingResponseVO:
    """响应 VO（对应 GameSettingResponseVO）。"""
    isAouAccession: bool = False
    gameSetting: GameSetting = field(default_factory=GameSetting)


# =============================================================================
# 公开 API
# =============================================================================

def GetGameSettings(
    *,
    place_id: int = PLACE_ID,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> GameSettingResponseVO:
    """
    获取游戏设置（服务器下发的运行时配置）。

    参数：
        place_id:  店铺 ID（可选，默认 config.PLACE_ID）
        client_id: 机台短值（可选，默认 config.CLIENT_ID）
        timeout_ms: 超时毫秒（可选）
        client:    可复用的 MaimaiNetClient（可选）

    返回：
        GameSettingResponseVO
    """
    log_info("获取游戏设置：place_id=" + str(place_id) + " client_id=" + client_id)

    raw = request_dict(
        "GetGameSettingApi",
        GameSettingRequestVO(placeId=place_id, clientId=client_id),
        user_id=0, client_id=client_id,
        timeout_ms=timeout_ms or TIMEOUT_MS, client=client,
    )

    gs_raw = raw.get("gameSetting") or {}
    known = {f for f in GameSetting.__dataclass_fields__}
    gs = GameSetting(**{k: v for k, v in gs_raw.items() if k in known})
    resp = GameSettingResponseVO(
        isAouAccession=bool(raw.get("isAouAccession", False)),
        gameSetting=gs,
    )

    if gs.isMaintenance:
        log_warning("服务器处于维护状态（isMaintenance=True）")
    if gs.pingDisable:
        log_info("服务器已禁用心跳（pingDisable=True）")

    log_info(
        "游戏设置获取完成：isMaintenance=" + str(gs.isMaintenance)
        + " requestInterval=" + str(gs.requestInterval)
        + " packetTimeout=" + str(gs.packetTimeout)
        + " packetTimeoutLong=" + str(gs.packetTimeoutLong)
        + " pingDisable=" + str(gs.pingDisable)
    )
    return resp


def is_maintenance(settings: GameSettingResponseVO) -> bool:
    """便捷判断：服务器是否处于维护状态。"""
    return bool(settings.gameSetting.isMaintenance)


def is_ping_disabled(settings: GameSettingResponseVO) -> bool:
    """便捷判断：是否已禁用心跳。"""
    return bool(settings.gameSetting.pingDisable)


# =============================================================================
# 单独运行（调试）
# =============================================================================

if __name__ == "__main__":
    from .log_setup import setup_logging, teardown_logging

    def _main() -> int:
        setup_logging("gamesettings_test")
        try:
            resp = GetGameSettings()
            gs = resp.gameSetting
            print("")
            for name in GameSetting.__dataclass_fields__:
                print("   " + name.ljust(34) + "= " + str(getattr(gs, name)))
            return 0
        except Exception as exc:
            from .log_setup import log_error
            log_error("获取游戏设置失败：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
