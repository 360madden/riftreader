using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Models;

public static class PlayerActorCoordReader
{
    public static PlayerActorCoordReadResult ReadCurrent(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        int inspectionRadius,
        int maxHits,
        PlayerCoordAnchorReadResult? anchorResult)
    {
        ArgumentNullException.ThrowIfNull(reader);

        if (CanUseAnchor(anchorResult, snapshotDocument))
        {
            return BuildFromAnchor(anchorResult!, snapshotDocument);
        }

        if (snapshotDocument?.Current?.Player is null)
        {
            throw new InvalidOperationException("ReaderBridge export did not contain a player snapshot, and no current-process coord trace could provide a live actor-coordinate sample.");
        }

        var currentResult = PlayerCurrentReader.ReadCurrent(
            reader,
            processId,
            processName,
            snapshotDocument,
            inspectionRadius,
            maxHits);

        return BuildFromCurrent(currentResult, anchorResult);
    }

    private static bool CanUseAnchor(PlayerCoordAnchorReadResult? anchorResult, ReaderBridgeSnapshotDocument? snapshotDocument)
    {
        if (anchorResult is null || !anchorResult.TraceMatchesProcess)
        {
            return false;
        }

        var requireSnapshotMatch = HasExpectedCoord(snapshotDocument);
        var sourceObjectUsable =
            anchorResult.SourceObjectSample is not null &&
            (!requireSnapshotMatch || anchorResult.SourceObjectMatch?.CoordMatchesWithinTolerance == true);
        var anchorUsable =
            anchorResult.MemorySample is not null &&
            (!requireSnapshotMatch || anchorResult.Match?.CoordMatchesWithinTolerance == true);

        return sourceObjectUsable || anchorUsable;
    }

    private static PlayerActorCoordReadResult BuildFromAnchor(
        PlayerCoordAnchorReadResult anchorResult,
        ReaderBridgeSnapshotDocument? snapshotDocument)
    {
        ArgumentNullException.ThrowIfNull(anchorResult);

        var requireSnapshotMatch = HasExpectedCoord(snapshotDocument);
        var preferSourceObject =
            anchorResult.SourceObjectSample is not null &&
            (!requireSnapshotMatch || anchorResult.SourceObjectMatch?.CoordMatchesWithinTolerance == true);
        var useSourceObject = preferSourceObject ||
            (anchorResult.MemorySample is null && anchorResult.SourceObjectSample is not null);

        var memory = useSourceObject
            ? new PlayerCurrentReadSample(
                AddressHex: anchorResult.SourceObjectSample!.AddressHex,
                Level: null,
                Health: null,
                Name: null,
                Location: null,
                CoordX: anchorResult.SourceObjectSample.CoordX,
                CoordY: anchorResult.SourceObjectSample.CoordY,
                CoordZ: anchorResult.SourceObjectSample.CoordZ)
            : anchorResult.MemorySample
              ?? throw new InvalidOperationException("The current coord trace did not expose a readable actor-coordinate sample.");

        var expected = BuildExpected(snapshotDocument, memory);
        var match = useSourceObject
            ? BuildSourceObjectMatch(anchorResult, snapshotDocument, expected, memory)
            : BuildAnchorMatch(anchorResult, snapshotDocument, expected, memory);

        var coordBaseOffset = useSourceObject ? anchorResult.SourceCoordRelativeOffset : anchorResult.InferredCoordBaseRelativeOffset;
        var coordXOffset = coordBaseOffset;
        var coordYOffset = coordBaseOffset.HasValue ? (int?)(coordBaseOffset.Value + sizeof(float)) : null;
        var coordZOffset = coordBaseOffset.HasValue ? (int?)(coordBaseOffset.Value + (sizeof(float) * 2)) : null;

        return new PlayerActorCoordReadResult(
            Mode: "player-actor-coords",
            ProcessId: anchorResult.ProcessId,
            ProcessName: anchorResult.ProcessName,
            ReaderBridgeSourceFile: snapshotDocument?.SourceFile ?? anchorResult.ReaderBridgeSourceFile ?? string.Empty,
            TraceSourceFile: anchorResult.SourceFile,
            TraceAvailable: true,
            TraceMatchesProcess: true,
            ResolutionSource: useSourceObject ? "coord-trace-source-object" : "coord-trace-anchor",
            AnchorProvenance: useSourceObject ? "coord-trace-source-object" : "coord-trace-anchor",
            FamilyId: useSourceObject ? "coord-trace-source-object" : "coord-trace-anchor",
            FamilyNotes: useSourceObject ? "code-path-backed source-object actor coords" : "code-path-backed actor coordinate anchor",
            Signature: coordBaseOffset.HasValue
                ? $"trace-{(useSourceObject ? "source-object" : "object-base")}@{(useSourceObject ? anchorResult.SourceObjectRegister : anchorResult.BaseRegister)}+coord@0x{coordBaseOffset.Value:X}"
                : (useSourceObject ? "trace-source-object" : "trace-object-base"),
            SelectionSource: useSourceObject ? "coord-trace-source-object" : "coord-trace-anchor",
            ConfirmationFile: anchorResult.SourceFile,
            CeConfirmedSampleCount: 0,
            BaseRegister: useSourceObject ? anchorResult.SourceObjectRegister : anchorResult.BaseRegister,
            BaseRegisterValue: useSourceObject ? anchorResult.SourceObjectRegisterValue : anchorResult.BaseRegisterValue,
            ObjectBaseAddress: useSourceObject ? anchorResult.SourceObjectAddress : anchorResult.ObjectBaseAddress,
            CoordBaseRelativeOffset: coordBaseOffset,
            CoordXRelativeOffset: coordXOffset,
            CoordYRelativeOffset: coordYOffset,
            CoordZRelativeOffset: coordZOffset,
            LevelRelativeOffset: useSourceObject ? null : anchorResult.LevelRelativeOffset,
            HealthRelativeOffset: useSourceObject ? null : anchorResult.HealthRelativeOffset,
            ModuleName: anchorResult.ModuleName,
            ModuleOffset: anchorResult.ModulePattern?.RelativeOffsetHex ?? anchorResult.ModuleOffset,
            InstructionSymbol: anchorResult.InstructionSymbol,
            Instruction: anchorResult.Instruction,
            Pattern: anchorResult.Pattern,
            Memory: memory,
            Expected: expected,
            Match: match,
            ModulePattern: anchorResult.ModulePattern,
            BestContainerChain: null,
            BestRootFamily: null,
            RootFamilySummary: null,
            Notes: Array.Empty<string>());
    }

