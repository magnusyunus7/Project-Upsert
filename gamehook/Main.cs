using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using HarmonyLib;
using MelonLoader;

// ★ MelonLoader 靠这个特性识别 mod 并调用 OnInitializeMelon。
//   缺了它只会 "Melon Assembly loaded" 但不会实例化（表现为 "N Mods loaded" 不计入）。
[assembly: MelonInfo(typeof(MaimaiNetSpy.Main), "MaimaiNetSpy", "1.0.0", "wahappy")]
[assembly: MelonGame(null, null)]
[assembly: MelonColor(255, 120, 200, 255)]

namespace MaimaiNetSpy
{
    /// <summary>
    /// MaimaiNetSpy —— hook 舞萌DX 游戏网络层，做实时拦截与落盘。
    ///
    /// 拦截点（全部依据 Assembly-CSharp 的实际签名）：
    ///   Net.NetHttpClient.AddHeader(name, value)          所有请求头
    ///   Net.NetHttpClient.AddCookie(userId)               Cookie
    ///   Net.NetHttpClient.Request(bytes, ua, method)      ★ 加密前的明文 JSON
    ///   Net.NetHttpClient.GetResponse()                   解密后的响应
    ///   Net.NetPacketUtil.GetUserAgent(query)             逻辑 API 名
    ///   Manager.GameManager.CalcSpecialNum()              playSpecial 的硬件标志位
    ///
    /// 输出：
    ///   &lt;游戏根目录&gt;/MaimaiNetSpy/YYYY-MM-DD_HHmmss.log     人类可读时间线
    ///   &lt;游戏根目录&gt;/MaimaiNetSpy/raw/*.json                每个接口的请求/响应原文
    /// </summary>
    public class Main : MelonMod
    {
        internal static MelonLogger.Instance Log;

        //: 当前请求的上下文（按线程隔离，游戏是异步回调模型）
        private static readonly object _lock = new object();

        private static string _outDir;
        private static StreamWriter _writer;

        //: 本次请求累积的头部（AddHeader 逐条调用，Request 时才真正发出）
        [ThreadStatic] private static List<KeyValuePair<string, string>> _headers;
        [ThreadStatic] private static string _cookie;
        [ThreadStatic] private static string _currentApi;
        [ThreadStatic] private static string _currentUrl;

        //: 统计
        private static int _reqCount;
        private static int _respCount;

        public override void OnInitializeMelon()
        {
            Log = LoggerInstance;

            string root = MelonLoader.Utils.MelonEnvironment.GameRootDirectory;
            _outDir = Path.Combine(root, "MaimaiNetSpy");
            Directory.CreateDirectory(_outDir);
            Directory.CreateDirectory(Path.Combine(_outDir, "raw"));

            string file = Path.Combine(_outDir,
                DateTime.Now.ToString("yyyy-MM-dd_HHmmss") + ".log");
            _writer = new StreamWriter(file, false, new UTF8Encoding(false)) { AutoFlush = true };

            Line("=".PadRight(78, '='));
            Line("  MaimaiNetSpy 已加载  —— 舞萌DX 网络层实时拦截");
            Line("  日志: " + file);
            Line("=".PadRight(78, '='));

            try
            {
                var h = new HarmonyLib.Harmony("MaimaiNetSpy");
                int n = 0;

                // ★ Request 有两个重载：Request() 与 Request(byte[], string, string)
                //   必须按参数类型精确匹配，否则会命中无参版本导致
                //   "Parameter bytes not found in method Request()"
                n += PatchBySig(h, "Net.NetHttpClient", "Create",
                                new[] { typeof(string) },
                                nameof(PreCreate), null);
                n += PatchBySig(h, "Net.NetHttpClient", "AddHeader",
                                new[] { typeof(string), typeof(string) },
                                nameof(PreAddHeader), null);
                n += PatchBySig(h, "Net.NetHttpClient", "AddCookie",
                                new[] { typeof(ulong) },
                                nameof(PreAddCookie), null);
                n += PatchBySig(h, "Net.NetHttpClient", "Request",
                                new[] { typeof(byte[]), typeof(string), typeof(string) },
                                nameof(PreRequest), nameof(PostRequestDumpHeaders));
                n += PatchBySig(h, "Net.NetHttpClient", "GetResponse",
                                Type.EmptyTypes,
                                null, nameof(PostGetResponse));
                n += PatchBySig(h, "Net.NetPacketUtil", "GetUserAgent",
                                new[] { AccessTools.TypeByName("Net.INetQuery") },
                                null, nameof(PostGetUserAgent));
                n += PatchBySig(h, "Manager.GameManager", "CalcSpecialNum",
                                Type.EmptyTypes,
                                null, nameof(PostCalcSpecialNum));
                n += PatchBySig(h, "Net.NetHttpClient", "SetError",
                                new[] { typeof(System.Net.WebExceptionStatus), typeof(string),
                                        typeof(int), typeof(System.Net.HttpWebResponse) },
                                nameof(PreSetError), null);

                Line("  已挂载 " + n + " 个 hook");
            }
            catch (Exception e)
            {
                Line("  !! hook 挂载失败: " + e);
            }
            Line("");
        }

