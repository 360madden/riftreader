using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public static class TargetCurrentReader
{
    private const int DefaultLevelOffset = -144;
    private const int DefaultHealthOffset = -136;
    private const int DefaultCoordXOffset = 0;
    private const int DefaultCoordYOffset = 4;
    private const int DefaultCoordZOffset = 8;
    private const float CoordTolerance = 0.25f;
    private const float DistanceTolerance = 1.0f;

    public static TargetCurrentReadResult ReadCurrent(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int inspectionRadius,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(snapshotDocument);

        var target = snapshotDocument.Current?.Target;
        if (target is null)
        {
            return BuildNoTargetResult(processId, processName, snapshotDocument);
        }

        var expected = BuildExpected(target);

        var anchorCandidates = TargetCurrentAnchorCacheStore.LoadCandidates(null, out var cacheFile, out _);

        foreach (var anchorCandidate in anchorCandidates)
        {
            var cachedAnchor = anchorCandidate.Document;
            if (!string.Equals(cachedAnchor.ProcessName, processName, StringComparison.OrdinalIgnoreCase) ||
                !string.Equals(cachedAnchor.TargetName, target.Name ?? string.Empty, StringComparison.OrdinalIgnoreCase) ||
                !TargetCurrentAnchorCacheStore.TryParseAddress(cachedAnchor.AddressHex, out var cachedAddress))
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

        var capture = TargetSignatureProbeCaptureBuilder.CaptureBestFamily(
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
            var heuristicCapture = TargetSignatureProbeCaptureBuilder.CaptureBestFamily(
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
            throw new InvalidOperationException($"Unable to resolve a full current-target snapshot from family '{capture.FamilyId}'.");
        }

        if (TargetCurrentAnchorCacheStore.TryParseAddress(result.Memory.AddressHex, out _))
        {
            var updatedCacheFile = TargetCurrentAnchorCacheStore.Save(
                new TargetCurrentAnchorCacheDocument(
                    TargetName: target.Name ?? "unknown",
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
                    DistanceOffset: 12,
                    SavedAtUtc: DateTimeOffset.UtcNow),
                cacheFile);

            result = result with { AnchorCacheFile = updatedCacheFile };
        }

        return result;
    }

    private static TargetCurrentReadExpected BuildExpected(ReaderBridgeUnitSnapshot target) =>
        new(
            Name: target.Name,
            Level: target.Level,
            Health: target.Hp,
            HealthMax: target.HpMax,
            CoordX: target.Coord?.X,
            CoordY: target.Coord?.Y,
            CoordZ: target.Coord?.Z,
            Distance: target.Distance);

    private static bool IsAcceptableCurrentRead(TargetCurrentReadMatch match, TargetCurrentReadExpected expected)
    {
        if (!match.CoordMatchesWithinTolerance)
        {
            return false;
        }

        if (expected.Level.HasValue && !match.LevelMatches)
        {
            return false;
        }

        if (expected.Health.HasValue && !match.HealthMatches)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(expected.Name) && !match.NameMatches)
        {
            return false;
        }

        if (expected.Distance.HasValue && !match.DistanceMatchesWithinTolerance)
        {
            return false;
        }

        return true;
    }

    private static TargetCurrentReadResult BuildNoTargetResult(int processId, string processName, ReaderBridgeSnapshotDocument snapshotDocument)
    {
        var emptySample = new TargetCurrentReadSample(
            AddressHex: "n/a",
            Level: null,
            Health: null,
            Name: null,
            CoordX: null,
            CoordY: null,
            CoordZ: null,
            Distance: null);

        var emptyExpected = new TargetCurrentReadExpected(
            Name: null,
            Level: null,
            Health: null,
            HealthMax: null,
            CoordX: null,
            CoordY: null,
            CoordZ: null,
            Distance: null);

        var emptyMatch = new TargetCurrentReadMatch(
            NameMatches: false,
            LevelMatches: false,
            HealthMatches: false,
            CoordMatchesWithinTolerance: false,
            DistanceMatchesWithinTolerance: false,
            DeltaX: null,
            DeltaY: null,
            DeltaZ: null,
            DeltaDistance: null);

        return new TargetCurrentReadResult(
            Mode: "target-current-read",
            ProcessId: processId,
            ProcessName: processName,
            ReaderBridgeSourceFile: snapshotDocument.SourceFile,
            FamilyId: "n/a",
            FamilyNotes: "no target selected",
            Signature: "n/a",
            SelectionSource: "none",
            AnchorProvenance: "none",
            AnchorCacheFile: null,
            AnchorCacheUsed: false,
            AnchorCacheUpdated: false,
            ConfirmationFile: null,
            CeConfirmedSampleCount: 0,
            Memory: emptySample,
            Expected: emptyExpected,
            Match: emptyMatch,
            HasTarget: false);
    }

    private static TargetCurrentReadResult BuildResultFromCapture(
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        string? cacheFile,
        TargetSignatureProbeCapture capture,
        TargetCurrentReadExpected expected)
    {
        var captureSample = capture.Samples.FirstOrDefault()
            ?? throw new InvalidOperationException("The selected target-signature family did not produce a readable sample.");

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
            new TargetCurrentReadSample(
                AddressHex: captureSample.AddressHex,
                Level: captureSample.Level,
                Health: captureSample.Health,
                Name: captureSample.Name,
                CoordX: captureSample.CoordX,
                CoordY: captureSample.CoordY,
                CoordZ: captureSample.CoordZ,
                Distance: captureSample.Distance),
            expected);
    }

    private static TargetCurrentReadResult BuildResult(
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
        TargetCurrentReadSample memory,
        TargetCurrentReadExpected expected)
    {
        var nameMatches = !string.IsNullOrWhiteSpace(memory.Name) &&
            !string.IsNullOrWhiteSpace(expected.Name) &&
            string.Equals(memory.Name, expected.Name, StringComparison.OrdinalIgnoreCase);

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

        float? deltaDistance = memory.Distance.HasValue && expected.Distance.HasValue
            ? memory.Distance.Value - (float)expected.Distance.Value
            : null;
        var distanceMatches = deltaDistance.HasValue && MathF.Abs(deltaDistance.Value) <= DistanceTolerance;

        return new TargetCurrentReadResult(
            Mode: "target-current-read",
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
            Match: new TargetCurrentReadMatch(
                NameMatches: nameMatches,
                LevelMatches: levelMatches,
                HealthMatches: healthMatches,
                CoordMatchesWithinTolerance: coordMatches,
                DistanceMatchesWithinTolerance: distanceMatches,
                DeltaX: deltaX,
                DeltaY: deltaY,
                DeltaZ: deltaZ,
                DeltaDistance: deltaDistance),
            HasTarget: true);
    }

    private static TargetCurrentReadSample? ReadSampleAt(
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

        return new TargetCurrentReadSample(
            AddressHex: $"0x{baseAddress:X}",
            Level: level,
            Health: health,
            Name: null,
            CoordX: coordX,
            CoordY: coordY,
            CoordZ: coordZ,
            Distance: null);
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