    private static bool HasExpectedCoord(ReaderBridgeSnapshotDocument? snapshotDocument) =>
        snapshotDocument?.Current?.Player?.Coord is { X: not null, Y: not null, Z: not null };

    private static PlayerCurrentReadExpected BuildExpected(
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCurrentReadSample memory)
    {
        var player = snapshotDocument?.Current?.Player;
        return new PlayerCurrentReadExpected(
            Name: player?.Name ?? memory.Name,
            Location: player?.LocationName ?? memory.Location,
            Level: player?.Level ?? memory.Level,
            Health: player?.Hp ?? memory.Health,
            HealthMax: player?.HpMax,
            CoordX: player?.Coord?.X ?? memory.CoordX,
            CoordY: player?.Coord?.Y ?? memory.CoordY,
            CoordZ: player?.Coord?.Z ?? memory.CoordZ);
    }

    private static PlayerCurrentReadMatch BuildSourceObjectMatch(
        PlayerCoordAnchorReadResult anchorResult,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCurrentReadExpected expected,
        PlayerCurrentReadSample memory)
    {
        if (HasExpectedCoord(snapshotDocument) && anchorResult.SourceObjectMatch is not null)
        {
            return new PlayerCurrentReadMatch(
                LevelMatches: !expected.Level.HasValue || !memory.Level.HasValue || expected.Level.Value == memory.Level.Value,
                HealthMatches: !expected.Health.HasValue || !memory.Health.HasValue || expected.Health.Value == memory.Health.Value,
                CoordMatchesWithinTolerance: anchorResult.SourceObjectMatch.CoordMatchesWithinTolerance,
                DeltaX: anchorResult.SourceObjectMatch.DeltaX,
                DeltaY: anchorResult.SourceObjectMatch.DeltaY,
                DeltaZ: anchorResult.SourceObjectMatch.DeltaZ);
        }

        return new PlayerCurrentReadMatch(
            LevelMatches: !expected.Level.HasValue || !memory.Level.HasValue || expected.Level.Value == memory.Level.Value,
            HealthMatches: !expected.Health.HasValue || !memory.Health.HasValue || expected.Health.Value == memory.Health.Value,
            CoordMatchesWithinTolerance: true,
            DeltaX: 0f,
            DeltaY: 0f,
            DeltaZ: 0f);
    }

