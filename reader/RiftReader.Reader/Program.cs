using System.Diagnostics;
using System.Globalization;
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

        if (!options.WriteCheatEngineProbe && !options.CaptureReaderBridgeBestFamily && !options.ReadPlayerCurrent && !options.ReadPlayerCoordAnchor && !options.RecordSession && !scanRequested && (!options.Address.HasValue || !options.Length.HasValue))
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

        var outputDirectory = Path.GetFullPath(options.SessionOutputDirectory!);
        Directory.CreateDirectory(outputDirectory);

        var sessionId = new DirectoryInfo(outputDirectory).Name;
        var watchsetFile = Path.GetFullPath(options.SessionWatchsetFile!);
        var manifestFile = Path.Combine(outputDirectory, "recording-manifest.json");
        var samplesFile = Path.Combine(outputDirectory, "samples.ndjson");
        var markersFile = Path.Combine(outputDirectory, "markers.ndjson");
        var modulesFile = Path.Combine(outputDirectory, "modules.json");

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

        File.WriteAllText(modulesFile, JsonOutput.Serialize(modules));

        var startedAtUtc = DateTimeOffset.UtcNow;
        var requiredReadFailures = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var recordedSampleCount = 0;

        using var sampleWriter = new StreamWriter(samplesFile, append: false);
        using var markerWriter = new StreamWriter(markersFile, append: false);

        var stopwatch = Stopwatch.StartNew();
        WriteSessionMarker(
            markerWriter,
            new SessionMarkerRecord(
                Kind: "session-start",
                RecordedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: 0,
                Label: options.SessionLabel,
                Message: "Session recording started."));

        if (!string.IsNullOrWhiteSpace(options.SessionLabel))
        {
            WriteSessionMarker(
                markerWriter,
                new SessionMarkerRecord(
                    Kind: "label",
                    RecordedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                    ElapsedMilliseconds: 0,
                    Label: options.SessionLabel,
                    Message: "Initial session label."));
        }

        for (var sampleIndex = 0; sampleIndex < options.SessionSampleCount; sampleIndex++)
        {
            if (sampleIndex > 0 && options.SessionIntervalMilliseconds > 0)
            {
                Thread.Sleep(options.SessionIntervalMilliseconds);
            }

            var sampleTimeUtc = DateTimeOffset.UtcNow;
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
                    regions.Add(new SessionRegionSampleRecord(
                        Name: regionName,
                        Category: regionCategory,
                        Address: region.Address ?? string.Empty,
                        Length: region.Length,
                        Required: region.Required,
                        ReadSucceeded: false,
                        BytesRead: 0,
                        BytesHex: null,
                        Error: $"Invalid address '{region.Address}'."));

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

                regions.Add(new SessionRegionSampleRecord(
                    Name: regionName,
                    Category: regionCategory,
                    Address: $"0x{regionAddress.ToInt64():X}",
                    Length: region.Length,
                    Required: region.Required,
                    ReadSucceeded: readSucceeded,
                    BytesRead: bytes.Length,
                    BytesHex: bytesHex,
                    Error: readError));

                if (region.Required && !readSucceeded)
                {
                    requiredReadFailures.Add(regionName);
                }
            }

            var sample = new SessionSampleRecord(
                SampleIndex: sampleIndex,
                RecordedAtUtc: sampleTimeUtc.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                Regions: regions);

            sampleWriter.WriteLine(JsonSerializer.Serialize(sample, NdjsonOptions));
            sampleWriter.Flush();
            recordedSampleCount++;
        }

        var completedAtUtc = DateTimeOffset.UtcNow;
        WriteSessionMarker(
            markerWriter,
            new SessionMarkerRecord(
                Kind: "session-end",
                RecordedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                Label: options.SessionLabel,
                Message: "Session recording completed."));
        markerWriter.Flush();

        if (requiredReadFailures.Count > 0)
        {
            warnings.Add($"Required watchset regions had read failures: {string.Join(", ", requiredReadFailures.OrderBy(static name => name, StringComparer.OrdinalIgnoreCase))}");
        }

        var result = new SessionRecordResult(
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
            Modules: modules,
            WatchsetWarnings: watchsetWarnings,
            Warnings: warnings
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray());

        File.WriteAllText(manifestFile, JsonOutput.Serialize(result));

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
        Console.WriteLine($"Manifest:         {result.ManifestFile}");
        Console.WriteLine($"Samples file:     {result.SamplesFile}");
        Console.WriteLine($"Markers file:     {result.MarkersFile}");

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

    private static void WriteSessionMarker(StreamWriter writer, SessionMarkerRecord marker)
    {
        writer.WriteLine(JsonSerializer.Serialize(marker, NdjsonOptions));
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
}
