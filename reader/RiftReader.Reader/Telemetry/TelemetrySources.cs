using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Models;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Telemetry;

public sealed class AddonContextSource(string? snapshotFile) : IContextSource
{
    private readonly string? _snapshotFile = snapshotFile;
    private ReaderBridgeSnapshotDocument? _lastGoodDocument;

    public TelemetryContextSourceReading Read()
    {
        var sampledAtUtc = DateTimeOffset.UtcNow;
        var document = ReaderBridgeSnapshotLoader.TryLoad(_snapshotFile, out var error);
        if (document is not null)
        {
            _lastGoodDocument = document;
        }

        var effectiveDocument = document ?? _lastGoodDocument;
        var snapshot = effectiveDocument?.Current;
        var player = snapshot?.Player;
        var telemetry = snapshot?.Telemetry;
        var coord = telemetry?.Position?.Coord ?? player?.Coord;

        TelemetryPositionValue? addonPosition = null;
        if (coord?.X is double x && coord.Y is double y && coord.Z is double z)
        {
            addonPosition = new TelemetryPositionValue(
                Valid: true,
                SourceKind: "addon-readerbridge-export",
                SampledAtUtc: sampledAtUtc,
                Coord: new TelemetryVector3(x, y, z),
                Zone: telemetry?.Position?.Zone ?? player?.Zone,
                LocationName: telemetry?.Position?.LocationName ?? player?.LocationName,
                Address: null,
                Reason: error,
                Provenance: effectiveDocument?.SourceFile);
        }

        double? snapshotFileAgeSeconds = null;
        var sourceFile = effectiveDocument?.SourceFile;
        if (!string.IsNullOrWhiteSpace(sourceFile) && File.Exists(sourceFile))
        {
            var lastWriteUtc = File.GetLastWriteTimeUtc(sourceFile);
            snapshotFileAgeSeconds = Math.Max(0d, (sampledAtUtc.UtcDateTime - lastWriteUtc).TotalSeconds);
        }

        return new TelemetryContextSourceReading(
            Available: effectiveDocument is not null,
            Valid: document is not null,
            SampledAtUtc: sampledAtUtc,
            SourceKind: "addon-readerbridge-export",
            Reason: document is null ? error : null,
            SnapshotFile: effectiveDocument?.SourceFile,
            SnapshotFileAgeSeconds: snapshotFileAgeSeconds,
            SnapshotDocument: effectiveDocument,
            AddonPosition: addonPosition,
            PlayerId: telemetry?.Context?.PlayerId ?? player?.Id,
            TargetId: telemetry?.Context?.TargetId ?? snapshot?.Target?.Id,
            Zone: telemetry?.Context?.Zone ?? player?.Zone,
            LocationName: telemetry?.Context?.LocationName ?? player?.LocationName,
            Combat: telemetry?.Context?.Combat ?? player?.Combat,
            SourceAddon: telemetry?.Context?.SourceAddon ?? snapshot?.SourceAddon,
            SourceMode: telemetry?.Context?.SourceMode ?? snapshot?.SourceMode);
    }
}

public sealed class MemoryCoordSource : IPositionSource
{
    private readonly ProcessMemoryReader _reader;
    private readonly int _processId;
    private readonly string _processName;
    private readonly string _proofCoordAnchorScript;
    private readonly string? _playerCoordTraceFile;
    private readonly TimeSpan _revalidationInterval;
    private readonly TimeSpan _maxAnchorAge;
    private readonly ITelemetryLogger _logger;
    private readonly bool _diagnosticsEnabled;

    private ProofCoordAnchorDocument? _anchor;
    private DateTimeOffset? _lastResolveAttemptUtc;
    private string? _lastResolveError;

    public MemoryCoordSource(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string proofCoordAnchorScript,
        string? playerCoordTraceFile,
        TimeSpan revalidationInterval,
        TimeSpan maxAnchorAge,
        ITelemetryLogger logger,
        bool diagnosticsEnabled)
    {
        _reader = reader;
        _processId = processId;
        _processName = processName;
        _proofCoordAnchorScript = proofCoordAnchorScript;
        _playerCoordTraceFile = playerCoordTraceFile;
        _revalidationInterval = revalidationInterval;
        _maxAnchorAge = maxAnchorAge;
        _logger = logger;
        _diagnosticsEnabled = diagnosticsEnabled;
    }

