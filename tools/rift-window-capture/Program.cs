using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using SharpGen.Runtime;
using Vortice.Direct3D;
using Vortice.Direct3D11;
using Vortice.DXGI;
using WinRT;
using Windows.Graphics;
using Windows.Graphics.Capture;
using Windows.Graphics.DirectX;
using WgiD3D = Windows.Graphics.DirectX.Direct3D11;

Options options;
try
{
    options = Options.Parse(args);
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
    Console.Error.WriteLine(Options.Usage);
    Environment.Exit(64);
    return;
}

if (options.Command is "inspect" or "validate")
{
    ManifestInspectionReport inspection = ManifestCommands.Run(options);
    if (options.Json)
    {
        Console.WriteLine(JsonSerializer.Serialize(inspection, CaptureJsonContext.Default.ManifestInspectionReport));
    }
    else
    {
        Console.WriteLine(inspection.Ok
            ? $"Manifest {inspection.Command} passed: {inspection.Manifest}"
            : $"Manifest {inspection.Command} failed: {string.Join("; ", inspection.Blockers)}");
    }

    Environment.Exit(inspection.Ok ? 0 : 2);
    return;
}

if (options.Command == "benchmark")
{
    BenchmarkReport benchmark = await BenchmarkCommands.RunAsync(options, CaptureOnceAsync);
    if (options.Json)
    {
        Console.WriteLine(JsonSerializer.Serialize(benchmark, CaptureJsonContext.Default.BenchmarkReport));
    }
    else
    {
        Console.WriteLine(benchmark.Ok
            ? $"Benchmark passed: {benchmark.FramesCompleted}/{benchmark.FramesRequested} frames, avg={benchmark.AverageMs:F1}ms, root={benchmark.OutputRoot}"
            : $"Benchmark blocked: {string.Join("; ", benchmark.Blockers)}");
    }

    Environment.Exit(benchmark.Ok ? 0 : 2);
    return;
}

RunArtifacts? artifacts = RunArtifacts.Create(options);
CaptureReport report;
try
{
    artifacts?.Log("info", "run.start", new { args, outputRoot = artifacts.OutputRoot });
    report = await CaptureOnceAsync(options, artifacts);
}
catch (Exception ex)
{
    report = CaptureReport.Error(options, ex.ToString(), ex.GetType().Name, knownBlocker: false);
}

if (artifacts is not null)
{
    try
    {
        report = artifacts.Finish(report);
    }
    catch (Exception ex)
    {
        report = CaptureReport.Error(
            options,
            $"Artifact bundle write failed: {ex.Message}",
            ex.GetType().Name,
            knownBlocker: false) with
        {
            OutputRoot = artifacts.OutputRoot,
            RunLog = artifacts.RunLogPath,
            Summary = artifacts.SummaryPath,
            Manifest = artifacts.ManifestPath,
        };
    }
}

if (options.Json)
{
    Console.WriteLine(JsonSerializer.Serialize(report, CaptureJsonContext.Default.CaptureReport));
}
else
{
    Console.WriteLine(report.Ok
        ? $"Captured {report.Width}x{report.Height} to {report.Output} (usable={report.Usable}, blackRatio={report.BlackPixelRatio:P1}, stdDev={report.LumaStdDev:F2})"
        : $"Capture failed: {report.Message}");
}

Environment.Exit(GetExitCode(report, options));

static int GetExitCode(CaptureReport report, Options options)
{
    if (report.Ok && (!options.RequireUsable || report.Usable))
    {
        return 0;
    }

    return report.KnownBlocker ? 2 : 1;
}

static async Task<CaptureReport> CaptureOnceAsync(Options options, RunArtifacts? artifacts)
{
    if (!GraphicsCaptureSession.IsSupported())
    {
        return CaptureReport.Error(options, "Windows Graphics Capture is not supported on this OS/session.", null);
    }

    artifacts?.Log("info", "target.resolve.start", new
    {
        options.Pid,
        hwnd = Options.FormatHwnd(options.Hwnd),
        options.ProcessName,
        options.TitleContains,
        expectedProcessStartUtc = options.ExpectedProcessStartUtc?.ToString("O"),
    });
    WindowLookupResult lookup = WindowFinder.Find(options);
    if (lookup.Blocker is not null)
    {
        artifacts?.Log("warning", "target.resolve.blocked", new { lookup.Blocker });
        return CaptureReport.Error(options, lookup.Blocker, null, lookup.Match);
    }

    WindowMatch window = lookup.Match ?? new WindowMatch(IntPtr.Zero, 0, string.Empty, string.Empty, null);
    if (window.Hwnd == IntPtr.Zero)
    {
        return CaptureReport.Error(options, "No matching visible top-level window was found.", null);
    }

    artifacts?.Log("info", "target.resolve.done", new
    {
        hwnd = Options.FormatHwnd(window.Hwnd),
        pid = window.Pid,
        processName = window.ProcessName,
        title = window.Title,
        processStartUtc = window.ProcessStartUtc?.ToString("O"),
    });

    if (!NativeMethods.GetClientRect(window.Hwnd, out RECT clientRect))
    {
        return CaptureReport.Error(options, $"GetClientRect failed: {Marshal.GetLastWin32Error()}", null, window);
    }

    int width = Math.Max(0, clientRect.Right - clientRect.Left);
    int height = Math.Max(0, clientRect.Bottom - clientRect.Top);
    if (width <= 0 || height <= 0)
    {
        return CaptureReport.Error(options, "Matched window has an empty client rectangle, likely minimized.", null, window);
    }

    string output = Path.GetFullPath(options.Output ?? artifacts?.ImagePath ?? Defaults.CreateDefaultOutputPath());
    Directory.CreateDirectory(Path.GetDirectoryName(output) ?? Environment.CurrentDirectory);

    using D3DObjects d3d = D3DObjects.Create();

    if (options.CaptureDesktopDuplication)
    {
        try
        {
            artifacts?.Log("info", "backend.selected", new { backend = "dxgi-desktop" });
            IntPtr monitor = NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST);
            QualityReport quality = DesktopDuplicationCapture.CaptureNearestMonitor(
                d3d,
                monitor,
                output,
                options.TimeoutMs,
                options.CaptureAttempts,
                options.ShouldEmitPng);
            artifacts?.Log("info", "frame.acquired", new { quality.Width, quality.Height, quality.Output, quality.Usable });
            return CaptureReport.Success(options, window, quality.Output, quality);
        }
        catch (Exception ex)
        {
            return CaptureReport.Error(options, $"DXGI Desktop Duplication failed: {ex}", ex.GetType().Name, window);
        }
    }

    WgiD3D.IDirect3DDevice winrtDevice;
    try
    {
        winrtDevice = Direct3D11Helpers.CreateDirect3DDevice(d3d.Device);
    }
    catch (Exception ex)
    {
        return CaptureReport.Error(options, $"CreateDirect3DDevice failed: {ex.Message}", ex.GetType().Name, window);
    }

    GraphicsCaptureItem item;
    try
    {
        artifacts?.Log("info", "backend.selected", new { backend = options.CaptureMonitor ? "wgc-monitor" : "wgc-window" });
        item = options.CaptureMonitor
            ? GraphicsCaptureItemFactory.CreateForMonitor(NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST))
            : GraphicsCaptureItemFactory.CreateForWindow(window.Hwnd);
    }
    catch (Exception ex)
    {
        string captureSource = options.CaptureMonitor ? "CreateForMonitor" : "CreateForWindow";
        return CaptureReport.Error(options, $"{captureSource} failed: {ex.Message}", ex.GetType().Name, window);
    }
    SizeInt32 size = item.Size;
    if (size.Width <= 0 || size.Height <= 0)
    {
        size = new SizeInt32 { Width = width, Height = height };
    }

    using Direct3D11CaptureFramePool framePool = Direct3D11CaptureFramePool.CreateFreeThreaded(
        winrtDevice,
        DirectXPixelFormat.B8G8R8A8UIntNormalized,
        1,
        size);

    using GraphicsCaptureSession session = framePool.CreateCaptureSession(item);
    TaskCompletionSource<Direct3D11CaptureFrame> tcs = new(TaskCreationOptions.RunContinuationsAsynchronously);
    framePool.FrameArrived += (_, _) =>
    {
        try
        {
            Direct3D11CaptureFrame? frame = framePool.TryGetNextFrame();
            if (frame is not null)
            {
                tcs.TrySetResult(frame);
            }
        }
        catch (Exception ex)
        {
            tcs.TrySetException(ex);
        }
    };

    session.StartCapture();

    using CancellationTokenSource timeout = new(options.TimeoutMs);
    await using (timeout.Token.Register(() => tcs.TrySetCanceled(timeout.Token)))
    {
        Direct3D11CaptureFrame frame;
        try
        {
            frame = await tcs.Task.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            return CaptureReport.Error(options, $"Timed out waiting for a WGC frame after {options.TimeoutMs} ms.", null, window);
        }

        using (frame)
        {
            QualityReport quality = TextureSaver.SaveFrameToImage(d3d, frame.Surface, output, options.ShouldEmitPng);
            artifacts?.Log("info", "frame.acquired", new { quality.Width, quality.Height, quality.Output, quality.Usable });
            return CaptureReport.Success(options, window, quality.Output, quality);
        }
    }
}

