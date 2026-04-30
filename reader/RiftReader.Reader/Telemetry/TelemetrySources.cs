using System.Diagnostics;
using System.Globalization;
using System.Text;
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
    private const double CoordMatchTolerance = 0.25d;
    private static readonly TimeSpan StaleAnchorGraceWindow = TimeSpan.FromSeconds(10);
    private static readonly string[] CheatEngineDebuggerModuleNames =
    [
        "vehdebug-x86_64.dll",
        "vehdebug-i386.dll"
    ];

    private readonly ProcessMemoryReader _reader;
    private readonly int _processId;
    private readonly string _processName;
    private readonly string _proofCoordAnchorScript;
    private readonly string? _playerCoordTraceFile;
    private readonly string? _proofAnchorCacheFile;
    private readonly TimeSpan _revalidationInterval;
    private readonly TimeSpan _maxAnchorAge;
    private readonly ITelemetryLogger _logger;
    private readonly bool _diagnosticsEnabled;
    private readonly object _refreshSync = new();

    private ProofCoordAnchorDocument? _anchor;
    private DateTimeOffset? _lastResolveAttemptUtc;
    private string? _lastResolveError;
    private bool _cacheLoadAttempted;
    private Task<ProofCoordAnchorRefreshResult>? _refreshTask;

    public MemoryCoordSource(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string proofCoordAnchorScript,
        string? playerCoordTraceFile,
        string? proofAnchorCacheFile,
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
        _proofAnchorCacheFile = string.IsNullOrWhiteSpace(proofAnchorCacheFile)
            ? null
            : Path.GetFullPath(proofAnchorCacheFile);
        _revalidationInterval = revalidationInterval;
        _maxAnchorAge = maxAnchorAge;
        _logger = logger;
        _diagnosticsEnabled = diagnosticsEnabled;
    }

    public TelemetryPositionSourceReading Read(TelemetryContextSourceReading? context)
    {
        var sampledAtUtc = DateTimeOffset.UtcNow;
        TryLoadCachedAnchorIfNeeded(sampledAtUtc);
        ConsumeRefreshResultIfReady();
        StartRefreshIfNeeded(sampledAtUtc);

        var anchor = _anchor;
        var refreshInFlight = IsRefreshInFlight();
        if (anchor is null)
        {
            return new TelemetryPositionSourceReading(
                Available: false,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: refreshInFlight
                    ? "Proof coord anchor refresh is in progress."
                    : _lastResolveError ?? "Proof coord anchor has not been established.",
                Position: null,
                ProofAnchor: null,
                CoordMismatch: null,
                Discovery: null);
        }

        var anchorAge = sampledAtUtc - anchor.GeneratedAtUtc;
        var anchorAgeSeconds = Math.Max(0d, anchorAge.TotalSeconds);
        var staleGraceActive =
            refreshInFlight &&
            anchorAge > _maxAnchorAge &&
            anchorAge <= (_maxAnchorAge + StaleAnchorGraceWindow);

        if (!TryParseAddress(anchor.CoordRegionAddress, out var coordRegionAddress))
        {
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: $"Invalid coord region address '{anchor.CoordRegionAddress ?? "<null>"}'.",
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(anchor, anchorAgeSeconds, staleGraceActive),
                CoordMismatch: BuildCoordMismatch(anchor.Match),
                Discovery: BuildDiscovery(anchor));
        }

        var sample = TryReadVector3(coordRegionAddress, anchor.CoordXRelativeOffset ?? 0, anchor.CoordYRelativeOffset ?? 4, anchor.CoordZRelativeOffset ?? 8, out var readError);
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
                ProofAnchor: BuildProofAnchorDiagnostics(anchor, anchorAgeSeconds, staleGraceActive),
                CoordMismatch: BuildCoordMismatch(anchor.Match),
                Discovery: BuildDiscovery(anchor));
        }

        var liveCoordMismatch = BuildCoordMismatch(sample, context?.AddonPosition?.Coord);
        if (liveCoordMismatch is not null && !CoordMatchesWithinTolerance(liveCoordMismatch))
        {
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: "Proof coord anchor memory sample does not match current ReaderBridge coordinates.",
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(anchor, anchorAgeSeconds, staleGraceActive),
                CoordMismatch: liveCoordMismatch,
                Discovery: BuildDiscovery(anchor));
        }

        var acceptedStaleAnchor =
            anchorAge > _maxAnchorAge &&
            !staleGraceActive &&
            liveCoordMismatch is not null &&
            CoordMatchesWithinTolerance(liveCoordMismatch);
        if (anchorAge > _maxAnchorAge && !staleGraceActive && !acceptedStaleAnchor)
        {
            return new TelemetryPositionSourceReading(
                Available: true,
                Valid: false,
                SampledAtUtc: sampledAtUtc,
                SourceKind: "proof-coord-anchor",
                Reason: $"Proof coord anchor validation is stale ({anchorAgeSeconds:0.0}s old).",
                Position: null,
                ProofAnchor: BuildProofAnchorDiagnostics(anchor, anchorAgeSeconds),
                CoordMismatch: liveCoordMismatch ?? BuildCoordMismatch(anchor.Match),
                Discovery: BuildDiscovery(anchor));
        }

        var position = new TelemetryPositionValue(
            Valid: true,
            SourceKind: "validated-memory-coords",
            SampledAtUtc: sampledAtUtc,
            Coord: sample,
            Zone: context?.Zone,
            LocationName: context?.LocationName,
            Address: anchor.CoordRegionAddress,
            Reason: null,
            Provenance: anchor.CanonicalCoordSourceKind);

        return new TelemetryPositionSourceReading(
            Available: true,
            Valid: true,
            SampledAtUtc: sampledAtUtc,
            SourceKind: "proof-coord-anchor",
            Reason: null,
            Position: position,
            ProofAnchor: BuildProofAnchorDiagnostics(
                anchor,
                anchorAgeSeconds,
                staleGraceActive,
                acceptedStaleAnchor
                    ? "Accepted stale proof coord anchor for this sample because current memory coordinates match ReaderBridge."
                    : null),
            CoordMismatch: liveCoordMismatch ?? BuildCoordMismatch(anchor.Match),
            Discovery: BuildDiscovery(anchor));
    }

    private void TryLoadCachedAnchorIfNeeded(DateTimeOffset nowUtc)
    {
        if (_cacheLoadAttempted || _anchor is not null)
        {
            return;
        }

        _cacheLoadAttempted = true;
        if (string.IsNullOrWhiteSpace(_proofAnchorCacheFile) || !File.Exists(_proofAnchorCacheFile))
        {
            return;
        }

        try
        {
            var json = File.ReadAllText(_proofAnchorCacheFile);
            var document = JsonSerializer.Deserialize<ProofCoordAnchorDocument>(json, TelemetryJson.SerializerOptions);
            if (document is null || !document.MatchIsValid)
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(document.ProcessName) &&
                !string.Equals(document.ProcessName, _processName, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            if (document.ProcessId.HasValue && document.ProcessId.Value != _processId)
            {
                return;
            }

            _anchor = document;
            _lastResolveAttemptUtc = nowUtc;
            _lastResolveError = null;
            var age = nowUtc - document.GeneratedAtUtc;

            _logger.LogTransition(
                "source.coord",
                $"coord-anchor-cache:{document.CanonicalCoordSourceKind}:{document.CoordRegionAddress}",
                "Loaded cached proof coord anchor.",
                new
                {
                    document.CanonicalCoordSourceKind,
                    document.MatchSource,
                    document.CoordRegionAddress,
                    CacheFile = _proofAnchorCacheFile,
                    AgeSeconds = age.TotalSeconds
                },
                discovery: _diagnosticsEnabled);
        }
        catch (Exception ex)
        {
            _lastResolveError = $"Unable to load cached proof coord anchor '{_proofAnchorCacheFile}': {ex.Message}";
        }
    }

    private void StartRefreshIfNeeded(DateTimeOffset nowUtc)
    {
        lock (_refreshSync)
        {
            if (_refreshTask is not null)
            {
                return;
            }

            var needsResolve =
                _anchor is null ||
                !_anchor.MatchIsValid ||
                !_lastResolveAttemptUtc.HasValue ||
                (nowUtc - _lastResolveAttemptUtc.Value) >= _revalidationInterval;

            if (!needsResolve)
            {
                return;
            }

            _lastResolveAttemptUtc = nowUtc;
            _refreshTask = Task.Run(ResolveAnchorAsync);
        }
    }

    private void ConsumeRefreshResultIfReady()
    {
        Task<ProofCoordAnchorRefreshResult>? completedTask;
        lock (_refreshSync)
        {
            if (_refreshTask is null || !_refreshTask.IsCompleted)
            {
                return;
            }

            completedTask = _refreshTask;
            _refreshTask = null;
        }

        ProofCoordAnchorRefreshResult refresh;
        try
        {
            refresh = completedTask!.GetAwaiter().GetResult();
        }
        catch (Exception ex)
        {
            _lastResolveError = $"Proof coord anchor refresh task failed: {ex.Message}";
            _logger.LogTransition(
                "validation.mismatch",
                $"coord-anchor-error:{_lastResolveError}",
                "Proof coord anchor validation failed.",
                new
                {
                    Error = _lastResolveError
                },
                discovery: _diagnosticsEnabled);

            return;
        }

        if (refresh.Document is not null && refresh.Document.MatchIsValid)
        {
            _anchor = refresh.Document;
            _lastResolveError = null;
            PersistAnchorCache(refresh.Document);
            _logger.LogTransition(
                "source.coord",
                $"coord-anchor:{refresh.Document.CanonicalCoordSourceKind}:{refresh.Document.CoordRegionAddress}",
                refresh.UsedFullRefresh
                    ? "Refreshed proof coord anchor."
                    : "Validated proof coord anchor.",
                new
                {
                    refresh.Document.CanonicalCoordSourceKind,
                    refresh.Document.MatchSource,
                    refresh.Document.CoordRegionAddress
                },
                discovery: _diagnosticsEnabled);

            return;
        }

        if (!string.IsNullOrWhiteSpace(refresh.Error))
        {
            _lastResolveError = refresh.Error;
            _logger.LogTransition(
                "validation.mismatch",
                $"coord-anchor-error:{refresh.Error}",
                "Proof coord anchor validation failed.",
                new
                {
                    Error = refresh.Error,
                    QuickMatch = refresh.QuickDocument?.Match,
                    FullMatch = refresh.FullDocument?.Match
                },
                discovery: _diagnosticsEnabled);
        }
    }

    private ProofCoordAnchorRefreshResult ResolveAnchorAsync()
    {
        var quick = TryResolve(skipRefresh: true);
        if (quick.Document is not null && quick.Document.MatchIsValid)
        {
            return new ProofCoordAnchorRefreshResult(
                Document: quick.Document,
                Error: null,
                UsedFullRefresh: false,
                QuickDocument: quick.Document,
                FullDocument: null);
        }

        if (TryDetectManualCeDebuggerSession(out var debuggerModuleName))
        {
            return new ProofCoordAnchorRefreshResult(
                Document: null,
                Error: $"Full proof coord anchor refresh was skipped because the target process already has Cheat Engine debugger module '{debuggerModuleName}' loaded. Stop the manual CE debugger session or restart telemetry with a fresh primed proof cache.",
                UsedFullRefresh: false,
                QuickDocument: quick.Document,
                FullDocument: null);
        }

        var full = TryResolve(skipRefresh: false);
        return new ProofCoordAnchorRefreshResult(
            Document: full.Document is not null && full.Document.MatchIsValid ? full.Document : null,
            Error: full.Error ?? quick.Error,
            UsedFullRefresh: true,
            QuickDocument: quick.Document,
            FullDocument: full.Document);
    }

    private bool IsRefreshInFlight()
    {
        lock (_refreshSync)
        {
            return _refreshTask is not null;
        }
    }

    private void PersistAnchorCache(ProofCoordAnchorDocument document)
    {
        if (string.IsNullOrWhiteSpace(_proofAnchorCacheFile) || !document.MatchIsValid)
        {
            return;
        }

        try
        {
            var directory = Path.GetDirectoryName(_proofAnchorCacheFile);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var tempFile = _proofAnchorCacheFile + ".tmp";
            var json = JsonSerializer.Serialize(document, TelemetryJson.SerializerOptions);
            File.WriteAllText(tempFile, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            File.Move(tempFile, _proofAnchorCacheFile, overwrite: true);
        }
        catch (Exception ex)
        {
            _logger.LogEvent(
                "source.coord",
                "Unable to persist proof coord anchor cache.",
                new
                {
                    CacheFile = _proofAnchorCacheFile,
                    ex.Message
                },
                discovery: _diagnosticsEnabled);
        }
    }

    private bool TryDetectManualCeDebuggerSession(out string? debuggerModuleName)
    {
        debuggerModuleName = null;

        try
        {
            using var process = Process.GetProcessById(_processId);
            foreach (ProcessModule module in process.Modules)
            {
                if (CheatEngineDebuggerModuleNames.Any(
                    expectedName => string.Equals(module.ModuleName, expectedName, StringComparison.OrdinalIgnoreCase)))
                {
                    debuggerModuleName = module.ModuleName;
                    return true;
                }
            }
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception or NotSupportedException)
        {
            if (_diagnosticsEnabled)
            {
                _logger.LogEvent(
                    "source.coord",
                    "Unable to inspect target modules before telemetry proof refresh.",
                    new
                    {
                        ProcessId = _processId,
                        ProcessName = _processName,
                        ex.Message
                    },
                    discovery: true);
            }
        }

        return false;
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

    private TelemetryProofAnchorDiagnostics BuildProofAnchorDiagnostics(
        ProofCoordAnchorDocument anchor,
        double ageSeconds,
        bool staleGraceActive = false,
        string? additionalNote = null)
    {
        IReadOnlyList<string> notes = anchor.Notes ?? Array.Empty<string>();
        if (staleGraceActive)
        {
            notes = notes
                .Concat(["Telemetry host is temporarily using a stale proof coord anchor while background refresh is in progress."])
                .ToArray();
        }

        if (!string.IsNullOrWhiteSpace(additionalNote))
        {
            notes = notes
                .Concat([additionalNote])
                .ToArray();
        }

        return new TelemetryProofAnchorDiagnostics(
            Valid: anchor.MatchIsValid,
            SourceKind: anchor.CanonicalCoordSourceKind,
            MatchSource: anchor.MatchSource,
            TraceSourceFile: anchor.TraceSourceFile,
            CoordRegionAddress: anchor.CoordRegionAddress,
            AgeSeconds: Math.Max(0d, ageSeconds),
            Notes: notes);
    }

    private static TelemetryDeltaDiagnostics? BuildCoordMismatch(ProofCoordAnchorMatch? match) =>
        match is null
            ? null
            : new TelemetryDeltaDiagnostics(match.DeltaX, match.DeltaY, match.DeltaZ);

    private static TelemetryDeltaDiagnostics? BuildCoordMismatch(TelemetryVector3? sample, TelemetryVector3? reference) =>
        sample is null || reference is null
            ? null
            : new TelemetryDeltaDiagnostics(
                sample.X - reference.X,
                sample.Y - reference.Y,
                sample.Z - reference.Z);

    private static bool CoordMatchesWithinTolerance(TelemetryDeltaDiagnostics mismatch) =>
        Math.Abs(mismatch.Dx ?? double.PositiveInfinity) <= CoordMatchTolerance &&
        Math.Abs(mismatch.Dy ?? double.PositiveInfinity) <= CoordMatchTolerance &&
        Math.Abs(mismatch.Dz ?? double.PositiveInfinity) <= CoordMatchTolerance;

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

public sealed record ProofCoordAnchorRefreshResult(
    ProofCoordAnchorDocument? Document,
    string? Error,
    bool UsedFullRefresh,
    ProofCoordAnchorDocument? QuickDocument,
    ProofCoordAnchorDocument? FullDocument);

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
