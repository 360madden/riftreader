using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.Formatting;

public sealed class PlayerActorTruthChainDumpTextFormatterTests
{
    [Fact]
    public void Format_IncludesCompactRootFamilySummaryWhenPresent()
    {
        var result = PlayerActorTestData.CreateChainDumpResult();

        var formatted = PlayerActorTruthChainDumpTextFormatter.Format(result);

        Assert.Contains("Canonical root instance: 0x2000", formatted);
        Assert.Contains("Root family summary:     0x7ff00000 canonicalObs=3/5 rep=0x2000", formatted);
        Assert.Contains("Best root family:        0x7ff00000 (4/5, distinct=2, avgMatch=42.0)", formatted);
    }

    [Fact]
    public void Format_OmitsCompactRootFamilySummaryWhenAbsent()
    {
        var result = PlayerActorTestData.CreateChainDumpResult(summary: null) with
        {
            RootFamilySummary = null,
            Truth = PlayerActorTestData.CreateTruthResult(
                PlayerActorTestData.CreateContainerChain(),
                PlayerActorTestData.CreateRootFamilyCandidate(),
                null)
        };

        var formatted = PlayerActorTruthChainDumpTextFormatter.Format(result);

        Assert.DoesNotContain("Canonical root instance:", formatted);
        Assert.DoesNotContain("Root family summary:", formatted);
        Assert.Contains("Best root family:", formatted);
    }
}
