using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.CheatEngine;
using RiftReader.Reader.Cli;
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

    private static readonly JsonSerializerOptions NdjsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
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

        if (options.SessionSummary)
        {
            return RunSessionSummaryMode(options);
        }

        if (options.ReadPlayerOrientation)
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

        if (!options.WriteCheatEngineProbe && !options.CaptureReaderBridgeBestFamily && !options.ReadPlayerCurrent && !options.FindPlayerOrientationCandidate && !options.ReadPlayerCoordAnchor && !options.RecordSession && !scanRequested && (!options.Address.HasValue || !options.Length.HasValue))
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
            return RunFindPlayerOrientationCandidateMode(options, target, reader);
        }

        if (options.ReadTargetCurrent)
        {
            return RunReadTargetCurrentMode(options, target, reader);
        }

        if (options.ReadPlayerCoordAnchor)
        {
            return RunReadPlayerCoordAnchorMode(options, process, target, reader);
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

    private static int RunFindPlayerOrientationCandidateMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        if (snapshotDocument?.Current?.Player?.Coord is null)
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the latest ReaderBridge export for player orientation candidate search.");
            return 1;
        }

        PlayerOrientationCandidateSearchResult result;
        try
        {
            result = PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
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

        ModulePatternScanResult? modulePattern = null;
        var trace = traceDocument.Trace;
        if (!string.IsNullOrWhiteSpace(trace.ModuleName) && !string.IsNullOrWhiteSpace(trace.NormalizedPattern ?? trace.InstructionBytes))
        {
            var module = ProcessModuleLocator.FindModule(process, trace.ModuleName, out var moduleError);
            if (module is null)
            {
                Console.Error.WriteLine(moduleError ?? "Unable to resolve the traced module.");
                return 1;
            }

            var pattern = trace.NormalizedPattern;
            if (string.IsNullOrWhiteSpace(pattern))
            {
                pattern = string.Join(' ', Enumerable.Range(0, trace.InstructionBytes!.Replace(" ", string.Empty).Length / 2)
                    .Select(index => trace.InstructionBytes.Replace(" ", string.Empty).Substring(index * 2, 2).ToUpperInvariant()));
            }

            modulePattern = ModulePatternScanner.Scan(
                process,
                reader,
                target.ProcessId,
                target.ProcessName,
                module.ModuleName,
                module.FileName,
                module.BaseAddress.ToInt64(),
                module.ModuleMemorySize,
                pattern!,
                options.ScanContextBytes);
        }

        PlayerCoordAnchorReadResult result;
        try
        {
            result = PlayerCoordAnchorReader.Read(
                reader,
                target.ProcessId,
                target.ProcessName,
                traceDocument.SourceFile,
                traceDocument,
                snapshotDocument,
                modulePattern);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"Unable to read the current player coord anchor: {ex.Message}");
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
                markerWriter.Flush();

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