        public override void OnDeinitializeMelon()
        {
            try { _writer?.Flush(); _writer?.Dispose(); } catch { }
        }

        // ------------------------------------------------------------------
        // hook 挂载工具
        // ------------------------------------------------------------------

        /// <summary>
        /// 按**参数类型**精确挂载 hook。
        ///
        /// ★ 为什么必须精确匹配：NetHttpClient.Request 有两个重载
        ///     Boolean Request()                              —— 只发请求（无体）
        ///     Boolean Request(Byte[] bytes, String ua, String m) —— 带请求体
        ///   用 AccessTools.Method(t, "Request") 会命中前者，
        ///   导致 prefix 里的 bytes 参数对不上而抛
        ///   "Parameter bytes not found in method Request()"。
        /// </summary>
        private static int PatchBySig(HarmonyLib.Harmony h, string typeName, string methodName,
                                      Type[] paramTypes, string pre, string post)
        {
            var t = AccessTools.TypeByName(typeName);
            if (t == null) { Line("  [skip] 类型未找到: " + typeName); return 0; }
            if (paramTypes == null || paramTypes.Any(x => x == null))
            { Line("  [skip] 参数类型解析失败: " + typeName + "." + methodName); return 0; }

            var m = AccessTools.Method(t, methodName, paramTypes);
            if (m == null)
            {
                Line("  [skip] 方法未找到: " + typeName + "." + methodName
                     + "(" + string.Join(", ", Array.ConvertAll(paramTypes, x => x.Name)) + ")");
                return 0;
            }

            HarmonyMethod preM = pre == null ? null
                : new HarmonyMethod(typeof(Main).GetMethod(pre, BindingFlags.Static | BindingFlags.NonPublic));
            HarmonyMethod postM = post == null ? null
                : new HarmonyMethod(typeof(Main).GetMethod(post, BindingFlags.Static | BindingFlags.NonPublic));

            try
            {
                h.Patch(m, preM, postM);
                Line("  [ok] " + typeName + "." + methodName
                     + "(" + string.Join(", ", Array.ConvertAll(paramTypes, x => x.Name)) + ")");
                return 1;
            }
            catch (Exception e)
            {
                Line("  [fail] " + typeName + "." + methodName + " -> " + e.Message);
                return 0;
            }
        }

        // ------------------------------------------------------------------
        // Create —— 捕获完整 URL（NetHttpClient.Create(url)）
        // ------------------------------------------------------------------

        private static void PreCreate(string url)
        {
            _currentUrl = url;
        }

        // ------------------------------------------------------------------
        // AddHeader —— 收集请求头
        // ------------------------------------------------------------------

        private static void PreAddHeader(string name, string value)
        {
            if (_headers == null) _headers = new List<KeyValuePair<string, string>>();
            _headers.Add(new KeyValuePair<string, string>(name, value));
        }

        private static void PostAddHeader()
        {
            // 不在这里输出：AddHeader 会被多次调用，等 Request 时统一打印
        }

        // ------------------------------------------------------------------
        // AddCookie —— 记录 Cookie
        // ------------------------------------------------------------------

        private static void PreAddCookie(ulong userId)
        {
            _cookie = "userId=" + userId;
        }

        // ------------------------------------------------------------------
        // Request —— ★ 核心：加密前的明文 JSON 在这里
        // ------------------------------------------------------------------

