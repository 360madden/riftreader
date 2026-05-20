using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

JsonSerializerOptions JsonOptions = new()
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    WriteIndented = false,
};

try
{
    Options options = Options.Parse(args);
    object result = options.Command switch
    {
        "inspect" => WindowOperations.Inspect(options),
        "resize" => WindowOperations.Resize(options),
        "click" => WindowOperations.Click(options),
        _ => throw new KnownBlockerException($"Unsupported command '{options.Command}'."),
    };

    Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
    return 0;
}
catch (KnownBlockerException ex)
{
    Console.WriteLine(JsonSerializer.Serialize(new ToolError(false, "blocked", ex.Message), JsonOptions));
    return 2;
}
catch (Exception ex)
{
    Console.WriteLine(JsonSerializer.Serialize(new ToolError(false, "failed", ex.Message, ex.GetType().Name), JsonOptions));
    return 1;
}

sealed record Options(
    string Command,
    IntPtr Hwnd,
    int? ExpectedPid,
    string? ExpectedProcessName,
    string? ExpectedTitleContains,
    int? ClientWidth,
    int? ClientHeight,
    int? ClientX,
    int? ClientY,
    int CursorSettleMilliseconds,
    int ClickDelayMilliseconds,
    bool DryRun)
{
    public static Options Parse(string[] args)
    {
        if (args.Length == 0)
        {
            throw new KnownBlockerException(Usage);
        }

        string command = args[0].Trim().ToLowerInvariant();
        if (command is not ("inspect" or "resize" or "click"))
        {
            throw new KnownBlockerException($"Unknown command '{args[0]}'. {Usage}");
        }

        IntPtr hwnd = IntPtr.Zero;
        int? expectedPid = null;
        string? expectedProcessName = null;
        string? expectedTitleContains = null;
        int? clientWidth = null;
        int? clientHeight = null;
        int? clientX = null;
        int? clientY = null;
        int cursorSettleMilliseconds = 30;
        int clickDelayMilliseconds = 50;
        bool dryRun = false;

        for (int i = 1; i < args.Length; i++)
        {
            string arg = args[i];
            switch (arg)
            {
                case "--hwnd":
                case "--window-handle":
                    hwnd = ParseHwnd(RequireValue(args, ref i, arg));
                    break;
                case "--expected-pid":
                case "--pid":
                    expectedPid = ParsePositiveInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--expected-process-name":
                case "--process-name":
                    expectedProcessName = Path.GetFileNameWithoutExtension(RequireValue(args, ref i, arg));
                    break;
                case "--expected-title-contains":
                case "--title-contains":
                    expectedTitleContains = RequireValue(args, ref i, arg);
                    break;
                case "--client-width":
                    clientWidth = ParsePositiveInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--client-height":
                    clientHeight = ParsePositiveInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--client-x":
                    clientX = ParseNonNegativeInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--client-y":
                    clientY = ParseNonNegativeInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--cursor-settle-ms":
                    cursorSettleMilliseconds = ParseNonNegativeInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--click-delay-ms":
                    clickDelayMilliseconds = ParseNonNegativeInt(RequireValue(args, ref i, arg), arg);
                    break;
                case "--dry-run":
                    dryRun = ParseBool(RequireValue(args, ref i, arg), arg);
                    break;
                case "--json":
                    break;
                case "--help":
                case "-h":
                case "/?":
                    throw new KnownBlockerException(Usage);
                default:
                    throw new KnownBlockerException($"Unknown argument '{arg}'. {Usage}");
            }
        }

        if (hwnd == IntPtr.Zero)
        {
            throw new KnownBlockerException("--hwnd is required and must be non-zero.");
        }

        if (command == "resize")
        {
            if (clientWidth is null || clientHeight is null)
            {
                throw new KnownBlockerException("resize requires --client-width and --client-height.");
            }
        }

        if (command == "click")
        {
            if (clientX is null || clientY is null)
            {
                throw new KnownBlockerException("click requires --client-x and --client-y.");
            }
        }

        return new Options(
            command,
            hwnd,
            expectedPid,
            expectedProcessName,
            expectedTitleContains,
            clientWidth,
            clientHeight,
            clientX,
            clientY,
            Math.Min(cursorSettleMilliseconds, 1000),
            Math.Min(clickDelayMilliseconds, 1000),
            dryRun);
    }

    public static string Usage => "Usage: RiftReader.WindowTools inspect --hwnd <0xHWND> [--expected-pid <pid>] [--expected-process-name <name>] [--expected-title-contains <text>] [--json]\n       RiftReader.WindowTools resize --hwnd <0xHWND> --client-width <px> --client-height <px> [--dry-run true|false] [expected target options] [--json]\n       RiftReader.WindowTools click --hwnd <0xHWND> --client-x <px> --client-y <px> [--cursor-settle-ms <ms>] [--click-delay-ms <ms>] [--dry-run true|false] [expected target options] [--json]";

    private static string RequireValue(string[] args, ref int index, string name)
    {
        if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
        {
            throw new KnownBlockerException($"{name} requires a value.");
        }

        index++;
        return args[index];
    }

    private static int ParsePositiveInt(string value, string name)
    {
        if (!int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed) || parsed <= 0)
        {
            throw new KnownBlockerException($"{name} must be a positive integer.");
        }

        return parsed;
    }

    private static int ParseNonNegativeInt(string value, string name)
    {
        if (!int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed) || parsed < 0)
        {
            throw new KnownBlockerException($"{name} must be a non-negative integer.");
        }

        return parsed;
    }

    private static bool ParseBool(string value, string name)
    {
        return value.Trim().ToLowerInvariant() switch
        {
            "1" or "true" or "yes" or "on" => true,
            "0" or "false" or "no" or "off" => false,
            _ => throw new KnownBlockerException($"{name} must be true or false."),
        };
    }

    private static IntPtr ParseHwnd(string value)
    {
        string trimmed = value.Trim();
        bool isHex = trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase);
        string numeric = isHex ? trimmed[2..] : trimmed;
        NumberStyles style = isHex ? NumberStyles.AllowHexSpecifier : NumberStyles.Integer;
        if (!long.TryParse(numeric, style, CultureInfo.InvariantCulture, out long parsed) || parsed <= 0)
        {
            throw new KnownBlockerException("--hwnd must be a positive window handle, for example 0xC0994.");
        }

        return new IntPtr(parsed);
    }
}