    private static PlayerCurrentReadMatch BuildAnchorMatch(
        PlayerCoordAnchorReadResult anchorResult,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCurrentReadExpected expected,
        PlayerCurrentReadSample memory)
    {
        if (HasExpectedCoord(snapshotDocument) && anchorResult.Match is not null)
        {
            return anchorResult.Match;
        }

        return new PlayerCurrentReadMatch(
            LevelMatches: !expected.Level.HasValue || !memory.Level.HasValue || expected.Level.Value == memory.Level.Value,
            HealthMatches: !expected.Health.HasValue || !memory.Health.HasValue || expected.Health.Value == memory.Health.Value,
            CoordMatchesWithinTolerance: true,
            DeltaX: 0f,
            DeltaY: 0f,
            DeltaZ: 0f);
    }

    private static PlayerActorCoordReadResult BuildFromCurrent(
        PlayerCurrentReadResult currentResult,
        PlayerCoordAnchorReadResult? anchorResult)
    {
        ArgumentNullException.ThrowIfNull(currentResult);

        var traceCurrent = anchorResult?.TraceMatchesProcess == true;
        var liveModuleOffset = anchorResult?.ModulePattern?.RelativeOffsetHex;
        var instructionSymbol = traceCurrent
            ? anchorResult?.InstructionSymbol
            : null;
        var instruction = traceCurrent
            ? anchorResult?.Instruction
            : null;

        return new PlayerActorCoordReadResult(
            Mode: "player-actor-coords",
            ProcessId: currentResult.ProcessId,
            ProcessName: currentResult.ProcessName,
            ReaderBridgeSourceFile: currentResult.ReaderBridgeSourceFile,
            TraceSourceFile: anchorResult?.SourceFile,
            TraceAvailable: anchorResult is not null,
            TraceMatchesProcess: traceCurrent,
            ResolutionSource: currentResult.SelectionSource,
            AnchorProvenance: currentResult.AnchorProvenance,
            FamilyId: currentResult.FamilyId,
            FamilyNotes: currentResult.FamilyNotes,
            Signature: currentResult.Signature,
            SelectionSource: currentResult.SelectionSource,
            ConfirmationFile: currentResult.ConfirmationFile,
            CeConfirmedSampleCount: currentResult.CeConfirmedSampleCount,
            BaseRegister: traceCurrent ? anchorResult?.BaseRegister : null,
            BaseRegisterValue: traceCurrent ? anchorResult?.BaseRegisterValue : null,
            ObjectBaseAddress: traceCurrent ? anchorResult?.ObjectBaseAddress : null,
            CoordBaseRelativeOffset: traceCurrent ? anchorResult?.InferredCoordBaseRelativeOffset : null,
            CoordXRelativeOffset: traceCurrent ? anchorResult?.CoordXRelativeOffset : null,
            CoordYRelativeOffset: traceCurrent ? anchorResult?.CoordYRelativeOffset : null,
            CoordZRelativeOffset: traceCurrent ? anchorResult?.CoordZRelativeOffset : null,
            LevelRelativeOffset: traceCurrent ? anchorResult?.LevelRelativeOffset : null,
            HealthRelativeOffset: traceCurrent ? anchorResult?.HealthRelativeOffset : null,
            ModuleName: anchorResult?.ModuleName,
            ModuleOffset: liveModuleOffset,
            InstructionSymbol: instructionSymbol,
            Instruction: instruction,
            Pattern: anchorResult?.Pattern,
            Memory: currentResult.Memory,
            Expected: currentResult.Expected,
            Match: currentResult.Match,
            ModulePattern: anchorResult?.ModulePattern,
            BestContainerChain: null,
            BestRootFamily: null,
            RootFamilySummary: null,
            Notes: Array.Empty<string>());
    }
}
