# -*- coding: utf-8 -*-
"""
api Package — systemOneExport
================================================================================

The master script only needs from api import... you get all the features..

- fileAt the time of importBelow _API_FUNCS inListofeachPieceFunctionUp"log",
 So the main script has already got a logged version. — callusetimeMeetingsoutput:

   === ParseQRCode Get started ===
    [interfacedescription] parseQR Codefetch userId And token.
    [Location Parameters] 'SGWCMAID2610022219463A297AF4CA...'
    [result] Success tuple(2 item)(time 412 ms)
   === ParseQRCode run completion ===

 Master Script**Not required**Write Decorator, You don't have to bury it yourself..

--------------------------------------------------------------------------------
text(One api A script)
--------------------------------------------------------------------------------
 Infrastructure
  log_setup. py       systemOnelog(INFO / DEBUG Dual Mode)
  maimai_net. py      network(AES / deflate / URL obfuscation / Cookie)
  user_getter_common. py  Taking the number of feet from the common base(request VO / _get / )

 Session Link
  chime. py           QR login -> userId + token
  get_game_settings. py     GetGameSettingApi()
  ping. py           Heartbeat Probe Alive
  get_user_preview. py     GetUserPreviewApi(user)
  userlogin. py         UserLoginApi(currentlogin -> loginId + loginDateTime)
  userlogout. py        UserLogoutApi(logout)

 Upload / settlement(hasSide effectsofinterface)
  upsert_user_all. py      - UpsertUserAllApi(Upload Grades)
  upsert_user_chargelog. py   UpsertUserChargelogApi(purchase tickets Tickets)
  get_need_user_data. py    - settlement snapshot orchestration(systemOnecalluseBelowofFetch Script),
                 and trail the results to <Engineering Root>/data/<userId>. json

 - Naming conventions: server API Nameside Belt Get of,**scriptFirst nameAndFunction nameAlwaysBelt get / Get**
  (Don't be ambiguous). So the following documents are all get_ Beginning.

 Take number — GetUser*(one interface, one script)
  get_user_data. py       GetUserDataApi
  get_user_extend. py      GetUserExtendApi
  get_user_option. py      GetUserOptionApi
  get_user_character. py    GetUserCharacterApi
  get_user_ghost. py      GetUserGhostApi
  get_user_map. py       GetUserMapApi
  get_user_login_bonus. py   GetUserLoginBonusApi
  get_user_rating. py      GetUserRatingApi
  get_user_item. py       GetUserItemApi
  get_user_music. py      GetUserMusicApi
  get_user_course. py      GetUserCourseApi
  get_user_charge. py      GetUserChargeApi
  get_user_favorite. py     GetUserFavoriteApi
  get_user_activity. py     GetUserActivityApi
  get_user_mission. py     GetUserMissionDataApi
  get_user_intimate. py     GetUserIntimateApi
  get_user_shop_stock. py    GetUserShopStockApi
  get_user_favorite_item. py  GetUserFavoriteItemApi
  get_user_rival. py      GetUserRivalDataApi / GetUserRivalMusicApi
  get_user_friend_bonus. py   GetUserFriendBonusApi
  get_user_kaleidx_scope. py  GetUserKaleidxScopeApi / GetGameKaleidxScopeApi
  get_user_region. py      GetUserRegionApi
  get_user_recommend_music. py GetUserRecommendRateMusicApi / GetUserRecommendSelectMusicApi
  get_user_new_item. py     GetUserNewItemListApi

 Take number — GetGame*
  get_game_settings. py     GetGameSettingApi
  get_game_charge. py      GetGameChargeApi
"""

from .log_setup import (
    # Session
    setup_logging,
    teardown_logging,
    #
    autowrap,
    get_called_apis,
    # mode
    get_level,
    set_level,
    is_debug,
    LEVEL_INFO,
    LEVEL_DEBUG,
    # / Compatible
    api_log,
    get_logger,
    # log(INFO Visible)
    log_info,
    log_step,
    log_result,
    log_warning,
    log_error,
    log_section,
    log_field,
    log_debug,
    # receivehairdatalog(DEBUG Exclusive)
    log_request,
    log_response,
    log_payload,
)

# ---------------------------------------------------------------------------
# 1) network
# ---------------------------------------------------------------------------

