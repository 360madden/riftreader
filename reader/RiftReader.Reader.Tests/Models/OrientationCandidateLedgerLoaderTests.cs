using RiftReader.Reader.Models;

namespace RiftReader.Reader.Tests.Models;

public sealed class OrientationCandidateLedgerLoaderTests
{
    [Fact]
    public void BuildCandidateKey_NormalizesSourceAndBasisOffset()
    {
        var key = OrientationCandidateLedgerLoader.BuildCandidateKey("0xabcdef00", "212");

        Assert.Equal("0xABCDEF00|0xD4", key);
    }

    [Fact]
    public void BuildCandidateKey_DefaultsMissingBasisOffsetToZero()
    {
        var key = OrientationCandidateLedgerLoader.BuildCandidateKey("2748", null);

        Assert.Equal("0xABC|0x0", key);
    }

    [Fact]
    public void Load_MissingLedgerFileReturnsEmptyLedgerWithoutError()
    {
        using var temp = TemporaryLedgerDirectory.Create();
        var missingPath = Path.Combine(temp.DirectoryPath, "missing.ndjson");

        var ledger = OrientationCandidateLedgerLoader.Load(missingPath);

        Assert.Equal(Path.GetFullPath(missingPath), ledger.FilePath);
        Assert.Empty(ledger.Entries);
        Assert.Empty(ledger.EvidenceByCandidate);
        Assert.Null(ledger.LoadError);
    }

    [Fact]
    public void Load_MalformedNdjsonReturnsLoadErrorWithoutEvidenceIndex()
    {
        using var temp = TemporaryLedgerDirectory.Create();
        var ledgerPath = temp.WriteLedger(
            """{"generatedAtUtc":"2026-05-08T00:00:00Z","sourceAddress":"0xABCDEF00","basisForwardOffset":"0xD4"}""",
            """{"generatedAtUtc":""");

        var ledger = OrientationCandidateLedgerLoader.Load(ledgerPath);

        Assert.Single(ledger.Entries);
        Assert.Empty(ledger.EvidenceByCandidate);
        Assert.NotNull(ledger.LoadError);
        Assert.Contains("line 2", ledger.LoadError, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_PenalizesRepeatedStableNonresponsiveEvidenceForCandidate()
    {
        using var temp = TemporaryLedgerDirectory.Create();
        var ledgerPath = temp.WriteLedger(
            """{"generatedAtUtc":"2026-05-08T00:00:00Z","sourceAddress":"0xabcdef00","basisForwardOffset":"0xd4","candidateResponsive":false,"candidateRejectedReason":"stable_but_nonresponsive"}""",
            """{"generatedAtUtc":"2026-05-08T00:01:00Z","sourceAddress":"0xABCDEF00","basisForwardOffset":"212","candidateResponsive":false,"candidateRejectedReason":"stable_but_nonresponsive"}""");

        var ledger = OrientationCandidateLedgerLoader.Load(ledgerPath);

        var evidence = Assert.Single(ledger.EvidenceByCandidate).Value;
        Assert.Equal("0xABCDEF00", evidence.SourceAddress);
        Assert.Equal("0xD4", evidence.BasisForwardOffset);
        Assert.Equal(2, evidence.StableNonresponsiveCount);
        Assert.Equal(0, evidence.ResponsiveCount);
        Assert.Equal("stable_but_nonresponsive", evidence.LatestCandidateRejectedReason);
        Assert.False(evidence.LatestCandidateResponsive);
        Assert.Equal(240, evidence.ScorePenalty);
    }

    [Fact]
    public void Load_PenalizesLatestIdleDriftEvidence()
    {
        using var temp = TemporaryLedgerDirectory.Create();
        var ledgerPath = temp.WriteLedger(
            """{"generatedAtUtc":"2026-05-08T00:00:00Z","sourceAddress":"0xABCDEF00","basisForwardOffset":"0xD4","candidateResponsive":false,"candidateRejectedReason":"idle_drift"}""");

        var ledger = OrientationCandidateLedgerLoader.Load(ledgerPath);

        var evidence = Assert.Single(ledger.EvidenceByCandidate).Value;
        Assert.Equal("idle_drift", evidence.LatestCandidateRejectedReason);
        Assert.False(evidence.LatestCandidateResponsive);
        Assert.Equal(0, evidence.StableNonresponsiveCount);
        Assert.Equal(180, evidence.ScorePenalty);
    }

    [Fact]
    public void Load_LatestResponsiveEvidenceClearsStaleStableNonresponsivePenalty()
    {
        using var temp = TemporaryLedgerDirectory.Create();
        var ledgerPath = temp.WriteLedger(
            """{"generatedAtUtc":"2026-05-08T00:00:00Z","sourceAddress":"0xABCDEF00","basisForwardOffset":"0xD4","candidateResponsive":false,"candidateRejectedReason":"stable_but_nonresponsive"}""",
            """{"generatedAtUtc":"2026-05-08T00:01:00Z","sourceAddress":"0xABCDEF00","basisForwardOffset":"0xD4","candidateResponsive":true}""");

        var ledger = OrientationCandidateLedgerLoader.Load(ledgerPath);

        var evidence = Assert.Single(ledger.EvidenceByCandidate).Value;
        Assert.Equal(1, evidence.StableNonresponsiveCount);
        Assert.Equal(1, evidence.ResponsiveCount);
        Assert.Null(evidence.LatestCandidateRejectedReason);
        Assert.True(evidence.LatestCandidateResponsive);
        Assert.Equal(0, evidence.ScorePenalty);
    }

    private sealed class TemporaryLedgerDirectory : IDisposable
    {
        private TemporaryLedgerDirectory(string directoryPath)
        {
            DirectoryPath = directoryPath;
        }

        public string DirectoryPath { get; }

        public static TemporaryLedgerDirectory Create()
        {
            var directoryPath = Path.Combine(
                Path.GetTempPath(),
                "RiftReader-orientation-ledger-tests-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(directoryPath);
            return new TemporaryLedgerDirectory(directoryPath);
        }

        public string WriteLedger(params string[] lines)
        {
            var ledgerPath = Path.Combine(DirectoryPath, "ledger.ndjson");
            File.WriteAllLines(ledgerPath, lines);
            return ledgerPath;
        }

        public void Dispose()
        {
            if (Directory.Exists(DirectoryPath))
            {
                Directory.Delete(DirectoryPath, recursive: true);
            }
        }
    }
}
