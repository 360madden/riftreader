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
using RiftReader.Reader.Navigation;
using RiftReader.Reader.Processes;
using RiftReader.Reader.Scanning;
using RiftReader.Reader.Sessions;
using RiftReader.Reader.Telemetry;

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

        if (options.ImportTomTomWaypoints)
        {
            return RunImportTomTomWaypointsMode(options);
        }

        if (options.ReadPlayerOrientation)
        {
            return RunReadPlayerOrientationMode(options);
        }

        if (options.TelemetryPreflight)
        {
            return RunTelemetryPreflightMode(options);
        }

        if (options.RunTelemetryHost)
        {
            return RunTelemetryHostMode(options);
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

        if (options.PlanNavigationRoute)
        {
            return RunPlanNavigationRouteMode(options, target);
        }

        if (!options.WriteCheatEngineProbe && !options.CaptureReaderBridgeBestFamily && !options.ReadPlayerCurrent && !options.FindPlayerOrientationCandidate && !options.ReadTargetCurrent && !options.ReadNavigationCurrent && !options.CaptureNavigationWaypoint && !options.NavigateWaypointRoute && !options.NavigateWaypoints && !options.ReadPlayerCoordAnchor && !options.RecordSession && !options.RunTelemetryHost && !scanRequested && (!options.Address.HasValue || !options.Length.HasValue))
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

        if (options.ReadNavigationCurrent)
        {
            return RunReadNavigationCurrentMode(options, process, target, reader);
        }

        if (options.CaptureNavigationWaypoint)
        {
            return RunCaptureNavigationWaypointMode(options, target, reader);
        }

        if (options.NavigateWaypointRoute)
        {
            return RunNavigateWaypointRouteMode(options, process, target, reader);
        }

        if (options.NavigateWaypoints)
        {
            return RunNavigateWaypointsMode(options, process, target, reader);
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
        var readerBridgeDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        var validatorDocument = ValidatorSnapshotLoader.TryLoad(null, out var validatorLoadError);
        var bootstrapDocuments = BuildPlayerCurrentBootstrapDocuments(readerBridgeDocument, validatorDocument);

        if (bootstrapDocuments.Count == 0)
        {
            var errors = new[]
                {
                    loadError,
                    validatorLoadError
                }
                .Where(static error => !string.IsNullOrWhiteSpace(error))
                .ToArray();

            Console.Error.WriteLine(errors.Length > 0
                ? string.Join(" ", errors)
                : "Unable to load any player-current bootstrap snapshot.");
            return 1;
        }

        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);

        var failures = new List<string>(bootstrapDocuments.Count);

        for (var index = 0; index < bootstrapDocuments.Count; index++)
        {
            var document = bootstrapDocuments[index];

            try
            {
                var result = PlayerCurrentReader.ReadCurrent(
                    reader,
                    target.ProcessId,
                    target.ProcessName,
                    document,
                    inspectionRadius,
                    options.MaxHits);

                if (options.JsonOutput)
                {
                    Console.WriteLine(JsonOutput.Serialize(result));
                    return 0;
                }

                Console.WriteLine(PlayerCurrentReadTextFormatter.Format(result));
                return 0;
            }
            catch (Exception ex)
            {
                failures.Add($"[{index + 1}/{bootstrapDocuments.Count}] {document.SourceFile}: {ex.Message}");
            }
        }

        Console.Error.WriteLine($"Unable to read the current player snapshot: {string.Join(" | ", failures)}");
        return 1;
    }

    private static int RunFindPlayerOrientationCandidateMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var readerBridgeDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
        var validatorDocument = ValidatorSnapshotLoader.TryLoad(null, out var validatorLoadError);
        var bootstrapDocuments = BuildPlayerCurrentBootstrapDocuments(readerBridgeDocument, validatorDocument)
            .Where(static document => document.Current?.Player?.Coord is not null)
            .ToArray();

        if (bootstrapDocuments.Length == 0)
        {
            var errors = new[]
                {
                    loadError,
                    validatorLoadError
                }
                .Where(static error => !string.IsNullOrWhiteSpace(error))
                .ToArray();

            Console.Error.WriteLine(errors.Length > 0
                ? string.Join(" ", errors)
                : "Unable to load any player-orientation bootstrap snapshot.");
            return 1;
        }

        var failures = new List<string>(bootstrapDocuments.Length);

        for (var index = 0; index < bootstrapDocuments.Length; index++)
        {
            var document = bootstrapDocuments[index];

            try
            {
                var result = PlayerOrientationCandidateFinder.Find(
                    reader,
                    target.ProcessId,
                    target.ProcessName,
                    document,
                    options.MaxHits,
                    orientationCandidateLedgerFile: options.OrientationCandidateLedgerFile);

                if (result.CandidateCount == 0 && result.PointerHopCandidateCount == 0)
                {
                    failures.Add($"[{index + 1}/{bootstrapDocuments.Length}] {document.SourceFile}: no live orientation candidates were found for the bootstrap coordinates.");
                    continue;
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
            catch (Exception ex)
            {
                failures.Add($"[{index + 1}/{bootstrapDocuments.Length}] {document.SourceFile}: {ex.Message}");
            }
        }

        Console.Error.WriteLine($"Unable to find a live player orientation candidate: {string.Join(" | ", failures)}");
        return 1;
    }

    private static IReadOnlyList<ReaderBridgeSnapshotDocument> BuildPlayerCurrentBootstrapDocuments(
        ReaderBridgeSnapshotDocument? readerBridgeDocument,
        ValidatorSnapshotDocument? validatorDocument)
    {
        var candidates = new List<(ReaderBridgeSnapshotDocument Document, DateTime FileWriteTimeUtc, int Priority)>(2);

        if (readerBridgeDocument?.Current?.Player is not null)
        {
            candidates.Add((readerBridgeDocument, TryGetFileLastWriteTimeUtc(readerBridgeDocument.SourceFile), 1));
        }

        if (validatorDocument?.Current is not null)
        {
            candidates.Add((BuildValidatorBootstrapDocument(validatorDocument), TryGetFileLastWriteTimeUtc(validatorDocument.SourceFile), 0));
        }

        return candidates
            .OrderByDescending(static candidate => candidate.FileWriteTimeUtc)
            .ThenByDescending(static candidate => candidate.Priority)
            .Select(static candidate => candidate.Document)
            .ToArray();
    }

    private static ReaderBridgeSnapshotDocument BuildValidatorBootstrapDocument(ValidatorSnapshotDocument document)
    {
        var snapshot = document.Current!;
        var exportCount = snapshot.Sequence is >= int.MinValue and <= int.MaxValue
            ? (int)snapshot.Sequence.Value
            : (int?)null;
        long? hpPct = snapshot.Health.HasValue && snapshot.HealthMax is > 0
            ? (long)Math.Clamp((int)Math.Round((double)snapshot.Health.Value / snapshot.HealthMax.Value * 100d), 0, 100)
            : null;

        return new ReaderBridgeSnapshotDocument(
            SourceFile: $"validator-bootstrap: {document.SourceFile}",
            LoadedAtUtc: document.LoadedAtUtc,
            SchemaVersion: 1,
            LastExportAt: document.LastCaptureAt,
            LastReason: document.LastReason,
            ExportCount: exportCount,
            Current: new ReaderBridgeSnapshot(
                SchemaVersion: 1,
                Status: "ready",
                ExportReason: snapshot.Reason ?? document.LastReason,
                ExportCount: exportCount,
                GeneratedAtRealtime: snapshot.CapturedAt,
                SourceMode: "ValidatorBootstrap",
                SourceAddon: "RiftReaderValidator",
                SourceVersion: null,
                Hud: null,
                Player: new ReaderBridgeUnitSnapshot(
                    Id: snapshot.PlayerUnit,
                    Name: snapshot.Name,
                    Level: snapshot.Level,
                    Calling: null,
                    Guild: null,
                    Relation: null,
                    Role: snapshot.Role,
                    Player: true,
                    Combat: snapshot.Combat,
                    Pvp: null,
                    Hp: snapshot.Health,
                    HpMax: snapshot.HealthMax,
                    HpPct: hpPct,
                    Absorb: null,
                    Vitality: null,
                    ResourceKind: snapshot.ManaMax.HasValue ? "Mana" :
                        snapshot.EnergyMax.HasValue ? "Energy" :
                        snapshot.Power.HasValue ? "Power" :
                        snapshot.ChargeMax.HasValue ? "Charge" :
                        null,
                    Resource: snapshot.Mana ?? snapshot.Energy ?? snapshot.Power ?? snapshot.Charge,
                    ResourceMax: snapshot.ManaMax ?? snapshot.EnergyMax ?? snapshot.ChargeMax,
                    ResourcePct: null,
                    Mana: snapshot.Mana,
                    ManaMax: snapshot.ManaMax,
                    Energy: snapshot.Energy,
                    EnergyMax: snapshot.EnergyMax,
                    Power: snapshot.Power,
                    Charge: snapshot.Charge,
                    ChargeMax: snapshot.ChargeMax,
                    ChargePct: null,
                    Planar: null,
                    PlanarMax: null,
                    PlanarPct: null,
                    Combo: snapshot.Combo,
                    Zone: snapshot.Zone,
                    LocationName: snapshot.LocationName,
                    Coord: snapshot.Coord,
                    Distance: null,
                    Ttd: null,
                    TtdText: null,
                    Cast: null),
                Target: null,
                Telemetry: null,
                PlayerBuffLines: Array.Empty<string>(),
                PlayerDebuffLines: Array.Empty<string>(),
                TargetBuffLines: Array.Empty<string>(),
                TargetDebuffLines: Array.Empty<string>()));
    }

    private static DateTime TryGetFileLastWriteTimeUtc(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return DateTime.MinValue;
        }

        try
        {
            return File.Exists(path)
                ? File.GetLastWriteTimeUtc(path)
                : DateTime.MinValue;
        }
        catch
        {
            return DateTime.MinValue;
        }
    }

    private static FloatSequenceScanResult? TryScanBootstrapPlayerCoords(
        ProcessMemoryReader reader,
        ProcessTarget target,
        IReadOnlyList<ReaderBridgeSnapshotDocument> bootstrapDocuments,
        int contextBytes,
        int maxHits,
        double scanTolerance = 0d)
    {
        foreach (var document in bootstrapDocuments)
        {
            var playerCoord = document.Current?.Player?.Coord;
            if (playerCoord?.X is not double coordX || playerCoord.Y is not double coordY || playerCoord.Z is not double coordZ)
            {
                continue;
            }

            var result = ProcessFloatSequenceScanner.ScanFloatTriplet(
                reader,
                target.ProcessId,
                target.ProcessName,
                $"player-coords ({document.SourceFile})",
                (float)coordX,
                (float)coordY,
                (float)coordZ,
                contextBytes,
                maxHits,
                scanTolerance);

            if (result.HitCount > 0)
            {
                return result;
            }
        }

        return null;
    }

    private static PlayerSignatureScanResult? TryScanBootstrapPlayerSignature(
        ProcessMemoryReader reader,
        ProcessTarget target,
        IReadOnlyList<ReaderBridgeSnapshotDocument> bootstrapDocuments,
        int inspectionRadius,
        int maxHits)
    {
        foreach (var document in bootstrapDocuments)
        {
            var player = document.Current?.Player;
            var playerCoord = player?.Coord;
            if (playerCoord?.X is not double coordX || playerCoord.Y is not double coordY || playerCoord.Z is not double coordZ)
            {
                continue;
            }

            var result = ProcessPlayerSignatureScanner.ScanReaderBridgePlayerSignature(
                reader,
                target.ProcessId,
                target.ProcessName,
                $"player-signature ({document.SourceFile})",
                (float)coordX,
                (float)coordY,
                (float)coordZ,
                player?.Level,
                player?.Hp,
                player?.HpMax,
                player?.Name,
                player?.LocationName,
                inspectionRadius,
                maxHits);

            if (result.FamilyCount > 0 && result.HitCount > 0)
            {
                return result;
            }
        }

        return null;
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

    private static int RunReadNavigationCurrentMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        if (!TryLoadWaypointNavigationConfiguration(options, out var configuration, out var loadError))
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the waypoint navigation configuration.");
            return 1;
        }

        if (!TryResolveWaypoint(configuration!, options.DestinationWaypointId, "destination", out var destinationWaypoint, out var waypointError))
        {
            Console.Error.WriteLine(waypointError ?? "Unable to resolve the destination waypoint.");
            return 1;
        }

        var resolvedConfiguration = configuration!;
        var resolvedDestinationWaypoint = destinationWaypoint!;

        var snapshotDocument = TryLoadExplicitReaderBridgeSnapshot(options.ReaderBridgeSnapshotFile);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var poseSource = NavigationPoseSourceFactory.TryCreate(
            reader,
            target.ProcessId,
            target.ProcessName,
            snapshotDocument,
            inspectionRadius,
            NavigationPoseSourcePolicy.AllowFallback,
            options.MaxHits,
            out var poseError);

        if (poseSource is null)
        {
            Console.Error.WriteLine(poseError ?? "Unable to resolve a navigation pose anchor.");
            return 1;
        }

        var arrivalRadius = ResolveArrivalRadius(options.ArrivalRadius, resolvedDestinationWaypoint, resolvedConfiguration.Movement);
        var facing = TryBuildReadOnlyNavigationFacingSummary(
            process,
            target,
            reader,
            snapshotDocument,
            resolvedDestinationWaypoint,
            poseSource.InitialSample);
        var result = NavigationMath.BuildSummary(
            target.ProcessId,
            target.ProcessName,
            resolvedConfiguration.SourceFile,
            resolvedDestinationWaypoint,
            poseSource.InitialSample,
            poseSource.Source.AnchorSource,
            arrivalRadius,
            facing);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(NavigationVectorSummaryTextFormatter.Format(result));
        return 0;
    }

    private static int RunPlanNavigationRouteMode(ReaderOptions options, ProcessTarget target)
    {
        if (!TryLoadWaypointNavigationConfiguration(options, out var configuration, out var loadError))
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the waypoint navigation configuration.");
            return 1;
        }

        var resolvedConfiguration = configuration!;
        if (!TryResolveRouteWaypoints(resolvedConfiguration, options, out var routeWaypoints, out var routeError))
        {
            Console.Error.WriteLine(routeError ?? "Unable to resolve the navigation route.");
            return 1;
        }

        var result = WaypointRoutePlanner.BuildPlan(
            processId: target.ProcessId,
            processName: target.ProcessName,
            waypointFile: resolvedConfiguration.SourceFile,
            movement: resolvedConfiguration.Movement,
            routeWaypoints: routeWaypoints);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return string.Equals(result.Status, "success", StringComparison.OrdinalIgnoreCase) ? 0 : 1;
        }

        Console.WriteLine(NavigationRoutePlanTextFormatter.Format(result));
        return string.Equals(result.Status, "success", StringComparison.OrdinalIgnoreCase) ? 0 : 1;
    }

    private static int RunNavigateWaypointRouteMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        if (!TryLoadWaypointNavigationConfiguration(options, out var configuration, out var loadError))
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the waypoint navigation configuration.");
            return 1;
        }

        var resolvedConfiguration = configuration!;
        if (!TryResolveRouteWaypoints(resolvedConfiguration, options, out var routeWaypoints, out var routeError))
        {
            Console.Error.WriteLine(routeError ?? "Unable to resolve the navigation route.");
            return 1;
        }

        var plan = WaypointRoutePlanner.BuildPlan(
            processId: target.ProcessId,
            processName: target.ProcessName,
            waypointFile: resolvedConfiguration.SourceFile,
            movement: resolvedConfiguration.Movement,
            routeWaypoints: routeWaypoints);

        if (!string.Equals(plan.Status, "success", StringComparison.OrdinalIgnoreCase))
        {
            var planFailure = BuildNavigationRouteFailureResult(
                plan,
                routeWaypoints,
                anchorSource: "none",
                stopReason: "route-plan-invalid",
                issues: plan.Issues);

            return EmitNavigationResult(
                options,
                planFailure,
                success: false,
                result => NavigationRouteRunResultTextFormatter.Format(result));
        }

        if (!TryResolveNavigationAutoTurnOptions(options, out var autoTurnOptions, out var autoTurnError))
        {
            Console.Error.WriteLine(autoTurnError ?? "Unable to resolve navigation auto-turn options.");
            return 1;
        }

        var snapshotDocument = TryLoadExplicitReaderBridgeSnapshot(options.ReaderBridgeSnapshotFile);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var poseSource = NavigationPoseSourceFactory.TryCreate(
            reader,
            target.ProcessId,
            target.ProcessName,
            snapshotDocument,
            inspectionRadius,
            NavigationPoseSourcePolicy.StrictCoordTrace,
            options.MaxHits,
            out var poseError);

        if (poseSource is null)
        {
            var anchorFailure = BuildNavigationRouteFailureResult(
                plan,
                routeWaypoints,
                anchorSource: "none",
                stopReason: "anchor-unavailable",
                issues: [poseError ?? "Unable to resolve a navigation pose anchor."]);

            if (!options.JsonOutput)
            {
                Console.Error.WriteLine(poseError ?? "Unable to resolve a navigation pose anchor.");
            }

            return EmitNavigationResult(
                options,
                anchorFailure,
                success: false,
                result => NavigationRouteRunResultTextFormatter.Format(result));
        }

        var movementBackend = new PowerShellMovementBackend(
            NavigationPathResolver.ResolveMovementScriptFile(),
            target.ProcessName,
            target.ProcessId,
            target.MainWindowHandleHex);
        movementBackend.PrepareForMovement();

        if (!NavigationProofCoordAnchorRefresher.TryRefresh(target.ProcessName, target.ProcessId, out var refreshError))
        {
            var anchorFailure = BuildNavigationRouteFailureResult(
                plan,
                routeWaypoints,
                anchorSource: poseSource.Source.AnchorSource,
                stopReason: "anchor-unavailable",
                issues: [refreshError ?? "Unable to refresh the proof coord anchor before live navigation started."]);

            if (!options.JsonOutput)
            {
                Console.Error.WriteLine(refreshError ?? "Unable to refresh the proof coord anchor before live navigation started.");
            }

            return EmitNavigationResult(
                options,
                anchorFailure,
                success: false,
                result => NavigationRouteRunResultTextFormatter.Format(result));
        }

        var refreshedPoseSource = NavigationPoseSourceFactory.TryCreate(
            reader,
            target.ProcessId,
            target.ProcessName,
            snapshotDocument,
            inspectionRadius,
            NavigationPoseSourcePolicy.StrictCoordTrace,
            options.MaxHits,
            out var refreshPoseError);

        if (refreshedPoseSource is null)
        {
            var anchorFailure = BuildNavigationRouteFailureResult(
                plan,
                routeWaypoints,
                anchorSource: poseSource.Source.AnchorSource,
                stopReason: "anchor-unavailable",
                issues: [refreshPoseError ?? "Unable to reacquire the proof coord anchor after live-interaction arming."]);

            if (!options.JsonOutput)
            {
                Console.Error.WriteLine(refreshPoseError ?? "Unable to reacquire the proof coord anchor after live-interaction arming.");
            }

            return EmitNavigationResult(
                options,
                anchorFailure,
                success: false,
                result => NavigationRouteRunResultTextFormatter.Format(result));
        }

        Func<NavigationRouteSegmentTurnRequest, NavigationTurnResult>? turnBeforeSegment = null;
        if (autoTurnOptions.Enabled)
        {
            turnBeforeSegment = request => NavigationAutoTurner.Execute(
                request.CurrentSample,
                refreshedPoseSource.Source,
                movementBackend,
                autoTurnOptions,
                sample => BuildNavigationTurnPlan(
                    process,
                    target,
                    reader,
                    snapshotDocument,
                    request.DestinationWaypoint,
                    sample,
                    autoTurnOptions.WithinDegrees));
        }

        var result = WaypointRouteNavigator.Run(
            target.ProcessId,
            target.ProcessName,
            resolvedConfiguration.SourceFile,
            resolvedConfiguration.Movement,
            routeWaypoints,
            refreshedPoseSource.Source,
            movementBackend,
            turnBeforeSegment);

        return EmitNavigationResult(
            options,
            result,
            success: string.Equals(result.Status, "success", StringComparison.OrdinalIgnoreCase),
            result => NavigationRouteRunResultTextFormatter.Format(result));
    }

    private static bool TryResolveRouteWaypoints(
        WaypointNavigationConfiguration configuration,
        ReaderOptions options,
        out IReadOnlyList<WaypointDefinition> routeWaypoints,
        out string? error)
    {
        var waypointIds = new List<string> { options.StartWaypointId! };
        if (options.ViaWaypointIds is { Count: > 0 } viaWaypointIds)
        {
            waypointIds.AddRange(viaWaypointIds);
        }

        waypointIds.Add(options.DestinationWaypointId!);

        var resolvedWaypoints = new List<WaypointDefinition>();
        foreach (var waypointId in waypointIds)
        {
            if (!TryResolveWaypoint(configuration, waypointId, "route", out var waypoint, out var resolveError))
            {
                routeWaypoints = Array.Empty<WaypointDefinition>();
                error = resolveError ?? $"Unable to resolve route waypoint '{waypointId}'.";
                return false;
            }

            resolvedWaypoints.Add(waypoint!);
        }

        routeWaypoints = resolvedWaypoints;
        error = null;
        return true;
    }

    private static NavigationRouteRunResult BuildNavigationRouteFailureResult(
        NavigationRoutePlanResult plan,
        IReadOnlyList<WaypointDefinition> routeWaypoints,
        string anchorSource,
        string stopReason,
        IReadOnlyList<string> issues)
    {
        var destinationPosition = routeWaypoints.Count > 0
            ? routeWaypoints[^1].Coordinate
            : (NavigationCoordinate?)null;

        return new NavigationRouteRunResult(
            Mode: "navigate-waypoint-route",
            ProcessId: plan.ProcessId,
            ProcessName: plan.ProcessName,
            WaypointFile: plan.WaypointFile,
            Status: "failure",
            StartWaypointId: plan.StartWaypointId,
            DestinationWaypointId: plan.DestinationWaypointId,
            WaypointIds: plan.WaypointIds,
            SegmentCount: plan.SegmentCount,
            CompletedSegmentCount: 0,
            FailedSegmentIndex: null,
            StopReason: stopReason,
            AnchorSource: anchorSource,
            TotalPlanarDistance: plan.TotalPlanarDistance,
            FinalPlanarDistance: 0d,
            TotalPulseCount: 0,
            InitialPosition: null,
            FinalPosition: null,
            DestinationPosition: destinationPosition,
            ElapsedMilliseconds: 0,
            SegmentResults: Array.Empty<NavigationRunResult>(),
            Issues: issues.ToArray());
    }

    private static NavigationFacingSummary TryBuildNavigationFacingSummary(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        WaypointDefinition destinationWaypoint,
        NavigationPoseSample currentSample)
    {
        try
        {
            var leadDocument = ActorFacingBehaviorBackedLeadLoader.TryLoad(null, out var leadError);
            if (leadDocument is null)
            {
                return NavigationMath.BuildUnavailableFacingSummary(
                    status: "lead-unavailable",
                    message: leadError ?? "Unable to load the actor-facing behavior-backed lead.");
            }

            DateTimeOffset processStartTimeUtc;
            try
            {
                processStartTimeUtc = process.StartTime.ToUniversalTime();
            }
            catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                return NavigationMath.BuildUnavailableFacingSummary(
                    status: "process-start-unavailable",
                    message: $"Unable to read the live process start time for PID {process.Id}: {ex.Message}");
            }

            var leadValidation = ActorFacingBehaviorBackedLeadValidator.Validate(
                leadDocument,
                process.ProcessName,
                process.Id,
                processStartTimeUtc);
            if (!leadValidation.IsValid)
            {
                return NavigationMath.BuildUnavailableFacingSummary(
                    status: "lead-invalid",
                    message: leadValidation.Error ?? "The actor-facing behavior-backed lead is not valid for the live process.");
            }

            var orientation = PlayerOrientationReader.ReadLive(reader, target, snapshotDocument, leadDocument);
            var deltaX = destinationWaypoint.X - currentSample.X;
            var deltaZ = destinationWaypoint.Z - currentSample.Z;
            var (_, bearingDegrees) = NavigationMath.ComputeBearing(deltaX, deltaZ);
            return NavigationMath.BuildFacingSummary(orientation, bearingDegrees);
        }
        catch (Exception ex)
        {
            return NavigationMath.BuildUnavailableFacingSummary(
                status: "read-failed",
                message: $"Unable to read live actor-facing data for navigation alignment: {ex.Message}");
        }
    }

    private static NavigationFacingSummary TryBuildReadOnlyNavigationFacingSummary(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        WaypointDefinition destinationWaypoint,
        NavigationPoseSample currentSample)
    {
        var behaviorBackedFacing = TryBuildNavigationFacingSummary(
            process,
            target,
            reader,
            snapshotDocument,
            destinationWaypoint,
            currentSample);
        if (string.Equals(behaviorBackedFacing.Status, "available", StringComparison.OrdinalIgnoreCase))
        {
            return behaviorBackedFacing;
        }

        try
        {
            var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(null, out _);
            if (artifactDocument is null)
            {
                return behaviorBackedFacing;
            }

            var orientation = PlayerOrientationReader.Read(artifactDocument, snapshotDocument);
            var deltaX = destinationWaypoint.X - currentSample.X;
            var deltaZ = destinationWaypoint.Z - currentSample.Z;
            var (_, bearingDegrees) = NavigationMath.ComputeBearing(deltaX, deltaZ);
            var behaviorReason = string.IsNullOrWhiteSpace(behaviorBackedFacing.Reason)
                ? $"Behavior-backed facing status was '{behaviorBackedFacing.Status}'."
                : $"Behavior-backed facing status was '{behaviorBackedFacing.Status}': {behaviorBackedFacing.Reason}";
            var reason = $"{behaviorReason} Owner-components artifact is reported as fallback candidate only, not canonical/actionable navigation truth.";

            return NavigationMath.BuildCandidateFacingSummary(
                orientation,
                bearingDegrees,
                status: "fallback-candidate",
                sourceKind: "owner-components-artifact-candidate-facing",
                reason: reason);
        }
        catch
        {
            return behaviorBackedFacing;
        }
    }

    private static int RunNavigateWaypointsMode(ReaderOptions options, Process process, ProcessTarget target, ProcessMemoryReader reader)
    {
        if (!TryLoadWaypointNavigationConfiguration(options, out var configuration, out var loadError))
        {
            Console.Error.WriteLine(loadError ?? "Unable to load the waypoint navigation configuration.");
            return 1;
        }

        if (!TryResolveWaypoint(configuration!, options.StartWaypointId, "start", out var startWaypoint, out var startError))
        {
            Console.Error.WriteLine(startError ?? "Unable to resolve the start waypoint.");
            return 1;
        }

        if (!TryResolveWaypoint(configuration!, options.DestinationWaypointId, "destination", out var destinationWaypoint, out var destinationError))
        {
            Console.Error.WriteLine(destinationError ?? "Unable to resolve the destination waypoint.");
            return 1;
        }

        var resolvedConfiguration = configuration!;
        var resolvedStartWaypoint = startWaypoint!;
        var resolvedDestinationWaypoint = destinationWaypoint!;

        var snapshotDocument = TryLoadExplicitReaderBridgeSnapshot(options.ReaderBridgeSnapshotFile);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var poseSource = NavigationPoseSourceFactory.TryCreate(
            reader,
            target.ProcessId,
            target.ProcessName,
            snapshotDocument,
            inspectionRadius,
            NavigationPoseSourcePolicy.StrictCoordTrace,
            options.MaxHits,
            out var poseError);

        if (poseSource is null)
        {
            var anchorFailure = BuildNavigationAnchorUnavailableResult(
                target,
                resolvedConfiguration.SourceFile,
                resolvedStartWaypoint,
                resolvedDestinationWaypoint,
                ResolveEffectivePace(options.Pace, resolvedDestinationWaypoint, resolvedConfiguration.Movement),
                ResolveArrivalRadius(options.ArrivalRadius, resolvedDestinationWaypoint, resolvedConfiguration.Movement),
                resolvedConfiguration.Movement.StartRadius,
                "anchor-unavailable");

            if (!options.JsonOutput)
            {
                Console.Error.WriteLine(poseError ?? "Unable to resolve a navigation pose anchor.");
            }

            return EmitNavigationResult(
                options,
                anchorFailure,
                success: false,
                result => NavigationRunResultTextFormatter.Format(result, options.VerboseNavigationEvents));
        }

        var effectivePace = ResolveEffectivePace(options.Pace, resolvedDestinationWaypoint, resolvedConfiguration.Movement);
        var arrivalRadius = ResolveArrivalRadius(options.ArrivalRadius, resolvedDestinationWaypoint, resolvedConfiguration.Movement);
        var maxTravelSeconds = options.MaxTravelSeconds ?? resolvedConfiguration.Movement.MaxTravelSeconds;
        if (!TryResolveNavigationAutoTurnOptions(options, out var autoTurnOptions, out var autoTurnError))
        {
            Console.Error.WriteLine(autoTurnError ?? "Unable to resolve navigation auto-turn options.");
            return 1;
        }

        var movementBackend = new PowerShellMovementBackend(
            NavigationPathResolver.ResolveMovementScriptFile(),
            target.ProcessName,
            target.ProcessId,
            target.MainWindowHandleHex);
        var initialMovementDistance = NavigationMath.ComputePlanarDistance(
            resolvedDestinationWaypoint.X - poseSource.InitialSample.X,
            resolvedDestinationWaypoint.Z - poseSource.InitialSample.Z);
        if (initialMovementDistance > arrivalRadius)
        {
            movementBackend.PrepareForMovement();

            if (!NavigationProofCoordAnchorRefresher.TryRefresh(target.ProcessName, target.ProcessId, out var refreshError))
            {
                var anchorFailure = BuildNavigationAnchorUnavailableResult(
                    target,
                    resolvedConfiguration.SourceFile,
                    resolvedStartWaypoint,
                    resolvedDestinationWaypoint,
                    effectivePace,
                    arrivalRadius,
                    resolvedConfiguration.Movement.StartRadius,
                    "anchor-unavailable");

                if (!options.JsonOutput)
                {
                    Console.Error.WriteLine(refreshError ?? "Unable to refresh the proof coord anchor before live navigation started.");
                }

                return EmitNavigationResult(
                    options,
                    anchorFailure,
                    success: false,
                    result => NavigationRunResultTextFormatter.Format(result, options.VerboseNavigationEvents));
            }

            var refreshedPoseSource = NavigationPoseSourceFactory.TryCreate(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
                inspectionRadius,
                NavigationPoseSourcePolicy.StrictCoordTrace,
                options.MaxHits,
                out var refreshPoseError);

            if (refreshedPoseSource is null)
            {
                var anchorFailure = BuildNavigationAnchorUnavailableResult(
                    target,
                    resolvedConfiguration.SourceFile,
                    resolvedStartWaypoint,
                    resolvedDestinationWaypoint,
                    effectivePace,
                    arrivalRadius,
                    resolvedConfiguration.Movement.StartRadius,
                    "anchor-unavailable");

                if (!options.JsonOutput)
                {
                    Console.Error.WriteLine(refreshPoseError ?? "Unable to reacquire the proof coord anchor after live-interaction arming.");
                }

                return EmitNavigationResult(
                    options,
                    anchorFailure,
                    success: false,
                    result => NavigationRunResultTextFormatter.Format(result, options.VerboseNavigationEvents));
            }

            poseSource = refreshedPoseSource;
        }

        NavigationTurnResult? turnResult = null;

        if (autoTurnOptions.Enabled)
        {
            turnResult = NavigationAutoTurner.Execute(
                poseSource.InitialSample,
                poseSource.Source,
                movementBackend,
                autoTurnOptions,
                sample => BuildNavigationTurnPlan(
                    process,
                    target,
                    reader,
                    snapshotDocument,
                    resolvedDestinationWaypoint,
                    sample,
                    autoTurnOptions.WithinDegrees));

            if (!turnResult.Succeeded)
            {
                var turnFailure = BuildNavigationAutoTurnFailureResult(
                    target,
                    resolvedConfiguration.SourceFile,
                    resolvedStartWaypoint,
                    resolvedDestinationWaypoint,
                    effectivePace,
                    arrivalRadius,
                    resolvedConfiguration.Movement.StartRadius,
                    poseSource.InitialSample,
                    poseSource.Source.AnchorSource,
                    turnResult);

                if (!options.JsonOutput)
                {
                    Console.Error.WriteLine(turnResult.Reason ?? "Auto-turn failed before forward movement could start.");
                }

                return EmitNavigationResult(
                    options,
                    turnFailure,
                    success: false,
                    result => NavigationRunResultTextFormatter.Format(result, options.VerboseNavigationEvents));
            }
        }

        var result = WaypointNavigator.Run(
            target.ProcessId,
            target.ProcessName,
            resolvedConfiguration.SourceFile,
            resolvedConfiguration.Movement,
            resolvedStartWaypoint,
            resolvedDestinationWaypoint,
            poseSource.Source,
            movementBackend,
            effectivePace,
            arrivalRadius,
            maxTravelSeconds);

        if (turnResult is not null)
        {
            result = result with { TurnResult = turnResult };
        }

        return EmitNavigationResult(
            options,
            result,
            success: string.Equals(result.Status, "success", StringComparison.OrdinalIgnoreCase),
            result => NavigationRunResultTextFormatter.Format(result, options.VerboseNavigationEvents));
    }

    private static int RunCaptureNavigationWaypointMode(ReaderOptions options, ProcessTarget target, ProcessMemoryReader reader)
    {
        var snapshotDocument = TryLoadExplicitReaderBridgeSnapshot(options.ReaderBridgeSnapshotFile);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var poseSource = NavigationPoseSourceFactory.TryCreate(
            reader,
            target.ProcessId,
            target.ProcessName,
            snapshotDocument,
            inspectionRadius,
            NavigationPoseSourcePolicy.AllowFallback,
            options.MaxHits,
            out var poseError);

        if (poseSource is null)
        {
            Console.Error.WriteLine(poseError ?? "Unable to resolve a navigation pose anchor.");
            return 1;
        }

        var waypoint = WaypointNavigationConfigurationStore.TryUpsertWaypoint(
            options.NavigationWaypointFile,
            options.CaptureNavigationWaypointId!,
            poseSource.InitialSample,
            options.WaypointLabel,
            options.WaypointZone,
            options.WaypointArrivalRadius,
            options.WaypointPace,
            out var waypointFile,
            out var created,
            out var storeError);

        if (waypoint is null)
        {
            Console.Error.WriteLine(storeError ?? "Unable to capture the waypoint.");
            return 1;
        }

        var result = new WaypointCaptureResult(
            Mode: "capture-navigation-waypoint",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            WaypointFile: waypointFile,
            Status: created ? "created" : "updated",
            WaypointId: waypoint.Id,
            WaypointLabel: waypoint.Label,
            WaypointZone: waypoint.Zone,
            Pace: waypoint.Pace,
            ArrivalRadius: waypoint.ArrivalRadius,
            AnchorSource: poseSource.Source.AnchorSource,
            AnchorAddress: poseSource.InitialSample.AddressHex,
            Position: waypoint.Coordinate);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine(WaypointCaptureResultTextFormatter.Format(result));
        return 0;
    }

    private static int RunImportTomTomWaypointsMode(ReaderOptions options)
    {
        var sourceFile = Path.GetFullPath(options.TomTomSavedVariablesFile!);
        var destinationFile = NavigationPathResolver.ResolveWaypointFile(options.NavigationWaypointFile);

        var result = TomTomWaypointImporter.TryImport(
            new TomTomWaypointImportOptions(
                SourceFile: sourceFile,
                DestinationFile: destinationFile,
                ListNames: options.TomTomListNames ?? Array.Empty<string>(),
                Zone: options.TomTomZone,
                DefaultY: options.TomTomDefaultY ?? 0d,
                IdPrefix: options.TomTomIdPrefix ?? "tomtom",
                ArrivalRadius: options.TomTomArrivalRadius,
                Pace: options.TomTomPace),
            out var error);

        if (result is null)
        {
            Console.Error.WriteLine(error ?? "Unable to import TomTom waypoints.");
            return 1;
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
            return 0;
        }

        Console.WriteLine("TomTom waypoint import");
        Console.WriteLine($"Source:      {result.SourceFile}");
        Console.WriteLine($"Destination: {result.DestinationFile}");
        Console.WriteLine($"Imported:    {result.ImportedWaypointCount}");
        Console.WriteLine($"Preserved:   {result.PreservedWaypointCount}");
        Console.WriteLine($"Updated:     {result.UpdatedWaypointCount}");

        if (result.Lists.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine("Lists:");
            foreach (var list in result.Lists)
            {
                Console.WriteLine($"  {list.Name}: imported={list.ImportedWaypointCount}, skipped={list.SkippedWaypointCount}");
            }
        }

        if (result.Warnings.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine("Warnings:");
            foreach (var warning in result.Warnings)
            {
                Console.WriteLine($"  - {warning}");
            }
        }

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
        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(null, out _);

        PlayerOrientationReadResult result;
        try
        {
            if (options.ProcessId.HasValue || !string.IsNullOrWhiteSpace(options.ProcessName))
            {
                using var process = TryResolveProcess(options, out var resolveError);
                if (process is null)
                {
                    Console.Error.WriteLine(resolveError ?? "Unable to resolve the target process for live player-orientation.");
                    return 1;
                }

                var leadDocument = ActorFacingBehaviorBackedLeadLoader.TryLoad(null, out var leadError);
                if (leadDocument is null)
                {
                    Console.Error.WriteLine(leadError ?? "Unable to load the actor-facing behavior-backed lead.");
                    return 1;
                }

                DateTimeOffset processStartTimeUtc;
                try
                {
                    processStartTimeUtc = process.StartTime.ToUniversalTime();
                }
                catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
                {
                    Console.Error.WriteLine($"Unable to read the live process start time for PID {process.Id}: {ex.Message}");
                    return 1;
                }

                var leadValidation = ActorFacingBehaviorBackedLeadValidator.Validate(
                    leadDocument,
                    process.ProcessName,
                    process.Id,
                    processStartTimeUtc);
                if (!leadValidation.IsValid)
                {
                    Console.Error.WriteLine(leadValidation.Error ?? "The actor-facing behavior-backed lead is not valid for the live process.");
                    return 1;
                }

                var target = ProcessTarget.FromProcess(process);
                using var reader = ProcessMemoryReader.TryOpen(target, out var openError);
                if (reader is null)
                {
                    Console.Error.WriteLine(openError ?? "Unable to open the target process for live player-orientation.");
                    return 1;
                }

                result = PlayerOrientationReader.ReadLive(reader, target, snapshotDocument, leadDocument);
            }
            else
            {
                var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(options.OwnerComponentsFile, out var artifactError);
                if (artifactDocument is null)
                {
                    Console.Error.WriteLine(artifactError ?? "Unable to load the player owner-component artifact.");
                    return 1;
                }

                result = PlayerOrientationReader.Read(artifactDocument, snapshotDocument);
            }
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

    private static int RunTelemetryHostMode(ReaderOptions options)
    {
        using var process = TryResolveProcess(options, out var resolveError);
        if (process is null)
        {
            Console.Error.WriteLine(resolveError ?? "Unable to resolve the target process for telemetry host mode.");
            return 1;
        }

        DateTimeOffset processStartTimeUtc;
        try
        {
            processStartTimeUtc = process.StartTime.ToUniversalTime();
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            Console.Error.WriteLine($"Unable to read the live process start time for PID {process.Id}: {ex.Message}");
            return 1;
        }

        var target = ProcessTarget.FromProcess(process);
        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);
        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open the target process for telemetry host mode.");
            return 1;
        }

        var repoRoot = RepositoryPathLocator.FindRepoRoot();
        var latestSnapshotFile = options.TelemetryOutputFile
            ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.latest.json");
        var eventLogFile = options.TelemetryEventLogFile
            ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.events.ndjson");
        var discoveryLogFile = options.TelemetryDiagnosticsLogFile
            ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.discovery.ndjson");
        var proofAnchorCacheFile = options.TelemetryProofAnchorFile
            ?? Path.Combine(repoRoot, "scripts", "captures", "telemetry-proof-coord-anchor.json");
        var proofCoordAnchorScript = Path.Combine(repoRoot, "scripts", "resolve-proof-coord-anchor.ps1");

        var hostOptions = new TelemetryHostOptions(
            ProcessName: target.ProcessName,
            ProcessId: target.ProcessId,
            PollIntervalMilliseconds: options.TelemetryPollIntervalMilliseconds,
            DiagnosticsEnabled: options.TelemetryDiagnostics,
            ReaderBridgeSnapshotFile: options.ReaderBridgeSnapshotFile,
            PlayerCoordTraceFile: options.PlayerCoordTraceFile,
            LatestSnapshotFile: latestSnapshotFile,
            EventLogFile: eventLogFile,
            DiscoveryLogFile: options.TelemetryDiagnostics ? discoveryLogFile : null,
            ProofCoordAnchorScript: proofCoordAnchorScript,
            ProofAnchorCacheFile: proofAnchorCacheFile,
            ProofAnchorRevalidationInterval: TimeSpan.FromSeconds(5),
            ProofAnchorMaxAge: TimeSpan.FromSeconds(15));

        var logger = new StructuredTelemetryLogger(
            hostOptions.EventLogFile,
            hostOptions.DiagnosticsEnabled ? hostOptions.DiscoveryLogFile : null);
        var publisher = new JsonFileTelemetryPublisher(hostOptions.LatestSnapshotFile);
        var host = new TelemetryHost(
            options: hostOptions,
            process: new TelemetryProcessInfo(
                ProcessId: target.ProcessId,
                ProcessName: target.ProcessName,
                ModuleName: target.ModuleName,
                MainWindowTitle: target.MainWindowTitle,
                StartedAtUtc: processStartTimeUtc),
            contextSource: new AddonContextSource(options.ReaderBridgeSnapshotFile),
            positionSource: new MemoryCoordSource(
                reader,
                target.ProcessId,
                target.ProcessName,
                hostOptions.ProofCoordAnchorScript,
                hostOptions.PlayerCoordTraceFile,
                hostOptions.ProofAnchorCacheFile,
                hostOptions.ProofAnchorRevalidationInterval,
                hostOptions.ProofAnchorMaxAge,
                logger,
                hostOptions.DiagnosticsEnabled),
            facingSource: new MemoryFacingSource(reader, target, processStartTimeUtc, hostOptions.DiagnosticsEnabled),
            merger: new DefaultTelemetryMerger(hostOptions.PollIntervalMilliseconds, hostOptions.DiagnosticsEnabled),
            publisher: publisher,
            logger: logger);

        if (!options.JsonOutput)
        {
            Console.WriteLine("RiftReader.Reader telemetry host");
            Console.WriteLine($"Process: {target.ProcessName} ({target.ProcessId})");
            Console.WriteLine($"Latest snapshot: {hostOptions.LatestSnapshotFile}");
            Console.WriteLine($"Event log: {hostOptions.EventLogFile}");

            if (hostOptions.DiagnosticsEnabled && !string.IsNullOrWhiteSpace(hostOptions.DiscoveryLogFile))
            {
                Console.WriteLine($"Discovery log: {hostOptions.DiscoveryLogFile}");
            }

            Console.WriteLine("Press Ctrl+C to stop.");
            Console.WriteLine();
        }

        using var cancellationSource = new CancellationTokenSource();
        ConsoleCancelEventHandler? handler = null;
        handler = (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cancellationSource.Cancel();
        };

        Console.CancelKeyPress += handler;

        try
        {
            return host.Run(cancellationSource.Token);
        }
        finally
        {
            Console.CancelKeyPress -= handler;
        }
    }

    private static int RunTelemetryPreflightMode(ReaderOptions options)
    {
        using var process = TryResolveProcess(options, out var resolveError);
        if (process is null)
        {
            Console.Error.WriteLine(resolveError ?? "Unable to resolve the target process for telemetry preflight mode.");
            return 1;
        }

        DateTimeOffset processStartTimeUtc;
        try
        {
            processStartTimeUtc = process.StartTime.ToUniversalTime();
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            Console.Error.WriteLine($"Unable to read the live process start time for PID {process.Id}: {ex.Message}");
            return 1;
        }

        var target = ProcessTarget.FromProcess(process);
        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);
        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open the target process for telemetry preflight mode.");
            return 1;
        }

        var repoRoot = RepositoryPathLocator.FindRepoRoot();
        var proofCoordAnchorScript = Path.Combine(repoRoot, "scripts", "resolve-proof-coord-anchor.ps1");
        var proofAnchorCacheFile = options.TelemetryProofAnchorFile
            ?? Path.Combine(repoRoot, "scripts", "captures", "telemetry-proof-coord-anchor.json");
        var hostOptions = new TelemetryHostOptions(
            ProcessName: target.ProcessName,
            ProcessId: target.ProcessId,
            PollIntervalMilliseconds: options.TelemetryPollIntervalMilliseconds,
            DiagnosticsEnabled: options.TelemetryDiagnostics,
            ReaderBridgeSnapshotFile: options.ReaderBridgeSnapshotFile,
            PlayerCoordTraceFile: options.PlayerCoordTraceFile,
            LatestSnapshotFile: options.TelemetryOutputFile
                ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.latest.json"),
            EventLogFile: options.TelemetryEventLogFile
                ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.events.ndjson"),
            DiscoveryLogFile: options.TelemetryDiagnostics
                ? options.TelemetryDiagnosticsLogFile ?? Path.Combine(repoRoot, "scripts", "captures", "readerbridge-telemetry.discovery.ndjson")
                : null,
            ProofCoordAnchorScript: proofCoordAnchorScript,
            ProofAnchorCacheFile: proofAnchorCacheFile,
            ProofAnchorRevalidationInterval: TimeSpan.FromSeconds(5),
            ProofAnchorMaxAge: TimeSpan.FromSeconds(15));

        var processInfo = new TelemetryProcessInfo(
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ModuleName: target.ModuleName,
            MainWindowTitle: target.MainWindowTitle,
            StartedAtUtc: processStartTimeUtc);
        var logger = new NullTelemetryLogger();
        var context = new AddonContextSource(options.ReaderBridgeSnapshotFile).Read();
        var memoryPosition = new MemoryCoordSource(
            reader,
            target.ProcessId,
            target.ProcessName,
            hostOptions.ProofCoordAnchorScript,
            hostOptions.PlayerCoordTraceFile,
            hostOptions.ProofAnchorCacheFile,
            hostOptions.ProofAnchorRevalidationInterval,
            hostOptions.ProofAnchorMaxAge,
            logger,
            hostOptions.DiagnosticsEnabled).Read(context);
        var facing = new MemoryFacingSource(reader, target, processStartTimeUtc, hostOptions.DiagnosticsEnabled).Read(context);
        var snapshot = new DefaultTelemetryMerger(hostOptions.PollIntervalMilliseconds, hostOptions.DiagnosticsEnabled)
            .Merge(1, DateTimeOffset.UtcNow, processInfo, context, memoryPosition, facing);

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(snapshot));
            return memoryPosition.Valid && facing.Valid ? 0 : 1;
        }

        Console.WriteLine("RiftReader.Reader telemetry preflight");
        Console.WriteLine($"Process: {target.ProcessName} ({target.ProcessId})");
        Console.WriteLine($"Memory coords: {(memoryPosition.Valid ? "valid" : "invalid")}");
        Console.WriteLine($"Facing: {(facing.Valid ? "valid" : "invalid")}");
        Console.WriteLine($"Effective position source: {snapshot.Meta.EffectivePositionSource}");
        Console.WriteLine($"Effective facing source: {snapshot.Meta.EffectiveFacingSource}");

        if (!memoryPosition.Valid && !string.IsNullOrWhiteSpace(memoryPosition.Reason))
        {
            Console.WriteLine($"Coord reason: {memoryPosition.Reason}");
        }

        if (!facing.Valid && !string.IsNullOrWhiteSpace(facing.Reason))
        {
            Console.WriteLine($"Facing reason: {facing.Reason}");
        }

        return memoryPosition.Valid && facing.Valid ? 0 : 1;
    }

    private static Process? TryResolveProcess(ReaderOptions options, out string? error)
    {
        var locator = new ProcessLocator();

        if (options.ProcessId.HasValue)
        {
            return locator.FindById(options.ProcessId.Value, out error);
        }

        if (!string.IsNullOrWhiteSpace(options.ProcessName))
        {
            return locator.FindByName(options.ProcessName, out error);
        }

        error = "A process selector was not provided.";
        return null;
    }

    private static ReaderBridgeSnapshotDocument? TryLoadExplicitReaderBridgeSnapshot(string? snapshotFile)
    {
        // Navigation modes must not silently trust the default ReaderBridge
        // SavedVariables file as live truth. It is a post-save snapshot and can
        // lag behind proof-anchor memory immediately after movement.
        return string.IsNullOrWhiteSpace(snapshotFile)
            ? null
            : ReaderBridgeSnapshotLoader.TryLoad(snapshotFile, out _);
    }

    private static int EmitNavigationResult<T>(
        ReaderOptions options,
        T result,
        bool success,
        Func<T, string> textFormatter)
    {
        var summaryWritten = TryWriteNavigationRunSummary(options.NavigationRunSummaryFile, result, out var summaryError);
        if (!summaryWritten && !string.IsNullOrWhiteSpace(summaryError))
        {
            Console.Error.WriteLine(summaryError);
        }

        if (options.JsonOutput)
        {
            Console.WriteLine(JsonOutput.Serialize(result));
        }
        else
        {
            Console.WriteLine(textFormatter(result));
        }

        return success && summaryWritten ? 0 : 1;
    }

    private static bool TryWriteNavigationRunSummary<T>(string? summaryFile, T result, out string? error)
    {
        error = null;
        if (string.IsNullOrWhiteSpace(summaryFile))
        {
            return true;
        }

        try
        {
            var fullPath = Path.GetFullPath(summaryFile);
            var directory = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            File.WriteAllText(fullPath, JsonOutput.Serialize(result));
            return true;
        }
        catch (Exception ex)
        {
            error = $"Unable to write navigation run summary file '{summaryFile}': {ex.Message}";
            return false;
        }
    }

    private static bool TryLoadWaypointNavigationConfiguration(
        ReaderOptions options,
        out WaypointNavigationConfiguration? configuration,
        out string? error)
    {
        configuration = WaypointNavigationConfigurationLoader.TryLoad(options.NavigationWaypointFile, out error);
        return configuration is not null;
    }

    private static bool TryResolveWaypoint(
        WaypointNavigationConfiguration configuration,
        string? waypointId,
        string role,
        out WaypointDefinition? waypoint,
        out string? error)
    {
        if (string.IsNullOrWhiteSpace(waypointId))
        {
            waypoint = null;
            error = $"The {role} waypoint id was not provided.";
            return false;
        }

        if (!configuration.Waypoints.TryGetValue(waypointId.Trim(), out waypoint))
        {
            error = $"The {role} waypoint '{waypointId}' was not found in '{configuration.SourceFile}'.";
            return false;
        }

        error = null;
        return true;
    }

    private static string ResolveEffectivePace(
        string? paceOverride,
        WaypointDefinition destinationWaypoint,
        WaypointMovementSettings movement) =>
        paceOverride ??
        destinationWaypoint.Pace ??
        movement.DefaultPace;

    private static double ResolveArrivalRadius(
        double? arrivalRadiusOverride,
        WaypointDefinition destinationWaypoint,
        WaypointMovementSettings movement) =>
        arrivalRadiusOverride ??
        destinationWaypoint.ArrivalRadius ??
        movement.DefaultArrivalRadius;

    private static bool TryResolveNavigationAutoTurnOptions(
        ReaderOptions options,
        out NavigationAutoTurnOptions resolved,
        out string? error)
    {
        var withinDegrees = options.AutoTurnWithinDegrees ?? 7.5d;
        var turnLeftKey = string.IsNullOrWhiteSpace(options.TurnLeftKey) ? "a" : options.TurnLeftKey.Trim();
        var turnRightKey = string.IsNullOrWhiteSpace(options.TurnRightKey) ? "d" : options.TurnRightKey.Trim();
        var turnPulseMilliseconds = options.TurnPulseMilliseconds ?? 75;
        var postTurnSampleDelayMilliseconds = options.TurnPostSampleDelayMilliseconds ?? 150;
        var settleDelayMilliseconds = options.TurnSettleDelayMilliseconds ?? 250;
        var maxTurnPulses = options.TurnMaxPulses ?? 12;
        var worseningToleranceDegrees = options.TurnWorseningToleranceDegrees ?? 0.5d;
        var maxWorseningPulses = options.TurnMaxWorseningPulses ?? 2;

        if (withinDegrees < 0d)
        {
            resolved = default!;
            error = "--auto-turn-within-degrees cannot be negative.";
            return false;
        }

        if (string.IsNullOrWhiteSpace(turnLeftKey))
        {
            resolved = default!;
            error = "--turn-left-key must not be blank.";
            return false;
        }

        if (string.IsNullOrWhiteSpace(turnRightKey))
        {
            resolved = default!;
            error = "--turn-right-key must not be blank.";
            return false;
        }

        if (turnPulseMilliseconds <= 0)
        {
            resolved = default!;
            error = "--turn-pulse-ms must be positive.";
            return false;
        }

        if (postTurnSampleDelayMilliseconds < 0)
        {
            resolved = default!;
            error = "--turn-post-sample-delay-ms cannot be negative.";
            return false;
        }

        if (settleDelayMilliseconds < 0)
        {
            resolved = default!;
            error = "--turn-settle-delay-ms cannot be negative.";
            return false;
        }

        if (maxTurnPulses <= 0)
        {
            resolved = default!;
            error = "--turn-max-pulses must be positive.";
            return false;
        }

        if (worseningToleranceDegrees < 0d)
        {
            resolved = default!;
            error = "--turn-worsening-tolerance cannot be negative.";
            return false;
        }

        if (maxWorseningPulses <= 0)
        {
            resolved = default!;
            error = "--turn-max-worsening-pulses must be positive.";
            return false;
        }

        resolved = new NavigationAutoTurnOptions(
            Enabled: options.AutoTurnBeforeMove,
            WithinDegrees: withinDegrees,
            TurnLeftKey: turnLeftKey,
            TurnRightKey: turnRightKey,
            TurnPulseMilliseconds: turnPulseMilliseconds,
            PostTurnSampleDelayMilliseconds: postTurnSampleDelayMilliseconds,
            SettleDelayMilliseconds: settleDelayMilliseconds,
            MaxTurnPulses: maxTurnPulses,
            WorseningToleranceDegrees: worseningToleranceDegrees,
            MaxWorseningPulses: maxWorseningPulses);
        error = null;
        return true;
    }

    private static NavigationTurnPlan BuildNavigationTurnPlan(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        WaypointDefinition destinationWaypoint,
        NavigationPoseSample currentSample,
        double alignmentThresholdDegrees)
    {
        var facing = TryBuildNavigationFacingSummary(
            process,
            target,
            reader,
            snapshotDocument,
            destinationWaypoint,
            currentSample);
        var deltaX = destinationWaypoint.X - currentSample.X;
        var deltaZ = destinationWaypoint.Z - currentSample.Z;
        var (_, bearingDegrees) = NavigationMath.ComputeBearing(deltaX, deltaZ);
        return NavigationMath.BuildTurnPlan(facing, bearingDegrees, alignmentThresholdDegrees);
    }

    private static NavigationRunResult BuildNavigationAnchorUnavailableResult(
        ProcessTarget target,
        string waypointFile,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        string pace,
        double arrivalRadius,
        double startRadius,
        string stopReason)
    {
        var events = new[]
        {
            CreateNavigationLifecycleEvent(
                type: "stop",
                status: stopReason,
                position: startWaypoint.Coordinate,
                detail: "A validated coord-trace navigation anchor was unavailable for this run.")
        };

        return new NavigationRunResult(
            Mode: "navigate-waypoints",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            WaypointFile: waypointFile,
            Status: "failure",
            StartWaypointId: startWaypoint.Id,
            DestinationWaypointId: destinationWaypoint.Id,
            Pace: pace,
            AnchorSource: "none",
            StartRadius: startRadius,
            ArrivalRadius: arrivalRadius,
            InitialPlanarDistance: 0d,
            FinalPlanarDistance: 0d,
            PulseCount: 0,
            StopReason: stopReason,
            InitialPosition: startWaypoint.Coordinate,
            FinalPosition: startWaypoint.Coordinate,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: 0,
            Events: events);
    }

    private static NavigationRunResult BuildNavigationAutoTurnFailureResult(
        ProcessTarget target,
        string waypointFile,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        string pace,
        double arrivalRadius,
        double startRadius,
        NavigationPoseSample initialSample,
        string anchorSource,
        NavigationTurnResult turnResult)
    {
        var initialPosition = new NavigationCoordinate(initialSample.X, initialSample.Y, initialSample.Z);
        var initialPlanarDistance = ComputePlanarDistance(initialPosition, destinationWaypoint);
        var finalPlanarDistance = ComputePlanarDistance(turnResult.FinalPosition, destinationWaypoint);
        var events = new[]
        {
            CreateNavigationLifecycleEvent(
                type: "stop",
                status: $"auto-turn-{turnResult.Status}",
                pulseIndex: turnResult.PulseCount,
                position: turnResult.FinalPosition,
                planarDistance: finalPlanarDistance,
                detail: turnResult.Reason ?? "Auto-turn failed before forward movement could start.")
        };

        return new NavigationRunResult(
            Mode: "navigate-waypoints",
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            WaypointFile: waypointFile,
            Status: "failure",
            StartWaypointId: startWaypoint.Id,
            DestinationWaypointId: destinationWaypoint.Id,
            Pace: pace,
            AnchorSource: anchorSource,
            StartRadius: startRadius,
            ArrivalRadius: arrivalRadius,
            InitialPlanarDistance: initialPlanarDistance,
            FinalPlanarDistance: finalPlanarDistance,
            PulseCount: 0,
            StopReason: $"auto-turn-{turnResult.Status}",
            InitialPosition: initialPosition,
            FinalPosition: turnResult.FinalPosition,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: 0,
            TurnResult: turnResult,
            Events: events);
    }

    private static NavigationEvent CreateNavigationLifecycleEvent(
        string type,
        string status,
        NavigationCoordinate position,
        string detail,
        int? pulseIndex = null,
        double? planarDistance = null) =>
        new(
            Stage: "navigation",
            Type: type,
            ElapsedMilliseconds: 0,
            Status: status,
            PulseIndex: pulseIndex,
            Position: position,
            PlanarDistance: planarDistance,
            Detail: detail);

    private static double ComputePlanarDistance(NavigationCoordinate currentPosition, WaypointDefinition destinationWaypoint)
    {
        var deltaX = destinationWaypoint.X - currentPosition.X;
        var deltaZ = destinationWaypoint.Z - currentPosition.Z;
        return NavigationMath.ComputePlanarDistance(deltaX, deltaZ);
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
            var readerBridgeDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var loadError);
            var validatorDocument = ValidatorSnapshotLoader.TryLoad(null, out var validatorLoadError);
            var bootstrapDocuments = BuildPlayerCurrentBootstrapDocuments(readerBridgeDocument, validatorDocument);
            var sequenceResult = TryScanBootstrapPlayerCoords(
                reader,
                target,
                bootstrapDocuments,
                options.ScanContextBytes,
                options.MaxHits,
                options.ScanTolerance);

            if (sequenceResult is null)
            {
                var errors = new[]
                    {
                        loadError,
                        validatorLoadError
                    }
                    .Where(static error => !string.IsNullOrWhiteSpace(error))
                    .ToArray();

                Console.Error.WriteLine(errors.Length > 0
                    ? string.Join(" ", errors)
                    : "Unable to resolve current player coordinates from any bootstrap snapshot.");
                return 1;
            }

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
            var readerBridgeDocument = ReaderBridgeSnapshotLoader.TryLoad(null, out var loadError);
            var validatorDocument = ValidatorSnapshotLoader.TryLoad(null, out var validatorLoadError);
            var bootstrapDocuments = BuildPlayerCurrentBootstrapDocuments(readerBridgeDocument, validatorDocument);
            var signatureResult = TryScanBootstrapPlayerSignature(
                reader,
                target,
                bootstrapDocuments,
                options.ScanContextBytes,
                options.MaxHits);

            if (signatureResult is null)
            {
                var errors = new[]
                    {
                        loadError,
                        validatorLoadError
                    }
                    .Where(static error => !string.IsNullOrWhiteSpace(error))
                    .ToArray();

                Console.Error.WriteLine(errors.Length > 0
                    ? string.Join(" ", errors)
                    : "Unable to resolve current player coordinates from any bootstrap snapshot.");
                return 1;
            }

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
            DateTimeOffset completedAtUtc = startedAtUtc;

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

                completedAtUtc = DateTimeOffset.UtcNow;
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

            }

            if (cancelHandler is not null)
            {
                Console.CancelKeyPress -= cancelHandler;
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
