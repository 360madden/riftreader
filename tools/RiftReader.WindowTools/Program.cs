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
    bool DryRun)
{
    public static Options Parse(string[] args)
    {
        if (args.Length == 0)
        {
            throw new KnownBlockerException(Usage);
        }

        string command = args[0].Trim().ToLowerInvariant();
        if (command is not ("inspect" or "resize"))
        {
            throw new KnownBlockerException($"Unknown command '{args[0]}'. {Usage}");
        }

        IntPtr hwnd = IntPtr.Zero;
        int? expectedPid = null;
        string? expectedProcessName = null;
        string? expectedTitleContains = null;
        int? clientWidth = null;
        int? clientHeight = null;
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

        return new Options(command, hwnd, expectedPid, expectedProcessName, expectedTitleContains, clientWidth, clientHeight, dryRun);
    }

    public static string Usage => "Usage: RiftReader.WindowTools inspect --hwnd <0xHWND> [--expected-pid <pid>] [--expected-process-name <name>] [--expected-title-contains <text>] [--json]\n       RiftReader.WindowTools resize --hwnd <0xHWND> --client-width <px> --client-height <px> [--dry-run true|false] [expected target options] [--json]";

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

sealed record RectObject(int Left, int Top, int Right, int Bottom)
{
    public int Width => Right - Left;
    public int Height => Bottom - Top;

    public static RectObject FromNative(RECT rect) => new(rect.Left, rect.Top, rect.Right, rect.Bottom);
}

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

    public static string GetLastErrorMessage()
    {
        int error = Marshal.GetLastWin32Error();
        return error == 0 ? "No Win32 error was reported." : new System.ComponentModel.Win32Exception(error).Message;
    }
}
