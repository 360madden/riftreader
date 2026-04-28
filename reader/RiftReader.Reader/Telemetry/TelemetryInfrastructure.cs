using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RiftReader.Reader.Telemetry;

public static class TelemetryJson
{
    public static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = true
    };

    public static readonly JsonSerializerOptions NdjsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };
}

public sealed class JsonFileTelemetryPublisher(string latestSnapshotFile) : ITelemetryPublisher
{
    private readonly string _latestSnapshotFile = Path.GetFullPath(latestSnapshotFile);

    public void Publish(TelemetryHostSnapshot snapshot)
    {
        var directory = Path.GetDirectoryName(_latestSnapshotFile);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var tempFile = _latestSnapshotFile + ".tmp";
        var json = JsonSerializer.Serialize(snapshot, TelemetryJson.SerializerOptions);
        File.WriteAllText(tempFile, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        File.Move(tempFile, _latestSnapshotFile, overwrite: true);
    }
}

public sealed class StructuredTelemetryLogger : ITelemetryLogger
{
    private const long MaxLogBytes = 10L * 1024L * 1024L;
    private const int MaxRollFiles = 5;

    private readonly string _eventLogFile;
    private readonly string? _discoveryLogFile;
    private readonly Dictionary<string, string> _transitionKeys = new(StringComparer.Ordinal);

    public StructuredTelemetryLogger(string eventLogFile, string? discoveryLogFile)
    {
        _eventLogFile = Path.GetFullPath(eventLogFile);
        _discoveryLogFile = string.IsNullOrWhiteSpace(discoveryLogFile)
            ? null
            : Path.GetFullPath(discoveryLogFile);
    }

    public void LogEvent(string category, string message, object? data = null, bool discovery = false)
    {
        var file = discovery ? _discoveryLogFile : _eventLogFile;
        if (string.IsNullOrWhiteSpace(file))
        {
            return;
        }

        var entry = new TelemetryLogEvent(
            GeneratedAtUtc: DateTimeOffset.UtcNow,
            Category: category,
            Message: message,
            Data: data);

        var json = JsonSerializer.Serialize(entry, TelemetryJson.NdjsonOptions);
        AppendLineWithRotation(file, json);
    }

    public void LogTransition(string category, string key, string message, object? data = null, bool discovery = false)
    {
        if (_transitionKeys.TryGetValue(category, out var previous) && string.Equals(previous, key, StringComparison.Ordinal))
        {
            return;
        }

        _transitionKeys[category] = key;
        LogEvent(category, message, data, discovery);
    }

    private static void AppendLineWithRotation(string file, string line)
    {
        var directory = Path.GetDirectoryName(file);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var entryBytes = Encoding.UTF8.GetByteCount(line + Environment.NewLine);
        RotateIfNeeded(file, entryBytes);
        File.AppendAllText(file, line + Environment.NewLine, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
    }

    private static void RotateIfNeeded(string file, int incomingBytes)
    {
        if (!File.Exists(file))
        {
            return;
        }

        var info = new FileInfo(file);
        if ((info.Length + incomingBytes) <= MaxLogBytes)
        {
            return;
        }

        for (var index = MaxRollFiles; index >= 1; index--)
        {
            var source = index == 1 ? file : $"{file}.{index - 1}";
            var destination = $"{file}.{index}";

            if (!File.Exists(source))
            {
                continue;
            }

            if (File.Exists(destination))
            {
                File.Delete(destination);
            }

            File.Move(source, destination);
        }
    }
}

public sealed class NullTelemetryLogger : ITelemetryLogger
{
    public void LogEvent(string category, string message, object? data = null, bool discovery = false)
    {
    }

    public void LogTransition(string category, string key, string message, object? data = null, bool discovery = false)
    {
    }
}

public sealed class DefaultTelemetryMerger(int pollIntervalMilliseconds, bool diagnosticsEnabled) : ITelemetryMerger
{
    private TelemetryPositionValue? _previousEffectivePosition;
    private DateTimeOffset? _previousEffectivePositionAtUtc;
    private double? _previousYawDegrees;
    private DateTimeOffset? _previousYawAtUtc;