sealed record Options(
    string Command,
    string? ProcessName,
    int? Pid,
    IntPtr? Hwnd,
    string? TitleContains,
    string? Output,
    string? OutputRoot,
    string? ManifestPath,
    DateTimeOffset? ExpectedProcessStartUtc,
    bool Json,
    int TimeoutMs,
    bool CaptureMonitor,
    bool CaptureDesktopDuplication,
    int CaptureAttempts,
    int Frames,
    bool RequireUsable,
    bool EmitPng,
    string[] CropProfiles)
{
    public static string Usage => "Usage: RiftWindowCapture [capture] [--process-name rift_x64 | --pid <pid> | --hwnd <0xHWND> | --title-contains <text>] [--expected-process-start-utc <iso-utc>] [--output <image>] [--output-root <dir>] [--emit-png] [--crop full-window] [--json] [--timeout-ms <n>] [--capture-monitor | --desktop-duplication] [--attempts <n>] [--require-usable]\n       RiftWindowCapture benchmark [--frames <n>] [capture target/options] --output-root <dir> [--json]\n       RiftWindowCapture inspect --manifest <manifest.json> [--json]\n       RiftWindowCapture validate --manifest <manifest.json> [--json]";

    public string CaptureMethod => CaptureDesktopDuplication
        ? "DXGIDesktopDuplication"
        : CaptureMonitor
            ? "WindowsGraphicsCaptureMonitor"
            : "WindowsGraphicsCaptureWindow";

    public bool ShouldEmitPng => EmitPng || OutputRoot is not null || string.Equals(Path.GetExtension(Output), ".png", StringComparison.OrdinalIgnoreCase);

    public static Options Parse(string[] args)
    {
        string command = "capture";
        int startIndex = 0;
        if (args.Length > 0 && IsCommand(args[0]))
        {
            command = args[0].ToLowerInvariant();
            startIndex = 1;
        }

        string? processName = null;
        int? pid = null;
        IntPtr? hwnd = null;
        string? titleContains = null;
        string? output = null;
        string? outputRoot = null;
        string? manifestPath = null;
        DateTimeOffset? expectedProcessStartUtc = null;
        bool json = false;
        int timeoutMs = Defaults.TimeoutMs;
        bool captureMonitor = false;
        bool captureDesktopDuplication = false;
        int captureAttempts = 1;
        int frames = 30;
        bool requireUsable = false;
        bool emitPng = false;
        List<string> cropProfiles = [];

        for (int i = startIndex; i < args.Length; i++)
        {
            string arg = args[i];
            switch (arg)
            {
                case "capture":
                    if (i != startIndex)
                    {
                        throw new ArgumentException("The capture command must be the first argument.");
                    }
                    command = "capture";
                    break;
                case "--process-name":
                    processName = RequireValue(args, ref i, arg);
                    break;
                case "--pid":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out int parsedPid) || parsedPid <= 0)
                    {
                        throw new ArgumentException("--pid must be a positive integer.");
                    }
                    pid = parsedPid;
                    break;
                case "--hwnd":
                    hwnd = ParseHwnd(RequireValue(args, ref i, arg));
                    break;
                case "--title-contains":
                    titleContains = RequireValue(args, ref i, arg);
                    break;
                case "--output":
                    output = RequireValue(args, ref i, arg);
                    break;
                case "--output-root":
                    outputRoot = RequireValue(args, ref i, arg);
                    break;
                case "--manifest":
                    manifestPath = RequireValue(args, ref i, arg);
                    break;
                case "--expected-process-start-utc":
                    expectedProcessStartUtc = ParseUtc(RequireValue(args, ref i, arg), arg);
                    break;
                case "--json":
                    json = true;
                    break;
                case "--emit-png":
                    emitPng = true;
                    break;
                case "--crop":
                    string crop = RequireValue(args, ref i, arg);
                    if (!string.Equals(crop, "full-window", StringComparison.OrdinalIgnoreCase))
                    {
                        throw new ArgumentException($"Unsupported --crop profile for this implementation slice: {crop}. Supported: full-window.");
                    }
                    cropProfiles.Add("full-window");
                    break;
                case "--capture-monitor":
                    captureMonitor = true;
                    break;
                case "--desktop-duplication":
                    captureDesktopDuplication = true;
                    break;
                case "--timeout-ms":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out timeoutMs) || timeoutMs < 250)
                    {
                        throw new ArgumentException("--timeout-ms must be at least 250.");
                    }
                    break;
                case "--attempts":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out captureAttempts) || captureAttempts < 1)
                    {
                        throw new ArgumentException("--attempts must be at least 1.");
                    }
                    break;
                case "--frames":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out frames) || frames < 1 || frames > 1_000)
                    {
                        throw new ArgumentException("--frames must be between 1 and 1000.");
                    }
                    break;
                case "--require-usable":
                    requireUsable = true;
                    break;
                case "--help":
                case "-h":
                case "/?":
                    throw new ArgumentException(Usage);
                default:
                    throw new ArgumentException($"Unknown argument: {arg}");
            }
        }

        if (command is "inspect" or "validate")
        {
            if (string.IsNullOrWhiteSpace(manifestPath))
            {
                throw new ArgumentException($"{command} requires --manifest <manifest.json>.");
            }
        }

        if (command is "capture" or "benchmark" && processName is null && pid is null && hwnd is null && titleContains is null)
        {
            processName = "rift_x64";
        }

        if (captureMonitor && captureDesktopDuplication)
        {
            throw new ArgumentException("--capture-monitor and --desktop-duplication are mutually exclusive.");
        }

        if (cropProfiles.Count == 0)
        {
            cropProfiles.Add("full-window");
        }

        return new Options(command, processName, pid, hwnd, titleContains, output, outputRoot, manifestPath, expectedProcessStartUtc, json, timeoutMs, captureMonitor, captureDesktopDuplication, captureAttempts, frames, requireUsable, emitPng, cropProfiles.ToArray());
    }

    private static bool IsCommand(string value) =>
        string.Equals(value, "capture", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "benchmark", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "inspect", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "validate", StringComparison.OrdinalIgnoreCase);

    private static string RequireValue(string[] args, ref int index, string name)
    {
        if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
        {
            throw new ArgumentException($"{name} requires a value.");
        }

        index++;
        return args[index];
    }

    private static IntPtr ParseHwnd(string value)
    {
        string trimmed = value.Trim();
        bool isHex = trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase);
        string numeric = isHex ? trimmed[2..] : trimmed;
        NumberStyles style = isHex ? NumberStyles.AllowHexSpecifier : NumberStyles.Integer;
        if (!long.TryParse(numeric, style, CultureInfo.InvariantCulture, out long parsed) || parsed <= 0)
        {
            throw new ArgumentException("--hwnd must be a positive window handle, for example 0xC0994.");
        }

        return new IntPtr(parsed);
    }

    private static DateTimeOffset ParseUtc(string value, string name)
    {
        if (!DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out DateTimeOffset parsed))
        {
            throw new ArgumentException($"{name} must be an ISO-8601 date/time value.");
        }

        return parsed.ToUniversalTime();
    }

    public static string? FormatHwnd(IntPtr? hwnd) => hwnd is null ? null : FormatHwnd(hwnd.Value);

    public static string FormatHwnd(IntPtr hwnd) => $"0x{hwnd.ToInt64():X}";
}

sealed record WindowMatch(IntPtr Hwnd, int Pid, string ProcessName, string Title, DateTimeOffset? ProcessStartUtc);

sealed record WindowLookupResult(WindowMatch? Match, string? Blocker);

