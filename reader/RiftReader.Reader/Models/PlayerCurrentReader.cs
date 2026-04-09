using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public static class PlayerCurrentReader
{
    private const int DefaultLevelOffset = -144;
    private const int DefaultHealthOffset = -136;
    private const int DefaultCoordXOffset = 0;
    private const int DefaultCoordYOffset = 4;
    private const int DefaultCoordZOffset = 8;
    private const float CoordTolerance = 0.25f;

    public static PlayerCurrentReadResult ReadCurrent(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int inspectionRadius,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(snapshotDocument);

        var player = snapshotDocument.Current?.Player
            ?? throw new InvalidOperationException("ReaderBridge export did not contain a player snapshot.");

        var expected = BuildExpected(player);

        var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(null, out _);
        var traceAnchor =
            traceDocument?.Reader?.ProcessId == processId &&
            string.Equals(traceDocument.Reader.ProcessName, processName, StringComparison.OrdinalIgnoreCase)
                ? PlayerCoordAnchorReader.TryResolveObjectAnchor(traceDocument)
                : null;
        if (traceAnchor is not null)
        {
            var traceSample = ReadSampleAt(
                reader,
                traceAnchor.ObjectBaseAddress,
                traceAnchor.LevelOffset,
                traceAnchor.HealthOffset,
                traceAnchor.CoordXOffset,
                traceAnchor.CoordYOffset,
                traceAnchor.CoordZOffset);

            if (traceSample is not null)
            {
                var traceResult = BuildResult(
                    processId,
                    processName,
                    snapshotDocument,
                    familyId: "coord-trace-anchor",
                    familyNotes: "code-path-backed object anchor",
                    signature: $"trace-object-base@{traceAnchor.BaseRegister}+coord@0x{traceAnchor.CoordBaseRelativeOffset:X}",
                    selectionSource: "coord-trace-anchor",
                    anchorProvenance: traceDocument!.SourceFile ?? "coord-trace-anchor",
                    anchorCacheFile: traceDocument!.SourceFile,
                    anchorCacheUsed: true,
                    anchorCacheUpdated: false,
                    confirmationFile: traceDocument!.SourceFile,
                    ceConfirmedSampleCount: 0,
                    memory: traceSample,
                    expected: expected);

                if (IsAcceptableCurrentRead(traceResult.Match, expected))
                {
                    return traceResult;
                }
            }
        }

        var anchorCandidates = PlayerCurrentAnchorCacheStore.LoadCandidates(null, out var cacheFile, out _);

        foreach (var anchorCandidate in anchorCandidates)
        {
            var cachedAnchor = anchorCandidate.Document;
            if (!string.Equals(cachedAnchor.ProcessName, processName, StringComparison.OrdinalIgnoreCase) ||
                !PlayerCurrentAnchorCacheStore.TryParseAddress(cachedAnchor.AddressHex, out var cachedAddress))
            {
                continue;
            }

            var cachedSample = ReadSampleAt(
                reader,
                cachedAddress,
                cachedAnchor.LevelOffset,
                cachedAnchor.HealthOffset,
                cachedAnchor.CoordXOffset,
                cachedAnchor.CoordYOffset,
                cachedAnchor.CoordZOffset);

            if (cachedSample is null)
            {
                continue;
            }

            var cachedResult = BuildResult(
                processId,
                processName,
                snapshotDocument,
                cachedAnchor.FamilyId,
                cachedAnchor.FamilyNotes,
                cachedAnchor.Signature,
                selectionSource: "cached-anchor",
                anchorProvenance: cachedAnchor.SelectionSource,
                anchorCacheFile: anchorCandidate.Path,
                anchorCacheUsed: true,
                anchorCacheUpdated: false,
                cachedAnchor.ConfirmationFile,
                cachedAnchor.CeConfirmedSampleCount,
                cachedSample,
                expected);

            if (IsAcceptableCurrentRead(cachedResult.Match, expected))
            {
                return cachedResult;
            }
        }

        var capture = PlayerSignatureProbeCaptureBuilder.CaptureBestFamily(
            reader,
            processId,
            processName,
            snapshotDocument,
            inspectionRadius,
            maxHits,
            label: null,
            outputFile: null,
            preferCeConfirmation: true);

        var result = BuildResultFromCapture(processId, processName, snapshotDocument, cacheFile, capture, expected);

        if (!IsAcceptableCurrentRead(result.Match, expected) &&
            capture.SelectionSource.StartsWith("ce-", StringComparison.Ordinal))
        {
            var heuristicCapture = PlayerSignatureProbeCaptureBuilder.CaptureBestFamily(
                reader,
                processId,
                processName,
                snapshotDocument,
                inspectionRadius,
                maxHits,
                label: null,
                outputFile: null,
                preferCeConfirmation: false);

            var heuristicResult = BuildResultFromCapture(processId, processName, snapshotDocument, cacheFile, heuristicCapture, expected);
            if (IsAcceptableCurrentRead(heuristicResult.Match, expected))
            {
                result = heuristicResult with
                {
                    AnchorProvenance = $"{capture.SelectionSource} -> heuristic-fallback",
                    AnchorCacheUpdated = true
                };
                capture = heuristicCapture;
            }
        }

        if (!IsAcceptableCurrentRead(result.Match, expected))
        {
            throw new InvalidOperationException($"Unable to resolve a full current-player snapshot from family '{capture.FamilyId}'.");
        }

        if (PlayerCurrentAnchorCacheStore.TryParseAddress(result.Memory.AddressHex, out _))
        {
            var updatedCacheFile = PlayerCurrentAnchorCacheStore.Save(
                new PlayerCurrentAnchorCacheDocument(
                    ProcessName: processName,
                    AddressHex: result.Memory.AddressHex,
                    FamilyId: result.FamilyId,
                    FamilyNotes: result.FamilyNotes,
                    Signature: result.Signature,
                    SelectionSource: result.AnchorProvenance,
                    ConfirmationFile: result.ConfirmationFile,
                    CeConfirmedSampleCount: result.CeConfirmedSampleCount,
                    LevelOffset: DefaultLevelOffset,
                    HealthOffset: DefaultHealthOffset,
                    CoordXOffset: DefaultCoordXOffset,
                    CoordYOffset: DefaultCoordYOffset,
                    CoordZOffset: DefaultCoordZOffset,
                    SavedAtUtc: DateTimeOffset.UtcNow),
                cacheFile);

            result = result with { AnchorCacheFile = updatedCacheFile };
        }

        return result;
    }

    private static PlayerCurrentReadExpected BuildExpected(ReaderBridgeUnitSnapshot player) =>
        new(
            Name: player.Name,
            Location: player.LocationName,
            Level: player.Level,
            Health: player.Hp,
            HealthMax: player.HpMax,
            CoordX: player.Coord?.X,
            CoordY: player.Coord?.Y,
            CoordZ: player.Coord?.Z);

    private static bool IsAcceptableCurrentRead(PlayerCurrentReadMatch match, PlayerCurrentReadExpected expected)
    {
        if (!match.CoordMatchesWithinTolerance || !match.LevelMatches)
        {
            return false;
        }

        if (expected.Health.HasValue)
        {
            return match.HealthMatches;
        }

        return true;
    }

    private static PlayerCurrentReadResult BuildResultFromCapture(
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        string? cacheFile,
        PlayerSignatureProbeCapture capture,
        PlayerCurrentReadExpected expected)
    {
        var captureSample = capture.Samples.FirstOrDefault()
            ?? throw new InvalidOperationException("The selected player-signature family did not produce a readable sample.");

        return BuildResult(
            processId,
            processName,
            snapshotDocument,
            capture.FamilyId,
            capture.FamilyNotes,
            capture.Signature,
            selectionSource: capture.SelectionSource,
            anchorProvenance: capture.SelectionSource,
            anchorCacheFile: cacheFile,
            anchorCacheUsed: false,
            anchorCacheUpdated: true,
            capture.ConfirmationFile,
            capture.CeConfirmedSampleCount,
            new PlayerCurrentReadSample(
                AddressHex: captureSample.AddressHex,
                Level: captureSample.Level,
                Health: captureSample.Health,
                Name: captureSample.Name,
                Location: captureSample.Location,
                CoordX: captureSample.CoordX,
                CoordY: captureSample.CoordY,
                CoordZ: captureSample.CoordZ),
            expected);
    }

    private static PlayerCurrentReadResult BuildResult(
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        string familyId,
        string familyNotes,
        string signature,
        string selectionSource,
        string anchorProvenance,
        string? anchorCacheFile,
        bool anchorCacheUsed,
        bool anchorCacheUpdated,
        string? confirmationFile,
        int ceConfirmedSampleCount,
        PlayerCurrentReadSample memory,
        PlayerCurrentReadExpected expected)
    {
        var levelMatches = memory.Level.HasValue && expected.Level.HasValue && memory.Level.Value == expected.Level.Value;
        var healthMatches = memory.Health.HasValue && expected.Health.HasValue && memory.Health.Value == expected.Health.Value;

        float? deltaX = memory.CoordX.HasValue && expected.CoordX.HasValue
            ? memory.CoordX.Value - (float)expected.CoordX.Value
            : null;
        float? deltaY = memory.CoordY.HasValue && expected.CoordY.HasValue
            ? memory.CoordY.Value - (float)expected.CoordY.Value
            : null;
        float? deltaZ = memory.CoordZ.HasValue && expected.CoordZ.HasValue
            ? memory.CoordZ.Value - (float)expected.CoordZ.Value
            : null;

        var coordMatches =
            deltaX.HasValue && MathF.Abs(deltaX.Value) <= CoordTolerance &&
            deltaY.HasValue && MathF.Abs(deltaY.Value) <= CoordTolerance &&
            deltaZ.HasValue && MathF.Abs(deltaZ.Value) <= CoordTolerance;

        return new PlayerCurrentReadResult(
            Mode: "player-current-read",
            ProcessId: processId,
            ProcessName: processName,
            ReaderBridgeSourceFile: snapshotDocument.SourceFile,
            FamilyId: familyId,
            FamilyNotes: familyNotes,
            Signature: signature,
            SelectionSource: selectionSource,
            AnchorProvenance: anchorProvenance,
            AnchorCacheFile: anchorCacheFile,
            AnchorCacheUsed: anchorCacheUsed,
            AnchorCacheUpdated: anchorCacheUpdated,
            ConfirmationFile: confirmationFile,
            CeConfirmedSampleCount: ceConfirmedSampleCount,
            Memory: memory,
            Expected: expected,
            Match: new PlayerCurrentReadMatch(
                LevelMatches: levelMatches,
                HealthMatches: healthMatches,
                CoordMatchesWithinTolerance: coordMatches,
                DeltaX: deltaX,
                DeltaY: deltaY,
                DeltaZ: deltaZ));
    }

    private static PlayerCurrentReadSample? ReadSampleAt(
        ProcessMemoryReader reader,
        long baseAddress,
        int levelOffset,
        int healthOffset,
        int coordXOffset,
        int coordYOffset,
        int coordZOffset)
    {
        var level = TryReadInt32(reader, baseAddress + levelOffset);
        var health = TryReadInt32(reader, baseAddress + healthOffset);
        var coordX = TryReadFloat(reader, baseAddress + coordXOffset);
        var coordY = TryReadFloat(reader, baseAddress + coordYOffset);
        var coordZ = TryReadFloat(reader, baseAddress + coordZOffset);

        if (!coordX.HasValue || !coordY.HasValue || !coordZ.HasValue)
        {
            return null;
        }

        return new PlayerCurrentReadSample(
            AddressHex: $"0x{baseAddress:X}",
            Level: level,
            Health: health,
            Name: null,
            Location: null,
            CoordX: coordX,
            CoordY: coordY,
            CoordZ: coordZ);
    }

    private static int? TryReadInt32(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(int), out var bytes, out _) || bytes.Length != sizeof(int))
        {
            return null;
        }

        return BitConverter.ToInt32(bytes, 0);
    }

    private static float? TryReadFloat(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(float), out var bytes, out _) || bytes.Length != sizeof(float))
        {
            return null;
        }

        return BitConverter.ToSingle(bytes, 0);
    }
}
