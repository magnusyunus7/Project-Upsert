# -*- coding: utf-8 -*-
"""
maimai_net.py —— textDX networktext（text HTTP Reprint）
================================================================================

textis【Unique】directlyandtextservertextoftext，Remaining api scriptalltextreceivehairpacket。

--------------------------------------------------------------------------------
One、Agreement Basis（All from source/ Decompile source code）
--------------------------------------------------------------------------------

1) servertextAnd API text
     source/Assembly-CSharp/Manager/OperationManager.cs:225,338
         ServerUri = Auth.GameServerUri + MovieServerUri("mE2s3Jhd/")
     source/Assembly-CSharp/Net.Packet/Packet.cs:116
         Client = NetHttpClient.Create(BaseUrl + Obfuscator(query.Api))
     source/Assembly-CSharp/Net.Packet/Packet.cs:485
         Obfuscator(s) = md5_hex_lower(s + "8bF76dE9")
     source/Assembly-CSharp/Net.VO/NetQuery.cs:14
         Api = api + "MaimaiChn"

     => Final URL = BASE_URL + md5(textinterfaceFirst name + "MaimaiChn" + "8bF76dE9")

     Validated with real logs：md5("GetGameSettingApiMaimaiChn" + "8bF76dE9")
                       = 83a5d5a20b062c5c2ad817460b8f7f76
                       （source/2026-10-05.log:1 ofrequestistexttothisPieceTail Segment）

2) request bodytext（Stage 3：JSON -> deflate -> AES）
     source/Assembly-CSharp/Net/NetHttpClient.cs:262-300 RequestCallback
         a. DeflateStream(CompressionMode.Compress) Compression JSON Bytes
         b. Spell it by hand zlib Head 0x78 0x9C + Compress Data + Adler32(4 Byte Big End)
         c. CipherAES.Encrypt(...) text AES Encryption
     source/Assembly-CSharp/Net/CipherAES.cs:11-30
         AES-256-CBC / PKCS7 / Key 32B / IV 16B

3) Response body decapsulation（text）
     source/Assembly-CSharp/Net/NetHttpClient.cs:355-380 Decrypt + Decompress
         a. AES decrypt
         b. Before Removal 2 Bytes zlib Head and back 4 Bytes Adler32
         c. Deflate text -> UTF-8 JSON

4) requestHead
     source/Assembly-CSharp/Net/NetHttpClient.cs:174-190 Request()
         Content-Type   : application/json
         charset        : UTF-8
         Mai-Encoding   : 1.55      (DefaultHttpHeaderEncryption)
         Content-Encoding: deflate  (hasrequest bodytime)
         User-Agent     : <obfuscationAfterofAPIFirst name>#<userId or clientId>
                          （source/Assembly-CSharp/Net/NetPacketUtil.cs:12-19）
         number         : <ping textseconds>（non- Ping interface；Packet.cs:189）

     ★ number ofsemantic：GameManager.PingMsec，Only by Ping Heartbeat Package Refresh
       （PingChecker.cs:227 <- PacketPing.cs:34 of sw.ElapsedMilliseconds）。
       real machinetextgame 53 of business requests number Constant is the same value（Measured 63）。
       So the caller**You should run once first Ping()**，After that, the request will bring the real thing. number；
       texttime number = 0，Consistent with the behavior of the first screen after the real machine is turned on。

     ★ Cookie：★ UserLoginApi ofResponseMeetingsIssue
           Set-Cookie: JSESSIONID=FC9D0F122F7F24A522CD623BA3B76B74; Path=/Maimai2Servlet; HttpOnly
       （Packet.cs:228-234 Only in UserLogin Respond by including it in the CookieContainer，
        After Packet.cs:190-193 eachPieceBelt userId ofrequestalltexttimesGo）。
       Ping etcinterfaceofResponse headerinnone Set-Cookie，so you have to run through the login to get it.。
       this is**realofSessiontext**，Must bring。
       requests.Session will automatically take it off and take it with you，notextCode ——
       but only if**Reuse the same throughout MaimaiNetClient**（use get_default_client()）。

--------------------------------------------------------------------------------
Two、★ requestHeadtext：Must be consistent with the real machine（2026-10-06 real machinetextPackageEmpirical）
--------------------------------------------------------------------------------
     real machine（Unity Mono of HttpWebRequest）Actual emitted head**Only these few**：

         number / Content-Type / User-Agent / charset / Mai-Encoding /
         Content-Encoding / (+ loginAfterof Cookie)

     **none Accept，Neither Connection。**

     requests defaultMeetingstext Accept: * / Connection: keep-alive，
     at MaimaiNetClient.__init__ inFrom session.headers Delete。

     ★ Accept-Encoding isUniqueofExampletext，Required**Exists and is empty**：

         Measured（GetGameSettingApi，2026-10-06）：
             Accept-Encoding: ""                -> 200 + application/json
             Do not send / "gzip, deflate" / "identity" -> 200 + application/octet-stream（0 Bytes）

       Reverse：real machinecantextto JSON Response body，description Mono The hair is also**emptyValue**of Accept-Encoding
       （Headers.AllKeys intextNototext，istextPlusof）。
       So it's fixed here. Accept-Encoding: ""。

--------------------------------------------------------------------------------
Three、External Interface
--------------------------------------------------------------------------------
     MaimaiNetClient         Client Class（textMultiplexing + Cookie text）
     get_default_client()    Take global default client
     request(...)            Convenience functions：Make a request and return to the original JSON String
     request_vo(...)         Convenience functions：Send a request and return the mapped dataclass

     Encryption and decryption tools：aes_encrypt / aes_decrypt / deflate_compress / deflate_decompress
     Protocol Tools  ：obfuscate_api_name / build_api_url / adler32
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
# Protocol Constants（Originally at config.py，2026-10-06 sink to this module —— They only serve the network layer）
# =============================================================================

#: textserver（Maimai2Servlet）
#: Basis source/Assembly-CSharp/Manager/OperationManager.cs:225,338
#:     _operationData.ServerUri = Auth.GameServerUri + MovieServerUri("mE2s3Jhd/")
BASE_URL = "https://maimai-gm.wahlap.com:42081/Maimai2Servlet/mE2s3Jhd/"

#: AES Parameter，Basis source/Assembly-CSharp/Net/CipherAES.cs:11-12
#:   AesKey 32 Bytes -> AES-256；AesIV 16 Bytes
AES_KEY = b"FKM2JX:VjZNK6hc:A0<JU:i5oR7LA]9W"
AES_IV = b"F>;24DjU9W6ZsRH["

#: API First name obfuscated salt，Basis source/Assembly-CSharp/Net.Packet/Packet.cs:44
#: usage：URL Tail Segment = md5(textinterfaceFirst name + "MaimaiChn" + OBFUSCATE_PARAM) Lowercase hex
OBFUSCATE_PARAM = "8bF76dE9"

from .log_setup import log_debug, log_error, log_request, log_response

# =============================================================================
# Protocol Constants
# =============================================================================

#: API First Name Suffix（NetQuery.cs:14  Api = api + "MaimaiChn"）
API_SUFFIX = "MaimaiChn"

#: HTTP Head（NetHttpClient.cs:174-190）
HEADER_CONTENT_TYPE = "application/json"
HEADER_CHARSET = "UTF-8"
HEADER_CONTENT_ENCODING = "deflate"

#: AES Parameter
AES_BLOCK_SIZE = 16

T = TypeVar("T")


# =============================================================================
# One、Protocol Tools
# =============================================================================

def obfuscate_api_name(api_name: str) -> str:
    """
    Do the name of the logical interface MD5 obfuscation，Get URL Tail Segment（Corresponding Packet.Obfuscator）。

        textFirst name "GetUserPreviewApi"  ->  "GetUserPreviewApiMaimaiChn"
                                    ->  md5(Above + "8bF76dE9")

    Parameter：
        api_name: textinterfaceFirst name，**Don't**textBelt MaimaiChn Suffix

    returntimes：
        32 Bits Lowercase Hexadecimal String
    """
    full_name = api_name if api_name.endswith(API_SUFFIX) else api_name + API_SUFFIX
    return hashlib.md5((full_name + OBFUSCATE_PARAM).encode("utf-8")).hexdigest()


def build_api_url(api_name: str) -> str:
    """textFullofrequest URL。"""
    return urljoin(BASE_URL, obfuscate_api_name(api_name))


def build_user_agent(api_name: str, user_id: int = 0, client_id: str = CLIENT_ID) -> str:
    """
    text User-Agent（Corresponding NetPacketUtil.GetUserAgent）。

        userId != 0  ->  "<obfuscationAPIFirst name>#<userId>"
        userId == 0  ->  "<obfuscationAPIFirst name>#<clientId>"
    """
    tail = user_id if user_id else client_id
    return obfuscate_api_name(api_name) + "#" + str(tail)


def adler32(data: bytes) -> int:
    """
    countcalculate Adler-32 textand（Corresponding NetHttpClient.Adler32:437-452）。

    ★ noteAnd zlib.adler32 oftext：C# textistextcurrentof，
      returntimesValue is (b << 16) + a，And zlib.adler32 Match，thisinHoldHaratextcurrentintextControl。
    """
    a = 1
    b = 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


# =============================================================================
# Two、Encryption and decryption / Compression
# =============================================================================

def aes_encrypt(data: bytes) -> bytes:
    """AES-256-CBC Encryption（PKCS7 Fill）。Corresponding CipherAES.Encrypt。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data, AES_BLOCK_SIZE))