static class WindowOperations
{
    private const uint SWP_NOZORDER = 0x0004;
    private const uint SWP_NOACTIVATE = 0x0010;
    private const uint SWP_NOOWNERZORDER = 0x0200;
    private const int INPUT_MOUSE = 0;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;

    public static WindowSnapshot Inspect(Options options)
    {
        WindowSnapshot snapshot = GetSnapshot(options.Hwnd);
        AssertMatches(options, snapshot);
        return snapshot;
    }

    public static ResizeResult Resize(Options options)
    {
        WindowSnapshot before = Inspect(options);
        int targetClientWidth = options.ClientWidth ?? throw new KnownBlockerException("resize requires --client-width.");
        int targetClientHeight = options.ClientHeight ?? throw new KnownBlockerException("resize requires --client-height.");

        if (targetClientWidth <= 0 || targetClientHeight <= 0)
        {
            throw new KnownBlockerException("Client width and height must be positive.");
        }

        if (before.IsMinimized && !options.DryRun)
        {
            throw new KnownBlockerException("Cannot resize a minimized window. Restore/focus it first or use --dry-run true.");
        }

        int borderWidth = before.WindowRect.Width - before.ClientRect.Width;
        int borderHeight = before.WindowRect.Height - before.ClientRect.Height;
        if (borderWidth < 0 || borderHeight < 0)
        {
            throw new KnownBlockerException("Window/client rectangle mismatch prevents safe resize math.");
        }

        int targetWindowWidth = targetClientWidth + borderWidth;
        int targetWindowHeight = targetClientHeight + borderHeight;
        RectObject requestedWindow = new(before.WindowRect.Left, before.WindowRect.Top, before.WindowRect.Left + targetWindowWidth, before.WindowRect.Top + targetWindowHeight);
        SizeObject requestedClientSize = new(targetClientWidth, targetClientHeight);
        SizeObject border = new(borderWidth, borderHeight);

        if (options.DryRun)
        {
            return new ResizeResult(true, false, false, before, null, requestedClientSize, requestedWindow, border);
        }

        uint flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER;
        if (!NativeMethods.SetWindowPos(options.Hwnd, IntPtr.Zero, before.WindowRect.Left, before.WindowRect.Top, targetWindowWidth, targetWindowHeight, flags))
        {
            throw new InvalidOperationException($"SetWindowPos failed. {NativeMethods.GetLastErrorMessage()}");
        }

        Thread.Sleep(300);
        WindowSnapshot after = Inspect(options);
        bool resizeOk = after.ClientRect.Width == targetClientWidth && after.ClientRect.Height == targetClientHeight;
        return new ResizeResult(false, true, resizeOk, before, after, requestedClientSize, requestedWindow, border);
    }

