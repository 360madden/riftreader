using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Models;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Tests;

internal static class PlayerActorTestData
{
    public static PlayerActorTruthBestContainerChain CreateContainerChain(
        string? parentAddress = "0x1000",
        int parentObservationCount = 4,
        string? rootAddress = "0x2000",
        int rootObservationCount = 7,
        int stabilitySampleCount = 11) =>
        new(
            UnifiedTruthObjectAddress: null,
            UnifiedTruthObservationCount: 0,
            ParentAddress: parentAddress,
            ParentObservationCount: parentObservationCount,
            RootAddress: rootAddress,
            RootObservationCount: rootObservationCount,
            StabilitySampleCount: stabilitySampleCount);

    public static PlayerActorTruthRootFamilyCandidate CreateRootFamilyCandidate(
        string regionBase = "0x7ff00000",
        string representativeAddress = "0x2000",
        int score = 88,
        int observationCount = 4,
        int distinctAddressCount = 2,
        int stabilitySampleCount = 5,
        int representativeObservationCount = 3,
        IReadOnlyList<string>? memberAddresses = null) =>
        new(
            RegionBase: regionBase,
            Score: score,
            ObservationCount: observationCount,
            DistinctAddressCount: distinctAddressCount,
            StabilitySampleCount: stabilitySampleCount,
            RepresentativeAddress: representativeAddress,
            RepresentativeObservationCount: representativeObservationCount,
            MemberAddresses: memberAddresses ?? ["0x2000", "0x3000"],
            AverageMatchingBytes: 42,
            MinimumMatchingBytes: 24,
            MaximumMatchingBytes: 128,
            RepresentativeAsciiPreview: null);

    public static PlayerActorTruthRootFamilySummary CreateRootFamilySummary(
        string regionBase = "0x7ff00000",
        string canonicalInstanceAddress = "0x2000",
        int canonicalInstanceObservationCount = 3,
        string representativeAddress = "0x2000",
        int representativeObservationCount = 3,
        int observationCount = 4,
        int distinctAddressCount = 2,
        int stabilitySampleCount = 5,
        int score = 88) =>
        new(
            RegionBase: regionBase,
            CanonicalInstanceAddress: canonicalInstanceAddress,
            CanonicalInstanceObservationCount: canonicalInstanceObservationCount,
            RepresentativeAddress: representativeAddress,
            RepresentativeObservationCount: representativeObservationCount,
            ObservationCount: observationCount,
            DistinctAddressCount: distinctAddressCount,
            StabilitySampleCount: stabilitySampleCount,
            Score: score);

    public static IReadOnlyList<PlayerActorTruthChainObservation> CreateObservations(params string[] rootAddresses) =>
        rootAddresses
            .Select((rootAddress, index) => new PlayerActorTruthChainObservation(
                SampleIndex: index + 1,
                UnifiedTruthObjectAddress: null,
                CoordObjectAddress: "0xAABBCC",
                OrientationObjectAddress: "0xBEEF",
                OrientationParentAddress: "0x1234",
                OrientationRootAddress: rootAddress))
            .ToArray();

