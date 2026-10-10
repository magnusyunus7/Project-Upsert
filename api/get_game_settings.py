# -*- coding: utf-8 -*-
"""
get_game_settings.py —— getTaketext（GetGameSettingApi）
================================================================================

Features：Get the runtime configuration sent by the server（text、Heartbeat Interval、Package timeout、Various upper limits）。

Corresponding interface：GetGameSettingApi
request body  ：{"placeId": <StoreID>, "clientId": "<machineStageshortValue>"}
          source/Assembly-CSharp/Net.VO.Mai2/GameSettingRequestVO.cs
          source/Assembly-CSharp/Net.Packet.Mai2/PacketGetGameSetting.cs:21-24

★ real machinecallusetimemachine：Session Start、Ping Before（source/2026-10-05.log:1）。

call exampleExample：
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
# VO（Field Comparison source/Assembly-CSharp/Net.VO.Mai2/GameSetting.cs Response to real machine）
# =============================================================================

@dataclass
class GameSetting:
    """texttimetext（Corresponding Net.VO.Mai2.GameSetting）。"""
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
    """request VO（Corresponding GameSettingRequestVO）。"""
    placeId: int = 0
    clientId: str = ""


@dataclass
class GameSettingResponseVO:
    """Response VO（Corresponding GameSettingResponseVO）。"""
    isAouAccession: bool = False
    gameSetting: GameSetting = field(default_factory=GameSetting)


# =============================================================================
# Public API
# =============================================================================

def GetGameSettings(
    *,
    place_id: int = PLACE_ID,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
) -> GameSettingResponseVO:
    """
    getTaketext（serverIssueoftexttimetext）。

    Parameter：
        place_id:  Store ID（Optional，default config.PLACE_ID）
        client_id: machineStageshortValue（Optional，default config.CLIENT_ID）
        timeout_ms: timeout milliseconds（Optional）
        client:    Reusable MaimaiNetClient（Optional）

    returntimes：
        GameSettingResponseVO
    """
    log_info("getTaketext：place_id=" + str(place_id) + " client_id=" + client_id)

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
        log_warning("serverplaceintext（isMaintenance=True）")
    if gs.pingDisable:
        log_info("serverAlreadytextuseHeartbeat（pingDisable=True）")

    log_info(
        "textgetTakeDone：isMaintenance=" + str(gs.isMaintenance)
        + " requestInterval=" + str(gs.requestInterval)
        + " packetTimeout=" + str(gs.packetTimeout)
        + " packetTimeoutLong=" + str(gs.packetTimeoutLong)
        + " pingDisable=" + str(gs.pingDisable)
    )
    return resp


def is_maintenance(settings: GameSettingResponseVO) -> bool:
    """Convenient Judgment：serverisNoplaceintext。"""
    return bool(settings.gameSetting.isMaintenance)


def is_ping_disabled(settings: GameSettingResponseVO) -> bool:
    """Convenient Judgment：isNoAlreadytextuseHeartbeat。"""
    return bool(settings.gameSetting.pingDisable)


# =============================================================================
# Run separately（debug）
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
            log_error("getTaketextFailed：" + str(exc))
            return 1
        finally:
            teardown_logging()

    raise SystemExit(_main())