def aes_decrypt(data: bytes) -> bytes:
    """AES-256-CBC decrypt（PKCS7 Unfill）。Corresponding CipherAES.Decrypt。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(data), AES_BLOCK_SIZE)


def deflate_compress(data: bytes) -> bytes:
    """
    Original deflate Compression + Spell it by hand zlib Head vs. Adler32。

    Corresponding NetHttpClient.cs:262-300 RequestCallback：
        memoryStream.WriteByte(120);      // 0x78
        memoryStream.WriteByte(156);      // 0x9C
        ... Original deflate data ...
        ... Adler32 Big End 4 Bytes ...

    ★ C# of DeflateStream The result is**Original deflate**（no zlib Head），
      So Python Side to use compressobj(wbits=-zlib.MAX_WBITS)。
    """
    compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
    compressed = compressor.compress(data) + compressor.flush()
    checksum = adler32(data)
    return bytes([0x78, 0x9C]) + compressed + checksum.to_bytes(4, "big")


def deflate_decompress(data: bytes) -> bytes:
    """
    Remove zlib Head vs. Adler32 Post-primitive deflate text。

    Corresponding NetHttpClient.cs:355-380 Decompress：
        _temporaryStream.Position = 2;                          // skip 2 Byte header
        _temporaryStream.SetLength(_temporaryStream.Length - 4); // Remove 4 Byte check
    """
    if len(data) < 6:
        return b""
    return zlib.decompress(data[2:-4], -zlib.MAX_WBITS)


# =============================================================================
# Three、real machinetimetext
# =============================================================================

def local_utc_offset_seconds() -> int:
    """Take the native time zone relative UTC ofOffsetsecondsnumber（Dongba District = +28800）。"""
    offset = -time.timezone
    if time.daylight and time.localtime().tm_isdst > 0:
        offset = -time.altzone
    return int(offset)


def login_date_time_now() -> int:
    """
    textreal machine UserLoginApi of loginDateTime。

    ★ real machinecalculatetext（source/Assembly-CSharp/MAI2/DateTime.cs + PacketUserLogin.cs:29）：
        MAI2.DateTime.Now returntimes DateTime.UtcNow + LocalOffset，Kind = Unspecified；
        new DateTimeOffset(the Unspecified Value) will add another offset by local time zone，
        Final ToUnixTimeSeconds() = standard Unix seconds + texttimetextOffset。

      Eastern Eight Wards now + 28800。

    ★ Why it must be consistent：
        PacketUserLogin.cs:43 will backfill the request value into the response，
        PacketUpsertUserAll.cs:31 / PacketUserLogout.cs:29 allMultiplexingtheValue，
        Inconsistent with login will be rejected by the server。
    """
    return int(time.time()) + local_utc_offset_seconds()


# =============================================================================
# Four、VO Serialization / Deserialization
# =============================================================================

def vo_to_json(obj: Any) -> str:
    """
    putrequestObjectSerializationtext JSON（Corresponding VOSerializer.Serialize）。

    textThen：
        - dataclass       -> pressFieldDeclarationorder，skipValuefor None ofField
        - Belt __dict__ ofObject -> Ibid.
        - dict / Other      -> directly json.dumps
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
    """json.dumps ofPocket backtext：dataclass / textObject -> dict。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: getattr(value, k) for k in value.__dataclass_fields__}
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)


def _convert_value(value: Any, target_type: Any) -> Any:
    """presstextReturnedtextNested dataclass。"""
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
    putResponse JSON Deserialize to dataclass（Corresponding VOSerializer.Deserialize）。

    ★ Populate only declared fields in the class —— servertextofFieldMeetingstextIgnore，No errors。
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
# Five、networkClient
# =============================================================================

class MaimaiNetError(RuntimeError):
    """networktext / Protocol Layer Error。"""


class MaimaiNetClient:
    """
    textDX textserverClient。

    The process of a full request：

        requesttextTowards：VO -> text JSON -> Original deflate -> 0x78 0x9C + Adler32 -> AES-256-CBC -> HTTP POST
        Response Direction：HTTP Body -> AES decrypt -> Go 2 Byte header / 4 End of byte -> deflate text -> JSON -> VO

    Cookie by requests.Session text；logininterfacereturntimesof Set-Cookie will be saved，
    Subsequent requests automatically bring（Corresponding C# of CookieContainer，Packet.cs:183-190）。
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
        # ★ Align request header collection of the real machine（2026-10-06 real machinetextPackageEmpirical）
        # ---------------------------------------------------------------------
        # real machine（Unity Mono of HttpWebRequest）at Headers.AllKeys in**Only**：
        #     number / Content-Type / User-Agent / charset / Mai-Encoding /
        #     Content-Encoding / (+ Cookie)
        # none Accept，Neither Connection。
        #
        # and requests defaultMeetingstextUp：
        #     Accept: */*        <- Delete（real machineDo not send）
        #     Connection: keep-alive <- Delete（real machineDo not send；HTTP/1.1 textislongtext）
        #     Accept-Encoding    <- Delete（real machineDo not send），changeby _build_headers explicittextempty
        #
        # ★ Accept-Encoding Why it must be**Exists and is empty**：
        #     Measured（GetGameSettingApi，2026-10-06）：
        #         Accept-Encoding: ""              -> 200 + application/json（384 B）
        #         Don't hair the right hair / "gzip, deflate" / "identity"
        #                                          -> 200 + application/octet-stream（0 B）
        #   So here from Session defaultinDelete，Then by _build_headers explicithairOneemptyValue。
        self.session.headers.pop("Accept", None)
        self.session.headers.pop("Connection", None)
        self.session.headers.pop("Accept-Encoding", None)

        #: ★ number Value of the header（Packet.cs:189 GameManager.PingMsec）。
        #:   Only by **Ping Heartbeat Packet**update（Corresponding PingChecker.cs:227 PingSuccess），
        #:   textrequestNoMeetingschangetext —— real machinetextgame 53 of requests number Constantly 63。
        self.ping_msec: int = 0

        if not verify_ssl:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Internal
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
        textrequestHead（Corresponding NetHttpClient.Request:174-190 + Packet.ProcImpl:166-176）。

        ★ About number Head：
            source/Assembly-CSharp/Net.Packet/Packet.cs:187-194

                if (!IsPingPacket())
                {
                    Client.AddHeader("number", GameManager.PingMsec.ToString());
                    if (Query.UserId != 0L) { Client.AddCookie(Query.UserId); }
                }

            i.e.**text Ping Per Interface Outside**allMeetingsBeltOne number Head，Value is native to server
            ping textsecondsnumber（GameManager.PingMsec）。

        ★ number oftext（source codetext，textitemtextcheck）：
            Main/PingChecker.cs:166   StartPacket(new PacketPing(PingSuccess, PingError))
            Net.Packet.Mai2/PacketPing.cs:34
                                      _onDone((int)sw.ElapsedMilliseconds)
                                      → Value = **Ping Packet round trip in milliseconds**
            Main/PingChecker.cs:227   GameManager.PingMsec = pingMsec

            So number **Only by Ping Heartbeat Refresh**，textrequestNoMeetingschangetext。
            Measured（gamehook textreal machineOnegame 70 requests）：
                #1  ~ #10   number = 0     ← text Ping
                #11 ~ #17   Ping Heartbeat（Without number Head）
                #18 ~ #70   number = 63    ← Ping Round trip 63ms，textAfterHengtext
            textat request() inYes. Ping to do the same thing.：putRound triptextsecondstext self.ping_msec。

        ★ About Cookie（Packet.cs:190-193 + 228-234）：
            Client.AddCookie(Query.UserId) put「logintimeserver Set-Cookie Saved
            CookieContainer」texttotextrequestUp（NetHttpClient.cs:170-177）。

            ★ Measured **UserLoginApi ofResponse headerintexthas**：
                Set-Cookie: JSESSIONID=FC9D0F122F7F24A522CD623BA3B76B74; Path=/Maimai2Servlet; HttpOnly
              and Ping etcinterfaceofResponse headerinnone Set-Cookie（Only Date / Content-Type /
              Content-Length / Connection / Pragma / Cache-Control）。
              So「loginagonone Cookie、loginAfterOnetextBelttext JSESSIONID」currentisreal machinetextfor。

            Cookie by requests.Session text：receivetotext、Subsequent automatic tape —— notextCode，
            But**Must reuse the same throughout MaimaiNetClient**，Otherwise, it will be discarded. JSESSIONID。
        """
        headers = {
            "Content-Type": HEADER_CONTENT_TYPE,
            "charset": HEADER_CHARSET,
            "Mai-Encoding": MAI_ENCODING,
            "User-Agent": build_user_agent(api_name, user_id, client_id),
            # ★ Must be explicitly empty，text docstring numberTwotext
            "Accept-Encoding": "",
        }
        if has_body:
            headers["Content-Encoding"] = HEADER_CONTENT_ENCODING
        # ★ number Head（Packet.cs:189）：text Ping External interfaces must be
        if not api_name.startswith("Ping"):
            value = self.ping_msec if ping_msec is None else ping_msec
            headers["number"] = str(int(value))
        return headers

    @property
    def last_ping_msec(self) -> int:
        """number Current value of the header（= Last Ping ofRound triptextseconds）。Compatible with old field names。"""
        return self.ping_msec

    def _encrypt_request(self, json_str: str) -> bytes:
        """JSON -> deflate(zlibHead+Adler32) -> AES。"""
        return aes_encrypt(deflate_compress(json_str.encode("utf-8")))

    def _decrypt_response(self, encrypted: bytes) -> str:
        """AES -> Go to head and tail -> deflate -> UTF-8 String。"""
        return deflate_decompress(aes_decrypt(encrypted)).decode("utf-8")

    # -------------------------------------------------------------------------
    # Public
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
        Send a request once，returntimes**Original JSON Response string**。

        Parameter：
            api_name:      textinterfaceFirst name（As "GetUserPreviewApi"，Do not bring MaimaiChn）
            request_vo:    request bodyObject（dataclass / dict / None textemptyObject {}）
            user_id:       user ID（0 textnotloginrequest；Impact User-Agent And Cookie）
            client_id:     Client ID
            timeout_ms:    texttimeoverwrite（textseconds）
            extra_headers: textrequestHead（As number）

        returntimes：
            Response JSON String

        Exceptions：
            MaimaiNetError: networkExceptions / emptyResponse / decryptortextFailed
        """
        url = urljoin(self.base_url, obfuscate_api_name(api_name))
        timeout = (timeout_ms or self.timeout * 1000) / 1000.0

        request_json = vo_to_json(request_vo)
        body = self._encrypt_request(request_json)

        headers = self._build_headers(api_name, user_id, client_id, has_body=True)
        if extra_headers:
            headers.update(extra_headers)

        # ★ DEBUG mode：record「Towards api Data sent」
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
            log_error("interface " + api_name + " requestFailed：" + str(exc))
            raise MaimaiNetError("interface " + api_name + " requestFailed：" + str(exc)) from exc

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # ★ Only Ping Package will refresh number（Corresponding PingChecker.cs:224-229 PingSuccess）。
        #   textPackageimmovabletext，Otherwise number will jitter with the time consuming of each packet，Does not match the real machine。
        if api_name.startswith("Ping"):
            self.ping_msec = elapsed_ms
        content = response.content

        # 0 Byte response：requestnottext
        if len(content) == 0:
            detail = (
                "interface " + api_name + " returntimes HTTP " + str(response.status_code)
                + "，Response body is 0 Bytes（emptyResponse）。\n"
                "  Meaning：servernonereturntimesAnyContent，requesttextcannottext。\n"
                "  textcheck：userId/token isNohastext、interfaceFirst nameAndrequest bodyFieldisNoAndsource codeMatch、"
                "Accept-Encoding isNotextempty。\n"
                "  Response header：" + repr(dict(response.headers))
            )
            log_error(detail)
            raise MaimaiNetError(detail)

        try:
            response_json = self._decrypt_response(content)
        except ValueError as exc:
            detail = (
                "interface " + api_name + " Response decryption failed（HTTP " + str(response.status_code)
                + "，body " + str(len(content)) + " Bytes）：" + str(exc) + "\n"
                "  Meaning：serverreturntimestextContent，But not legally. AES Ciphertext，or length is not 16 oftimesnumber。"
            )
            log_error(detail)
            raise MaimaiNetError(detail) from exc
        except zlib.error as exc:
            detail = (
                "interface " + api_name + " Response decompression failed（HTTP " + str(response.status_code)
                + "，body " + str(len(content)) + " Bytes）：" + str(exc) + "\n"
                "  Meaning：AES decryptSuccessBut deflate textFailed，Response is not in the expected compression format"
                "（Probably a gateway/textreturntimesoftext）。"
            )
            log_error(detail)
            raise MaimaiNetError(detail) from exc

        if not response_json:
            detail = (
                "interface " + api_name + " returntimesemptytext（HTTP " + str(response.status_code)
                + "，Ciphertext " + str(len(content)) + " Bytes，decryptAfteris an empty string）。\n"
                "  Meaning：textAndEncryptionallcurrenttext，But the server did not return any content。\n"
                "  textcheck：userId / token isNotext、keychip Match with this card?、thetextisNocurrentattext。"
            )
            log_error(detail)
            raise MaimaiNetError(detail)

        # ★ DEBUG mode：record「api returntimesofdata」
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
        """Send request and map response to dataclass。"""
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
        Send request and go back**Raw Response dict**。

        ★ Use this for all sampling scripts：upsertUserAll needResponse original text，
          text dataclass Will lose the fields given by the server。
        """
        raw = self.request(
            api_name, request_vo,
            user_id=user_id, client_id=client_id,
            timeout_ms=timeout_ms, extra_headers=extra_headers,
        )
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"_data": data}

    def close(self) -> None:
        """Close the underlying session。"""
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "MaimaiNetClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# =============================================================================
# Sat、Global Default Client
# =============================================================================

_default_client: Optional[MaimaiNetClient] = None


def get_default_client() -> MaimaiNetClient:
    """getTake（Create if necessary）Global Default Client —— textAnd Cookie will be automatically reused。"""
    global _default_client
    if _default_client is None:
        _default_client = MaimaiNetClient()
    return _default_client


def close_default_client() -> None:
    """Turn off global default client（Manual calls are generally not required）。"""
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
    """Convenience functions：usedefaultClientSend a request，returntimesOriginal JSON String。"""
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
    """Convenience functions：usedefaultClientSend a request，returntimesRaw Response dict。"""
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
    """Convenience functions：usedefaultClientSend a request，returntimestextAfterof dataclass。"""
    net = client or get_default_client()
    return net.request_vo(
        api_name, request_vo, response_cls,
        user_id=user_id, client_id=client_id,
        timeout_ms=timeout_ms, extra_headers=extra_headers,
    )


# =============================================================================
# Seven、textuserequest / Response VO
# =============================================================================

@dataclass
class EmptyRequestVO:
    """emptyrequest body —— Corresponding C# innoneAnyField RequestVO（As PingRequestVO）。"""


