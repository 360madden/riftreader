using RiftReader.Reader.Models;

namespace RiftReader.Reader.Tests.Models;

public sealed class TargetCurrentReaderTests
{
    [Fact]
    public void IsAcceptableCurrentRead_AllowsUnreadNameAndDistanceWhenCoreFieldsMatch()
    {
        var memory = BuildMemory(name: null, distance: null);
        var match = BuildMatch(nameMatches: false, distanceMatches: false);
        var expected = BuildExpected();

        Assert.True(TargetCurrentReader.IsAcceptableCurrentRead(memory, match, expected));
    }

    [Fact]
    public void IsAcceptableCurrentRead_RejectsPopulatedWrongName()
    {
        var memory = BuildMemory(name: "WrongTarget", distance: null);
        var match = BuildMatch(nameMatches: false, distanceMatches: false);
        var expected = BuildExpected();

        Assert.False(TargetCurrentReader.IsAcceptableCurrentRead(memory, match, expected));
    }

    [Fact]
    public void IsAcceptableCurrentRead_RejectsPopulatedWrongDistance()
    {
        var memory = BuildMemory(name: null, distance: 12.5f);
        var match = BuildMatch(nameMatches: false, distanceMatches: false);
        var expected = BuildExpected();

        Assert.False(TargetCurrentReader.IsAcceptableCurrentRead(memory, match, expected));
    }

    [Fact]
    public void IsAcceptableCurrentRead_RejectsMissingExpectedHealth()
    {
        var memory = BuildMemory(name: null, distance: null) with { Health = null };
        var match = BuildMatch(nameMatches: false, distanceMatches: false) with { HealthMatches = false };
        var expected = BuildExpected();

        Assert.False(TargetCurrentReader.IsAcceptableCurrentRead(memory, match, expected));
    }

    private static TargetCurrentReadSample BuildMemory(string? name, float? distance) =>
        new(
            AddressHex: "0x1234",
            Level: 45,
            Health: 18208,
            Name: name,
            CoordX: 7251.04f,
            CoordY: 821.44f,
            CoordZ: 2987.8699f,
            Distance: distance);

    private static TargetCurrentReadExpected BuildExpected() =>
        new(
            Name: "Atank",
            Level: 45,
            Health: 18208,
            HealthMax: 18208,
            CoordX: 7251.0400390625,
            CoordY: 821.44000244141,
            CoordZ: 2987.8698730469,
            Distance: 0);

    private static TargetCurrentReadMatch BuildMatch(bool nameMatches, bool distanceMatches) =>
        new(
            NameMatches: nameMatches,
            LevelMatches: true,
            HealthMatches: true,
            CoordMatchesWithinTolerance: true,
            DistanceMatchesWithinTolerance: distanceMatches,
            DeltaX: 0,
            DeltaY: 0,
            DeltaZ: 0,
            DeltaDistance: distanceMatches ? 0 : 12.5f);
}
