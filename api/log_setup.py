# -*- coding: utf-8 -*-
"""
log_setup. py — systemOnelog(INFO / DEBUG Dual Mode)
================================================================================

[Two modes]

  INFO (default) Show only api scriptofandresult:
           === ParseQRCode Get started ===
            [interfacedescription]...
            [calluseParameter]...
            [result]...
           === ParseQRCode run completion ===

  DEBUG     at INFO Basis, Showcase"Towards api Data sent"and"api returnsofdata":
           -> request GetUserPreviewApi
              URL: https://...
              request header: {...}
              request body: {... JSON Full..}
           <- Response GetUserPreviewApi
: 200
              Response body: {... JSON Full..}

[modeWhere did you come from?]

  Priority: setup_logging(level=...) explicitPassing on > config. py of LOG_LEVEL > INFO

  onlychange config. py One Row:

    LOG_LEVEL = "info"   # Just look at the flow
    LOG_LEVEL = "debug"   # receivehairdataOne

[logfile(Two forms co-exist, Simultaneous writes)]

  logs/latest. log    overwritemode("w")— Contains only[Current time]Log of master script run output,
              Overwritten the next time the master script is run
  logs/YYYY-MM-DD. log  Plusmode("a")— Storage[Same day]All generated logs

  eachallBelt [YYYY-MM-DD HH: MM: SS] time

[How to use the main script]

  from api import setup_logging, teardown_logging, ParseQRCode, UserLogin

  def main():
    setup_logging("My Master Script")   # Beginning sentence; api calluseFromrecord
    try:
      user_id, token = ParseQRCode(qr)   # output"Get started / run completion"
      login = UserLogin(user_id, token)
    finally:
      teardown_logging()          # TailOne(It will end automatically when you exit without writing)

  api Functions don't need to be written by themselves print, or decorators. — api/__init__. py At the time of import
  systemOneUplog(autowrap).

[api scriptuse]

  from api import log_info, log_debug, log_request, log_response

  def GetUserPreview(user_id, token,...):
    # First line of the function docstring will be in the log."[interfacedescription]"
    # Example: '''getFetch Users'''
    log_info(f"requestuser user_id={user_id}")  # Optional, Write only when you want to memorize extra words

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
# Constants and Global State
# =============================================================================

LEVEL_INFO = "info"
LEVEL_DEBUG = "debug"

_LEVEL_RANK = {LEVEL_INFO: 20, LEVEL_DEBUG: 10}

# item(fileat api/ Down, isUpOne)
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGS_DIR = os.path.join(_ROOT_DIR, "logs")

_SEPARATOR = "=" * 66
_INDENT = " "

# Global State
_session_started = False
_session_script_name = ""
_current_level = LEVEL_INFO
_value_max = 0

_date_log_path: Optional[str] = None
_latest_log_path: Optional[str] = None
_date_log_file = None
_latest_log_file = None

# of api Function name(For banner display)
_tracked_api_names: list = []
# Sessionactualcalluseof api(pressfirstcalluseorder)
_called_apis: list = []


# =============================================================================
# modeDetermine
# =============================================================================

def _normalize_level(level: Any) -> str:
    """putEachofmodeFirst nameNormalization 'info' / 'debug'."""
    if level is None:
        return LEVEL_INFO
    text = str(level).strip().lower()
    if text in ("debug", "dbg", "verbose", "text", "debug"):
        return LEVEL_DEBUG
    return LEVEL_INFO


def _config_level() -> str:
    """From config. py read LOG_LEVEL; readNotouse INFO."""
    try:
        import config  # type: ignore
        return _normalize_level(getattr(config, "LOG_LEVEL", LEVEL_INFO))
    except Exception:
        return LEVEL_INFO


def _config_value_max() -> int:
    """From config. py read LOG_VALUE_MAX(0 = No truncation)."""
    try:
        import config  # type: ignore
        return int(getattr(config, "LOG_VALUE_MAX", 0) or 0)
    except Exception:
        return 0


def get_level() -> str:
    """returnsCurrentlogmode('info' / 'debug')."""
    return _current_level


def is_debug() -> bool:
    """Is it currently DEBUG mode."""
    return _LEVEL_RANK.get(_current_level, 20) <= _LEVEL_RANK[LEVEL_DEBUG]


def set_level(level: Any) -> str:
    """timeCutmode(Generally not, change config. py Just do it). returnsCutafterofmode."""
    global _current_level
    _current_level = _normalize_level(level)
    return _current_level


# =============================================================================
# logfile
# =============================================================================

def _ensure_logs_dir() -> None:
    os.makedirs(_LOGS_DIR, exist_ok=True)


def _get_date_log_path() -> str:
    return os.path.join(_LOGS_DIR, datetime.now().strftime("%Y-%m-%d") + ". log")


def _get_latest_log_path() -> str:
    return os.path.join(_LOGS_DIR, "latest. log")


def _write_files(message: str) -> None:
    """putOnetwo log files(eachBelttime)."""
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
    """systemOneoutStage + Two log files."""
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
# api Function sleeve log shell
# =============================================================================
#
# Main Script Write Only setup_logging("First name") + Business Code,
#    calluseofeachPiece api Function Automatic Output"===Function name Get started=== / ===Function name run completion===",
#    callusenoWrite Decorator, You don't have to bury it yourself..
#
# Principle: api/__init__. py After importing each api scriptAftercalluse autowrap(globals(), _API_FUNCS),
#    putfirst nameemptyinofFunctionBeltlogof — So from api import ParseQRCode
#    toofAlreadyisPackagingAfterofFunction.

def _describe(func: Callable) -> str:
    """Fetch Function docstring firstAs"[interfacedescription]"."""
    doc = (func.__doc__ or "").strip()
    if not doc:
        return ""
    return doc.splitlines()[0].strip()


def _make_tracked(func: Callable) -> Callable:
    """BeltlogofPackagingFunction."""
    name = func.__name__
    summary = _describe(func)

    @functools.wraps(func)
    def tracked(*args, **kwargs) -> Any:
        _note_api_call(name)

        _emit("")
        _emit("=== " + name + " Get started ===")
        if summary:
            _emit(_INDENT + "[interfacedescription] " + summary)

        # calluseParameter: DEBUG Expand multiple rows JSON, INFO must
        if args:
            if is_debug():
                _emit(_INDENT + "[Location Parameters]")
                _emit(_fmt_pretty(list(args)))
            else:
                _emit(_INDENT + "[Location Parameters] " + ", ".join(_fmt(a) for a in args))
        if kwargs:
            shown = {k: v for k, v in kwargs.items() if v is not None}
            if shown:
                if is_debug():
                    _emit(_INDENT + "[Keyword Parameters]")
                    _emit(_fmt_pretty(shown))
                else:
                    _emit(_INDENT + "[Keyword Parameters] "
                          + ", ".join(k + "=" + _fmt(v) for k, v in shown.items()))

        t0 = time.monotonic()
        try:
            result = func(*args, **kwargs)
        except BaseException as exc:
            ms = int((time.monotonic() - t0) * 1000)
            _emit(_INDENT + "[result] Exceptions " + type(exc).__name__ + ": "
                  + str(exc) + "(time " + str(ms) + " ms)")
            _emit("=== " + name + " run completion ===")
            _emit("")
            raise

        ms = int((time.monotonic() - t0) * 1000)
        _emit(_INDENT + "[result] Success " + _fmt_result(result)
              + "(time " + str(ms) + " ms)")
        if is_debug() and result is not None:
            _emit(_INDENT + "[returnsdata]")
            _emit(_fmt_pretty(result))
        _emit("=== " + name + " run completion ===")
        _emit("")
        return result

    tracked.__mai_logged__ = True          # type: ignore[attr-defined]
    tracked.__mai_original__ = func        # type: ignore[attr-defined]
    return tracked


def autowrap(namespace: dict, names: Iterable[str]) -> list:
    """
  first nameemptyinofFunctionUplog(Called on import, Idempotent).

  Parameter:
    namespace: first nameemptyis api/__init__. py of globals()
    names:   mustPackagingofFunction nameSequence

  Returns:
    List of function names that actually finished wrapping
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
    """recordMaster Scriptcalluseof api(Deduplication, Preserve first call order)."""
    if name not in _called_apis:
        _called_apis.append(name)


