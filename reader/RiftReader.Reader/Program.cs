using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.CheatEngine;
using RiftReader.Reader.Cli;
using RiftReader.Reader.Debugging;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Models;
using RiftReader.Reader.Processes;
using RiftReader.Reader.Scanning;
using RiftReader.Reader.Sessions;

namespace RiftReader.Reader;

internal static class Program
{
    private const int SessionRecordingSchemaVersion = 1;
    private const int SessionMarkerPollSliceMilliseconds = 50;
    private const int SessionRecentMarkerDisplayCount = 12;
    private const long SessionRecommendedRawByteBudget = 8L * 1024L * 1024L;
    private const int SessionRecommendedBurstSampleCount = 200;
    private const int SessionRecommendedBurstIntervalMilliseconds = 50;
    private const int PlayerCoordTraceRefreshTimeoutMilliseconds = 30000;
    private const int PlayerCoordTraceRefreshMaxHits = 4;
    private const int PlayerCoordTraceRefreshMaxEvents = 4096;
    private const int PlayerCoordTraceRefreshAttempts = 2;
    private const int TruthChainSecondHopSeedLimitPerSurface = 2;
    private const int TruthChainSecondHopPointerScanMaxHits = 6;
    private const int ParentChainSecondHopSeedLimit = 3;
    private const int ParentChainSecondHopMaxHits = 4;
    private const int ParentChainPreviewBytes = 64;
    private const int TruthChainStabilitySampleCount = 5;
    private const int TruthChainStabilityDelayMilliseconds = 250;
    private const int RootFamilyComparisonBytes = 128;

    private static readonly JsonSerializerOptions NdjsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    private static readonly JsonSerializerOptions PrettyJsonOptions = new()
    {
        WriteIndented = true
    };

