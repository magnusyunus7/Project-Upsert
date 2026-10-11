using System;
using System. Collections. Generic;
using System. IO;
using System. Linq;
using System. Reflection;
using System. Text;
using HarmonyLib;
using MelonLoader;

// - MelonLoader this Piece mod and call OnInitializeMelon.
//  OnlyMeetings "Melon Assembly loaded" but will not be instantiated(currentfor "N Mods loaded" Do not count).
[assembly: MelonInfo(typeof(MaimaiNetSpy. Main), "MaimaiNetSpy", "1.0.0", "wahappy")]
[assembly: MelonGame(null, null)]
[assembly: MelonColor(255, 120, 200, 255)]

namespace MaimaiNetSpy
{
  /// <summary>
  /// MaimaiNetSpy — hook DX network, Do real-time interception and data logging.
  ///
  /// (All by Assembly-CSharp of actual First name):
  ///  Net. NetHttpClient. AddHeader(name, value)     All Request Headers
  ///  Net. NetHttpClient. AddCookie(userId)        Cookie
  ///  Net. NetHttpClient. Request(bytes, ua, method)   - Pre-encrypted clear JSON
  ///  Net. NetHttpClient. GetResponse()          decrypt After of Response
  ///  Net. NetPacketUtil. GetUserAgent(query)       API First name
  ///  Manager. GameManager. CalcSpecialNum()       play Special of Bit
  ///
  /// out:
  ///  &lt; text&gt;/MaimaiNetSpy/YYYY-MM-DD_HHmmss. log   Human Readable Timeline
  ///  &lt; text&gt;/MaimaiNetSpy/raw/*. json        eachPieceinterfaceofrequest/Response original
  /// </summary>
  public class Main: MelonMod
  {
    internal static MelonLogger. Instance Log;

    //: Con of the current request(press, istimescall)
    private static readonly object _lock = new object();

    private static string _outDir;
    private static StreamWriter _writer;

    //: requestofHead(AddHeader itemcalluse, Request timeonlycurrenthairout)
    [ThreadStatic] private static List<KeyValuePair<string, string>> _headers;
    [ThreadStatic] private static string _cookie;
    [ThreadStatic] private static string _currentApi;
    [ThreadStatic] private static string _currentUrl;

    //: systemcount
    private static int _reqCount;
    private static int _respCount;

    public override void OnInitializeMelon()
    {
      Log = LoggerInstance;

      string root = MelonLoader. Utils. MelonEnvironment. GameRootDirectory;
      _outDir = Path. Combine(root, "MaimaiNetSpy");
      Directory. CreateDirectory(_outDir);
      Directory. CreateDirectory(Path. Combine(_outDir, "raw"));

      string file = Path. Combine(_outDir,
        DateTime. Now. ToString("yyyy-MM-dd_HHmmss") + ". log");
      _writer = new StreamWriter(file, false, new UTF8Encoding(false)) { AutoFlush = true };

      Line("=". PadRight(78, '='));
      Line(" MaimaiNetSpy Loaded — DX network time");
      Line(" log: " + file);
      Line("=". PadRight(78, '='));

      try
      {
        var h = new HarmonyLib. Harmony("MaimaiNetSpy");
        int n = 0;

        // - Request hasTwo: Request() And Request(byte[], string, string)
        //  Must match exactly by parameter type, Otherwise, it will hit the unparametric version.
        //  "Parameter bytes not found in method Request()"
        n += PatchBySig(h, "Net. NetHttpClient", "Create",
                new[] { typeof(string) },
                nameof(PreCreate), null);
        n += PatchBySig(h, "Net. NetHttpClient", "AddHeader",
                new[] { typeof(string), typeof(string) },
                nameof(PreAddHeader), null);
        n += PatchBySig(h, "Net. NetHttpClient", "AddCookie",
                new[] { typeof(ulong) },
                nameof(PreAddCookie), null);
        n += PatchBySig(h, "Net. NetHttpClient", "Request",
                new[] { typeof(byte[]), typeof(string), typeof(string) },
                nameof(PreRequest), nameof(PostRequestDumpHeaders));
        n += PatchBySig(h, "Net. NetHttpClient", "GetResponse",
                Type. EmptyTypes,
                null, nameof(PostGetResponse));
        n += PatchBySig(h, "Net. NetPacketUtil", "GetUserAgent",
                new[] { AccessTools. TypeByName("Net. INetQuery") },
                null, nameof(PostGetUserAgent));
        n += PatchBySig(h, "Manager. GameManager", "CalcSpecialNum",
                Type. EmptyTypes,
                null, nameof(PostCalcSpecialNum));
        n += PatchBySig(h, "Net. NetHttpClient", "SetError",
                new[] { typeof(System. Net. WebExceptionStatus), typeof(string),
                    typeof(int), typeof(System. Net. HttpWebResponse) },
                nameof(PreSetError), null);

        Line(" Mounted " + n + " Piece hook");
      }
      catch (Exception e)
      {
        Line("!! hook Failed: " + e);
      }
      Line("");
    }