    public TelemetryPositionSourceReading Read(TelemetryContextSourceReading? context)
    {
        var sampledAtUtc = DateTimeOffset.UtcNow;
        var refreshed = TryRefreshAnchorIfNeeded(sampledAtUtc);
        if (refreshed?.Document is not null)
        {
            _anchor = refreshed.Document;
            _lastResolveError = null;
        }
        else if (!string.IsNullOrWhiteSpace(refreshed?.Error))
        {
            _lastResolveError = refreshed.Error;
        }

        if (_anchor is null)
        {
            return new TelemetryPositionSourceReading(
                Available: false,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: _lastResolveError ?? "Proof coord anchor has not been established.",
                Position: null,
                ProofAnchor: null,
                CoordMismatch: null,
                Discovery: null);
        }

        var anchorAge = sampledAtUtc - _anchor.GeneratedAtUtc;
        if (anchorAge > _maxAnchorAge)
        {
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: $"Proof coord anchor validation is stale ({anchorAge.TotalSeconds:0.0}s old).",
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(_anchor, anchorAge.TotalSeconds),
                CoordMismatch: BuildCoordMismatch(_anchor.Match),
                Discovery: BuildDiscovery(_anchor));
        }

        if (!TryParseAddress(_anchor.CoordRegionAddress, out var coordRegionAddress))
        {
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: $"Invalid coord region address '{_anchor.CoordRegionAddress ?? "<null>"}'.",
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(_anchor, anchorAge.TotalSeconds),
                CoordMismatch: BuildCoordMismatch(_anchor.Match),
                Discovery: BuildDiscovery(_anchor));
        }

        var sample = TryReadVector3(coordRegionAddress, _anchor.CoordXRelativeOffset ?? 0, _anchor.CoordYRelativeOffset ?? 4, _anchor.CoordZRelativeOffset ?? 8, out var readError);
        if (sample is null)
        {
            _lastResolveError = readError;
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: readError,
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(_anchor, anchorAge.TotalSeconds),
                CoordMismatch: BuildCoordMismatch(_anchor.Match),
                Discovery: BuildDiscovery(_anchor));
        }

        var position = new TelemetryPositionValue(
            Valid: true,
            SourceKind: "validated-memory-coords",
            SampledAtUtc: sampledAtUtc,
            Coord: sample,
            Zone: context?.Zone,
            LocationName: context?.LocationName,
            Address: _anchor.CoordRegionAddress,
            Reason: null,
            Provenance: _anchor.CanonicalCoordSourceKind);

        return new TelemetryPositionSourceReading(
            Available: true,
            Valid: true,
            SampledAtUtc: sampledAtUtc,
            SourceKind: "proof-coord-anchor",
            Reason: null,
            Position: position,
            ProofAnchor: BuildProofAnchorDiagnostics(_anchor, anchorAge.TotalSeconds),
            CoordMismatch: BuildCoordMismatch(_anchor.Match),
            Discovery: BuildDiscovery(_anchor));
    }

    private ProofCoordAnchorResolveAttempt? TryRefreshAnchorIfNeeded(DateTimeOffset nowUtc)
    {
        var needsResolve =
            _anchor is null ||
            !_anchor.MatchIsValid ||
            !_lastResolveAttemptUtc.HasValue ||
            (nowUtc - _lastResolveAttemptUtc.Value) >= _revalidationInterval;

        if (!needsResolve)
        {
            return null;
        }

        _lastResolveAttemptUtc = nowUtc;

        var quick = TryResolve(skipRefresh: true);
        if (quick.Document is not null && quick.Document.MatchIsValid)
        {
            _logger.LogTransition(
                "source.coord",
                $"coord-anchor:{quick.Document.CanonicalCoordSourceKind}:{quick.Document.CoordRegionAddress}",
                "Validated proof coord anchor.",
                new
                {
                    quick.Document.CanonicalCoordSourceKind,
                    quick.Document.MatchSource,
                    quick.Document.CoordRegionAddress
                },
                discovery: _diagnosticsEnabled);

            return quick;
        }

        var full = TryResolve(skipRefresh: false);
        if (full.Document is not null && full.Document.MatchIsValid)
        {
            _logger.LogTransition(
                "source.coord",
                $"coord-anchor:{full.Document.CanonicalCoordSourceKind}:{full.Document.CoordRegionAddress}",
                "Refreshed proof coord anchor.",
                new
                {
                    full.Document.CanonicalCoordSourceKind,
                    full.Document.MatchSource,
                    full.Document.CoordRegionAddress
                },
                discovery: _diagnosticsEnabled);
        }
        else if (!string.IsNullOrWhiteSpace(full.Error ?? quick.Error))
        {
            _logger.LogTransition(
                "validation.mismatch",
                $"coord-anchor-error:{full.Error ?? quick.Error}",
                "Proof coord anchor validation failed.",
                new
                {
                    Error = full.Error ?? quick.Error,
                    QuickMatch = quick.Document?.Match,
                    FullMatch = full.Document?.Match
                },
                discovery: _diagnosticsEnabled);
        }

        return full.Document is not null ? full : quick;
    }

    private ProofCoordAnchorResolveAttempt TryResolve(bool skipRefresh)
    {
        using var process = new Process();
        process.StartInfo = new ProcessStartInfo
        {
            FileName = "pwsh",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        process.StartInfo.ArgumentList.Add("-NoProfile");
        process.StartInfo.ArgumentList.Add("-ExecutionPolicy");
        process.StartInfo.ArgumentList.Add("Bypass");
        process.StartInfo.ArgumentList.Add("-File");
        process.StartInfo.ArgumentList.Add(_proofCoordAnchorScript);
        process.StartInfo.ArgumentList.Add("-ProcessName");
        process.StartInfo.ArgumentList.Add(_processName);
        if (_processId > 0)
        {
            process.StartInfo.ArgumentList.Add("-ProcessId");
            process.StartInfo.ArgumentList.Add(_processId.ToString(CultureInfo.InvariantCulture));
        }

        process.StartInfo.ArgumentList.Add("-RefreshAttempts");
        process.StartInfo.ArgumentList.Add("1");
        if (skipRefresh)
        {
            process.StartInfo.ArgumentList.Add("-SkipRefresh");
        }

        if (!string.IsNullOrWhiteSpace(_playerCoordTraceFile))
        {
            process.StartInfo.ArgumentList.Add("-PlayerCoordTraceFile");
            process.StartInfo.ArgumentList.Add(_playerCoordTraceFile!);
        }

        process.StartInfo.ArgumentList.Add("-Json");

        process.Start();
        var stdout = process.StandardOutput.ReadToEnd();
        var stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        if (process.ExitCode != 0)
        {
            return new ProofCoordAnchorResolveAttempt(
                Document: null,
                Error: string.IsNullOrWhiteSpace(stderr) ? stdout.Trim() : stderr.Trim());
        }

        try
        {
            var document = JsonSerializer.Deserialize<ProofCoordAnchorDocument>(
                stdout,
                TelemetryJson.SerializerOptions);

            if (document is null)
            {
                return new ProofCoordAnchorResolveAttempt(Document: null, Error: "Proof coord anchor resolver returned an empty document.");
            }

            return new ProofCoordAnchorResolveAttempt(
                Document: document,
                Error: document.MatchIsValid ? null : "Proof coord anchor document did not contain a validated coord source.");
        }
        catch (Exception ex)
        {
            return new ProofCoordAnchorResolveAttempt(Document: null, Error: $"Unable to parse proof coord anchor JSON: {ex.Message}");
        }
    }

    private TelemetryProofAnchorDiagnostics BuildProofAnchorDiagnostics(ProofCoordAnchorDocument anchor, double ageSeconds) =>
        new(
            Valid: anchor.MatchIsValid,
            SourceKind: anchor.CanonicalCoordSourceKind,
            MatchSource: anchor.MatchSource,
            TraceSourceFile: anchor.TraceSourceFile,
            CoordRegionAddress: anchor.CoordRegionAddress,
            AgeSeconds: ageSeconds,
            Notes: anchor.Notes ?? Array.Empty<string>());

    private static TelemetryDeltaDiagnostics? BuildCoordMismatch(ProofCoordAnchorMatch? match) =>
        match is null
            ? null
            : new TelemetryDeltaDiagnostics(match.DeltaX, match.DeltaY, match.DeltaZ);

    private object? BuildDiscovery(ProofCoordAnchorDocument anchor)
    {
        if (!_diagnosticsEnabled)
        {
            return null;
        }

        return new
        {
            anchor.TraceSourceFile,
            anchor.TraceTargetAddress,
            anchor.TraceCandidateAddress,
            anchor.TraceObjectBaseAddress,
            anchor.ObjectBaseAddress,
            anchor.SourceObjectAddress,
            anchor.SourceCoordRelativeOffset,
            anchor.Match,
            anchor.TraceMatch,
            anchor.SourceObjectMatch
        };
    }

    private TelemetryVector3? TryReadVector3(long baseAddress, int xOffset, int yOffset, int zOffset, out string? error)
    {
        error = null;
        var minOffset = Math.Min(xOffset, Math.Min(yOffset, zOffset));
        var maxOffset = Math.Max(xOffset, Math.Max(yOffset, zOffset));
        var startAddress = baseAddress + minOffset;
        var length = (maxOffset - minOffset) + sizeof(float);

        if (!_reader.TryReadBytes(new IntPtr(startAddress), length, out var bytes, out var readError))
        {
            error = readError;
            return null;
        }

        var x = ReadSingle(bytes, xOffset - minOffset);
        var y = ReadSingle(bytes, yOffset - minOffset);
        var z = ReadSingle(bytes, zOffset - minOffset);

        if (!float.IsFinite(x) || !float.IsFinite(y) || !float.IsFinite(z))
        {
            error = $"Non-finite coordinate sample at 0x{baseAddress:X}.";
            return null;
        }

        return new TelemetryVector3(x, y, z);
    }

    private static float ReadSingle(byte[] bytes, int offset) =>
        BitConverter.ToSingle(bytes, offset);

    private static bool TryParseAddress(string? value, out long address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var token = value.Trim();
        if (token.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            token = token[2..];
        }

        return long.TryParse(token, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address);
    }
}

