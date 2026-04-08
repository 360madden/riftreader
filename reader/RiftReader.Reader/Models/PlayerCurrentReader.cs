using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public static class PlayerCurrentReader
{
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

        var capture = PlayerSignatureProbeCaptureBuilder.CaptureBestFamily(
            reader,
            processId,
            processName,
            snapshotDocument,
            inspectionRadius,
            maxHits,
            label: null,
            outputFile: null);

        var sample = capture.Samples.FirstOrDefault()
            ?? throw new InvalidOperationException("The selected player-signature family did not produce a readable sample.");

        var player = snapshotDocument.Current?.Player
            ?? throw new InvalidOperationException("ReaderBridge export did not contain a player snapshot.");

        var expected = new PlayerCurrentReadExpected(
            Name: player.Name,
            Location: player.LocationName,
            Level: player.Level,
            Health: player.Hp,
            HealthMax: player.HpMax,
            CoordX: player.Coord?.X,
            CoordY: player.Coord?.Y,
            CoordZ: player.Coord?.Z);

        var levelMatches = sample.Level.HasValue && expected.Level.HasValue && sample.Level.Value == expected.Level.Value;
        var healthMatches = sample.Health.HasValue && expected.Health.HasValue && sample.Health.Value == expected.Health.Value;

        float? deltaX = sample.CoordX.HasValue && expected.CoordX.HasValue
            ? sample.CoordX.Value - (float)expected.CoordX.Value
            : null;
        float? deltaY = sample.CoordY.HasValue && expected.CoordY.HasValue
            ? sample.CoordY.Value - (float)expected.CoordY.Value
            : null;
        float? deltaZ = sample.CoordZ.HasValue && expected.CoordZ.HasValue
            ? sample.CoordZ.Value - (float)expected.CoordZ.Value
            : null;

        var coordMatches =
            deltaX.HasValue && MathF.Abs(deltaX.Value) <= 0.25f &&
            deltaY.HasValue && MathF.Abs(deltaY.Value) <= 0.25f &&
            deltaZ.HasValue && MathF.Abs(deltaZ.Value) <= 0.25f;

        return new PlayerCurrentReadResult(
            Mode: "player-current-read",
            ProcessId: processId,
            ProcessName: processName,
            ReaderBridgeSourceFile: snapshotDocument.SourceFile,
            FamilyId: capture.FamilyId,
            FamilyNotes: capture.FamilyNotes,
            Signature: capture.Signature,
            SelectionSource: capture.SelectionSource,
            ConfirmationFile: capture.ConfirmationFile,
            CeConfirmedSampleCount: capture.CeConfirmedSampleCount,
            Memory: new PlayerCurrentReadSample(
                AddressHex: sample.AddressHex,
                Level: sample.Level,
                Health: sample.Health,
                Name: sample.Name,
                Location: sample.Location,
                CoordX: sample.CoordX,
                CoordY: sample.CoordY,
                CoordZ: sample.CoordZ),
            Expected: expected,
            Match: new PlayerCurrentReadMatch(
                LevelMatches: levelMatches,
                HealthMatches: healthMatches,
                CoordMatchesWithinTolerance: coordMatches,
                DeltaX: deltaX,
                DeltaY: deltaY,
                DeltaZ: deltaZ));
    }
}