        private static void PreRequest(byte[] bytes, string userAgent, string method)
        {
            _reqCount++;
            string plain = null;
            try
            {
                if (bytes != null && bytes.Length > 0)
                    plain = Encoding.UTF8.GetString(bytes);
            }
            catch { }

            var sb = new StringBuilder();
            sb.AppendLine();
            sb.AppendLine("+" + new string('-', 76));
            sb.AppendLine("| [" + _reqCount + "] >>> 请求  "
                          + DateTime.Now.ToString("HH:mm:ss.fff"));
            sb.AppendLine("+" + new string('-', 76));
            sb.AppendLine("| API          : " + (_currentApi ?? "(unknown)"));
            if (!string.IsNullOrEmpty(_currentUrl))
                sb.AppendLine("| URL          : " + _currentUrl);
            sb.AppendLine("| User-Agent   : " + userAgent);
            sb.AppendLine("| Method       : " + method);
            sb.AppendLine("| Cookie       : " + (_cookie ?? "(none)"));
            sb.AppendLine("| 明文长度     : " + (bytes == null ? 0 : bytes.Length) + " 字节");

            if (_headers != null && _headers.Count > 0)
            {
                sb.AppendLine("| ---- 请求头（AddHeader 收集）----");
                foreach (var kv in _headers)
                    sb.AppendLine("|   " + kv.Key + ": " + kv.Value);
            }
            else
            {
                sb.AppendLine("| ---- 请求头: (无 AddHeader 调用) ----");
            }

            if (plain != null)
            {
                sb.AppendLine("| ---- 请求体（加密前明文）----");
                foreach (var ln in Wrap(plain, 150))
                    sb.AppendLine("| " + ln);
            }
            Line(sb.ToString());

            // 落盘原始明文
            try
            {
                string safe = Sanitize(_currentApi ?? ("req" + _reqCount));
                File.WriteAllText(
                    Path.Combine(_outDir, "raw", _reqCount.ToString("D3") + "_" + safe + "_request.json"),
                    plain ?? "", new UTF8Encoding(false));
            }
            catch { }

            // 清空累积状态（本次请求已消费）
            _headers = null;
        }

        private static void PostRequest()
        {
            // 状态清理交给下一次 PreRequest
        }

        // ------------------------------------------------------------------
        // ★ 真实 HTTP 请求头 dump
        // ------------------------------------------------------------------
        //
        // 为什么必须用 postfix：
        //   PreRequest 跑在 Request() 方法体**之前**，那时
        //   Method / ContentType / UserAgent / Content-Encoding 都还没设置。
        //   只有 postfix 才能看到最终真正要发出去的头（含框架自带的）。
        //
        // 目的：把真机的**完整请求头**抓下来，和纯 Python 脚本发的做逐字节对比。
        //       （排查「报文一致但服务端 returnCode=0」这类问题）
        private static void PostRequestDumpHeaders(Net.NetHttpClient __instance)
        {
            try
            {
                var fld = AccessTools.Field(typeof(Net.NetHttpClient), "_request");
                var wr = (fld == null ? null : fld.GetValue(__instance)) as System.Net.HttpWebRequest;
                if (wr == null) { Line("| [头 dump] _request 取不到"); return; }

                var sb = new StringBuilder();
                sb.AppendLine("| ---- ★ 真实 HTTP 请求头（HttpWebRequest，含框架自带）----");
                sb.AppendLine("|   [Method]        : " + wr.Method);
                sb.AppendLine("|   [ContentType]   : " + wr.ContentType);
                sb.AppendLine("|   [UserAgent]     : " + wr.UserAgent);
                sb.AppendLine("|   [ContentLength] : " + wr.ContentLength);
                sb.AppendLine("|   [KeepAlive]     : " + wr.KeepAlive);
                sb.AppendLine("|   [Expect]        : " + wr.Expect);
                sb.AppendLine("|   [AutomaticDecompression] : " + wr.AutomaticDecompression);
                sb.AppendLine("|   [AllowAutoRedirect]      : " + wr.AllowAutoRedirect);
                try
                {
                    foreach (string k in wr.Headers.AllKeys)
                        sb.AppendLine("|   " + k + ": " + wr.Headers[k]);
                }
                catch (Exception e2) { sb.AppendLine("|   [Headers 枚举失败] " + e2.Message); }
                try
                {
                    sb.AppendLine("|   [Cookie 头] : "
                        + (wr.CookieContainer == null ? "(null container)"
                           : "[" + wr.CookieContainer.GetCookieHeader(wr.RequestUri) + "]"));
                }
                catch (Exception e3) { sb.AppendLine("|   [Cookie 取失败] " + e3.Message); }
                Line(sb.ToString());
            }
            catch (Exception e)
            {
                Line("| [头 dump 失败] " + e);
            }
        }