public sealed class MemoryFacingSource : IFacingSource
{
    private readonly ProcessMemoryReader _reader;
    private readonly ProcessTarget _target;
    private readonly DateTimeOffset _processStartTimeUtc;
    private readonly bool _diagnosticsEnabled;

    public MemoryFacingSource(ProcessMemoryReader reader, ProcessTarget target, DateTimeOffset processStartTimeUtc, bool diagnosticsEnabled)
    {
        _reader = reader;
        _target = target;
        _processStartTimeUtc = processStartTimeUtc;
        _diagnosticsEnabled = diagnosticsEnabled;
    }

    public TelemetryFacingSourceReading Read(TelemetryContextSourceReading? context)
    {
        var sampledAtUtc = DateTimeOffset.UtcNow;
        var leadDocument = ActorFacingBehaviorBackedLeadLoader.TryLoad(null, out var leadError);
        if (leadDocument is null)
        {
            return Invalid(sampledAtUtc, leadError ?? "Unable to load the actor-facing behavior-backed lead.", null, null);
        }

        var leadValidation = ActorFacingBehaviorBackedLeadValidator.Validate(leadDocument, _target.ProcessName, _target.ProcessId, _processStartTimeUtc);
        if (!leadValidation.IsValid)
        {
            return Invalid(sampledAtUtc, leadValidation.Error ?? "Behavior-backed lead validation failed.", leadDocument, null);
        }

        try
        {
            var result = PlayerOrientationReader.ReadLive(_reader, _target, context?.SnapshotDocument, leadDocument);
            var preferred = result.PreferredEstimate;
            var vector = preferred?.Vector;
            if (preferred is null || vector?.X is not double x || vector.Y is not double y || vector.Z is not double z)
            {
                return Invalid(sampledAtUtc, "Live facing read did not yield a preferred estimate.", leadDocument, result);
            }

            var facing = new TelemetryFacingEnvelope(
                Valid: true,
                SourceKind: "behavior-backed-memory-facing",
                YawRadians: preferred.YawRadians,
                YawDegrees: preferred.YawDegrees,
                PitchRadians: preferred.PitchRadians,
                PitchDegrees: preferred.PitchDegrees,
                Forward: new TelemetryVector3(x, y, z),
                SourceAddress: result.SelectedSourceAddress,
                BasisForwardOffset: result.BasisPrimaryForwardOffset,
                BasisDuplicateForwardOffset: result.BasisDuplicateForwardOffset,
                Reason: null,
                Provenance: result.ArtifactFile);

            return new TelemetryFacingSourceReading(
                Available: true,
                Valid: true,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "behavior-backed-memory-facing",
                Reason: null,
                Facing: facing,
                LeadDiagnostics: BuildLeadDiagnostics(leadDocument),
                Discovery: BuildFacingDiscovery(result));
        }
        catch (Exception ex)
        {
            return Invalid(sampledAtUtc, ex.Message, leadDocument, null);
        }
    }