static class WindowFinder
{
    public static WindowLookupResult Find(Options options)
    {
        if (options.Hwnd is { } exactHwnd)
        {
            return FindExactHwnd(options, exactHwnd);
        }

        List<WindowMatch> matches = [];
        NativeMethods.EnumWindows((hwnd, _) =>
        {
            if (!NativeMethods.IsWindowVisible(hwnd) || NativeMethods.GetWindow(hwnd, NativeMethods.GW_OWNER) != IntPtr.Zero)
            {
                return true;
            }

            _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int windowPid);
            if (windowPid <= 0)
            {
                return true;
            }

            string title = GetWindowText(hwnd);
            if (string.IsNullOrWhiteSpace(title))
            {
                return true;
            }

            ProcessIdentity processIdentity;
            try
            {
                processIdentity = ProcessIdentity.FromPid(windowPid);
            }
            catch
            {
                return true;
            }

            if (options.Pid is { } pid && windowPid != pid)
            {
                return true;
            }

            if (options.ProcessName is { Length: > 0 } expectedProcess)
            {
                string normalizedExpected = Path.GetFileNameWithoutExtension(expectedProcess);
                if (!string.Equals(processIdentity.ProcessName, normalizedExpected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            if (options.ExpectedProcessStartUtc is not null && !ProcessStartMatches(processIdentity.ProcessStartUtc, options.ExpectedProcessStartUtc.Value))
            {
                return true;
            }

            if (options.TitleContains is { Length: > 0 } titleContains &&
                title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
            {
                return true;
            }

            matches.Add(new WindowMatch(hwnd, windowPid, processIdentity.ProcessName, title, processIdentity.ProcessStartUtc));
            return true;
        }, IntPtr.Zero);

        WindowMatch? match = matches.OrderByDescending(m => NativeMethods.GetForegroundWindow() == m.Hwnd).FirstOrDefault();
        return match is null
            ? new WindowLookupResult(null, "No matching visible top-level window was found.")
            : new WindowLookupResult(match, null);
    }

    private static WindowLookupResult FindExactHwnd(Options options, IntPtr hwnd)
    {
        if (!NativeMethods.IsWindow(hwnd))
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is not a valid window handle.");
        }

        if (!NativeMethods.IsWindowVisible(hwnd))
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is not visible.");
        }

        if (NativeMethods.GetWindow(hwnd, NativeMethods.GW_OWNER) != IntPtr.Zero)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is an owned window, not a top-level capture target.");
        }

        _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int windowPid);
        if (windowPid <= 0)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} has no owning process.");
        }

        string title = GetWindowText(hwnd);
        ProcessIdentity processIdentity;
        try
        {
            processIdentity = ProcessIdentity.FromPid(windowPid);
        }
        catch (Exception ex)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} process lookup failed: {ex.Message}");
        }

        WindowMatch match = new(hwnd, windowPid, processIdentity.ProcessName, title, processIdentity.ProcessStartUtc);

        if (options.Pid is { } pid && windowPid != pid)
        {
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} belongs to PID {windowPid}, not expected PID {pid}.");
        }

        if (options.ProcessName is { Length: > 0 } expectedProcess)
        {
            string normalizedExpected = Path.GetFileNameWithoutExtension(expectedProcess);
            if (!string.Equals(processIdentity.ProcessName, normalizedExpected, StringComparison.OrdinalIgnoreCase))
            {
                return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} belongs to process {processIdentity.ProcessName}, not expected process {normalizedExpected}.");
            }
        }

        if (options.TitleContains is { Length: > 0 } titleContains &&
            title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
        {
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} title '{title}' does not contain expected text '{titleContains}'.");
        }

        if (options.ExpectedProcessStartUtc is not null && !ProcessStartMatches(processIdentity.ProcessStartUtc, options.ExpectedProcessStartUtc.Value))
        {
            string actual = processIdentity.ProcessStartUtc?.ToString("O") ?? "unavailable";
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} process start {actual} does not match expected {options.ExpectedProcessStartUtc.Value:O} within {Defaults.ProcessStartTolerance.TotalSeconds:N0}s.");
        }

        return new WindowLookupResult(match, null);
    }

    private static bool ProcessStartMatches(DateTimeOffset? actualUtc, DateTimeOffset expectedUtc)
    {
        if (actualUtc is null)
        {
            return false;
        }

        TimeSpan delta = (actualUtc.Value.ToUniversalTime() - expectedUtc.ToUniversalTime()).Duration();
        return delta <= Defaults.ProcessStartTolerance;
    }

    private static string GetWindowText(IntPtr hwnd)
    {
        int length = NativeMethods.GetWindowTextLength(hwnd);
        if (length <= 0)
        {
            return string.Empty;
        }

        StringBuilder buffer = new(length + 1);
        _ = NativeMethods.GetWindowText(hwnd, buffer, buffer.Capacity);
        return buffer.ToString();
    }
}

sealed record ProcessIdentity(string ProcessName, DateTimeOffset? ProcessStartUtc)
{
    public static ProcessIdentity FromPid(int pid)
    {
        using Process process = Process.GetProcessById(pid);
        DateTimeOffset? startUtc = null;
        try
        {
            startUtc = new DateTimeOffset(process.StartTime.ToUniversalTime(), TimeSpan.Zero);
        }
        catch
        {
            // Some system processes deny StartTime. Keep the process usable unless an expected start gate is requested.
        }

        return new ProcessIdentity(process.ProcessName, startUtc);
    }
}

sealed class D3DObjects : IDisposable
{
    public required ID3D11Device Device { get; init; }
    public required ID3D11DeviceContext Context { get; init; }

    public static D3DObjects Create()
    {
        FeatureLevel[] featureLevels =
        [
            FeatureLevel.Level_12_1,
            FeatureLevel.Level_12_0,
            FeatureLevel.Level_11_1,
            FeatureLevel.Level_11_0,
        ];

                SharpGen.Runtime.Result result = D3D11.D3D11CreateDevice(
            IntPtr.Zero,
            DriverType.Hardware,
            DeviceCreationFlags.BgraSupport,
            featureLevels,
            out ID3D11Device device,
            out _,
            out ID3D11DeviceContext context);

        if (result.Failure)
        {
            throw new InvalidOperationException($"D3D11CreateDevice failed: 0x{result.Code:X8}");
        }

        return new D3DObjects { Device = device, Context = context };
    }

    public void Dispose()
    {
        Context.Dispose();
        Device.Dispose();
    }
}

static class Defaults
{
    public const int TimeoutMs = 2_500;
    public static readonly TimeSpan ProcessStartTolerance = TimeSpan.FromSeconds(2);

    public static string CreateDefaultOutputPath()
    {
        string root = Path.Combine(Path.GetTempPath(), "RiftReader-window-capture", "wgc");
        return Path.Combine(root, $"capture-{DateTime.Now:yyyyMMdd-HHmmss-fff}.bmp");
    }

    public static string CreateDefaultBenchmarkOutputRoot()
    {
        string root = Path.Combine(Path.GetTempPath(), "RiftReader-window-capture", "benchmark");
        return Path.Combine(root, $"benchmark-{DateTime.Now:yyyyMMdd-HHmmss-fff}");
    }
}

static class GraphicsCaptureItemFactory
{
    private static readonly Guid IID_IGraphicsCaptureItem = new("79C3F95B-31F7-4EC2-A464-632EF5D30760");
    private static readonly Guid IID_IGraphicsCaptureItemInterop = new("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356");

    public static GraphicsCaptureItem CreateForWindow(IntPtr hwnd)
    {
        return Create(hwnd, captureMonitor: false);
    }

    public static GraphicsCaptureItem CreateForMonitor(IntPtr monitor)
    {
        return Create(monitor, captureMonitor: true);
    }

    private static GraphicsCaptureItem Create(IntPtr handle, bool captureMonitor)
    {
        IntPtr className = IntPtr.Zero;
        IntPtr factoryPtr = IntPtr.Zero;
        IntPtr itemPtr = IntPtr.Zero;
        try
        {
            Guid interopIid = IID_IGraphicsCaptureItemInterop;
            Guid itemIid = IID_IGraphicsCaptureItem;
            int hr = NativeMethods.WindowsCreateString("Windows.Graphics.Capture.GraphicsCaptureItem", 44, out className);
            ThrowIfFailed(hr, "WindowsCreateString(GraphicsCaptureItem)");

            hr = NativeMethods.RoGetActivationFactory(className, ref interopIid, out factoryPtr);
            ThrowIfFailed(hr, "RoGetActivationFactory(IGraphicsCaptureItemInterop)");

            IGraphicsCaptureItemInterop factory = (IGraphicsCaptureItemInterop)Marshal.GetObjectForIUnknown(factoryPtr);
            hr = captureMonitor
                ? factory.CreateForMonitor(handle, ref itemIid, out itemPtr)
                : factory.CreateForWindow(handle, ref itemIid, out itemPtr);
            ThrowIfFailed(hr, captureMonitor
                ? "IGraphicsCaptureItemInterop.CreateForMonitor"
                : "IGraphicsCaptureItemInterop.CreateForWindow");

            return MarshalInspectable<GraphicsCaptureItem>.FromAbi(itemPtr);
        }
        finally
        {
            if (itemPtr != IntPtr.Zero)
            {
                Marshal.Release(itemPtr);
            }
            if (factoryPtr != IntPtr.Zero)
            {
                Marshal.Release(factoryPtr);
            }
            if (className != IntPtr.Zero)
            {
                _ = NativeMethods.WindowsDeleteString(className);
            }
        }
    }

