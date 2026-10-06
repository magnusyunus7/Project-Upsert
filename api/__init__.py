# -*- coding: utf-8 -*-
"""
api 包 —— 统一导出
================================================================================

主脚本只需要 from api import ... 就能拿到全部功能。

★ 本文件在导入时就给下面 _API_FUNCS 里列出的每个函数套上「日志外壳」，
  所以主脚本拿到的已经是带日志的版本 —— 调用时会自动产出：

      === ParseQRCode 开始运行 ===
        [接口说明] 解析二维码并换取 userId 与 token。
        [位置参数] 'SGWCMAID2610022219463A297AF4CA...'
        [运行结果] 成功 tuple(2 项)（耗时 412 ms）
      === ParseQRCode 运行结束 ===

  主脚本**不需要**写装饰器，也不需要自己埋点。

--------------------------------------------------------------------------------
目录结构（一个 api 一个脚本）
--------------------------------------------------------------------------------
  基础设施
    log_setup.py             统一日志（INFO / DEBUG 双模式）
    maimai_net.py            网络核心（AES / deflate / URL 混淆 / Cookie）
    user_getter_common.py    取数脚本公共底座（请求 VO / _get / 翻页）

  会话链路
    chime.py                 扫码登录 -> userId + token
    gamesettings.py          取游戏设置
    ping.py                  心跳探活
    userpreview.py           用户预览
    userlogin.py             正式登录 -> loginId + loginDateTime
    userlogout.py            登出

  上传成绩
    upsert_user_all.py       ★ 上传成绩（唯一有副作用的接口）
    upsert_snapshot.py       结算快照编排（统一调用下面的取数脚本）

  取数（一个接口一个脚本）
    userdata.py              GetUserDataApi
    user_extend.py           GetUserExtendApi
    user_option.py           GetUserOptionApi
    user_character.py        GetUserCharacterApi
    user_ghost.py            GetUserGhostApi
    user_map.py              GetUserMapApi
    user_login_bonus.py      GetUserLoginBonusApi
    user_rating.py           GetUserRatingApi
    user_item.py             GetUserItemApi
    user_music.py            GetUserMusicApi
    user_course.py           GetUserCourseApi
    user_charge.py           GetUserChargeApi
    user_favorite.py         GetUserFavoriteApi
    user_activity.py         GetUserActivityApi
    user_mission.py          GetUserMissionDataApi
    user_intimate.py         GetUserIntimateApi
    user_shop_stock.py       GetUserShopStockApi
    user_favorite_item.py    GetUserFavoriteItemApi
    user_rival.py            GetUserRivalDataApi / GetUserRivalMusicApi
    user_friend_bonus.py     GetUserFriendBonusApi
    user_kaleidx_scope.py    GetUserKaleidxScopeApi / GetGameKaleidxScopeApi
    user_region.py           GetUserRegionApi
    user_recommend_music.py  GetUserRecommendRateMusicApi / GetUserRecommendSelectMusicApi
    user_new_item.py         GetUserNewItemListApi
    game_ranking.py          GetGameRankingApi
    game_event.py            GetGameEventApi
    game_charge.py           GetGameChargeApi
    game_weekly_data.py      GetGameWeeklyDataApi
    game_tournament_info.py  GetGameTournamentInfoApi
    game_ng_music_id.py      GetGameNgMusicIdApi
"""

from .log_setup import (
    # 会话
    setup_logging,
    teardown_logging,
    # 自动跟踪
    autowrap,
    get_called_apis,
    # 模式
    get_level,
    set_level,
    is_debug,
    LEVEL_INFO,
    LEVEL_DEBUG,
    # 装饰器 / 兼容
    api_log,
    get_logger,
    # 流程日志（INFO 可见）
    log_info,
    log_step,
    log_result,
    log_warning,
    log_error,
    log_section,
    log_field,
    log_debug,
    # 收发数据日志（DEBUG 专属）
    log_request,
    log_response,
    log_payload,
)

# ---------------------------------------------------------------------------
# 1) 网络核心
# ---------------------------------------------------------------------------

