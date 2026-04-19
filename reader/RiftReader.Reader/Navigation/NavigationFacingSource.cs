using System.Text.Json;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Facing;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Navigation;

public interface INavigationFacingSource
{
    string SourceName { get; }

    string SourceAddressHex { get; }

    bool TryReadCurrent(out NavigationFacingSample sample, out string? error);
}

public sealed record NavigationFacingSample(
    string SourceName,
    string SourceAddressHex,
    string BasisForwardOffset,
    double YawRadians,
    double YawDegrees,
    bool? CoordValidated,
    bool IntegrityPass,
    IReadOnlyList<string> IntegrityNotes);

public sealed record NavigationFacingSourceCreationResult(
    INavigationFacingSource Source,
    NavigationFacingSample InitialSample);

public sealed record NavigationFacingSummary(
    string SourceName,
    string SourceAddressHex,
    string BasisForwardOffset,
    double ActorYawRadians,
    double ActorYawDegrees,
    double SignedTurnErrorRadians,
    double SignedTurnErrorDegrees,
    bool? CoordValidated,
    bool IntegrityPass,
    IReadOnlyList<string> IntegrityNotes);

public static class NavigationFacingSourceFactory
{
    private const int SourceReadLength = 0xC0;
    private const double CoordMatchTolerance = 0.75d;
    private const string DefaultSourceName = "selected-source-basis-forward-row";
    private const string ActorFacingSampleRelativePath = @"scripts\captures\player-actor-facing.json";
    private const string ActorOrientationCaptureRelativePath = @"scripts\captures\player-actor-orientation.json";
    private const string PassiveAnalysisRelativePath = @"scripts\captures\actor-facing-passive-analysis.json";
    private const int BasisPrimaryForwardOffset = 0x60;
    private const int BasisPrimaryUpOffset = 0x6C;
    private const int BasisPrimaryRightOffset = 0x78;
    private const int BasisDuplicateForwardOffset = 0x94;
    private const int BasisDuplicateUpOffset = 0xA0;
    private const int BasisDuplicateRightOffset = 0xAC;

    public static NavigationFacingSourceCreationResult? TryCreate(
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        string? ownerComponentsFile,
        out string? error)
    {
        ArgumentNullException.ThrowIfNull(reader);

        error = null;
        var addressErrors = new List<string>();
        var selectedSourceAddress = TryResolveSelectedSourceAddress(
            snapshotDocument,
            ownerComponentsFile,
            addressErrors);

        if (!selectedSourceAddress.HasValue)
        {
            error = addressErrors.Count == 0
                ? "Unable to resolve a selected-source address for navigation-facing reads."
                : string.Join(" ", addressErrors);
            return null;
        }

        var source = new LiveMemoryNavigationFacingSource(
            reader,
            selectedSourceAddress.Value,
            snapshotDocument?.Current?.Player?.Coord);

        if (!source.TryReadCurrent(out var initialSample, out error))
        {
            return null;
        }

        return new NavigationFacingSourceCreationResult(source, initialSample);
    }

    private static long? TryResolveSelectedSourceAddress(
        ReaderBridgeSnapshotDocument? snapshotDocument,
        string? ownerComponentsFile,
        List<string> errors)
    {
        if (TryResolveFromOwnerComponents(snapshotDocument, ownerComponentsFile, out var ownerComponentAddress, out var ownerComponentError))
        {
            return ownerComponentAddress;
        }

        if (!string.IsNullOrWhiteSpace(ownerComponentError))
        {
            errors.Add(ownerComponentError!);
        }

        if (TryResolveFromJsonArtifact(ResolveRepoFile(ActorFacingSampleRelativePath), out var actorFacingAddress))
        {
            return actorFacingAddress;
        }

        if (TryResolveFromJsonArtifact(ResolveRepoFile(ActorOrientationCaptureRelativePath), out var actorOrientationAddress))
        {
            return actorOrientationAddress;
        }

        if (TryResolveFromJsonArtifact(ResolveRepoFile(PassiveAnalysisRelativePath), out var passiveAnalysisAddress))
        {
            return passiveAnalysisAddress;
        }

        return null;
    }

