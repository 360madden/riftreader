using System.Reflection;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Tests.Models;

public sealed class PlayerOrientationCandidateFinderLedgerTests
{
    [Fact]
    public void ApplyLedgerEvidence_PenalizesMatchingPointerHopCandidate()
    {
        var candidate = NewCandidate(score: 260);
        var ledger = NewLedgerEvidence(
            "0xABCDEF00",
            "0xD4",
            new OrientationCandidateLedgerEvidence(
                SourceAddress: "0xABCDEF00",
                BasisForwardOffset: "0xD4",
                StableNonresponsiveCount: 2,
                ResponsiveCount: 0,
                LatestCandidateRejectedReason: "stable_but_nonresponsive",
                LatestGeneratedAtUtc: "2026-05-08T00:01:00Z",
                LatestCandidateResponsive: false,
                ScorePenalty: 240));

        var result = ApplyLedgerEvidence(candidate, ledger);

        Assert.Equal(260, result.RawScore);
        Assert.Equal(20, result.Score);
        Assert.Equal(240, result.LedgerPenalty);
        Assert.Equal("stable_but_nonresponsive", result.LedgerRejectionReason);
        Assert.Equal(2, result.LedgerStableNonresponsiveCount);
        Assert.Equal(0, result.LedgerResponsiveCount);
        Assert.Equal("2026-05-08T00:01:00Z", result.LedgerLatestGeneratedAtUtc);
    }

    [Fact]
    public void ApplyLedgerEvidence_DoesNotPenalizeDifferentBasisOffset()
    {
        var candidate = NewCandidate(score: 260);
        var ledger = NewLedgerEvidence(
            "0xABCDEF00",
            "0x94",
            new OrientationCandidateLedgerEvidence(
                SourceAddress: "0xABCDEF00",
                BasisForwardOffset: "0x94",
                StableNonresponsiveCount: 1,
                ResponsiveCount: 0,
                LatestCandidateRejectedReason: "stable_but_nonresponsive",
                LatestGeneratedAtUtc: "2026-05-08T00:01:00Z",
                LatestCandidateResponsive: false,
                ScorePenalty: 180));

        var result = ApplyLedgerEvidence(candidate, ledger);

        Assert.Equal(260, result.RawScore);
        Assert.Equal(260, result.Score);
        Assert.Equal(0, result.LedgerPenalty);
        Assert.Null(result.LedgerRejectionReason);
    }

    [Fact]
    public void ApplyLedgerEvidence_ClampsPenalizedScoreAtZero()
    {
        var candidate = NewCandidate(score: 90);
        var ledger = NewLedgerEvidence(
            "0xABCDEF00",
            "0xD4",
            new OrientationCandidateLedgerEvidence(
                SourceAddress: "0xABCDEF00",
                BasisForwardOffset: "0xD4",
                StableNonresponsiveCount: 5,
                ResponsiveCount: 0,
                LatestCandidateRejectedReason: "stable_but_nonresponsive",
                LatestGeneratedAtUtc: "2026-05-08T00:05:00Z",
                LatestCandidateResponsive: false,
                ScorePenalty: 400));

        var result = ApplyLedgerEvidence(candidate, ledger);

        Assert.Equal(90, result.RawScore);
        Assert.Equal(0, result.Score);
        Assert.Equal(400, result.LedgerPenalty);
    }

    private static PlayerOrientationPointerHopCandidate ApplyLedgerEvidence(
        PlayerOrientationPointerHopCandidate candidate,
        IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> ledger)
    {
        var method = typeof(PlayerOrientationCandidateFinder).GetMethod(
            "ApplyLedgerEvidence",
            BindingFlags.NonPublic | BindingFlags.Static);
        Assert.NotNull(method);

        var result = method.Invoke(null, [candidate, ledger]);
        return Assert.IsType<PlayerOrientationPointerHopCandidate>(result);
    }

    private static IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> NewLedgerEvidence(
        string sourceAddress,
        string basisForwardOffset,
        OrientationCandidateLedgerEvidence evidence)
    {
        var key = OrientationCandidateLedgerLoader.BuildCandidateKey(sourceAddress, basisForwardOffset);
        Assert.NotNull(key);
        return new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase)
        {
            [key] = evidence
        };
    }

    private static PlayerOrientationPointerHopCandidate NewCandidate(int score)
    {
        var forward = new ValidatorCoordinateSnapshot(0.70710677d, 0.0d, 0.70710677d);
        var up = new ValidatorCoordinateSnapshot(0.0d, 1.0d, 0.0d);
        var right = new ValidatorCoordinateSnapshot(-0.70710677d, 0.0d, 0.70710677d);
        var basis = new PlayerOrientationBasisCandidate(
            Name: "Basis@0xD4",
            Forward: forward,
            Up: up,
            Right: right,
            Determinant: 1.0d,
            IsOrthonormal: true,
            ForwardDotUp: 0.0d,
            ForwardDotRight: 0.0d,
            UpDotRight: 0.0d);
        var estimate = new PlayerOrientationVectorEstimate(
            Name: "Basis@0xD4",
            Vector: forward,
            YawRadians: Math.PI / 4.0d,
            YawDegrees: 45.0d,
            PitchRadians: 0.0d,
            PitchDegrees: 0.0d,
            Magnitude: 1.0d);

        return new PlayerOrientationPointerHopCandidate(
            Address: "0xABCDEF00",
            ParentAddress: "0x12345000",
            ParentFamilyId: "test-family",
            ParentScore: 100,
            DiscoveryMode: "pointer-hop",
            BasisPrimaryForwardOffset: "0xD4",
            Score: score,
            Basis: basis,
            PreferredEstimate: estimate,
            RootAddress: "0x12345000",
            RootSource: "coord-anchor-source-object",
            HopDepth: 1,
            PointerOffset: "0x20");
    }
}
