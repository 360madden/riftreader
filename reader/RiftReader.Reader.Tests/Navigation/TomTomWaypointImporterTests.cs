using System.Text.Json;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Tests.Navigation;

public sealed class TomTomWaypointImporterTests
{
    [Fact]
    public void TryImport_ImportsBracketedTomTomWaypointArrays()
    {
        var tempDirectory = CreateTempDirectory();
        var tomTomFile = Path.Combine(tempDirectory, "TomTom.lua");
        var destinationFile = Path.Combine(tempDirectory, "waypoints.json");
        File.WriteAllText(
            tomTomFile,
            """
            TomTomGlobal = {
              PickupLocations = {
                ["Rare Mobs"] = {
                  [1] = {
                    [1] = "zone-a",
                    [2] = 7424.099609375,
                    [3] = 3206.4599609375,
                    [4] = 1,
                    [5] = "rare spawn"
                  },
                  [2] = {
                    [1] = "zone-b",
                    [2] = 1,
                    [3] = 2,
                    [4] = 1,
                    [5] = "other zone"
                  }
                }
              }
            }
            """);

        try
        {
            var result = TomTomWaypointImporter.TryImport(
                new TomTomWaypointImportOptions(
                    SourceFile: tomTomFile,
                    DestinationFile: destinationFile,
                    ListNames: ["Rare Mobs"],
                    Zone: "zone-a",
                    DefaultY: 818.10998535156d,
                    IdPrefix: "tt",
                    ArrivalRadius: 4.5d,
                    Pace: "keep"),
                out var error);

            Assert.NotNull(result);
            Assert.Null(error);
            Assert.Equal(1, result!.ImportedWaypointCount);
            Assert.Equal(0, result.PreservedWaypointCount);
            Assert.Equal(0, result.UpdatedWaypointCount);
            Assert.Contains(result.Lists, list => list.Name == "Rare Mobs" && list.ImportedWaypointCount == 1 && list.SkippedWaypointCount == 1);

            var imported = Assert.Single(result.Waypoints);
            Assert.Equal("tt_rare_mobs_001", imported.Id);
            Assert.Equal("Rare Mobs", imported.ListName);
            Assert.Equal("zone-a", imported.Zone);
            Assert.Equal(7424.099609375d, imported.X);
            Assert.Equal(818.10998535156d, imported.Y);
            Assert.Equal(3206.4599609375d, imported.Z);
            Assert.Equal("Rare Mobs: rare spawn", imported.Label);

            var configuration = WaypointNavigationConfigurationLoader.TryLoad(destinationFile, out var loadError);
            Assert.NotNull(configuration);
            Assert.Null(loadError);
            var waypoint = Assert.Single(configuration!.Waypoints.Values);
            Assert.Equal("tt_rare_mobs_001", waypoint.Id);
            Assert.Equal("Rare Mobs: rare spawn", waypoint.Label);
            Assert.Equal("zone-a", waypoint.Zone);
            Assert.Equal(4.5d, waypoint.ArrivalRadius);
            Assert.Equal("keep", waypoint.Pace);
            Assert.Equal(7424.099609375d, waypoint.X);
            Assert.Equal(818.10998535156d, waypoint.Y);
            Assert.Equal(3206.4599609375d, waypoint.Z);
        }
        finally
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }

