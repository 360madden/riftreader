using System.Reflection;
using RiftReader.Reader.Models;
using Xunit;

namespace RiftReader.Reader.Tests.InternalLogic;

public sealed class ProgramRootFamilySummaryTests
{
    private static readonly Type ProgramType =
        typeof(PlayerActorTruthReadResult).Assembly.GetType("RiftReader.Reader.Program")
        ?? throw new InvalidOperationException("Unable to resolve RiftReader.Reader.Program for reflection tests.");

    private static readonly MethodInfo BuildRootFamilySummaryMethod =
        ProgramType.GetMethod("BuildRootFamilySummary", BindingFlags.NonPublic | BindingFlags.Static)
        ?? throw new InvalidOperationException("Unable to resolve BuildRootFamilySummary.");

    [Fact]
    public void BuildRootFamilySummary_ReturnsNullWhenBestFamilyIsMissing()
    {
        var result = InvokeBuildRootFamilySummary(
            PlayerActorTestData.CreateContainerChain(),
            null,
            PlayerActorTestData.CreateObservations("0x2000"),
            "0x2000");

        Assert.Null(result);
    }

    [Fact]
    public void BuildRootFamilySummary_PrefersCurrentRootWhenCountsTie()
    {
        var containerChain = PlayerActorTestData.CreateContainerChain(rootAddress: "0x2000", rootObservationCount: 2, stabilitySampleCount: 4);
        var family = PlayerActorTestData.CreateRootFamilyCandidate(
            representativeAddress: "0x2000",
            observationCount: 4,
            representativeObservationCount: 2,
            memberAddresses: ["0x2000", "0x3000"]);
        var observations = PlayerActorTestData.CreateObservations("0x2000", "0x3000", "0x2000", "0x3000");

        var result = InvokeBuildRootFamilySummary(containerChain, family, observations, preferredCurrentRootAddress: "0x3000");

        Assert.NotNull(result);
        Assert.Equal("0x3000", result!.CanonicalInstanceAddress);
        Assert.Equal(2, result.CanonicalInstanceObservationCount);
    }

    [Fact]
    public void BuildRootFamilySummary_PrefersBestChainRootBeforeRepresentativeWhenCountsTieAndNoCurrentRoot()
    {
        var containerChain = PlayerActorTestData.CreateContainerChain(rootAddress: "0x3000", rootObservationCount: 2, stabilitySampleCount: 4);
        var family = PlayerActorTestData.CreateRootFamilyCandidate(
            representativeAddress: "0x2000",
            observationCount: 4,
            representativeObservationCount: 2,
            memberAddresses: ["0x2000", "0x3000"]);
        var observations = PlayerActorTestData.CreateObservations("0x2000", "0x3000", "0x2000", "0x3000");

        var result = InvokeBuildRootFamilySummary(containerChain, family, observations, preferredCurrentRootAddress: null);

        Assert.NotNull(result);
        Assert.Equal("0x3000", result!.CanonicalInstanceAddress);
        Assert.Equal(2, result.CanonicalInstanceObservationCount);
    }

    [Fact]
    public void BuildRootFamilySummary_FallsBackToRepresentativeWhenFamilyHasNoObservedMembers()
    {
        var containerChain = PlayerActorTestData.CreateContainerChain(rootAddress: null);
        var family = PlayerActorTestData.CreateRootFamilyCandidate(
            representativeAddress: "0x9999",
            observationCount: 0,
            representativeObservationCount: 0,
            memberAddresses: ["0x9999", "0xAAAA"]);
        var observations = PlayerActorTestData.CreateObservations("0x2000", "0x3000");

        var result = InvokeBuildRootFamilySummary(containerChain, family, observations, preferredCurrentRootAddress: null);

        Assert.NotNull(result);
        Assert.Equal("0x9999", result!.CanonicalInstanceAddress);
        Assert.Equal(0, result.CanonicalInstanceObservationCount);
    }

    private static PlayerActorTruthRootFamilySummary? InvokeBuildRootFamilySummary(
        PlayerActorTruthBestContainerChain? containerChain,
        PlayerActorTruthRootFamilyCandidate? rootFamily,
        IReadOnlyList<PlayerActorTruthChainObservation> observations,
        string? preferredCurrentRootAddress) =>
        (PlayerActorTruthRootFamilySummary?)BuildRootFamilySummaryMethod.Invoke(
            obj: null,
            parameters:
            [
                containerChain,
                rootFamily,
                observations,
                preferredCurrentRootAddress
            ]);
}
