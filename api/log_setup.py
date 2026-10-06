# -*- coding: utf-8 -*-
"""
log_setup.py —— 统一日志模块（INFO / DEBUG 双模式）
================================================================================

【两种模式】

    INFO （默认）  只展示 api 脚本的运行情况和结果：
                      === ParseQRCode 开始运行 ===
                        [接口说明] ...
                        [调用参数] ...
                        [运行结果] ...
                      === ParseQRCode 运行结束 ===

    DEBUG          在 INFO 基础上，额外展示「向 api 发送的数据」和「api 返回的数据」：
                      -> 请求 GetUserPreviewApi
                           URL    : https://...
                           请求头 : {...}
                           请求体 : {...JSON 全文...}
                      <- 响应 GetUserPreviewApi
                           状态码 : 200
                           响应体 : {...JSON 全文...}

【模式从哪来】

    优先级：  setup_logging(level=...) 显式传参  >  config.py 的 LOG_LEVEL  >  INFO

    日常只改 config.py 一行：

        LOG_LEVEL = "info"      # 只看流程
        LOG_LEVEL = "debug"     # 连收发数据一起看

【日志文件（两种形式同时存在、同时写入）】

    logs/latest.log        覆盖模式（"w"）—— 只包含【当次】主脚本运行产出的日志，
                           下一次运行主脚本时被覆盖
    logs/YYYY-MM-DD.log    追加模式（"a"）—— 存放【当日】产生的所有日志

    每行都带 [YYYY-MM-DD HH:MM:SS] 时间戳。

【主脚本怎么用】

    from api import setup_logging, teardown_logging, ParseQRCode, UserLogin

    def main():
        setup_logging("我的主脚本")     # 开头一句；api 调用从此自动记录
        try:
            user_id, token = ParseQRCode(qr)     # 自动产出「开始运行 / 运行结束」
            login = UserLogin(user_id, token)
        finally:
            teardown_logging()                   # 结尾一句（不写也会在退出时自动收尾）

    api 函数不需要自己写 print，也不需要装饰器 —— api/__init__.py 在导入时就
    统一套上了日志外壳（见 autowrap）。

【api 脚本怎么用】

    from api import log_info, log_debug, log_request, log_response

    def GetUserPreview(user_id, token, ...):
        # 函数的第一行 docstring 会成为日志里的「[接口说明]」
        # 例如： '''获取用户预览信息'''
        log_info(f"请求用户预览 user_id={user_id}")   # 可选，想额外记话时才写

        log_request(url=url, body=req, headers=hdr, api_name="GetUserPreviewApi")
        raw = _http_post(...)
        log_response(status=200, body=raw, headers=hdr, api_name="GetUserPreviewApi")

        return parsed
"""

from __future__ import annotations

import atexit
import functools
import json
import os
import platform
import time
from datetime import datetime
from typing import Any, Callable, Iterable, Optional

# =============================================================================
# 常量与全局状态
# =============================================================================

LEVEL_INFO = "info"
LEVEL_DEBUG = "debug"

_LEVEL_RANK = {LEVEL_INFO: 20, LEVEL_DEBUG: 10}

# 项目根目录（本文件在 api/ 下，根目录是上一级）
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGS_DIR = os.path.join(_ROOT_DIR, "logs")

_SEPARATOR = "=" * 66
_INDENT = "  "

# 全局状态
_session_started = False
_session_script_name = ""
_current_level = LEVEL_INFO
_value_max = 0

_date_log_path: Optional[str] = None
_latest_log_path: Optional[str] = None
_date_log_file = None
_latest_log_file = None

# 被自动跟踪的 api 函数名（供横幅展示）
_tracked_api_names: list = []
# 本次会话实际调用过的 api（按首次调用顺序）
_called_apis: list = []


# =============================================================================
# 模式判定
# =============================================================================

def _normalize_level(level: Any) -> str:
    """把各种写法的模式名归一化成 'info' / 'debug'。"""
    if level is None:
        return LEVEL_INFO
    text = str(level).strip().lower()
    if text in ("debug", "dbg", "verbose", "详细", "调试"):
        return LEVEL_DEBUG
    return LEVEL_INFO


def _config_level() -> str:
    """从 config.py 读 LOG_LEVEL；读不到就用 INFO。"""
    try:
        import config  # type: ignore
        return _normalize_level(getattr(config, "LOG_LEVEL", LEVEL_INFO))
    except Exception:
        return LEVEL_INFO