    public static PlayerActorCoordReadResult CreateCoordResult() =>
        new(
            Mode: "player-actor-coords",
            ProcessId: 1337,
            ProcessName: "rift_x64",
            ReaderBridgeSourceFile: "reader-bridge.json",
            TraceSourceFile: "coord-trace.json",
            TraceAvailable: true,
            TraceMatchesProcess: true,
            ResolutionSource: "coord-trace-anchor",
            AnchorProvenance: "coord-trace-anchor",
            FamilyId: "trace-family",
            FamilyNotes: "trace-backed actor coordinates",
            Signature: "trace-anchor@coord",
            SelectionSource: "coord-trace-anchor",
            ConfirmationFile: "confirmation.json",
            CeConfirmedSampleCount: 1,
            BaseRegister: "r8",
            BaseRegisterValue: "0x7f00",
            ObjectBaseAddress: "0xAABBCC",
            CoordBaseRelativeOffset: 72,
            CoordXRelativeOffset: 76,
            CoordYRelativeOffset: 80,
            CoordZRelativeOffset: 84,
            LevelRelativeOffset: -144,
            HealthRelativeOffset: -136,
            ModuleName: "rift_x64.exe",
            ModuleOffset: "0x200000",
            InstructionSymbol: "movss xmm0,[rsi+0x15C]",
            Instruction: "movss",
            Pattern: "AA 55",
            Memory: new PlayerCurrentReadSample(
                AddressHex: "0xAABBCC",
                Level: 42,
                Health: 32000,
                Name: "Player",
                Location: "Eredon",
                CoordX: 10.25f,
                CoordY: 20.75f,
                CoordZ: 30.125f),
            Expected: new PlayerCurrentReadExpected(
                Name: "Player",
                Location: "Eredon",
                Level: 42,
                Health: 32000,
                HealthMax: 35000,
                CoordX: 10.25,
                CoordY: 20.75,
                CoordZ: 30.125),
            Match: new PlayerCurrentReadMatch(
                LevelMatches: true,
                HealthMatches: true,
                CoordMatchesWithinTolerance: true,
                DeltaX: 0f,
                DeltaY: 0f,
                DeltaZ: 0f),
            ModulePattern: null,
            BestContainerChain: null,
            BestRootFamily: null,
            RootFamilySummary: null,
            Notes: Array.Empty<string>());