    private static void ThrowIfFailed(int hr, string api)
    {
        if (hr < 0)
        {
            Marshal.ThrowExceptionForHR(hr);
        }
    }
}

static class Direct3D11Helpers
{
    private static readonly Guid IID_ID3D11Texture2D = new("6f15aaf2-d208-4e89-9ab4-489535d34f9c");

    public static WgiD3D.IDirect3DDevice CreateDirect3DDevice(ID3D11Device d3dDevice)
    {
        using IDXGIDevice dxgiDevice = d3dDevice.QueryInterface<IDXGIDevice>();
        IntPtr dxgiDevicePtr = dxgiDevice.NativePointer;
        int hr = NativeMethods.CreateDirect3D11DeviceFromDXGIDevice(dxgiDevicePtr, out IntPtr inspectablePtr);
        if (hr < 0)
        {
            Marshal.ThrowExceptionForHR(hr);
        }

        try
        {
            return MarshalInterface<WgiD3D.IDirect3DDevice>.FromAbi(inspectablePtr);
        }
        finally
        {
            Marshal.Release(inspectablePtr);
        }
    }

    public static ID3D11Texture2D GetTexture2D(WgiD3D.IDirect3DSurface surface)
    {
        IObjectReference surfaceReference = MarshalInterface<WgiD3D.IDirect3DSurface>.CreateMarshaler(surface);
        IntPtr surfaceUnknown = MarshalInterface<WgiD3D.IDirect3DSurface>.GetAbi(surfaceReference);
        IntPtr accessPtr = IntPtr.Zero;
        IntPtr texturePtr = IntPtr.Zero;
        try
        {
            Guid textureIid = IID_ID3D11Texture2D;
            int hr = Marshal.QueryInterface(surfaceUnknown, typeof(IDirect3DDxgiInterfaceAccess).GUID, out accessPtr);
            if (hr < 0)
            {
                Marshal.ThrowExceptionForHR(hr);
            }

            IDirect3DDxgiInterfaceAccess access = (IDirect3DDxgiInterfaceAccess)Marshal.GetObjectForIUnknown(accessPtr);
            hr = access.GetInterface(ref textureIid, out texturePtr);
            if (hr < 0)
            {
                Marshal.ThrowExceptionForHR(hr);
            }

            ID3D11Texture2D texture = new(texturePtr);
            texturePtr = IntPtr.Zero;
            return texture;
        }
        finally
        {
            if (texturePtr != IntPtr.Zero)
            {
                Marshal.Release(texturePtr);
            }
            if (accessPtr != IntPtr.Zero)
            {
                Marshal.Release(accessPtr);
            }
            MarshalInterface<WgiD3D.IDirect3DSurface>.DisposeMarshaler(surfaceReference);
        }
    }
}

static class DesktopDuplicationCapture
{
    public static QualityReport CaptureNearestMonitor(D3DObjects d3d, IntPtr monitor, string output, int timeoutMs, int captureAttempts, bool emitPng)
    {
        using IDXGIOutput1 output1 = FindOutputForMonitor(d3d.Device, monitor, out OutputDescription outputDescription);
        using IDXGIOutputDuplication duplication = output1.DuplicateOutput(d3d.Device);
        OutduplDescription duplicationDescription = duplication.Description;

        QualityReport? best = null;
        Exception? lastException = null;
        int completedAttempts = 0;

        for (int attempt = 1; attempt <= captureAttempts; attempt++)
        {
            bool frameAcquired = false;
            IDXGIResource? desktopResource = null;
            try
            {
                Result result = duplication.AcquireNextFrame((uint)timeoutMs, out OutduplFrameInfo frameInfo, out desktopResource);
                result.CheckError();
                frameAcquired = true;
                completedAttempts++;

                using ID3D11Texture2D desktopTexture = desktopResource.QueryInterface<ID3D11Texture2D>();
                string attemptOutput = captureAttempts == 1 ? output : TextureSaver.CreateAttemptOutputPath(output, attempt, emitPng);
                QualityReport quality = TextureSaver.SaveTextureToImage(d3d, desktopTexture, attemptOutput, emitPng) with
                {
                    CaptureAttemptCount = captureAttempts,
                    CompletedAttemptCount = completedAttempts,
                    SelectedAttempt = attempt,
                    DesktopDuplicationDeviceName = outputDescription.DeviceName,
                    DesktopDuplicationDesktopCoordinates = outputDescription.DesktopCoordinates.ToString(),
                    DesktopDuplicationRotation = outputDescription.Rotation.ToString(),
                    DesktopDuplicationModeDescription = duplicationDescription.ModeDescription.ToString(),
                    DesktopDuplicationModeFormat = duplicationDescription.ModeDescription.Format.ToString(),
                    DesktopDuplicationDesktopImageInSystemMemory = duplicationDescription.DesktopImageInSystemMemory,
                    DesktopDuplicationAccumulatedFrames = (int)frameInfo.AccumulatedFrames,
                    DesktopDuplicationProtectedContentMaskedOut = frameInfo.ProtectedContentMaskedOut,
                    DesktopDuplicationPointerVisible = frameInfo.PointerPosition.Visible,
                    DesktopDuplicationPointerPosition = frameInfo.PointerPosition.Position.ToString(),
                };

                if (best is null || IsBetter(quality, best))
                {
                    best = quality;
                }
            }
            catch (Exception ex) when (best is not null)
            {
                lastException = ex;
                break;
            }
            finally
            {
                desktopResource?.Dispose();
                if (frameAcquired)
                {
                    duplication.ReleaseFrame().CheckError();
                }
            }
        }

        if (best is null)
        {
            throw lastException ?? new InvalidOperationException("DXGI Desktop Duplication did not return a frame.");
        }

        string finalOutput = TextureSaver.NormalizeImageOutputPath(output, emitPng);
        if (!string.Equals(best.Output, finalOutput, StringComparison.OrdinalIgnoreCase))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(finalOutput) ?? Environment.CurrentDirectory);
            File.Copy(best.Output, finalOutput, overwrite: true);
            best = best with { Output = finalOutput };
        }

        return best with
        {
            CompletedAttemptCount = completedAttempts,
            LastAttemptError = lastException?.Message,
        };
    }

    private static bool IsBetter(QualityReport candidate, QualityReport incumbent)
    {
        if (candidate.Usable != incumbent.Usable)
        {
            return candidate.Usable;
        }

        if (candidate.ContentBlackPixelRatio != incumbent.ContentBlackPixelRatio)
        {
            return candidate.ContentBlackPixelRatio < incumbent.ContentBlackPixelRatio;
        }

        return candidate.ContentLumaStdDev > incumbent.ContentLumaStdDev;
    }

    private static IDXGIOutput1 FindOutputForMonitor(ID3D11Device device, IntPtr monitor, out OutputDescription matchedDescription)
    {
        using IDXGIDevice dxgiDevice = device.QueryInterface<IDXGIDevice>();
        dxgiDevice.GetAdapter(out IDXGIAdapter adapter).CheckError();
        using (adapter)
        {
            for (uint i = 0; ; i++)
            {
                Result result = adapter.EnumOutputs(i, out IDXGIOutput output);
                if (result.Failure)
                {
                    break;
                }

                OutputDescription description = output.Description;
                if (description.Monitor == monitor)
                {
                    try
                    {
                        matchedDescription = description;
                        return output.QueryInterface<IDXGIOutput1>();
                    }
                    finally
                    {
                        output.Dispose();
                    }
                }

                output.Dispose();
            }
        }

        matchedDescription = default;
        throw new InvalidOperationException("No DXGI output matched the Rift window's nearest monitor.");
    }
}

static class TextureSaver
{
    public static QualityReport SaveFrameToImage(D3DObjects d3d, WgiD3D.IDirect3DSurface surface, string output, bool emitPng)
    {
        using ID3D11Texture2D source = Direct3D11Helpers.GetTexture2D(surface);
        return SaveTextureToImage(d3d, source, output, emitPng);
    }

