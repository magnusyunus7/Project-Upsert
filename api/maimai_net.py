# -*- coding: utf-8 -*-
"""
maimai_net.py —— 舞萌DX 网络核心层（纯 HTTP 复刻）
================================================================================

本模块是【唯一】直接和游戏服务器说话的地方，其余 api 脚本都通过它收发报文。

--------------------------------------------------------------------------------
一、协议依据（全部来自 source/ 反编译源码）
--------------------------------------------------------------------------------

1) 服务器基址与 API 路径
     source/Assembly-CSharp/Manager/OperationManager.cs:225,338
         ServerUri = Auth.GameServerUri + MovieServerUri("mE2s3Jhd/")
     source/Assembly-CSharp/Net.Packet/Packet.cs:116
         Client = NetHttpClient.Create(BaseUrl + Obfuscator(query.Api))
     source/Assembly-CSharp/Net.Packet/Packet.cs:485
         Obfuscator(s) = md5_hex_lower(s + "8bF76dE9")
     source/Assembly-CSharp/Net.VO/NetQuery.cs:14
         Api = api + "MaimaiChn"

     => 最终 URL = BASE_URL + md5(逻辑接口名 + "MaimaiChn" + "8bF76dE9")

     已用真实日志验证：md5("GetGameSettingApiMaimaiChn" + "8bF76dE9")
                       = 83a5d5a20b062c5c2ad817460b8f7f76
                       （source/2026-10-05.log:1 的请求就是打到这个尾段）

2) 请求体封装（三段：JSON -> deflate -> AES）
     source/Assembly-CSharp/Net/NetHttpClient.cs:262-300 RequestCallback
         a. DeflateStream(CompressionMode.Compress) 压缩 JSON 字节
         b. 手工拼 zlib 头 0x78 0x9C + 压缩数据 + Adler32(4 字节大端)
         c. CipherAES.Encrypt(...) 整体 AES 加密
     source/Assembly-CSharp/Net/CipherAES.cs:11-30
         AES-256-CBC / PKCS7 / Key 32B / IV 16B

3) 响应体解封装（逆过程）
     source/Assembly-CSharp/Net/NetHttpClient.cs:355-380 Decrypt + Decompress
         a. AES 解密
         b. 去掉前 2 字节 zlib 头与后 4 字节 Adler32
         c. Deflate 解压 -> UTF-8 JSON

4) 请求头
     source/Assembly-CSharp/Net/NetHttpClient.cs:174-190 Request()
         Content-Type   : application/json
         charset        : UTF-8
         Mai-Encoding   : 1.55      (DefaultHttpHeaderEncryption)
         Content-Encoding: deflate  (有请求体时)
         User-Agent     : <混淆后的API名>#<userId 或 clientId>
                          （source/Assembly-CSharp/Net/NetPacketUtil.cs:12-19）
         number         : <ping 毫秒>（非 Ping 接口；Packet.cs:189）

     ★ number 的语义：GameManager.PingMsec，只由 Ping 心跳包刷新
       （PingChecker.cs:227 <- PacketPing.cs:34 的 sw.ElapsedMilliseconds）。
       真机整局 53 个业务请求的 number 恒为同一个值（实测 63）。
       所以调用方**应当先跑一次 Ping()**，之后的请求才会带上真实 number；
       没跑过时 number = 0，与真机开机后第一屏的行为一致。

     ★ Cookie：★ UserLoginApi 的响应会下发
           Set-Cookie: JSESSIONID=FC9D0F122F7F24A522CD623BA3B76B74; Path=/Maimai2Servlet; HttpOnly
       （Packet.cs:228-234 只在 UserLogin 响应上把它收进 CookieContainer，
        之后 Packet.cs:190-193 每个带 userId 的请求都挂回去）。
       Ping 等接口的响应头里没有 Set-Cookie，所以必须跑过登录才会拿到。
       这是**真实的会话粘滞**，必须带着。
       requests.Session 会自动收下并自动带上，无需额外代码 ——
       但前提是**全程复用同一个 MaimaiNetClient**（用 get_default_client()）。

--------------------------------------------------------------------------------
二、★ 请求头集合：必须与真机一致（2026-10-06 真机抓包实证）
--------------------------------------------------------------------------------
     真机（Unity Mono 的 HttpWebRequest）实际发出的头**只有这几个**：

         number / Content-Type / User-Agent / charset / Mai-Encoding /
         Content-Encoding / (+ 登录后的 Cookie)

     **没有 Accept，也没有 Connection。**

     requests 默认会补 Accept: * / Connection: keep-alive，
     已在 MaimaiNetClient.__init__ 里从 session.headers 删掉。

     ★ Accept-Encoding 是唯一的例外，必须**存在且为空**：

         实测（GetGameSettingApi，2026-10-06）：
             Accept-Encoding: ""                -> 200 + application/json
             不发 / "gzip, deflate" / "identity" -> 200 + application/octet-stream（0 字节）

       反推：真机能拿到 JSON 响应体，说明 Mono 发的也是**空值**的 Accept-Encoding
       （Headers.AllKeys 里看不到它，是框架层加的）。
       所以这里固定 Accept-Encoding: ""。

--------------------------------------------------------------------------------
三、对外接口
--------------------------------------------------------------------------------
     MaimaiNetClient         客户端类（连接复用 + Cookie 管理）
     get_default_client()    取全局默认客户端
     request(...)            便捷函数：发一次请求并返回原始 JSON 字符串
     request_vo(...)         便捷函数：发一次请求并返回映射后的 dataclass

     加解密工具：aes_encrypt / aes_decrypt / deflate_compress / deflate_decompress
     协议工具  ：obfuscate_api_name / build_api_url / adler32
"""