    public override void OnDeinitializeMelon()
    {
      try { _writer?. Flush(); _writer?. Dispose(); } catch { }
    }

    // ------------------------------------------------------------------
    // hook Tools
    // ------------------------------------------------------------------

    /// <summary>
    /// press **Parameter Type** hook.
    ///
    /// - Why it's important to match exactly: NetHttpClient. Request hasTwo
    ///   Boolean Request()               — Request only(no)
    ///   Boolean Request(Byte[] bytes, String ua, String m) — With request body
    ///  use AccessTools. Method(t, "Request") will hit the former,
    ///  lead to prefix inof bytes Parameters are thrown at the top
    ///  "Parameter bytes not found in method Request()".
    /// </summary>
    private static int PatchBySig(HarmonyLib. Harmony h, string typeName, string methodName,
                   Type[] paramTypes, string pre, string post)
    {
      var t = AccessTools. TypeByName(typeName);
      if (t == null) { Line(" [skip] not found: " + typeName); return 0; }
      if (paramTypes == null || paramTypes. Any(x => x == null))
      { Line(" [skip] Parameter type parsing failed: " + typeName + "." + methodName); return 0; }

      var m = AccessTools. Method(t, methodName, paramTypes);
      if (m == null)
      {
        Line(" [skip] not found: " + typeName + "." + methodName
           + "(" + string. Join(", ", Array. ConvertAll(paramTypes, x => x. Name)) + ")");
        return 0;
      }

      HarmonyMethod preM = pre == null? null
: new HarmonyMethod(typeof(Main). GetMethod(pre, BindingFlags. Static | BindingFlags. NonPublic));
      HarmonyMethod postM = post == null? null
: new HarmonyMethod(typeof(Main). GetMethod(post, BindingFlags. Static | BindingFlags. NonPublic));

      try
      {
        h. Patch(m, preM, postM);
        Line(" [ok] " + typeName + "." + methodName
           + "(" + string. Join(", ", Array. ConvertAll(paramTypes, x => x. Name)) + ")");
        return 1;
      }
      catch (Exception e)
      {
        Line(" [fail] " + typeName + "." + methodName + " -> " + e. Message);
        return 0;
      }
    }

    // ------------------------------------------------------------------
    // Create — get full URL (NetHttpClient. Create(url))
    // ------------------------------------------------------------------

    private static void PreCreate(string url)
    {
      _currentUrl = url;
    }

    // ------------------------------------------------------------------
    // AddHeader — receive request header
    // ------------------------------------------------------------------

    private static void PreAddHeader(string name, string value)
    {
      if (_headers == null) _headers = new List<KeyValuePair<string, string>>();
      _headers. Add(new KeyValuePair<string, string>(name, value));
    }

    private static void PostAddHeader()
    {
      // Don't output here: AddHeader will be called multiple times, etc Request timesystemOne
    }

    // ------------------------------------------------------------------
    // AddCookie — record Cookie
    // ------------------------------------------------------------------

    private static void PreAddCookie(ulong userId)
    {
      _cookie = "userId=" + userId;
    }

    // ------------------------------------------------------------------
    // Request — Pre-encrypted clear JSON here
    // ------------------------------------------------------------------