    public static QualityReport SaveTextureToImage(D3DObjects d3d, ID3D11Texture2D source, string output, bool emitPng)
    {
        Texture2DDescription sourceDescription = source.Description;
        int width = (int)sourceDescription.Width;
        int height = (int)sourceDescription.Height;

        Texture2DDescription stagingDescription = new(
            Format.B8G8R8A8_UNorm,
            (uint)width,
            (uint)height,
            1,
            1,
            BindFlags.None,
            ResourceUsage.Staging,
            CpuAccessFlags.Read,
            1,
            0,
            ResourceOptionFlags.None);

        using ID3D11Texture2D staging = d3d.Device.CreateTexture2D(stagingDescription);
        d3d.Context.CopyResource(staging, source);

        d3d.Context.Map(staging, 0, MapMode.Read, Vortice.Direct3D11.MapFlags.None, out MappedSubresource mapped).CheckError();
        try
        {
            return SaveMappedBgraImage(mapped, width, height, output, emitPng) with
            {
                SourceTextureFormat = sourceDescription.Format.ToString(),
                SourceTextureUsage = sourceDescription.Usage.ToString(),
                SourceTextureBindFlags = sourceDescription.BindFlags.ToString(),
                SourceTextureCpuAccessFlags = sourceDescription.CPUAccessFlags.ToString(),
                SourceTextureMiscFlags = sourceDescription.MiscFlags.ToString(),
            };
        }
        finally
        {
            d3d.Context.Unmap(staging, 0);
        }
    }

    private static QualityReport SaveMappedBgraImage(MappedSubresource mapped, int width, int height, string output, bool emitPng)
    {
        long pixelCount = (long)width * height;
        long blackPixels = 0;
        long transparentPixels = 0;
        double lumaSum = 0;
        double lumaSquaredSum = 0;
        const int contentTop = 40;
        long contentPixelCount = 0;
        long contentBlackPixels = 0;
        long contentTransparentPixels = 0;
        double contentLumaSum = 0;
        double contentLumaSquaredSum = 0;
        byte[] row = new byte[width * 4];
        byte[] image = new byte[checked(width * height * 4)];

        for (int y = 0; y < height; y++)
        {
            IntPtr sourceRow = IntPtr.Add(mapped.DataPointer, y * (int)mapped.RowPitch);
            Marshal.Copy(sourceRow, row, 0, row.Length);
            Buffer.BlockCopy(row, 0, image, y * row.Length, row.Length);

            for (int x = 0; x < row.Length; x += 4)
            {
                byte b = row[x];
                byte g = row[x + 1];
                byte r = row[x + 2];
                byte a = row[x + 3];
                if (a == 0)
                {
                    transparentPixels++;
                }

                if (r < 4 && g < 4 && b < 4)
                {
                    blackPixels++;
                }

                double luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
                lumaSum += luma;
                lumaSquaredSum += luma * luma;

                if (y >= contentTop)
                {
                    contentPixelCount++;
                    if (a == 0)
                    {
                        contentTransparentPixels++;
                    }

                    if (r < 4 && g < 4 && b < 4)
                    {
                        contentBlackPixels++;
                    }

                    contentLumaSum += luma;
                    contentLumaSquaredSum += luma * luma;
                }
            }
        }

        BgraFrame frame = new(width, height, width * 4, "BGRA32", "top-down", image);
        string actualOutput = NormalizeImageOutputPath(output, emitPng);
        if (string.Equals(Path.GetExtension(actualOutput), ".png", StringComparison.OrdinalIgnoreCase))
        {
            WriteTopDownBgraPng(actualOutput, frame);
        }
        else
        {
            WriteTopDownBgraBmp(actualOutput, frame);
        }

        double mean = pixelCount == 0 ? 0 : lumaSum / pixelCount;
        double variance = pixelCount == 0 ? 0 : Math.Max(0, (lumaSquaredSum / pixelCount) - (mean * mean));
        double stdDev = Math.Sqrt(variance);
        double blackRatio = pixelCount == 0 ? 1 : blackPixels / (double)pixelCount;
        double transparentRatio = pixelCount == 0 ? 1 : transparentPixels / (double)pixelCount;
        double contentMean = contentPixelCount == 0 ? 0 : contentLumaSum / contentPixelCount;
        double contentVariance = contentPixelCount == 0 ? 0 : Math.Max(0, (contentLumaSquaredSum / contentPixelCount) - (contentMean * contentMean));
        double contentStdDev = Math.Sqrt(contentVariance);
        double contentBlackRatio = contentPixelCount == 0 ? 1 : contentBlackPixels / (double)contentPixelCount;
        double contentTransparentRatio = contentPixelCount == 0 ? 1 : contentTransparentPixels / (double)contentPixelCount;
        bool usable = contentPixelCount > 0 && contentTransparentRatio < 0.95 && contentBlackRatio < 0.98 && contentStdDev >= 2.0;

        return new QualityReport(width, height, frame.StrideBytes, frame.PixelFormat, frame.Orientation, blackRatio, transparentRatio, stdDev, contentBlackRatio, contentTransparentRatio, contentStdDev, usable, actualOutput);
    }

    private static void WriteTopDownBgraBmp(string output, BgraFrame frame)
    {
        output = Path.GetFullPath(output);
        string parent = Path.GetDirectoryName(output) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        int imageBytes = checked(frame.Width * frame.Height * 4);
        int fileBytes = checked(14 + 40 + imageBytes);

        using FileStream stream = new(output, FileMode.Create, FileAccess.Write, FileShare.Read);
        using BinaryWriter writer = new(stream, Encoding.UTF8, leaveOpen: false);
        writer.Write((byte)'B');
        writer.Write((byte)'M');
        writer.Write(fileBytes);
        writer.Write(0);
        writer.Write(14 + 40);
        writer.Write(40);
        writer.Write(frame.Width);
        writer.Write(-frame.Height);
        writer.Write((ushort)1);
        writer.Write((ushort)32);
        writer.Write(0);
        writer.Write(imageBytes);
        writer.Write(2835);
        writer.Write(2835);
        writer.Write(0);
        writer.Write(0);
        writer.Write(frame.Pixels);
    }