    private TelemetryFacingSourceReading Invalid(
        DateTimeOffset sampledAtUtc,
        string reason,
        ActorFacingBehaviorBackedLeadDocument? leadDocument,
        PlayerOrientationReadResult? result)
    {
        return new TelemetryFacingSourceReading(
            Available: leadDocument is not null,
            Valid: false,
            SampledAtUtc: sampledAtUtc,
            SourceKind: "behavior-backed-memory-facing",
            Reason: reason,
            Facing: new TelemetryFacingEnvelope(
                Valid: false,
                SourceKind: "behavior-backed-memory-facing",
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: null,
                PitchDegrees: null,
                Forward: null,
                SourceAddress: result?.SelectedSourceAddress ?? leadDocument?.SourceAddress,
                BasisForwardOffset: result?.BasisPrimaryForwardOffset ?? leadDocument?.BasisForwardOffset,
                BasisDuplicateForwardOffset: result?.BasisDuplicateForwardOffset ?? leadDocument?.BasisDuplicateForwardOffset,
                Reason: reason,
                Provenance: leadDocument?.SourceFile),
            LeadDiagnostics: leadDocument is null ? null : BuildLeadDiagnostics(leadDocument),
            Discovery: BuildFacingDiscovery(result));
    }

    private TelemetryFacingLeadDiagnostics BuildLeadDiagnostics(ActorFacingBehaviorBackedLeadDocument leadDocument)
    {
        var leadTimestamp = leadDocument.ValidatedAtUtc ?? leadDocument.GeneratedAtUtc;
        var ageSeconds = leadTimestamp.HasValue
            ? Math.Max(0d, (DateTimeOffset.UtcNow - leadTimestamp.Value.ToUniversalTime()).TotalSeconds)
            : (double?)null;

        return new TelemetryFacingLeadDiagnostics(
            Valid: true,
            LeadFile: leadDocument.SourceFile,
            AgeSeconds: ageSeconds,
            SourceAddress: leadDocument.SourceAddress,
            BasisForwardOffset: leadDocument.BasisForwardOffset,
            BasisDuplicateForwardOffset: leadDocument.BasisDuplicateForwardOffset,
            Notes: leadDocument.Notes ?? Array.Empty<string>());
    }