from .maimai_net import (
    MaimaiNetClient,
    MaimaiNetError,
    get_default_client,
    close_default_client,
    request,
    request_dict,
    request_vo,
    obfuscate_api_name,
    build_api_url,
    build_user_agent,
    adler32,
    aes_encrypt,
    aes_decrypt,
    deflate_compress,
    deflate_decompress,
    vo_to_json,
    vo_from_json,
    local_utc_offset_seconds,
    login_date_time_now,
    EmptyRequestVO,
    UserIdRequestVO,
    ReturnCodeVO,
)

# ---------------------------------------------------------------------------
# 2) 会话链路
# ---------------------------------------------------------------------------

from .chime import ParseQRCode

from .gamesettings import (
    GetGameSettings,
    GameSetting,
    GameSettingRequestVO,
    GameSettingResponseVO,
    is_maintenance,
    is_ping_disabled,
)

from .ping import Ping

from .userpreview import (
    UserPreview,
    UserPreviewRequestVO,
    UserPreviewResponseVO,
)

from .userlogin import (
    UserLogin,
    UserLoginRequestVO,
    UserLoginResponseVO,
)

from .userlogout import (
    UserLogout,
    LogoutType,
    DelayLog,
    RequestAPI,
    UserLogoutRequestVO,
    UserLogoutRequest2VO,
    UserLogoutResponseVO,
    create_empty_delay_log,
    create_delay_log_from_stats,
    DELAY_LOG_SLOTS,
)

# ---------------------------------------------------------------------------
# 3) 上传成绩
# ---------------------------------------------------------------------------

from .upsert_user_all import (
    UpsertUserAll,
    PlayData,
    build_play_from_config,
    derive_play_characters,
    UserAllRequestVO,
    UpsertResponseVO,
    UpsertUserAllError,
    ConfirmRequiredError,
    PatchError,
    # 节点结构
    NODE_TYPES,
    NODE_ORDER,
    BITS_TO_ARRAY,
    ARRAY_TO_BITS,
    DIFF_PRIMARY_KEYS,
    MAY_BE_EMPTY_NODES,
    DEFAULT_EMPTY_NODES,
    # 组包辅助
    empty_node,
    empty_user_all,
    coerce_node_value,
    sync_bits_to_arrays,
    build_delta,
    build_favorite_delta,
    build_user_all,
    build_user_playlog,
    build_user_game_playlog,
    build_post_play_user_data,
    validate_user_playlog,
    validate_before_send,
    apply_play_effects,
    # ★ 额外 JSON 合并 / 落库回查
    load_extra_data,
    merge_extra_data,
    verify_upsert_landing,
    default_user_weekly_data,
    default_user_2p_playlog,
    calc_play_special,
    normalize_snapshot,
    wait_send_cooldown,
    # 字段表
    PLAYLOG_FIELDS,
    PLAYLOG_BOOL_FIELDS,
    PLAYLOG_STRING_FIELDS,
    JUDGE_TYPES,
    JUDGE_BOXES,
    USER_DATA_DROP_KEYS,
    USER_OPTION_DROP_KEYS,
    USER_CHARACTER_KEEP_KEYS,
    USER_MUSIC_DETAIL_DROP_KEYS,
    USER_CHARGE_DROP_KEYS,
    USER_MISSION_DROP_KEYS,
)

from .upsert_snapshot import (
    fetch_upsert_snapshot,
    save_snapshot,
    load_snapshot,
    summarize_snapshot,
    DEFAULT_SNAPSHOT_NODES,
)

from .upsert_user_chargelog import (
    UpsertUserChargelog,
    ChargelogConfirmError,
    ChargelogGuardError,
    UserChargeVO,
    UserChargelogVO,
    UserChargelogRequestVO,
    ticket_name,
    ticket_price,
    calc_valid_date,
    parse_wall_time,
    now_cst,
)

# ---------------------------------------------------------------------------
# 4) 取数公共底座
# ---------------------------------------------------------------------------