    private static void WriteTopDownBgraPng(string output, BgraFrame frame)
    {
        output = Path.GetFullPath(output);
        string parent = Path.GetDirectoryName(output) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        using Bitmap bitmap = new(frame.Width, frame.Height, PixelFormat.Format32bppArgb);
        Rectangle rectangle = new(0, 0, frame.Width, frame.Height);
        BitmapData data = bitmap.LockBits(rectangle, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try
        {
            int rowBytes = checked(frame.Width * 4);
            for (int y = 0; y < frame.Height; y++)
            {
                IntPtr destination = IntPtr.Add(data.Scan0, y * data.Stride);
                Marshal.Copy(frame.Pixels, y * rowBytes, destination, rowBytes);
            }
        }
        finally
        {
            bitmap.UnlockBits(data);
        }

        bitmap.Save(output, ImageFormat.Png);
    }

    public static string NormalizeImageOutputPath(string output, bool emitPng)
    {
        string full = Path.GetFullPath(output);
        string extension = Path.GetExtension(full);
        if (emitPng || string.Equals(extension, ".png", StringComparison.OrdinalIgnoreCase))
        {
            return Path.ChangeExtension(full, ".png");
        }

        return Path.ChangeExtension(full, ".bmp");
    }

    public static string CreateAttemptOutputPath(string output, int attempt, bool emitPng)
    {
        string imageOutput = NormalizeImageOutputPath(output, emitPng);
        string directory = Path.GetDirectoryName(imageOutput) ?? Environment.CurrentDirectory;
        string fileName = Path.GetFileNameWithoutExtension(imageOutput);
        string extension = Path.GetExtension(imageOutput);
        return Path.Combine(directory, $"{fileName}.attempt{attempt}{extension}");
    }
}

sealed record BgraFrame(int Width, int Height, int StrideBytes, string PixelFormat, string Orientation, byte[] Pixels);

sealed record QualityReport(
    int Width,
    int Height,
    int StrideBytes,
    string PixelFormat,
    string Orientation,
    double BlackPixelRatio,
    double TransparentPixelRatio,
    double LumaStdDev,
    double ContentBlackPixelRatio,
    double ContentTransparentPixelRatio,
    double ContentLumaStdDev,
    bool Usable,
    string Output)
{
    public string? SourceTextureFormat { get; init; }
    public string? SourceTextureUsage { get; init; }
    public string? SourceTextureBindFlags { get; init; }
    public string? SourceTextureCpuAccessFlags { get; init; }
    public string? SourceTextureMiscFlags { get; init; }
    public int? CaptureAttemptCount { get; init; }
    public int? CompletedAttemptCount { get; init; }
    public int? SelectedAttempt { get; init; }
    public string? LastAttemptError { get; init; }
    public string? DesktopDuplicationDeviceName { get; init; }
    public string? DesktopDuplicationDesktopCoordinates { get; init; }
    public string? DesktopDuplicationRotation { get; init; }
    public string? DesktopDuplicationModeDescription { get; init; }
    public string? DesktopDuplicationModeFormat { get; init; }
    public bool? DesktopDuplicationDesktopImageInSystemMemory { get; init; }
    public int? DesktopDuplicationAccumulatedFrames { get; init; }
    public bool? DesktopDuplicationProtectedContentMaskedOut { get; init; }
    public bool? DesktopDuplicationPointerVisible { get; init; }
    public string? DesktopDuplicationPointerPosition { get; init; }
}

static class ManifestCommands
{
    public static ManifestInspectionReport Run(Options options)
    {
        string manifestPath = Path.GetFullPath(options.ManifestPath ?? throw new InvalidOperationException("--manifest is required."));
        List<string> blockers = [];
        List<string> warnings = [];
        string? schema = null;
        string? status = null;
        string? runId = null;
        string? outputImage = null;
        string? runLog = null;
        string? summary = null;
        bool manifestExists = File.Exists(manifestPath);
        bool jsonParsed = false;
        bool artifactPathsExist = false;

        if (!manifestExists)
        {
            blockers.Add($"Manifest not found: {manifestPath}");
            return new ManifestInspectionReport(options.Command, false, manifestPath, false, false, null, null, null, null, null, null, false, blockers.ToArray(), warnings.ToArray());
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(manifestPath, Encoding.UTF8));
            JsonElement root = document.RootElement;
            jsonParsed = true;
            schema = ReadString(root, "schema");
            status = ReadString(root, "status");
            runId = ReadString(root, "runId");
            if (!string.Equals(schema, "rift-window-capture-manifest/v1", StringComparison.Ordinal))
            {
                blockers.Add($"Unexpected manifest schema: {schema ?? "<missing>"}");
            }

            if (string.IsNullOrWhiteSpace(status))
            {
                blockers.Add("Manifest is missing status.");
            }

            if (root.TryGetProperty("artifacts", out JsonElement artifacts))
            {
                runLog = ResolveArtifact(manifestPath, ReadString(artifacts, "runLogJsonl"));
                summary = ResolveArtifact(manifestPath, ReadString(artifacts, "summaryMarkdown"));
                outputImage = ResolveArtifact(manifestPath, ReadString(artifacts, "fullWindowImage"));
            }
            else
            {
                blockers.Add("Manifest is missing artifacts object.");
            }
        }
        catch (Exception ex)
        {
            blockers.Add($"Manifest JSON parse failed: {ex.Message}");
        }

        if (options.Command == "validate" && jsonParsed)
        {
            if (runLog is null || !File.Exists(runLog))
            {
                blockers.Add("Run log JSONL artifact is missing.");
            }
            else if (!JsonlLooksValid(runLog, out string? jsonlError))
            {
                blockers.Add($"Run log JSONL is invalid: {jsonlError}");
            }

            if (summary is null || !File.Exists(summary))
            {
                blockers.Add("Summary Markdown artifact is missing.");
            }

            if (string.Equals(status, "passed", StringComparison.OrdinalIgnoreCase))
            {
                if (outputImage is null || !File.Exists(outputImage))
                {
                    blockers.Add("Passed capture manifest is missing fullWindowImage artifact.");
                }
                else if (new FileInfo(outputImage).Length <= 0)
                {
                    blockers.Add("fullWindowImage artifact is empty.");
                }
            }
        }
        else if (options.Command == "inspect")
        {
            if (runLog is not null && !File.Exists(runLog))
            {
                warnings.Add("Run log artifact path does not exist.");
            }

            if (summary is not null && !File.Exists(summary))
            {
                warnings.Add("Summary artifact path does not exist.");
            }

            if (outputImage is not null && !File.Exists(outputImage))
            {
                warnings.Add("fullWindowImage artifact path does not exist.");
            }
        }

        artifactPathsExist =
            (runLog is null || File.Exists(runLog)) &&
            (summary is null || File.Exists(summary)) &&
            (outputImage is null || File.Exists(outputImage));

        bool ok = blockers.Count == 0;
        return new ManifestInspectionReport(options.Command, ok, manifestPath, manifestExists, jsonParsed, schema, status, runId, runLog, summary, outputImage, artifactPathsExist, blockers.ToArray(), warnings.ToArray());
    }

    private static string? ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static string? ResolveArtifact(string manifestPath, string? artifactPath)
    {
        if (string.IsNullOrWhiteSpace(artifactPath))
        {
            return null;
        }

        return Path.IsPathRooted(artifactPath)
            ? Path.GetFullPath(artifactPath)
            : Path.GetFullPath(Path.Combine(Path.GetDirectoryName(manifestPath) ?? Environment.CurrentDirectory, artifactPath));
    }

    private static bool JsonlLooksValid(string path, out string? error)
    {
        int lineNumber = 0;
        foreach (string line in File.ReadLines(path, Encoding.UTF8))
        {
            lineNumber++;
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                using JsonDocument _ = JsonDocument.Parse(line);
            }
            catch (Exception ex)
            {
                error = $"line {lineNumber}: {ex.Message}";
                return false;
            }
        }

        error = null;
        return true;
    }
}

sealed record ManifestInspectionReport(
    string Command,
    bool Ok,
    string Manifest,
    bool ManifestExists,
    bool JsonParsed,
    string? Schema,
    string? Status,
    string? RunId,
    string? RunLog,
    string? Summary,
    string? FullWindowImage,
    bool ArtifactPathsExist,
    string[] Blockers,
    string[] Warnings);

static class BenchmarkCommands
{
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

    public static async Task<BenchmarkReport> RunAsync(
        Options options,
        Func<Options, RunArtifacts?, Task<CaptureReport>> captureOnceAsync)
    {
        string outputRoot = Path.GetFullPath(options.OutputRoot ?? Defaults.CreateDefaultBenchmarkOutputRoot());
        Directory.CreateDirectory(outputRoot);

        List<BenchmarkFrameReport> frames = [];
        List<string> blockers = [];
        Stopwatch total = Stopwatch.StartNew();

        for (int i = 1; i <= options.Frames; i++)
        {
            string frameRoot = Path.Combine(outputRoot, $"frame-{i:0000}");
            Options frameOptions = options with
            {
                Command = "capture",
                OutputRoot = frameRoot,
                Output = null,
                Json = true,
            };
            RunArtifacts? artifacts = RunArtifacts.Create(frameOptions);
            Stopwatch frameWatch = Stopwatch.StartNew();
            CaptureReport report;
            try
            {
                artifacts?.Log("info", "benchmark.frame.start", new { frame = i, frames = options.Frames });
                report = await captureOnceAsync(frameOptions, artifacts);
            }
            catch (Exception ex)
            {
                report = CaptureReport.Error(frameOptions, ex.ToString(), ex.GetType().Name, knownBlocker: false);
            }

            if (artifacts is not null)
            {
                report = artifacts.Finish(report);
            }

            frameWatch.Stop();
            int exitCode = report.Ok && (!frameOptions.RequireUsable || report.Usable)
                ? 0
                : report.KnownBlocker
                    ? 2
                    : 1;

            frames.Add(new BenchmarkFrameReport(
                i,
                frameRoot,
                exitCode,
                report.Ok,
                report.Usable,
                frameWatch.Elapsed.TotalMilliseconds,
                report.Manifest,
                report.Output,
                report.Blockers));

            if (exitCode != 0)
            {
                blockers.Add($"Frame {i} blocked/failed with exit code {exitCode}: {string.Join("; ", report.Blockers.DefaultIfEmpty(report.Message ?? "unknown"))}");
                break;
            }
        }

        total.Stop();
        double[] durations = frames.Select(f => f.DurationMs).ToArray();
        bool ok = frames.Count == options.Frames && frames.All(f => f.ExitCode == 0);
        BenchmarkReport benchmark = new(
            ok,
            outputRoot,
            options.Frames,
            frames.Count,
            durations.Length == 0 ? 0 : durations.Average(),
            durations.Length == 0 ? 0 : durations.Min(),
            durations.Length == 0 ? 0 : durations.Max(),
            total.Elapsed.TotalMilliseconds,
            frames.ToArray(),
            blockers.ToArray(),
            []);

        File.WriteAllText(Path.Combine(outputRoot, "benchmark.json"), JsonSerializer.Serialize(benchmark, CaptureJsonContext.Default.BenchmarkReport), Utf8NoBom);
        File.WriteAllText(Path.Combine(outputRoot, "summary.md"), BuildSummary(benchmark), Utf8NoBom);
        return benchmark;
    }