@dataclass
class UserIdRequestVO:
    """Only userId ofrequest body（Corresponding UserDetailRequestVO / UserCharacterRequestVO etc）。"""
    userId: int


@dataclass
class ReturnCodeVO:
    """textuse「Only returnCode」ofResponse body。"""
    returnCode: int = 0


# =============================================================================
# Run separately：Protocol Self-Test（Do not send a business request）
# =============================================================================

if __name__ == "__main__":
    print("=== maimai_net Protocol Self-Test ===")
    print("BASE_URL          :", BASE_URL)
    print("GetGameSettingApi :", build_api_url("GetGameSettingApi"))
    print("  textTail Segment         : 83a5d5a20b062c5c2ad817460b8f7f76")
    print("User-Agent textExample   :", build_user_agent("UserLoginApi", 12345678))

    sample = '{"userId":12345678,"token":"abc"}'
    packed = deflate_compress(sample.encode("utf-8"))
    print("deflate Head/Tail     :", packed[:2].hex(), packed[-4:].hex(),
          " Adler32 =", hex(adler32(sample.encode("utf-8"))))
    assert deflate_decompress(packed).decode("utf-8") == sample

    enc = aes_encrypt(packed)
    assert aes_decrypt(enc) == packed
    print("AES Round trip           : OK（Ciphertext", len(enc), "Bytes，16 oftimesnumber：", len(enc) % 16 == 0, "）")
    print("text")