def _config_value_max() -> int:
    """从 config.py 读 LOG_VALUE_MAX（0 = 不截断）。"""
    try:
        import config  # type: ignore
        return int(getattr(config, "LOG_VALUE_MAX", 0) or 0)
    except Exception:
        return 0


def get_level() -> str:
    """返回当前日志模式（'info' / 'debug'）。"""
    return _current_level


def is_debug() -> bool:
    """当前是否 DEBUG 模式。"""
    return _LEVEL_RANK.get(_current_level, 20) <= _LEVEL_RANK[LEVEL_DEBUG]


def set_level(level: Any) -> str:
    """运行时切换模式（一般不用，改 config.py 即可）。返回切换后的模式。"""
    global _current_level
    _current_level = _normalize_level(level)
    return _current_level


# =============================================================================
# 日志文件
# =============================================================================

def _ensure_logs_dir() -> None:
    os.makedirs(_LOGS_DIR, exist_ok=True)


def _get_date_log_path() -> str:
    return os.path.join(_LOGS_DIR, datetime.now().strftime("%Y-%m-%d") + ".log")


def _get_latest_log_path() -> str:
    return os.path.join(_LOGS_DIR, "latest.log")


def _write_files(message: str) -> None:
    """把一段文本写进两个日志文件（每行带时间戳）。"""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    lines = message.splitlines() or [""]
    payload = "".join(timestamp + line + "\n" for line in lines)
    for handle in (_date_log_file, _latest_log_file):
        if handle:
            try:
                handle.write(payload)
                handle.flush()
            except Exception:
                pass


def _emit(message: str = "", *, console: bool = True) -> None:
    """统一出口：控制台 + 两个日志文件。"""
    if console:
        try:
            print(message)
        except Exception:
            try:
                print(message.encode("utf-8", "replace").decode("utf-8", "replace"))
            except Exception:
                pass
    _write_files(message)


def _close_log_files() -> None:
    global _date_log_file, _latest_log_file
    for name in ("_date_log_file", "_latest_log_file"):
        handle = globals()[name]
        if handle:
            try:
                handle.close()
            except Exception:
                pass
            globals()[name] = None


# =============================================================================
# 自动跟踪：给 api 函数套日志外壳
# =============================================================================
#
# 目标：主脚本只写 setup_logging("名字") + 业务代码，
#       调用的每个 api 函数自动产出「===函数名 开始运行=== / ===函数名 运行结束===」，
#       调用方不必自己写装饰器，也不必自己埋点。
#
# 原理：api/__init__.py 在导入完各 api 脚本后调用 autowrap(globals(), _API_FUNCS)，
#       把命名空间里的函数替换成带日志的版本 —— 于是 from api import ParseQRCode
#       拿到的已经是包装后的函数。

def _describe(func: Callable) -> str:
    """取函数 docstring 首行，作为「[接口说明]」。"""
    doc = (func.__doc__ or "").strip()
    if not doc:
        return ""
    return doc.splitlines()[0].strip()


def _make_tracked(func: Callable) -> Callable:
    """生成带日志外壳的包装函数。"""
    name = func.__name__
    summary = _describe(func)

    @functools.wraps(func)
    def tracked(*args, **kwargs) -> Any:
        _note_api_call(name)

        _emit("")
        _emit("=== " + name + " 开始运行 ===")
        if summary:
            _emit(_INDENT + "[接口说明] " + summary)

        # 调用参数：DEBUG 展开多行 JSON，INFO 记单行摘要
        if args:
            if is_debug():
                _emit(_INDENT + "[位置参数]")
                _emit(_fmt_pretty(list(args)))
            else:
                _emit(_INDENT + "[位置参数] " + ", ".join(_fmt(a) for a in args))
        if kwargs:
            shown = {k: v for k, v in kwargs.items() if v is not None}
            if shown:
                if is_debug():
                    _emit(_INDENT + "[关键字参数]")
                    _emit(_fmt_pretty(shown))
                else:
                    _emit(_INDENT + "[关键字参数] "
                          + ", ".join(k + "=" + _fmt(v) for k, v in shown.items()))

        t0 = time.monotonic()
        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            ms = int((time.monotonic() - t0) * 1000)
            _emit(_INDENT + "[运行结果] 异常 " + type(exc).__name__ + ": "
                  + str(exc) + "（耗时 " + str(ms) + " ms）")
            _emit("=== " + name + " 运行结束 ===")
            _emit("")
            raise

        ms = int((time.monotonic() - t0) * 1000)
        _emit(_INDENT + "[运行结果] 成功 " + _fmt_result(result)
              + "（耗时 " + str(ms) + " ms）")
        if is_debug() and result is not None:
            _emit(_INDENT + "[返回数据]")
            _emit(_fmt_pretty(result))
        _emit("=== " + name + " 运行结束 ===")
        _emit("")
        return result

    tracked.__mai_logged__ = True          # type: ignore[attr-defined]
    tracked.__mai_original__ = func        # type: ignore[attr-defined]
    return tracked


