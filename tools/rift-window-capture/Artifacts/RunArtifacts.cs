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