from __future__ import annotations

import hashlib
import json
import time
import zlib
from dataclasses import dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar
from urllib.parse import urljoin

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from config import CLIENT_ID, MAI_ENCODING, TIMEOUT_LONG_MS, TIMEOUT_MS

# =============================================================================
# 协议常量（原在 config.py，2026-10-06 下沉到本模块 —— 它们只服务于网络层）
# =============================================================================

#: 游戏服务器（Maimai2Servlet）
#: 依据 source/Assembly-CSharp/Manager/OperationManager.cs:225,338
#:     _operationData.ServerUri = Auth.GameServerUri + MovieServerUri("mE2s3Jhd/")
BASE_URL = "https://maimai-gm.wahlap.com:42081/Maimai2Servlet/mE2s3Jhd/"

#: AES 参数，依据 source/Assembly-CSharp/Net/CipherAES.cs:11-12
#:   AesKey 32 字节 -> AES-256；AesIV 16 字节
AES_KEY = b"FKM2JX:VjZNK6hc:A0<JU:i5oR7LA]9W"
AES_IV = b"F>;24DjU9W6ZsRH["

#: API 名混淆盐，依据 source/Assembly-CSharp/Net.Packet/Packet.cs:44
#: 用法：URL 尾段 = md5(逻辑接口名 + "MaimaiChn" + OBFUSCATE_PARAM) 小写 hex
OBFUSCATE_PARAM = "8bF76dE9"

from .log_setup import log_debug, log_error, log_request, log_response

# =============================================================================
# 协议常量
# =============================================================================

#: API 名后缀（NetQuery.cs:14  Api = api + "MaimaiChn"）
API_SUFFIX = "MaimaiChn"

#: HTTP 头（NetHttpClient.cs:174-190）
HEADER_CONTENT_TYPE = "application/json"
HEADER_CHARSET = "UTF-8"
HEADER_CONTENT_ENCODING = "deflate"

#: AES 参数
AES_BLOCK_SIZE = 16

T = TypeVar("T")


# =============================================================================
# 一、协议工具
# =============================================================================

def obfuscate_api_name(api_name: str) -> str:
    """
    对逻辑接口名做 MD5 混淆，得到 URL 尾段（对应 Packet.Obfuscator）。

        逻辑名 "GetUserPreviewApi"  ->  "GetUserPreviewApiMaimaiChn"
                                    ->  md5(上面 + "8bF76dE9")

    参数：
        api_name: 逻辑接口名，**不要**自己带 MaimaiChn 后缀

    返回：
        32 位小写十六进制字符串
    """
    full_name = api_name if api_name.endswith(API_SUFFIX) else api_name + API_SUFFIX
    return hashlib.md5((full_name + OBFUSCATE_PARAM).encode("utf-8")).hexdigest()


def build_api_url(api_name: str) -> str:
    """构建完整的请求 URL。"""
    return urljoin(BASE_URL, obfuscate_api_name(api_name))