    private static string BuildSummary(BenchmarkReport benchmark)
    {
        StringBuilder builder = new();
        builder.AppendLine("# Rift window capture benchmark summary");
        builder.AppendLine();
        builder.AppendLine($"- Status: `{(benchmark.Ok ? "passed" : "blocked")}`");
        builder.AppendLine($"- Output root: `{benchmark.OutputRoot}`");
        builder.AppendLine($"- Frames: `{benchmark.FramesCompleted}/{benchmark.FramesRequested}`");
        builder.AppendLine($"- Average ms: `{benchmark.AverageMs:F2}`");
        builder.AppendLine($"- Min ms: `{benchmark.MinMs:F2}`");
        builder.AppendLine($"- Max ms: `{benchmark.MaxMs:F2}`");
        builder.AppendLine();
        builder.AppendLine("## Safety");
        builder.AppendLine();
        builder.AppendLine("- movementSent: `false`");
        builder.AppendLine("- inputSent: `false`");
        builder.AppendLine("- reloaduiSent: `false`");
        builder.AppendLine("- screenshotKeySent: `false`");
        builder.AppendLine("- cheatEngineUsed: `false`");
        builder.AppendLine("- x64dbgAttached: `false`");
        if (benchmark.Blockers.Length > 0)
        {
            builder.AppendLine();
            builder.AppendLine("## Blockers");
            foreach (string blocker in benchmark.Blockers)
            {
                builder.AppendLine($"- {blocker}");
            }
        }

        return builder.ToString();
    }
}

sealed record BenchmarkReport(
    bool Ok,
    string OutputRoot,
    int FramesRequested,
    int FramesCompleted,
    double AverageMs,
    double MinMs,
    double MaxMs,
    double TotalMs,
    BenchmarkFrameReport[] Frames,
    string[] Blockers,
    string[] Warnings);

sealed record BenchmarkFrameReport(
    int Index,
    string OutputRoot,
    int ExitCode,
    bool Ok,
    bool Usable,
    double DurationMs,
    string? Manifest,
    string? Output,
    string[] Blockers);

sealed class RunArtifacts
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

    private RunArtifacts(string outputRoot, string imagePath)
    {
        OutputRoot = outputRoot;
        ImagePath = imagePath;
        RunId = Path.GetFileName(outputRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        ManifestPath = Path.Combine(outputRoot, "manifest.json");
        SummaryPath = Path.Combine(outputRoot, "summary.md");
        RunLogPath = Path.Combine(outputRoot, "logs", "run.jsonl");
        StartedAtUtc = DateTimeOffset.UtcNow;
    }

    public string OutputRoot { get; }
    public string ImagePath { get; }
    public string RunId { get; }
    public string ManifestPath { get; }
    public string SummaryPath { get; }
    public string RunLogPath { get; }
    public DateTimeOffset StartedAtUtc { get; }

    public static RunArtifacts? Create(Options options)
    {
        if (string.IsNullOrWhiteSpace(options.OutputRoot))
        {
            return null;
        }

        string outputRoot = Path.GetFullPath(options.OutputRoot);
        string imagePath = options.Output is null
            ? Path.Combine(outputRoot, "images", "full-window.png")
            : Path.GetFullPath(options.Output);

        Directory.CreateDirectory(outputRoot);
        Directory.CreateDirectory(Path.Combine(outputRoot, "logs"));
        Directory.CreateDirectory(Path.Combine(outputRoot, "images"));
        Directory.CreateDirectory(Path.Combine(outputRoot, "debug"));

        return new RunArtifacts(outputRoot, imagePath);
    }

    public void Log(string level, string eventName, object? data = null)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(RunLogPath) ?? OutputRoot);
        Dictionary<string, object?> payload = new(StringComparer.Ordinal)
        {
            ["tsUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ["level"] = level,
            ["event"] = eventName,
        };

        if (data is not null)
        {
            payload["data"] = data;
        }

        File.AppendAllText(RunLogPath, JsonSerializer.Serialize(payload) + Environment.NewLine, Utf8NoBom);
    }

    public CaptureReport Finish(CaptureReport report)
    {
        DateTimeOffset endedAtUtc = DateTimeOffset.UtcNow;
        CaptureReport reportWithPaths = report with
        {
            OutputRoot = OutputRoot,
            Manifest = ManifestPath,
            RunLog = RunLogPath,
            Summary = SummaryPath,
        };

        CaptureRunManifest manifest = BuildManifest(reportWithPaths, endedAtUtc);
        Directory.CreateDirectory(Path.GetDirectoryName(ManifestPath) ?? OutputRoot);
        File.WriteAllText(ManifestPath, JsonSerializer.Serialize(manifest, CaptureJsonContext.Default.CaptureRunManifest), Utf8NoBom);
        File.WriteAllText(SummaryPath, BuildSummary(reportWithPaths, manifest), Utf8NoBom);
        Log("info", "run.finish", new { manifest = ManifestPath, summary = SummaryPath, status = manifest.Status });
        return reportWithPaths;
    }

    private CaptureRunManifest BuildManifest(CaptureReport report, DateTimeOffset endedAtUtc)
    {
        string status = report.Ok && (!report.KnownBlocker)
            ? "passed"
            : report.KnownBlocker
                ? "blocked"
                : "failed";

        string[] blockers = report.Blockers.Length > 0
            ? report.Blockers
            : report.KnownBlocker && !string.IsNullOrWhiteSpace(report.Message)
                ? [report.Message]
                : [];

        string[] warnings = report.Warnings;
        CaptureArtifactsManifest artifacts = new(
            Relative(ManifestPath),
            Relative(SummaryPath),
            Relative(RunLogPath),
            report.Output is null ? null : Relative(report.Output));

        return new CaptureRunManifest(
            "rift-window-capture-manifest/v1",
            RunId,
            status,
            StartedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            endedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            new CaptureTargetManifest(
                report.WindowPid,
                report.Hwnd,
                report.WindowProcessName,
                report.WindowProcessStartUtc,
                report.WindowTitle,
                report.Pid,
                report.RequestedHwnd,
                report.ProcessName,
                report.TitleContains,
                report.ExpectedProcessStartUtc),
            new CaptureBackendManifest(report.CaptureMethod, report.CaptureMethod, false),
            report.Ok
                ? new CaptureFrameManifest(report.Quality?.PixelFormat ?? "BGRA32", report.Width, report.Height, report.Quality?.StrideBytes ?? report.Width * 4, report.Quality?.Orientation ?? "top-down")
                : null,
            new CaptureTimingManifest(
                StartedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                endedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                (endedAtUtc - StartedAtUtc).TotalMilliseconds),
            report.Quality is null
                ? null
                : new CaptureQualityManifest(report.Usable, report.BlackPixelRatio, report.LumaStdDev, report.TransparentPixelRatio, report.ContentBlackPixelRatio, report.ContentLumaStdDev, report.ContentTransparentPixelRatio),
            CaptureSafetyManifest.SafeNoInput,
            artifacts,
            blockers,
            warnings,
            report.ErrorType is null ? null : new CaptureErrorManifest("capture", report.ErrorType, report.Message ?? string.Empty));
    }

    private string BuildSummary(CaptureReport report, CaptureRunManifest manifest)
    {
        StringBuilder builder = new();
        builder.AppendLine("# Rift window capture run summary");
        builder.AppendLine();
        builder.AppendLine($"- Run: `{RunId}`");
        builder.AppendLine($"- Status: `{manifest.Status}`");
        builder.AppendLine($"- Started UTC: `{manifest.StartedAtUtc}`");
        builder.AppendLine($"- Ended UTC: `{manifest.EndedAtUtc}`");
        builder.AppendLine($"- Target: PID `{report.WindowPid?.ToString(CultureInfo.InvariantCulture) ?? "n/a"}`, HWND `{report.Hwnd ?? "n/a"}`, process `{report.WindowProcessName ?? "n/a"}`");
        builder.AppendLine($"- Backend: `{report.CaptureMethod}`");
        builder.AppendLine($"- Output: `{report.Output ?? "n/a"}`");
        builder.AppendLine($"- Usable: `{report.Usable}`");
        builder.AppendLine();
        builder.AppendLine("## Safety");
        builder.AppendLine();
        builder.AppendLine("- movementSent: `false`");
        builder.AppendLine("- inputSent: `false`");
        builder.AppendLine("- reloaduiSent: `false`");
        builder.AppendLine("- screenshotKeySent: `false`");
        builder.AppendLine("- cheatEngineUsed: `false`");
        builder.AppendLine("- x64dbgAttached: `false`");
        builder.AppendLine();
        if (manifest.Blockers.Length > 0)
        {
            builder.AppendLine("## Blockers");
            builder.AppendLine();
            foreach (string blocker in manifest.Blockers)
            {
                builder.AppendLine($"- {blocker}");
            }
            builder.AppendLine();
        }

        if (manifest.Warnings.Length > 0)
        {
            builder.AppendLine("## Warnings");
            builder.AppendLine();
            foreach (string warning in manifest.Warnings)
            {
                builder.AppendLine($"- {warning}");
            }
            builder.AppendLine();
        }

        return builder.ToString();
    }

    private string Relative(string path)
    {
        string fullPath = Path.GetFullPath(path);
        string root = Path.GetFullPath(OutputRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        return fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase)
            ? fullPath[root.Length..].Replace(Path.DirectorySeparatorChar, '/')
            : fullPath;
    }
}

