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