def build_user_agent(api_name: str, user_id: int = 0, client_id: str = CLIENT_ID) -> str:
    """
    构建 User-Agent（对应 NetPacketUtil.GetUserAgent）。

        userId != 0  ->  "<混淆API名>#<userId>"
        userId == 0  ->  "<混淆API名>#<clientId>"
    """
    tail = user_id if user_id else client_id
    return obfuscate_api_name(api_name) + "#" + str(tail)


def adler32(data: bytes) -> int:
    """
    计算 Adler-32 校验和（对应 NetHttpClient.Adler32:437-452）。

    ★ 注意与 zlib.adler32 的区别：C# 端是自己实现的，
      返回值是 (b << 16) + a，与 zlib.adler32 一致，这里保留原实现以便对照。
    """
    a = 1
    b = 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


# =============================================================================
# 二、加解密 / 压缩
# =============================================================================

def aes_encrypt(data: bytes) -> bytes:
    """AES-256-CBC 加密（PKCS7 填充）。对应 CipherAES.Encrypt。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data, AES_BLOCK_SIZE))


def aes_decrypt(data: bytes) -> bytes:
    """AES-256-CBC 解密（PKCS7 去填充）。对应 CipherAES.Decrypt。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(data), AES_BLOCK_SIZE)


def deflate_compress(data: bytes) -> bytes:
    """
    原始 deflate 压缩 + 手工拼 zlib 头与 Adler32。

    对应 NetHttpClient.cs:262-300 RequestCallback：
        memoryStream.WriteByte(120);      // 0x78
        memoryStream.WriteByte(156);      // 0x9C
        ... 原始 deflate 数据 ...
        ... Adler32 大端 4 字节 ...

    ★ C# 的 DeflateStream 产生的是**原始 deflate**（无 zlib 头），
      所以 Python 侧要用 compressobj(wbits=-zlib.MAX_WBITS)。
    """
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    compressed = compressor.compress(data) + compressor.flush()
    checksum = adler32(data)
    return bytes([0x78, 0x9C]) + compressed + checksum.to_bytes(4, "big")


def deflate_decompress(data: bytes) -> bytes:
    """
    去掉 zlib 头与 Adler32 后做原始 deflate 解压。

    对应 NetHttpClient.cs:355-380 Decompress：
        _temporaryStream.Position = 2;                          // 跳过 2 字节头
        _temporaryStream.SetLength(_temporaryStream.Length - 4); // 去掉 4 字节校验
    """
    if len(data) < 6:
        return b""
    return zlib.decompress(data[2:-4], -zlib.MAX_WBITS)


# =============================================================================
# 三、真机时间戳
# =============================================================================

def local_utc_offset_seconds() -> int:
    """取本机时区相对 UTC 的偏移秒数（东八区 = +28800）。"""
    offset = -time.timezone
    if time.daylight and time.localtime().tm_isdst > 0:
        offset = -time.altzone
    return int(offset)


def login_date_time_now() -> int:
    """
    生成真机 UserLoginApi 的 loginDateTime。

    ★ 真机算法（source/Assembly-CSharp/MAI2/DateTime.cs + PacketUserLogin.cs:29）：
        MAI2.DateTime.Now 返回 DateTime.UtcNow + LocalOffset，Kind = Unspecified；
        new DateTimeOffset(该 Unspecified 值) 会再按本地时区加一次偏移，
        最终 ToUnixTimeSeconds() = 标准 Unix 秒 + 本地时区偏移。

      东八区即 now + 28800。

    ★ 为什么必须一致：
        PacketUserLogin.cs:43 会把请求值回填进响应，
        PacketUpsertUserAll.cs:31 / PacketUserLogout.cs:29 都复用该值，
        与登录时不一致会被服务端拒绝。
    """
    return int(time.time()) + local_utc_offset_seconds()


# =============================================================================
# 四、VO 序列化 / 反序列化
# =============================================================================

