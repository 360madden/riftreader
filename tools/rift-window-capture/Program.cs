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

if (options.Command is "convert" or "crop" or "diff")
{
    OfflineFrameReport offline = OfflineFrameCommands.Run(options);
    if (options.Json)
    {
        Console.WriteLine(JsonSerializer.Serialize(offline, CaptureJsonContext.Default.OfflineFrameReport));
    }
    else
    {
        Console.WriteLine(offline.Ok
            ? $"{offline.Command} passed: {offline.Message}"
            : $"{offline.Command} failed: {string.Join("; ", offline.Blockers)}");
    }

    Environment.Exit(offline.Ok ? 0 : 2);
    return;
}

if (options.Command == "benchmark")
{
    BenchmarkReport benchmark = await BenchmarkCommands.RunAsync(options, CaptureRunner.CaptureOnceAsync);
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
    report = await CaptureRunner.CaptureOnceAsync(options, artifacts);
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

Environment.Exit(CaptureRunner.GetExitCode(report, options));