    private object? BuildFacingDiscovery(PlayerOrientationReadResult? result)
    {
        if (!_diagnosticsEnabled || result is null)
        {
            return null;
        }

        return new
        {
            result.ResolutionMode,
            result.SelectedSourceAddress,
            result.BasisPrimaryForwardOffset,
            result.BasisDuplicateForwardOffset,
            result.BasisDuplicateDeltaMagnitude,
            result.BasisDuplicateAgreementStrong,
            Estimates = result.Estimates.Select(static estimate => new
            {
                estimate.Name,
                estimate.YawDegrees,
                estimate.PitchDegrees,
                estimate.Magnitude
            }).ToArray(),
            result.Notes
        };
    }
}

internal static class RepositoryPathLocator
{
    public static string FindRepoRoot(string? startDirectory = null)
    {
        var current = new DirectoryInfo(startDirectory ?? Directory.GetCurrentDirectory());
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return Directory.GetCurrentDirectory();
    }
}

public sealed record ProofCoordAnchorResolveAttempt(
    ProofCoordAnchorDocument? Document,
    string? Error);

public sealed record ProofCoordAnchorDocument(
    string? Mode,
    DateTimeOffset GeneratedAtUtc,
    string? ProcessName,
    int? ProcessId,
    string? CanonicalCoordSourceKind,
    string? MatchSource,
    string? TraceSourceFile,
    string? VerificationMethod,
    bool? TraceMatchesProcess,
    string? TraceTargetAddress,
    string? TraceCandidateAddress,
    string? TraceObjectBaseAddress,
    string? ObjectBaseAddress,
    string? CoordRegionAddress,
    int? CoordXRelativeOffset,
    int? CoordYRelativeOffset,
    int? CoordZRelativeOffset,
    string? SourceObjectAddress,
    int? SourceCoordRelativeOffset,
    ProofCoordAnchorMatch? Match,
    ProofCoordAnchorMatch? TraceMatch,
    ProofCoordAnchorMatch? SourceObjectMatch,
    IReadOnlyList<string>? Notes)
{
    public bool MatchIsValid => Match?.CoordMatchesWithinTolerance == true;
}

public sealed record ProofCoordAnchorMatch(
    bool CoordMatchesWithinTolerance,
    double? DeltaX,
    double? DeltaY,
    double? DeltaZ,
    string? ReferenceSource,
    string? ReferenceCapturedAtUtc,
    double? ReferenceAgeSeconds);