def vo_to_json(obj: Any) -> str:
    """
    把请求对象序列化成紧凑 JSON（对应 VOSerializer.Serialize）。

    规则：
        - dataclass       -> 按字段声明顺序，跳过值为 None 的字段
        - 带 __dict__ 的对象 -> 同上
        - dict / 其他      -> 直接 json.dumps
    """
    if obj is None:
        return "{}"
    if is_dataclass(obj) and not isinstance(obj, type):
        data = {k: getattr(obj, k) for k in obj.__dataclass_fields__}
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False, default=_json_default)
    if isinstance(obj, dict):
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=_json_default)
    if hasattr(obj, "__dict__"):
        data = {k: v for k, v in vars(obj).items() if v is not None and not k.startswith("_")}
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False, default=_json_default)
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> Any:
    """json.dumps 的兜底转换：dataclass / 普通对象 -> dict。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: getattr(value, k) for k in value.__dataclass_fields__}
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def _convert_value(value: Any, target_type: Any) -> Any:
    """按目标类型递归转换嵌套 dataclass。"""
    if value is None:
        return None

    if isinstance(target_type, type) and is_dataclass(target_type) and isinstance(value, dict):
        kwargs = {}
        for fname, fdef in target_type.__dataclass_fields__.items():
            if fname in value:
                kwargs[fname] = _convert_value(value[fname], fdef.type)
        return target_type(**kwargs)

    origin = getattr(target_type, "__origin__", None)
    if origin is list and isinstance(value, list):
        args = getattr(target_type, "__args__", None)
        if args and isinstance(args[0], type) and is_dataclass(args[0]):
            return [_convert_value(v, args[0]) for v in value]
        return value

    return value


def vo_from_json(cls: Type[T], json_str: str) -> T:
    """
    把响应 JSON 反序列化成 dataclass（对应 VOSerializer.Deserialize）。

    ★ 只填充类里声明过的字段 —— 服务端多给的字段会被忽略，不会报错。
    """
    data = json.loads(json_str)
    if not isinstance(data, dict):
        return data  # type: ignore[return-value]

    if is_dataclass(cls):
        kwargs = {}
        for fname, fdef in cls.__dataclass_fields__.items():
            if fname in data:
                kwargs[fname] = _convert_value(data[fname], fdef.type)
        return cls(**kwargs)

    obj = cls()  # type: ignore[call-arg]
    for k, v in data.items():
        if hasattr(obj, k):
            setattr(obj, k, v)
    return obj


# =============================================================================
# 五、网络客户端
# =============================================================================

class MaimaiNetError(RuntimeError):
    """网络层 / 协议层错误。"""


class MaimaiNetClient:
    """
    舞萌DX 游戏服务器客户端。

    一次完整请求的流程：

        请求方向：VO -> 紧凑 JSON -> 原始 deflate -> 0x78 0x9C + Adler32 -> AES-256-CBC -> HTTP POST
        响应方向：HTTP Body -> AES 解密 -> 去 2 字节头 / 4 字节尾 -> deflate 解压 -> JSON -> VO

    Cookie 由 requests.Session 自动管理；登录接口返回的 Set-Cookie 会被保存，
    后续请求自动带上（对应 C# 的 CookieContainer，Packet.cs:183-190）。
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout_ms: int = TIMEOUT_MS,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout_ms / 1000.0
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # ---------------------------------------------------------------------
        # ★ 对齐真机的请求头集合（2026-10-06 真机抓包实证）
        # ---------------------------------------------------------------------
        # 真机（Unity Mono 的 HttpWebRequest）在 Headers.AllKeys 里**只有**：
        #     number / Content-Type / User-Agent / charset / Mai-Encoding /
        #     Content-Encoding / (+ Cookie)
        # 没有 Accept，也没有 Connection。
        #
        # 而 requests 默认会补上：
        #     Accept: */*        <- 删掉（真机不发）
        #     Connection: keep-alive <- 删掉（真机不发；HTTP/1.1 本来就是长连接）
        #     Accept-Encoding    <- 删掉（真机不发），改由 _build_headers 显式置空
        #
        # ★ Accept-Encoding 为什么必须**存在且为空**：
        #     实测（GetGameSettingApi，2026-10-06）：
        #         Accept-Encoding: ""              -> 200 + application/json（384 B）
        #         不发该头 / "gzip, deflate" / "identity"
        #                                          -> 200 + application/octet-stream（0 B）
        #   所以这里从 Session 默认里删掉，再由 _build_headers 显式发一个空值。
        self.session.headers.pop("Accept", None)
        self.session.headers.pop("Connection", None)
        self.session.headers.pop("Accept-Encoding", None)

        #: ★ number 头的值（Packet.cs:189 GameManager.PingMsec）。
        #:   只由 **Ping 心跳包**更新（对应 PingChecker.cs:227 PingSuccess），
        #:   普通业务请求不会改动它 —— 真机整局 53 个请求的 number 恒为 63。
        self.ping_msec: int = 0

        if not verify_ssl:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # 内部
    # -------------------------------------------------------------------------

    def _build_headers(
        self,
        api_name: str,
        user_id: int = 0,
        client_id: str = CLIENT_ID,
        has_body: bool = True,
        ping_msec: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        构建请求头（对应 NetHttpClient.Request:174-190 + Packet.ProcImpl:166-176）。

        ★ 关于 number 头：
            source/Assembly-CSharp/Net.Packet/Packet.cs:187-194

                if (!IsPingPacket())
                {
                    Client.AddHeader("number", GameManager.PingMsec.ToString());
                    if (Query.UserId != 0L) { Client.AddCookie(Query.UserId); }
                }

            即**除 Ping 外的每个接口**都会带一个 number 头，值是本机到服务器的
            ping 毫秒数（GameManager.PingMsec）。

        ★ number 的来源（源码链路，逐条可查）：
            Main/PingChecker.cs:166   StartPacket(new PacketPing(PingSuccess, PingError))
            Net.Packet.Mai2/PacketPing.cs:34
                                      _onDone((int)sw.ElapsedMilliseconds)
                                      → 值 = **Ping 包的往返毫秒**
            Main/PingChecker.cs:227   GameManager.PingMsec = pingMsec

            所以 number **只由 Ping 心跳刷新**，普通业务请求不会改它。
            实测（gamehook 抓真机一局 70 个请求）：
                #1  ~ #10   number = 0     ← 还没跑过 Ping
                #11 ~ #17   Ping 心跳（不带 number 头）
                #18 ~ #70   number = 63    ← Ping 往返 63ms，此后恒定
            本类在 request() 里对 Ping 包做同样的事：把往返毫秒写进 self.ping_msec。

        ★ 关于 Cookie（Packet.cs:190-193 + 228-234）：
            Client.AddCookie(Query.UserId) 把「登录时服务端 Set-Cookie 存下来的
            CookieContainer」挂到本次请求上（NetHttpClient.cs:170-177）。

            ★ 实测 **UserLoginApi 的响应头里确实有**：
                Set-Cookie: JSESSIONID=FC9D0F122F7F24A522CD623BA3B76B74; Path=/Maimai2Servlet; HttpOnly
              而 Ping 等接口的响应头里没有 Set-Cookie（只有 Date / Content-Type /
              Content-Length / Connection / Pragma / Cache-Control）。
              所以「登录前没有 Cookie、登录后一直带着 JSESSIONID」正是真机行为。

            Cookie 由 requests.Session 自动管理：收到就存、后续自动带 —— 无需额外代码，
            但**必须全程复用同一个 MaimaiNetClient**，否则会丢掉 JSESSIONID。
        """
        headers = {
            "Content-Type": HEADER_CONTENT_TYPE,
            "charset": HEADER_CHARSET,
            "Mai-Encoding": MAI_ENCODING,
            "User-Agent": build_user_agent(api_name, user_id, client_id),
            # ★ 必须显式置空，见模块 docstring 第二节
            "Accept-Encoding": "",
        }
        if has_body:
            headers["Content-Encoding"] = HEADER_CONTENT_ENCODING
        # ★ number 头（Packet.cs:189）：除 Ping 外的接口都要带
        if not api_name.startswith("Ping"):
            value = self.ping_msec if ping_msec is None else ping_msec
            headers["number"] = str(int(value))
        return headers

    @property
    def last_ping_msec(self) -> int:
        """number 头的当前值（= 最近一次 Ping 的往返毫秒）。兼容旧字段名。"""
        return self.ping_msec

    def _encrypt_request(self, json_str: str) -> bytes:
        """JSON -> deflate(zlib头+Adler32) -> AES。"""
        return aes_encrypt(deflate_compress(json_str.encode("utf-8")))

    def _decrypt_response(self, encrypted: bytes) -> str:
        """AES -> 去头尾 -> deflate -> UTF-8 字符串。"""
        return deflate_decompress(aes_decrypt(encrypted)).decode("utf-8")

    # -------------------------------------------------------------------------
    # 公开
    # -------------------------------------------------------------------------

    def request(
        self,
        api_name: str,
        request_vo: Any = None,
        *,
        user_id: int = 0,
        client_id: str = CLIENT_ID,
        timeout_ms: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        发送一次请求，返回**原始 JSON 响应字符串**。

        参数：
            api_name:      逻辑接口名（如 "GetUserPreviewApi"，不要带 MaimaiChn）
            request_vo:    请求体对象（dataclass / dict / None 表示空对象 {}）
            user_id:       用户 ID（0 表示未登录请求；影响 User-Agent 与 Cookie）
            client_id:     客户端 ID
            timeout_ms:    超时覆盖（毫秒）
            extra_headers: 额外请求头（如 number）

        返回：
            响应 JSON 字符串

        异常：
            MaimaiNetError: 网络异常 / 空响应 / 解密或解压失败
        """
        url = urljoin(self.base_url, obfuscate_api_name(api_name))
        timeout = (timeout_ms or self.timeout * 1000) / 1000.0

        request_json = vo_to_json(request_vo)
        body = self._encrypt_request(request_json)

        headers = self._build_headers(api_name, user_id, client_id, has_body=True)
        if extra_headers:
            headers.update(extra_headers)

        # ★ DEBUG 模式：记录「向 api 发送的数据」
        log_request(url=url, body=request_json, headers=headers, api_name=api_name)

        t0 = time.monotonic()
        try:
            response = self.session.post(
                url,
                data=body,
                headers=headers,
                timeout=timeout,
                verify=self.verify_ssl,
            )
        except requests.exceptions.RequestException as exc:
            log_error("接口 " + api_name + " 请求失败：" + str(exc))
            raise MaimaiNetError("接口 " + api_name + " 请求失败：" + str(exc)) from exc

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # ★ 只有 Ping 包会刷新 number（对应 PingChecker.cs:224-229 PingSuccess）。
        #   普通业务包不动它，否则 number 会随每个包的耗时抖动，与真机不符。
        if api_name.startswith("Ping"):
            self.ping_msec = elapsed_ms
        content = response.content

        # 0 字节响应：请求未进入业务层
        if len(content) == 0:
            detail = (
                "接口 " + api_name + " 返回 HTTP " + str(response.status_code)
                + "，响应体为 0 字节（空响应）。\n"
                "  含义：服务端没有返回任何内容，请求很可能未进入业务层。\n"
                "  排查：userId/token 是否有效、接口名与请求体字段是否与源码一致、"
                "Accept-Encoding 是否被置空。\n"
                "  响应头：" + repr(dict(response.headers))
            )
            log_error(detail)
            raise MaimaiNetError(detail)

        try:
            response_json = self._decrypt_response(content)
        except ValueError as exc:
            detail = (
                "接口 " + api_name + " 响应解密失败（HTTP " + str(response.status_code)
                + "，body " + str(len(content)) + " 字节）：" + str(exc) + "\n"
                "  含义：服务器返回了内容，但不是合法的 AES 密文，或长度不是 16 的倍数。"
            )
            log_error(detail)
            raise MaimaiNetError(detail) from exc
        except zlib.error as exc:
            detail = (
                "接口 " + api_name + " 响应解压失败（HTTP " + str(response.status_code)
                + "，body " + str(len(content)) + " 字节）：" + str(exc) + "\n"
                "  含义：AES 解密成功但 deflate 解压失败，响应不是预期的压缩格式"
                "（可能是网关/防火墙返回的页面）。"
            )
            log_error(detail)
            raise MaimaiNetError(detail) from exc

        if not response_json:
            detail = (
                "接口 " + api_name + " 返回空明文（HTTP " + str(response.status_code)
                + "，密文 " + str(len(content)) + " 字节，解密后为空串）。\n"
                "  含义：链路与加密都正常，但服务端没有返回内容。\n"
                "  排查：userId / token 是否失效、keychip 与该卡是否匹配、该卡是否正在游戏中。"
            )
            log_error(detail)
            raise MaimaiNetError(detail)

        # ★ DEBUG 模式：记录「api 返回的数据」
        try:
            shown_body: Any = json.loads(response_json)
        except Exception:
            shown_body = response_json
        log_response(
            status=response.status_code,
            body=shown_body,
            headers={k: v for k, v in response.headers.items()},
            api_name=api_name,
            elapsed_ms=elapsed_ms,
        )

        return response_json

    def request_vo(
        self,
        api_name: str,
        request_vo: Any,
        response_cls: Type[T],
        *,
        user_id: int = 0,
        client_id: str = CLIENT_ID,
        timeout_ms: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> T:
        """发送请求并把响应映射成 dataclass。"""
        raw = self.request(
            api_name, request_vo,
            user_id=user_id, client_id=client_id,
            timeout_ms=timeout_ms, extra_headers=extra_headers,
        )
        return vo_from_json(response_cls, raw)

    def request_dict(
        self,
        api_name: str,
        request_vo: Any = None,
        *,
        user_id: int = 0,
        client_id: str = CLIENT_ID,
        timeout_ms: Optional[int] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        发送请求并返回**原始响应 dict**。

        ★ 取数脚本一律用这个：upsertUserAll 需要响应原文，
          映射成 dataclass 会丢掉服务端多给的字段。
        """
        raw = self.request(
            api_name, request_vo,
            user_id=user_id, client_id=client_id,
            timeout_ms=timeout_ms, extra_headers=extra_headers,
        )
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"_data": data}

    def close(self) -> None:
        """关闭底层会话。"""
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "MaimaiNetClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# =============================================================================
# 六、全局默认客户端
# =============================================================================

_default_client: Optional[MaimaiNetClient] = None


def get_default_client() -> MaimaiNetClient:
    """获取（必要时创建）全局默认客户端 —— 连接与 Cookie 会自动复用。"""
    global _default_client
    if _default_client is None:
        _default_client = MaimaiNetClient()
    return _default_client


def close_default_client() -> None:
    """关闭全局默认客户端（一般不需要手动调用）。"""
    global _default_client
    if _default_client is not None:
        _default_client.close()
        _default_client = None


def request(
    api_name: str,
    request_vo: Any = None,
    *,
    user_id: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str:
    """便捷函数：用默认客户端发一次请求，返回原始 JSON 字符串。"""
    net = client or get_default_client()
    return net.request(
        api_name, request_vo,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms, extra_headers=extra_headers,
    )


def request_dict(
    api_name: str,
    request_vo: Any = None,
    *,
    user_id: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """便捷函数：用默认客户端发一次请求，返回原始响应 dict。"""
    net = client or get_default_client()
    return net.request_dict(
        api_name, request_vo,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms, extra_headers=extra_headers,
    )


def request_vo(
    api_name: str,
    request_vo: Any,
    response_cls: Type[T],
    *,
    user_id: int = 0,
    client_id: str = CLIENT_ID,
    timeout_ms: Optional[int] = None,
    client: Optional[MaimaiNetClient] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> T:
    """便捷函数：用默认客户端发一次请求，返回映射后的 dataclass。"""
    net = client or get_default_client()
    return net.request_vo(
        api_name, request_vo, response_cls,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms, extra_headers=extra_headers,
    )


# =============================================================================
# 七、通用请求 / 响应 VO
# =============================================================================

@dataclass
class EmptyRequestVO:
    """空请求体 —— 对应 C# 里没有任何字段的 RequestVO（如 PingRequestVO）。"""


@dataclass
class UserIdRequestVO:
    """只有 userId 的请求体（对应 UserDetailRequestVO / UserCharacterRequestVO 等）。"""
    userId: int


@dataclass
class ReturnCodeVO:
    """通用「只有 returnCode」的响应体。"""
    returnCode: int = 0


# =============================================================================
# 单独运行：协议自检（不发业务请求）
# =============================================================================

if __name__ == "__main__":
    print("=== maimai_net 协议自检 ===")
    print("BASE_URL          :", BASE_URL)
    print("GetGameSettingApi :", build_api_url("GetGameSettingApi"))
    print("  期望尾段         : 83a5d5a20b062c5c2ad817460b8f7f76")
    print("User-Agent 示例   :", build_user_agent("UserLoginApi", 12345678))

    sample = '{"userId":12345678,"token":"abc"}'
    packed = deflate_compress(sample.encode("utf-8"))
    print("deflate 头/尾     :", packed[:2].hex(), packed[-4:].hex(),
          " Adler32 =", hex(adler32(sample.encode("utf-8"))))
    assert deflate_decompress(packed).decode("utf-8") == sample

    enc = aes_encrypt(packed)
    assert aes_decrypt(enc) == packed
    print("AES 往返           : OK（密文", len(enc), "字节，16 的倍数：", len(enc) % 16 == 0, "）")
    print("自检通过")