def autowrap(namespace: dict, names: Iterable[str]) -> list:
    """
    给命名空间里的函数套上日志外壳（导入时调用，幂等）。

    参数：
        namespace: 目标命名空间，通常是 api/__init__.py 的 globals()
        names:     要包装的函数名序列

    返回：
        实际完成包装的函数名列表
    """
    wrapped = []
    for name in names:
        obj = namespace.get(name)
        if obj is None or not callable(obj):
            continue
        if getattr(obj, "__mai_logged__", False):
            wrapped.append(name)
            continue
        try:
            namespace[name] = _make_tracked(obj)
            wrapped.append(name)
        except Exception:
            continue

    for n in wrapped:
        if n not in _tracked_api_names:
            _tracked_api_names.append(n)
    return wrapped


def _note_api_call(name: str) -> None:
    """记录主脚本调用过的 api（去重，保留首次调用顺序）。"""
    if name not in _called_apis:
        _called_apis.append(name)


def get_called_apis() -> list:
    """返回本次会话实际调用过的 api 名称（按首次调用顺序）。"""
    return list(_called_apis)


# =============================================================================
# 会话：初始化 / 收尾
# =============================================================================

def setup_logging(script_name: str, level: Any = None) -> str:
    """
    初始化日志会话（主脚本开头调用一次）。

    做三件事：
      1. 确定日志模式（level 显式传参 > config.LOG_LEVEL > INFO）
      2. 打开两个日志文件：日期日志（追加）+ latest.log（覆盖）
      3. 打印会话横幅

    参数：
        script_name: 脚本名，显示在横幅上
        level:       日志模式；None（默认）= 读 config.py 的 LOG_LEVEL

    返回：
        实际生效的模式（'info' / 'debug'）
    """
    global _session_started, _session_script_name, _value_max
    global _date_log_path, _latest_log_path, _date_log_file, _latest_log_file

    set_level(level if level is not None else _config_level())
    _value_max = _config_value_max()

    if _session_started:
        return _current_level

    _ensure_logs_dir()
    _session_script_name = script_name
    _date_log_path = _get_date_log_path()
    _latest_log_path = _get_latest_log_path()

    _called_apis.clear()

    _date_log_file = open(_date_log_path, "a", encoding="utf-8")      # 追加：当日全部
    _latest_log_file = open(_latest_log_path, "w", encoding="utf-8")  # 覆盖：仅当次

    _print_banner(script_name)
    _session_started = True
    return _current_level


def _print_banner(script_name: str) -> None:
    mode_text = "DEBUG（含收发数据）" if is_debug() else "INFO（仅运行情况与结果）"
    lines = [
        _SEPARATOR,
        _INDENT + "日志会话开始  ——  " + script_name,
        _SEPARATOR,
        _INDENT * 2 + "主脚本      : " + script_name,
        _INDENT * 2 + "开始时间    : " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        _INDENT * 2 + "日志模式    : " + mode_text,
        _INDENT * 2 + "Python      : " + platform.python_version()
        + " (" + platform.python_implementation() + " " + platform.machine() + ")",
        _INDENT * 2 + "工作目录    : " + os.getcwd(),
        _INDENT * 2 + "已挂载 api  : " + str(len(_tracked_api_names))
        + " 个（自动跟踪，主脚本无需写日志代码）",
        _INDENT * 2 + "当次日志    : " + str(_latest_log_path),
        _INDENT * 2 + "日期日志    : " + str(_date_log_path),
        _SEPARATOR,
    ]
    _emit("\n".join(lines))


