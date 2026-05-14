sealed record Options(
    string Command,
    string? ProcessName,
    int? Pid,
    IntPtr? Hwnd,
    string? TitleContains,
    string? Output,
    string? OutputRoot,
    string? ManifestPath,
    string? RawPath,
    string? MetadataPath,
    string? PngPath,
    string? Profile,
    string? BeforePath,
    string? AfterPath,
    DateTimeOffset? ExpectedProcessStartUtc,
    bool Json,
    int TimeoutMs,
    bool CaptureMonitor,
    bool CaptureDesktopDuplication,
    int CaptureAttempts,
    int Frames,
    bool RequireUsable,
    bool EmitPng,
    bool EmitRawBgra,
    string[] CropProfiles)
{
    public static string Usage => "Usage: RiftWindowCapture [capture] [--process-name rift_x64 | --pid <pid> | --hwnd <0xHWND> | --title-contains <text>] [--expected-process-start-utc <iso-utc>] [--output <image>] [--output-root <dir>] [--emit-png] [--emit-raw-bgra] [--crop full-window] [--json] [--timeout-ms <n>] [--capture-monitor | --desktop-duplication] [--attempts <n>] [--require-usable]\n       RiftWindowCapture benchmark [--frames <n>] [capture target/options] --output-root <dir> [--json]\n       RiftWindowCapture inspect --manifest <manifest.json> [--json]\n       RiftWindowCapture validate --manifest <manifest.json> [--json]\n       RiftWindowCapture convert --raw <frame.bgra> --metadata <frame.json> --png <out.png> [--json]\n       RiftWindowCapture crop (--manifest <manifest.json> | --raw <frame.bgra> --metadata <frame.json>) --profile <name> [--output-root <dir>] [--png <out.png>] [--emit-raw-bgra] [--json]\n       RiftWindowCapture diff --before <before.bgra> --after <after.bgra> --metadata <frame.json> [--json]";

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
        string? rawPath = null;
        string? metadataPath = null;
        string? pngPath = null;
        string? profile = null;
        string? beforePath = null;
        string? afterPath = null;
        DateTimeOffset? expectedProcessStartUtc = null;
        bool json = false;
        int timeoutMs = Defaults.TimeoutMs;
        bool captureMonitor = false;
        bool captureDesktopDuplication = false;
        int captureAttempts = 1;
        int frames = 30;
        bool requireUsable = false;
        bool emitPng = false;
        bool emitRawBgra = false;
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
                case "--raw":
                    rawPath = RequireValue(args, ref i, arg);
                    break;
                case "--metadata":
                    metadataPath = RequireValue(args, ref i, arg);
                    break;
                case "--png":
                    pngPath = RequireValue(args, ref i, arg);
                    break;
                case "--profile":
                    profile = CropProfileRegistry.Normalize(RequireValue(args, ref i, arg));
                    break;
                case "--before":
                    beforePath = RequireValue(args, ref i, arg);
                    break;
                case "--after":
                    afterPath = RequireValue(args, ref i, arg);
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
                case "--emit-raw-bgra":
                    emitRawBgra = true;
                    break;
                case "--crop":
                    cropProfiles.Add(CropProfileRegistry.Normalize(RequireValue(args, ref i, arg)));
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

        if (command == "convert")
        {
            RequireOfflineValue(rawPath, "--raw", command);
            RequireOfflineValue(metadataPath, "--metadata", command);
            RequireOfflineValue(pngPath, "--png", command);
        }

        if (command == "crop")
        {
            if (string.IsNullOrWhiteSpace(manifestPath) && (string.IsNullOrWhiteSpace(rawPath) || string.IsNullOrWhiteSpace(metadataPath)))
            {
                throw new ArgumentException("crop requires either --manifest <manifest.json> or --raw <frame.bgra> --metadata <frame.json>.");
            }

            RequireOfflineValue(profile, "--profile", command);
        }

        if (command == "diff")
        {
            RequireOfflineValue(beforePath, "--before", command);
            RequireOfflineValue(afterPath, "--after", command);
            RequireOfflineValue(metadataPath, "--metadata", command);
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

        return new Options(command, processName, pid, hwnd, titleContains, output, outputRoot, manifestPath, rawPath, metadataPath, pngPath, profile, beforePath, afterPath, expectedProcessStartUtc, json, timeoutMs, captureMonitor, captureDesktopDuplication, captureAttempts, frames, requireUsable, emitPng, emitRawBgra, cropProfiles.ToArray());
    }

    private static bool IsCommand(string value) =>
        string.Equals(value, "capture", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "benchmark", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "inspect", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "validate", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "convert", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "crop", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "diff", StringComparison.OrdinalIgnoreCase);

    private static string RequireValue(string[] args, ref int index, string name)
    {
        if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
        {
            throw new ArgumentException($"{name} requires a value.");
        }

        index++;
        return args[index];
    }

    private static void RequireOfflineValue(string? value, string name, string command)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException($"{command} requires {name}.");
        }
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
