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
    chime.py                     扫码登录 -> userId + token
    get_game_settings.py         GetGameSettingApi（游戏设置）
    ping.py                      心跳探活
    get_user_preview.py          GetUserPreviewApi（用户预览）
    userlogin.py                 UserLoginApi（正式登录 -> loginId + loginDateTime）
    userlogout.py                UserLogoutApi（登出）

  上传 / 结算（有副作用的接口）
    upsert_user_all.py           ★ UpsertUserAllApi（上传成绩）
    upsert_user_chargelog.py     UpsertUserChargelogApi（购买功能票）
    get_need_user_data.py        ★ 结算快照编排（统一调用下面的取数脚本），
                                 并把结果落盘到 <工程根>/data/<userId>.json

  ★ 命名约定：服务端 API 名里带 Get 的，**脚本名与函数名一律带 get / Get**
    （不要模棱两可）。所以下面这些文件全是 get_ 开头。

  取数 —— GetUser*（一个接口一个脚本）
    get_user_data.py             GetUserDataApi
    get_user_extend.py           GetUserExtendApi
    get_user_option.py           GetUserOptionApi
    get_user_character.py        GetUserCharacterApi
    get_user_ghost.py            GetUserGhostApi
    get_user_map.py              GetUserMapApi
    get_user_login_bonus.py      GetUserLoginBonusApi
    get_user_rating.py           GetUserRatingApi
    get_user_item.py             GetUserItemApi
    get_user_music.py            GetUserMusicApi
    get_user_course.py           GetUserCourseApi
    get_user_charge.py           GetUserChargeApi
    get_user_favorite.py         GetUserFavoriteApi
    get_user_activity.py         GetUserActivityApi
    get_user_mission.py          GetUserMissionDataApi
    get_user_intimate.py         GetUserIntimateApi
    get_user_shop_stock.py       GetUserShopStockApi
    get_user_favorite_item.py    GetUserFavoriteItemApi
    get_user_rival.py            GetUserRivalDataApi / GetUserRivalMusicApi
    get_user_friend_bonus.py     GetUserFriendBonusApi
    get_user_kaleidx_scope.py    GetUserKaleidxScopeApi / GetGameKaleidxScopeApi
    get_user_region.py           GetUserRegionApi
    get_user_recommend_music.py  GetUserRecommendRateMusicApi / GetUserRecommendSelectMusicApi
    get_user_new_item.py         GetUserNewItemListApi

  取数 —— GetGame*
    get_game_settings.py         GetGameSettingApi
    get_game_charge.py           GetGameChargeApi
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
    # 协议常量（原在 config.py，已下沉到 maimai_net.py）
    BASE_URL,
    AES_KEY,
    AES_IV,
    OBFUSCATE_PARAM,
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

from .chime import (
    ParseQRCode,
    # aimedb / QR 常量（原在 config.py，已下沉到 chime.py）
    AIMEDB_HOST,
    AIMEDB_PORT,
    AIMEDB_PATH,
    QR_SIGN_KEY,
    QR_OPEN_GAME_ID,
    QR_TITLE_KEY,
    QR_USER_AGENT,
)

from .get_game_settings import (
    GetGameSettings,
    GameSetting,
    GameSettingRequestVO,
    GameSettingResponseVO,
    is_maintenance,
    is_ping_disabled,
)

from .ping import Ping

