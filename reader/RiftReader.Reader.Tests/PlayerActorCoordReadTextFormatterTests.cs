using RiftReader.Reader.Formatting;
using RiftReader.Reader.Models;
using RiftReader.Reader.Scanning;
using Xunit;

namespace RiftReader.Reader.Tests.Formatting;

public sealed class PlayerActorCoordReadTextFormatterTests
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

        var result = CreateCoordResult(containerChain, rootFamily, rootSummary);
        var formatted = PlayerActorCoordReadTextFormatter.Format(result);

        Assert.Contains("Best chain parent:       0x1000", formatted);
        Assert.Contains("Best chain root:         0x2000", formatted);
        Assert.Contains("Chain observations:      4/11 parent, 7/11 root", formatted);
        Assert.Contains("Best root family:        0x7ff00000", formatted);
        Assert.Contains("Root family evidence:    4/5 observations across 2 addresses", formatted);
        Assert.Contains("Root family exemplar:    0x2000", formatted);
        Assert.Contains("Canonical root instance: 0x2000", formatted);
        Assert.Contains("Root family summary:     0x7ff00000 canonicalObs=3/5 rep=0x2000", formatted);
    }

    [Fact]
    public void Format_WithNoProvenanceSectionsOmitsProvenanceOutput()
    {
        var result = CreateCoordResult();
        var formatted = PlayerActorCoordReadTextFormatter.Format(result);

        Assert.DoesNotContain("Best chain parent:", formatted);
        Assert.DoesNotContain("Best chain root:", formatted);
        Assert.DoesNotContain("Root family evidence:", formatted);
        Assert.DoesNotContain("Root family summary:", formatted);
        Assert.Contains("Memory sample:", formatted);
    }

    private static PlayerActorCoordReadResult CreateCoordResult(
        PlayerActorTruthBestContainerChain? containerChain = null,
        PlayerActorTruthRootFamilyCandidate? rootFamily = null,
        PlayerActorTruthRootFamilySummary? summary = null)
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
            ModulePattern: new ModulePatternScanResult(
                Mode: "module-pattern",
                ProcessId: 1337,
                ProcessName: "rift_x64",
                ModuleName: "rift_x64.exe",
                ModuleFileName: "rift_x64.exe",
                ModuleBaseAddress: "0x100000",
                ModuleMemorySize: 1048576,
                Pattern: "AA 55",
                Found: true,
                RelativeOffset: 4096,
                RelativeOffsetHex: "0x1000",
                Address: "0x101000",
                ContextBytes: 16,
                ContextBytesHex: "AA 55"),
            BestContainerChain: containerChain,
            BestRootFamily: rootFamily,
            RootFamilySummary: summary,
            Notes: Array.Empty<string>());
    }
}
