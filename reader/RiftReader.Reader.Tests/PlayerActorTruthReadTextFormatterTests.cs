using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Models;
using Xunit;

namespace RiftReader.Reader.Tests.Formatting;

public sealed class PlayerActorTruthReadTextFormatterTests
{
    [Fact]
    public void Format_IncludesAllProvenanceLinesWhenPresent()
    {
        var containerChain = new PlayerActorTruthBestContainerChain(
            UnifiedTruthObjectAddress: null,
            UnifiedTruthObservationCount: 0,
            ParentAddress: "0x1000",
            ParentObservationCount: 4,
            RootAddress: "0x2000",
            RootObservationCount: 7,
            StabilitySampleCount: 11);

        var rootFamily = new PlayerActorTruthRootFamilyCandidate(
            RegionBase: "0x7ff00000",
            Score: 88,
            ObservationCount: 4,
            DistinctAddressCount: 2,
            StabilitySampleCount: 5,
            RepresentativeAddress: "0x2000",
            RepresentativeObservationCount: 3,
            MemberAddresses: Array.Empty<string>(),
            AverageMatchingBytes: 42,
            MinimumMatchingBytes: 24,
            MaximumMatchingBytes: 128,
            RepresentativeAsciiPreview: null);

        var rootSummary = new PlayerActorTruthRootFamilySummary(
            RegionBase: "0x7ff00000",
            CanonicalInstanceAddress: "0x2000",
            CanonicalInstanceObservationCount: 3,
            RepresentativeAddress: "0x2000",
            RepresentativeObservationCount: 3,
            ObservationCount: 4,
            DistinctAddressCount: 2,
            StabilitySampleCount: 5,
            Score: 88);

        var result = CreateTruthResult(containerChain, rootFamily, rootSummary);
        var formatted = PlayerActorTruthReadTextFormatter.Format(result);

        Assert.Contains("Best chain parent/root:  0x1000 -> 0x2000 (7/11 root obs)", formatted);
        Assert.Contains("Best root family:        0x7ff00000 (4/5, distinct=2)", formatted);
        Assert.Contains("Canonical root instance: 0x2000", formatted);
        Assert.Contains("Root family summary:     rep=0x2000 canonicalObs=3/5", formatted);
        Assert.Contains("Coord object:            0xAABBCC @ 0x48", formatted);
        Assert.Contains("Notes:                   none", formatted);
    }

    [Fact]
    public void Format_WithMinimalInputOmitsProvenanceLines()
    {
        var result = CreateTruthResult();
        var formatted = PlayerActorTruthReadTextFormatter.Format(result);

        Assert.DoesNotContain("Best chain parent/root:", formatted);
        Assert.DoesNotContain("Best root family:", formatted);
        Assert.DoesNotContain("Canonical root instance:", formatted);
        Assert.Contains("Notes:", formatted);
    }

    private static PlayerActorTruthReadResult CreateTruthResult(
        PlayerActorTruthBestContainerChain? containerChain = null,
        PlayerActorTruthRootFamilyCandidate? rootFamily = null,
        PlayerActorTruthRootFamilySummary? summary = null)
    {
        return new PlayerActorTruthReadResult(
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
    }

    private static PlayerActorCoordReadResult CreateCoordResult()
    {
        return new PlayerActorCoordReadResult(
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
    }

    private static PlayerActorOrientationReadResult CreateOrientationResult()
    {
        return new PlayerActorOrientationReadResult(
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
    }
}