    private static void PreRequest(byte[] bytes, string userAgent, string method)
    {
      _reqCount++;
      string plain = null;
      try
      {
        if (bytes!= null && bytes. Length > 0)
          plain = Encoding. UTF8. GetString(bytes);
      }
      catch { }

      var sb = new StringBuilder();
      sb. AppendLine();
      sb. AppendLine("+" + new string('-', 76));
      sb. AppendLine("| [" + _reqCount + "] >>> request "
             + DateTime. Now. ToString("HH: mm: ss. fff"));
      sb. AppendLine("+" + new string('-', 76));
      sb. AppendLine("| API: " + (_currentApi?? "(unknown)"));
      if (! string. IsNullOrEmpty(_currentUrl))
        sb. AppendLine("| URL: " + _currentUrl);
      sb. AppendLine("| User-Agent: " + userAgent);
      sb. AppendLine("| Method: " + method);
      sb. AppendLine("| Cookie: " + (_cookie?? "(none)"));
      sb. AppendLine("| length: " + (bytes == null? 0: bytes. Length) + " Bytes");

      if (_headers!= null && _headers. Count > 0)
      {
        sb. AppendLine("| ---- request header (AddHeader receive) ----");
        foreach (var kv in _headers)
          sb. AppendLine("|  " + kv. Key + ": " + kv. Value);
      }
      else
      {
        sb. AppendLine("| ---- request header: (no AddHeader calluse) ----");
      }

      if (plain!= null)
      {
        sb. AppendLine("| ---- request body (Pre-encrypted clear) ----");
        foreach (var ln in Wrap(plain, 150))
          sb. AppendLine("| " + ln);
      }
      Line(sb. ToString());

      // fallOriginal
      try
      {
        string safe = Sanitize(_currentApi?? ("req" + _reqCount));
        File. WriteAll(
          Path. Combine(_outDir, "raw", _reqCount. ToString("D3") + "_" + safe + "_request. json"),
          plain?? "", new UTF8Encoding(false));
      }
      catch { }

      // empty(requestAlready)
      _headers = null;
    }

    private static void PostRequest()
    {
      // Hand overDownOnce PreRequest
    }

    // ------------------------------------------------------------------
    // - real HTTP request header dump
    // ------------------------------------------------------------------
    //
    // Why do I have to use postfix:
    //  PreRequest at Request()**Before**, thattime
    //  Method / ContentType / UserAgent / Content-Encoding all.
    //  Only postfix onlycantoFinalcurrentmustSend outofHead(Includes frame-built).
    //
    // of: putreal machineof**Full request headers**Down, and pure Python scripthairofBytesYes. text.
    //    (check"packetMatchButserver returnCode=0"this)
    private static void PostRequestDumpHeaders(Net. NetHttpClient __instance)
    {
      try
      {
        var fld = AccessTools. Field(typeof(Net. NetHttpClient), "_request");
        var wr = (fld == null? null: fld. GetValue(__instance)) as System. Net. HttpWebRequest;
        if (wr == null) { Line("| [Head dump] _request Unable to retrieve"); return; }

        var sb = new StringBuilder();
        sb. AppendLine("| ---- - real HTTP request header(HttpWebRequest, Includes Frame Bring Your Own)----");
        sb. AppendLine("|  [Method]: " + wr. Method);
        sb. AppendLine("|  [ContentType]: " + wr. ContentType);
        sb. AppendLine("|  [UserAgent]: " + wr. UserAgent);
        sb. AppendLine("|  [ContentLength]: " + wr. ContentLength);
        sb. AppendLine("|  [KeepAlive]: " + wr. KeepAlive);
        sb. AppendLine("|  [Expect]: " + wr. Expect);
        sb. AppendLine("|  [AutomaticDecompression]: " + wr. AutomaticDecompression);
        sb. AppendLine("|  [AllowAutoRedirect]: " + wr. AllowAutoRedirect);
        try
        {
          foreach (string k in wr. Headers. AllKeys)
            sb. AppendLine("|  " + k + ": " + wr. Headers[k]);
        }
        catch (Exception e2) { sb. AppendLine("|  [Headers Failed] " + e2. Message); }
        try
        {
          sb. AppendLine("|  [Cookie Head]: "
            + (wr. CookieContainer == null? "(null container)"
: "[" + wr. CookieContainer. GetCookieHeader(wr. RequestUri) + "]"));
        }
        catch (Exception e3) { sb. AppendLine("|  [Cookie Fetch failed] " + e3. Message); }
        Line(sb. ToString());
      }
      catch (Exception e)
      {
        Line("| [Head dump Failed] " + e);
      }
    }