    private static int Main(string[] args)
    {
        var parseResult = ReaderOptionsParser.Parse(args);

        if (parseResult.ShowUsage)
        {
            WriteUsage(parseResult);
            return parseResult.ExitCode;
        }

        if (!parseResult.IsSuccess || parseResult.Options is null)
        {
            Console.Error.WriteLine(parseResult.ErrorMessage ?? "Unable to parse command line arguments.");
            Console.Error.WriteLine();
            WriteUsage(parseResult);
            return parseResult.ExitCode;
        }

        var options = parseResult.Options;

        if (options.ReadAddonSnapshot)
        {
            return RunAddonSnapshotMode(options);
        }

        if (options.ReadReaderBridgeSnapshot)
        {
            return RunReaderBridgeSnapshotMode(options);
        }

        if (options.DebugWorker)
        {
            return RunDebugWorkerMode(options);
        }

        if (options.DebugTraceSummary)
        {
            return RunDebugTraceSummaryMode(options);
        }

        if (options.SessionSummary)
        {
            return RunSessionSummaryMode(options);
        }

        if (options.ReadPlayerOrientation && !options.ProcessId.HasValue && string.IsNullOrWhiteSpace(options.ProcessName))
        {
            return RunReadPlayerOrientationMode(options);
        }

        if (options.RankOwnerComponents)
        {
            return RunOwnerComponentRankingMode(options);
        }

        if (options.RankStatHubs)
        {
            return RunStatHubRankingMode(options);
        }

        if (!options.JsonOutput)
        {
            Console.WriteLine("RiftReader.Reader");
            Console.WriteLine("Use this tool only against Rift client processes you explicitly intend to inspect.");
            Console.WriteLine();
        }

        var locator = new ProcessLocator();

        string? lookupError;
        using var process = options.ProcessId.HasValue
            ? locator.FindById(options.ProcessId.Value, out lookupError)
            : locator.FindByName(options.ProcessName!, out lookupError);

        if (process is null)
        {
            Console.Error.WriteLine(lookupError ?? "Unable to resolve the target process.");
            return 1;
        }

        var target = ProcessTarget.FromProcess(process);

        if (!options.JsonOutput)
        {
            Console.WriteLine($"Attached to PID {target.ProcessId} ({target.ProcessName}).");

            if (!string.IsNullOrWhiteSpace(target.ModuleName))
            {
                Console.WriteLine($"Module: {target.ModuleName}");
            }

            if (!string.IsNullOrWhiteSpace(target.MainWindowTitle))
            {
                Console.WriteLine($"Window: {target.MainWindowTitle}");
            }

            Console.WriteLine();
        }

        var scanRequested =
            !string.IsNullOrWhiteSpace(options.ScanModulePattern) ||
            !string.IsNullOrWhiteSpace(options.ScanString) ||
            options.ScanPointer.HasValue ||
            options.ScanInt32.HasValue ||
            options.ScanFloat.HasValue ||
            options.ScanDouble.HasValue ||
            options.ScanReaderBridgePlayerName ||
            options.ScanReaderBridgePlayerCoords ||
            options.ScanReaderBridgePlayerSignature ||
            options.ScanReaderBridgeIdentity;

        if (options.ListModules)
        {
            try
            {
                var modules = ProcessModuleLocator.ListModules(process);
                var moduleListResult = new ModuleListResult(
                    Mode: "module-list",
                    ProcessId: target.ProcessId,
                    ProcessName: target.ProcessName,
                    ModuleCount: modules.Count,
                    Modules: modules);

                if (options.JsonOutput)
                {
                    Console.WriteLine(JsonOutput.Serialize(moduleListResult));
                    return 0;
                }

                Console.WriteLine(ModuleListTextFormatter.Format(moduleListResult));
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Unable to enumerate process modules: {ex.Message}");
                return 1;
            }
        }

        if (options.KillRiftErrorHandler)
        {
            return RunKillRiftErrorHandlerMode(options, target, process);
        }

        if (DebugTraceRequestBuilder.IsDebugTraceMode(options))
        {
            return RunDebugTraceMode(options, process, target);
        }

        if (!options.WriteCheatEngineProbe && !options.CaptureReaderBridgeBestFamily && !options.ReadPlayerCurrent && !options.ReadPlayerOrientation && !options.FindPlayerOrientationCandidate && !options.ReadPlayerCoordAnchor && !options.RefreshPlayerCoordTrace && !options.ReadPlayerActorCoords && !options.ReadPlayerActorOrientation && !options.ReadPlayerActorTruth && !options.DumpPlayerActorTruthChain && !options.RecordSession && !scanRequested && (!options.Address.HasValue || !options.Length.HasValue))
        {
            if (options.JsonOutput)
            {
                var attachResult = new ProcessAttachResult(
                    Mode: "attach",
                    ProcessId: target.ProcessId,
                    ProcessName: target.ProcessName,
                    ModuleName: target.ModuleName,
                    MainWindowTitle: target.MainWindowTitle);

                Console.WriteLine(JsonOutput.Serialize(attachResult));
                return 0;
            }

            Console.WriteLine("Attach verified. No memory read was requested.");
            Console.WriteLine("Next step: add pointer maps and typed readers for the Rift structures you want to inspect.");
            return 0;
        }

        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);

        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open a memory-reading handle for the target process.");
            return 1;
        }

        if (scanRequested)
        {
            return RunScanMode(options, process, target, reader);
        }

        if (options.WriteCheatEngineProbe)
        {
            return RunCheatEngineProbeMode(options, target, reader);
        }

        if (options.CaptureReaderBridgeBestFamily)
        {
            return RunPlayerSignatureCaptureMode(options, target, reader);
        }

        if (options.ReadPlayerCurrent)
        {
            return RunReadPlayerCurrentMode(options, target, reader);
        }

        if (options.FindPlayerOrientationCandidate)
        {
            return RunFindPlayerOrientationCandidateMode(options, process, target, reader);
        }

        if (options.ReadTargetCurrent)
        {
            return RunReadTargetCurrentMode(options, target, reader);
        }

        if (options.ReadPlayerCoordAnchor)
        {
            return RunReadPlayerCoordAnchorMode(options, process, target, reader);
        }

        if (options.RefreshPlayerCoordTrace)
        {
            return RunRefreshPlayerCoordTraceMode(options, process, target, reader);
        }

        if (options.ReadPlayerActorCoords)
        {
            return RunReadPlayerActorCoordsMode(options, process, target, reader);
        }

        if (options.ReadPlayerActorOrientation)
        {
            return RunReadPlayerActorOrientationMode(options, process, target, reader);
        }

        if (options.ReadPlayerActorTruth)
        {
            return RunReadPlayerActorTruthMode(options, process, target, reader);
        }

        if (options.DumpPlayerActorTruthChain)
        {
            return RunDumpPlayerActorTruthChainMode(options, process, target, reader);
        }

        if (options.ReadPlayerOrientation)
        {
            return RunReadPlayerOrientationLiveCompatibilityMode(options, process, target, reader);
        }

        if (options.RecordSession)
        {
            return RunRecordSessionMode(options, process, target, reader);
        }

        var address = options.Address!.Value;
        var length = options.Length!.Value;

        if (!reader.TryReadBytes(address, length, out var bytes, out var readError))
        {
            Console.Error.WriteLine(readError ?? "Memory read failed.");
            return 1;
        }

        if (options.JsonOutput)
        {
            var memoryReadResult = new MemoryReadResult(
                Mode: "memory-read",
                ProcessId: target.ProcessId,
                ProcessName: target.ProcessName,
                ModuleName: target.ModuleName,
                MainWindowTitle: target.MainWindowTitle,
                Address: $"0x{address.ToInt64():X}",
                Length: bytes.Length,
                BytesHex: Convert.ToHexString(bytes));

            Console.WriteLine(JsonOutput.Serialize(memoryReadResult));
            return 0;
        }

        Console.WriteLine($"Read {bytes.Length} bytes from 0x{address.ToInt64():X}.");
        Console.WriteLine();
        Console.WriteLine(HexDumpFormatter.Format(bytes, address));

        return 0;
    }

    private static int RunKillRiftErrorHandlerMode(ReaderOptions options, ProcessTarget target, Process process)
    {
        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);
        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open a memory-reading handle for the target process.");
            return 1;
        }

        var result = DebugTraceWorker.ClearBlockingRiftErrorHandler(process, reader);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return result.Error is null ? 0 : 1;
        }

        Console.WriteLine("# **✅ RESULT**");
        Console.WriteLine();
        Console.WriteLine($"Process: {result.ProcessName} [{result.ProcessId}]");
        Console.WriteLine($"Status: {result.Status}");
        Console.WriteLine($"DebuggerPresent(before): {result.DebuggerPresentBefore}");
        Console.WriteLine($"DebuggerPresent(after): {result.DebuggerPresentAfter}");
        Console.WriteLine($"HelperFound: {result.HelperFound}");
        Console.WriteLine($"HelperStopped: {result.HelperStopped}");

        if (result.HelperFound)
        {
            Console.WriteLine($"Helper: {result.HelperImageName} [{result.HelperProcessId}]");
        }

        if (!string.IsNullOrWhiteSpace(result.Error))
        {
            Console.WriteLine($"Error: {result.Error}");
        }

        if (result.Warnings.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine("Warnings:");
            foreach (var warning in result.Warnings)
            {
                Console.WriteLine($"- {warning}");
            }
        }

        return result.Error is null ? 0 : 1;
    }

    private static int RunSessionSummaryMode(ReaderOptions options)
    {
        var inspection = BuildSessionInspectResult(options.SessionDirectory, out var loadError);
        if (inspection is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the session package manifest.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(inspection));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client artifacts and processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(SessionSummaryTextFormatter.Format(inspection));
        return 0;
    }

    private static int RunDebugTraceSummaryMode(ReaderOptions options)
    {
        var inspection = DebugTracePackageLoader.TryInspect(options.DebugTraceDirectory, out var loadError);
        if (inspection is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the debug trace package.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(inspection));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client artifacts and processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(DebugTraceSummaryTextFormatter.Format(inspection));
        return 0;
    }

    private static int RunDebugWorkerMode(ReaderOptions options)
    {
        var request = DebugTraceRequestBuilder.TryLoadRequest(options.DebugRequestFile, out var loadError);
        if (request is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the debug trace request.");
            return 1;
        }

        return DebugTraceWorker.Execute(request);
    }

    private static int RunDebugTraceMode(ReaderOptions options, Process process, ProcessTarget target)
    {
        var request = DebugTraceRequestBuilder.TryBuild(options, process, target, out var requestError);
        if (request is null)
        {
            Console.Error.WriteLine(requestError ?? "Unable to build the debug trace request.");
            return 1;
        }

        var requestFile = DebugTraceRequestBuilder.WriteRequestFile(request);
        var startInfo = BuildDebugWorkerStartInfo(requestFile);

        using var worker = Process.Start(startInfo);
        if (worker is null)
        {
            Console.Error.WriteLine("Unable to start the internal debug worker.");
            return 1;
        }

        var workerStdout = worker.StandardOutput.ReadToEnd();
        var workerStderr = worker.StandardError.ReadToEnd();
        worker.WaitForExit();

        var inspection = DebugTracePackageLoader.TryInspect(request.OutputDirectory, out var inspectError);
        if (inspection is not null)
        {
            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(inspection));
            }
            else
            {
                Console.WriteLine(DebugTraceSummaryTextFormatter.Format(inspection));
            }
        }
        else if (!string.IsNullOrWhiteSpace(inspectError))
        {
            Console.Error.WriteLine(inspectError);
        }

        if (!string.IsNullOrWhiteSpace(workerStdout) && !options.JsonOutput)
        {
            Console.WriteLine(workerStdout.TrimEnd());
        }

        if (!string.IsNullOrWhiteSpace(workerStderr))
        {
            Console.Error.WriteLine(workerStderr.TrimEnd());
        }

        return worker.ExitCode;
    }

    private static int RunCheatEngineProbeMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var document = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        if (document?.Current?.Player is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest ReaderBridge export for Cheat Engine probe generation.");
            return 1;
        }

        var outputFile = ResolveCheatEngineProbeOutputFile(options.CheatEngineProbeFile);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        CheatEngineProbeExportResult exportResult;

        try
        {
            exportResult = CheatEngineProbeScriptWriter.WriteProbeScript(
                reader,
                target,
                document,
                inspectionRadius,
                options.MaxHits,
                outputFile);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to generate the Cheat Engine probe script: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(exportResult));
            return 0;
        }

        Console.WriteLine($"Cheat Engine probe script: {exportResult.OutputFile}");
        Console.WriteLine($"Source export:              {exportResult.ReaderBridgeSourceFile}");
        Console.WriteLine($"Player:                     {exportResult.PlayerName ?? "n/a"}");

        if (exportResult.PlayerLevel.HasValue)
        {
            Console.WriteLine($"Level:                      {exportResult.PlayerLevel.Value}");
        }

        if (exportResult.PlayerHealth.HasValue || exportResult.PlayerHealthMax.HasValue)
        {
            Console.WriteLine($"Health:                     {exportResult.PlayerHealth?.ToString() ?? "n/a"}/{exportResult.PlayerHealthMax?.ToString() ?? "n/a"}");
        }

        if (!string.IsNullOrWhiteSpace(exportResult.LocationName))
        {
            Console.WriteLine($"Location:                   {exportResult.LocationName}");
        }

        if (!string.IsNullOrWhiteSpace(exportResult.CoordText))
        {
            Console.WriteLine($"Coords:                     {exportResult.CoordText}");
        }

        Console.WriteLine($"Families:                   {exportResult.FamilyCount}");
        Console.WriteLine($"Representative hits:        {exportResult.HitCount}");
        Console.WriteLine();
        Console.WriteLine("Load the script in Cheat Engine, or install the autorun bootstrap and restart Cheat Engine.");
        Console.WriteLine("Then run: RiftReaderProbe.attachAndPopulate()");
        return 0;
    }

    private static int RunPlayerSignatureCaptureMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var document = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        if (document?.Current?.Player is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest ReaderBridge export for player-signature capture.");
            return 1;
        }

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var outputFile = string.IsNullOrWhiteSpace(options.CaptureFile)
            ? null
            : Path.GetFullPath(options.CaptureFile);

        PlayerSignatureProbeCapture capture;

        try
        {
            capture = PlayerSignatureProbeCaptureBuilder.CaptureBestFamily(
                reader,
                target.ProcessId,
                target.ProcessName,
                document,
                inspectionRadius,
                options.MaxHits,
                options.CaptureLabel,
                outputFile);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to capture the current best player-signature family: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(capture));
            return 0;
        }

        Console.WriteLine(PlayerSignatureProbeCaptureTextFormatter.Format(capture));
        return 0;
    }

    private static int RunReadPlayerCurrentMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var document = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        if (document?.Current?.Player is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest ReaderBridge export for player-current reading.");
            return 1;
        }

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        PlayerCurrentReadResult result;

        try
        {
            result = PlayerCurrentReader.ReadCurrent(
                reader,
                target.ProcessId,
                target.ProcessName,
                document,
                inspectionRadius,
                options.MaxHits);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the current player snapshot: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerCurrentReadTextFormatter.Format(result));
        return 0;
    }

    private static int RunFindPlayerOrientationCandidateMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        var actorCoordAnchorResult = TryReadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            refreshIfNeeded: true,
            out _);
        var effectiveSnapshotDocument = TryEnsurePlayerCoordSnapshot(snapshotDocument, actorCoordAnchorResult);
        if (effectiveSnapshotDocument?.Current?.Player?.Coord is null)
        {
            Console.Error.WriteLine("Unable to derive live player coordinates for player orientation candidate search.");
            return 1;
        }

        PlayerOrientationCandidateSearchResult result;
        try
        {
            result = PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                effectiveSnapshotDocument,
                options.MaxHits,
                orientationCandidateLedgerFile: options.OrientationCandidateLedgerFile);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to find a live player orientation candidate: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine("Player orientation candidate search");
        Console.WriteLine($"Player:                      {result.PlayerName ?? "n/a"}");
        Console.WriteLine($"Candidate count:             {result.CandidateCount}");
        Console.WriteLine($"Pointer-hop candidate count: {result.PointerHopCandidateCount}");

        if (result.BestPointerHopCandidate is not null)
        {
            Console.WriteLine($"Best pointer-hop candidate:  {result.BestPointerHopCandidate.Address} @ {result.BestPointerHopCandidate.BasisPrimaryForwardOffset}");
            Console.WriteLine($"Pointer-hop yaw/pitch (deg): {result.BestPointerHopCandidate.PreferredEstimate.YawDegrees?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a"} / {result.BestPointerHopCandidate.PreferredEstimate.PitchDegrees?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a"}");
        }
        else if (result.BestCandidate is not null)
        {
            Console.WriteLine($"Best local candidate:        {result.BestCandidate.Address} @ {result.BestCandidate.BasisPrimaryForwardOffset}");
            Console.WriteLine($"Local yaw/pitch (deg):       {result.BestCandidate.PreferredEstimate.YawDegrees?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a"} / {result.BestCandidate.PreferredEstimate.PitchDegrees?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a"}");
        }

        foreach (var note in result.Notes)
        {
            Console.WriteLine($"- {note}");
        }

        return 0;
    }

    private static int RunReadTargetCurrentMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var document = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        if (document?.Current?.Target is null && document?.Current?.Player is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest ReaderBridge export for target-current reading.");
            return 1;
        }

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        TargetCurrentReadResult result;

        try
        {
            result = TargetCurrentReader.ReadCurrent(
                reader,
                target.ProcessId,
                target.ProcessName,
                document!,
                inspectionRadius,
                options.MaxHits);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the current target snapshot: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(TargetCurrentReadTextFormatter.Format(result));
        return 0;
    }

    private static int RunReadPlayerCoordAnchorMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(options.PlayerCoordTraceFile, out var loadError);
        if (traceDocument?.Trace is null || string.IsNullOrWhiteSpace(traceDocument.SourceFile))
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest player coord trace artifact.");
            return 1;
        }

        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        var result = TryReadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            refreshIfNeeded: true,
            out var anchorError);
        if (result is null)
        {
            Console.Error.WriteLine(anchorError ?? "Unable to read the current player coord anchor.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerCoordAnchorReadTextFormatter.Format(result));
        return 0;
    }

    private static int RunReadPlayerActorCoordsMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        var anchorResult = TryReadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            refreshIfNeeded: true,
            out _);

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        PlayerActorCoordReadResult result;
        try
        {
            result = PlayerActorCoordReader.ReadCurrent(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
                inspectionRadius,
                options.MaxHits,
                anchorResult);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the current player actor coordinates: {ex.Message}");
            return 1;
        }

        result = EnrichPlayerActorCoordResultWithTruthChainContext(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            anchorResult,
            result);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerActorCoordReadTextFormatter.Format(result));
        return 0;
    }

    private static PlayerActorCoordReadResult EnrichPlayerActorCoordResultWithTruthChainContext(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCoordAnchorReadResult? anchorResult,
        PlayerActorCoordReadResult result)
    {
        var notes = result.Notes.Count == 0
            ? new List<string>()
            : result.Notes.ToList();

        var effectiveSnapshotDocument = TryEnsurePlayerCoordSnapshot(snapshotDocument, anchorResult);
        if (effectiveSnapshotDocument?.Current?.Player?.Coord is null)
        {
            notes.Add("Skipped root-family structural context because no live player-coordinate snapshot could be derived.");
            return result with { Notes = notes };
        }

        PlayerOrientationCandidateSearchResult orientationSearchResult;
        try
        {
            orientationSearchResult = PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                effectiveSnapshotDocument,
                options.MaxHits,
                orientationCandidateLedgerFile: options.OrientationCandidateLedgerFile);
        }
        catch (Exception ex)
        {
            notes.Add($"Skipped root-family structural context because live actor-orientation discovery failed: {ex.Message}");
            return result with { Notes = notes };
        }

        PlayerActorOrientationReadResult orientationResult;
        try
        {
            orientationResult = PlayerActorOrientationReader.ReadCurrent(
                effectiveSnapshotDocument,
                anchorResult,
                orientationSearchResult);
        }
        catch (Exception ex)
        {
            notes.Add($"Skipped root-family structural context because live actor-orientation reading failed: {ex.Message}");
            return result with { Notes = notes };
        }

        var truthNotes = new List<string>
        {
            "Actor-coordinate read enriched with live truth-chain stability context."
        };
        var truthResult = new PlayerActorTruthReadResult(
            Mode: "player-actor-truth",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ReaderBridgeSourceFile: effectiveSnapshotDocument.SourceFile,
            TraceSourceFile: anchorResult?.SourceFile,
            TraceAvailable: anchorResult is not null,
            TraceMatchesProcess: anchorResult?.TraceMatchesProcess == true,
            CoordBootstrapSource: orientationResult.CoordBootstrapSource,
            OrientationResolutionSource: orientationResult.ResolutionSource,
            Coordinates: result,
            Orientation: orientationResult,
            BestContainerChain: null,
            BestRootFamily: null,
            RootFamilySummary: null,
            Notes: truthNotes);

        var structuralContext = AnalyzeTruthStructuralContext(
            options,
            process,
            target,
            reader,
            truthResult);
        var bestContainerChain = structuralContext.BestContainerChain;
        var bestRootFamily = structuralContext.BestRootFamily;
        var rootFamilySummary = structuralContext.RootFamilySummary;

        if (bestRootFamily is not null)
        {
            notes.Add($"Best root family {bestRootFamily.RegionBase} held {bestRootFamily.ObservationCount}/{bestRootFamily.StabilitySampleCount} observations across {bestRootFamily.DistinctAddressCount} root instances.");
        }
        else
        {
            notes.Add("Truth-chain stability sampling did not produce a root-family candidate for the current actor-coordinate read.");
        }

        if (bestContainerChain?.RootAddress is not null)
        {
            notes.Add($"Best parent/root chain during coord enrichment: {bestContainerChain.ParentAddress ?? "n/a"} -> {bestContainerChain.RootAddress} ({bestContainerChain.RootObservationCount}/{bestContainerChain.StabilitySampleCount} root observations).");
        }

        if (rootFamilySummary is not null)
        {
            notes.Add($"Canonical root-family instance for coord truth: {rootFamilySummary.CanonicalInstanceAddress} in {rootFamilySummary.RegionBase} ({rootFamilySummary.CanonicalInstanceObservationCount}/{rootFamilySummary.StabilitySampleCount} observations).");
        }

        foreach (var note in structuralContext.Notes)
        {
            if (!notes.Contains(note, StringComparer.Ordinal))
            {
                notes.Add(note);
            }
        }

        return result with
        {
            BestContainerChain = bestContainerChain,
            BestRootFamily = bestRootFamily,
            RootFamilySummary = rootFamilySummary,
            Notes = notes
        };
    }

    private static PlayerActorTruthStructuralContext AnalyzeTruthStructuralContext(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        PlayerActorTruthReadResult truthResult)
    {
        var notes = new List<string>();
        var stabilityObservations = CollectTruthChainObservations(
            options,
            process,
            target,
            reader,
            truthResult,
            notes);
        var bestContainerChain = BuildBestContainerChain(stabilityObservations);
        var readableRegions = reader.EnumerateMemoryRegions()
            .Where(static region => region.IsCommitted && region.IsReadable)
            .ToArray();
        var rootFamilyCandidates = AnalyzeRootFamilyCandidates(
            reader,
            readableRegions,
            stabilityObservations,
            RootFamilyComparisonBytes,
            notes);
        var bestRootFamily = rootFamilyCandidates.FirstOrDefault();
        var rootFamilySummary = BuildRootFamilySummary(
            bestContainerChain,
            bestRootFamily,
            stabilityObservations,
            truthResult.Orientation.RootAddress);

        return new PlayerActorTruthStructuralContext(
            StabilityObservations: stabilityObservations,
            BestContainerChain: bestContainerChain,
            BestRootFamily: bestRootFamily,
            RootFamilySummary: rootFamilySummary,
            Notes: notes);
    }

    private static PlayerActorTruthRootFamilySummary? BuildRootFamilySummary(
        PlayerActorTruthBestContainerChain? bestContainerChain,
        PlayerActorTruthRootFamilyCandidate? bestRootFamily,
        IReadOnlyList<PlayerActorTruthChainObservation> observations,
        string? preferredCurrentRootAddress)
    {
        if (bestRootFamily is null)
        {
            return null;
        }

        var canonicalInstanceAddress = SelectCanonicalRootFamilyInstanceAddress(
            bestContainerChain,
            bestRootFamily,
            observations,
            preferredCurrentRootAddress);
        var canonicalInstanceObservationCount = CountRootFamilyObservations(
            observations,
            canonicalInstanceAddress);

        return new PlayerActorTruthRootFamilySummary(
            RegionBase: bestRootFamily.RegionBase,
            CanonicalInstanceAddress: canonicalInstanceAddress,
            CanonicalInstanceObservationCount: canonicalInstanceObservationCount,
            RepresentativeAddress: bestRootFamily.RepresentativeAddress,
            RepresentativeObservationCount: bestRootFamily.RepresentativeObservationCount,
            ObservationCount: bestRootFamily.ObservationCount,
            DistinctAddressCount: bestRootFamily.DistinctAddressCount,
            StabilitySampleCount: bestRootFamily.StabilitySampleCount,
            Score: bestRootFamily.Score);
    }

    private static string SelectCanonicalRootFamilyInstanceAddress(
        PlayerActorTruthBestContainerChain? bestContainerChain,
        PlayerActorTruthRootFamilyCandidate bestRootFamily,
        IReadOnlyList<PlayerActorTruthChainObservation> observations,
        string? preferredCurrentRootAddress)
    {
        var rootCounts = observations
            .Where(observation => bestRootFamily.MemberAddresses.Contains(observation.OrientationRootAddress, StringComparer.OrdinalIgnoreCase))
            .GroupBy(static observation => observation.OrientationRootAddress, StringComparer.OrdinalIgnoreCase)
            .Select(group => new
            {
                Address = group.Key,
                Count = group.Count(),
                IsCurrentRoot = !string.IsNullOrWhiteSpace(preferredCurrentRootAddress) &&
                    string.Equals(group.Key, preferredCurrentRootAddress, StringComparison.OrdinalIgnoreCase),
                IsBestChainRoot = !string.IsNullOrWhiteSpace(bestContainerChain?.RootAddress) &&
                    string.Equals(group.Key, bestContainerChain.RootAddress, StringComparison.OrdinalIgnoreCase),
                IsRepresentative = string.Equals(group.Key, bestRootFamily.RepresentativeAddress, StringComparison.OrdinalIgnoreCase)
            })
            .OrderByDescending(static item => item.Count)
            .ThenByDescending(static item => item.IsCurrentRoot)
            .ThenByDescending(static item => item.IsBestChainRoot)
            .ThenByDescending(static item => item.IsRepresentative)
            .ThenBy(static item => item.Address, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();

        return rootCounts?.Address
            ?? bestContainerChain?.RootAddress
            ?? bestRootFamily.RepresentativeAddress;
    }

    private static int CountRootFamilyObservations(
        IReadOnlyList<PlayerActorTruthChainObservation> observations,
        string? rootAddress)
    {
        if (string.IsNullOrWhiteSpace(rootAddress))
        {
            return 0;
        }

        return observations.Count(observation =>
            string.Equals(observation.OrientationRootAddress, rootAddress, StringComparison.OrdinalIgnoreCase));
    }

    private sealed record PlayerActorTruthStructuralContext(
        IReadOnlyList<PlayerActorTruthChainObservation> StabilityObservations,
        PlayerActorTruthBestContainerChain? BestContainerChain,
        PlayerActorTruthRootFamilyCandidate? BestRootFamily,
        PlayerActorTruthRootFamilySummary? RootFamilySummary,
        IReadOnlyList<string> Notes);

    private static int RunReadPlayerActorOrientationMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        var anchorResult = TryReadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            refreshIfNeeded: true,
            out _);

        var effectiveSnapshotDocument = TryEnsurePlayerCoordSnapshot(snapshotDocument, anchorResult);
        if (effectiveSnapshotDocument?.Current?.Player?.Coord is null)
        {
            Console.Error.WriteLine("Unable to derive live player coordinates for player actor-orientation reading.");
            return 1;
        }

        PlayerOrientationCandidateSearchResult searchResult;
        try
        {
            searchResult = PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                effectiveSnapshotDocument,
                options.MaxHits,
                orientationCandidateLedgerFile: options.OrientationCandidateLedgerFile);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to find a live player actor-orientation candidate: {ex.Message}");
            return 1;
        }

        PlayerActorOrientationReadResult result;
        try
        {
            result = PlayerActorOrientationReader.ReadCurrent(
                effectiveSnapshotDocument,
                anchorResult,
                searchResult);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the current player actor orientation: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerActorOrientationReadTextFormatter.Format(result));
        return 0;
    }

    private static int RunReadPlayerOrientationLiveCompatibilityMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        return RunReadPlayerActorOrientationMode(options, process, target, reader);
    }

    private static int RunReadPlayerActorTruthMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        if (!TryBuildPlayerActorTruthResult(options, process, target, reader, out var result, out var error))
        {
            Console.Error.WriteLine(error ?? "Unable to read the current player actor truth.");
            return 1;
        }

        var enrichedResult = EnrichPlayerActorTruthResultWithStructuralContext(
            options,
            process,
            target,
            reader,
            result!);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(enrichedResult));
            return 0;
        }

        Console.WriteLine(PlayerActorTruthReadTextFormatter.Format(enrichedResult));
        return 0;
    }

    private static int RunDumpPlayerActorTruthChainMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var truthSearchOptions = options with
        {
            MaxHits = options.TruthSearchMaxHits
        };

        if (!TryBuildPlayerActorTruthResult(truthSearchOptions, process, target, reader, out var truthResult, out var error))
        {
            Console.Error.WriteLine(error ?? "Unable to read the current player actor truth for chain dumping.");
            return 1;
        }

        var resolvedTruthResult = truthResult!;

        var notes = new List<string>
        {
            "Chain dump captured the current coord truth object, the canonical orientation surface, and pointer backrefs for each parsed address."
        };
        var unifiedTruthObjectAddress = string.Equals(
            resolvedTruthResult.Coordinates.ObjectBaseAddress,
            resolvedTruthResult.Orientation.SelectedAddress,
            StringComparison.OrdinalIgnoreCase)
            ? resolvedTruthResult.Coordinates.ObjectBaseAddress
            : null;
        if (!string.IsNullOrWhiteSpace(unifiedTruthObjectAddress))
        {
            notes.Add($"Coord and orientation truth unified on the same live object surface at {unifiedTruthObjectAddress}.");
        }
        var stabilityObservations = CollectTruthChainObservations(
            truthSearchOptions,
            process,
            target,
            reader,
            resolvedTruthResult,
            notes);
        var unifiedTruthObservationCount = stabilityObservations.Count(observation =>
            !string.IsNullOrWhiteSpace(observation.UnifiedTruthObjectAddress));
        var bestContainerChain = BuildBestContainerChain(stabilityObservations);

        var windowLength = Math.Max(options.ScanContextBytes, 128);
        var pointerWidth = options.PointerWidth;
        var pointerScanMaxHits = options.MaxHits;
        var readableRegions = reader.EnumerateMemoryRegions()
            .Where(static region => region.IsCommitted && region.IsReadable)
            .ToArray();
        var rootFamilyCandidates = AnalyzeRootFamilyCandidates(
            reader,
            readableRegions,
            stabilityObservations,
            RootFamilyComparisonBytes,
            notes);
        var bestRootFamily = rootFamilyCandidates.FirstOrDefault();
        var rootFamilySummary = BuildRootFamilySummary(
            bestContainerChain,
            bestRootFamily,
            stabilityObservations,
            resolvedTruthResult.Orientation.RootAddress);

        var knownTargets = new Dictionary<long, string>
        {
            [TryParseRequiredAddress(resolvedTruthResult.Coordinates.ObjectBaseAddress)] = "coord-object",
            [TryParseRequiredAddress(resolvedTruthResult.Orientation.SelectedAddress)] = "orientation-object",
            [TryParseRequiredAddress(resolvedTruthResult.Orientation.ParentAddress)] = "orientation-parent",
            [TryParseRequiredAddress(resolvedTruthResult.Orientation.RootAddress)] = "orientation-root"
        };

        var coordWindow = TryBuildTruthObjectWindow(
            reader,
            resolvedTruthResult.Coordinates.ObjectBaseAddress,
            "coord-object",
            windowLength,
            pointerWidth,
            readableRegions,
            knownTargets,
            notes);
        var orientationWindow = TryBuildTruthObjectWindow(
            reader,
            resolvedTruthResult.Orientation.SelectedAddress,
            "orientation-object",
            windowLength,
            pointerWidth,
            readableRegions,
            knownTargets,
            notes);
        var orientationParentWindow = TryBuildTruthObjectWindow(
            reader,
            resolvedTruthResult.Orientation.ParentAddress,
            "orientation-parent",
            windowLength,
            pointerWidth,
            readableRegions,
            knownTargets,
            notes);
        var orientationRootWindow = TryBuildTruthObjectWindow(
            reader,
            resolvedTruthResult.Orientation.RootAddress,
            "orientation-root",
            windowLength,
            pointerWidth,
            readableRegions,
            knownTargets,
            notes);

        var coordBackrefs = RunPointerScanOrEmpty(
            reader,
            target,
            resolvedTruthResult.Coordinates.ObjectBaseAddress,
            pointerWidth,
            windowLength,
            pointerScanMaxHits,
            notes,
            "coord-object");
        var orientationBackrefs = RunPointerScanOrEmpty(
            reader,
            target,
            resolvedTruthResult.Orientation.SelectedAddress,
            pointerWidth,
            windowLength,
            pointerScanMaxHits,
            notes,
            "orientation-object");
        var orientationParentBackrefs = RunPointerScanOrEmpty(
            reader,
            target,
            resolvedTruthResult.Orientation.ParentAddress,
            pointerWidth,
            windowLength,
            pointerScanMaxHits,
            notes,
            "orientation-parent");

        var secondHopSeedLimit = Math.Min(TruthChainSecondHopSeedLimitPerSurface, pointerScanMaxHits);
        var secondHopMaxHits = Math.Min(TruthChainSecondHopPointerScanMaxHits, pointerScanMaxHits);
        var slotCorrelations = FindSlotCorrelations(
            coordWindow,
            orientationWindow,
            orientationParentWindow,
            orientationRootWindow);
        var parentContainerCandidates = FindParentContainerCandidates(
            reader,
            target,
            readableRegions,
            resolvedTruthResult.Orientation.ParentAddress,
            resolvedTruthResult.Orientation.RootAddress,
            orientationParentWindow,
            orientationParentBackrefs,
            pointerWidth,
            windowLength,
            stabilityObservations,
            notes);
        var sharedAncestorCandidates = FindSharedAncestorCandidates(
            reader,
            target,
            new Dictionary<string, PointerScanResult>(StringComparer.OrdinalIgnoreCase)
            {
                ["coord-object"] = coordBackrefs,
                ["orientation-object"] = orientationBackrefs,
                ["orientation-parent"] = orientationParentBackrefs
            },
            pointerWidth,
            windowLength,
            secondHopSeedLimit,
            secondHopMaxHits,
            notes);

        var result = new PlayerActorTruthChainDumpResult(
            Mode: "player-actor-truth-chain-dump",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ReaderBridgeSourceFile: resolvedTruthResult.ReaderBridgeSourceFile,
            TraceSourceFile: resolvedTruthResult.TraceSourceFile,
            WindowLength: windowLength,
            PointerWidth: pointerWidth,
            PointerScanMaxHits: pointerScanMaxHits,
            SecondHopSeedLimitPerSurface: secondHopSeedLimit,
            SecondHopPointerScanMaxHits: secondHopMaxHits,
            StabilitySampleCount: TruthChainStabilitySampleCount,
            StabilitySampleDelayMilliseconds: TruthChainStabilityDelayMilliseconds,
            Truth: resolvedTruthResult,
            UnifiedTruthObjectAddress: unifiedTruthObjectAddress,
            UnifiedTruthObservationCount: unifiedTruthObservationCount,
            BestContainerChain: bestContainerChain,
            BestRootFamily: bestRootFamily,
            RootFamilySummary: rootFamilySummary,
            CoordObjectWindow: coordWindow,
            OrientationObjectWindow: orientationWindow,
            OrientationParentWindow: orientationParentWindow,
            OrientationRootWindow: orientationRootWindow,
            CoordObjectBackrefs: coordBackrefs,
            OrientationObjectBackrefs: orientationBackrefs,
            OrientationParentBackrefs: orientationParentBackrefs,
            SlotCorrelations: slotCorrelations,
            ParentContainerCandidates: parentContainerCandidates,
            RootFamilyCandidates: rootFamilyCandidates,
            StabilityObservations: stabilityObservations,
            SharedAncestorCandidates: sharedAncestorCandidates,
            Notes: notes)
        {
            TruthSearchMaxHits = truthSearchOptions.MaxHits
        };

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerActorTruthChainDumpTextFormatter.Format(result));
        return 0;
    }

    private static int RunRefreshPlayerCoordTraceMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        if (!TryRefreshPlayerCoordTraceArtifact(options, process, target, reader, out var refreshError))
        {
            Console.Error.WriteLine(refreshError ?? "Unable to refresh the current player coord trace.");
            return 1;
        }

        var anchorResult = TryLoadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            out var anchorError);
        if (anchorResult is null)
        {
            Console.Error.WriteLine(anchorError ?? "Unable to load the refreshed player coord anchor.");
            return 1;
        }

        var traceSourceFile = ResolvePlayerCoordTraceOutputFile(options.PlayerCoordTraceFile);
        var result = new PlayerCoordTraceRefreshResult(
            Mode: "player-coord-trace-refresh",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            TraceSourceFile: traceSourceFile,
            RefreshPerformed: true,
            Anchor: anchorResult);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(PlayerCoordTraceRefreshTextFormatter.Format(result));
        return 0;
    }

    private static bool TryBuildPlayerActorTruthResult(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        out PlayerActorTruthReadResult? result,
        out string? error)
    {
        result = null;
        error = null;

        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out _);

        var anchorResult = TryReadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            refreshIfNeeded: true,
            out _);

        var effectiveSnapshotDocument = TryEnsurePlayerCoordSnapshot(snapshotDocument, anchorResult);
        if (effectiveSnapshotDocument?.Current?.Player?.Coord is null)
        {
            error = "Unable to derive live player coordinates for player actor-truth reading.";
            return false;
        }

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        PlayerActorCoordReadResult coordResult;
        try
        {
            coordResult = PlayerActorCoordReader.ReadCurrent(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
                inspectionRadius,
                options.MaxHits,
                anchorResult);
        }
        catch (Exception ex)
        {
            error = $"Unable to read the current player actor coordinates for player actor-truth: {ex.Message}";
            return false;
        }

        PlayerOrientationCandidateSearchResult orientationSearchResult;
        try
        {
            orientationSearchResult = PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                effectiveSnapshotDocument,
                options.MaxHits,
                orientationCandidateLedgerFile: options.OrientationCandidateLedgerFile);
        }
        catch (Exception ex)
        {
            error = $"Unable to find a live player actor-orientation candidate for player actor-truth: {ex.Message}";
            return false;
        }

        PlayerActorOrientationReadResult orientationResult;
        try
        {
            orientationResult = PlayerActorOrientationReader.ReadCurrent(
                effectiveSnapshotDocument,
                anchorResult,
                orientationSearchResult);
        }
        catch (Exception ex)
        {
            error = $"Unable to read the current player actor orientation for player actor-truth: {ex.Message}";
            return false;
        }

        var notes = new List<string>
        {
            "Combined actor-truth read succeeded through the trace-backed coord source object and the canonical pointer-hop orientation basis."
        };

        if (!string.Equals(coordResult.ObjectBaseAddress, orientationResult.SelectedAddress, StringComparison.OrdinalIgnoreCase))
        {
            notes.Add($"Coord truth and orientation truth currently resolve on different live object surfaces ({coordResult.ObjectBaseAddress ?? "n/a"} vs {orientationResult.SelectedAddress}).");
        }

        result = new PlayerActorTruthReadResult(
            Mode: "player-actor-truth",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ReaderBridgeSourceFile: effectiveSnapshotDocument.SourceFile,
            TraceSourceFile: anchorResult?.SourceFile,
            TraceAvailable: anchorResult is not null,
            TraceMatchesProcess: anchorResult?.TraceMatchesProcess == true,
            CoordBootstrapSource: orientationResult.CoordBootstrapSource,
            OrientationResolutionSource: orientationResult.ResolutionSource,
            Coordinates: coordResult,
            Orientation: orientationResult,
            BestContainerChain: null,
            BestRootFamily: null,
            RootFamilySummary: null,
            Notes: notes);

        return true;
    }

    private static PlayerActorTruthReadResult EnrichPlayerActorTruthResultWithStructuralContext(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        PlayerActorTruthReadResult result)
    {
        var structuralContext = AnalyzeTruthStructuralContext(
            options,
            process,
            target,
            reader,
            result);
        var notes = result.Notes.Count == 0
            ? new List<string>()
            : result.Notes.ToList();

        if (structuralContext.BestRootFamily is not null)
        {
            notes.Add($"Best root family {structuralContext.BestRootFamily.RegionBase} held {structuralContext.BestRootFamily.ObservationCount}/{structuralContext.BestRootFamily.StabilitySampleCount} observations across {structuralContext.BestRootFamily.DistinctAddressCount} root instances.");
        }

        if (structuralContext.BestContainerChain?.RootAddress is not null)
        {
            notes.Add($"Best parent/root chain during actor-truth enrichment: {structuralContext.BestContainerChain.ParentAddress ?? "n/a"} -> {structuralContext.BestContainerChain.RootAddress} ({structuralContext.BestContainerChain.RootObservationCount}/{structuralContext.BestContainerChain.StabilitySampleCount} root observations).");
        }

        if (structuralContext.RootFamilySummary is not null)
        {
            notes.Add($"Canonical root-family instance for actor truth: {structuralContext.RootFamilySummary.CanonicalInstanceAddress} in {structuralContext.RootFamilySummary.RegionBase} ({structuralContext.RootFamilySummary.CanonicalInstanceObservationCount}/{structuralContext.RootFamilySummary.StabilitySampleCount} observations).");
        }

        foreach (var note in structuralContext.Notes)
        {
            if (!notes.Contains(note, StringComparer.Ordinal))
            {
                notes.Add(note);
            }
        }

        return result with
        {
            BestContainerChain = structuralContext.BestContainerChain,
            BestRootFamily = structuralContext.BestRootFamily,
            RootFamilySummary = structuralContext.RootFamilySummary,
            Notes = notes
        };
    }

    private static ReaderBridgeSnapshotDocument? TryEnsurePlayerCoordSnapshot(
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCoordAnchorReadResult? anchorResult = null)
    {
        if (snapshotDocument?.Current?.Player?.Coord is { X: not null, Y: not null, Z: not null })
        {
            return snapshotDocument;
        }

        var sample = anchorResult?.SourceObjectSample;
        if (sample?.CoordX is null || sample.CoordY is null || sample.CoordZ is null)
        {
            sample = anchorResult?.MemorySample is null
                ? null
                : new PlayerCoordAnchorSourceSample(
                    AddressHex: anchorResult.MemorySample.AddressHex,
                    CoordX: anchorResult.MemorySample.CoordX,
                    CoordY: anchorResult.MemorySample.CoordY,
                    CoordZ: anchorResult.MemorySample.CoordZ);
        }

        if (sample?.CoordX is null || sample.CoordY is null || sample.CoordZ is null)
        {
            return snapshotDocument;
        }

        var coord = new ValidatorCoordinateSnapshot(sample.CoordX.Value, sample.CoordY.Value, sample.CoordZ.Value);
        var existingCurrent = snapshotDocument?.Current;
        var existingPlayer = existingCurrent?.Player;
        var enrichedPlayer = existingPlayer is null
            ? new ReaderBridgeUnitSnapshot(
                Id: "player",
                Name: null,
                Level: anchorResult?.MemorySample?.Level,
                Calling: null,
                Guild: null,
                Relation: null,
                Role: null,
                Player: true,
                Combat: null,
                Pvp: null,
                Hp: anchorResult?.MemorySample?.Health,
                HpMax: null,
                HpPct: null,
                Absorb: null,
                Vitality: null,
                ResourceKind: null,
                Resource: null,
                ResourceMax: null,
                ResourcePct: null,
                Mana: null,
                ManaMax: null,
                Energy: null,
                EnergyMax: null,
                Power: null,
                Charge: null,
                ChargeMax: null,
                ChargePct: null,
                Planar: null,
                PlanarMax: null,
                PlanarPct: null,
                Combo: null,
                Zone: null,
                LocationName: null,
                Coord: coord,
                Distance: null,
                Ttd: null,
                TtdText: null,
                Cast: null)
            : existingPlayer with
            {
                Coord = coord,
                Level = existingPlayer.Level ?? anchorResult?.MemorySample?.Level,
                Hp = existingPlayer.Hp ?? anchorResult?.MemorySample?.Health
            };

        var current = existingCurrent is null
            ? new ReaderBridgeSnapshot(
                SchemaVersion: snapshotDocument?.SchemaVersion,
                Status: null,
                ExportReason: snapshotDocument?.LastReason,
                ExportCount: snapshotDocument?.ExportCount,
                GeneratedAtRealtime: snapshotDocument?.LastExportAt,
                SourceMode: null,
                SourceAddon: null,
                SourceVersion: null,
                Hud: null,
                Player: enrichedPlayer,
                Target: null,
                OrientationProbe: null,
                PlayerBuffLines: Array.Empty<string>(),
                PlayerDebuffLines: Array.Empty<string>(),
                TargetBuffLines: Array.Empty<string>(),
                TargetDebuffLines: Array.Empty<string>())
            : existingCurrent with { Player = enrichedPlayer };

        return new ReaderBridgeSnapshotDocument(
            SourceFile: snapshotDocument?.SourceFile ?? "trace-derived-player-coords",
            LoadedAtUtc: snapshotDocument?.LoadedAtUtc ?? DateTimeOffset.UtcNow,
            SchemaVersion: snapshotDocument?.SchemaVersion,
            LastExportAt: snapshotDocument?.LastExportAt,
            LastReason: snapshotDocument?.LastReason,
            ExportCount: snapshotDocument?.ExportCount,
            Current: current);
    }

    private static PlayerCoordAnchorReadResult? TryReadPlayerCoordAnchorResult(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        bool refreshIfNeeded,
        out string? error)
    {
        error = null;

        var anchorResult = TryLoadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            out var loadError);

        if (!refreshIfNeeded || !ShouldRefreshPlayerCoordAnchor(anchorResult))
        {
            error = loadError;
            return anchorResult;
        }

        if (!TryRefreshPlayerCoordTraceArtifact(options, process, target, reader, out var refreshError))
        {
            error = refreshError ?? loadError;
            return anchorResult;
        }

        var refreshedResult = TryLoadPlayerCoordAnchorResult(
            options,
            process,
            target,
            reader,
            snapshotDocument,
            out var refreshLoadError);

        error = refreshedResult is null
            ? refreshLoadError ?? refreshError ?? loadError
            : refreshLoadError;

        return refreshedResult ?? anchorResult;
    }

    private static PlayerCoordAnchorReadResult? TryLoadPlayerCoordAnchorResult(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        out string? error)
    {
        error = null;

        var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(options.PlayerCoordTraceFile, out var loadError);
        if (traceDocument?.Trace is null || string.IsNullOrWhiteSpace(traceDocument.SourceFile))
        {
            error = loadError ?? "Unable to load the latest player coord trace artifact.";
            return null;
        }

        try
        {
            return PlayerCoordAnchorReader.Read(
                reader,
                target.ProcessId,
                target.ProcessName,
                traceDocument.SourceFile,
                traceDocument,
                snapshotDocument,
                ScanTraceModulePattern(process, target, reader, traceDocument, options.ScanContextBytes));
        }
        catch (Exception ex)
        {
            error = $"Unable to read the current player coord anchor: {ex.Message}";
            return null;
        }
    }

    private static bool ShouldRefreshPlayerCoordAnchor(PlayerCoordAnchorReadResult? anchorResult)
    {
        if (anchorResult is null || !anchorResult.TraceMatchesProcess)
        {
            return true;
        }

        var coordMatch =
            anchorResult.Match?.CoordMatchesWithinTolerance == true ||
            anchorResult.SourceObjectMatch?.CoordMatchesWithinTolerance == true;

        return !coordMatch;
    }

    private static bool TryRefreshPlayerCoordTraceArtifact(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        out string? error)
    {
        error = null;

        var baselineDocument = PlayerCoordTraceAnchorLoader.TryLoad(options.PlayerCoordTraceFile, out var loadError);
        if (baselineDocument?.Trace is null)
        {
            error = loadError ?? "Unable to load the baseline player coord trace artifact for refresh.";
            return false;
        }

        var modulePattern = ScanTraceModulePattern(process, target, reader, baselineDocument, options.ScanContextBytes);
        if (modulePattern is null || !modulePattern.Found || string.IsNullOrWhiteSpace(modulePattern.RelativeOffsetHex))
        {
            error = "Unable to resolve the live coord instruction pattern for player-coord trace refresh.";
            return false;
        }
        string? lastError = null;

        for (var attempt = 1; attempt <= PlayerCoordTraceRefreshAttempts; attempt++)
        {
            var outputDirectory = ResolvePlayerCoordTraceRefreshOutputDirectory(attempt);
            var request = new DebugTraceRequest(
                SchemaVersion: DebugTraceRequestBuilder.SchemaVersion,
                Mode: "debug-trace-instruction",
                Target: new DebugTraceTargetSpec(
                    ProcessId: target.ProcessId,
                    ProcessName: target.ProcessName,
                    ModuleName: target.ModuleName,
                    MainWindowTitle: target.MainWindowTitle,
                    ProcessStartTimeUtc: TryGetProcessStartTimeUtc(process)),
                Breakpoint: new DebugTraceBreakpointSpec(
                    Kind: "instruction",
                    ResolutionMode: "module-relative",
                    Address: null,
                    ModuleName: modulePattern.ModuleName,
                    ModuleOffset: modulePattern.RelativeOffsetHex,
                    Width: null,
                    Pattern: modulePattern.Pattern,
                    SourceFile: baselineDocument.SourceFile,
                    AccessType: baselineDocument.Trace.AccessType,
                    Metadata: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                    {
                        ["instruction"] = baselineDocument.Trace.Instruction ?? string.Empty,
                        ["effectiveAddress"] = baselineDocument.Trace.EffectiveAddress ?? string.Empty,
                        ["targetAddress"] = baselineDocument.Trace.TargetAddress ?? string.Empty
                    }),
                Capture: new DebugTraceCaptureOptions(
                    StackBytes: options.DebugCaptureStackBytes,
                    MemoryWindowBytes: options.DebugCaptureMemoryWindowBytes),
                Limits: new DebugTraceLimits(
                    TimeoutMilliseconds: Math.Max(options.DebugTimeoutMilliseconds, PlayerCoordTraceRefreshTimeoutMilliseconds),
                    MaxHits: Math.Max(options.DebugMaxHits, PlayerCoordTraceRefreshMaxHits),
                    MaxEvents: Math.Max(options.DebugMaxEvents, PlayerCoordTraceRefreshMaxEvents)),
                Capabilities: new DebugTraceCapabilities(
                    PreflightValidation: true,
                    RegisterCapture: !options.DebugDisableRegisterCapture,
                    StackCapture: !options.DebugDisableStackCapture,
                    MemoryWindows: !options.DebugDisableMemoryWindows,
                    InstructionDecode: !options.DebugDisableInstructionDecode,
                    InstructionFingerprint: !options.DebugDisableInstructionFingerprint,
                    HitClustering: !options.DebugDisableHitClustering,
                    FollowUpSuggestions: !options.DebugDisableFollowUpSuggestions,
                    Artifacts: true),
                OutputDirectory: outputDirectory,
                Label: $"refresh-player-coord-trace-attempt-{attempt}",
                MarkerInputFile: null,
                PresetName: "player-coord-write-refresh",
                PlayerCoordTraceFile: options.PlayerCoordTraceFile,
                ReaderBridgeSnapshotFile: options.ReaderBridgeSnapshotFile,
                JsonOutput: false);

            var requestFile = DebugTraceRequestBuilder.WriteRequestFile(request);
            var startInfo = BuildDebugWorkerStartInfo(requestFile);

            using var worker = Process.Start(startInfo);
            if (worker is null)
            {
                error = "Unable to start the internal debug worker for player-coord trace refresh.";
                return false;
            }

            var workerStdout = worker.StandardOutput.ReadToEnd();
            var workerStderr = worker.StandardError.ReadToEnd();
            worker.WaitForExit();

            var inspection = DebugTracePackageLoader.TryInspect(request.OutputDirectory, out var inspectError);
            if (inspection is null)
            {
                lastError = inspectError
                    ?? workerStderr
                    ?? "Unable to inspect the refreshed player-coord trace package.";
                continue;
            }

            if (inspection.Hits.Count == 0)
            {
                lastError = inspection.Package.FailureMessage
                    ?? workerStderr
                    ?? $"Player-coord trace refresh attempt {attempt} completed without any debug hits.";
                continue;
            }

            var outputFile = ResolvePlayerCoordTraceOutputFile(options.PlayerCoordTraceFile);
            var refreshedDocument = BuildRefreshedPlayerCoordTraceDocument(baselineDocument, inspection, outputFile);
            File.WriteAllText(outputFile, JsonSerializer.Serialize(refreshedDocument, PrettyJsonOptions));
            return true;
        }

        error = lastError ?? "Unable to refresh the player-coord trace artifact.";
        return false;
    }

    private static ModulePatternScanResult? ScanTraceModulePattern(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        PlayerCoordTraceAnchorDocument traceDocument,
        int scanContextBytes)
    {
        var trace = traceDocument.Trace;
        var pattern = ResolveTracePattern(trace);
        if (trace is null || string.IsNullOrWhiteSpace(trace.ModuleName) || string.IsNullOrWhiteSpace(pattern))
        {
            return null;
        }

        var module = ProcessModuleLocator.FindModule(process, trace.ModuleName, out _);
        if (module is null)
        {
            return null;
        }

        return ModulePatternScanner.Scan(
            process,
            reader,
            target.ProcessId,
            target.ProcessName,
            module.ModuleName,
            module.FileName,
            module.BaseAddress.ToInt64(),
            module.ModuleMemorySize,
            pattern,
            scanContextBytes);
    }

    private static string ResolvePlayerCoordTraceOutputFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, "scripts", "captures", "player-coord-write-trace.json");
    }

    private static string ResolvePlayerCoordTraceRefreshOutputDirectory(int attempt)
    {
        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(
            repoRoot,
            "scripts",
            "captures",
            "debug-traces",
            $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmssfff}-refresh-player-coord-trace-attempt-{attempt}");
    }

    private static PlayerCoordTraceAnchorDocument BuildRefreshedPlayerCoordTraceDocument(
        PlayerCoordTraceAnchorDocument baselineDocument,
        DebugTraceInspectResult inspection,
        string outputFile)
    {
        var baselineTrace = baselineDocument.Trace
            ?? throw new InvalidOperationException("The baseline player coord trace document did not contain a trace payload.");
        var hit = inspection.Hits.FirstOrDefault()
            ?? throw new InvalidOperationException("The debug trace inspection did not contain any hits.");

        var matchedOffset = TryParseInvariantInt32(baselineTrace.MatchedOffset);
        var effectiveAddress = NormalizeAddressText(hit.EffectiveAddress) ?? baselineTrace.EffectiveAddress;
        var candidateAddress = effectiveAddress is not null && matchedOffset.HasValue
            ? TryAddOffsetToAddress(effectiveAddress, -matchedOffset.Value)
            : baselineTrace.CandidateAddress;
        var (hitModuleName, hitModuleOffset) = ParseModuleRelativeRip(hit.ModuleRelativeRip);
        var moduleName = hitModuleName
            ?? inspection.TraceManifest?.BreakpointModuleName
            ?? baselineTrace.ModuleName;
        var moduleOffset = hitModuleOffset
            ?? inspection.TraceManifest?.BreakpointModuleOffset
            ?? baselineTrace.ModuleOffset;
        var moduleBase = ResolveModuleBaseAddress(inspection, moduleName) ?? baselineTrace.ModuleBase;
        var instructionAddress = NormalizeAddressText(hit.RawRip) ?? baselineTrace.InstructionAddress;
        var instructionBytes = NormalizeHexBytes(hit.InstructionBytes) ?? baselineTrace.InstructionBytes;
        var normalizedPattern = baselineTrace.NormalizedPattern ?? instructionBytes;
        var instructionText = hit.InstructionText ?? baselineTrace.Instruction;
        var instructionSymbol = hit.ModuleRelativeRip;
        if (string.IsNullOrWhiteSpace(instructionSymbol) &&
            !string.IsNullOrWhiteSpace(moduleName) &&
            !string.IsNullOrWhiteSpace(moduleOffset))
        {
            instructionSymbol = $"{moduleName}+{moduleOffset}";
        }

        var refreshedTrace = new PlayerCoordTraceAnchorTrace(
            Status: inspection.Package.Status ?? (inspection.Hits.Count > 0 ? "hit" : baselineTrace.Status),
            VerificationMethod: baselineTrace.VerificationMethod ?? "native-debug-trace-instruction",
            CandidateAddress: candidateAddress,
            CandidateSource: "native-debug-trace-package",
            TargetAddress: candidateAddress ?? baselineTrace.TargetAddress,
            HitCount: inspection.Package.HitCount ?? inspection.Hits.Count,
            InstructionAddress: instructionAddress,
            InstructionSymbol: instructionSymbol ?? baselineTrace.InstructionSymbol,
            Instruction: instructionText,
            InstructionBytes: instructionBytes,
            NormalizedPattern: normalizedPattern,
            InstructionOpcode: instructionText ?? baselineTrace.InstructionOpcode,
            InstructionExtra: baselineTrace.InstructionExtra,
            InstructionSize: ResolveInstructionSize(instructionBytes, baselineTrace.InstructionSize),
            WriteOperand: baselineTrace.WriteOperand,
            AccessOperand: baselineTrace.AccessOperand,
            AccessType: baselineTrace.AccessType,
            EffectiveAddress: effectiveAddress,
            AccessMatchesTarget: candidateAddress is not null ? bool.TrueString.ToLowerInvariant() : baselineTrace.AccessMatchesTarget,
            MatchedOffset: baselineTrace.MatchedOffset,
            ModuleName: moduleName,
            ModuleBase: moduleBase,
            ModuleOffset: moduleOffset,
            Registers: hit.Registers?.ToDictionary(
                static pair => pair.Key,
                static pair => pair.Value,
                StringComparer.OrdinalIgnoreCase));

        return new PlayerCoordTraceAnchorDocument(
            Mode: baselineDocument.Mode ?? "player-coord-write-trace",
            GeneratedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            Reader: new PlayerCoordTraceAnchorReaderSummary(
                Mode: inspection.TraceManifest?.Mode ?? baselineDocument.Reader?.Mode ?? "debug-trace-instruction",
                ProcessId: inspection.TraceManifest?.ProcessId ?? inspection.Package.ProcessId,
                ProcessName: inspection.TraceManifest?.ProcessName ?? inspection.Package.ProcessName),
            Trace: refreshedTrace,
            OutputFile: outputFile,
            SourceFile: outputFile);
    }

    private static string? ResolveTracePattern(PlayerCoordTraceAnchorTrace? trace)
    {
        if (trace is null)
        {
            return null;
        }

        if (!string.IsNullOrWhiteSpace(trace.NormalizedPattern))
        {
            return trace.NormalizedPattern;
        }

        return NormalizeHexBytes(trace.InstructionBytes);
    }

    private static string? NormalizeHexBytes(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var compact = value.Replace(" ", string.Empty).Trim();
        if (compact.Length == 0 || (compact.Length % 2) != 0)
        {
            return null;
        }

        return string.Join(' ', Enumerable.Range(0, compact.Length / 2)
            .Select(index => compact.Substring(index * 2, 2).ToUpperInvariant()));
    }

    private static string? NormalizeAddressText(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return TryParseHexAddress(value, out var address)
            ? $"0x{address:X}"
            : null;
    }

    private static string? TryAddOffsetToAddress(string addressText, int delta)
    {
        if (!TryParseHexAddress(addressText, out var address))
        {
            return null;
        }

        var adjusted = address + delta;
        return adjusted < 0
            ? null
            : $"0x{adjusted:X}";
    }

    private static bool TryParseHexAddress(string? value, out long address)
    {
        address = 0;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var token = value.Trim();
        if (token.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            token = token[2..];
        }

        return long.TryParse(token, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address);
    }

    private static long TryParseRequiredAddress(string? value)
    {
        if (!TryParseHexAddress(value, out var address))
        {
            throw new InvalidOperationException($"Unable to parse the required hex address '{value ?? "n/a"}'.");
        }

        return address;
    }

    private static PlayerActorTruthObjectWindow? TryBuildTruthObjectWindow(
        ProcessMemoryReader reader,
        string? targetAddressText,
        string label,
        int windowLength,
        int pointerWidth,
        IReadOnlyList<ProcessMemoryRegion> readableRegions,
        IReadOnlyDictionary<long, string> knownTargets,
        ICollection<string> notes)
    {
        if (!TryParseHexAddress(targetAddressText, out var targetAddress))
        {
            notes.Add($"Skipped {label} window capture because the target address was unavailable.");
            return null;
        }

        var normalizedWindowLength = Math.Max(windowLength, pointerWidth);
        var halfWindow = normalizedWindowLength / 2;
        var windowStart = Math.Max(0, targetAddress - halfWindow);

        if (!reader.TryReadBytes(new nint(windowStart), normalizedWindowLength, out var bytes, out var readError))
        {
            notes.Add($"Unable to capture the {label} window at 0x{targetAddress:X}: {readError ?? "read failed"}");
            return null;
        }

        var pointerSlots = BuildPointerSlots(windowStart, bytes, pointerWidth, readableRegions, knownTargets);
        return new PlayerActorTruthObjectWindow(
            Label: label,
            TargetAddress: $"0x{targetAddress:X}",
            WindowStart: $"0x{windowStart:X}",
            WindowLength: bytes.Length,
            BytesHex: Convert.ToHexString(bytes),
            AsciiPreview: BuildAsciiPreview(bytes),
            Utf16Preview: BuildUtf16Preview(bytes),
            PointerSlots: pointerSlots);
    }

    private static IReadOnlyList<PlayerActorTruthPointerSlot> BuildPointerSlots(
        long windowStart,
        byte[] bytes,
        int pointerWidth,
        IReadOnlyList<ProcessMemoryRegion> readableRegions,
        IReadOnlyDictionary<long, string> knownTargets)
    {
        var normalizedPointerWidth = pointerWidth is 4 or 8 ? pointerWidth : IntPtr.Size;
        var slots = new List<PlayerActorTruthPointerSlot>();

        for (var offset = 0; offset + normalizedPointerWidth <= bytes.Length; offset += normalizedPointerWidth)
        {
            long value = normalizedPointerWidth switch
            {
                4 => BitConverter.ToUInt32(bytes, offset),
                8 => unchecked((long)BitConverter.ToUInt64(bytes, offset)),
                _ => throw new InvalidOperationException($"Unsupported pointer width {normalizedPointerWidth}.")
            };

            var (classification, targetRegionBase) = ClassifyPointerSlot(value, readableRegions, knownTargets);
            var slotAddress = windowStart + offset;
            slots.Add(new PlayerActorTruthPointerSlot(
                Offset: offset,
                OffsetHex: $"0x{offset:X}",
                SlotAddress: $"0x{slotAddress:X}",
                ValueHex: $"0x{value:X}",
                Classification: classification,
                TargetRegionBase: targetRegionBase));
        }

        return slots;
    }

    private static (string Classification, string? TargetRegionBase) ClassifyPointerSlot(
        long value,
        IReadOnlyList<ProcessMemoryRegion> readableRegions,
        IReadOnlyDictionary<long, string> knownTargets)
    {
        if (value == 0)
        {
            return ("null", null);
        }

        if (knownTargets.TryGetValue(value, out var label))
        {
            return (label, readableRegions.FirstOrDefault(region => region.ContainsAddress(new nint(value))) is { } knownRegion
                ? $"0x{knownRegion.BaseAddress.ToInt64():X}"
                : null);
        }

        return value < 0x10000
            ? ("small-immediate", null)
            : TryFindReadableRegionBase(value, readableRegions) is { } regionBase
                ? ("readable-region", regionBase)
                : ("non-pointer-data", null);
    }

    private static string? TryFindReadableRegionBase(long value, IReadOnlyList<ProcessMemoryRegion> readableRegions)
    {
        foreach (var region in readableRegions)
        {
            if (region.ContainsAddress(new nint(value)))
            {
                return $"0x{region.BaseAddress.ToInt64():X}";
            }
        }

        return null;
    }

    private static IReadOnlyList<PlayerActorTruthSlotCorrelation> FindSlotCorrelations(params PlayerActorTruthObjectWindow?[] windows)
    {
        var uniqueWindows = windows
            .Where(static window => window is not null)
            .GroupBy(static window => window!.TargetAddress, StringComparer.OrdinalIgnoreCase)
            .Select(static group => group.First()!)
            .ToArray();

        var grouped = uniqueWindows
            .SelectMany(static window => window!.PointerSlots.Select(slot => new
            {
                Window = window,
                Slot = slot
            }))
            .Where(static item =>
                string.Equals(item.Slot.Classification, "readable-region", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(item.Slot.Classification, "coord-object", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(item.Slot.Classification, "orientation-object", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(item.Slot.Classification, "orientation-parent", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(item.Slot.Classification, "orientation-root", StringComparison.OrdinalIgnoreCase))
            .GroupBy(static item => item.Slot.ValueHex, StringComparer.OrdinalIgnoreCase);

        return grouped
            .Select(group =>
            {
                var references = group
                    .Select(item => new PlayerActorTruthSlotCorrelationReference(
                        Surface: item.Window!.Label,
                        OffsetHex: item.Slot.OffsetHex,
                        SlotAddress: item.Slot.SlotAddress,
                        Classification: item.Slot.Classification))
                    .OrderBy(reference => reference.Surface, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(reference => reference.OffsetHex, StringComparer.OrdinalIgnoreCase)
                    .ToArray();
                var surfaces = references.Select(reference => reference.Surface)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .OrderBy(static surface => surface, StringComparer.OrdinalIgnoreCase)
                    .ToArray();
                var score = (surfaces.Length * 100) + references.Length;
                var targetRegionBase = group.Select(item => item.Slot.TargetRegionBase)
                    .FirstOrDefault(static value => !string.IsNullOrWhiteSpace(value));

                return new PlayerActorTruthSlotCorrelation(
                    ValueHex: group.Key,
                    TargetRegionBase: targetRegionBase,
                    Score: score,
                    DistinctSurfaceCount: surfaces.Length,
                    Surfaces: surfaces,
                    References: references);
            })
            .Where(correlation =>
                correlation.DistinctSurfaceCount >= 2 ||
                correlation.References.Any(reference =>
                    !string.Equals(reference.Classification, "readable-region", StringComparison.OrdinalIgnoreCase)))
            .OrderByDescending(static correlation => correlation.Score)
            .ThenBy(static correlation => correlation.ValueHex, StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .ToArray();
    }

    private static IReadOnlyList<PlayerActorTruthChainObservation> CollectTruthChainObservations(
        ReaderOptions options,
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        PlayerActorTruthReadResult initialResult,
        ICollection<string> notes)
    {
        var observations = new List<PlayerActorTruthChainObservation>
        {
            BuildTruthChainObservation(1, initialResult)
        };

        for (var sampleIndex = 2; sampleIndex <= TruthChainStabilitySampleCount; sampleIndex++)
        {
            Thread.Sleep(TruthChainStabilityDelayMilliseconds);

            if (!TryBuildPlayerActorTruthResult(options, process, target, reader, out var sampleResult, out var error) ||
                sampleResult is null)
            {
                notes.Add($"Truth-chain stability sample {sampleIndex} failed: {error ?? "unknown error"}");
                continue;
            }

            observations.Add(BuildTruthChainObservation(sampleIndex, sampleResult));
        }

        notes.Add($"Collected {observations.Count} truth-chain stability observations over {TruthChainStabilitySampleCount} attempted samples.");
        return observations;
    }

    private static PlayerActorTruthChainObservation BuildTruthChainObservation(int sampleIndex, PlayerActorTruthReadResult result)
    {
        var unifiedTruthObjectAddress = string.Equals(
            result.Coordinates.ObjectBaseAddress,
            result.Orientation.SelectedAddress,
            StringComparison.OrdinalIgnoreCase)
            ? result.Coordinates.ObjectBaseAddress
            : null;

        return new PlayerActorTruthChainObservation(
            SampleIndex: sampleIndex,
            UnifiedTruthObjectAddress: unifiedTruthObjectAddress,
            CoordObjectAddress: result.Coordinates.ObjectBaseAddress,
            OrientationObjectAddress: result.Orientation.SelectedAddress,
            OrientationParentAddress: result.Orientation.ParentAddress,
            OrientationRootAddress: result.Orientation.RootAddress);
    }

    private static PlayerActorTruthBestContainerChain? BuildBestContainerChain(IReadOnlyList<PlayerActorTruthChainObservation> observations)
    {
        if (observations.Count == 0)
        {
            return null;
        }

        var unifiedTruthObservationCount = observations.Count(observation =>
            !string.IsNullOrWhiteSpace(observation.UnifiedTruthObjectAddress));
        var bestUnifiedTruth = observations
            .Where(static observation => !string.IsNullOrWhiteSpace(observation.UnifiedTruthObjectAddress))
            .GroupBy(static observation => observation.UnifiedTruthObjectAddress!, StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(static group => group.Count())
            .ThenBy(static group => group.Key, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();
        var bestParent = observations
            .GroupBy(static observation => observation.OrientationParentAddress, StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(static group => group.Count())
            .ThenBy(static group => group.Key, StringComparer.OrdinalIgnoreCase)
            .First();
        var bestRoot = observations
            .GroupBy(static observation => observation.OrientationRootAddress, StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(static group => group.Count())
            .ThenBy(static group => group.Key, StringComparer.OrdinalIgnoreCase)
            .First();

        return new PlayerActorTruthBestContainerChain(
            UnifiedTruthObjectAddress: bestUnifiedTruth?.Key,
            UnifiedTruthObservationCount: unifiedTruthObservationCount,
            ParentAddress: bestParent.Key,
            ParentObservationCount: bestParent.Count(),
            RootAddress: bestRoot.Key,
            RootObservationCount: bestRoot.Count(),
            StabilitySampleCount: observations.Count);
    }

    private static IReadOnlyList<PlayerActorTruthRootFamilyCandidate> AnalyzeRootFamilyCandidates(
        ProcessMemoryReader reader,
        IReadOnlyList<ProcessMemoryRegion> readableRegions,
        IReadOnlyList<PlayerActorTruthChainObservation> observations,
        int comparisonBytes,
        ICollection<string> notes)
    {
        if (observations.Count == 0)
        {
            return Array.Empty<PlayerActorTruthRootFamilyCandidate>();
        }

        var effectiveComparisonBytes = Math.Max(16, comparisonBytes);
        var groupedObservations = observations
            .Select(observation =>
            {
                if (!TryParseHexAddress(observation.OrientationRootAddress, out var rootAddress))
                {
                    return null;
                }

                var regionBase = TryFindReadableRegionBase(rootAddress, readableRegions);
                return regionBase is null
                    ? null
                    : new
                    {
                        Observation = observation,
                        RootAddress = rootAddress,
                        RootAddressHex = observation.OrientationRootAddress,
                        RegionBase = regionBase
                    };
            })
            .Where(static item => item is not null)
            .Select(static item => item!)
            .GroupBy(static item => item.RegionBase, StringComparer.OrdinalIgnoreCase);

        var candidates = new List<PlayerActorTruthRootFamilyCandidate>();

        foreach (var group in groupedObservations)
        {
            var representativeGroup = group
                .GroupBy(static item => item.RootAddressHex, StringComparer.OrdinalIgnoreCase)
                .OrderByDescending(static item => item.Count())
                .ThenBy(static item => item.Key, StringComparer.OrdinalIgnoreCase)
                .First();

            var representativeAddress = representativeGroup.Key;
            if (!TryParseHexAddress(representativeAddress, out var representativeValue))
            {
                continue;
            }

            if (!reader.TryReadBytes(new nint(representativeValue), effectiveComparisonBytes, out var representativeBytes, out _))
            {
                notes.Add($"Unable to read representative root-family bytes at {representativeAddress}.");
                continue;
            }

            var comparisons = new List<int> { representativeBytes.Length };
            foreach (var addressText in group.Select(static item => item.RootAddressHex).Distinct(StringComparer.OrdinalIgnoreCase))
            {
                if (string.Equals(addressText, representativeAddress, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (!TryParseHexAddress(addressText, out var addressValue))
                {
                    continue;
                }

                if (!reader.TryReadBytes(new nint(addressValue), effectiveComparisonBytes, out var otherBytes, out _))
                {
                    notes.Add($"Unable to read comparison root-family bytes at {addressText}.");
                    continue;
                }

                comparisons.Add(CountMatchingBytes(representativeBytes, otherBytes));
            }

            var (asciiPreview, _) = TryReadPreview(reader, representativeValue, Math.Min(ParentChainPreviewBytes, representativeBytes.Length));
            var memberAddresses = group
                .Select(static item => item.RootAddressHex)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(static item => item, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            var score = (group.Count() * 100) + (memberAddresses.Length * 10) + (int)Math.Round(comparisons.Average());

            candidates.Add(new PlayerActorTruthRootFamilyCandidate(
                RegionBase: group.Key,
                Score: score,
                ObservationCount: group.Count(),
                DistinctAddressCount: memberAddresses.Length,
                StabilitySampleCount: observations.Count,
                RepresentativeAddress: representativeAddress,
                RepresentativeObservationCount: representativeGroup.Count(),
                MemberAddresses: memberAddresses,
                AverageMatchingBytes: comparisons.Average(),
                MinimumMatchingBytes: comparisons.Min(),
                MaximumMatchingBytes: comparisons.Max(),
                RepresentativeAsciiPreview: asciiPreview));
        }

        notes.Add($"Root-family analysis grouped {observations.Count} stability observations into {candidates.Count} candidate root families.");

        return candidates
            .OrderByDescending(static candidate => candidate.Score)
            .ThenBy(static candidate => candidate.RegionBase, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static int CountMatchingBytes(byte[] left, byte[] right)
    {
        var length = Math.Min(left.Length, right.Length);
        var same = 0;
        for (var index = 0; index < length; index++)
        {
            if (left[index] == right[index])
            {
                same++;
            }
        }

        return same;
    }

    private static IReadOnlyList<PlayerActorTruthParentContainerCandidate> FindParentContainerCandidates(
        ProcessMemoryReader reader,
        ProcessTarget target,
        IReadOnlyList<ProcessMemoryRegion> readableRegions,
        string? parentAddressText,
        string? rootAddressText,
        PlayerActorTruthObjectWindow? parentWindow,
        PointerScanResult parentBackrefs,
        int pointerWidth,
        int windowLength,
        IReadOnlyList<PlayerActorTruthChainObservation> stabilityObservations,
        ICollection<string> notes)
    {
        if (!TryParseHexAddress(parentAddressText, out var parentAddress))
        {
            notes.Add("Skipped focused parent-container analysis because the direct parent address was unavailable.");
            return Array.Empty<PlayerActorTruthParentContainerCandidate>();
        }

        TryParseHexAddress(rootAddressText, out var rootAddress);

        var candidates = new Dictionary<long, ParentCandidateAccumulator>();

        ParentCandidateAccumulator EnsureCandidate(long address)
        {
            if (!candidates.TryGetValue(address, out var candidate))
            {
                candidate = new ParentCandidateAccumulator(address, TryFindReadableRegionBase(address, readableRegions));
                candidates[address] = candidate;
            }

            return candidate;
        }

        var directParent = EnsureCandidate(parentAddress);
        directParent.IsDirectParent = true;
        directParent.Sources.Add("direct-parent");

        if (rootAddress != 0)
        {
            var rootCandidate = EnsureCandidate(rootAddress);
            rootCandidate.IsOrientationRoot = true;
            rootCandidate.Sources.Add("orientation-root");
        }

        foreach (var observation in stabilityObservations)
        {
            if (TryParseHexAddress(observation.OrientationParentAddress, out var observedParentAddress))
            {
                var candidate = EnsureCandidate(observedParentAddress);
                candidate.ObservedAsParentCount++;
                candidate.Sources.Add($"stability-parent#{observation.SampleIndex}");
            }

            if (TryParseHexAddress(observation.OrientationRootAddress, out var observedRootAddress))
            {
                var candidate = EnsureCandidate(observedRootAddress);
                candidate.ObservedAsRootCount++;
                candidate.Sources.Add($"stability-root#{observation.SampleIndex}");
            }
        }

        if (parentWindow is not null)
        {
            foreach (var slot in parentWindow.PointerSlots.Where(static slot =>
                         string.Equals(slot.Classification, "readable-region", StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(slot.Classification, "coord-object", StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(slot.Classification, "orientation-object", StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(slot.Classification, "orientation-parent", StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(slot.Classification, "orientation-root", StringComparison.OrdinalIgnoreCase)))
            {
                if (!TryParseHexAddress(slot.ValueHex, out var address))
                {
                    continue;
                }

                var candidate = EnsureCandidate(address);
                candidate.ParentWindowSlotCount++;
                candidate.Sources.Add($"parent-slot{slot.OffsetHex}");
            }
        }

        foreach (var hit in parentBackrefs.Hits)
        {
            var candidate = EnsureCandidate(hit.Address);
            candidate.RegionBase ??= hit.RegionBaseHex;
            candidate.ParentBackrefCount++;
            candidate.Sources.Add("parent-backref");
        }

        foreach (var hit in parentBackrefs.Hits.Take(ParentChainSecondHopSeedLimit))
        {
            try
            {
                var secondHop = ProcessPointerScanner.Scan(
                    reader,
                    target.ProcessId,
                    target.ProcessName,
                    new nint(hit.Address),
                    pointerWidth,
                    windowLength,
                    ParentChainSecondHopMaxHits);

                foreach (var secondHit in secondHop.Hits)
                {
                    var candidate = EnsureCandidate(secondHit.Address);
                    candidate.RegionBase ??= secondHit.RegionBaseHex;
                    candidate.ParentSecondHopCount++;
                    candidate.Sources.Add("parent-second-hop");
                }
            }
            catch (Exception ex)
            {
                notes.Add($"Focused parent second-hop scan failed for {hit.AddressHex}: {ex.Message}");
            }
        }

        var result = candidates.Values
            .Select(candidate =>
            {
                candidate.Score =
                    (candidate.IsOrientationRoot ? 300 : 0) +
                    (candidate.IsDirectParent ? 200 : 0) +
                    (candidate.ObservedAsRootCount * 140) +
                    (candidate.ObservedAsParentCount * 110) +
                    (candidate.ParentBackrefCount * 80) +
                    (candidate.ParentSecondHopCount * 30) +
                    (candidate.ParentWindowSlotCount * 10) +
                    (candidate.Sources.Count * 5);

                var (asciiPreview, utf16Preview) = TryReadPreview(reader, candidate.Address, Math.Min(windowLength, ParentChainPreviewBytes));
                return new PlayerActorTruthParentContainerCandidate(
                    Address: $"0x{candidate.Address:X}",
                    RegionBase: candidate.RegionBase,
                    Score: candidate.Score,
                    IsDirectParent: candidate.IsDirectParent,
                    IsOrientationRoot: candidate.IsOrientationRoot,
                    ObservedAsParentCount: candidate.ObservedAsParentCount,
                    ObservedAsRootCount: candidate.ObservedAsRootCount,
                    ParentWindowSlotCount: candidate.ParentWindowSlotCount,
                    ParentBackrefCount: candidate.ParentBackrefCount,
                    ParentSecondHopCount: candidate.ParentSecondHopCount,
                    Sources: candidate.Sources.OrderBy(static source => source, StringComparer.OrdinalIgnoreCase).ToArray(),
                    AsciiPreview: asciiPreview,
                    Utf16Preview: utf16Preview);
            })
            .Where(candidate =>
                candidate.IsDirectParent ||
                candidate.IsOrientationRoot ||
                candidate.ObservedAsParentCount > 0 ||
                candidate.ObservedAsRootCount > 0 ||
                candidate.ParentBackrefCount > 0 ||
                candidate.ParentSecondHopCount > 0 ||
                candidate.ParentWindowSlotCount > 1)
            .OrderByDescending(static candidate => candidate.Score)
            .ThenBy(static candidate => candidate.Address, StringComparer.OrdinalIgnoreCase)
            .Take(10)
            .ToArray();

        notes.Add($"Focused parent-container analysis produced {result.Length} ranked candidates above the unified truth surface.");
        return result;
    }

    private static (string? AsciiPreview, string? Utf16Preview) TryReadPreview(ProcessMemoryReader reader, long address, int length)
    {
        if (address <= 0 || length <= 0)
        {
            return (null, null);
        }

        if (!reader.TryReadBytes(new nint(address), length, out var bytes, out _))
        {
            return (null, null);
        }

        return (BuildAsciiPreview(bytes), BuildUtf16Preview(bytes));
    }

    private sealed class ParentCandidateAccumulator
    {
        public ParentCandidateAccumulator(long address, string? regionBase)
        {
            Address = address;
            RegionBase = regionBase;
        }

        public long Address { get; }
        public string? RegionBase { get; set; }
        public int Score { get; set; }
        public bool IsDirectParent { get; set; }
        public bool IsOrientationRoot { get; set; }
        public int ObservedAsParentCount { get; set; }
        public int ObservedAsRootCount { get; set; }
        public int ParentWindowSlotCount { get; set; }
        public int ParentBackrefCount { get; set; }
        public int ParentSecondHopCount { get; set; }
        public HashSet<string> Sources { get; } = new(StringComparer.OrdinalIgnoreCase);
    }

    private static PointerScanResult RunPointerScanOrEmpty(
        ProcessMemoryReader reader,
        ProcessTarget target,
        string? pointerTargetText,
        int pointerWidth,
        int contextBytes,
        int maxHits,
        ICollection<string> notes,
        string label)
    {
        if (!TryParseHexAddress(pointerTargetText, out var pointerTarget))
        {
            notes.Add($"Skipped pointer backref scan for {label} because the target address was unavailable.");
            return BuildEmptyPointerScanResult(target, pointerTargetText, pointerWidth, contextBytes, maxHits);
        }

        try
        {
            return ProcessPointerScanner.Scan(
                reader,
                target.ProcessId,
                target.ProcessName,
                new nint(pointerTarget),
                pointerWidth,
                contextBytes,
                maxHits);
        }
        catch (Exception ex)
        {
            notes.Add($"Pointer backref scan for {label} failed at 0x{pointerTarget:X}: {ex.Message}");
            return BuildEmptyPointerScanResult(target, $"0x{pointerTarget:X}", pointerWidth, contextBytes, maxHits);
        }
    }

    private static PointerScanResult BuildEmptyPointerScanResult(
        ProcessTarget target,
        string? pointerTargetText,
        int pointerWidth,
        int contextBytes,
        int maxHits)
    {
        return new PointerScanResult(
            Mode: "pointer-scan",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            PointerTarget: pointerTargetText ?? "n/a",
            PointerWidth: pointerWidth,
            ContextBytes: contextBytes,
            MaxHits: maxHits,
            HitCount: 0,
            Hits: Array.Empty<PointerScanHit>());
    }

    private static IReadOnlyList<PlayerActorTruthSharedAncestorCandidate> FindSharedAncestorCandidates(
        ProcessMemoryReader reader,
        ProcessTarget target,
        IReadOnlyDictionary<string, PointerScanResult> firstHopScans,
        int pointerWidth,
        int contextBytes,
        int secondHopSeedLimitPerSurface,
        int secondHopMaxHits,
        ICollection<string> notes)
    {
        var candidatePaths = new Dictionary<long, HashSet<PlayerActorTruthSharedAncestorPath>>();
        var candidateRegionBases = new Dictionary<long, string>();
        var performedSecondHopScans = 0;

        foreach (var firstHopScan in firstHopScans)
        {
            foreach (var firstHopHit in firstHopScan.Value.Hits.Take(secondHopSeedLimitPerSurface))
            {
                performedSecondHopScans++;
                PointerScanResult secondHopScan;
                try
                {
                    secondHopScan = ProcessPointerScanner.Scan(
                        reader,
                        target.ProcessId,
                        target.ProcessName,
                        new nint(firstHopHit.Address),
                        pointerWidth,
                        contextBytes,
                        secondHopMaxHits);
                }
                catch (Exception ex)
                {
                    notes.Add($"Second-hop pointer scan failed for {firstHopScan.Key} backref {firstHopHit.AddressHex}: {ex.Message}");
                    continue;
                }

                foreach (var secondHopHit in secondHopScan.Hits)
                {
                    if (!candidatePaths.TryGetValue(secondHopHit.Address, out var pathSet))
                    {
                        pathSet = new HashSet<PlayerActorTruthSharedAncestorPath>();
                        candidatePaths[secondHopHit.Address] = pathSet;
                        candidateRegionBases[secondHopHit.Address] = secondHopHit.RegionBaseHex;
                    }

                    pathSet.Add(new PlayerActorTruthSharedAncestorPath(
                        Surface: firstHopScan.Key,
                        FirstHopAddress: firstHopHit.AddressHex,
                        SecondHopAddress: secondHopHit.AddressHex));
                }
            }
        }

        notes.Add($"Second-hop ancestor search scanned {performedSecondHopScans} first-hop seeds across {firstHopScans.Count} truth surfaces.");

        var candidates = candidatePaths
            .Select(pair =>
            {
                var paths = pair.Value.OrderBy(path => path.Surface, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(path => path.FirstHopAddress, StringComparer.OrdinalIgnoreCase)
                    .ThenBy(path => path.SecondHopAddress, StringComparer.OrdinalIgnoreCase)
                    .ToArray();
                var surfaces = paths.Select(path => path.Surface)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .OrderBy(surface => surface, StringComparer.OrdinalIgnoreCase)
                    .ToArray();
                var firstHopReferenceCount = paths.Select(path => path.FirstHopAddress)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .Count();
                var secondHopReferenceCount = paths.Select(path => path.SecondHopAddress)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .Count();
                var score = (surfaces.Length * 100) + (firstHopReferenceCount * 10) + secondHopReferenceCount;

                return new PlayerActorTruthSharedAncestorCandidate(
                    Address: $"0x{pair.Key:X}",
                    RegionBase: candidateRegionBases[pair.Key],
                    Score: score,
                    DistinctSurfaceCount: surfaces.Length,
                    Surfaces: surfaces,
                    FirstHopReferenceCount: firstHopReferenceCount,
                    SecondHopReferenceCount: secondHopReferenceCount,
                    Paths: paths);
            })
            .Where(candidate => candidate.DistinctSurfaceCount >= 2)
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => candidate.Address, StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .ToArray();

        if (candidates.Length == 0)
        {
            notes.Add("No shared second-hop ancestor candidate pointed to backrefs from more than one truth surface.");
        }
        else
        {
            notes.Add($"Found {candidates.Length} shared second-hop ancestor candidates spanning multiple truth surfaces.");
        }

        return candidates;
    }

    private static string BuildAsciiPreview(byte[] bytes)
    {
        var builder = new StringBuilder(bytes.Length);
        foreach (var value in bytes)
        {
            builder.Append(value is >= 32 and <= 126 ? (char)value : '.');
        }

        return builder.ToString();
    }

    private static string BuildUtf16Preview(byte[] bytes)
    {
        if ((bytes.Length % 2) != 0)
        {
            bytes = bytes.Take(bytes.Length - 1).ToArray();
        }

        if (bytes.Length == 0)
        {
            return string.Empty;
        }

        var chars = Encoding.Unicode.GetChars(bytes);
        var builder = new StringBuilder(chars.Length);
        foreach (var value in chars)
        {
            builder.Append(!char.IsControl(value) ? value : '.');
        }

        return builder.ToString();
    }

    private static int? TryParseInvariantInt32(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static string? ResolveModuleBaseAddress(DebugTraceInspectResult inspection, string? moduleName)
    {
        if (string.IsNullOrWhiteSpace(moduleName))
        {
            return null;
        }

        return inspection.Modules.FirstOrDefault(module =>
            string.Equals(module.ModuleName, moduleName, StringComparison.OrdinalIgnoreCase))
            ?.BaseAddressHex;
    }

    private static string? ResolveInstructionSize(string? instructionBytes, string? fallback)
    {
        var normalized = NormalizeHexBytes(instructionBytes);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return fallback;
        }

        var size = normalized.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length;
        return size.ToString(CultureInfo.InvariantCulture);
    }

    private static string? TryGetProcessStartTimeUtc(Process process)
    {
        try
        {
            return process.StartTime.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);
        }
        catch
        {
            return null;
        }
    }

    private static (string? ModuleName, string? ModuleOffset) ParseModuleRelativeRip(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return (null, null);
        }

        var separatorIndex = value.IndexOf('+');
        if (separatorIndex <= 0 || separatorIndex >= value.Length - 1)
        {
            return (null, null);
        }

        var moduleName = value[..separatorIndex].Trim();
        var moduleOffset = NormalizeAddressText(value[(separatorIndex + 1)..].Trim());
        return (
            string.IsNullOrWhiteSpace(moduleName) ? null : moduleName,
            moduleOffset);
    }

    private static int RunReadPlayerOrientationMode(ReaderOptions options)
    {
        var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(options.OwnerComponentsFile, out var artifactError);
        if (artifactDocument is null)
        {
            Console.Error.WriteLine(artifactError ?? "Unable to load the player owner-component artifact.");
            return 1;
        }

        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(null, out _);

        PlayerOrientationReadResult result;
        try
        {
            result = PlayerOrientationReader.Read(artifactDocument, snapshotDocument);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the player orientation snapshot: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client artifacts and processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(PlayerOrientationReadTextFormatter.Format(result));
        return 0;
    }

    private static void WriteUsage(ReaderOptionsParseResult parseResult)
    {
        Console.WriteLine(parseResult.UsageText);
    }

    private static int RunAddonSnapshotMode(ReaderOptions options)
    {
        var document = ValidatorSnapshotLoader.TryLoad(options.AddonSnapshotFile, out var error);

        if (document is null)
        {
            Console.Error.WriteLine(error ?? "Unable to load the addon snapshot.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(document));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(ValidatorSnapshotTextFormatter.Format(document));
        return 0;
    }

    private static int RunReaderBridgeSnapshotMode(ReaderOptions options)
    {
        var document = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var error);

        if (document is null)
        {
            Console.Error.WriteLine(error ?? "Unable to load the ReaderBridge snapshot.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(document));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(ReaderBridgeSnapshotTextFormatter.Format(document));
        return 0;
    }

    private static int RunOwnerComponentRankingMode(ReaderOptions options)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(null, out var snapshotError);
        if (snapshotDocument?.Current?.Player is null)
        {
            Console.Error.WriteLine(snapshotError ?? "Unable to load the latest ReaderBridge export for owner-component ranking.");
            return 1;
        }

        var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(options.OwnerComponentsFile, out var artifactError);
        if (artifactDocument is null)
        {
            Console.Error.WriteLine(artifactError ?? "Unable to load the player owner-component artifact.");
            return 1;
        }

        PlayerOwnerComponentRankResult result;
        try
        {
            result = PlayerOwnerComponentRanker.Rank(snapshotDocument, artifactDocument);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to rank owner components: {ex.Message}");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client artifacts and processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(PlayerOwnerComponentRankTextFormatter.Format(result));
        return 0;
    }

    private static int RunScanMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        if (!string.IsNullOrWhiteSpace(options.ScanModulePattern))
        {
            var module = ProcessModuleLocator.FindModule(process, options.ScanModuleName, out var moduleError);
            if (module is null)
            {
                Console.Error.WriteLine(moduleError ?? "Unable to resolve the requested module.");
                return 1;
            }

            ModulePatternScanResult scanResult;
            try
            {
                scanResult = ModulePatternScanner.Scan(
                    process,
                    reader,
                    target.ProcessId,
                    target.ProcessName,
                    module.ModuleName,
                    module.FileName,
                    module.BaseAddress.ToInt64(),
                    module.ModuleMemorySize,
                    options.ScanModulePattern,
                    options.ScanContextBytes);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Unable to run the module pattern scan: {ex.Message}");
                return 1;
            }

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(scanResult));
                return 0;
            }

            Console.WriteLine(ModulePatternScanTextFormatter.Format(scanResult));
            return 0;
        }

        if (options.ScanPointer.HasValue)
        {
            var pointerResult = ProcessPointerScanner.Scan(
                reader,
                target.ProcessId,
                target.ProcessName,
                options.ScanPointer.Value,
                options.PointerWidth,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(pointerResult));
                return 0;
            }

            Console.WriteLine(PointerScanTextFormatter.Format(pointerResult));
            return 0;
        }

        if (options.ScanInt32.HasValue)
        {
            var numericResult = ProcessNumericScanner.ScanInt32(
                reader,
                target.ProcessId,
                target.ProcessName,
                options.ScanInt32.Value,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(numericResult));
                return 0;
            }

            Console.WriteLine(NumericScanTextFormatter.Format(numericResult));
            return 0;
        }

        if (options.ScanFloat.HasValue)
        {
            var numericResult = ProcessNumericScanner.ScanFloat(
                reader,
                target.ProcessId,
                target.ProcessName,
                options.ScanFloat.Value,
                options.ScanTolerance,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(numericResult));
                return 0;
            }

            Console.WriteLine(NumericScanTextFormatter.Format(numericResult));
            return 0;
        }

        if (options.ScanDouble.HasValue)
        {
            var numericResult = ProcessNumericScanner.ScanDouble(
                reader,
                target.ProcessId,
                target.ProcessName,
                options.ScanDouble.Value,
                options.ScanTolerance,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(numericResult));
                return 0;
            }

            Console.WriteLine(NumericScanTextFormatter.Format(numericResult));
            return 0;
        }

        if (options.ScanReaderBridgePlayerCoords)
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(null, out var loadError);
            var playerCoord = document?.Current?.Player?.Coord;
            var sourceFile = document?.SourceFile ?? "<unknown>";

            if (playerCoord?.X is not double coordX || playerCoord.Y is not double coordY || playerCoord.Z is not double coordZ)
            {
                Console.Error.WriteLine(loadError ?? "Unable to resolve current player coordinates from the latest ReaderBridge export.");
                return 1;
            }

            var sequenceResult = ProcessFloatSequenceScanner.ScanFloatTriplet(
                reader,
                target.ProcessId,
                target.ProcessName,
                $"readerbridge-player-coords ({sourceFile})",
                (float)coordX,
                (float)coordY,
                (float)coordZ,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(sequenceResult));
                return 0;
            }

            Console.WriteLine(FloatSequenceScanTextFormatter.Format(sequenceResult));
            return 0;
        }

        if (options.ScanReaderBridgePlayerSignature)
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(null, out var loadError);
            var player = document?.Current?.Player;
            var playerCoord = player?.Coord;
            var sourceFile = document?.SourceFile ?? "<unknown>";

            if (playerCoord?.X is not double coordX || playerCoord.Y is not double coordY || playerCoord.Z is not double coordZ)
            {
                Console.Error.WriteLine(loadError ?? "Unable to resolve current player coordinates from the latest ReaderBridge export.");
                return 1;
            }

            var signatureResult = ProcessPlayerSignatureScanner.ScanReaderBridgePlayerSignature(
                reader,
                target.ProcessId,
                target.ProcessName,
                $"readerbridge-player-signature ({sourceFile})",
                (float)coordX,
                (float)coordY,
                (float)coordZ,
                player?.Level,
                player?.Hp,
                player?.HpMax,
                player?.Name,
                player?.LocationName,
                options.ScanContextBytes,
                options.MaxHits);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(signatureResult));
                return 0;
            }

            Console.WriteLine(PlayerSignatureScanTextFormatter.Format(signatureResult));
            return 0;
        }

        string searchText;
        string searchSource;

        if (options.ScanReaderBridgePlayerName)
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(null, out var loadError);
            if (document?.Current?.Player?.Name is not { Length: > 0 } playerName)
            {
                Console.Error.WriteLine(loadError ?? "Unable to resolve the player name from the latest ReaderBridge export.");
                return 1;
            }

            searchText = playerName;
            searchSource = $"readerbridge-player-name ({document.SourceFile})";
        }
        else if (options.ScanReaderBridgeIdentity)
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(null, out var loadError);
            if (!TryBuildReaderBridgeIdentitySearchText(document, out searchText, out searchSource))
            {
                Console.Error.WriteLine(loadError ?? "Unable to derive a ReaderBridge identity string from the latest export.");
                return 1;
            }
        }
        else if (!string.IsNullOrWhiteSpace(options.ScanString))
        {
            searchText = options.ScanString;
            searchSource = "cli";
        }
        else
        {
            Console.Error.WriteLine("No scan target was specified.");
            return 1;
        }

        var result = ProcessStringScanner.Scan(
            reader,
            target.ProcessId,
            target.ProcessName,
            searchText,
            searchSource,
            options.ScanEncoding,
            options.ScanContextBytes,
            options.MaxHits);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(StringScanTextFormatter.Format(result));
        return 0;
    }

    private static int RunRecordSessionMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        var watchset = SessionWatchsetLoader.TryLoad(options.SessionWatchsetFile, out var loadError);
        if (watchset?.Regions is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the session watchset.");
            return 1;
        }

        if (watchset.Regions.Count == 0)
        {
            Console.Error.WriteLine("The session watchset does not contain any regions.");
            return 1;
        }

        var outputDirectory = Path.GetFullPath(options.SessionOutputDirectory!);
        Directory.CreateDirectory(outputDirectory);

        var sessionId = new DirectoryInfo(outputDirectory).Name;
        var watchsetFile = Path.GetFullPath(options.SessionWatchsetFile!);
        var manifestFile = Path.Combine(outputDirectory, "recording-manifest.json");
        var samplesFile = Path.Combine(outputDirectory, "samples.ndjson");
        var markersFile = Path.Combine(outputDirectory, "markers.ndjson");
        var modulesFile = Path.Combine(outputDirectory, "modules.json");
        var sessionMarkerInputFile = string.IsNullOrWhiteSpace(options.SessionMarkerInputFile)
            ? null
            : Path.GetFullPath(options.SessionMarkerInputFile);
        var tempFileSuffix = $".{Guid.NewGuid():N}.tmp";
        var tempManifestFile = manifestFile + tempFileSuffix;
        var tempSamplesFile = samplesFile + tempFileSuffix;
        var tempMarkersFile = markersFile + tempFileSuffix;
        var tempModulesFile = modulesFile + tempFileSuffix;

        var conflictingOutputFiles = new[]
        {
            manifestFile,
            samplesFile,
            markersFile,
            modulesFile
        }
        .Where(File.Exists)
        .ToArray();

        if (conflictingOutputFiles.Length > 0)
        {
            Console.Error.WriteLine(
                $"Session output directory '{outputDirectory}' already contains recorder-managed files: {string.Join(", ", conflictingOutputFiles.Select(Path.GetFileName))}. Choose a new directory or remove the stale files first.");
            return 1;
        }

        if (!string.IsNullOrWhiteSpace(sessionMarkerInputFile) &&
            (string.Equals(sessionMarkerInputFile, manifestFile, StringComparison.OrdinalIgnoreCase) ||
             string.Equals(sessionMarkerInputFile, samplesFile, StringComparison.OrdinalIgnoreCase) ||
             string.Equals(sessionMarkerInputFile, markersFile, StringComparison.OrdinalIgnoreCase) ||
             string.Equals(sessionMarkerInputFile, modulesFile, StringComparison.OrdinalIgnoreCase)))
        {
            Console.Error.WriteLine("--session-marker-input-file cannot target a recorder-managed output file.");
            return 1;
        }

        var warnings = new List<string>();
        if (!string.IsNullOrWhiteSpace(watchset.ProcessName) &&
            !string.Equals(watchset.ProcessName, target.ProcessName, StringComparison.OrdinalIgnoreCase))
        {
            warnings.Add($"Watchset targets process '{watchset.ProcessName}', but the active process is '{target.ProcessName}'.");
        }

        var watchsetWarnings = watchset.Warnings?
            .Where(static warning => !string.IsNullOrWhiteSpace(warning))
            .Select(static warning => warning!)
            .ToArray()
            ?? Array.Empty<string>();

        warnings.AddRange(watchsetWarnings);

        var requestedRegionByteCount = watchset.Regions
            .Where(static region => region is not null)
            .Sum(static region => Math.Max(region!.Length, 0));
        var projectedRawBytes = (long)requestedRegionByteCount * Math.Max(options.SessionSampleCount, 0);
        if (projectedRawBytes > SessionRecommendedRawByteBudget)
        {
            warnings.Add(
                $"Projected raw session payload is {projectedRawBytes} bytes ({requestedRegionByteCount} bytes/sample x {options.SessionSampleCount} samples), which exceeds the recommended budget of {SessionRecommendedRawByteBudget} bytes.");
        }

        if (options.SessionIntervalMilliseconds <= SessionRecommendedBurstIntervalMilliseconds)
        {
            warnings.Add(
                $"Session interval {options.SessionIntervalMilliseconds} ms enables burst/high-frequency sampling. Review timing drift and capture duration before promoting anchors.");
        }

        if (options.SessionIntervalMilliseconds == 0 && options.SessionSampleCount >= SessionRecommendedBurstSampleCount)
        {
            warnings.Add(
                $"Zero-interval session requested {options.SessionSampleCount} samples. This is supported, but treat the output as burst-mode evidence and verify capture duration before using it for stability decisions.");
        }

        IReadOnlyList<ProcessModuleInfo> modules;
        try
        {
            modules = ProcessModuleLocator.ListModules(process);
        }
        catch (Exception ex)
        {
            modules = Array.Empty<ProcessModuleInfo>();
            warnings.Add($"Unable to enumerate modules for the session manifest: {ex.Message}");
        }

        ConsoleCancelEventHandler? cancelHandler = null;

        try
        {
            if (!string.IsNullOrWhiteSpace(sessionMarkerInputFile))
            {
                var markerInputDirectory = Path.GetDirectoryName(sessionMarkerInputFile);
                if (!string.IsNullOrWhiteSpace(markerInputDirectory))
                {
                    Directory.CreateDirectory(markerInputDirectory);
                }

                if (!File.Exists(sessionMarkerInputFile))
                {
                    File.WriteAllText(sessionMarkerInputFile, string.Empty);
                }
            }

            File.WriteAllText(tempModulesFile, JsonOutput.Serialize(modules));

            var startedAtUtc = DateTimeOffset.UtcNow;
            var requiredReadFailures = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var regionAccumulators = new Dictionary<string, SessionRegionAccumulator>(StringComparer.OrdinalIgnoreCase);
            var markerKinds = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            var emittedMarkerInputWarnings = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var totalBytesRead = 0L;
            var totalRegionReadFailures = 0;
            var recordedSampleCount = 0;
            var markerCount = 0;
            var interrupted = false;
            var markerInputProcessedLineCount = 0;
            var cancelRequested = false;
            SessionRecordResult result;

            using (var sampleWriter = new StreamWriter(tempSamplesFile, append: false))
            using (var markerWriter = new StreamWriter(tempMarkersFile, append: false))
            {
                cancelHandler = (_, eventArgs) =>
                {
                    eventArgs.Cancel = true;
                    cancelRequested = true;
                };

                Console.CancelKeyPress += cancelHandler;

                var stopwatch = Stopwatch.StartNew();
                RecordSessionMarker(
                    markerWriter,
                    CreateSessionMarker(
                        Kind: "session-start",
                        RecordedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                        ElapsedMilliseconds: 0,
                        SampleIndex: 0,
                        Label: options.SessionLabel,
                        Message: "Session recording started.",
                        Source: "system",
                        Metadata: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                        {
                            ["watchsetFile"] = watchsetFile,
                            ["outputDirectory"] = outputDirectory
                        }),
                    markerKinds,
                    ref markerCount);

                if (!string.IsNullOrWhiteSpace(options.SessionLabel))
                {
                    RecordSessionMarker(
                        markerWriter,
                        CreateSessionMarker(
                            Kind: "label",
                            RecordedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                            ElapsedMilliseconds: 0,
                            SampleIndex: 0,
                            Label: options.SessionLabel,
                            Message: "Initial session label.",
                            Source: "system"),
                        markerKinds,
                        ref markerCount);
                }

                DrainSessionMarkerInputFile(
                    markerWriter,
                    sessionMarkerInputFile,
                    ref markerInputProcessedLineCount,
                    options.SessionLabel,
                    sampleIndex: 0,
                    stopwatch,
                    markerKinds,
                    ref markerCount,
                    warnings,
                    emittedMarkerInputWarnings);

                for (var sampleIndex = 0; sampleIndex < options.SessionSampleCount; sampleIndex++)
                {
                    var expectedElapsedMilliseconds = (long)sampleIndex * options.SessionIntervalMilliseconds;
                    if (!WaitForNextSessionSample(
                            stopwatch,
                            expectedElapsedMilliseconds,
                            () => cancelRequested,
                            () => DrainSessionMarkerInputFile(
                                markerWriter,
                                sessionMarkerInputFile,
                                ref markerInputProcessedLineCount,
                                options.SessionLabel,
                                sampleIndex,
                                stopwatch,
                                markerKinds,
                                ref markerCount,
                                warnings,
                                emittedMarkerInputWarnings)))
                    {
                        interrupted = true;
                        break;
                    }

                    DrainSessionMarkerInputFile(
                        markerWriter,
                        sessionMarkerInputFile,
                        ref markerInputProcessedLineCount,
                        options.SessionLabel,
                        sampleIndex,
                        stopwatch,
                        markerKinds,
                        ref markerCount,
                        warnings,
                        emittedMarkerInputWarnings);

                    if (cancelRequested)
                    {
                        interrupted = true;
                        break;
                    }

                    var sampleTimeUtc = DateTimeOffset.UtcNow;
                    var sampleStartedElapsed = stopwatch.ElapsedMilliseconds;
                    var regions = new List<SessionRegionSampleRecord>(watchset.Regions.Count);

                    foreach (var region in watchset.Regions)
                    {
                        if (region is null)
                        {
                            continue;
                        }

                        var regionName = string.IsNullOrWhiteSpace(region.Name)
                            ? $"region-{regions.Count}"
                            : region.Name!;
                        var regionCategory = string.IsNullOrWhiteSpace(region.Category)
                            ? "memory"
                            : region.Category!;

                        if (!TryParseSessionAddress(region.Address, out var regionAddress))
                        {
                            var regionRecord = new SessionRegionSampleRecord(
                                Name: regionName,
                                Category: regionCategory,
                                Address: region.Address ?? string.Empty,
                                Length: region.Length,
                                Required: region.Required,
                                ReadSucceeded: false,
                                BytesRead: 0,
                                BytesHex: null,
                                Error: $"Invalid address '{region.Address}'.");
                            regions.Add(regionRecord);
                            UpdateSessionRegionAccumulator(regionAccumulators, regionRecord);
                            totalRegionReadFailures++;

                            if (region.Required)
                            {
                                requiredReadFailures.Add(regionName);
                            }

                            continue;
                        }

                        var readSucceeded = reader.TryReadBytes(regionAddress, region.Length, out var bytes, out var readError);
                        var bytesHex = bytes.Length > 0
                            ? Convert.ToHexString(bytes)
                            : null;

                        var sampledRegionRecord = new SessionRegionSampleRecord(
                            Name: regionName,
                            Category: regionCategory,
                            Address: $"0x{regionAddress.ToInt64():X}",
                            Length: region.Length,
                            Required: region.Required,
                            ReadSucceeded: readSucceeded,
                            BytesRead: bytes.Length,
                            BytesHex: bytesHex,
                            Error: readError);
                        regions.Add(sampledRegionRecord);
                        UpdateSessionRegionAccumulator(regionAccumulators, sampledRegionRecord);
                        totalBytesRead += bytes.Length;

                        if (!readSucceeded)
                        {
                            totalRegionReadFailures++;
                        }

                        if (region.Required && !readSucceeded)
                        {
                            requiredReadFailures.Add(regionName);
                        }
                    }

                    var captureDurationMilliseconds = Math.Max(0, stopwatch.ElapsedMilliseconds - sampleStartedElapsed);
                    var sample = new SessionSampleRecord(
                        SampleIndex: sampleIndex,
                        RecordedAtUtc: sampleTimeUtc.ToString("O", CultureInfo.InvariantCulture),
                        ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                        ExpectedElapsedMilliseconds: expectedElapsedMilliseconds,
                        TimingDriftMilliseconds: sampleStartedElapsed - expectedElapsedMilliseconds,
                        CaptureDurationMilliseconds: captureDurationMilliseconds,
                        Regions: regions);

                    sampleWriter.WriteLine(JsonSerializer.Serialize(sample, NdjsonOptions));
                    sampleWriter.Flush();
                    recordedSampleCount++;

                    DrainSessionMarkerInputFile(
                        markerWriter,
                        sessionMarkerInputFile,
                        ref markerInputProcessedLineCount,
                        options.SessionLabel,
                        sampleIndex,
                        stopwatch,
                        markerKinds,
                        ref markerCount,
                        warnings,
                        emittedMarkerInputWarnings);

                    if (cancelRequested)
                    {
                        interrupted = true;
                        break;
                    }
                }

                var completedAtUtc = DateTimeOffset.UtcNow;
                var terminalSampleIndex = recordedSampleCount > 0
                    ? Math.Max(0, recordedSampleCount - 1)
                    : 0;

                DrainSessionMarkerInputFile(
                    markerWriter,
                    sessionMarkerInputFile,
                    ref markerInputProcessedLineCount,
                    options.SessionLabel,
                    terminalSampleIndex,
                    stopwatch,
                    markerKinds,
                    ref markerCount,
                    warnings,
                    emittedMarkerInputWarnings);

                if (interrupted)
                {
                    warnings.Add($"Session recording was interrupted after {recordedSampleCount} of {options.SessionSampleCount} samples.");
                    RecordSessionMarker(
                        markerWriter,
                        CreateSessionMarker(
                            Kind: "session-interrupted",
                            RecordedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                            ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                            SampleIndex: terminalSampleIndex,
                            Label: options.SessionLabel,
                            Message: "Session recording interrupted by the operator.",
                            Source: "system",
                            Metadata: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                            {
                                ["recordedSampleCount"] = recordedSampleCount.ToString(CultureInfo.InvariantCulture),
                                ["requestedSampleCount"] = options.SessionSampleCount.ToString(CultureInfo.InvariantCulture)
                            }),
                        markerKinds,
                        ref markerCount);
                }

                RecordSessionMarker(
                    markerWriter,
                    CreateSessionMarker(
                        Kind: "session-end",
                        RecordedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                        ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                        SampleIndex: terminalSampleIndex,
                        Label: options.SessionLabel,
                        Message: interrupted
                            ? "Session recording ended after interruption."
                            : "Session recording completed.",
                        Source: "system",
                        Metadata: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                        {
                            ["outcome"] = interrupted ? "interrupted" : "completed",
                            ["recordedSampleCount"] = recordedSampleCount.ToString(CultureInfo.InvariantCulture)
                        }),
                    markerKinds,
                    ref markerCount);
                sampleWriter.Flush();
                markerWriter.Flush();
                sampleWriter.Dispose();
                markerWriter.Dispose();

                if (requiredReadFailures.Count > 0)
                {
                    warnings.Add($"Required watchset regions had read failures: {string.Join(", ", requiredReadFailures.OrderBy(static name => name, StringComparer.OrdinalIgnoreCase))}");
                }

                PromoteTempFile(tempModulesFile, modulesFile);
                PromoteTempFile(tempSamplesFile, samplesFile);
                PromoteTempFile(tempMarkersFile, markersFile);

                var missingFiles = BuildMissingSessionFiles(watchsetFile, modulesFile, samplesFile, markersFile);
                if (missingFiles.Count > 0)
                {
                    warnings.Add($"Session output files are missing after recording: {string.Join(", ", missingFiles)}");
                }

                result = new SessionRecordResult(
                    SchemaVersion: SessionRecordingSchemaVersion,
                    Mode: "record-session",
                    SessionId: sessionId,
                    OutputDirectory: outputDirectory,
                    ProcessId: target.ProcessId,
                    ProcessName: target.ProcessName,
                    ModuleName: target.ModuleName,
                    MainWindowTitle: target.MainWindowTitle,
                    WatchsetFile: watchsetFile,
                    WatchsetRegionCount: watchset.Regions.Count,
                    RequestedSampleCount: options.SessionSampleCount,
                    RecordedSampleCount: recordedSampleCount,
                    IntervalMilliseconds: options.SessionIntervalMilliseconds,
                    Label: options.SessionLabel,
                    StartedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                    CompletedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                    ManifestFile: manifestFile,
                    SamplesFile: samplesFile,
                    MarkersFile: markersFile,
                    ModulesFile: modulesFile,
                    Interrupted: interrupted,
                    SessionMarkerInputFile: sessionMarkerInputFile,
                    MarkerCount: markerCount,
                    MarkerKinds: markerKinds.Keys
                        .OrderBy(static kind => kind, StringComparer.OrdinalIgnoreCase)
                        .ToArray(),
                    RequestedRegionByteCount: requestedRegionByteCount,
                    TotalBytesRead: totalBytesRead,
                    TotalRegionReadFailures: totalRegionReadFailures,
                    IntegrityStatus: missingFiles.Count > 0 ? "failed" : (!interrupted && requiredReadFailures.Count == 0 && totalRegionReadFailures == 0 ? "ok" : "warning"),
                    MissingFiles: missingFiles,
                    RegionSummaries: BuildSessionRegionSummaries(regionAccumulators),
                    Modules: modules,
                    WatchsetWarnings: watchsetWarnings,
                    Warnings: warnings
                        .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                        .Distinct(StringComparer.OrdinalIgnoreCase)
                        .ToArray());
            }

            if (cancelHandler is not null)
            {
                Console.CancelKeyPress -= cancelHandler;
            }

            File.WriteAllText(tempManifestFile, JsonOutput.Serialize(result));
            PromoteTempFile(tempManifestFile, manifestFile);

            if (options.JsonOutput)
            {
                Console.WriteLine(JsonOutput.Serialize(result));
                return 0;
            }

            Console.WriteLine($"Session recorded: {result.SessionId}");
            Console.WriteLine($"Output directory: {result.OutputDirectory}");
            Console.WriteLine($"Watchset file:    {result.WatchsetFile}");
            Console.WriteLine($"Samples:          {result.RecordedSampleCount}/{result.RequestedSampleCount} at {result.IntervalMilliseconds} ms");
            Console.WriteLine($"Regions:          {result.WatchsetRegionCount}");
            Console.WriteLine($"Markers:          {result.MarkerCount}");
            Console.WriteLine($"Bytes read:       {result.TotalBytesRead}");
            Console.WriteLine($"Interrupted:      {(result.Interrupted ? "yes" : "no")}");
            Console.WriteLine($"Manifest:         {result.ManifestFile}");
            Console.WriteLine($"Samples file:     {result.SamplesFile}");
            Console.WriteLine($"Markers file:     {result.MarkersFile}");
            Console.WriteLine($"Integrity:        {result.IntegrityStatus}");

            if (result.Warnings.Count > 0)
            {
                Console.WriteLine();
                Console.WriteLine("Warnings:");
                foreach (var warning in result.Warnings)
                {
                    Console.WriteLine($"- {warning}");
                }
            }

            return 0;
        }
        catch (Exception ex)
        {
            if (cancelHandler is not null)
            {
                Console.CancelKeyPress -= cancelHandler;
            }

            DeleteFileIfExists(tempManifestFile);
            DeleteFileIfExists(tempSamplesFile);
            DeleteFileIfExists(tempMarkersFile);
            DeleteFileIfExists(tempModulesFile);
            Console.Error.WriteLine($"Session recording failed: {ex.Message}");
            return 1;
        }
    }

    private static bool TryBuildReaderBridgeIdentitySearchText(
        ReaderBridgeSnapshotDocument? document,
        out string searchText,
        out string searchSource)
    {
        searchText = string.Empty;
        searchSource = string.Empty;

        var playerName = document?.Current?.Player?.Name;
        if (string.IsNullOrWhiteSpace(playerName) || string.IsNullOrWhiteSpace(document?.SourceFile))
        {
            return false;
        }

        var fileInfo = new FileInfo(document.SourceFile);
        var shardDirectoryName = fileInfo.Directory?.Parent?.Parent?.Name;
        if (string.IsNullOrWhiteSpace(shardDirectoryName))
        {
            return false;
        }

        searchText = $"{playerName}@{shardDirectoryName}";
        searchSource = $"readerbridge-identity ({document.SourceFile})";
        return true;
    }

    private static string ResolveCheatEngineProbeOutputFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, "scripts", "cheat-engine", "RiftReaderProbe.lua");
    }

    private static ProcessStartInfo BuildDebugWorkerStartInfo(string requestFile)
    {
        var hostPath = Environment.ProcessPath ?? Process.GetCurrentProcess().MainModule?.FileName;
        var assemblyPath = System.Reflection.Assembly.GetExecutingAssembly().Location;
        if (string.IsNullOrWhiteSpace(hostPath))
        {
            throw new InvalidOperationException("Unable to resolve the current reader host path for debug worker startup.");
        }

        var isDotnetHost = string.Equals(Path.GetFileName(hostPath), "dotnet", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(Path.GetFileName(hostPath), "dotnet.exe", StringComparison.OrdinalIgnoreCase);

        var arguments = isDotnetHost
            ? $"\"{assemblyPath}\" --debug-worker --debug-request-file \"{requestFile}\""
            : $"--debug-worker --debug-request-file \"{requestFile}\"";

        return new ProcessStartInfo
        {
            FileName = hostPath,
            Arguments = arguments,
            WorkingDirectory = Directory.GetCurrentDirectory(),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
    }

    private static string? TryFindRepoRoot(string startDirectory)
    {
        if (string.IsNullOrWhiteSpace(startDirectory))
        {
            return null;
        }

        var current = new DirectoryInfo(startDirectory);

        while (current is not null)
        {
            var markerFile = Path.Combine(current.FullName, "RiftReader.slnx");
            if (File.Exists(markerFile))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }

    private static int RunStatHubRankingMode(ReaderOptions options)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var snapshotError);
        if (snapshotDocument?.Current?.Player is null)
        {
            Console.Error.WriteLine(snapshotError ?? "Unable to load the latest ReaderBridge export for stat-hub ranking.");
            return 1;
        }

        var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(options.OwnerComponentsFile, out var artifactError);
        if (artifactDocument is null)
        {
            Console.Error.WriteLine(artifactError ?? "Unable to load the player owner-component artifact.");
            return 1;
        }

        var locator = new ProcessLocator();
        string? lookupError;
        using var process = options.ProcessId.HasValue
            ? locator.FindById(options.ProcessId.Value, out lookupError)
            : locator.FindByName(options.ProcessName!, out lookupError);

        if (process is null)
        {
            Console.Error.WriteLine(lookupError ?? "Unable to resolve the target process for live hub mapping.");
            return 1;
        }

        var target = ProcessTarget.FromProcess(process);
        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);
        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open a memory-reading handle for live hub mapping.");
            return 1;
        }

        PlayerStatHubRankResult result;
        try
        {
            result = PlayerStatHubRanker.Rank(reader, snapshotDocument, artifactDocument);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to rank stat hubs: {ex.Message}");
            return 1;
        }

        if (options.CheatEngineStatHubs)
        {
            var outputFile = ResolveCheatEngineProbeOutputFile(options.CheatEngineProbeFile);
            var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

            try
            {
                CheatEngineProbeScriptWriter.WriteProbeScript(
                    reader,
                    target,
                    snapshotDocument,
                    inspectionRadius,
                    options.MaxHits,
                    outputFile,
                    statHubs: result);
                Console.WriteLine($"Cheat Engine probe script generated: {outputFile}");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Unable to generate Cheat Engine probe script: {ex.Message}");
                return 1;
            }
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("Use this tool only against Rift client artifacts and processes you explicitly intend to inspect.");
        Console.WriteLine();
        Console.WriteLine(PlayerStatHubRankTextFormatter.Format(result));
        return 0;
    }

    private static SessionInspectResult? BuildSessionInspectResult(string? sessionDirectory, out string? error)
    {
        var package = SessionPackageManifestLoader.TryLoad(sessionDirectory, out error);
        if (package is null)
        {
            return null;
        }

        var warnings = new List<string>();
        AddSessionWarnings(warnings, package.Warnings);

        SessionRecordResult? recordingManifest = null;
        if (!string.IsNullOrWhiteSpace(package.RecordingManifestFile))
        {
            recordingManifest = SessionRecordManifestLoader.TryLoad(package.RecordingManifestFile, out var recordingError);
            if (recordingManifest is null)
            {
                warnings.Add(recordingError ?? $"Unable to load session recording manifest '{package.RecordingManifestFile}'.");
            }
            else
            {
                AddSessionWarnings(warnings, recordingManifest.Warnings);
                AddSessionWarnings(warnings, recordingManifest.WatchsetWarnings);
            }
        }

        ReaderBridgeSnapshotDocument? readerBridgeSnapshot = null;
        if (!string.IsNullOrWhiteSpace(package.ReaderBridgeSnapshotFile))
        {
            readerBridgeSnapshot = ReaderBridgeSnapshotLoader.TryLoad(package.ReaderBridgeSnapshotFile, out var readerBridgeError);
            if (readerBridgeSnapshot is null)
            {
                warnings.Add(readerBridgeError ?? $"Unable to load ReaderBridge snapshot '{package.ReaderBridgeSnapshotFile}'.");
            }
        }

        var samples = Array.Empty<SessionSampleRecord>();
        if (!string.IsNullOrWhiteSpace(package.SamplesFile))
        {
            var loadedSamples = SessionNdjsonLoader.TryLoadSamples(package.SamplesFile, out var sampleError);
            if (loadedSamples is null)
            {
                warnings.Add(sampleError ?? $"Unable to load session samples '{package.SamplesFile}'.");
            }
            else
            {
                samples = loadedSamples.ToArray();
            }
        }

        var markers = Array.Empty<SessionMarkerRecord>();
        if (!string.IsNullOrWhiteSpace(package.MarkersFile))
        {
            var loadedMarkers = SessionNdjsonLoader.TryLoadMarkers(package.MarkersFile, out var markerError);
            if (loadedMarkers is null)
            {
                warnings.Add(markerError ?? $"Unable to load session markers '{package.MarkersFile}'.");
            }
            else
            {
                markers = loadedMarkers.ToArray();
            }
        }

        if (recordingManifest is not null)
        {
            if (samples.Length > 0 && recordingManifest.RecordedSampleCount != samples.Length)
            {
                warnings.Add(
                    $"Session sample count mismatch: package loaded {samples.Length} sample records, but the recording manifest reports {recordingManifest.RecordedSampleCount}.");
            }

            if (markers.Length > 0 && recordingManifest.MarkerCount != markers.Length)
            {
                warnings.Add(
                    $"Session marker count mismatch: package loaded {markers.Length} marker records, but the recording manifest reports {recordingManifest.MarkerCount}.");
            }
        }

        ValidateSessionMarkerTimeline(markers, samples.Length, warnings);

        var maxTimingDriftMilliseconds = samples.Length > 0
            ? (long?)samples.Max(static sample => AbsoluteSessionValue(sample.TimingDriftMilliseconds))
            : null;
        var maxCaptureDurationMilliseconds = samples.Length > 0
            ? (long?)samples.Max(static sample => sample.CaptureDurationMilliseconds)
            : null;
        var averageCaptureDurationMilliseconds = samples.Length > 0
            ? (long?)Math.Round(samples.Average(static sample => (double)sample.CaptureDurationMilliseconds))
            : null;

        var markerKinds = BuildSessionMarkerKindSummaries(markers);
        var regionSummaries = recordingManifest?.RegionSummaries is { Count: > 0 }
            ? recordingManifest.RegionSummaries
                .OrderByDescending(static region => region.Required)
                .ThenByDescending(static region => region.FailedReadCount)
                .ThenBy(static region => region.Name, StringComparer.OrdinalIgnoreCase)
                .ToArray()
            : BuildSessionRegionSummaries(samples);

        error = null;
        return new SessionInspectResult(
            SchemaVersion: package.SchemaVersion ?? SessionRecordingSchemaVersion,
            Mode: "session-summary",
            SessionDirectory: package.SessionDirectory ?? Path.GetFullPath(sessionDirectory!),
            Package: package,
            RecordingManifest: recordingManifest,
            ReaderBridgeSnapshot: readerBridgeSnapshot,
            Samples: samples,
            LoadedSampleCount: samples.Length,
            LoadedMarkerCount: markers.Length,
            MaxTimingDriftMilliseconds: maxTimingDriftMilliseconds,
            MaxCaptureDurationMilliseconds: maxCaptureDurationMilliseconds,
            AverageCaptureDurationMilliseconds: averageCaptureDurationMilliseconds,
            MarkerKinds: markerKinds,
            Markers: markers,
            Regions: regionSummaries,
            Warnings: warnings
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray());
    }

    private static IReadOnlyList<SessionRegionSummaryRecord> BuildSessionRegionSummaries(IReadOnlyList<SessionSampleRecord> samples)
    {
        var accumulators = new Dictionary<string, SessionRegionAccumulator>(StringComparer.OrdinalIgnoreCase);
        foreach (var sample in samples)
        {
            if (sample?.Regions is null)
            {
                continue;
            }

            foreach (var region in sample.Regions)
            {
                if (region is null)
                {
                    continue;
                }

                UpdateSessionRegionAccumulator(accumulators, region);
            }
        }

        return BuildSessionRegionSummaries(accumulators);
    }

    private static void DrainSessionMarkerInputFile(
        StreamWriter markerWriter,
        string? markerInputFile,
        ref int processedLineCount,
        string? sessionLabel,
        int? sampleIndex,
        Stopwatch stopwatch,
        Dictionary<string, int> markerKinds,
        ref int markerCount,
        List<string> warnings,
        HashSet<string> emittedWarnings)
    {
        if (string.IsNullOrWhiteSpace(markerInputFile))
        {
            return;
        }

        var pendingLines = TryReadPendingSessionMarkerLines(markerInputFile, ref processedLineCount, out var loadError);
        if (pendingLines is null)
        {
            if (!string.IsNullOrWhiteSpace(loadError) && emittedWarnings.Add(loadError))
            {
                warnings.Add(loadError);
            }

            return;
        }

        foreach (var line in pendingLines)
        {
            if (!TryParseExternalSessionMarker(
                    line,
                    stopwatch.ElapsedMilliseconds,
                    sampleIndex,
                    sessionLabel,
                    out var marker,
                    out var parseError))
            {
                if (!string.IsNullOrWhiteSpace(parseError) && emittedWarnings.Add(parseError))
                {
                    warnings.Add(parseError);
                }

                continue;
            }

            if (marker is not null)
            {
                RecordSessionMarker(markerWriter, marker, markerKinds, ref markerCount);
            }
        }
    }

    private static IReadOnlyList<string>? TryReadPendingSessionMarkerLines(string filePath, ref int processedLineCount, out string? error)
    {
        if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
        {
            error = null;
            return Array.Empty<string>();
        }

        List<string> allLines;
        try
        {
            allLines = ReadSharedSessionLines(filePath);
        }
        catch (Exception ex)
        {
            error = $"Unable to read session marker input file '{filePath}': {ex.Message}";
            return null;
        }

        if (processedLineCount < 0 || processedLineCount > allLines.Count)
        {
            processedLineCount = 0;
        }

        var pendingLines = allLines.Skip(processedLineCount).ToArray();
        processedLineCount = allLines.Count;
        error = null;
        return pendingLines;
    }

    private static List<string> ReadSharedSessionLines(string filePath)
    {
        var lines = new List<string>();
        using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);

        while (!reader.EndOfStream)
        {
            lines.Add(reader.ReadLine() ?? string.Empty);
        }

        return lines;
    }

    private static bool TryParseExternalSessionMarker(
        string line,
        long elapsedMilliseconds,
        int? sampleIndex,
        string? sessionLabel,
        out SessionMarkerRecord? marker,
        out string? error)
    {
        marker = null;
        error = null;

        if (string.IsNullOrWhiteSpace(line))
        {
            return false;
        }

        var trimmedLine = line.Trim();
        if (trimmedLine.StartsWith('{'))
        {
            SessionExternalMarkerInputRecord? inputRecord;
            try
            {
                inputRecord = JsonSerializer.Deserialize<SessionExternalMarkerInputRecord>(trimmedLine, NdjsonOptions);
            }
            catch (JsonException ex)
            {
                error = $"Unable to parse session marker input JSON: {ex.Message}";
                return false;
            }

            if (inputRecord is null)
            {
                error = "Session marker input JSON line did not contain a valid marker record.";
                return false;
            }

            marker = CreateSessionMarker(
                Kind: inputRecord.Kind,
                RecordedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: elapsedMilliseconds,
                SampleIndex: sampleIndex,
                Label: string.IsNullOrWhiteSpace(inputRecord.Label) ? sessionLabel : inputRecord.Label,
                Message: inputRecord.Message,
                Source: string.IsNullOrWhiteSpace(inputRecord.Source) ? "external" : inputRecord.Source,
                Metadata: inputRecord.Metadata);
            return true;
        }

        marker = CreateSessionMarker(
            Kind: "note",
            RecordedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ElapsedMilliseconds: elapsedMilliseconds,
            SampleIndex: sampleIndex,
            Label: sessionLabel,
            Message: trimmedLine,
            Source: "external-text");
        return true;
    }

    private static bool WaitForNextSessionSample(
        Stopwatch stopwatch,
        long expectedElapsedMilliseconds,
        Func<bool> isCancelled,
        Action drainMarkers)
    {
        while (!isCancelled())
        {
            var remainingMilliseconds = expectedElapsedMilliseconds - stopwatch.ElapsedMilliseconds;
            if (remainingMilliseconds <= 0)
            {
                return true;
            }

            drainMarkers();
            var sleepMilliseconds = (int)Math.Min(SessionMarkerPollSliceMilliseconds, remainingMilliseconds);
            if (sleepMilliseconds > 0)
            {
                Thread.Sleep(sleepMilliseconds);
            }
        }

        return false;
    }

    private static SessionMarkerRecord CreateSessionMarker(
        string? Kind,
        string RecordedAtUtc,
        long? ElapsedMilliseconds,
        int? SampleIndex,
        string? Label,
        string? Message,
        string? Source = null,
        IReadOnlyDictionary<string, string>? Metadata = null) =>
        new(
            Kind: NormalizeSessionMarkerKind(Kind),
            RecordedAtUtc: RecordedAtUtc,
            ElapsedMilliseconds: ElapsedMilliseconds,
            SampleIndex: SampleIndex,
            Label: string.IsNullOrWhiteSpace(Label) ? null : Label.Trim(),
            Message: string.IsNullOrWhiteSpace(Message) ? null : Message.Trim(),
            Source: string.IsNullOrWhiteSpace(Source) ? null : Source.Trim(),
            Metadata: NormalizeSessionMarkerMetadata(Metadata));

    private static void RecordSessionMarker(
        StreamWriter writer,
        SessionMarkerRecord marker,
        Dictionary<string, int> markerKinds,
        ref int markerCount)
    {
        WriteSessionMarker(writer, marker);
        markerCount++;

        if (markerKinds.TryGetValue(marker.Kind, out var currentCount))
        {
            markerKinds[marker.Kind] = currentCount + 1;
        }
        else
        {
            markerKinds[marker.Kind] = 1;
        }
    }

    private static string NormalizeSessionMarkerKind(string? kind)
    {
        if (string.IsNullOrWhiteSpace(kind))
        {
            return "note";
        }

        var builder = new StringBuilder(kind.Length);
        var previousWasDash = false;
        foreach (var character in kind.Trim().ToLowerInvariant())
        {
            if (char.IsLetterOrDigit(character))
            {
                builder.Append(character);
                previousWasDash = false;
                continue;
            }

            if (!previousWasDash)
            {
                builder.Append('-');
                previousWasDash = true;
            }
        }

        var normalized = builder.ToString().Trim('-');
        return string.IsNullOrWhiteSpace(normalized)
            ? "note"
            : normalized;
    }

    private static IReadOnlyDictionary<string, string>? NormalizeSessionMarkerMetadata(IReadOnlyDictionary<string, string>? metadata)
    {
        if (metadata is null || metadata.Count == 0)
        {
            return null;
        }

        var normalized = metadata
            .Where(static pair => !string.IsNullOrWhiteSpace(pair.Key) && !string.IsNullOrWhiteSpace(pair.Value))
            .ToDictionary(
                static pair => pair.Key.Trim(),
                static pair => pair.Value.Trim(),
                StringComparer.OrdinalIgnoreCase);

        return normalized.Count == 0 ? null : normalized;
    }

    private static void UpdateSessionRegionAccumulator(
        Dictionary<string, SessionRegionAccumulator> accumulators,
        SessionRegionSampleRecord region)
    {
        var key = $"{region.Name}|{region.Category}|{region.Address}|{region.Length}|{region.Required}";
        if (!accumulators.TryGetValue(key, out var accumulator))
        {
            accumulator = new SessionRegionAccumulator(
                region.Name,
                region.Category,
                region.Address,
                region.Length,
                region.Required);
            accumulators[key] = accumulator;
        }

        accumulator.SampleCount++;
        accumulator.TotalBytesRead += region.BytesRead;
        accumulator.LastError = string.IsNullOrWhiteSpace(region.Error) ? accumulator.LastError : region.Error;

        if (region.ReadSucceeded)
        {
            accumulator.SuccessfulReadCount++;
            if (!string.IsNullOrWhiteSpace(region.BytesHex) &&
                accumulator.LastSuccessfulBytesHex is not null &&
                !string.Equals(accumulator.LastSuccessfulBytesHex, region.BytesHex, StringComparison.Ordinal))
            {
                accumulator.ChangedSampleCount++;
            }

            if (!string.IsNullOrWhiteSpace(region.BytesHex))
            {
                accumulator.LastSuccessfulBytesHex = region.BytesHex;
            }
        }
        else
        {
            accumulator.FailedReadCount++;
        }
    }

    private static IReadOnlyList<SessionRegionSummaryRecord> BuildSessionRegionSummaries(
        Dictionary<string, SessionRegionAccumulator> accumulators) =>
        accumulators.Values
            .Select(static accumulator => new SessionRegionSummaryRecord(
                Name: accumulator.Name,
                Category: accumulator.Category,
                Address: accumulator.Address,
                Length: accumulator.Length,
                Required: accumulator.Required,
                SampleCount: accumulator.SampleCount,
                SuccessfulReadCount: accumulator.SuccessfulReadCount,
                FailedReadCount: accumulator.FailedReadCount,
                TotalBytesRead: accumulator.TotalBytesRead,
                ChangedSampleCount: accumulator.ChangedSampleCount,
                LastError: accumulator.LastError))
            .OrderByDescending(static region => region.Required)
            .ThenByDescending(static region => region.FailedReadCount)
            .ThenBy(static region => region.Name, StringComparer.OrdinalIgnoreCase)
            .ToArray();

    private static IReadOnlyList<SessionMarkerKindSummaryRecord> BuildSessionMarkerKindSummaries(IReadOnlyList<SessionMarkerRecord> markers) =>
        markers
            .GroupBy(static marker => NormalizeSessionMarkerKind(marker.Kind), StringComparer.OrdinalIgnoreCase)
            .OrderBy(static group => group.Key, StringComparer.OrdinalIgnoreCase)
            .Select(static group => new SessionMarkerKindSummaryRecord(group.Key, group.Count()))
            .ToArray();

    private static void ValidateSessionMarkerTimeline(
        IReadOnlyList<SessionMarkerRecord> markers,
        int sampleCount,
        List<string> warnings)
    {
        long? lastElapsedMilliseconds = null;
        DateTimeOffset? lastRecordedAtUtc = null;
        var warnedElapsedOrdering = false;
        var warnedTimeOrdering = false;

        foreach (var marker in markers)
        {
            if (marker.ElapsedMilliseconds.HasValue &&
                lastElapsedMilliseconds.HasValue &&
                marker.ElapsedMilliseconds.Value < lastElapsedMilliseconds.Value &&
                !warnedElapsedOrdering)
            {
                warnings.Add("Session markers are not ordered by elapsed time.");
                warnedElapsedOrdering = true;
            }

            if (DateTimeOffset.TryParse(marker.RecordedAtUtc, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var recordedAtUtc))
            {
                if (lastRecordedAtUtc.HasValue && recordedAtUtc < lastRecordedAtUtc.Value && !warnedTimeOrdering)
                {
                    warnings.Add("Session markers are not ordered by recorded timestamp.");
                    warnedTimeOrdering = true;
                }

                lastRecordedAtUtc = recordedAtUtc;
            }

            if (marker.ElapsedMilliseconds.HasValue)
            {
                lastElapsedMilliseconds = marker.ElapsedMilliseconds.Value;
            }

            if (marker.SampleIndex.HasValue &&
                marker.SampleIndex.Value < 0)
            {
                warnings.Add($"Session marker '{marker.Kind}' has negative sample index {marker.SampleIndex.Value}.");
            }

            if (marker.SampleIndex.HasValue &&
                sampleCount > 0 &&
                marker.SampleIndex.Value >= sampleCount)
            {
                warnings.Add($"Session marker '{marker.Kind}' references sample index {marker.SampleIndex.Value}, but only {sampleCount} samples were loaded.");
            }
        }
    }

    private static void AddSessionWarnings(List<string> target, IEnumerable<string>? warnings)
    {
        if (warnings is null)
        {
            return;
        }

        foreach (var warning in warnings)
        {
            if (!string.IsNullOrWhiteSpace(warning))
            {
                target.Add(warning);
            }
        }
    }

    private static long AbsoluteSessionValue(long value) =>
        value == long.MinValue ? long.MaxValue : Math.Abs(value);

    private static void WriteSessionMarker(StreamWriter writer, SessionMarkerRecord marker)
    {
        writer.WriteLine(JsonSerializer.Serialize(marker, NdjsonOptions));
    }

    private static IReadOnlyList<string> BuildMissingSessionFiles(params string[] paths) =>
        paths
            .Where(static path => !string.IsNullOrWhiteSpace(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Where(static path => !File.Exists(path))
            .ToArray();

    private static void PromoteTempFile(string sourcePath, string destinationPath)
    {
        if (!File.Exists(sourcePath))
        {
            throw new FileNotFoundException($"Temporary session file '{sourcePath}' was not created.", sourcePath);
        }

        if (File.Exists(destinationPath))
        {
            throw new IOException($"Destination session file '{destinationPath}' already exists.");
        }

        File.Move(sourcePath, destinationPath);
    }

    private static void DeleteFileIfExists(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch
        {
            // Best-effort temp cleanup only.
        }
    }

    private static bool TryParseSessionAddress(string? value, out nint address)
    {
        address = 0;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        long parsedValue;
        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            if (!long.TryParse(value[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out parsedValue))
            {
                return false;
            }
        }
        else if (!long.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out parsedValue))
        {
            return false;
        }

        if (parsedValue <= 0)
        {
            return false;
        }

        try
        {
            address = checked((nint)parsedValue);
            return true;
        }
        catch (OverflowException)
        {
            return false;
        }
    }

    private sealed class SessionRegionAccumulator(
        string name,
        string category,
        string address,
        int length,
        bool required)
    {
        public string Name { get; } = name;
        public string Category { get; } = category;
        public string Address { get; } = address;
        public int Length { get; } = length;
        public bool Required { get; } = required;
        public int SampleCount { get; set; }
        public int SuccessfulReadCount { get; set; }
        public int FailedReadCount { get; set; }
        public long TotalBytesRead { get; set; }
        public int ChangedSampleCount { get; set; }
        public string? LastError { get; set; }
        public string? LastSuccessfulBytesHex { get; set; }
    }
}
