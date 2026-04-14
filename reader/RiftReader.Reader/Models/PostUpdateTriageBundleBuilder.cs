using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Cli;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Processes;
using RiftReader.Reader.Scanning;
using RiftReader.Reader.Sessions;

namespace RiftReader.Reader.Models;

public static class PostUpdateTriageBundleBuilder
{
    public static PostUpdateTriageBundle Build(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderOptions options)
    {
        ArgumentNullException.ThrowIfNull(process);
        ArgumentNullException.ThrowIfNull(target);
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(options);

        var snapshotDocument = ReaderBridgeSnapshotLoader.TryLoad(options.ReaderBridgeSnapshotFile, out var snapshotError);
        if (snapshotDocument?.Current?.Player?.Coord is not { } playerCoord ||
            playerCoord.X is null ||
            playerCoord.Y is null ||
            playerCoord.Z is null)
        {
            throw new InvalidOperationException(snapshotError ?? "Unable to load the latest ReaderBridge export for post-update triage.");
        }

        var player = snapshotDocument.Current.Player!;
        var snapshotSummary = BuildSnapshotSummary(snapshotDocument);
        var inspectionRadius = Math.Max(options.ScanContextBytes, 192);
        var maxHits = Math.Max(options.MaxHits, 8);

        var playerCurrentValidation = TryRun(
            () => PlayerCurrentReader.ReadCurrent(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
                inspectionRadius,
                maxHits));

        var coordAnchorValidation = BuildCoordAnchorValidation(
            process,
            target,
            reader,
            snapshotDocument,
            options);
        var probeSeeds = BuildProbeSeeds(coordAnchorValidation.Result);

        var structureFamilyScan = TryRun(
            () => ProcessPlayerSignatureScanner.ScanReaderBridgePlayerSignature(
                reader,
                target.ProcessId,
                target.ProcessName,
                $"readerbridge-player-signature ({snapshotDocument.SourceFile})",
                (float)playerCoord.X.Value,
                (float)playerCoord.Y.Value,
                (float)playerCoord.Z.Value,
                player.Level,
                player.Hp,
                player.HpMax,
                player.Name,
                player.LocationName,
                inspectionRadius,
                Math.Max(maxHits, 12)));

        var coordNeighborhoodProbe = TryRun(
            () => PlayerOrientationCandidateFinder.Find(
                reader,
                target.ProcessId,
                target.ProcessName,
                snapshotDocument,
                maxHits,
                probeSeeds));

        var savedSessionEvidence = LoadSavedSessionEvidence(options.SessionWatchsetFile);
        var previousBundleContext = LoadPreviousBundleContext(options.RecoveryBundleFile);
        var familyAddressIndex = BuildFamilyAddressIndex(structureFamilyScan.Result);
        var structureFamilies = BuildStructureFamilies(structureFamilyScan.Result, coordNeighborhoodProbe.Result, previousBundleContext);
        var rankedYawCandidates = BuildRankedYawCandidates(coordNeighborhoodProbe.Result, savedSessionEvidence, familyAddressIndex, coordAnchorValidation.Result, previousBundleContext)
            .Take(maxHits)
            .ToArray();
        var previousBundleEvidence = previousBundleContext.Evidence with
        {
            StableCandidateCount = rankedYawCandidates.Count(static candidate => candidate.SeenInPreviousBundle)
        };
        var survivingAnchors = BuildSurvivingAnchors(snapshotSummary, playerCurrentValidation, coordAnchorValidation);
        var lineageSummaries = BuildLineageSummaries(rankedYawCandidates);

        return new PostUpdateTriageBundle(
            Mode: "post-update-triage",
            GeneratedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            OutputFile: null,
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ModuleName: target.ModuleName,
            MainWindowTitle: target.MainWindowTitle,
            Snapshot: snapshotSummary,
            SurvivingAnchors: survivingAnchors,
            PlayerCurrentValidation: playerCurrentValidation,
            CoordAnchorValidation: coordAnchorValidation,
            StructureFamilyScan: structureFamilyScan,
            CoordNeighborhoodProbe: coordNeighborhoodProbe,
            SavedSessionEvidence: savedSessionEvidence,
            PreviousBundleEvidence: previousBundleEvidence,
            StructureFamilies: structureFamilies,
            RankedYawCandidates: rankedYawCandidates,
            SuggestedWatchRegions: BuildSuggestedWatchRegions(rankedYawCandidates),
            LineageSummaries: lineageSummaries,
            Notes: BuildNotes(snapshotSummary, survivingAnchors, structureFamilyScan.Result, coordNeighborhoodProbe.Result, rankedYawCandidates, probeSeeds, previousBundleEvidence));
    }

    private static PostUpdateTriageSnapshotSummary BuildSnapshotSummary(ReaderBridgeSnapshotDocument snapshotDocument)
    {
        var orientationProbe = snapshotDocument.Current?.OrientationProbe;
        var playerProbe = orientationProbe?.Player;
        var targetProbe = orientationProbe?.Target;

        var orientationProbePresent =
            playerProbe is not null ||
            targetProbe is not null ||
            (orientationProbe?.StatCandidates?.Count ?? 0) > 0;

        return new PostUpdateTriageSnapshotSummary(
            SourceFile: snapshotDocument.SourceFile,
            LoadedAtUtc: snapshotDocument.LoadedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            SchemaVersion: snapshotDocument.SchemaVersion,
            Status: snapshotDocument.Current?.Status,
            ExportCount: snapshotDocument.ExportCount,
            PlayerName: snapshotDocument.Current?.Player?.Name,
            PlayerLevel: snapshotDocument.Current?.Player?.Level,
            PlayerLocation: snapshotDocument.Current?.Player?.LocationName,
            PlayerCoord: snapshotDocument.Current?.Player?.Coord,
            OrientationProbePresent: orientationProbePresent,
            PlayerOrientationProbeHasSignals: HasOrientationSignals(playerProbe),
            TargetOrientationProbeHasSignals: HasOrientationSignals(targetProbe),
            StatOrientationCandidateCount: orientationProbe?.StatCandidates?.Count ?? 0);
    }

    private static bool HasOrientationSignals(ReaderBridgeOrientationProbeUnitSnapshot? probe) =>
        probe is not null &&
        (probe.DirectHeading.HasValue ||
         probe.DirectPitch.HasValue ||
         probe.Yaw.HasValue ||
         !string.IsNullOrWhiteSpace(probe.Facing) ||
         (probe.DetailCandidates?.Count ?? 0) > 0 ||
         (probe.StateCandidates?.Count ?? 0) > 0);

