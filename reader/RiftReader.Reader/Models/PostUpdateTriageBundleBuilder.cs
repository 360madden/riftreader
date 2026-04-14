using System.Diagnostics;
using System.Globalization;
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
                maxHits));

        var savedSessionEvidence = LoadSavedSessionEvidence(options.SessionWatchsetFile);
        var familyAddressIndex = BuildFamilyAddressIndex(structureFamilyScan.Result);
        var structureFamilies = BuildStructureFamilies(structureFamilyScan.Result, coordNeighborhoodProbe.Result);
        var rankedYawCandidates = BuildRankedYawCandidates(coordNeighborhoodProbe.Result, savedSessionEvidence, familyAddressIndex)
            .Take(maxHits)
            .ToArray();
        var survivingAnchors = BuildSurvivingAnchors(snapshotSummary, playerCurrentValidation, coordAnchorValidation);

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
            StructureFamilies: structureFamilies,
            RankedYawCandidates: rankedYawCandidates,
            Notes: BuildNotes(snapshotSummary, survivingAnchors, structureFamilyScan.Result, coordNeighborhoodProbe.Result, rankedYawCandidates));
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
        PlayerOrientationCandidateSearchResult? orientationResult)
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
                    BestLocalCandidateAddress: localMatches.OrderByDescending(static candidate => candidate.Score).FirstOrDefault()?.Address,
                    BestPointerHopCandidateAddress: pointerMatches.OrderByDescending(static candidate => candidate.Score).FirstOrDefault()?.Address);
            })
            .OrderByDescending(static family => family.BestScore)
            .ThenByDescending(static family => family.PointerHopCandidateCount)
            .ThenByDescending(static family => family.LocalLayoutCandidateCount)
            .ToArray();
    }

    private static IReadOnlyList<PostUpdateTriageYawCandidate> BuildRankedYawCandidates(
        PlayerOrientationCandidateSearchResult? orientationResult,
        PostUpdateTriageSavedSessionEvidence savedEvidence,
        IReadOnlyDictionary<string, string> familyAddressIndex)
    {
        var ranked = new List<PostUpdateTriageYawCandidate>();

        foreach (var candidate in orientationResult?.Candidates ?? Array.Empty<PlayerOrientationCandidate>())
        {
            ranked.Add(BuildLocalYawCandidate(candidate, savedEvidence, familyAddressIndex));
        }

        foreach (var candidate in orientationResult?.PointerHopCandidates ?? Array.Empty<PlayerOrientationPointerHopCandidate>())
        {
            ranked.Add(BuildPointerHopYawCandidate(candidate, savedEvidence));
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
        IReadOnlyDictionary<string, string> familyAddressIndex)
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

        return new PostUpdateTriageYawCandidate(
            Kind: "local-layout",
            FamilyId: familyAddressIndex.TryGetValue(candidate.HitAddress, out var familyId) ? familyId : null,
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
            EvidenceNotes: evidenceNotes);
    }

    private static PostUpdateTriageYawCandidate BuildPointerHopYawCandidate(
        PlayerOrientationPointerHopCandidate candidate,
        PostUpdateTriageSavedSessionEvidence savedEvidence)
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
            EvidenceNotes: evidenceNotes);
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
        IReadOnlyList<PostUpdateTriageYawCandidate> rankedYawCandidates)
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
    IReadOnlyList<PostUpdateTriageFamilyClusterSummary> StructureFamilies,
    IReadOnlyList<PostUpdateTriageYawCandidate> RankedYawCandidates,
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
    string? BestPointerHopCandidateAddress);

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
    IReadOnlyList<string> EvidenceNotes);
