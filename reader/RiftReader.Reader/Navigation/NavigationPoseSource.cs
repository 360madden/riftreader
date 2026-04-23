using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Models;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Navigation;

public interface INavigationPoseSource
{
    string AnchorSource { get; }

    string AddressHex { get; }

    bool TryReadCurrent(out NavigationPoseSample sample, out string? error);
}

public sealed record NavigationPoseSample(
    string AddressHex,
    double X,
    double Y,
    double Z);

public sealed record NavigationPoseSourceCreationResult(
    INavigationPoseSource Source,
    NavigationPoseSample InitialSample);

internal enum NavigationPoseSourcePolicy
{
    AllowFallback = 0,
    StrictCoordTrace = 1
}

internal sealed record NavigationPoseSourceResolutionStepResult(
    NavigationPoseSourceCreationResult? Result,
    string? Error = null);

public static class NavigationPoseSourceFactory
{
    private const float VerificationTolerance = 0.25f;
    private const int DefaultCoordXOffset = 0;
    private const int DefaultCoordYOffset = 4;
    private const int DefaultCoordZOffset = 8;

    internal static NavigationPoseSourceCreationResult? TryCreate(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        int inspectionRadius,
        NavigationPoseSourcePolicy policy,
        int maxHits,
        out string? error)
    {
        ArgumentNullException.ThrowIfNull(reader);

        return TryCreateWithPolicy(
            policy,
            tryTraceAnchor: () =>
            {
                return TryResolveTraceAnchor(reader, processId, processName, snapshotDocument, out var traceResult)
                    ? new NavigationPoseSourceResolutionStepResult(traceResult)
                    : new NavigationPoseSourceResolutionStepResult(null);
            },
            tryCachedAnchor: () =>
            {
                return TryResolveCachedAnchor(reader, processName, snapshotDocument, out var cachedResult)
                    ? new NavigationPoseSourceResolutionStepResult(cachedResult)
                    : new NavigationPoseSourceResolutionStepResult(null);
            },
            tryReacquiredAnchor: () =>
            {
                if (snapshotDocument?.Current?.Player is null)
                {
                    return new NavigationPoseSourceResolutionStepResult(null);
                }

                return TryResolveReacquiredAnchor(
                    reader,
                    processId,
                    processName,
                    snapshotDocument,
                    inspectionRadius,
                    maxHits,
                    out var reacquiredResult,
                    out var reacquireError)
                    ? new NavigationPoseSourceResolutionStepResult(reacquiredResult)
                    : new NavigationPoseSourceResolutionStepResult(null, reacquireError);
            },
            out error);
    }

    internal static NavigationPoseSourceCreationResult? TryCreateWithPolicy(
        NavigationPoseSourcePolicy policy,
        Func<NavigationPoseSourceResolutionStepResult> tryTraceAnchor,
        Func<NavigationPoseSourceResolutionStepResult> tryCachedAnchor,
        Func<NavigationPoseSourceResolutionStepResult> tryReacquiredAnchor,
        out string? error)
    {
        ArgumentNullException.ThrowIfNull(tryTraceAnchor);
        ArgumentNullException.ThrowIfNull(tryCachedAnchor);
        ArgumentNullException.ThrowIfNull(tryReacquiredAnchor);

        var traceStep = tryTraceAnchor();
        if (traceStep.Result is not null)
        {
            error = null;
            return traceStep.Result;
        }

        if (policy == NavigationPoseSourcePolicy.StrictCoordTrace)
        {
            error = string.IsNullOrWhiteSpace(traceStep.Error)
                ? "Unable to resolve a verified navigation pose anchor from the current-process coord trace. Proof-grade movement requires a validated coord-trace anchor; cached or reacquired anchors are not allowed."
                : $"Unable to resolve a verified navigation pose anchor from the current-process coord trace. {traceStep.Error} Proof-grade movement requires a validated coord-trace anchor; cached or reacquired anchors are not allowed.";
            return null;
        }

        var cachedStep = tryCachedAnchor();
        if (cachedStep.Result is not null)
        {
            error = null;
            return cachedStep.Result;
        }

        var reacquiredStep = tryReacquiredAnchor();
        if (reacquiredStep.Result is not null)
        {
            error = null;
            return reacquiredStep.Result;
        }

        error = string.IsNullOrWhiteSpace(reacquiredStep.Error)
            ? "Unable to resolve a verified navigation pose anchor from the coord trace, player anchor cache, or player-current reacquisition."
            : reacquiredStep.Error;
        return null;
    }