from .user_getter_common import (
    EmptyRequestVO as GetterEmptyRequestVO,
    UserIdRequestVO as GetterUserIdRequestVO,
    UserIdPageRequestVO,
    UserLoginBonusRequestVO,
    UserItemRequestVO,
    UserMusicRequestVO,
    UserCourseRequestVO,
    UserFavoriteRequestVO,
    UserFavoriteItemRequestVO,
    UserShopStockRequestVO,
    UserRivalRequestVO,
    UserRivalMusicRequestVO,
    fetch_all_pages,
    ITEM_KINDS,
    ITEM_NEXT_INDEX_FACTOR,
    FAVORITE_ITEM_KINDS,
    RIVAL_MUSIC_LEVELS,
)

# ---------------------------------------------------------------------------
# 5) 取数脚本（一个接口一个脚本）
# ---------------------------------------------------------------------------

from .userdata import UserData
from .user_extend import UserExtend
from .user_option import UserOption
from .user_character import UserCharacter
from .user_ghost import UserGhost
from .user_map import UserMap, UserMapAll
from .user_login_bonus import UserLoginBonus, UserLoginBonusAll
from .user_rating import UserRating
from .user_item import UserItem, UserItemAll
from .user_music import UserMusicDetail, UserMusicDetailAll
from .user_course import UserCourse, UserCourseAll
from .user_charge import UserCharge
from .user_favorite import UserFavorite, UserFavoriteAll
from .user_activity import UserActivity
from .user_mission import UserMissionData
from .user_intimate import UserIntimate
from .user_shop_stock import UserShopStock
from .user_favorite_item import (
    UserFavoriteItem,
    UserFavoriteItemAll,
    FAVORITE_ITEM_KIND_MUSIC,
    FAVORITE_ITEM_KIND_RIVAL,
)
from .user_rival import UserRivalData, UserRivalMusic, UserRivalMusicAll
from .user_friend_bonus import UserFriendBonus, extract_gift_points
from .user_kaleidx_scope import UserKaleidxScope, GameKaleidxScope
from .user_region import UserRegion
from .user_recommend_music import UserRecommendRateMusic, UserRecommendSelectMusic
from .user_new_item import UserNewItemList, UserNewItemListRequestVO

from .game_ranking import GetGameRanking, GameRankingRequestVO
from .game_event import GetGameEvent, GameEventRequestVO
from .game_charge import GetGameCharge, GameChargeRequestVO
from .game_weekly_data import GetGameWeeklyData
from .game_tournament_info import GetGameTournamentInfo
from .game_ng_music_id import GetGameNgMusicId

# ---------------------------------------------------------------------------
# 6) 需要日志跟踪的 api 函数（新增 api 时把函数名加到这里）
# ---------------------------------------------------------------------------

