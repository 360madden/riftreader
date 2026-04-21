using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public static class PlayerActorOrientationReader
{
    private const string CanonicalForwardOffset = "0xD4";

    public static PlayerActorOrientationReadResult ReadCurrent(
        ReaderBridgeSnapshotDocument snapshotDocument,
        PlayerCoordAnchorReadResult? anchorResult,
        PlayerOrientationCandidateSearchResult searchResult)
    {
        ArgumentNullException.ThrowIfNull(snapshotDocument);
        ArgumentNullException.ThrowIfNull(searchResult);

        var selected = SelectPreferredCandidate(searchResult);
        if (selected is null)
        {
            throw new InvalidOperationException("Unable to identify a live pointer-hop actor-orientation candidate from the current process.");
        }

        var playerCoord = snapshotDocument.Current?.Player?.Coord;
        if (playerCoord?.X is null || playerCoord.Y is null || playerCoord.Z is null)
        {
            throw new InvalidOperationException("The effective ReaderBridge snapshot did not contain complete player coordinates.");
        }

        var notes = new List<string>(searchResult.Notes);
        if (string.Equals(selected.BasisPrimaryForwardOffset, CanonicalForwardOffset, StringComparison.OrdinalIgnoreCase))
        {
            notes.Add("Selected the canonical behavior-backed pointer-hop forward basis at +0xD4.");
        }
        else
        {
            notes.Add($"Canonical +0xD4 pointer-hop basis was unavailable; fell back to {selected.BasisPrimaryForwardOffset}.");
        }

        if (anchorResult?.TraceMatchesProcess == true && !string.IsNullOrWhiteSpace(anchorResult.SourceObjectAddress))
        {
            notes.Add($"Coord bootstrap came from the current-process coord trace source object at {anchorResult.SourceObjectAddress}.");
        }

        return new PlayerActorOrientationReadResult(
            Mode: "player-actor-orientation",
            ProcessId: searchResult.ProcessId,
            ProcessName: searchResult.ProcessName,
            ReaderBridgeSourceFile: snapshotDocument.SourceFile,
            TraceSourceFile: anchorResult?.SourceFile,
            TraceAvailable: anchorResult is not null,
            TraceMatchesProcess: anchorResult?.TraceMatchesProcess == true,
            CoordBootstrapSource: ResolveCoordBootstrapSource(snapshotDocument, anchorResult),
            ResolutionSource: string.Equals(selected.BasisPrimaryForwardOffset, CanonicalForwardOffset, StringComparison.OrdinalIgnoreCase)
                ? "pointer-hop-canonical-d4"
                : "pointer-hop-fallback",
            PlayerName: snapshotDocument.Current?.Player?.Name ?? searchResult.PlayerName,
            PlayerCoord: playerCoord,
            SelectedAddress: selected.Address,
            ParentAddress: selected.ParentAddress,
            ParentFamilyId: selected.ParentFamilyId,
            ParentScore: selected.ParentScore,
            RootAddress: selected.RootAddress,
            RootSource: selected.RootSource,
            HopDepth: selected.HopDepth,
            PointerOffset: selected.PointerOffset,
            BasisPrimaryForwardOffset: selected.BasisPrimaryForwardOffset,
            Score: selected.Score,
            RawScore: selected.RawScore,
            LedgerPenalty: selected.LedgerPenalty,
            LedgerRejectionReason: selected.LedgerRejectionReason,
            LedgerStableNonresponsiveCount: selected.LedgerStableNonresponsiveCount,
            LedgerResponsiveCount: selected.LedgerResponsiveCount,
            LedgerLatestGeneratedAtUtc: selected.LedgerLatestGeneratedAtUtc,
            CoordSourceObjectAddress: anchorResult?.SourceObjectAddress,
            CoordSourceRegister: anchorResult?.SourceObjectRegister,
            CoordSourceRelativeOffset: anchorResult?.SourceCoordRelativeOffset,
            Basis: selected.Basis,
            PreferredEstimate: selected.PreferredEstimate,
            CandidateCount: searchResult.CandidateCount,
            PointerHopCandidateCount: searchResult.PointerHopCandidateCount,
            Diagnostics: searchResult.Diagnostics,
            Notes: notes);
    }

    private static PlayerOrientationPointerHopCandidate? SelectPreferredCandidate(
        PlayerOrientationCandidateSearchResult searchResult)
    {
        var pointerHopCandidates = searchResult.PointerHopCandidates
            .Where(static candidate =>
                candidate.Basis.IsOrthonormal &&
                candidate.PreferredEstimate.YawRadians.HasValue &&
                candidate.PreferredEstimate.PitchRadians.HasValue)
            .ToArray();

        return pointerHopCandidates
            .FirstOrDefault(candidate => string.Equals(candidate.BasisPrimaryForwardOffset, CanonicalForwardOffset, StringComparison.OrdinalIgnoreCase))
            ?? pointerHopCandidates.FirstOrDefault()
            ?? searchResult.BestPointerHopCandidate;
    }

    private static string ResolveCoordBootstrapSource(
        ReaderBridgeSnapshotDocument snapshotDocument,
        PlayerCoordAnchorReadResult? anchorResult)
    {
        if (string.Equals(snapshotDocument.SourceFile, "trace-derived-player-coords", StringComparison.OrdinalIgnoreCase))
        {
            return "trace-derived-player-coords";
        }

        if (anchorResult?.SourceObjectSample is not null)
        {
            return "readerbridge-snapshot+coord-trace-source-object";
        }

        if (anchorResult?.MemorySample is not null)
        {
            return "readerbridge-snapshot+coord-trace-anchor";
        }

        return snapshotDocument.SourceFile;
    }
}