    private static bool TryResolveFromOwnerComponents(
        ReaderBridgeSnapshotDocument? snapshotDocument,
        string? ownerComponentsFile,
        out long address,
        out string? error)
    {
        address = 0;
        error = null;

        var artifactDocument = PlayerOwnerComponentArtifactLoader.TryLoad(ownerComponentsFile, out error);
        if (artifactDocument is null)
        {
            return false;
        }

        var orientationResult = PlayerOrientationReader.Read(artifactDocument, snapshotDocument);
        var selectedSourceAddress = !string.IsNullOrWhiteSpace(orientationResult.SelectedSourceAddress)
            ? orientationResult.SelectedSourceAddress
            : orientationResult.SelectedEntryAddress;

        if (string.IsNullOrWhiteSpace(selectedSourceAddress) ||
            !PlayerCurrentAnchorCacheStore.TryParseAddress(selectedSourceAddress, out address))
        {
            error = $"Unable to parse the selected-source address from owner-components artifact '{artifactDocument.SourceFile}'.";
            return false;
        }

        error = null;
        return true;
    }

    private static bool TryResolveFromJsonArtifact(string? filePath, out long address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(filePath));
            var root = document.RootElement;

            var addressText =
                TryReadNestedString(root, "ActorFacingSample", "SourceAddress") ??
                TryReadNestedString(root, "ReaderOrientation", "SelectedSourceAddress") ??
                TryReadNestedString(root, "CurrentOrientation", "SelectedSourceAddress");