def get_called_apis() -> list:
    """returnsSessionactualcalluseof api Name(pressfirstcalluseorder)."""
    return list(_called_apis)


# =============================================================================
# Session: Initialization / receiveTail
# =============================================================================

def setup_logging(script_name: str, level: Any = None) -> str:
    """
  Initialize Log Session(Called once at the beginning of the main script).

  Do three things:
   1. logmode(level explicitPassing on > config. LOG_LEVEL > INFO)
   2. two log files: log(Plus)+ latest. log(overwrite)
   3. Session

  Parameter:
    script_name: scriptFirst name, atUp
    level:    logmode; None(default)= read config. py of LOG_LEVEL

  Returns:
    Patterns actually in effect('info' / 'debug')
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

    _date_log_file = open(_date_log_path, "a", encoding="utf-8")      # Plus: All of the day
    _latest_log_file = open(_latest_log_path, "w", encoding="utf-8")  # overwrite: Only if times

    _print_banner(script_name)
    _session_started = True
    return _current_level


def _print_banner(script_name: str) -> None:
    mode_text = "DEBUG(Includes transceiver data)" if is_debug() else "INFO(Runs and results only)"
    lines = [
        _SEPARATOR,
        _INDENT + "logSession — " + script_name,
        _SEPARATOR,
        _INDENT * 2 + "Master Script: " + script_name,
        _INDENT * 2 + "Start time: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        _INDENT * 2 + "logmode: " + mode_text,
        _INDENT * 2 + "Python: " + platform.python_version()
        + " (" + platform.python_implementation() + " " + platform.machine() + ")",
        _INDENT * 2 + "Working Directory: " + os.getcwd(),
        _INDENT * 2 + "Mounted api: " + str(len(_tracked_api_names))
        + " Piece(The main script does not need to write log code)",
        _INDENT * 2 + "Current Log: " + str(_latest_log_path),
        _INDENT * 2 + "log: " + str(_date_log_path),
        _SEPARATOR,
    ]
    _emit("\n".join(lines))


def teardown_logging() -> None:
    """logSession(Main script end call; Automatically ends when you exit without calling)."""
    global _session_started
    if not _session_started:
        return

    lines = [_SEPARATOR, _INDENT + "calluseof api", _SEPARATOR]
    if _called_apis:
        for i, name in enumerate(_called_apis, 1):
            lines.append(_INDENT * 2 + str(i).rjust(2) + ". " + name)
    else:
        lines.append(_INDENT * 2 + "(notcalluseAny api)")
    lines.append(_SEPARATOR)
    lines.append(_INDENT + "logSession — " + _session_script_name)
    lines.append(_SEPARATOR)

    _emit("\n".join(lines))
    _close_log_files()
    _session_started = False


# =============================================================================
# Value Formatting
# =============================================================================

def _truncate(text: str) -> str:
    if _value_max and len(text) > _value_max:
        return text[:_value_max] + "...(of " + str(len(text)) + " Character)"
    return text


def _fmt(value: Any) -> str:
    """putOneValue"""
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
    """put dataclass / Objectreturned JSON Structured."""
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


def _fmt_pretty(value: Any, indent: str = "   ") -> str:
    """put dict / list / VO of JSON. DEBUG Next Full Output, Unfolded."""
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
        text = text[:_value_max] + "\n" + indent + "...(of " + str(len(text)) + " Character, Truncated)"
    return "\n".join(indent + line for line in text.splitlines())


def _fmt_result(result: Any) -> str:
    """resultofmust(INFO use)."""
    if isinstance(result, list):
        return "list(" + str(len(result)) + " item)"
    if isinstance(result, tuple):
        return "tuple(" + str(len(result)) + " item)"
    if isinstance(result, dict):
        return "dict(" + str(len(result)) + " key)"
    if isinstance(result, str):
        return repr(result) if len(result) <= 60 else "str(" + str(len(result)) + " Character)"
    if hasattr(result, "__dataclass_fields__"):
        return type(result).__name__ + "(" + str(len(result.__dataclass_fields__)) + " Field)"
    return repr(result)


# =============================================================================
# log(INFO Visible)
# =============================================================================

def log_info(message: str) -> None:
    """— relatedWhenin"It will go into the log file. print"."""
    _emit(str(message))


def log_step(title: str, *, index: int = 0, total: int = 0) -> None:
    """onelog_step("QR login", index=1, total=5) -> [1/5] QR login"""
    if index and total:
        _emit("[" + str(index) + "/" + str(total) + "] " + title)
    elif index:
        _emit("[" + str(index) + "] " + title)
    else:
        _emit("[text] " + title)


def log_result(message: Any) -> None:
    """oneitemresult."""
    _emit("[result] " + (message if isinstance(message, str) else _fmt(message)))


def log_warning(message: str) -> None:
    """text(Does not affect process, But beware.)."""
    _emit("[text] " + str(message))


def log_error(message: str) -> None:
    """error."""
    _emit("[error] " + str(message))


def log_section(title: str) -> None:
    """oneMinutes(With Divider), used forMaster ScriptMinutes"""
    _emit("\n" + "-" * 60 + "\n" + title + "\n" + "-" * 60)


def log_field(name: str, value: Any, *, debug_only: bool = False) -> None:
    """
  one"Field: Value"; DEBUG Down dict / list / VO

    log_field("user_id", 12345)
    log_field("request body", {"userId": 12345}, debug_only=True)  # Only in DEBUG Appearance
  """
    if debug_only and not is_debug():
        return
    if is_debug() and (isinstance(value, (dict, list)) or hasattr(value, "__dataclass_fields__")):
        _emit(name + ":")
        _emit(_fmt_pretty(value))
        return
    _emit(name + ": " + _fmt(value))


def log_debug(message: Any) -> None:
    """debug — Only DEBUG modeout."""
    if not is_debug():
        return
    _emit("[debug] " + _fmt(message))


# =============================================================================
# receivehairdatalog(DEBUG Exclusive)— api scriptuserecord"Data sent / returnsofdata"
# =============================================================================

def log_request(
    url: str = "",
    body: Any = None,
    headers: Any = None,
    *,
    api_name: str = "",
) -> None:
    """
  recordOnce"Towards api Data sent"(Only DEBUG modeout).

  Parameter:
    url:   Full Request Address
    body:   request body(dict / VO / JSON String), Expand into JSON Full
    headers: request header(dict)
    api_name: interfaceFirst name
  """
    if not is_debug():
        return
    _emit("")
    _emit("-> request " + api_name if api_name else "-> request")
    if url:
        _emit("   URL: " + str(url))
    if headers:
        _emit("   request header: " + _fmt(headers))
    if body is not None:
        _emit("   request body:")
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
  recordOnce"api returnsofdata"(Only DEBUG modeout).

  Parameter:
    status:   HTTP
    body:    Response body(JSON String / dict / VO)
    headers:  Response header(dict)
    api_name:  interfaceFirst name
    elapsed_ms: time(seconds)
  """
    if not is_debug():
        return
    _emit("")
    _emit("<- Response " + api_name if api_name else "<- Response")
    if status is not None:
        _emit(": " + str(status))
    if elapsed_ms is not None:
        _emit("   time: " + str(elapsed_ms) + " ms")
    if headers:
        _emit("   Response header: " + _fmt(headers))
    if body is not None:
        _emit("   Response body:")
        _emit(_fmt_pretty(body))


def log_payload(label: str, data: Any) -> None:
    """recordpacket / data(Only DEBUG modeout)."""
    if not is_debug():
        return
    _emit("")
    _emit("   " + label + ":")
    _emit(_fmt_pretty(data))


# =============================================================================
# Compatible: And logger Object
# =============================================================================

def api_log(func: Callable) -> Callable:
    """
  api Function Decorator — Equivalent to auto-tracking(PackagingMeetingsskip).

  General[Not required]Handwriting: api/__init__. py of autowrap The shell has been uniformly set.
  thisinHoldisfor api scriptRun separately(python -m api. xxx)timeAlsocanrecord.
  """
    if getattr(func, "__mai_logged__", False):
        return func
    return _make_tracked(func)


class _Logger:
    """Compatible with legacy logger Object; codedirectlyuseFunctionJust do it."""

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
    """getTakeFullgame logger Example(etcindirectlyuseFunction)."""
    return _logger_instance


# =============================================================================
# outtimereceiveTail
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
