using System.Collections.Concurrent;
using RiftReader.Reader.Telemetry;

namespace RiftReader.Reader.Tests.Telemetry;

public sealed class TelemetryHostTimingTests
{
    [Fact]
    public async Task Run_UsesPostReadTimestampAndRecoversFromDegradedMemoryState()
    {
        var options = new TelemetryHostOptions(
            ProcessName: "rift_x64",
            ProcessId: 1234,
            PollIntervalMilliseconds: 1,
            DiagnosticsEnabled: true,
            ReaderBridgeSnapshotFile: null,
            PlayerCoordTraceFile: null,
            LatestSnapshotFile: @"C:\temp\telemetry.latest.json",
            EventLogFile: @"C:\temp\telemetry.events.ndjson",
            DiscoveryLogFile: @"C:\temp\telemetry.discovery.ndjson",
            ProofCoordAnchorScript: @"C:\temp\resolve-proof-coord-anchor.ps1",
            ProofAnchorCacheFile: null,
            ProofAnchorRevalidationInterval: TimeSpan.FromSeconds(5),
            ProofAnchorMaxAge: TimeSpan.FromSeconds(10));

        var process = new TelemetryProcessInfo(
            ProcessId: 1234,
            ProcessName: "rift_x64",
            ModuleName: "rift_x64.exe",
            MainWindowTitle: "RIFT",
            StartedAtUtc: new DateTimeOffset(2026, 4, 22, 16, 0, 0, TimeSpan.Zero));

        var context = new StaticContextSource();
        var positionSource = new DelayedRecoveryPositionSource();
        var facingSource = new StaticFacingSource();
        var merger = new DefaultTelemetryMerger(1, diagnosticsEnabled: true);
        using var cancellationSource = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        var publisher = new CapturingPublisher(expectedSnapshots: 2, cancellationSource);
        var logger = new NullTelemetryLogger();
        var host = new TelemetryHost(options, process, context, positionSource, facingSource, merger, publisher, logger);

        var exitCode = await Task.Run(() => host.Run(cancellationSource.Token));
        var snapshots = publisher.Snapshots.ToArray();

        Assert.Equal(0, exitCode);
        Assert.Equal(2, snapshots.Length);
        Assert.Equal("addon", snapshots[0].Meta.EffectivePositionSource);
        Assert.Equal("memory", snapshots[1].Meta.EffectivePositionSource);
        Assert.NotNull(positionSource.RecoveryCompletedAtUtc);
        Assert.True(
            snapshots[1].GeneratedAtUtc >= positionSource.RecoveryCompletedAtUtc!.Value,
            $"Expected snapshot timestamp {snapshots[1].GeneratedAtUtc:O} to be on or after recovery completion {positionSource.RecoveryCompletedAtUtc:O}.");
    }

    private sealed class StaticContextSource : IContextSource
    {
        public TelemetryContextSourceReading Read()
        {
            var sampledAtUtc = DateTimeOffset.UtcNow;
            return new TelemetryContextSourceReading(
                Available: true,
                Valid: true,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "addon-readerbridge-export",
                Reason: null,
                SnapshotFile: @"C:\temp\ReaderBridgeExport.lua",
                SnapshotFileAgeSeconds: 0.25d,
                SnapshotDocument: null,
                AddonPosition: new TelemetryPositionValue(
                    Valid: true,
                    SourceKind: "addon",
                    SampledAtUtc: sampledAtUtc,
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
                Combat: false,
                SourceAddon: "ReaderBridge",
                SourceMode: "ReaderBridge");
        }
    }

    private sealed class DelayedRecoveryPositionSource : IPositionSource
    {
        private int _readCount;

        public DateTimeOffset? RecoveryCompletedAtUtc { get; private set; }

