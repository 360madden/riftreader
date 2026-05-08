using System.Text.Json;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Tests.Formatting;

public sealed class PlayerOrientationCandidateSearchJsonOutputTests
{
    [Fact]
    public void Serialize_IncludesPointerHopLedgerEvidenceFields()
    {
        var candidate = NewCandidate(score: 20) with
        {
            RawScore = 260,
            LedgerPenalty = 240,
            LedgerRejectionReason = "stable_but_nonresponsive",
            LedgerStableNonresponsiveCount = 2,
            LedgerResponsiveCount = 0,
            LedgerLatestGeneratedAtUtc = "2026-05-08T00:01:00Z"
        };
        var result = new PlayerOrientationCandidateSearchResult(
            Mode: "player-orientation-candidate-search",
            ProcessId: 4242,
            ProcessName: "rift_x64",
            PlayerName: "Atank",
            PlayerCoord: new ValidatorCoordinateSnapshot(7436.64d, 885.22d, 3055.75d),
            CandidateCount: 0,
            BestCandidate: null,
            Candidates: Array.Empty<PlayerOrientationCandidate>(),
            PointerHopCandidateCount: 1,
            BestPointerHopCandidate: candidate,
            PointerHopCandidates: [candidate],
            Diagnostics: new PlayerOrientationProbeDiagnostics(
                CoordHitCount: 1,
                LocalWindowProbeCount: 0,
                LocalWindowReadFailures: 0,
                LocalCoordMismatchCount: 0,
                SeedProbeCount: 0,
                SeedProbeReadFailures: 0,
                SeedCoordMatchCount: 0,
                PointerRootCount: 1,
                PointerRootReadFailures: 0,
                PointerSlotCount: 3,
                UniqueChildPointerCount: 1,
                ChildReadFailures: 0,
                SecondHopRootCount: 0,
                RejectedNonOrthonormalBasisCount: 0,
                RejectedLowComponentDiversityCount: 0,
                RejectedLowHorizontalMagnitudeCount: 0),
            Notes:
            [
                "Orientation candidate ledger evidence loaded from 'ledger.ndjson': entries=2, uniqueCandidates=1, penalizedPointerHopCandidates=1."
            ]);

        using var document = JsonDocument.Parse(JsonOutput.Serialize(result));
        var root = document.RootElement;
        var best = root.GetProperty("BestPointerHopCandidate");
        Assert.Equal(260, best.GetProperty("RawScore").GetInt32());
        Assert.Equal(20, best.GetProperty("Score").GetInt32());
        Assert.Equal(240, best.GetProperty("LedgerPenalty").GetInt32());
        Assert.Equal("stable_but_nonresponsive", best.GetProperty("LedgerRejectionReason").GetString());
        Assert.Equal(2, best.GetProperty("LedgerStableNonresponsiveCount").GetInt32());
        Assert.Equal(0, best.GetProperty("LedgerResponsiveCount").GetInt32());
        Assert.Equal("2026-05-08T00:01:00Z", best.GetProperty("LedgerLatestGeneratedAtUtc").GetString());

        var row = root.GetProperty("PointerHopCandidates")[0];
        Assert.Equal(240, row.GetProperty("LedgerPenalty").GetInt32());
        Assert.Contains("penalizedPointerHopCandidates=1", root.GetProperty("Notes")[0].GetString(), StringComparison.Ordinal);
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