            return !string.IsNullOrWhiteSpace(addressText) &&
                   PlayerCurrentAnchorCacheStore.TryParseAddress(addressText, out address);
        }
        catch
        {
            return false;
        }
    }

    private static string? ResolveRepoFile(string relativePath)
    {
        var repoRoot = NavigationPathResolver.TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, relativePath);
    }

    private static string? TryReadNestedString(JsonElement element, params string[] pathSegments)
    {
        var current = element;
        foreach (var pathSegment in pathSegments)
        {
            if (!TryGetPropertyCaseInsensitive(current, pathSegment, out current))
            {
                return null;
            }
        }

        return current.ValueKind == JsonValueKind.String
            ? current.GetString()?.Trim()
            : null;
    }

    private static bool TryGetPropertyCaseInsensitive(JsonElement element, string propertyName, out JsonElement value)
    {
        foreach (var property in element.EnumerateObject())
        {
            if (string.Equals(property.Name, propertyName, StringComparison.OrdinalIgnoreCase))
            {
                value = property.Value;
                return true;
            }
        }

        value = default;
        return false;
    }

    private sealed class LiveMemoryNavigationFacingSource(
        ProcessMemoryReader reader,
        long baseAddress,
        ValidatorCoordinateSnapshot? expectedCoord) : INavigationFacingSource
    {
        public string SourceName => DefaultSourceName;

        public string SourceAddressHex => $"0x{baseAddress:X}";

        public bool TryReadCurrent(out NavigationFacingSample sample, out string? error)
        {
            sample = default!;

            if (!reader.TryReadBytes(new nint(baseAddress), SourceReadLength, out var bytes, out _) ||
                bytes.Length < SourceReadLength)
            {
                error = $"Unable to read the selected-source block at {SourceAddressHex} for navigation-facing.";
                return false;
            }

            var basis60 = TryReadBasis(bytes, BasisPrimaryForwardOffset, BasisPrimaryUpOffset, BasisPrimaryRightOffset);
            var basis94 = TryReadBasis(bytes, BasisDuplicateForwardOffset, BasisDuplicateUpOffset, BasisDuplicateRightOffset);
            var preferredBasis = basis60 ?? basis94;
            if (preferredBasis is null)
            {
                error = $"Unable to read a complete facing basis from the selected-source block at {SourceAddressHex}.";
                return false;
            }

            var coord48 = TryReadVector(bytes, 0x48);
            var coord88 = TryReadVector(bytes, 0x88);
            var coordValidated = ResolveCoordValidation(coord48, coord88, expectedCoord);
            var duplicateBasisMaximumRowDelta = ComputeDuplicateBasisMaximumRowDelta(basis60, basis94);
            var metrics = new ActorFacingBasisMetrics(
                Determinant: ComputeDeterminant(preferredBasis),
                ForwardMagnitude: ComputeMagnitude(preferredBasis.Forward),
                UpMagnitude: ComputeMagnitude(preferredBasis.Up),
                RightMagnitude: ComputeMagnitude(preferredBasis.Right),
                ForwardDotUp: ComputeDot(preferredBasis.Forward, preferredBasis.Up),
                ForwardDotRight: ComputeDot(preferredBasis.Forward, preferredBasis.Right),
                UpDotRight: ComputeDot(preferredBasis.Up, preferredBasis.Right),
                DuplicateBasisMaximumRowDelta: duplicateBasisMaximumRowDelta);
            var integrity = ActorFacingAnalyzer.EvaluateIntegrity(metrics);
            var yawRadians = ActorFacingMath.ComputeYawRadians(preferredBasis.Forward.X, preferredBasis.Forward.Z);

            sample = new NavigationFacingSample(
                SourceName: DefaultSourceName,
                SourceAddressHex: SourceAddressHex,
                BasisForwardOffset: preferredBasis.ForwardOffsetHex,
                YawRadians: yawRadians,
                YawDegrees: ActorFacingMath.DegreesFromRadians(yawRadians),
                CoordValidated: coordValidated,
                IntegrityPass: integrity.Pass,
                IntegrityNotes: integrity.Notes);
            error = null;
            return true;
        }

        private static BasisBlock? TryReadBasis(byte[] bytes, int forwardOffset, int upOffset, int rightOffset)
        {
            var forward = TryReadVector(bytes, forwardOffset);
            var up = TryReadVector(bytes, upOffset);
            var right = TryReadVector(bytes, rightOffset);
            return forward is null || up is null || right is null
                ? null
                : new BasisBlock($"0x{forwardOffset:X}", forward.Value, up.Value, right.Value);
        }

        private static Vector3? TryReadVector(byte[] bytes, int offset)
        {
            if (offset < 0 || offset + (sizeof(float) * 3) > bytes.Length)
            {
                return null;
            }

            return new Vector3(
                X: BitConverter.ToSingle(bytes, offset),
                Y: BitConverter.ToSingle(bytes, offset + sizeof(float)),
                Z: BitConverter.ToSingle(bytes, offset + (sizeof(float) * 2)));
        }

        private static bool? ResolveCoordValidation(
            Vector3? coord48,
            Vector3? coord88,
            ValidatorCoordinateSnapshot? expectedCoord)
        {
            if (expectedCoord?.X is null || expectedCoord.Y is null || expectedCoord.Z is null)
            {
                return null;
            }

            return MatchesExpectedCoord(coord48, expectedCoord) ||
                   MatchesExpectedCoord(coord88, expectedCoord);
        }

        private static bool MatchesExpectedCoord(Vector3? candidate, ValidatorCoordinateSnapshot expectedCoord) =>
            candidate.HasValue &&
            Math.Abs(candidate.Value.X - expectedCoord.X!.Value) <= CoordMatchTolerance &&
            Math.Abs(candidate.Value.Y - expectedCoord.Y!.Value) <= CoordMatchTolerance &&
            Math.Abs(candidate.Value.Z - expectedCoord.Z!.Value) <= CoordMatchTolerance;

        private static double ComputeMagnitude(Vector3 value) =>
            Math.Sqrt((value.X * value.X) + (value.Y * value.Y) + (value.Z * value.Z));

        private static double ComputeDot(Vector3 left, Vector3 right) =>
            (left.X * right.X) + (left.Y * right.Y) + (left.Z * right.Z);

        private static double ComputeDeterminant(BasisBlock basis) =>
            (basis.Forward.X * ((basis.Up.Y * basis.Right.Z) - (basis.Up.Z * basis.Right.Y))) -
            (basis.Forward.Y * ((basis.Up.X * basis.Right.Z) - (basis.Up.Z * basis.Right.X))) +
            (basis.Forward.Z * ((basis.Up.X * basis.Right.Y) - (basis.Up.Y * basis.Right.X)));

        private static double? ComputeDuplicateBasisMaximumRowDelta(BasisBlock? primary, BasisBlock? duplicate)
        {
            if (primary is null || duplicate is null)
            {
                return null;
            }

            var forwardDelta = ComputeVectorDeltaMagnitude(primary.Forward, duplicate.Forward);
            var upDelta = ComputeVectorDeltaMagnitude(primary.Up, duplicate.Up);
            var rightDelta = ComputeVectorDeltaMagnitude(primary.Right, duplicate.Right);
            return Math.Max(forwardDelta, Math.Max(upDelta, rightDelta));
        }

        private static double ComputeVectorDeltaMagnitude(Vector3 left, Vector3 right)
        {
            var deltaX = left.X - right.X;
            var deltaY = left.Y - right.Y;
            var deltaZ = left.Z - right.Z;
            return Math.Sqrt((deltaX * deltaX) + (deltaY * deltaY) + (deltaZ * deltaZ));
        }

        private sealed record BasisBlock(
            string ForwardOffsetHex,
            Vector3 Forward,
            Vector3 Up,
            Vector3 Right);

        private readonly record struct Vector3(
            double X,
            double Y,
            double Z);
    }
}