def teardown_logging() -> None:
    """结束日志会话（主脚本结尾调用；不调用也会在退出时自动收尾）。"""
    global _session_started
    if not _session_started:
        return

    lines = [_SEPARATOR, _INDENT + "本次运行调用的 api", _SEPARATOR]
    if _called_apis:
        for i, name in enumerate(_called_apis, 1):
            lines.append(_INDENT * 2 + str(i).rjust(2) + ". " + name)
    else:
        lines.append(_INDENT * 2 + "（未调用任何 api）")
    lines.append(_SEPARATOR)
    lines.append(_INDENT + "日志会话结束  ——  " + _session_script_name)
    lines.append(_SEPARATOR)

    _emit("\n".join(lines))
    _close_log_files()
    _session_started = False


# =============================================================================
# 值格式化
# =============================================================================

def _truncate(text: str) -> str:
    if _value_max and len(text) > _value_max:
        return text[:_value_max] + "...(共 " + str(len(text)) + " 字符)"
    return text


def _fmt(value: Any) -> str:
    """把一个值渲染成紧凑单行文本。"""
    if isinstance(value, str):
        return _truncate(value)
    if value is None or isinstance(value, (int, float, bool)):
        return repr(value)
    if isinstance(value, (dict, list, tuple)):
        try:
            return _truncate(json.dumps(value, ensure_ascii=False,
                                        separators=(",", ":"), default=str))
        except Exception:
            return _truncate(repr(value))
    if hasattr(value, "__dict__"):
        try:
            data = {k: v for k, v in vars(value).items() if not k.startswith("_")}
            return _truncate(json.dumps(data, ensure_ascii=False,
                                        separators=(",", ":"), default=str))
        except Exception:
            return _truncate(repr(value))
    return _truncate(repr(value))