sealed record CaptureRunManifest(
    string Schema,
    string RunId,
    string Status,
    string StartedAtUtc,
    string EndedAtUtc,
    CaptureTargetManifest Target,
    CaptureBackendManifest Backend,
    CaptureFrameManifest? Frame,
    CaptureTimingManifest Timing,
    CaptureQualityManifest? Quality,
    CaptureSafetyManifest Safety,
    CaptureArtifactsManifest Artifacts,
    string[] Blockers,
    string[] Warnings,
    CaptureErrorManifest? Error);

sealed record CaptureTargetManifest(
    int? Pid,
    string? Hwnd,
    string? ProcessName,
    string? ProcessStartUtc,
    string? WindowTitle,
    int? RequestedPid,
    string? RequestedHwnd,
    string? RequestedProcessName,
    string? RequestedTitleContains,
    string? ExpectedProcessStartUtc);

sealed record CaptureBackendManifest(string Requested, string? Actual, bool FallbackUsed);

sealed record CaptureFrameManifest(string PixelFormat, int Width, int Height, int StrideBytes, string Orientation);

sealed record CaptureTimingManifest(string StartedAtUtc, string EndedAtUtc, double DurationMs);

sealed record CaptureQualityManifest(bool Usable, double BlackPixelRatio, double LumaStdDev, double TransparentPixelRatio, double ContentBlackPixelRatio, double ContentLumaStdDev, double ContentTransparentPixelRatio);

sealed record CaptureSafetyManifest(bool MovementSent, bool InputSent, bool ReloaduiSent, bool ScreenshotKeySent, bool CheatEngineUsed, bool X64dbgAttached)
{
    public static CaptureSafetyManifest SafeNoInput { get; } = new(false, false, false, false, false, false);
}

sealed record CaptureArtifactsManifest(string ManifestJson, string SummaryMarkdown, string RunLogJsonl, string? FullWindowImage);

sealed record CaptureErrorManifest(string Stage, string Code, string Message);

sealed record CaptureReport(
    bool Ok,
    bool Usable,
    string CaptureMethod,
    string? Output,
    string? Message,
    string? ErrorType,
    string? ProcessName,
    int? Pid,
    string? TitleContains,
    string? WindowProcessName,
    int? WindowPid,
    string? WindowTitle,
    string? Hwnd,
    int Width,
    int Height,
    double BlackPixelRatio,
    double TransparentPixelRatio,
    double LumaStdDev,
    double ContentBlackPixelRatio,
    double ContentTransparentPixelRatio,
    double ContentLumaStdDev,
    QualityReport? Quality,
    bool KnownBlocker,
    string? RequestedHwnd,
    string? ExpectedProcessStartUtc,
    string? WindowProcessStartUtc,
    string? OutputRoot,
    string? Manifest,
    string? RunLog,
    string? Summary,
    string[] Warnings,
    string[] Blockers)
{
    public static CaptureReport Success(Options options, WindowMatch window, string output, QualityReport quality) => new(
        true,
        quality.Usable,
        options.CaptureMethod,
        output,
        quality.Usable ? "Captured a non-empty WGC frame." : "Captured a frame, but pixel statistics look black/flat/transparent.",
        null,
        options.ProcessName,
        options.Pid,
        options.TitleContains,
        window.ProcessName,
        window.Pid,
        window.Title,
        $"0x{window.Hwnd.ToInt64():X}",
        quality.Width,
        quality.Height,
        quality.BlackPixelRatio,
        quality.TransparentPixelRatio,
        quality.LumaStdDev,
        quality.ContentBlackPixelRatio,
        quality.ContentTransparentPixelRatio,
        quality.ContentLumaStdDev,
        quality,
        options.RequireUsable && !quality.Usable,
        Options.FormatHwnd(options.Hwnd),
        options.ExpectedProcessStartUtc?.ToString("O"),
        window.ProcessStartUtc?.ToString("O"),
        null,
        null,
        null,
        null,
        quality.Usable ? [] : ["Captured frame quality is below usable thresholds."],
        options.RequireUsable && !quality.Usable ? ["--require-usable was specified and captured frame quality is below usable thresholds."] : []);

    public static CaptureReport Error(Options options, string message, string? errorType, WindowMatch? window = null, bool knownBlocker = true) => new(
        false,
        false,
        options.CaptureMethod,
        options.Output is null ? null : Path.GetFullPath(options.Output),
        message,
        errorType,
        options.ProcessName,
        options.Pid,
        options.TitleContains,
        window?.ProcessName,
        window?.Pid,
        window?.Title,
        window?.Hwnd == IntPtr.Zero || window is null ? null : $"0x{window.Hwnd.ToInt64():X}",
        0,
        0,
        1,
        1,
        0,
        1,
        1,
        0,
        null,
        knownBlocker,
        Options.FormatHwnd(options.Hwnd),
        options.ExpectedProcessStartUtc?.ToString("O"),
        window?.ProcessStartUtc?.ToString("O"),
        null,
        null,
        null,
        null,
        [],
        [message]);
}

[JsonSerializable(typeof(QualityReport))]
[JsonSerializable(typeof(CaptureReport))]
[JsonSerializable(typeof(CaptureRunManifest))]
[JsonSerializable(typeof(ManifestInspectionReport))]
[JsonSerializable(typeof(BenchmarkReport))]
[JsonSourceGenerationOptions(WriteIndented = true, PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
partial class CaptureJsonContext : JsonSerializerContext;

[ComImport]
[Guid("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IGraphicsCaptureItemInterop
{
    [PreserveSig]
    int CreateForWindow(IntPtr window, ref Guid iid, out IntPtr result);

    [PreserveSig]
    int CreateForMonitor(IntPtr monitor, ref Guid iid, out IntPtr result);
}

[ComImport]
[Guid("A9B3D012-3DF2-4EE3-B8D1-8695F457D3C1")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDirect3DDxgiInterfaceAccess
{
    [PreserveSig]
    int GetInterface(ref Guid iid, out IntPtr p);
}

[StructLayout(LayoutKind.Sequential)]
struct RECT
{
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

static partial class NativeMethods
{
    public const uint GW_OWNER = 4;
    public const uint MONITOR_DEFAULTTONEAREST = 2;

    public delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool IsWindow(IntPtr hWnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool IsWindowVisible(IntPtr hWnd);

    [LibraryImport("user32.dll")]
    public static partial IntPtr GetWindow(IntPtr hWnd, uint uCmd);

    [LibraryImport("user32.dll")]
    public static partial IntPtr GetForegroundWindow();

    [LibraryImport("user32.dll")]
    public static partial IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [LibraryImport("user32.dll", SetLastError = true)]
    public static partial int GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextLengthW", SetLastError = true)]
    public static partial int GetWindowTextLength(IntPtr hWnd);

    [LibraryImport("combase.dll")]
    public static partial int WindowsCreateString([MarshalAs(UnmanagedType.LPWStr)] string sourceString, int length, out IntPtr hstring);

    [LibraryImport("combase.dll")]
    public static partial int WindowsDeleteString(IntPtr hstring);

    [LibraryImport("combase.dll")]
    public static partial int RoGetActivationFactory(IntPtr activatableClassId, ref Guid iid, out IntPtr factory);

    [LibraryImport("d3d11.dll")]
    public static partial int CreateDirect3D11DeviceFromDXGIDevice(IntPtr dxgiDevice, out IntPtr graphicsDevice);
}
