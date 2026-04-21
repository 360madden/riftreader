namespace RiftReader.Reader.Models;

public sealed record PlayerActorTruthReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ReaderBridgeSourceFile,
    string? TraceSourceFile,
    bool TraceAvailable,
    bool TraceMatchesProcess,
    string CoordBootstrapSource,
    string OrientationResolutionSource,
    PlayerActorCoordReadResult Coordinates,
    PlayerActorOrientationReadResult Orientation,
    PlayerActorTruthBestContainerChain? BestContainerChain,
    PlayerActorTruthRootFamilyCandidate? BestRootFamily,
    PlayerActorTruthRootFamilySummary? RootFamilySummary,
    IReadOnlyList<string> Notes);

public sealed record PlayerActorTruthRootFamilySummary(
    string RegionBase,
    string CanonicalInstanceAddress,
    int CanonicalInstanceObservationCount,
    string RepresentativeAddress,
    int RepresentativeObservationCount,
    int ObservationCount,
    int DistinctAddressCount,
    int StabilitySampleCount,
    int Score);