def _to_plain(value: Any) -> Any:
    """把 dataclass / 普通对象递归转成可 JSON 化的结构。"""
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, dict):
        return {k: _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {k: _to_plain(getattr(value, k, None)) for k in value.__dataclass_fields__}
    if hasattr(value, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def _fmt_pretty(value: Any, indent: str = "      ") -> str:
    """把 dict / list / VO 渲染成多行缩进的 JSON。DEBUG 下完整输出，不折叠。"""
    data = _to_plain(value)
    if isinstance(data, str):
        stripped = data.strip()
        if stripped[:1] in ("{", "["):
            try:
                data = json.loads(stripped)
            except Exception:
                return "\n".join(indent + line for line in data.splitlines())
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception:
        text = repr(data)

    if _value_max and len(text) > _value_max:
        text = text[:_value_max] + "\n" + indent + "...(共 " + str(len(text)) + " 字符，已截断)"
    return "\n".join(indent + line for line in text.splitlines())


def _fmt_result(result: Any) -> str:
    """结果的紧凑摘要（INFO 用）。"""
    if isinstance(result, list):
        return "list(" + str(len(result)) + " 项)"
    if isinstance(result, tuple):
        return "tuple(" + str(len(result)) + " 项)"
    if isinstance(result, dict):
        return "dict(" + str(len(result)) + " 键)"
    if isinstance(result, str):
        return repr(result) if len(result) <= 60 else "str(" + str(len(result)) + " 字符)"
    if hasattr(result, "__dataclass_fields__"):
        return type(result).__name__ + "(" + str(len(result.__dataclass_fields__)) + " 字段)"
    return repr(result)


# =============================================================================
# 流程日志（INFO 可见）
# =============================================================================

def log_info(message: str) -> None:
    """普通信息 —— 相当于「会进日志文件的 print」。"""
    _emit(str(message))


def log_step(title: str, *, index: int = 0, total: int = 0) -> None:
    """记一个运行步骤：log_step("扫码登录", index=1, total=5) -> [步骤 1/5] 扫码登录"""
    if index and total:
        _emit("[步骤 " + str(index) + "/" + str(total) + "] " + title)
    elif index:
        _emit("[步骤 " + str(index) + "] " + title)
    else:
        _emit("[步骤] " + title)


def log_result(message: Any) -> None:
    """记一条运行结果。"""
    _emit("[结果] " + (message if isinstance(message, str) else _fmt(message)))


def log_warning(message: str) -> None:
    """警告（不影响流程，但需要留意）。"""
    _emit("[警告] " + str(message))


def log_error(message: str) -> None:
    """错误。"""
    _emit("[错误] " + str(message))


def log_section(title: str) -> None:
    """记一个分节（带分隔线），用于主脚本分段。"""
    _emit("\n" + "-" * 60 + "\n" + title + "\n" + "-" * 60)


def log_field(name: str, value: Any, *, debug_only: bool = False) -> None:
    """
    记一个「字段: 值」；DEBUG 下 dict / list / VO 自动多行展开。

        log_field("user_id", 12345)
        log_field("请求体", {"userId": 12345}, debug_only=True)   # 只在 DEBUG 出现
    """
    if debug_only and not is_debug():
        return
    if is_debug() and (isinstance(value, (dict, list)) or hasattr(value, "__dataclass_fields__")):
        _emit(name + ":")
        _emit(_fmt_pretty(value))
        return
    _emit(name + ": " + _fmt(value))


def log_debug(message: Any) -> None:
    """调试信息 —— 仅 DEBUG 模式输出。"""
    if not is_debug():
        return
    _emit("[调试] " + _fmt(message))


# =============================================================================
# 收发数据日志（DEBUG 专属）—— api 脚本用它记录「发送的数据 / 返回的数据」
# =============================================================================

def log_request(
    url: str = "",
    body: Any = None,
    headers: Any = None,
    *,
    api_name: str = "",
) -> None:
    """
    记录一次「向 api 发送的数据」（仅 DEBUG 模式输出）。

    参数：
        url:      完整请求地址
        body:     请求体（dict / VO / JSON 字符串），展开成 JSON 全文
        headers:  请求头（dict）
        api_name: 接口名
    """
    if not is_debug():
        return
    _emit("")
    _emit("-> 请求 " + api_name if api_name else "-> 请求")
    if url:
        _emit("      URL    : " + str(url))
    if headers:
        _emit("      请求头 : " + _fmt(headers))
    if body is not None:
        _emit("      请求体 :")
        _emit(_fmt_pretty(body))


def log_response(
    status: Any = None,
    body: Any = None,
    headers: Any = None,
    *,
    api_name: str = "",
    elapsed_ms: Optional[int] = None,
) -> None:
    """
    记录一次「api 返回的数据」（仅 DEBUG 模式输出）。

    参数：
        status:     HTTP 状态码
        body:       响应体（JSON 字符串 / dict / VO）
        headers:    响应头（dict）
        api_name:   接口名
        elapsed_ms: 耗时（毫秒）
    """
    if not is_debug():
        return
    _emit("")
    _emit("<- 响应 " + api_name if api_name else "<- 响应")
    if status is not None:
        _emit("      状态码 : " + str(status))
    if elapsed_ms is not None:
        _emit("      耗时   : " + str(elapsed_ms) + " ms")
    if headers:
        _emit("      响应头 : " + _fmt(headers))
    if body is not None:
        _emit("      响应体 :")
        _emit(_fmt_pretty(body))


def log_payload(label: str, data: Any) -> None:
    """记录任意报文 / 数据结构（仅 DEBUG 模式输出）。"""
    if not is_debug():
        return
    _emit("")
    _emit("      " + label + " :")
    _emit(_fmt_pretty(data))


# =============================================================================
# 兼容：装饰器与 logger 对象
# =============================================================================

def api_log(func: Callable) -> Callable:
    """
    api 函数装饰器 —— 与自动跟踪等价（重复包装会被跳过）。

    一般【不需要】手写：api/__init__.py 的 autowrap 已经统一套好外壳。
    这里保留是为了让 api 脚本单独运行（python -m api.xxx）时也能记录。
    """
    if getattr(func, "__mai_logged__", False):
        return func
    return _make_tracked(func)


class _Logger:
    """兼容旧写法的 logger 对象；新代码直接用模块级函数即可。"""

    def info(self, message: str) -> None:
        log_info(message)

    def warning(self, message: str) -> None:
        log_warning(message)

    def error(self, message: str) -> None:
        log_error(message)

    def debug(self, message: Any) -> None:
        log_debug(message)

    def step(self, title: str, **kwargs) -> None:
        log_step(title, **kwargs)

    def result(self, message: Any) -> None:
        log_result(message)


_logger_instance = _Logger()


def get_logger() -> _Logger:
    """获取全局 logger 实例（等价于直接用模块级函数）。"""
    return _logger_instance


# =============================================================================
# 退出时自动收尾
# =============================================================================

def _auto_teardown() -> None:
    try:
        if _session_started:
            teardown_logging()
        else:
            _close_log_files()
    except Exception:
        pass


atexit.register(_auto_teardown)