    public static ClickResult Click(Options options)
    {
        WindowSnapshot before = Inspect(options);
        if (!options.DryRun && !before.IsForeground)
        {
            throw new KnownBlockerException("Refusing click because the bound game window is not the foreground window. Focus it first.");
        }

        if (!options.DryRun && before.IsMinimized)
        {
            throw new KnownBlockerException("Cannot click a minimized window.");
        }

        int clientX = options.ClientX ?? throw new KnownBlockerException("click requires --client-x.");
        int clientY = options.ClientY ?? throw new KnownBlockerException("click requires --client-y.");
        if (clientX < 0 || clientY < 0 || clientX >= before.ClientRect.Width || clientY >= before.ClientRect.Height)
        {
            throw new KnownBlockerException($"Client click point [{clientX},{clientY}] is outside the client area {before.ClientRect.Width}x{before.ClientRect.Height}.");
        }

        PointObject requestedClientPoint = new(clientX, clientY);
        PointObject screenPoint = ConvertClientPointToScreenPoint(options.Hwnd, clientX, clientY);
        if (options.DryRun)
        {
            return new ClickResult(
                true,
                false,
                false,
                "dotnet-win32-sendinput-mouse",
                "SetCursorPos+SendInputLeftDownUp",
                requestedClientPoint,
                screenPoint,
                options.CursorSettleMilliseconds,
                options.ClickDelayMilliseconds,
                before,
                null,
                "Dry-run only; no mouse input was sent.",
                "Input delivery only; caller must verify UI activation with screenshot/classifier state.");
        }

        if (!NativeMethods.SetCursorPos(screenPoint.X, screenPoint.Y))
        {
            throw new InvalidOperationException($"SetCursorPos failed. {NativeMethods.GetLastErrorMessage()}");
        }

        Thread.Sleep(Math.Max(0, options.CursorSettleMilliseconds));
        SendMouseInput(MOUSEEVENTF_LEFTDOWN);
        Thread.Sleep(Math.Max(0, options.ClickDelayMilliseconds));
        SendMouseInput(MOUSEEVENTF_LEFTUP);

        WindowSnapshot after = GetSnapshot(options.Hwnd);
        return new ClickResult(
            false,
            true,
            false,
            "dotnet-win32-sendinput-mouse",
            "SetCursorPos+SendInputLeftDownUp",
            requestedClientPoint,
            screenPoint,
            options.CursorSettleMilliseconds,
            options.ClickDelayMilliseconds,
            before,
            after,
            "Mouse input was sent to the foreground window.",
            "Input delivery only; caller must verify UI activation with screenshot/classifier state.");
    }

    private static PointObject ConvertClientPointToScreenPoint(IntPtr hwnd, int x, int y)
    {
        POINT point = new(x, y);
        if (!NativeMethods.ClientToScreen(hwnd, ref point))
        {
            throw new InvalidOperationException($"ClientToScreen failed. {NativeMethods.GetLastErrorMessage()}");
        }

        return new PointObject(point.X, point.Y);
    }

    private static void SendMouseInput(uint flags)
    {
        NativeMethods.INPUT input = new()
        {
            type = INPUT_MOUSE,
            U = new NativeMethods.InputUnion
            {
                mi = new NativeMethods.MOUSEINPUT
                {
                    dx = 0,
                    dy = 0,
                    mouseData = 0,
                    dwFlags = flags,
                    time = 0,
                    dwExtraInfo = IntPtr.Zero
                }
            }
        };
        int size = Marshal.SizeOf<NativeMethods.INPUT>();
        uint sent = NativeMethods.SendInput(1, new[] { input }, size);
        if (sent != 1)
        {
            throw new InvalidOperationException($"SendInput failed. {NativeMethods.GetLastErrorMessage()}");
        }
    }

    private static void AssertMatches(Options options, WindowSnapshot snapshot)
    {
        if (options.ExpectedPid is { } expectedPid && snapshot.ProcessId != expectedPid)
        {
            throw new KnownBlockerException($"Bound window process id changed. Expected {expectedPid}, found {snapshot.ProcessId}.");
        }

        if (!string.IsNullOrWhiteSpace(options.ExpectedProcessName) && !string.Equals(snapshot.ProcessName, options.ExpectedProcessName, StringComparison.OrdinalIgnoreCase))
        {
            throw new KnownBlockerException($"Bound window process changed. Expected '{options.ExpectedProcessName}', found '{snapshot.ProcessName}'.");
        }

        if (!string.IsNullOrWhiteSpace(options.ExpectedTitleContains) && snapshot.Title.IndexOf(options.ExpectedTitleContains, StringComparison.OrdinalIgnoreCase) < 0)
        {
            throw new KnownBlockerException($"Bound window title mismatch. Expected title containing '{options.ExpectedTitleContains}', found '{snapshot.Title}'.");
        }
    }

    private static WindowSnapshot GetSnapshot(IntPtr hwnd)
    {
        if (hwnd == IntPtr.Zero)
        {
            throw new KnownBlockerException("A non-zero window handle is required.");
        }

        if (!NativeMethods.IsWindow(hwnd))
        {
            throw new KnownBlockerException($"Window handle {FormatHwnd(hwnd)} is not valid.");
        }

        _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int processId);
        if (processId <= 0)
        {
            throw new KnownBlockerException($"No process id was found for window handle {FormatHwnd(hwnd)}.");
        }

