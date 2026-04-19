using RiftReader.Reader.Cli;

namespace RiftReader.Reader.Tests.Cli;

public sealed class ReaderOptionsParserTests
{
    [Fact]
    public void Parse_ReadNavigationCurrent_PreservesOwnerComponentsFile()
    {
        var result = ReaderOptionsParser.Parse([
            "--process-name", "rift_x64",
            "--read-navigation-current",
            "--destination-waypoint", "example_destination",
            "--owner-components-file", @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        Assert.NotNull(result.Options);
        Assert.Equal(
            @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            result.Options!.OwnerComponentsFile);
        Assert.True(result.Options.ReadNavigationCurrent);
    }

    [Fact]
    public void Parse_NavigateWaypoints_PreservesOwnerComponentsFile()
    {
        var result = ReaderOptionsParser.Parse([
            "--process-name", "rift_x64",
            "--navigate-waypoints",
            "--start-waypoint", "example_start",
            "--destination-waypoint", "example_destination",
            "--owner-components-file", @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        Assert.NotNull(result.Options);
        Assert.Equal(
            @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            result.Options!.OwnerComponentsFile);
        Assert.True(result.Options.NavigateWaypoints);
    }
}