    public static PlayerActorOrientationReadResult CreateOrientationResult() =>
        new(
            Mode: "player-actor-orientation",
            ProcessId: 1337,
            ProcessName: "rift_x64",
            ReaderBridgeSourceFile: "reader-bridge.json",
            TraceSourceFile: null,
            TraceAvailable: false,
            TraceMatchesProcess: false,
            CoordBootstrapSource: "trace-derived-player-coords",
            ResolutionSource: "pointer-hop-canonical-d4",
            PlayerName: "Player",
            PlayerCoord: new ValidatorCoordinateSnapshot(10.25, 20.75, 30.125),
            SelectedAddress: "0xBEEF",
            ParentAddress: "0x1234",
            ParentFamilyId: "orientation-family",
            ParentScore: 77,
            RootAddress: "0x2000",
            RootSource: "candidate-root",
            HopDepth: 1,
            PointerOffset: "0x10",
            BasisPrimaryForwardOffset: "0xD4",
            Score: 99,
            RawScore: 95,
            LedgerPenalty: 1,
            LedgerRejectionReason: null,
            LedgerStableNonresponsiveCount: 1,
            LedgerResponsiveCount: 2,
            LedgerLatestGeneratedAtUtc: null,
            CoordSourceObjectAddress: "0xAABBCC",
            CoordSourceRegister: "r8",
            CoordSourceRelativeOffset: 72,
            Basis: new PlayerOrientationBasisCandidate(
                Name: "basis",
                Forward: new ValidatorCoordinateSnapshot(1, 0, 0),
                Up: new ValidatorCoordinateSnapshot(0, 1, 0),
                Right: new ValidatorCoordinateSnapshot(0, 0, 1),
                Determinant: 1,
                IsOrthonormal: true,
                ForwardDotUp: 0,
                ForwardDotRight: 0,
                UpDotRight: 0),
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "estimate",
                Vector: new ValidatorCoordinateSnapshot(1, 0, 0),
                YawRadians: 0.123,
                YawDegrees: 7.055,
                PitchRadians: 0.045,
                PitchDegrees: 2.578,
                Magnitude: 1.0),
            CandidateCount: 3,
            PointerHopCandidateCount: 1,
            Diagnostics: new PlayerOrientationProbeDiagnostics(
                CoordHitCount: 12,
                LocalWindowProbeCount: 3,
                LocalWindowReadFailures: 0,
                LocalCoordMismatchCount: 0,
                SeedProbeCount: 2,
                SeedProbeReadFailures: 0,
                SeedCoordMatchCount: 2,
                PointerRootCount: 1,
                PointerRootReadFailures: 0,
                PointerSlotCount: 8,
                UniqueChildPointerCount: 4,
                ChildReadFailures: 0,
                SecondHopRootCount: 0,
                RejectedNonOrthonormalBasisCount: 0,
                RejectedLowComponentDiversityCount: 0,
                RejectedLowHorizontalMagnitudeCount: 0),
            Notes: Array.Empty<string>());

    public static PlayerActorTruthReadResult CreateTruthResult(
        PlayerActorTruthBestContainerChain? containerChain = null,
        PlayerActorTruthRootFamilyCandidate? rootFamily = null,
        PlayerActorTruthRootFamilySummary? summary = null) =>
        new(
            Mode: "player-actor-truth",
            ProcessId: 1337,
            ProcessName: "rift_x64",
            ReaderBridgeSourceFile: "reader-bridge.json",
            TraceSourceFile: "coord-trace.json",
            TraceAvailable: true,
            TraceMatchesProcess: true,
            CoordBootstrapSource: "trace-derived-player-coords",
            OrientationResolutionSource: "pointer-hop-canonical-d4",
            Coordinates: CreateCoordResult(),
            Orientation: CreateOrientationResult(),
            BestContainerChain: containerChain,
            BestRootFamily: rootFamily,
            RootFamilySummary: summary,
            Notes: Array.Empty<string>());

    public static PointerScanResult CreateEmptyPointerScanResult(string pointerTarget = "0xAABBCC") =>
        new(
            Mode: "pointer-scan",
            ProcessId: 1337,
            ProcessName: "rift_x64",
            PointerTarget: pointerTarget,
            PointerWidth: 8,
            ContextBytes: 128,
            MaxHits: 12,
            HitCount: 0,
            Hits: Array.Empty<PointerScanHit>());

    public static PlayerActorTruthChainDumpResult CreateChainDumpResult(
        PlayerActorTruthBestContainerChain? containerChain = null,
        PlayerActorTruthRootFamilyCandidate? rootFamily = null,
        PlayerActorTruthRootFamilySummary? summary = null,
        IReadOnlyList<PlayerActorTruthChainObservation>? observations = null)
    {
        var resolvedContainerChain = containerChain ?? CreateContainerChain();
        var resolvedRootFamily = rootFamily ?? CreateRootFamilyCandidate();
        var resolvedSummary = summary ?? CreateRootFamilySummary();
        var resolvedObservations = observations ?? CreateObservations("0x2000", "0x2000", "0x3000");

        return new PlayerActorTruthChainDumpResult(
            Mode: "player-actor-truth-chain-dump",
            ProcessId: 1337,
            ProcessName: "rift_x64",
            ReaderBridgeSourceFile: "reader-bridge.json",
            TraceSourceFile: "coord-trace.json",
            WindowLength: 128,
            PointerWidth: 8,
            PointerScanMaxHits: 12,
            SecondHopSeedLimitPerSurface: 2,
            SecondHopPointerScanMaxHits: 6,
            StabilitySampleCount: 5,
            StabilitySampleDelayMilliseconds: 250,
            Truth: CreateTruthResult(resolvedContainerChain, resolvedRootFamily, resolvedSummary),
            UnifiedTruthObjectAddress: "0xAABBCC",
            UnifiedTruthObservationCount: 2,
            BestContainerChain: resolvedContainerChain,
            BestRootFamily: resolvedRootFamily,
            RootFamilySummary: resolvedSummary,
            CoordObjectWindow: null,
            OrientationObjectWindow: null,
            OrientationParentWindow: null,
            OrientationRootWindow: null,
            CoordObjectBackrefs: CreateEmptyPointerScanResult("0xAABBCC"),
            OrientationObjectBackrefs: CreateEmptyPointerScanResult("0xBEEF"),
            OrientationParentBackrefs: CreateEmptyPointerScanResult("0x1234"),
            SlotCorrelations: Array.Empty<PlayerActorTruthSlotCorrelation>(),
            ParentContainerCandidates: Array.Empty<PlayerActorTruthParentContainerCandidate>(),
            RootFamilyCandidates: [resolvedRootFamily],
            StabilityObservations: resolvedObservations,
            SharedAncestorCandidates: Array.Empty<PlayerActorTruthSharedAncestorCandidate>(),
            Notes: Array.Empty<string>());
    }
}