    // ------------------------------------------------------------------
    // GetResponse — decrypt After of Response
    // ------------------------------------------------------------------

    private static void PostGetResponse(Net. NetHttpClient __instance, ref MemoryStream __result)
    {
      _respCount++;

      // - Response header dump(Especially looking at UserLoginApi of Set-Cookie: JSESSIONID)
      try
      {
        var fldR = AccessTools. Field(typeof(Net. NetHttpClient), "_response");
        var resp = (fldR == null? null: fldR. GetValue(__instance)) as System. Net. HttpWebResponse;
        if (resp!= null)
        {
          var sh = new StringBuilder();
          sh. AppendLine("| ---- - real HTTP Response header ----");
          sh. AppendLine("|  [StatusCode]: " + (int)resp. StatusCode);
          try
          {
            foreach (string k in resp. Headers. AllKeys)
              sh. AppendLine("|  " + k + ": " + resp. Headers[k]);
          }
          catch (Exception e4) { sh. AppendLine("|  [Response header enumeration failed] " + e4. Message); }
          Line(sh. ToString());
        }
      }
      catch (Exception e5) { Line("| [Response header dump Failed] " + e5. Message); }

      try
      {
        if (__result == null) return;
        long pos = __result. Position;
        __result. Position = 0;
        byte[] buf = new byte[__result. Length];
        int read = __result. Read(buf, 0, buf. Length);
        __result. Position = pos;

        string txt = Encoding. UTF8. GetString(buf, 0, read);

        var sb = new StringBuilder();
        sb. AppendLine("| [" + _respCount + "] <<< Response "
               + DateTime. Now. ToString("HH: mm: ss. fff")
               + "  (" + read + " Bytes)");
        foreach (var ln in Wrap(txt, 150))
          sb. AppendLine("| " + ln);
        Line(sb. ToString());

        string safe = Sanitize(_currentApi?? ("resp" + _respCount));
        File. WriteAll(
          Path. Combine(_outDir, "raw", _respCount. ToString("D3") + "_" + safe + "_response. json"),
          txt, new UTF8Encoding(false));
      }
      catch (Exception e)
      {
        Line("| [Response parsing failed] " + e. Message);
      }
    }

    // ------------------------------------------------------------------
    // GetUserAgent — From UA Reverse API First name; Record at the same time URL
    // ------------------------------------------------------------------

    private static void PostGetUserAgent(Net. INetQuery query, ref string __result)
    {
      try
      {
        _currentApi = query?. Api;
        // UA Shape like "<md5>#<userId>"
        Line(" [API] " + _currentApi + "  UA=" + __result);
      }
      catch { }
    }

    // ------------------------------------------------------------------
    // CalcSpecialNum — playSpecial ofBit
    // ------------------------------------------------------------------

    private static void PostCalcSpecialNum(ref int __result)
    {
      Line(" [CalcSpecialNum] = " + __result
         + "  (SpecialAP=" + SafeBool(() => Manager. GameManager. SpecialAP)
         + " IsFreedomMode=" + SafeBool(() => Manager. GameManager. IsFreedomMode)
         + ")");
    }

    private static string SafeBool(Func<bool> f)
    {
      try { return f(). ToString(); } catch { return "?"; }
    }

    // ------------------------------------------------------------------
    // SetError — record network error (Contains HTTP)
    // ------------------------------------------------------------------

    private static void PreSetError(System. Net. WebExceptionStatus status, string error,
                    int state, System. Net. HttpWebResponse response)
    {
      Line(" [NetError] status=" + status + " state=" + state
         + " error=" + error
         + (response!= null? (" http=" + (int)response. StatusCode): ""));
    }

    // ------------------------------------------------------------------
    // Tools
    // ------------------------------------------------------------------

    private static string Sanitize(string s)
    {
      var sb = new StringBuilder();
      foreach (char c in s)
        sb. Append(char. IsLetterOrDigit(c) || c == '_' || c == '-'? c: '_');
      return sb. ToString();
    }

    private static IEnumerable<string> Wrap(string s, int width)
    {
      if (s == null) yield break;
      for (int i = 0; i < s. Length; i += width)
        yield return s. Substring(i, Math. Min(width, s. Length - i));
    }

    internal static void Line(string s)
    {
      lock (_lock)
      {
        try { _writer?. WriteLine(s); } catch { }
      }
    }
  }
}