_API_FUNCS = (
    # --- 会话链路 ---
    "ParseQRCode",
    "GetGameSettings",
    "Ping",
    "UserPreview",
    "UserLogin",
    "UserLogout",
    # --- 上传成绩 ---
    "UpsertUserAll",
    "build_play_from_config",
    "derive_play_characters",
    "merge_extra_data",
    "verify_upsert_landing",
    "build_user_all",
    # --- 购买功能票 ---
    "UpsertUserChargelog",
    "ticket_name",
    "ticket_price",
    "calc_valid_date",
    "build_user_playlog",
    "build_user_game_playlog",
    "validate_user_playlog",
    "validate_before_send",
    "apply_play_effects",
    "build_post_play_user_data",
    "build_delta",
    "build_favorite_delta",
    "normalize_snapshot",
    "fetch_upsert_snapshot",
    "summarize_snapshot",
    "UserNewItemList",
    # --- 取数：单接口 ---
    "UserData",              # GetUserDataApi
    "UserExtend",            # GetUserExtendApi
    "UserOption",            # GetUserOptionApi
    "UserCharacter",         # GetUserCharacterApi
    "UserGhost",             # GetUserGhostApi
    "UserMap",               # GetUserMapApi（单页）
    "UserMapAll",            # GetUserMapApi（全量）
    "UserLoginBonus",        # GetUserLoginBonusApi（单页）
    "UserLoginBonusAll",     # GetUserLoginBonusApi（全量）
    "UserRating",            # GetUserRatingApi
    "UserItem",              # GetUserItemApi（单类）
    "UserItemAll",           # GetUserItemApi（全量）
    "UserMusicDetail",       # GetUserMusicApi（单页）
    "UserMusicDetailAll",    # GetUserMusicApi（全量）
    "UserCourse",            # GetUserCourseApi（单页）
    "UserCourseAll",         # GetUserCourseApi（全量）
    "UserCharge",            # GetUserChargeApi
    "UserFavorite",          # GetUserFavoriteApi（单类）
    "UserFavoriteAll",       # GetUserFavoriteApi（全量）
    "UserActivity",          # GetUserActivityApi
    "UserMissionData",       # GetUserMissionDataApi
    "UserIntimate",          # GetUserIntimateApi
    "UserShopStock",         # GetUserShopStockApi
    "UserFavoriteItem",      # GetUserFavoriteItemApi（单页）
    "UserFavoriteItemAll",   # GetUserFavoriteItemApi（全量）
    "UserRivalData",         # GetUserRivalDataApi
    "UserRivalMusic",        # GetUserRivalMusicApi（单页）
    "UserRivalMusicAll",     # GetUserRivalMusicApi（全量）
    "UserFriendBonus",       # GetUserFriendBonusApi
    "UserKaleidxScope",      # GetUserKaleidxScopeApi
    "GameKaleidxScope",      # GetGameKaleidxScopeApi
    "UserRegion",            # GetUserRegionApi
    "UserRecommendRateMusic",     # GetUserRecommendRateMusicApi
    "UserRecommendSelectMusic",   # GetUserRecommendSelectMusicApi
    "UserNewItemList",       # GetUserNewItemListApi
    # --- 取数：游戏侧 ---
    "GetGameRanking",        # GetGameRankingApi
    "GetGameEvent",          # GetGameEventApi
    "GetGameCharge",         # GetGameChargeApi
    "GetGameWeeklyData",     # GetGameWeeklyDataApi
    "GetGameTournamentInfo", # GetGameTournamentInfoApi
    "GetGameNgMusicId",      # GetGameNgMusicIdApi
)

# ---------------------------------------------------------------------------
# 7) 导入即包装：保证 from api import X 拿到的是带日志的版本
# ---------------------------------------------------------------------------

autowrap(globals(), _API_FUNCS)

# ---------------------------------------------------------------------------
# 8) 统一导出
# ---------------------------------------------------------------------------