    public TelemetryHostSnapshot Merge(
        long sequence,
        DateTimeOffset generatedAtUtc,
        TelemetryProcessInfo process,
        TelemetryContextSourceReading context,
        TelemetryPositionSourceReading memoryPosition,
        TelemetryFacingSourceReading facing)
    {
        var addonPosition = context.AddonPosition;
        var effectivePosition = memoryPosition.Valid
            ? memoryPosition.Position
            : addonPosition?.Valid == true
                ? addonPosition
                : null;
        var effectivePositionSource = memoryPosition.Valid
            ? "memory"
            : addonPosition?.Valid == true
                ? "addon"
                : "none";

        var effectiveFacingSource = facing.Valid ? "memory-facing" : "none";
        var normalizedProofAnchor = NormalizeProofAnchorDiagnostics(memoryPosition.ProofAnchor);
        var normalizedFacingLead = NormalizeFacingLeadDiagnostics(facing.LeadDiagnostics);

        double? dx = null;
        double? dy = null;
        double? dz = null;
        double? distance = null;
        double? dt = null;
        double? speed = null;
        if (_previousEffectivePosition?.Coord is not null && effectivePosition?.Coord is not null && _previousEffectivePositionAtUtc.HasValue)
        {
            dx = effectivePosition.Coord.X - _previousEffectivePosition.Coord.X;
            dy = effectivePosition.Coord.Y - _previousEffectivePosition.Coord.Y;
            dz = effectivePosition.Coord.Z - _previousEffectivePosition.Coord.Z;
            distance = Math.Sqrt((dx.Value * dx.Value) + (dy.Value * dy.Value) + (dz.Value * dz.Value));
            dt = (generatedAtUtc - _previousEffectivePositionAtUtc.Value).TotalSeconds;
            if (dt > 0d)
            {
                speed = distance / dt;
            }
        }

        var travelHeadingRadians = TelemetryMath.ComputeTravelHeadingRadians(dx, dz);
        var travelHeadingDegrees = travelHeadingRadians.HasValue
            ? travelHeadingRadians.Value * 180d / Math.PI
            : (double?)null;
        var yawRateDegreesPerSecond = TelemetryMath.ComputeYawRateDegreesPerSecond(_previousYawDegrees, _previousYawAtUtc, facing.Facing.YawDegrees, generatedAtUtc);

        if (effectivePosition is not null)
        {
            _previousEffectivePosition = effectivePosition;
            _previousEffectivePositionAtUtc = generatedAtUtc;
        }

        if (facing.Valid && facing.Facing.YawDegrees.HasValue)
        {
            _previousYawDegrees = facing.Facing.YawDegrees;
            _previousYawAtUtc = generatedAtUtc;
        }

        var movement = new TelemetryMovementEnvelope(
            Dx: dx,
            Dy: dy,
            Dz: dz,
            Distance: distance,
            Dt: dt,
            Speed: speed,
            TravelHeadingRadians: travelHeadingRadians,
            TravelHeadingDegrees: travelHeadingDegrees,
            YawRateDegreesPerSecond: yawRateDegreesPerSecond,
            IsMoving: speed.HasValue && speed.Value > 0.01d,
            IsTurning: yawRateDegreesPerSecond.HasValue && Math.Abs(yawRateDegreesPerSecond.Value) > 0.5d);

        return new TelemetryHostSnapshot(
            SchemaVersion: 1,
            Sequence: sequence,
            GeneratedAtUtc: generatedAtUtc,
            Process: process,
            Meta: new TelemetryMeta(
                HostVersion: typeof(DefaultTelemetryMerger).Assembly.GetName().Version?.ToString() ?? "dev",
                PollIntervalMilliseconds: pollIntervalMilliseconds,
                DiagnosticsEnabled: diagnosticsEnabled,
                SourceAvailability: new TelemetrySourceAvailability(
                    AddonContextAvailable: context.Available,
                    MemoryCoordAvailable: memoryPosition.Available,
                    MemoryFacingAvailable: facing.Available),
                Freshness: new TelemetrySourceFreshness(
                    AddonSnapshotFileAgeSeconds: context.SnapshotFileAgeSeconds,
                    ProofAnchorAgeSeconds: normalizedProofAnchor?.AgeSeconds,
                    FacingLeadAgeSeconds: normalizedFacingLead?.AgeSeconds),
                Validity: new TelemetrySourceValidity(
                    AddonPositionValid: addonPosition?.Valid == true,
                    MemoryCoordValid: memoryPosition.Valid,
                    FacingValid: facing.Valid),
                EffectivePositionSource: effectivePositionSource,
                EffectiveFacingSource: effectiveFacingSource),
            Position: new TelemetryPositionEnvelope(
                Addon: addonPosition,
                Memory: memoryPosition.Position,
                Effective: effectivePosition,
                EffectiveSource: effectivePositionSource),
            Facing: facing.Facing,
            Movement: movement,
            State: new TelemetryStateEnvelope(
                PlayerId: context.PlayerId,
                TargetId: context.TargetId,
                Zone: context.Zone,
                LocationName: context.LocationName,
                Combat: context.Combat),
            Diagnostics: new TelemetryDiagnosticsEnvelope(
                PositionReason: memoryPosition.Reason,
                FacingReason: facing.Reason,
                ProofAnchor: normalizedProofAnchor,
                FacingLead: normalizedFacingLead,
                CoordMismatch: memoryPosition.CoordMismatch,
                Discovery: diagnosticsEnabled
                    ? new
                    {
                        position = memoryPosition.Discovery,
                        facing = facing.Discovery
                    }
                    : null));
    }

    private static TelemetryProofAnchorDiagnostics? NormalizeProofAnchorDiagnostics(TelemetryProofAnchorDiagnostics? proofAnchor)
    {
        if (proofAnchor is null)
        {
            return null;
        }

        var normalizedAgeSeconds = NormalizeAgeSeconds(proofAnchor.AgeSeconds);
        return normalizedAgeSeconds == proofAnchor.AgeSeconds
            ? proofAnchor
            : proofAnchor with { AgeSeconds = normalizedAgeSeconds };
    }

    private static TelemetryFacingLeadDiagnostics? NormalizeFacingLeadDiagnostics(TelemetryFacingLeadDiagnostics? facingLead)
    {
        if (facingLead is null)
        {
            return null;
        }

        var normalizedAgeSeconds = NormalizeAgeSeconds(facingLead.AgeSeconds);
        return normalizedAgeSeconds == facingLead.AgeSeconds
            ? facingLead
            : facingLead with { AgeSeconds = normalizedAgeSeconds };
    }

    private static double? NormalizeAgeSeconds(double? ageSeconds) =>
        ageSeconds.HasValue
            ? Math.Max(0d, ageSeconds.Value)
            : null;
}
