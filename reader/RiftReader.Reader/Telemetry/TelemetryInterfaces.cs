namespace RiftReader.Reader.Telemetry;

public interface IContextSource
{
    TelemetryContextSourceReading Read();
}

public interface IPositionSource
{
    TelemetryPositionSourceReading Read(TelemetryContextSourceReading? context);
}

public interface IFacingSource
{
    TelemetryFacingSourceReading Read(TelemetryContextSourceReading? context);
}

public interface ITelemetryMerger
{
    TelemetryHostSnapshot Merge(
        long sequence,
        DateTimeOffset generatedAtUtc,
        TelemetryProcessInfo process,
        TelemetryContextSourceReading context,
        TelemetryPositionSourceReading memoryPosition,
        TelemetryFacingSourceReading facing);
}

public interface ITelemetryPublisher
{
    void Publish(TelemetryHostSnapshot snapshot);
}

public interface ITelemetryLogger
{
    void LogEvent(string category, string message, object? data = null, bool discovery = false);

    void LogTransition(string category, string key, string message, object? data = null, bool discovery = false);
}
