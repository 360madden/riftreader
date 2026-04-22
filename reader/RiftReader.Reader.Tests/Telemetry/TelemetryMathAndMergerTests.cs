using System.Text.Json;
using RiftReader.Reader.Telemetry;

namespace RiftReader.Reader.Tests.Telemetry;

public sealed class TelemetryMathAndMergerTests
{
    [Fact]
    public void ComputeTravelHeadingDegrees_UsesXzPlane()
    {
        var heading = TelemetryMath.ComputeTravelHeadingDegrees(1d, 1d);

        Assert.NotNull(heading);
        Assert.InRange(heading!.Value, 44.9d, 45.1d);
    }

    [Fact]
    public void NormalizeAngleDegrees_WrapsAcrossBoundary()
    {
        var normalized = TelemetryMath.NormalizeAngleDegrees(350d);

        Assert.Equal(-10d, normalized);
    }

    [Fact]
    public void Merge_PrefersMemoryCoordsAndLeavesFacingInvalidWhenUnavailable()
    {
        var merger = new DefaultTelemetryMerger(100, diagnosticsEnabled: false);
        var now = new DateTimeOffset(2026, 4, 22, 16, 0, 0, TimeSpan.Zero);
        var process = new TelemetryProcessInfo(1234, "rift_x64", "rift_x64.exe", "RIFT", now.AddMinutes(-2));

        var context = new TelemetryContextSourceReading(
            Available: true,
            Valid: true,
            SampledAtUtc: now,
            SourceKind: "addon-readerbridge-export",
            Reason: null,
            SnapshotFile: @"C:\temp\ReaderBridgeExport.lua",
            SnapshotFileAgeSeconds: 1d,
            SnapshotDocument: null,
            AddonPosition: new TelemetryPositionValue(
                Valid: true,
                SourceKind: "addon",
                SampledAtUtc: now,
                Coord: new TelemetryVector3(10d, 20d, 30d),
                Zone: "Sanctum",
                LocationName: "City",
                Address: null,
                Reason: null,
                Provenance: "addon"),
            PlayerId: "player.unit",
            TargetId: "target.unit",
            Zone: "Sanctum",
            LocationName: "City",
            Combat: true,
            SourceAddon: "ReaderBridge",
            SourceMode: "ReaderBridge");

        var memory = new TelemetryPositionSourceReading(
            Available: true,
            Valid: true,
            SampledAtUtc: now,
            SourceKind: "proof-coord-anchor",
            Reason: null,
            Position: new TelemetryPositionValue(
                Valid: true,
                SourceKind: "memory",
                SampledAtUtc: now,
                Coord: new TelemetryVector3(100d, 200d, 300d),
                Zone: "Sanctum",
                LocationName: "City",
                Address: "0x12345678",
                Reason: null,
                Provenance: "trace-epoch-current-player-region"),
            ProofAnchor: new TelemetryProofAnchorDiagnostics(true, "trace-epoch-current-player-region", "trace-epoch", null, "0x12345678", 2d, Array.Empty<string>()),
            CoordMismatch: null,
            Discovery: null);

        var facing = new TelemetryFacingSourceReading(
            Available: false,
            Valid: false,
            SampledAtUtc: now,
            SourceKind: "behavior-backed-memory-facing",
            Reason: "lead unavailable",
            Facing: new TelemetryFacingEnvelope(
                Valid: false,
                SourceKind: "behavior-backed-memory-facing",
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: null,
                PitchDegrees: null,
                Forward: null,
                SourceAddress: null,
                BasisForwardOffset: null,
                BasisDuplicateForwardOffset: null,
                Reason: "lead unavailable",
                Provenance: null),
            LeadDiagnostics: null,
            Discovery: null);

        var snapshot = merger.Merge(1, now, process, context, memory, facing);

        Assert.Equal("memory", snapshot.Meta.EffectivePositionSource);
        Assert.Equal(100d, snapshot.Position.Effective!.Coord!.X);
        Assert.False(snapshot.Facing.Valid);
        Assert.False(snapshot.Meta.Validity.FacingValid);
    }

    [Fact]
    public void TelemetrySnapshot_SerializesWithCamelCaseContract()
    {
        var snapshot = new TelemetryHostSnapshot(
            SchemaVersion: 1,
            Sequence: 1,
            GeneratedAtUtc: new DateTimeOffset(2026, 4, 22, 16, 0, 0, TimeSpan.Zero),
            Process: new TelemetryProcessInfo(1, "rift_x64", null, null, null),
            Meta: new TelemetryMeta(
                HostVersion: "1.0.0",
                PollIntervalMilliseconds: 100,
                DiagnosticsEnabled: false,
                SourceAvailability: new TelemetrySourceAvailability(true, false, false),
                Freshness: new TelemetrySourceFreshness(1d, null, null),
                Validity: new TelemetrySourceValidity(true, false, false),
                EffectivePositionSource: "addon",
                EffectiveFacingSource: "none"),
            Position: new TelemetryPositionEnvelope(null, null, null, "none"),
            Facing: new TelemetryFacingEnvelope(false, "none", null, null, null, null, null, null, null, null, null, null),
            Movement: new TelemetryMovementEnvelope(null, null, null, null, null, null, null, null, null, false, false),
            State: new TelemetryStateEnvelope(null, null, null, null, null),
            Diagnostics: new TelemetryDiagnosticsEnvelope(null, null, null, null, null, null));

        var json = JsonSerializer.Serialize(snapshot, TelemetryJson.SerializerOptions);

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        Assert.True(root.TryGetProperty("schemaVersion", out var schemaVersion));
        Assert.Equal(1, schemaVersion.GetInt32());
        Assert.True(root.TryGetProperty("generatedAtUtc", out _));
        Assert.Equal("addon", root.GetProperty("meta").GetProperty("effectivePositionSource").GetString());
    }
}