    private static PostUpdateTriageStep<PlayerCoordAnchorReadResult> BuildCoordAnchorValidation(
        Process process,
        ProcessTarget target,
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument snapshotDocument,
        ReaderOptions options)
    {
        var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(options.PlayerCoordTraceFile, out var traceError);
        if (traceDocument?.Trace is null || string.IsNullOrWhiteSpace(traceDocument.SourceFile))
        {
            return new PostUpdateTriageStep<PlayerCoordAnchorReadResult>(false, traceError ?? "Unable to load the latest player coord trace artifact.", null);
        }

        ModulePatternScanResult? modulePattern = null;
        var trace = traceDocument.Trace;
        if (!string.IsNullOrWhiteSpace(trace.ModuleName) && !string.IsNullOrWhiteSpace(trace.NormalizedPattern ?? trace.InstructionBytes))
        {
            var module = ProcessModuleLocator.FindModule(process, trace.ModuleName, out var moduleError);
            if (module is null)
            {
                return new PostUpdateTriageStep<PlayerCoordAnchorReadResult>(false, moduleError ?? "Unable to resolve the traced module.", null);
            }

            var pattern = trace.NormalizedPattern;
            if (string.IsNullOrWhiteSpace(pattern))
            {
                pattern = NormalizeInstructionBytes(trace.InstructionBytes);
            }

            if (!string.IsNullOrWhiteSpace(pattern))
            {
                modulePattern = ModulePatternScanner.Scan(
                    process,
                    reader,
                    target.ProcessId,
                    target.ProcessName,
                    module.ModuleName,
                    module.FileName,
                    module.BaseAddress.ToInt64(),
                    module.ModuleMemorySize,
                    pattern,
                    options.ScanContextBytes);
            }
        }

        return TryRun(
            () => PlayerCoordAnchorReader.Read(
                reader,
                target.ProcessId,
                target.ProcessName,
                traceDocument.SourceFile,
                traceDocument,
                snapshotDocument,
                modulePattern));
    }

    private static string? NormalizeInstructionBytes(string? instructionBytes)
    {
        if (string.IsNullOrWhiteSpace(instructionBytes))
        {
            return null;
        }

        var normalized = instructionBytes.Replace(" ", string.Empty, StringComparison.Ordinal);
        if ((normalized.Length % 2) != 0)
        {
            return null;
        }

        return string.Join(' ', Enumerable.Range(0, normalized.Length / 2)
            .Select(index => normalized.Substring(index * 2, 2).ToUpperInvariant()));
    }

    private static IReadOnlyList<PlayerOrientationProbeSeed> BuildProbeSeeds(PlayerCoordAnchorReadResult? coordAnchorResult)
    {
        var seeds = new List<PlayerOrientationProbeSeed>();

        if (!string.IsNullOrWhiteSpace(coordAnchorResult?.SourceObjectAddress))
        {
            seeds.Add(new PlayerOrientationProbeSeed(
                Address: coordAnchorResult.SourceObjectAddress,
                Source: "coord-anchor-source-object",
                RootScore: 140,
                PreferredCoordOffset: coordAnchorResult.SourceCoordRelativeOffset));
        }

        if (!string.IsNullOrWhiteSpace(coordAnchorResult?.ObjectBaseAddress))
        {
            seeds.Add(new PlayerOrientationProbeSeed(
                Address: coordAnchorResult.ObjectBaseAddress,
                Source: "coord-anchor-object-base",
                RootScore: 90,
                PreferredCoordOffset: coordAnchorResult.CoordXRelativeOffset));
        }

        if (!string.IsNullOrWhiteSpace(coordAnchorResult?.CandidateAddress))
        {
            seeds.Add(new PlayerOrientationProbeSeed(
                Address: coordAnchorResult.CandidateAddress,
                Source: "coord-anchor-candidate-address",
                RootScore: 45,
                PreferredCoordOffset: coordAnchorResult.InferredCoordBaseRelativeOffset));
        }

        return seeds;
    }

    private static PostUpdateTriageSavedSessionEvidence LoadSavedSessionEvidence(string? explicitWatchsetFile)
    {
        var sourceFile = ResolveSessionWatchsetFile(explicitWatchsetFile);
        if (string.IsNullOrWhiteSpace(sourceFile))
        {
            return new PostUpdateTriageSavedSessionEvidence(
                SourceFile: null,
                Loaded: false,
                Error: "Unable to resolve the default session watchset path.",
                PreferredSourceAddress: null,
                HistoricalCoordPrimaryOffset: null,
                HistoricalCoordDuplicateOffset: null,
                HistoricalBasisPrimaryForwardOffset: null,
                HistoricalBasisDuplicateForwardOffset: null,
                HistoricalBasisDuplicateSeparation: null,
                RequiredRegionCount: 0,
                Notes: Array.Empty<string>());
        }

        var watchset = SessionWatchsetLoader.TryLoad(sourceFile, out var error);
        if (watchset is null)
        {
            return new PostUpdateTriageSavedSessionEvidence(
                SourceFile: sourceFile,
                Loaded: false,
                Error: error,
                PreferredSourceAddress: null,
                HistoricalCoordPrimaryOffset: null,
                HistoricalCoordDuplicateOffset: null,
                HistoricalBasisPrimaryForwardOffset: null,
                HistoricalBasisDuplicateForwardOffset: null,
                HistoricalBasisDuplicateSeparation: null,
                RequiredRegionCount: 0,
                Notes: Array.Empty<string>());
        }

        long? preferredSourceAddress = TryParseHexInt64(watchset.PreferredSourceAddress);
        int? coordPrimaryOffset = null;
        int? coordDuplicateOffset = null;
        int? basisPrimaryOffset = null;
        int? basisDuplicateOffset = null;

        if (preferredSourceAddress.HasValue)
        {
            foreach (var region in watchset.Regions ?? Array.Empty<SessionWatchRegion>())
            {
                var regionAddress = TryParseHexInt64(region.Address);
                if (!regionAddress.HasValue)
                {
                    continue;
                }

                var relativeOffset = checked((int)(regionAddress.Value - preferredSourceAddress.Value));
                switch (region.Name)
                {
                    case "selected-source-coord48":
                        coordPrimaryOffset = relativeOffset;
                        break;
                    case "selected-source-coord88":
                        coordDuplicateOffset = relativeOffset;
                        break;
                    case "selected-source-basis60":
                        basisPrimaryOffset = relativeOffset;
                        break;
                    case "selected-source-basis94":
                        basisDuplicateOffset = relativeOffset;
                        break;
                }
            }
        }

        var notes = new List<string>();
        if (coordPrimaryOffset.HasValue && coordDuplicateOffset.HasValue)
        {
            notes.Add($"Historical coord layout preserved in watchset: primary=0x{coordPrimaryOffset.Value:X}, duplicate=0x{coordDuplicateOffset.Value:X}.");
        }

        if (basisPrimaryOffset.HasValue && basisDuplicateOffset.HasValue)
        {
            notes.Add($"Historical basis layout preserved in watchset: primary=0x{basisPrimaryOffset.Value:X}, duplicate=0x{basisDuplicateOffset.Value:X}.");
        }

        return new PostUpdateTriageSavedSessionEvidence(
            SourceFile: sourceFile,
            Loaded: true,
            Error: null,
            PreferredSourceAddress: watchset.PreferredSourceAddress,
            HistoricalCoordPrimaryOffset: coordPrimaryOffset,
            HistoricalCoordDuplicateOffset: coordDuplicateOffset,
            HistoricalBasisPrimaryForwardOffset: basisPrimaryOffset,
            HistoricalBasisDuplicateForwardOffset: basisDuplicateOffset,
            HistoricalBasisDuplicateSeparation:
                basisPrimaryOffset.HasValue && basisDuplicateOffset.HasValue
                    ? basisDuplicateOffset.Value - basisPrimaryOffset.Value
                    : null,
            RequiredRegionCount: watchset.Regions?.Count(static region => region.Required) ?? 0,
            Notes: notes);
    }

    private static string? ResolveSessionWatchsetFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory());
        return repoRoot is null
            ? null
            : Path.Combine(repoRoot, "scripts", "captures", "session-watchset.json");
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
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }

    private static PreviousBundleContext LoadPreviousBundleContext(string? explicitBundleFile)
    {
        var sourceFile = ResolveRecoveryBundleFile(explicitBundleFile);
        if (string.IsNullOrWhiteSpace(sourceFile))
        {
            return PreviousBundleContext.CreateEmpty("Unable to resolve the prior triage bundle path.");
        }

        if (!File.Exists(sourceFile))
        {
            return new PreviousBundleContext(
                new PostUpdateTriagePreviousBundleEvidence(
                    SourceFile: sourceFile,
                    Loaded: false,
                    Error: "No prior triage bundle was available.",
                    GeneratedAtUtc: null,
                    RankedYawCandidateCount: 0,
                    StructureFamilyCount: 0,
                    StableCandidateCount: 0,
                    Notes: Array.Empty<string>()),
                Array.Empty<PreviousYawCandidateFingerprint>(),
                new Dictionary<string, PreviousFamilyFingerprint>(StringComparer.OrdinalIgnoreCase));
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(sourceFile));
            var root = document.RootElement;
            var generatedAtUtc = TryGetString(root, "GeneratedAtUtc");
            var candidates = ParsePreviousYawCandidates(root);
            var families = ParsePreviousFamilies(root);

            var notes = new List<string>();
            if (!string.IsNullOrWhiteSpace(generatedAtUtc))
            {
                notes.Add($"Prior bundle timestamp: {generatedAtUtc}.");
            }

            if (candidates.Count > 0)
            {
                notes.Add($"Prior ranked yaw candidates: {candidates.Count}.");
            }

            return new PreviousBundleContext(
                new PostUpdateTriagePreviousBundleEvidence(
                    SourceFile: sourceFile,
                    Loaded: true,
                    Error: null,
                    GeneratedAtUtc: generatedAtUtc,
                    RankedYawCandidateCount: candidates.Count,
                    StructureFamilyCount: families.Count,
                    StableCandidateCount: 0,
                    Notes: notes),
                candidates,
                families.ToDictionary(static family => family.FamilyId, StringComparer.OrdinalIgnoreCase));
        }
        catch (Exception ex)
        {
            return PreviousBundleContext.CreateEmpty($"Unable to load the prior triage bundle: {ex.Message}", sourceFile);
        }
    }

    private static string? ResolveRecoveryBundleFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory());
        return repoRoot is null
            ? null
            : Path.Combine(repoRoot, "scripts", "captures", "post-update-triage-bundle.json");
    }

    private static List<PreviousYawCandidateFingerprint> ParsePreviousYawCandidates(JsonElement root)
    {
        var candidates = new List<PreviousYawCandidateFingerprint>();
        if (!root.TryGetProperty("RankedYawCandidates", out var rankedElement) || rankedElement.ValueKind is not JsonValueKind.Array)
        {
            return candidates;
        }

        var rank = 0;
        foreach (var element in rankedElement.EnumerateArray())
        {
            candidates.Add(new PreviousYawCandidateFingerprint(
                Rank: rank++,
                Kind: TryGetString(element, "Kind"),
                FamilyId: TryGetString(element, "FamilyId"),
                Address: NormalizeHexAddress(TryGetString(element, "Address")),
                ParentAddress: NormalizeHexAddress(TryGetString(element, "ParentAddress")),
                RootAddress: NormalizeHexAddress(TryGetString(element, "RootAddress")),
                RootSource: TryGetString(element, "RootSource"),
                HopDepth: TryGetInt32(element, "HopDepth") ?? 0,
                BasisPrimaryForwardOffset: NormalizeHexOffset(TryGetString(element, "BasisPrimaryForwardOffset"))));
        }

        return candidates;
    }

    private static List<PreviousFamilyFingerprint> ParsePreviousFamilies(JsonElement root)
    {
        var families = new List<PreviousFamilyFingerprint>();
        if (!root.TryGetProperty("StructureFamilies", out var familiesElement) || familiesElement.ValueKind is not JsonValueKind.Array)
        {
            return families;
        }

        foreach (var element in familiesElement.EnumerateArray())
        {
            var familyId = TryGetString(element, "FamilyId");
            if (string.IsNullOrWhiteSpace(familyId))
            {
                continue;
            }

            families.Add(new PreviousFamilyFingerprint(
                FamilyId: familyId,
                PointerHopCandidateCount: TryGetInt32(element, "PointerHopCandidateCount") ?? 0,
                LocalLayoutCandidateCount: TryGetInt32(element, "LocalLayoutCandidateCount") ?? 0,
                BestPointerHopCandidateAddress: NormalizeHexAddress(TryGetString(element, "BestPointerHopCandidateAddress")),
                BestLocalCandidateAddress: NormalizeHexAddress(TryGetString(element, "BestLocalCandidateAddress"))));
        }

        return families;
    }

    private static string? TryGetString(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;

    private static int? TryGetInt32(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var property) && property.TryGetInt32(out var value)
            ? value
            : null;

    private static string? NormalizeHexOffset(string? value)
    {
        var parsed = TryParseHexInt32(value);
        return parsed.HasValue ? $"0x{parsed.Value:X}" : value;
    }

    private static Dictionary<string, string> BuildFamilyAddressIndex(PlayerSignatureScanResult? scanResult)
    {
        var index = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (scanResult?.Families is null)
        {
            return index;
        }

        foreach (var family in scanResult.Families)
        {
            foreach (var sampleAddress in family.SampleAddresses)
            {
                if (!string.IsNullOrWhiteSpace(sampleAddress))
                {
                    index[sampleAddress] = family.FamilyId;
                }
            }
        }

        return index;
    }

    private static IReadOnlyList<PostUpdateTriageFamilyClusterSummary> BuildStructureFamilies(
        PlayerSignatureScanResult? scanResult,
        PlayerOrientationCandidateSearchResult? orientationResult,
        PreviousBundleContext previousBundleContext)
    {
        if (scanResult?.Families is null)
        {
            return Array.Empty<PostUpdateTriageFamilyClusterSummary>();
        }

        var localCandidates = orientationResult?.Candidates ?? Array.Empty<PlayerOrientationCandidate>();
        var pointerHopCandidates = orientationResult?.PointerHopCandidates ?? Array.Empty<PlayerOrientationPointerHopCandidate>();

        return scanResult.Families
            .Select(family =>
            {
                var localMatches = localCandidates
                    .Where(candidate => family.SampleAddresses.Contains(candidate.HitAddress, StringComparer.OrdinalIgnoreCase))
                    .ToArray();
                var pointerMatches = pointerHopCandidates
                    .Where(candidate => string.Equals(candidate.ParentFamilyId, family.FamilyId, StringComparison.Ordinal))
                    .ToArray();
                previousBundleContext.FamiliesById.TryGetValue(family.FamilyId, out var previousFamily);
                var currentBestLocal = localMatches.OrderByDescending(static candidate => candidate.Score).FirstOrDefault();
                var currentBestPointer = pointerMatches.OrderByDescending(static candidate => candidate.Score).FirstOrDefault();
                var stabilityScore = 0;

                if (previousFamily is not null)
                {
                    stabilityScore += 40;

                    if (string.Equals(NormalizeHexAddress(currentBestLocal?.Address), previousFamily.BestLocalCandidateAddress, StringComparison.OrdinalIgnoreCase))
                    {
                        stabilityScore += 20;
                    }

                    if (string.Equals(NormalizeHexAddress(currentBestPointer?.Address), previousFamily.BestPointerHopCandidateAddress, StringComparison.OrdinalIgnoreCase))
                    {
                        stabilityScore += 25;
                    }
                }

                return new PostUpdateTriageFamilyClusterSummary(
                    FamilyId: family.FamilyId,
                    Signature: family.Signature,
                    HitCount: family.HitCount,
                    BestScore: family.BestScore,
                    Notes: family.Notes,
                    RepresentativeAddressHex: family.RepresentativeAddressHex,
                    SampleAddressCount: family.SampleAddresses.Count,
                    LocalLayoutCandidateCount: localMatches.Length,
                    PointerHopCandidateCount: pointerMatches.Length,
                    BestLocalCandidateAddress: currentBestLocal?.Address,
                    BestPointerHopCandidateAddress: currentBestPointer?.Address,
                    SeenInPreviousBundle: previousFamily is not null,
                    StabilityScore: stabilityScore,
                    PreviousPointerHopCandidateCount: previousFamily?.PointerHopCandidateCount,
                    PreviousLocalLayoutCandidateCount: previousFamily?.LocalLayoutCandidateCount);
            })
            .OrderByDescending(static family => family.BestScore)
            .ThenByDescending(static family => family.StabilityScore)
            .ThenByDescending(static family => family.PointerHopCandidateCount)
            .ThenByDescending(static family => family.LocalLayoutCandidateCount)
            .ToArray();
    }

    private static IReadOnlyList<PostUpdateTriageYawCandidate> BuildRankedYawCandidates(
        PlayerOrientationCandidateSearchResult? orientationResult,
        PostUpdateTriageSavedSessionEvidence savedEvidence,
        IReadOnlyDictionary<string, string> familyAddressIndex,
        PlayerCoordAnchorReadResult? coordAnchorResult,
        PreviousBundleContext previousBundleContext)
    {
        var ranked = new List<PostUpdateTriageYawCandidate>();

        foreach (var candidate in orientationResult?.Candidates ?? Array.Empty<PlayerOrientationCandidate>())
        {
            ranked.Add(BuildLocalYawCandidate(candidate, savedEvidence, familyAddressIndex, coordAnchorResult, previousBundleContext));
        }

        foreach (var candidate in orientationResult?.PointerHopCandidates ?? Array.Empty<PlayerOrientationPointerHopCandidate>())
        {
            ranked.Add(BuildPointerHopYawCandidate(candidate, savedEvidence, coordAnchorResult, previousBundleContext));
        }

        return ranked
            .OrderByDescending(static candidate => candidate.TotalScore)
            .ThenByDescending(static candidate => candidate.EvidenceScore)
            .ThenByDescending(static candidate => candidate.ReaderScore)
            .ToArray();
    }

    private static PostUpdateTriageYawCandidate BuildLocalYawCandidate(
        PlayerOrientationCandidate candidate,
        PostUpdateTriageSavedSessionEvidence savedEvidence,
        IReadOnlyDictionary<string, string> familyAddressIndex,
        PlayerCoordAnchorReadResult? coordAnchorResult,
        PreviousBundleContext previousBundleContext)
    {
        var evidenceNotes = new List<string>();
        var evidenceScore = 0;

        var coordPrimaryOffset = TryParseHexInt32(candidate.CoordPrimaryOffset);
        var coordDuplicateOffset = TryParseHexInt32(candidate.CoordDuplicateOffset);
        var basisPrimaryOffset = TryParseHexInt32(candidate.BasisPrimaryForwardOffset);
        var basisDuplicateOffset = TryParseHexInt32(candidate.BasisDuplicateForwardOffset);

        if (savedEvidence.Loaded)
        {
            if (savedEvidence.HistoricalCoordPrimaryOffset == coordPrimaryOffset)
            {
                evidenceScore += 35;
                evidenceNotes.Add($"Matches historical coord primary offset 0x{coordPrimaryOffset:X}.");
            }

            if (savedEvidence.HistoricalCoordDuplicateOffset == coordDuplicateOffset)
            {
                evidenceScore += 35;
                evidenceNotes.Add($"Matches historical coord duplicate offset 0x{coordDuplicateOffset:X}.");
            }

            if (savedEvidence.HistoricalBasisPrimaryForwardOffset == basisPrimaryOffset)
            {
                evidenceScore += 45;
                evidenceNotes.Add($"Matches historical primary basis forward offset 0x{basisPrimaryOffset:X}.");
            }

            if (savedEvidence.HistoricalBasisDuplicateForwardOffset == basisDuplicateOffset)
            {
                evidenceScore += 45;
                evidenceNotes.Add($"Matches historical duplicate basis forward offset 0x{basisDuplicateOffset:X}.");
            }

            if (savedEvidence.HistoricalBasisDuplicateSeparation.HasValue &&
                basisPrimaryOffset.HasValue &&
                basisDuplicateOffset.HasValue &&
                (basisDuplicateOffset.Value - basisPrimaryOffset.Value) == savedEvidence.HistoricalBasisDuplicateSeparation.Value)
            {
                evidenceScore += 20;
                evidenceNotes.Add($"Matches historical basis duplicate separation 0x{savedEvidence.HistoricalBasisDuplicateSeparation.Value:X}.");
            }
        }

        ApplyLiveCoordAnchorEvidence(
            candidate.Address,
            candidate.ProbeRootAddress,
            candidate.ProbeSource,
            hopDepth: 0,
            coordAnchorResult,
            evidenceNotes,
            ref evidenceScore);
        var familyId = familyAddressIndex.TryGetValue(candidate.HitAddress, out var resolvedFamilyId)
            ? resolvedFamilyId
            : null;
        var previousEvidence = BuildPreviousBundleEvidence(
            candidate.DiscoveryMode,
            familyId,
            candidate.Address,
            candidate.ProbeRootAddress,
            candidate.ProbeSource,
            0,
            candidate.BasisPrimaryForwardOffset,
            previousBundleContext,
            evidenceNotes,
            ref evidenceScore);

        return new PostUpdateTriageYawCandidate(
            Kind: candidate.DiscoveryMode,
            FamilyId: familyId,
            Address: candidate.Address,
            ParentAddress: candidate.HitAddress,
            ReaderScore: candidate.Score,
            EvidenceScore: evidenceScore,
            TotalScore: candidate.Score + evidenceScore,
            BasisPrimaryForwardOffset: candidate.BasisPrimaryForwardOffset,
            BasisDuplicateForwardOffset: candidate.BasisDuplicateForwardOffset,
            CoordPrimaryOffset: candidate.CoordPrimaryOffset,
            CoordDuplicateOffset: candidate.CoordDuplicateOffset,
            YawDegrees: candidate.PreferredEstimate.YawDegrees,
            PitchDegrees: candidate.PreferredEstimate.PitchDegrees,
            BasisIsOrthonormal: candidate.Basis60.IsOrthonormal || candidate.Basis94.IsOrthonormal,
            Determinant: candidate.Basis60.Determinant ?? candidate.Basis94.Determinant,
            DuplicateMaxRowDeltaMagnitude: candidate.BasisDuplicateAgreement?.MaxRowDeltaMagnitude,
            RootAddress: candidate.ProbeRootAddress,
            RootSource: candidate.ProbeSource,
            HopDepth: 0,
            PointerOffset: null,
            SeenInPreviousBundle: previousEvidence.Seen,
            PreviousMatchKind: previousEvidence.MatchKind,
            PreviousRank: previousEvidence.PreviousRank,
            EvidenceNotes: evidenceNotes);
    }

    private static PostUpdateTriageYawCandidate BuildPointerHopYawCandidate(
        PlayerOrientationPointerHopCandidate candidate,
        PostUpdateTriageSavedSessionEvidence savedEvidence,
        PlayerCoordAnchorReadResult? coordAnchorResult,
        PreviousBundleContext previousBundleContext)
    {
        var evidenceNotes = new List<string>();
        var evidenceScore = 0;
        var basisPrimaryOffset = TryParseHexInt32(candidate.BasisPrimaryForwardOffset);

        if (savedEvidence.Loaded)
        {
            if (savedEvidence.HistoricalBasisPrimaryForwardOffset == basisPrimaryOffset)
            {
                evidenceScore += 45;
                evidenceNotes.Add($"Matches historical primary basis forward offset 0x{basisPrimaryOffset:X}.");
            }
            else if (savedEvidence.HistoricalBasisDuplicateForwardOffset == basisPrimaryOffset)
            {
                evidenceScore += 30;
                evidenceNotes.Add($"Matches historical duplicate basis forward offset 0x{basisPrimaryOffset:X}.");
            }
            else if (basisPrimaryOffset.HasValue)
            {
                evidenceNotes.Add($"Diverges from historical local basis offsets (current 0x{basisPrimaryOffset:X}).");
            }
        }

        ApplyLiveCoordAnchorEvidence(
            candidate.ParentAddress,
            candidate.RootAddress,
            candidate.RootSource,
            candidate.HopDepth,
            coordAnchorResult,
            evidenceNotes,
            ref evidenceScore);

        if (candidate.HopDepth > 1)
        {
            evidenceNotes.Add("Recovered through second-hop child traversal.");
        }
        var previousEvidence = BuildPreviousBundleEvidence(
            candidate.DiscoveryMode,
            candidate.ParentFamilyId,
            candidate.Address,
            candidate.RootAddress,
            candidate.RootSource,
            candidate.HopDepth,
            candidate.BasisPrimaryForwardOffset,
            previousBundleContext,
            evidenceNotes,
            ref evidenceScore);

        return new PostUpdateTriageYawCandidate(
            Kind: candidate.DiscoveryMode,
            FamilyId: candidate.ParentFamilyId,
            Address: candidate.Address,
            ParentAddress: candidate.ParentAddress,
            ReaderScore: candidate.Score,
            EvidenceScore: evidenceScore,
            TotalScore: candidate.Score + evidenceScore,
            BasisPrimaryForwardOffset: candidate.BasisPrimaryForwardOffset,
            BasisDuplicateForwardOffset: null,
            CoordPrimaryOffset: null,
            CoordDuplicateOffset: null,
            YawDegrees: candidate.PreferredEstimate.YawDegrees,
            PitchDegrees: candidate.PreferredEstimate.PitchDegrees,
            BasisIsOrthonormal: candidate.Basis.IsOrthonormal,
            Determinant: candidate.Basis.Determinant,
            DuplicateMaxRowDeltaMagnitude: null,
            RootAddress: candidate.RootAddress,
            RootSource: candidate.RootSource,
            HopDepth: candidate.HopDepth,
            PointerOffset: candidate.PointerOffset,
            SeenInPreviousBundle: previousEvidence.Seen,
            PreviousMatchKind: previousEvidence.MatchKind,
            PreviousRank: previousEvidence.PreviousRank,
            EvidenceNotes: evidenceNotes);
    }

    private static void ApplyLiveCoordAnchorEvidence(
        string? parentAddress,
        string? rootAddress,
        string? rootSource,
        int hopDepth,
        PlayerCoordAnchorReadResult? coordAnchorResult,
        List<string> evidenceNotes,
        ref int evidenceScore)
    {
        var liveSourceObject = NormalizeHexAddress(coordAnchorResult?.SourceObjectAddress);
        var liveObjectBase = NormalizeHexAddress(coordAnchorResult?.ObjectBaseAddress);
        var normalizedParent = NormalizeHexAddress(parentAddress);
        var normalizedRoot = NormalizeHexAddress(rootAddress);

        if (!string.IsNullOrWhiteSpace(rootSource))
        {
            if (string.Equals(rootSource, "coord-anchor-source-object", StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 80;
                evidenceNotes.Add("Recovered from the live coord-anchor source-object seed.");
            }
            else if (string.Equals(rootSource, "coord-anchor-object-base", StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 45;
                evidenceNotes.Add("Recovered from the live coord-anchor object-base seed.");
            }
            else if (string.Equals(rootSource, "coord-anchor-candidate-address", StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 20;
                evidenceNotes.Add("Recovered from the live coord-anchor candidate-address seed.");
            }
        }

        if (liveSourceObject is not null)
        {
            if (string.Equals(normalizedRoot, liveSourceObject, StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 120;
                evidenceNotes.Add("Root lineage matches the live coord-anchor source object.");
            }
            else if (string.Equals(normalizedParent, liveSourceObject, StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 100;
                evidenceNotes.Add("Immediate parent matches the live coord-anchor source object.");
            }
        }

        if (liveObjectBase is not null)
        {
            if (string.Equals(normalizedRoot, liveObjectBase, StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 70;
                evidenceNotes.Add("Root lineage matches the live coord-anchor object base.");
            }
            else if (string.Equals(normalizedParent, liveObjectBase, StringComparison.OrdinalIgnoreCase))
            {
                evidenceScore += 55;
                evidenceNotes.Add("Immediate parent matches the live coord-anchor object base.");
            }
        }

        if (hopDepth > 1)
        {
            evidenceScore -= 10;
        }
    }

    private static PreviousBundleMatchEvidence BuildPreviousBundleEvidence(
        string kind,
        string? familyId,
        string? address,
        string? rootAddress,
        string? rootSource,
        int hopDepth,
        string? basisPrimaryForwardOffset,
        PreviousBundleContext previousBundleContext,
        List<string> evidenceNotes,
        ref int evidenceScore)
    {
        if (!previousBundleContext.Evidence.Loaded || previousBundleContext.Candidates.Count == 0)
        {
            return PreviousBundleMatchEvidence.None;
        }

        var normalizedAddress = NormalizeHexAddress(address);
        var normalizedRootAddress = NormalizeHexAddress(rootAddress);
        var normalizedBasisOffset = NormalizeHexOffset(basisPrimaryForwardOffset);

        var exactMatch = previousBundleContext.Candidates.FirstOrDefault(candidate =>
            string.Equals(candidate.Kind, kind, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.Address, normalizedAddress, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.BasisPrimaryForwardOffset, normalizedBasisOffset, StringComparison.OrdinalIgnoreCase) &&
            candidate.HopDepth == hopDepth);

        if (exactMatch is not null)
        {
            evidenceScore += 110;
            evidenceNotes.Add("Exact candidate address persisted from the prior triage bundle.");
            if (exactMatch.Rank == 0)
            {
                evidenceScore += 15;
                evidenceNotes.Add("It was also the top-ranked candidate in the prior triage bundle.");
            }

            return new PreviousBundleMatchEvidence(true, "exact-address", exactMatch.Rank);
        }

        var rootMatch = previousBundleContext.Candidates.FirstOrDefault(candidate =>
            string.Equals(candidate.Kind, kind, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.RootAddress, normalizedRootAddress, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.RootSource, rootSource, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.BasisPrimaryForwardOffset, normalizedBasisOffset, StringComparison.OrdinalIgnoreCase) &&
            candidate.HopDepth == hopDepth);

        if (rootMatch is not null)
        {
            evidenceScore += 65;
            evidenceNotes.Add("A matching root-lineage candidate persisted from the prior triage bundle.");
            return new PreviousBundleMatchEvidence(true, "root-lineage", rootMatch.Rank);
        }

        var familyMatch = previousBundleContext.Candidates.FirstOrDefault(candidate =>
            !string.IsNullOrWhiteSpace(familyId) &&
            string.Equals(candidate.Kind, kind, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.FamilyId, familyId, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(candidate.BasisPrimaryForwardOffset, normalizedBasisOffset, StringComparison.OrdinalIgnoreCase));

        if (familyMatch is not null)
        {
            evidenceScore += 35;
            evidenceNotes.Add("A matching family/offset candidate was present in the prior triage bundle.");
            return new PreviousBundleMatchEvidence(true, "family-offset", familyMatch.Rank);
        }

        return PreviousBundleMatchEvidence.None;
    }

    private static string? NormalizeHexAddress(string? address)
    {
        var parsed = TryParseHexInt64(address);
        return parsed.HasValue ? $"0x{parsed.Value:X}" : null;
    }

    private static PostUpdateTriageSurvivingAnchors BuildSurvivingAnchors(
        PostUpdateTriageSnapshotSummary snapshot,
        PostUpdateTriageStep<PlayerCurrentReadResult> playerCurrentValidation,
        PostUpdateTriageStep<PlayerCoordAnchorReadResult> coordAnchorValidation)
    {
        var playerCurrentUsable =
            playerCurrentValidation.Result?.Match.CoordMatchesWithinTolerance == true &&
            playerCurrentValidation.Result?.Match.LevelMatches == true &&
            (playerCurrentValidation.Result.Expected.Health.HasValue is false ||
             playerCurrentValidation.Result.Match.HealthMatches);

        return new PostUpdateTriageSurvivingAnchors(
            PlayerCurrentUsable: playerCurrentUsable,
            PlayerCurrentFamilyId: playerCurrentValidation.Result?.FamilyId,
            CoordAnchorTraceMatchesProcess: coordAnchorValidation.Result?.TraceMatchesProcess == true,
            CoordAnchorPatternMatched: coordAnchorValidation.Result?.ModulePattern?.Found == true,
            CoordAnchorMemoryMatched: coordAnchorValidation.Result?.Match?.CoordMatchesWithinTolerance == true,
            CoordAnchorSourceObjectMatched: coordAnchorValidation.Result?.SourceObjectMatch?.CoordMatchesWithinTolerance == true,
            AddonOrientationProbePresent: snapshot.OrientationProbePresent);
    }

    private static IReadOnlyList<string> BuildNotes(
        PostUpdateTriageSnapshotSummary snapshot,
        PostUpdateTriageSurvivingAnchors anchors,
        PlayerSignatureScanResult? structureFamilyScan,
        PlayerOrientationCandidateSearchResult? coordNeighborhoodProbe,
        IReadOnlyList<PostUpdateTriageYawCandidate> rankedYawCandidates,
        IReadOnlyList<PlayerOrientationProbeSeed> probeSeeds,
        PostUpdateTriagePreviousBundleEvidence previousBundleEvidence)
    {
        var notes = new List<string>();

        if (anchors.PlayerCurrentUsable)
        {
            notes.Add("Player-current survived this pass and still matches the ReaderBridge snapshot.");
        }

        if (anchors.CoordAnchorPatternMatched)
        {
            notes.Add("The coord-anchor module pattern still matched in the live module.");
        }

        if (!snapshot.OrientationProbePresent)
        {
            notes.Add("The addon-side orientation probe is still absent or empty in the latest ReaderBridge snapshot.");
        }

        if ((structureFamilyScan?.FamilyCount ?? 0) > 0)
        {
            notes.Add($"The live player-signature scan clustered {structureFamilyScan!.FamilyCount} likely structure families.");
        }

        if (probeSeeds.Count > 0)
        {
            notes.Add($"The reader seeded yaw probing from {probeSeeds.Count} live coord-anchor-derived root(s).");
        }

        if (coordNeighborhoodProbe?.Diagnostics.SecondHopRootCount > 0)
        {
            notes.Add($"Pointer-hop probing expanded to second-hop traversal across {coordNeighborhoodProbe.Diagnostics.SecondHopRootCount} queued child roots.");
        }

        if (previousBundleEvidence.Loaded)
        {
            notes.Add($"Previous triage bundle comparison loaded {previousBundleEvidence.RankedYawCandidateCount} prior candidate(s); stable current candidates: {previousBundleEvidence.StableCandidateCount}.");
        }

        if ((coordNeighborhoodProbe?.CandidateCount ?? 0) == 0 && (coordNeighborhoodProbe?.PointerHopCandidateCount ?? 0) == 0)
        {
            notes.Add("No live local-layout or pointer-hop yaw candidate survived the current read-only triage pass.");
        }
        else if (rankedYawCandidates.Count > 0)
        {
            notes.Add($"Best ranked yaw candidate: {rankedYawCandidates[0].Address} ({rankedYawCandidates[0].Kind}).");
        }

        return notes;
    }

    private static IReadOnlyList<PostUpdateTriageSuggestedWatchRegion> BuildSuggestedWatchRegions(
        IReadOnlyList<PostUpdateTriageYawCandidate> rankedYawCandidates)
    {
        var regions = new List<PostUpdateTriageSuggestedWatchRegion>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        for (var index = 0; index < Math.Min(4, rankedYawCandidates.Count); index++)
        {
            var candidate = rankedYawCandidates[index];
            var candidateTag = $"candidate-{index + 1}";

            var candidateAddress = TryParseHexInt64(candidate.Address);
            var basisOffset = TryParseHexInt32(candidate.BasisPrimaryForwardOffset);
            if (candidateAddress.HasValue && basisOffset.HasValue)
            {
                AddWatchRegion(
                    regions,
                    seen,
                    $"{candidateTag}-basis",
                    $"0x{candidateAddress.Value + basisOffset.Value:X}",
                    0x24,
                    "Sample forward/up/right basis rows for the ranked yaw candidate.",
                    candidate.Address,
                    candidate.Kind,
                    candidate.SeenInPreviousBundle);
            }

            if (candidateAddress.HasValue)
            {
                AddWatchRegion(
                    regions,
                    seen,
                    $"{candidateTag}-object",
                    $"0x{candidateAddress.Value:X}",
                    0x100,
                    "Sample the candidate object body for before/after comparisons.",
                    candidate.Address,
                    candidate.Kind,
                    candidate.SeenInPreviousBundle);
            }

            var rootAddress = NormalizeHexAddress(candidate.RootAddress);
            if (!string.IsNullOrWhiteSpace(rootAddress))
            {
                AddWatchRegion(
                    regions,
                    seen,
                    $"{candidateTag}-root",
                    rootAddress,
                    0x80,
                    "Sample the candidate root lineage object used during triage discovery.",
                    candidate.Address,
                    candidate.Kind,
                    candidate.SeenInPreviousBundle);
            }
        }

        return regions;
    }

    private static IReadOnlyList<PostUpdateTriageLineageSummary> BuildLineageSummaries(
        IReadOnlyList<PostUpdateTriageYawCandidate> rankedYawCandidates)
    {
        var summaries = new List<PostUpdateTriageLineageSummary>();

        for (var index = 0; index < Math.Min(4, rankedYawCandidates.Count); index++)
        {
            var candidate = rankedYawCandidates[index];
            var normalizedCandidateAddress = NormalizeHexAddress(candidate.Address) ?? candidate.Address;
            var normalizedParentAddress = NormalizeHexAddress(candidate.ParentAddress);
            var normalizedRootAddress = NormalizeHexAddress(candidate.RootAddress);

            var pathSegments = new List<string>();
            if (!string.IsNullOrWhiteSpace(normalizedRootAddress))
            {
                pathSegments.Add(normalizedRootAddress);
            }

            if (!string.IsNullOrWhiteSpace(normalizedParentAddress) &&
                !string.Equals(normalizedParentAddress, normalizedRootAddress, StringComparison.OrdinalIgnoreCase))
            {
                pathSegments.Add(normalizedParentAddress);
            }

            if (!string.IsNullOrWhiteSpace(normalizedCandidateAddress) &&
                !string.Equals(normalizedCandidateAddress, normalizedParentAddress, StringComparison.OrdinalIgnoreCase))
            {
                pathSegments.Add(normalizedCandidateAddress);
            }

            var summaryParts = new List<string>
            {
                $"{candidate.Kind}: {string.Join(" -> ", pathSegments.Where(static value => !string.IsNullOrWhiteSpace(value)))}"
            };

            if (!string.IsNullOrWhiteSpace(candidate.BasisPrimaryForwardOffset))
            {
                summaryParts.Add($"basis {candidate.BasisPrimaryForwardOffset}");
            }

            if (!string.IsNullOrWhiteSpace(candidate.RootSource))
            {
                summaryParts.Add($"root-source {candidate.RootSource}");
            }

            if (candidate.HopDepth > 0)
            {
                summaryParts.Add($"hop {candidate.HopDepth}");
            }

            if (!string.IsNullOrWhiteSpace(candidate.PointerOffset))
            {
                summaryParts.Add($"ptr {candidate.PointerOffset}");
            }

            if (candidate.SeenInPreviousBundle)
            {
                summaryParts.Add(candidate.PreviousRank.HasValue
                    ? $"stable ({candidate.PreviousMatchKind ?? "match"}, prev rank {candidate.PreviousRank.Value})"
                    : $"stable ({candidate.PreviousMatchKind ?? "match"})");
            }

            summaries.Add(new PostUpdateTriageLineageSummary(
                Rank: index + 1,
                CandidateAddress: normalizedCandidateAddress,
                Kind: candidate.Kind,
                RootAddress: normalizedRootAddress,
                ParentAddress: normalizedParentAddress,
                RootSource: candidate.RootSource,
                HopDepth: candidate.HopDepth,
                PointerOffset: candidate.PointerOffset,
                BasisPrimaryForwardOffset: candidate.BasisPrimaryForwardOffset,
                StableAcrossBundles: candidate.SeenInPreviousBundle,
                PreviousMatchKind: candidate.PreviousMatchKind,
                PreviousRank: candidate.PreviousRank,
                TotalScore: candidate.TotalScore,
                Summary: string.Join(" | ", summaryParts)));
        }

        return summaries;
    }

    private static void AddWatchRegion(
        List<PostUpdateTriageSuggestedWatchRegion> regions,
        HashSet<string> seen,
        string name,
        string address,
        int length,
        string purpose,
        string candidateAddress,
        string kind,
        bool stableAcrossBundles)
    {
        var key = $"{address}:{length}";
        if (!seen.Add(key))
        {
            return;
        }

        regions.Add(new PostUpdateTriageSuggestedWatchRegion(
            Name: name,
            Address: address,
            Length: length,
            Purpose: purpose,
            CandidateAddress: candidateAddress,
            Kind: kind,
            StableAcrossBundles: stableAcrossBundles));
    }

    private static PostUpdateTriageStep<T> TryRun<T>(Func<T> action)
    {
        try
        {
            return new PostUpdateTriageStep<T>(true, null, action());
        }
        catch (Exception ex)
        {
            return new PostUpdateTriageStep<T>(false, ex.Message, default);
        }
    }

    private static int? TryParseHexInt32(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? value[2..]
            : value;

        return int.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static long? TryParseHexInt64(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? value[2..]
            : value;

        return long.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }
}

public sealed record PostUpdateTriageBundle(
    string Mode,
    string GeneratedAtUtc,
    string? OutputFile,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    PostUpdateTriageSnapshotSummary Snapshot,
    PostUpdateTriageSurvivingAnchors SurvivingAnchors,
    PostUpdateTriageStep<PlayerCurrentReadResult> PlayerCurrentValidation,
    PostUpdateTriageStep<PlayerCoordAnchorReadResult> CoordAnchorValidation,
    PostUpdateTriageStep<PlayerSignatureScanResult> StructureFamilyScan,
    PostUpdateTriageStep<PlayerOrientationCandidateSearchResult> CoordNeighborhoodProbe,
    PostUpdateTriageSavedSessionEvidence SavedSessionEvidence,
    PostUpdateTriagePreviousBundleEvidence PreviousBundleEvidence,
    IReadOnlyList<PostUpdateTriageFamilyClusterSummary> StructureFamilies,
    IReadOnlyList<PostUpdateTriageYawCandidate> RankedYawCandidates,
    IReadOnlyList<PostUpdateTriageSuggestedWatchRegion> SuggestedWatchRegions,
    IReadOnlyList<PostUpdateTriageLineageSummary> LineageSummaries,
    IReadOnlyList<string> Notes);

public sealed record PostUpdateTriageStep<T>(
    bool Succeeded,
    string? Error,
    T? Result);

public sealed record PostUpdateTriageSnapshotSummary(
    string SourceFile,
    string LoadedAtUtc,
    int? SchemaVersion,
    string? Status,
    int? ExportCount,
    string? PlayerName,
    int? PlayerLevel,
    string? PlayerLocation,
    ValidatorCoordinateSnapshot? PlayerCoord,
    bool OrientationProbePresent,
    bool PlayerOrientationProbeHasSignals,
    bool TargetOrientationProbeHasSignals,
    int StatOrientationCandidateCount);

public sealed record PostUpdateTriageSurvivingAnchors(
    bool PlayerCurrentUsable,
    string? PlayerCurrentFamilyId,
    bool CoordAnchorTraceMatchesProcess,
    bool CoordAnchorPatternMatched,
    bool CoordAnchorMemoryMatched,
    bool CoordAnchorSourceObjectMatched,
    bool AddonOrientationProbePresent);

public sealed record PostUpdateTriageSavedSessionEvidence(
    string? SourceFile,
    bool Loaded,
    string? Error,
    string? PreferredSourceAddress,
    int? HistoricalCoordPrimaryOffset,
    int? HistoricalCoordDuplicateOffset,
    int? HistoricalBasisPrimaryForwardOffset,
    int? HistoricalBasisDuplicateForwardOffset,
    int? HistoricalBasisDuplicateSeparation,
    int RequiredRegionCount,
    IReadOnlyList<string> Notes);

public sealed record PostUpdateTriagePreviousBundleEvidence(
    string? SourceFile,
    bool Loaded,
    string? Error,
    string? GeneratedAtUtc,
    int RankedYawCandidateCount,
    int StructureFamilyCount,
    int StableCandidateCount,
    IReadOnlyList<string> Notes);

public sealed record PostUpdateTriageFamilyClusterSummary(
    string FamilyId,
    string Signature,
    int HitCount,
    int BestScore,
    string Notes,
    string RepresentativeAddressHex,
    int SampleAddressCount,
    int LocalLayoutCandidateCount,
    int PointerHopCandidateCount,
    string? BestLocalCandidateAddress,
    string? BestPointerHopCandidateAddress,
    bool SeenInPreviousBundle,
    int StabilityScore,
    int? PreviousPointerHopCandidateCount,
    int? PreviousLocalLayoutCandidateCount);

public sealed record PostUpdateTriageYawCandidate(
    string Kind,
    string? FamilyId,
    string Address,
    string? ParentAddress,
    int ReaderScore,
    int EvidenceScore,
    int TotalScore,
    string? BasisPrimaryForwardOffset,
    string? BasisDuplicateForwardOffset,
    string? CoordPrimaryOffset,
    string? CoordDuplicateOffset,
    double? YawDegrees,
    double? PitchDegrees,
    bool BasisIsOrthonormal,
    double? Determinant,
    double? DuplicateMaxRowDeltaMagnitude,
    string? RootAddress,
    string? RootSource,
    int HopDepth,
    string? PointerOffset,
    bool SeenInPreviousBundle,
    string? PreviousMatchKind,
    int? PreviousRank,
    IReadOnlyList<string> EvidenceNotes);

public sealed record PostUpdateTriageSuggestedWatchRegion(
    string Name,
    string Address,
    int Length,
    string Purpose,
    string CandidateAddress,
    string Kind,
    bool StableAcrossBundles);

public sealed record PostUpdateTriageLineageSummary(
    int Rank,
    string CandidateAddress,
    string Kind,
    string? RootAddress,
    string? ParentAddress,
    string? RootSource,
    int HopDepth,
    string? PointerOffset,
    string? BasisPrimaryForwardOffset,
    bool StableAcrossBundles,
    string? PreviousMatchKind,
    int? PreviousRank,
    int TotalScore,
    string Summary);

internal sealed record PreviousBundleMatchEvidence(
    bool Seen,
    string? MatchKind,
    int? PreviousRank)
{
    public static PreviousBundleMatchEvidence None { get; } = new(false, null, null);
}

internal sealed record PreviousYawCandidateFingerprint(
    int Rank,
    string? Kind,
    string? FamilyId,
    string? Address,
    string? ParentAddress,
    string? RootAddress,
    string? RootSource,
    int HopDepth,
    string? BasisPrimaryForwardOffset);

internal sealed record PreviousFamilyFingerprint(
    string FamilyId,
    int PointerHopCandidateCount,
    int LocalLayoutCandidateCount,
    string? BestPointerHopCandidateAddress,
    string? BestLocalCandidateAddress);

internal sealed record PreviousBundleContext(
    PostUpdateTriagePreviousBundleEvidence Evidence,
    IReadOnlyList<PreviousYawCandidateFingerprint> Candidates,
    IReadOnlyDictionary<string, PreviousFamilyFingerprint> FamiliesById)
{
    public static PreviousBundleContext CreateEmpty(string error, string? sourceFile = null) =>
        new(
            new PostUpdateTriagePreviousBundleEvidence(
                SourceFile: sourceFile,
                Loaded: false,
                Error: error,
                GeneratedAtUtc: null,
                RankedYawCandidateCount: 0,
                StructureFamilyCount: 0,
                StableCandidateCount: 0,
                Notes: Array.Empty<string>()),
            Array.Empty<PreviousYawCandidateFingerprint>(),
            new Dictionary<string, PreviousFamilyFingerprint>(StringComparer.OrdinalIgnoreCase));
}
