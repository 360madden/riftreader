using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.Serialization;

public sealed class PlayerActorTruthChainDumpJsonOutputTests
{
    [Fact]
    public void Serialize_IncludesRootFamilySummaryWhenPresent()
    {
        var result = PlayerActorTestData.CreateChainDumpResult();

        var json = JsonOutput.Serialize(result);

        Assert.Contains("\"TruthSearchMaxHits\": 16", json);
        Assert.Contains("\"RootFamilySummary\"", json);
        Assert.Contains("\"CanonicalInstanceAddress\": \"0x2000\"", json);
        Assert.Contains("\"RepresentativeAddress\": \"0x2000\"", json);
    }

    [Fact]
    public void Serialize_OmitsRootFamilySummaryWhenAbsent()
    {
        var result = PlayerActorTestData.CreateChainDumpResult(summary: null) with
        {
            RootFamilySummary = null,
            Truth = PlayerActorTestData.CreateTruthResult(
                PlayerActorTestData.CreateContainerChain(),
                PlayerActorTestData.CreateRootFamilyCandidate(),
                null)
        };

        var json = JsonOutput.Serialize(result);

        Assert.DoesNotContain("\"RootFamilySummary\"", json);
    }
}