        public TelemetryPositionSourceReading Read(TelemetryContextSourceReading? context)
        {
            var readNumber = Interlocked.Increment(ref _readCount);
            if (readNumber == 1)
            {
                var sampledAtUtc = DateTimeOffset.UtcNow;
                return new TelemetryPositionSourceReading(
                    Available: true,
                    Valid: false,
                    SampledAtUtc: sampledAtUtc,
                    SourceKind: "proof-coord-anchor",
                    Reason: "Proof coord anchor refresh is in progress.",
                    Position: null,
                    ProofAnchor: new TelemetryProofAnchorDiagnostics(
                        Valid: false,
                        SourceKind: "coord-trace-direct-region",
                        MatchSource: "readerbridge-live",
                        TraceSourceFile: null,
                        CoordRegionAddress: "0x0",
                        AgeSeconds: 12d,
                        Notes: Array.Empty<string>()),
                    CoordMismatch: null,
                    Discovery: null);
            }

            Thread.Sleep(150);
            RecoveryCompletedAtUtc = DateTimeOffset.UtcNow;
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: true,
                SampledAtUtc: RecoveryCompletedAtUtc.Value,
                SourceKind: "proof-coord-anchor",
                Reason: null,
                Position: new TelemetryPositionValue(
                    Valid: true,
                    SourceKind: "validated-memory-coords",
                    SampledAtUtc: RecoveryCompletedAtUtc.Value,
                    Coord: new TelemetryVector3(100d, 200d, 300d),
                    Zone: context?.Zone,
                    LocationName: context?.LocationName,
                    Address: "0x12345678",
                    Reason: null,
                    Provenance: "coord-trace-direct-region"),
                ProofAnchor: new TelemetryProofAnchorDiagnostics(
                    Valid: true,
                    SourceKind: "coord-trace-direct-region",
                    MatchSource: "readerbridge-live",
                    TraceSourceFile: null,
                    CoordRegionAddress: "0x12345678",
                    AgeSeconds: 0d,
                    Notes: Array.Empty<string>()),
                CoordMismatch: null,
                Discovery: null);
        }
    }

    private sealed class StaticFacingSource : IFacingSource
    {
        public TelemetryFacingSourceReading Read(TelemetryContextSourceReading? context)
        {
            var sampledAtUtc = DateTimeOffset.UtcNow;
            return new TelemetryFacingSourceReading(
                Available: true,
                Valid: true,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "behavior-backed-memory-facing",
                Reason: null,
                Facing: new TelemetryFacingEnvelope(
                    Valid: true,
                    SourceKind: "behavior-backed-memory-facing",
                    YawRadians: 0.5d,
                    YawDegrees: 28.64788975654116d,
                    PitchRadians: 0.1d,
                    PitchDegrees: 5.729577951308232d,
                    Forward: new TelemetryVector3(0d, 0d, 1d),
                    SourceAddress: "0xABC",
                    BasisForwardOffset: "0xD4",
                    BasisDuplicateForwardOffset: null,
                    Reason: null,
                    Provenance: "lead.json"),
                LeadDiagnostics: new TelemetryFacingLeadDiagnostics(
                    Valid: true,
                    LeadFile: "lead.json",
                    AgeSeconds: 1d,
                    SourceAddress: "0xABC",
                    BasisForwardOffset: "0xD4",
                    BasisDuplicateForwardOffset: null,
                    Notes: Array.Empty<string>()),
                Discovery: null);
        }
    }

    private sealed class CapturingPublisher(int expectedSnapshots, CancellationTokenSource cancellationSource) : ITelemetryPublisher
    {
        private readonly int _expectedSnapshots = expectedSnapshots;
        private readonly CancellationTokenSource _cancellationSource = cancellationSource;

        public ConcurrentQueue<TelemetryHostSnapshot> Snapshots { get; } = new();

        public void Publish(TelemetryHostSnapshot snapshot)
        {
            Snapshots.Enqueue(snapshot);
            if (Snapshots.Count >= _expectedSnapshots)
            {
                _cancellationSource.Cancel();
            }
        }
    }
}