    [Fact]
    public void TryImport_PreservesExistingNonImportedWaypointsAndUpdatesStableTomTomIds()
    {
        var tempDirectory = CreateTempDirectory();
        var tomTomFile = Path.Combine(tempDirectory, "TomTom.lua");
        var destinationFile = Path.Combine(tempDirectory, "waypoints.json");
        File.WriteAllText(
            tomTomFile,
            """
            TomTomGlobal = {
              PickupLocations = {
                wood = {
                  { "zone-a", 10, 20, 1, "tree" }
                }
              }
            }
            """);
        File.WriteAllText(
            destinationFile,
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
                { "id": "manual", "label": "Manual", "x": 1, "y": 2, "z": 3 },
                { "id": "tomtom_wood_001", "label": "Old", "zone": "old-zone", "x": 4, "y": 5, "z": 6 }
              ]
            }
            """);

        try
        {
            var result = TomTomWaypointImporter.TryImport(
                new TomTomWaypointImportOptions(
                    SourceFile: tomTomFile,
                    DestinationFile: destinationFile,
                    ListNames: [],
                    Zone: null,
                    DefaultY: 7d,
                    IdPrefix: "tomtom",
                    ArrivalRadius: null,
                    Pace: null),
                out var error);

            Assert.NotNull(result);
            Assert.Null(error);
            Assert.Equal(1, result!.ImportedWaypointCount);
            Assert.Equal(1, result.PreservedWaypointCount);
            Assert.Equal(1, result.UpdatedWaypointCount);

            var configuration = WaypointNavigationConfigurationLoader.TryLoad(destinationFile, out var loadError);
            Assert.NotNull(configuration);
            Assert.Null(loadError);
            Assert.True(configuration!.Waypoints.ContainsKey("manual"));
            Assert.True(configuration.Waypoints.TryGetValue("tomtom_wood_001", out var imported));
            Assert.Equal("wood: tree", imported!.Label);
            Assert.Equal("zone-a", imported.Zone);
            Assert.Equal(10d, imported.X);
            Assert.Equal(7d, imported.Y);
            Assert.Equal(20d, imported.Z);
        }
        finally
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }

    [Fact]
    public void TryImport_PreservesExtendedProvenanceAndWritesCamelCaseSchema()
    {
        var tempDirectory = CreateTempDirectory();
        var tomTomFile = Path.Combine(tempDirectory, "TomTom.lua");
        var destinationFile = Path.Combine(tempDirectory, "waypoints.json");
        File.WriteAllText(
            tomTomFile,
            """
            TomTomGlobal = {
              PickupLocations = {
                wood = {
                  { "zone-a", 10, 20, 1, "tree" }
                }
              }
            }
            """);
        File.WriteAllText(
            destinationFile,
            """
            {
              "schemaVersion": 1,
              "provenance": {
                "kind": "smoke-route",
                "generatedAtUtc": "2026-05-08T05:36:00.0000000Z",
                "processId": 33912,
                "readerBridgeCoord": {
                  "x": 7435.94921875,
                  "y": 885.2191772460938,
                  "z": 3059.5537109375
                },
                "navigationBearingKind": "forward-key-movement-bearing",
                "navigationBearingSource": "actor-facing-basis-opposite-xz-projection",
                "navigationBearingDegrees": -145.71781003282072
              },
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
                { "id": "manual", "label": "Manual", "x": 1, "y": 2, "z": 3 }
              ]
            }
            """);

        try
        {
            var result = TomTomWaypointImporter.TryImport(
                new TomTomWaypointImportOptions(
                    SourceFile: tomTomFile,
                    DestinationFile: destinationFile,
                    ListNames: [],
                    Zone: null,
                    DefaultY: 7d,
                    IdPrefix: "tomtom",
                    ArrivalRadius: null,
                    Pace: null),
                out var error);

            Assert.NotNull(result);
            Assert.Null(error);
            Assert.Equal(1, result!.ImportedWaypointCount);

            using var document = JsonDocument.Parse(File.ReadAllText(destinationFile));
            var root = document.RootElement;
            Assert.True(root.TryGetProperty("schemaVersion", out _));
            Assert.True(root.TryGetProperty("movement", out _));
            Assert.True(root.TryGetProperty("waypoints", out _));
            Assert.False(root.TryGetProperty("SchemaVersion", out _));
            Assert.False(root.TryGetProperty("Movement", out _));
            Assert.False(root.TryGetProperty("Waypoints", out _));

            var provenance = root.GetProperty("provenance");
            Assert.Equal("smoke-route", provenance.GetProperty("kind").GetString());
            Assert.Equal("2026-05-08T05:36:00.0000000Z", provenance.GetProperty("generatedAtUtc").GetString());
            Assert.Equal(33912, provenance.GetProperty("processId").GetInt32());
            Assert.Equal("forward-key-movement-bearing", provenance.GetProperty("navigationBearingKind").GetString());
            Assert.Equal(
                "actor-facing-basis-opposite-xz-projection",
                provenance.GetProperty("navigationBearingSource").GetString());
            Assert.False(provenance.TryGetProperty("NavigationBearingKind", out _));

            var readerBridgeCoord = provenance.GetProperty("readerBridgeCoord");
            Assert.Equal(7435.94921875d, readerBridgeCoord.GetProperty("x").GetDouble());
            Assert.Equal(885.2191772460938d, readerBridgeCoord.GetProperty("y").GetDouble());
            Assert.Equal(3059.5537109375d, readerBridgeCoord.GetProperty("z").GetDouble());
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