from .get_user_preview import (
    GetUserPreview,
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
    derive_play_rating,
    derive_play_grade,
    find_music_detail,
    PLAY_SPECIAL_NUM,
    PLAY_LOCAL_PLAY_COUNT,
    PLAY_AFTER_GRADE_RANK,
    DERIVE_GRADE_FROM_MUSIC_DETAIL,
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

from .get_need_user_data import (
    GetNeedUserData,
    save_snapshot,
    load_snapshot,
    summarize_snapshot,
    DEFAULT_SNAPSHOT_NODES,
    # ★ 用户数据落盘（<工程根>/data/<userId>.json）
    PROJECT_ROOT,
    DATA_DIR,
    user_data_path,
    save_user_data,
    load_user_data,
    list_saved_user_ids,
)

from .upsert_user_chargelog import (
    # 票券主数据（原在 config.py，已下沉到 upsert_user_chargelog.py）
    TICKET_CREDIT_NUM,
    TICKET_NAMES,
    PAID_TICKET_IDS,
    TICKET_VALID_HOUR_OFFSET,
    TICKET_VALID_DAYS,
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
    get_all_pages,
    ITEM_KINDS,
    ITEM_NEXT_INDEX_FACTOR,
    FAVORITE_ITEM_KINDS,
    RIVAL_MUSIC_LEVELS,
)

# ---------------------------------------------------------------------------
# 5) 取数脚本（一个接口一个脚本）
# ---------------------------------------------------------------------------

from .get_user_data import GetUserData
from .get_user_extend import GetUserExtend
from .get_user_option import GetUserOption
from .get_user_character import GetUserCharacter
from .get_user_ghost import GetUserGhost
from .get_user_map import GetUserMap, GetUserMapAll
from .get_user_login_bonus import GetUserLoginBonus, GetUserLoginBonusAll
from .get_user_rating import GetUserRating
from .get_user_item import GetUserItem, GetUserItemAll
from .get_user_music import GetUserMusicDetail, GetUserMusicDetailAll
from .get_user_course import GetUserCourse, GetUserCourseAll
from .get_user_charge import GetUserCharge
from .get_user_favorite import GetUserFavorite, GetUserFavoriteAll
from .get_user_activity import GetUserActivity
from .get_user_mission import GetUserMissionData
from .get_user_intimate import GetUserIntimate
from .get_user_shop_stock import GetUserShopStock
from .get_user_favorite_item import (
    GetUserFavoriteItem,
    GetUserFavoriteItemAll,
    FAVORITE_ITEM_KIND_MUSIC,
    FAVORITE_ITEM_KIND_RIVAL,
)
from .get_user_rival import GetUserRivalData, GetUserRivalMusic, GetUserRivalMusicAll
from .get_user_friend_bonus import GetUserFriendBonus, extract_gift_points
from .get_user_kaleidx_scope import GetUserKaleidxScope, GetGameKaleidxScope
from .get_user_region import GetUserRegion
from .get_user_recommend_music import GetUserRecommendRateMusic, GetUserRecommendSelectMusic
from .get_user_new_item import GetUserNewItemList, UserNewItemListRequestVO

from .get_game_charge import GetGameCharge, GameChargeRequestVO

# ---------------------------------------------------------------------------
# 6) 需要日志跟踪的 api 函数（新增 api 时把函数名加到这里）
# ---------------------------------------------------------------------------

_API_FUNCS = (
    # --- 会话链路 ---
    "ParseQRCode",
    "GetGameSettings",
    "Ping",
    "GetUserPreview",
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
    "GetNeedUserData",
    "summarize_snapshot",
    "GetUserNewItemList",
    # --- 取数：单接口 ---
    "GetUserData",              # GetUserDataApi
    "GetUserExtend",            # GetUserExtendApi
    "GetUserOption",            # GetUserOptionApi
    "GetUserCharacter",         # GetUserCharacterApi
    "GetUserGhost",             # GetUserGhostApi
    "GetUserMap",               # GetUserMapApi（单页）
    "GetUserMapAll",            # GetUserMapApi（全量）
    "GetUserLoginBonus",        # GetUserLoginBonusApi（单页）
    "GetUserLoginBonusAll",     # GetUserLoginBonusApi（全量）
    "GetUserRating",            # GetUserRatingApi
    "GetUserItem",              # GetUserItemApi（单类）
    "GetUserItemAll",           # GetUserItemApi（全量）
    "GetUserMusicDetail",       # GetUserMusicApi（单页）
    "GetUserMusicDetailAll",    # GetUserMusicApi（全量）
    "GetUserCourse",            # GetUserCourseApi（单页）
    "GetUserCourseAll",         # GetUserCourseApi（全量）
    "GetUserCharge",            # GetUserChargeApi
    "GetUserFavorite",          # GetUserFavoriteApi（单类）
    "GetUserFavoriteAll",       # GetUserFavoriteApi（全量）
    "GetUserActivity",          # GetUserActivityApi
    "GetUserMissionData",       # GetUserMissionDataApi
    "GetUserIntimate",          # GetUserIntimateApi
    "GetUserShopStock",         # GetUserShopStockApi
    "GetUserFavoriteItem",      # GetUserFavoriteItemApi（单页）
    "GetUserFavoriteItemAll",   # GetUserFavoriteItemApi（全量）
    "GetUserRivalData",         # GetUserRivalDataApi
    "GetUserRivalMusic",        # GetUserRivalMusicApi（单页）
    "GetUserRivalMusicAll",     # GetUserRivalMusicApi（全量）
    "GetUserFriendBonus",       # GetUserFriendBonusApi
    "GetUserKaleidxScope",      # GetUserKaleidxScopeApi
    "GetGameKaleidxScope",      # GetGameKaleidxScopeApi
    "GetUserRegion",            # GetUserRegionApi
    "GetUserRecommendRateMusic",     # GetUserRecommendRateMusicApi
    "GetUserRecommendSelectMusic",   # GetUserRecommendSelectMusicApi
    "GetUserNewItemList",       # GetUserNewItemListApi
    # --- 取数：游戏侧 ---
    "GetGameCharge",         # GetGameChargeApi
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
    "GetUserPreview", "UserPreviewRequestVO", "UserPreviewResponseVO",
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
    "GetNeedUserData", "save_snapshot", "load_snapshot",
    "summarize_snapshot", "DEFAULT_SNAPSHOT_NODES",
    "PROJECT_ROOT", "DATA_DIR", "user_data_path",
    "save_user_data", "load_user_data", "list_saved_user_ids",
    # ---- 取数公共底座 ----
    "GetterEmptyRequestVO", "GetterUserIdRequestVO", "UserIdPageRequestVO",
    "UserLoginBonusRequestVO", "UserItemRequestVO", "UserMusicRequestVO",
    "UserCourseRequestVO", "UserFavoriteRequestVO", "UserFavoriteItemRequestVO",
    "UserShopStockRequestVO", "UserRivalRequestVO", "UserRivalMusicRequestVO",
    "get_all_pages",
    "ITEM_KINDS", "ITEM_NEXT_INDEX_FACTOR", "FAVORITE_ITEM_KINDS", "RIVAL_MUSIC_LEVELS",
    # ---- 取数脚本 ----
    "GetUserData", "GetUserExtend", "GetUserOption", "GetUserCharacter", "GetUserGhost",
    "GetUserMap", "GetUserMapAll",
    "GetUserLoginBonus", "GetUserLoginBonusAll",
    "GetUserRating",
    "GetUserItem", "GetUserItemAll",
    "GetUserMusicDetail", "GetUserMusicDetailAll",
    "GetUserCourse", "GetUserCourseAll",
    "GetUserCharge",
    "GetUserFavorite", "GetUserFavoriteAll",
    "GetUserActivity", "GetUserMissionData", "GetUserIntimate", "GetUserShopStock",
    "GetUserFavoriteItem", "GetUserFavoriteItemAll",
    "FAVORITE_ITEM_KIND_MUSIC", "FAVORITE_ITEM_KIND_RIVAL",
    "GetUserRivalData", "GetUserRivalMusic", "GetUserRivalMusicAll",
    "GetUserFriendBonus", "extract_gift_points",
    "GetUserKaleidxScope", "GetGameKaleidxScope",
    "GetUserRegion",
    "GetUserRecommendRateMusic", "GetUserRecommendSelectMusic",
    "GetUserNewItemList", "UserNewItemListRequestVO",
    "GetGameCharge", "GameChargeRequestVO",
    # --- 协议常量（原在 config.py，已下沉到各 api 模块）---
    "BASE_URL", "AES_KEY", "AES_IV", "OBFUSCATE_PARAM",
    "AIMEDB_HOST", "AIMEDB_PORT", "AIMEDB_PATH",
    "QR_SIGN_KEY", "QR_OPEN_GAME_ID", "QR_TITLE_KEY", "QR_USER_AGENT",
    "TICKET_CREDIT_NUM", "TICKET_NAMES", "PAID_TICKET_IDS",
    "TICKET_VALID_HOUR_OFFSET", "TICKET_VALID_DAYS",
]