    private static bool TryResolveTraceAnchor(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        out NavigationPoseSourceCreationResult? result)
    {
        result = null;

        var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(null, out _);
        if (traceDocument?.Reader?.ProcessId != processId ||
            !string.Equals(traceDocument.Reader.ProcessName, processName, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var resolvedAnchor = PlayerCoordAnchorReader.TryResolveObjectAnchor(traceDocument);
        if (resolvedAnchor is null)
        {
            return false;
        }

        var source = new DirectMemoryNavigationPoseSource(
            source: "coord-trace-anchor",
            addressHex: $"0x{resolvedAnchor.ObjectBaseAddress:X}",
            reader: reader,
            baseAddress: resolvedAnchor.ObjectBaseAddress,
            coordXOffset: resolvedAnchor.CoordXOffset,
            coordYOffset: resolvedAnchor.CoordYOffset,
            coordZOffset: resolvedAnchor.CoordZOffset);

        if (!source.TryReadCurrent(out var sample, out _) || !IsTrustedSample(sample, snapshotDocument))
        {
            return false;
        }

        result = new NavigationPoseSourceCreationResult(source, sample);
        return true;
    }

    private static bool TryResolveCachedAnchor(
        ProcessMemoryReader reader,
        string processName,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        out NavigationPoseSourceCreationResult? result)
    {
        result = null;

        var anchorCandidates = PlayerCurrentAnchorCacheStore.LoadCandidates(null, out _, out _);
        foreach (var anchorCandidate in anchorCandidates)
        {
            var cachedAnchor = anchorCandidate.Document;
            if (!string.Equals(cachedAnchor.ProcessName, processName, StringComparison.OrdinalIgnoreCase) ||
                !PlayerCurrentAnchorCacheStore.TryParseAddress(cachedAnchor.AddressHex, out var cachedAddress))
            {
                continue;
            }

            var source = new DirectMemoryNavigationPoseSource(
                source: "player-current-cache",
                addressHex: cachedAnchor.AddressHex,
                reader: reader,
                baseAddress: cachedAddress,
                coordXOffset: cachedAnchor.CoordXOffset,
                coordYOffset: cachedAnchor.CoordYOffset,
                coordZOffset: cachedAnchor.CoordZOffset);

            if (!source.TryReadCurrent(out var sample, out _) || !IsTrustedSample(sample, snapshotDocument))
            {
                continue;
            }

            result = new NavigationPoseSourceCreationResult(source, sample);
            return true;
        }

        return false;
    }

    private static bool TryResolveReacquiredAnchor(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int inspectionRadius,
        int maxHits,
        out NavigationPoseSourceCreationResult? result,
        out string? error)
    {
        result = null;
        error = null;
        string? playerCurrentError = null;

        PlayerCurrentReadResult currentRead;
        try
        {
            currentRead = PlayerCurrentReader.ReadCurrent(
                reader,
                processId,
                processName,
                snapshotDocument,
                inspectionRadius,
                maxHits);
        }
        catch (Exception ex)
        {
            playerCurrentError = ex.Message;

            if (TryResolveCoordOnlyReacquiredAnchor(
                reader,
                processId,
                processName,
                snapshotDocument,
                inspectionRadius,
                maxHits,
                out result,
                out var coordOnlyError))
            {
                return true;
            }

            error = string.IsNullOrWhiteSpace(coordOnlyError)
                ? $"Unable to reacquire a player-current anchor for navigation: {playerCurrentError}"
                : $"Unable to reacquire a player-current anchor for navigation: {playerCurrentError} Coord-only fallback failed: {coordOnlyError}";
            return false;
        }

        var sourceName = "player-current-reacquire";
        long baseAddress;
        var coordXOffset = DefaultCoordXOffset;
        var coordYOffset = DefaultCoordYOffset;
        var coordZOffset = DefaultCoordZOffset;

        if (string.Equals(currentRead.FamilyId, "coord-trace-anchor", StringComparison.OrdinalIgnoreCase))
        {
            var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(null, out _);
            var resolvedAnchor =
                traceDocument?.Reader?.ProcessId == processId &&
                string.Equals(traceDocument.Reader.ProcessName, processName, StringComparison.OrdinalIgnoreCase)
                    ? PlayerCoordAnchorReader.TryResolveObjectAnchor(traceDocument)
                    : null;
            if (resolvedAnchor is null)
            {
                error = "Player-current reacquisition selected the coord-trace anchor, but the live trace offsets could not be reloaded.";
                return false;
            }

            baseAddress = resolvedAnchor.ObjectBaseAddress;
            coordXOffset = resolvedAnchor.CoordXOffset;
            coordYOffset = resolvedAnchor.CoordYOffset;
            coordZOffset = resolvedAnchor.CoordZOffset;
            sourceName = "coord-trace-anchor";
        }
        else if (!PlayerCurrentAnchorCacheStore.TryParseAddress(currentRead.Memory.AddressHex, out baseAddress))
        {
            error = $"Player-current reacquisition did not return a readable base address: '{currentRead.Memory.AddressHex}'.";
            return false;
        }

        var source = new DirectMemoryNavigationPoseSource(
            source: sourceName,
            addressHex: $"0x{baseAddress:X}",
            reader: reader,
            baseAddress: baseAddress,
            coordXOffset: coordXOffset,
            coordYOffset: coordYOffset,
            coordZOffset: coordZOffset);

        if (!source.TryReadCurrent(out var sample, out error) || !IsTrustedSample(sample, snapshotDocument))
        {
            error ??= "Player-current reacquisition did not produce a trusted coordinate sample for navigation.";
            return false;
        }

        result = new NavigationPoseSourceCreationResult(source, sample);
        return true;
    }

    private static bool TryResolveCoordOnlyReacquiredAnchor(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int inspectionRadius,
        int maxHits,
        out NavigationPoseSourceCreationResult? result,
        out string? error)
    {
        result = null;
        error = null;

        PlayerSignatureProbeCapture capture;
        try
        {
            capture = PlayerSignatureProbeCaptureBuilder.CaptureBestFamily(
                reader,
                processId,
                processName,
                snapshotDocument,
                inspectionRadius,
                maxHits,
                label: null,
                outputFile: null,
                preferCeConfirmation: true);
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }

        var verifiedSample = capture.Samples.FirstOrDefault(sample =>
            sample.CoordX.HasValue &&
            sample.CoordY.HasValue &&
            sample.CoordZ.HasValue &&
            snapshotDocument.Current?.Player?.Coord is { X: double expectedX, Y: double expectedY, Z: double expectedZ } &&
            Math.Abs(sample.CoordX.Value - expectedX) <= VerificationTolerance &&
            Math.Abs(sample.CoordY.Value - expectedY) <= VerificationTolerance &&
            Math.Abs(sample.CoordZ.Value - expectedZ) <= VerificationTolerance);

        if (verifiedSample is null)
        {
            error = $"Player-signature coord-only fallback did not return a sample matching the current ReaderBridge coordinates for family '{capture.FamilyId}'.";
            return false;
        }

        if (!PlayerCurrentAnchorCacheStore.TryParseAddress(verifiedSample.AddressHex, out var baseAddress))
        {
            error = $"Player-signature coord-only fallback returned an unreadable base address: '{verifiedSample.AddressHex}'.";
            return false;
        }

        var source = new DirectMemoryNavigationPoseSource(
            source: "player-signature-reacquire",
            addressHex: verifiedSample.AddressHex,
            reader: reader,
            baseAddress: baseAddress,
            coordXOffset: DefaultCoordXOffset,
            coordYOffset: DefaultCoordYOffset,
            coordZOffset: DefaultCoordZOffset);

        if (!source.TryReadCurrent(out var sample, out error) || !IsTrustedSample(sample, snapshotDocument))
        {
            error ??= $"Player-signature coord-only fallback did not produce a trusted coordinate sample for family '{capture.FamilyId}'.";
            return false;
        }

        result = new NavigationPoseSourceCreationResult(source, sample);
        return true;
    }

    private static bool IsTrustedSample(NavigationPoseSample sample, ReaderBridgeSnapshotDocument? snapshotDocument)
    {
        if (snapshotDocument?.Current?.Player?.Coord is not { } coord ||
            !coord.X.HasValue ||
            !coord.Y.HasValue ||
            !coord.Z.HasValue)
        {
            return IsFinite(sample.X) && IsFinite(sample.Y) && IsFinite(sample.Z);
        }

        return Math.Abs(sample.X - coord.X.Value) <= VerificationTolerance &&
               Math.Abs(sample.Y - coord.Y.Value) <= VerificationTolerance &&
               Math.Abs(sample.Z - coord.Z.Value) <= VerificationTolerance;
    }

    private static bool IsFinite(double value) =>
        !double.IsNaN(value) && !double.IsInfinity(value);

    private sealed class DirectMemoryNavigationPoseSource(
        string source,
        string addressHex,
        ProcessMemoryReader reader,
        long baseAddress,
        int coordXOffset,
        int coordYOffset,
        int coordZOffset) : INavigationPoseSource
    {
        public string AnchorSource => source;

        public string AddressHex => addressHex;

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            sample = default!;

            var x = TryReadFloat(baseAddress + coordXOffset);
            var y = TryReadFloat(baseAddress + coordYOffset);
            var z = TryReadFloat(baseAddress + coordZOffset);
            if (!x.HasValue || !y.HasValue || !z.HasValue)
            {
                error = $"Unable to read a full coordinate triplet from navigation anchor '{source}' at {addressHex}.";
                return false;
            }

            sample = new NavigationPoseSample(addressHex, x.Value, y.Value, z.Value);
            error = null;
            return true;
        }

        private float? TryReadFloat(long address)
        {
            if (!reader.TryReadBytes(new nint(address), sizeof(float), out var bytes, out _) || bytes.Length != sizeof(float))
            {
                return null;
            }

            return BitConverter.ToSingle(bytes, 0);
        }
    }
}