from .maimai_net import (
    # Protocol Constants(Originally at config. py, moved to maimai_net. py)
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
# 2) Session Link
# ---------------------------------------------------------------------------

from .chime import (
    ParseQRCode,
    # aimedb / QR Constant(Originally at config. py, moved to chime. py)
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
# 3) Upload Grades
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
    # nodes
    NODE_TYPES,
    NODE_ORDER,
    BITS_TO_ARRAY,
    ARRAY_TO_BITS,
    DIFF_PRIMARY_KEYS,
    MAY_BE_EMPTY_NODES,
    DEFAULT_EMPTY_NODES,
    # batch packets
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
    # - JSON Merge / post-upload validation
    load_extra_data,
    merge_extra_data,
    verify_upsert_landing,
    default_user_weekly_data,
    default_user_2p_playlog,
    calc_play_special,
    normalize_snapshot,
    wait_send_cooldown,
    # Field table
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
    # - userdatafall(<Engineering Root>/data/<userId>. json)
    PROJECT_ROOT,
    DATA_DIR,
    user_data_path,
    save_user_data,
    load_user_data,
    list_saved_user_ids,
)

from .upsert_user_chargelog import (
    # Master Data(Originally at config. py, moved to upsert_user_chargelog. py)
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
# 4) Take the number of common bases
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
# 5) Fetch Script(one interface, one script)
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
# 6) needlogof api Function(added api timeputFunction namePlustothisin)
# ---------------------------------------------------------------------------

_API_FUNCS = (
    # --- Session Link ---
    "ParseQRCode",
    "GetGameSettings",
    "Ping",
    "GetUserPreview",
    "UserLogin",
    "UserLogout",
    # --- Upload Grades ---
    "UpsertUserAll",
    "build_play_from_config",
    "derive_play_characters",
    "merge_extra_data",
    "verify_upsert_landing",
    "build_user_all",
    # --- purchase tickets Tickets ---
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
    # --- Take number: Single Interface ---
    "GetUserData",              # GetUserDataApi
    "GetUserExtend",            # GetUserExtendApi
    "GetUserOption",            # GetUserOptionApi
    "GetUserCharacter",         # GetUserCharacterApi
    "GetUserGhost",             # GetUserGhostApi
    "GetUserMap",               # GetUserMapApi(Single Page)
    "GetUserMapAll",            # GetUserMapApi(Full Amount)
    "GetUserLoginBonus",        # GetUserLoginBonusApi(Single Page)
    "GetUserLoginBonusAll",     # GetUserLoginBonusApi(Full Amount)
    "GetUserRating",            # GetUserRatingApi
    "GetUserItem",              # GetUserItemApi(Single Class)
    "GetUserItemAll",           # GetUserItemApi(Full Amount)
    "GetUserMusicDetail",       # GetUserMusicApi(Single Page)
    "GetUserMusicDetailAll",    # GetUserMusicApi(Full Amount)
    "GetUserCourse",            # GetUserCourseApi(Single Page)
    "GetUserCourseAll",         # GetUserCourseApi(Full Amount)
    "GetUserCharge",            # GetUserChargeApi
    "GetUserFavorite",          # GetUserFavoriteApi(Single Class)
    "GetUserFavoriteAll",       # GetUserFavoriteApi(Full Amount)
    "GetUserActivity",          # GetUserActivityApi
    "GetUserMissionData",       # GetUserMissionDataApi
    "GetUserIntimate",          # GetUserIntimateApi
    "GetUserShopStock",         # GetUserShopStockApi
    "GetUserFavoriteItem",      # GetUserFavoriteItemApi(Single Page)
    "GetUserFavoriteItemAll",   # GetUserFavoriteItemApi(Full Amount)
    "GetUserRivalData",         # GetUserRivalDataApi
    "GetUserRivalMusic",        # GetUserRivalMusicApi(Single Page)
    "GetUserRivalMusicAll",     # GetUserRivalMusicApi(Full Amount)
    "GetUserFriendBonus",       # GetUserFriendBonusApi
    "GetUserKaleidxScope",      # GetUserKaleidxScopeApi
    "GetGameKaleidxScope",      # GetGameKaleidxScopeApi
    "GetUserRegion",            # GetUserRegionApi
    "GetUserRecommendRateMusic",     # GetUserRecommendRateMusicApi
    "GetUserRecommendSelectMusic",   # GetUserRecommendSelectMusicApi
    "GetUserNewItemList",       # GetUserNewItemListApi
    # --- Take number: Side ---
    "GetGameCharge",         # GetGameChargeApi
)

# ---------------------------------------------------------------------------
# 7) Import and Wrap: Warranty from api import X toofisBeltlogof
# ---------------------------------------------------------------------------

autowrap(globals(), _API_FUNCS)

# ---------------------------------------------------------------------------
# 8) systemOneExport
# ---------------------------------------------------------------------------

__all__ = [
    # ---- log: Session ----
    "setup_logging", "teardown_logging",
    # ---- log:----
    "autowrap", "get_called_apis",
    # ---- log: mode ----
    "get_level", "set_level", "is_debug", "LEVEL_INFO", "LEVEL_DEBUG",
    # ---- log:/ Compatible ----
    "api_log", "get_logger",
    # ---- log:----
    "log_info", "log_step", "log_result", "log_warning", "log_error",
    "log_section", "log_field",
    # ---- log: receivehairdata ----
    "log_debug", "log_request", "log_response", "log_payload",
    # ---- network ----
    "MaimaiNetClient", "MaimaiNetError", "get_default_client", "close_default_client",
    "request", "request_dict", "request_vo",
    "obfuscate_api_name", "build_api_url", "build_user_agent", "adler32",
    "aes_encrypt", "aes_decrypt", "deflate_compress", "deflate_decompress",
    "vo_to_json", "vo_from_json",
    "local_utc_offset_seconds", "login_date_time_now",
    "EmptyRequestVO", "UserIdRequestVO", "ReturnCodeVO",
    # ---- Session Link ----
    "ParseQRCode",
    "GetGameSettings", "GameSetting", "GameSettingRequestVO", "GameSettingResponseVO",
    "is_maintenance", "is_ping_disabled",
    "Ping",
    "GetUserPreview", "UserPreviewRequestVO", "UserPreviewResponseVO",
    "UserLogin", "UserLoginRequestVO", "UserLoginResponseVO",
    "UserLogout", "LogoutType", "DelayLog", "RequestAPI",
    "UserLogoutRequestVO", "UserLogoutRequest2VO", "UserLogoutResponseVO",
    "create_empty_delay_log", "create_delay_log_from_stats", "DELAY_LOG_SLOTS",
    # ---- Upload Grades ----
    "UpsertUserAll", "PlayData", "build_play_from_config", "derive_play_characters",
    "load_extra_data", "merge_extra_data", "verify_upsert_landing",
    # ---- purchase tickets Tickets ----
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
    # ---- Snapshot orchestration ----
    "GetNeedUserData", "save_snapshot", "load_snapshot",
    "summarize_snapshot", "DEFAULT_SNAPSHOT_NODES",
    "PROJECT_ROOT", "DATA_DIR", "user_data_path",
    "save_user_data", "load_user_data", "list_saved_user_ids",
    # ---- Take the number of common bases ----
    "GetterEmptyRequestVO", "GetterUserIdRequestVO", "UserIdPageRequestVO",
    "UserLoginBonusRequestVO", "UserItemRequestVO", "UserMusicRequestVO",
    "UserCourseRequestVO", "UserFavoriteRequestVO", "UserFavoriteItemRequestVO",
    "UserShopStockRequestVO", "UserRivalRequestVO", "UserRivalMusicRequestVO",
    "get_all_pages",
    "ITEM_KINDS", "ITEM_NEXT_INDEX_FACTOR", "FAVORITE_ITEM_KINDS", "RIVAL_MUSIC_LEVELS",
    # ---- Fetch Script ----
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
    # --- Protocol Constants(Originally at config. py, moved to each api )---
    "BASE_URL", "AES_KEY", "AES_IV", "OBFUSCATE_PARAM",
    "AIMEDB_HOST", "AIMEDB_PORT", "AIMEDB_PATH",
    "QR_SIGN_KEY", "QR_OPEN_GAME_ID", "QR_TITLE_KEY", "QR_USER_AGENT",
    "TICKET_CREDIT_NUM", "TICKET_NAMES", "PAID_TICKET_IDS",
    "TICKET_VALID_HOUR_OFFSET", "TICKET_VALID_DAYS",
]