        // ------------------------------------------------------------------
        // GetResponse —— 解密后的响应
        // ------------------------------------------------------------------

        private static void PostGetResponse(Net.NetHttpClient __instance, ref MemoryStream __result)
        {
            _respCount++;

            // ★ 响应头 dump（尤其看 UserLoginApi 的 Set-Cookie: JSESSIONID）
            try
            {
                var fldR = AccessTools.Field(typeof(Net.NetHttpClient), "_response");
                var resp = (fldR == null ? null : fldR.GetValue(__instance)) as System.Net.HttpWebResponse;
                if (resp != null)
                {
                    var sh = new StringBuilder();
                    sh.AppendLine("| ---- ★ 真实 HTTP 响应头 ----");
                    sh.AppendLine("|   [StatusCode] : " + (int)resp.StatusCode);
                    try
                    {
                        foreach (string k in resp.Headers.AllKeys)
                            sh.AppendLine("|   " + k + ": " + resp.Headers[k]);
                    }
                    catch (Exception e4) { sh.AppendLine("|   [响应头枚举失败] " + e4.Message); }
                    Line(sh.ToString());
                }
            }
            catch (Exception e5) { Line("| [响应头 dump 失败] " + e5.Message); }

            try
            {
                if (__result == null) return;
                long pos = __result.Position;
                __result.Position = 0;
                byte[] buf = new byte[__result.Length];
                int read = __result.Read(buf, 0, buf.Length);
                __result.Position = pos;

                string txt = Encoding.UTF8.GetString(buf, 0, read);

                var sb = new StringBuilder();
                sb.AppendLine("| [" + _respCount + "] <<< 响应  "
                              + DateTime.Now.ToString("HH:mm:ss.fff")
                              + "   (" + read + " 字节)");
                foreach (var ln in Wrap(txt, 150))
                    sb.AppendLine("| " + ln);
                Line(sb.ToString());

                string safe = Sanitize(_currentApi ?? ("resp" + _respCount));
                File.WriteAllText(
                    Path.Combine(_outDir, "raw", _respCount.ToString("D3") + "_" + safe + "_response.json"),
                    txt, new UTF8Encoding(false));
            }
            catch (Exception e)
            {
                Line("| [响应解析失败] " + e.Message);
            }
        }

        // ------------------------------------------------------------------
        // GetUserAgent —— 从 UA 反推 API 名；同时记录 URL
        // ------------------------------------------------------------------

        private static void PostGetUserAgent(Net.INetQuery query, ref string __result)
        {
            try
            {
                _currentApi = query?.Api;
                // UA 形如 "<md5>#<userId>"
                Line("  [API] " + _currentApi + "   UA=" + __result);
            }
            catch { }
        }

        // ------------------------------------------------------------------
        // CalcSpecialNum —— playSpecial 的硬件标志位
        // ------------------------------------------------------------------

        private static void PostCalcSpecialNum(ref int __result)
        {
            Line("  [CalcSpecialNum] = " + __result
                 + "   (SpecialAP=" + SafeBool(() => Manager.GameManager.SpecialAP)
                 + "  IsFreedomMode=" + SafeBool(() => Manager.GameManager.IsFreedomMode)
                 + ")");
        }

        private static string SafeBool(Func<bool> f)
        {
            try { return f().ToString(); } catch { return "?"; }
        }

        // ------------------------------------------------------------------
        // SetError —— 记录网络层错误（含 HTTP 状态码）
        // ------------------------------------------------------------------

        private static void PreSetError(System.Net.WebExceptionStatus status, string error,
                                        int state, System.Net.HttpWebResponse response)
        {
            Line("  [NetError] status=" + status + " state=" + state
                 + " error=" + error
                 + (response != null ? (" http=" + (int)response.StatusCode) : ""));
        }

        // ------------------------------------------------------------------
        // 工具
        // ------------------------------------------------------------------

        private static string Sanitize(string s)
        {
            var sb = new StringBuilder();
            foreach (char c in s)
                sb.Append(char.IsLetterOrDigit(c) || c == '_' || c == '-' ? c : '_');
            return sb.ToString();
        }

        private static IEnumerable<string> Wrap(string s, int width)
        {
            if (s == null) yield break;
            for (int i = 0; i < s.Length; i += width)
                yield return s.Substring(i, Math.Min(width, s.Length - i));
        }

        internal static void Line(string s)
        {
            lock (_lock)
            {
                try { _writer?.WriteLine(s); } catch { }
            }
        }
    }
}
