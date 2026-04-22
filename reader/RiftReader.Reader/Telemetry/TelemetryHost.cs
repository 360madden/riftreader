using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Telemetry;

public sealed class TelemetryHost
{
    private static readonly TimeSpan HeartbeatInterval = TimeSpan.FromSeconds(5);

    private readonly TelemetryHostOptions _options;
    private readonly TelemetryProcessInfo _process;
    private readonly IContextSource _contextSource;
    private readonly IPositionSource _positionSource;
    private readonly IFacingSource _facingSource;
    private readonly ITelemetryMerger _merger;
    private readonly ITelemetryPublisher _publisher;
    private readonly ITelemetryLogger _logger;

    public TelemetryHost(
        TelemetryHostOptions options,
        TelemetryProcessInfo process,
        IContextSource contextSource,
        IPositionSource positionSource,
        IFacingSource facingSource,
        ITelemetryMerger merger,
        ITelemetryPublisher publisher,
        ITelemetryLogger logger)
    {
        _options = options;
        _process = process;
        _contextSource = contextSource;
        _positionSource = positionSource;
        _facingSource = facingSource;
        _merger = merger;
        _publisher = publisher;
        _logger = logger;
    }

    public int Run(CancellationToken cancellationToken)
    {
        var sequence = 0L;
        var lastHeartbeatUtc = DateTimeOffset.MinValue;
        _logger.LogEvent(
            "host.lifecycle",
            "Telemetry host started.",
            new
            {
                _process.ProcessId,
                _process.ProcessName,
                _options.PollIntervalMilliseconds,
                _options.DiagnosticsEnabled,
                _options.LatestSnapshotFile
            });

        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var context = _contextSource.Read();
                var memoryPosition = _positionSource.Read(context);
                var facing = _facingSource.Read(context);
                var generatedAtUtc = DateTimeOffset.UtcNow;
                if (context.SampledAtUtc > generatedAtUtc)
                {
                    generatedAtUtc = context.SampledAtUtc;
                }

                if (memoryPosition.SampledAtUtc > generatedAtUtc)
                {
                    generatedAtUtc = memoryPosition.SampledAtUtc;
                }

                if (facing.SampledAtUtc > generatedAtUtc)
                {
                    generatedAtUtc = facing.SampledAtUtc;
                }

                var snapshot = _merger.Merge(++sequence, generatedAtUtc, _process, context, memoryPosition, facing);
                _publisher.Publish(snapshot);

                _logger.LogTransition(
                    "source.context",
                    $"{context.Available}|{context.Valid}|{context.SourceMode}|{context.Reason}",
                    "Context source state changed.",
                    new
                    {
                        context.Available,
                        context.Valid,
                        context.SourceMode,
                        context.SnapshotFile,
                        context.Reason
                    });

                _logger.LogTransition(
                    "source.coord",
                    $"{memoryPosition.Available}|{memoryPosition.Valid}|{memoryPosition.Position?.Address}|{memoryPosition.Reason}",
                    "Memory coord source state changed.",
                    new
                    {
                        memoryPosition.Available,
                        memoryPosition.Valid,
                        memoryPosition.Position?.Address,
                        memoryPosition.Reason
                    });

                _logger.LogTransition(
                    "source.facing",
                    $"{facing.Available}|{facing.Valid}|{facing.Facing.SourceAddress}|{facing.Reason}",
                    "Facing source state changed.",
                    new
                    {
                        facing.Available,
                        facing.Valid,
                        facing.Facing.SourceAddress,
                        facing.Reason
                    });

                _logger.LogTransition(
                    "source.switch",
                    $"{snapshot.Meta.EffectivePositionSource}|{snapshot.Meta.EffectiveFacingSource}",
                    "Effective telemetry sources changed.",
                    new
                    {
                        snapshot.Meta.EffectivePositionSource,
                        snapshot.Meta.EffectiveFacingSource
                    });

                if (!memoryPosition.Valid || !facing.Valid)
                {
                    _logger.LogTransition(
                        "publish.degraded",
                        $"{memoryPosition.Valid}|{facing.Valid}|{memoryPosition.Reason}|{facing.Reason}",
                        "Telemetry host is publishing degraded state.",
                        new
                        {
                            MemoryCoordValid = memoryPosition.Valid,
                            FacingValid = facing.Valid,
                            MemoryCoordReason = memoryPosition.Reason,
                            FacingReason = facing.Reason
                        });
                }

                if ((generatedAtUtc - lastHeartbeatUtc) >= HeartbeatInterval)
                {
                    lastHeartbeatUtc = generatedAtUtc;
                    _logger.LogEvent(
                        "publish.snapshot",
                        "Telemetry heartbeat.",
                        new
                        {
                            snapshot.Sequence,
                            snapshot.Meta.EffectivePositionSource,
                            snapshot.Meta.EffectiveFacingSource,
                            snapshot.Position.Effective?.Coord,
                            snapshot.Facing.YawDegrees,
                            snapshot.Movement.Speed
                        });
                }

                Task.Delay(_options.PollIntervalMilliseconds, cancellationToken).GetAwaiter().GetResult();
            }
        }
        catch (OperationCanceledException)
        {
            // graceful shutdown
        }
        finally
        {
            _logger.LogEvent(
                "host.lifecycle",
                "Telemetry host stopped.",
                new
                {
                    _process.ProcessId,
                    _process.ProcessName
                });
        }

        return 0;
    }
}