__all__ = [
    # ---- 日志：会话 ----
    "setup_logging", "teardown_logging",
    # ---- 日志：自动跟踪 ----
    "autowrap", "get_called_apis",
    # ---- 日志：模式 ----
    "get_level", "set_level", "is_debug", "LEVEL_INFO", "LEVEL_DEBUG",
    # ---- 日志：装饰器 / 兼容 ----
    "api_log", "get_logger",
    # ---- 日志：流程 ----
    "log_info", "log_step", "log_result", "log_warning", "log_error",
    "log_section", "log_field",
    # ---- 日志：收发数据 ----
    "log_debug", "log_request", "log_response", "log_payload",
    # ---- 网络核心 ----
    "MaimaiNetClient", "MaimaiNetError", "get_default_client", "close_default_client",
    "request", "request_dict", "request_vo",
    "obfuscate_api_name", "build_api_url", "build_user_agent", "adler32",
    "aes_encrypt", "aes_decrypt", "deflate_compress", "deflate_decompress",
    "vo_to_json", "vo_from_json",
    "local_utc_offset_seconds", "login_date_time_now",
    "EmptyRequestVO", "UserIdRequestVO", "ReturnCodeVO",
    # ---- 会话链路 ----
    "ParseQRCode",
    "GetGameSettings", "GameSetting", "GameSettingRequestVO", "GameSettingResponseVO",
    "is_maintenance", "is_ping_disabled",
    "Ping",
    "UserPreview", "UserPreviewRequestVO", "UserPreviewResponseVO",
    "UserLogin", "UserLoginRequestVO", "UserLoginResponseVO",
    "UserLogout", "LogoutType", "DelayLog", "RequestAPI",
    "UserLogoutRequestVO", "UserLogoutRequest2VO", "UserLogoutResponseVO",
    "create_empty_delay_log", "create_delay_log_from_stats", "DELAY_LOG_SLOTS",
    # ---- 上传成绩 ----
    "UpsertUserAll", "PlayData", "build_play_from_config", "derive_play_characters",
    "load_extra_data", "merge_extra_data", "verify_upsert_landing",
    # ---- 购买功能票 ----
    "UpsertUserChargelog", "ChargelogConfirmError", "ChargelogGuardError",
    "UserChargeVO", "UserChargelogVO", "UserChargelogRequestVO",
    "ticket_name", "ticket_price", "calc_valid_date", "parse_wall_time", "now_cst",
    "UserAllRequestVO", "UpsertResponseVO",
    "UpsertUserAllError", "ConfirmRequiredError", "PatchError",
    "NODE_TYPES", "NODE_ORDER", "BITS_TO_ARRAY", "ARRAY_TO_BITS",
    "DIFF_PRIMARY_KEYS", "MAY_BE_EMPTY_NODES", "DEFAULT_EMPTY_NODES",
    "empty_node", "empty_user_all", "coerce_node_value", "sync_bits_to_arrays",
    "build_delta", "build_favorite_delta", "build_user_all",
    "build_user_playlog", "build_user_game_playlog", "build_post_play_user_data",
    "validate_user_playlog", "validate_before_send", "apply_play_effects",
    "default_user_weekly_data", "default_user_2p_playlog", "calc_play_special",
    "normalize_snapshot", "wait_send_cooldown",
    "PLAYLOG_FIELDS", "PLAYLOG_BOOL_FIELDS", "PLAYLOG_STRING_FIELDS",
    "JUDGE_TYPES", "JUDGE_BOXES",
    "USER_DATA_DROP_KEYS", "USER_OPTION_DROP_KEYS", "USER_CHARACTER_KEEP_KEYS",
    "USER_MUSIC_DETAIL_DROP_KEYS", "USER_CHARGE_DROP_KEYS", "USER_MISSION_DROP_KEYS",
    # ---- 快照编排 ----
    "fetch_upsert_snapshot", "save_snapshot", "load_snapshot",
    "summarize_snapshot", "DEFAULT_SNAPSHOT_NODES",
    # ---- 取数公共底座 ----
    "GetterEmptyRequestVO", "GetterUserIdRequestVO", "UserIdPageRequestVO",
    "UserLoginBonusRequestVO", "UserItemRequestVO", "UserMusicRequestVO",
    "UserCourseRequestVO", "UserFavoriteRequestVO", "UserFavoriteItemRequestVO",
    "UserShopStockRequestVO", "UserRivalRequestVO", "UserRivalMusicRequestVO",
    "fetch_all_pages",
    "ITEM_KINDS", "ITEM_NEXT_INDEX_FACTOR", "FAVORITE_ITEM_KINDS", "RIVAL_MUSIC_LEVELS",
    # ---- 取数脚本 ----
    "UserData", "UserExtend", "UserOption", "UserCharacter", "UserGhost",
    "UserMap", "UserMapAll",
    "UserLoginBonus", "UserLoginBonusAll",
    "UserRating",
    "UserItem", "UserItemAll",
    "UserMusicDetail", "UserMusicDetailAll",
    "UserCourse", "UserCourseAll",
    "UserCharge",
    "UserFavorite", "UserFavoriteAll",
    "UserActivity", "UserMissionData", "UserIntimate", "UserShopStock",
    "UserFavoriteItem", "UserFavoriteItemAll",
    "FAVORITE_ITEM_KIND_MUSIC", "FAVORITE_ITEM_KIND_RIVAL",
    "UserRivalData", "UserRivalMusic", "UserRivalMusicAll",
    "UserFriendBonus", "extract_gift_points",
    "UserKaleidxScope", "GameKaleidxScope",
    "UserRegion",
    "UserRecommendRateMusic", "UserRecommendSelectMusic",
    "UserNewItemList", "UserNewItemListRequestVO",
    "GetGameRanking", "GameRankingRequestVO",
    "GetGameEvent", "GameEventRequestVO",
    "GetGameCharge", "GameChargeRequestVO",
    "GetGameWeeklyData", "GetGameTournamentInfo", "GetGameNgMusicId",
]
