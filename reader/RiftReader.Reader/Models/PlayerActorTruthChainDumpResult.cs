using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public sealed record PlayerActorTruthChainDumpResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ReaderBridgeSourceFile,
    string? TraceSourceFile,
    int WindowLength,
    int PointerWidth,
    int PointerScanMaxHits,
    int SecondHopSeedLimitPerSurface,
    int SecondHopPointerScanMaxHits,
    int StabilitySampleCount,
    int StabilitySampleDelayMilliseconds,
    PlayerActorTruthReadResult Truth,
    string? UnifiedTruthObjectAddress,
    int UnifiedTruthObservationCount,
    PlayerActorTruthBestContainerChain? BestContainerChain,
    PlayerActorTruthRootFamilyCandidate? BestRootFamily,
    PlayerActorTruthRootFamilySummary? RootFamilySummary,
    PlayerActorTruthObjectWindow? CoordObjectWindow,
    PlayerActorTruthObjectWindow? OrientationObjectWindow,
    PlayerActorTruthObjectWindow? OrientationParentWindow,
    PlayerActorTruthObjectWindow? OrientationRootWindow,
    PointerScanResult CoordObjectBackrefs,
    PointerScanResult OrientationObjectBackrefs,
    PointerScanResult OrientationParentBackrefs,
    IReadOnlyList<PlayerActorTruthSlotCorrelation> SlotCorrelations,
    IReadOnlyList<PlayerActorTruthParentContainerCandidate> ParentContainerCandidates,
    IReadOnlyList<PlayerActorTruthRootFamilyCandidate> RootFamilyCandidates,
    IReadOnlyList<PlayerActorTruthChainObservation> StabilityObservations,
    IReadOnlyList<PlayerActorTruthSharedAncestorCandidate> SharedAncestorCandidates,
    IReadOnlyList<string> Notes);

public sealed record PlayerActorTruthObjectWindow(
    string Label,
    string TargetAddress,
    string WindowStart,
    int WindowLength,
    string BytesHex,
    string AsciiPreview,
    string Utf16Preview,
    IReadOnlyList<PlayerActorTruthPointerSlot> PointerSlots);

public sealed record PlayerActorTruthPointerSlot(
    int Offset,
    string OffsetHex,
    string SlotAddress,
    string ValueHex,
    string Classification,
    string? TargetRegionBase);

public sealed record PlayerActorTruthSlotCorrelation(
    string ValueHex,
    string? TargetRegionBase,
    int Score,
    int DistinctSurfaceCount,
    IReadOnlyList<string> Surfaces,
    IReadOnlyList<PlayerActorTruthSlotCorrelationReference> References);

public sealed record PlayerActorTruthSlotCorrelationReference(
    string Surface,
    string OffsetHex,
    string SlotAddress,
    string Classification);

public sealed record PlayerActorTruthParentContainerCandidate(
    string Address,
    string? RegionBase,
    int Score,
    bool IsDirectParent,
    bool IsOrientationRoot,
    int ObservedAsParentCount,
    int ObservedAsRootCount,
    int ParentWindowSlotCount,
    int ParentBackrefCount,
    int ParentSecondHopCount,
    IReadOnlyList<string> Sources,
    string? AsciiPreview,
    string? Utf16Preview);

public sealed record PlayerActorTruthChainObservation(
    int SampleIndex,
    string? UnifiedTruthObjectAddress,
    string? CoordObjectAddress,
    string OrientationObjectAddress,
    string OrientationParentAddress,
    string OrientationRootAddress);

public sealed record PlayerActorTruthBestContainerChain(
    string? UnifiedTruthObjectAddress,
    int UnifiedTruthObservationCount,
    string? ParentAddress,
    int ParentObservationCount,
    string? RootAddress,
    int RootObservationCount,
    int StabilitySampleCount);

public sealed record PlayerActorTruthRootFamilyCandidate(
    string RegionBase,
    int Score,
    int ObservationCount,
    int DistinctAddressCount,
    int StabilitySampleCount,
    string RepresentativeAddress,
    int RepresentativeObservationCount,
    IReadOnlyList<string> MemberAddresses,
    double AverageMatchingBytes,
    int MinimumMatchingBytes,
    int MaximumMatchingBytes,
    string? RepresentativeAsciiPreview);

public sealed record PlayerActorTruthSharedAncestorCandidate(
    string Address,
    string RegionBase,
    int Score,
    int DistinctSurfaceCount,
    IReadOnlyList<string> Surfaces,
    int FirstHopReferenceCount,
    int SecondHopReferenceCount,
    IReadOnlyList<PlayerActorTruthSharedAncestorPath> Paths);

public sealed record PlayerActorTruthSharedAncestorPath(
    string Surface,
    string FirstHopAddress,
    string SecondHopAddress);
