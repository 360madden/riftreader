using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Tests.Navigation;

public sealed class WaypointNavigationConfigurationStoreTests
{
    [Fact]
    public void TryUpsertWaypoint_CreatesNewFileWithDefaultMovementSettings()
    {
        var tempDirectory = CreateTempDirectory();
        var filePath = Path.Combine(tempDirectory, "waypoints.json");
        var sample = new NavigationPoseSample("0x1234", 1.25d, 2.5d, 3.75d);

        try
        {
            var waypoint = WaypointNavigationConfigurationStore.TryUpsertWaypoint(
                filePath,
                waypointId: "point_a",
                sample: sample,
                label: "Point A",
                zone: "test_zone",
                arrivalRadius: 2.25d,
                pace: "keep",
                resolvedFile: out var resolvedFile,
                created: out var created,
                error: out var error);

            Assert.NotNull(waypoint);
            Assert.Equal(filePath, resolvedFile);
            Assert.True(created);
            Assert.Null(error);

            var configuration = WaypointNavigationConfigurationLoader.TryLoad(filePath, out var loadError);
            Assert.NotNull(configuration);
            Assert.Null(loadError);
            Assert.Equal("w", configuration!.Movement.ForwardKey);
            Assert.True(configuration.Waypoints.TryGetValue("point_a", out var storedWaypoint));
            Assert.Equal("Point A", storedWaypoint!.Label);
            Assert.Equal("test_zone", storedWaypoint.Zone);
            Assert.Equal(2.25d, storedWaypoint.ArrivalRadius);
            Assert.Equal("keep", storedWaypoint.Pace);
            Assert.Equal(sample.X, storedWaypoint.X);
            Assert.Equal(sample.Y, storedWaypoint.Y);
            Assert.Equal(sample.Z, storedWaypoint.Z);
        }
        finally
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }

    [Fact]
    public void TryUpsertWaypoint_UpdatesExistingWaypointAndPreservesMetadataWhenOverridesAreOmitted()
    {
        var tempDirectory = CreateTempDirectory();
        var filePath = Path.Combine(tempDirectory, "waypoints.json");
        File.WriteAllText(
            filePath,
            """
            {
              "schemaVersion": 1,
              "movement": {
                "forwardKey": "w",
                "defaultPace": "keep",
                "forwardPulseMilliseconds": 250,
                "postPulseSampleDelayMilliseconds": 150,
                "startRadius": 2.0,
                "defaultArrivalRadius": 1.5,
                "noProgressWindowMilliseconds": 1500,
                "minimumProgressDistance": 0.35,
                "wrongWayToleranceDistance": 0.75,
                "maxTravelSeconds": 30
              },
              "waypoints": [
                {
                  "id": "point_a",
                  "label": "Point A",
                  "zone": "test_zone",
                  "x": 1.0,
                  "y": 2.0,
                  "z": 3.0,
                  "arrivalRadius": 2.5,
                  "pace": "walk"
                }
              ]
            }
            """);

        try
        {
            var waypoint = WaypointNavigationConfigurationStore.TryUpsertWaypoint(
                filePath,
                waypointId: "POINT_A",
                sample: new NavigationPoseSample("0x1234", 9d, 8d, 7d),
                label: null,
                zone: null,
                arrivalRadius: null,
                pace: null,
                resolvedFile: out _,
                created: out var created,
                error: out var error);

            Assert.NotNull(waypoint);
            Assert.False(created);
            Assert.Null(error);
            Assert.Equal("Point A", waypoint!.Label);
            Assert.Equal("test_zone", waypoint.Zone);
            Assert.Equal(2.5d, waypoint.ArrivalRadius);
            Assert.Equal("walk", waypoint.Pace);
            Assert.Equal(9d, waypoint.X);
            Assert.Equal(8d, waypoint.Y);
            Assert.Equal(7d, waypoint.Z);
        }
        finally
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }

    private static string CreateTempDirectory()
    {
        var directory = Path.Combine(Path.GetTempPath(), "RiftReader.Tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        return directory;
    }
}