        Process process;
        try
        {
            process = Process.GetProcessById(processId);
        }
        catch (Exception ex)
        {
            throw new KnownBlockerException($"Process lookup failed for window handle {FormatHwnd(hwnd)}: {ex.Message}");
        }

        using (process)
        {
            if (!NativeMethods.GetWindowRect(hwnd, out RECT windowRect))
            {
                throw new InvalidOperationException($"GetWindowRect failed. {NativeMethods.GetLastErrorMessage()}");
            }

            RectObject clientRect = GetClientRectOnScreen(hwnd);
            IntPtr foreground = NativeMethods.GetForegroundWindow();

            return new WindowSnapshot(
                hwnd.ToInt64().ToString(CultureInfo.InvariantCulture),
                FormatHwnd(hwnd),
                process.Id,
                process.ProcessName,
                GetWindowTitle(hwnd),
                foreground == hwnd,
                NativeMethods.IsWindowVisible(hwnd),
                NativeMethods.IsIconic(hwnd),
                RectObject.FromNative(windowRect),
                clientRect);
        }
    }

    private static RectObject GetClientRectOnScreen(IntPtr hwnd)
    {
        if (!NativeMethods.GetClientRect(hwnd, out RECT clientRect))
        {
            throw new InvalidOperationException($"GetClientRect failed. {NativeMethods.GetLastErrorMessage()}");
        }

        POINT origin = new(0, 0);
        if (!NativeMethods.ClientToScreen(hwnd, ref origin))
        {
            throw new InvalidOperationException($"ClientToScreen failed. {NativeMethods.GetLastErrorMessage()}");
        }

        int width = clientRect.Right - clientRect.Left;
        int height = clientRect.Bottom - clientRect.Top;
        return new RectObject(origin.X, origin.Y, origin.X + width, origin.Y + height);
    }

    private static string GetWindowTitle(IntPtr hwnd)
    {
        int length = NativeMethods.GetWindowTextLength(hwnd);
        if (length <= 0)
        {
            return string.Empty;
        }

        StringBuilder builder = new(length + 1);
        _ = NativeMethods.GetWindowText(hwnd, builder, builder.Capacity);
        return builder.ToString();
    }

    private static string FormatHwnd(IntPtr hwnd) => $"0x{hwnd.ToInt64():X}";
}

sealed record WindowSnapshot(
    string WindowHandle,
    string WindowHandleHex,
    int ProcessId,
    string ProcessName,
    string Title,
    bool IsForeground,
    bool IsVisible,
    bool IsMinimized,
    RectObject WindowRect,
    RectObject ClientRect);

sealed record ResizeResult(
    bool DryRun,
    bool ResizeApplied,
    bool ResizeOk,
    WindowSnapshot Before,
    WindowSnapshot? After,
    SizeObject RequestedClientSize,
    RectObject RequestedWindow,
    SizeObject Border);

sealed record ClickResult(
    bool DryRun,
    bool InputSent,
    bool ActivationVerified,
    string Backend,
    string MouseInputMethod,
    PointObject RequestedClientPoint,
    PointObject ScreenPoint,
    int CursorSettleMilliseconds,
    int ClickDelayMilliseconds,
    WindowSnapshot Before,
    WindowSnapshot? After,
    string StatusNote,
    string VerificationRequired);

sealed record RectObject(int Left, int Top, int Right, int Bottom)
{
    public int Width => Right - Left;
    public int Height => Bottom - Top;

    public static RectObject FromNative(RECT rect) => new(rect.Left, rect.Top, rect.Right, rect.Bottom);
}

sealed record PointObject(int X, int Y);

sealed record SizeObject(int Width, int Height);

sealed record ToolError(bool Ok, string Status, string Error, string? ErrorType = null);

sealed class KnownBlockerException(string message) : Exception(message);

[StructLayout(LayoutKind.Sequential)]
struct RECT
{
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

[StructLayout(LayoutKind.Sequential)]
struct POINT(int x, int y)
{
    public int X = x;
    public int Y = y;
}

static partial class NativeMethods
{
    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT
    {
        public int type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion
    {
        [FieldOffset(0)]
        public MOUSEINPUT mi;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MOUSEINPUT
    {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", EntryPoint = "GetWindowTextLengthW", SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int x, int y, int cx, int cy, uint uFlags);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    public static string GetLastErrorMessage()
    {
        int error = Marshal.GetLastWin32Error();
        return error == 0 ? "No Win32 error was reported." : new System.ComponentModel.Win32Exception(error).Message;
    }
}
