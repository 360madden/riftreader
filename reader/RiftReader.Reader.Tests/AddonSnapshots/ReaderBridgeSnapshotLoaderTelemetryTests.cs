using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotLoaderTelemetryTests
{
    [Fact]
    public void TryLoad_MapsTelemetryBlockWhenPresent()
    {
        var file = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.lua");
        try
        {
            File.WriteAllText(file, """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = {
    lastExportAt = 123.0,
    lastReason = "heartbeat",
    exportCount = 7,
  },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "heartbeat",
    exportCount = 7,
    generatedAtRealtime = 123.5,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    sourceVersion = "3",
    telemetry = {
      version = 1,
      sequence = 42,
      generatedAtRealtime = 123.5,
      capabilities = {
        apiFacingAvailable = false,
        apiYawAvailable = false,
        readerBridgeAvailable = true,
        directApiAvailable = false,
        nearbyUnitsAvailable = false,
        targetAvailable = true,
      },
      position = {
        coord = { x = 1.0, y = 2.0, z = 3.0 },
        zone = "Sanctum",
        locationName = "City",
        sourceMode = "ReaderBridge",
      },
      movement = {
        dx = 0.1,
        dy = 0.0,
        dz = 0.2,
        distance = 0.2236,
        dt = 0.5,
        speed = 0.4472,
      },
      context = {
        playerId = "player.unit",
        targetId = "target.unit",
        combat = true,
        targetPresent = true,
        zone = "Sanctum",
        locationName = "City",
        sourceAddon = "ReaderBridge",
        sourceMode = "ReaderBridge",
        sourceVersion = "3",
        exportAddon = "ReaderBridgeExport",
        exportVersion = "0.1.0",
      },
    },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""");

            var document = ReaderBridgeSnapshotLoader.TryLoad(file, out var error);

            Assert.Null(error);
            Assert.NotNull(document);
            Assert.NotNull(document!.Current);
            Assert.NotNull(document.Current!.Telemetry);
            Assert.Equal(1, document.Current.Telemetry!.Version);
            Assert.Equal(42L, document.Current.Telemetry.Sequence);
            Assert.Equal("Sanctum", document.Current.Telemetry.Position!.Zone);
            Assert.Equal(0.4472d, document.Current.Telemetry.Movement!.Speed);
            Assert.True(document.Current.Telemetry.Context!.Combat);
        }
        finally
        {
            if (File.Exists(file))
            {
                File.Delete(file);
            }
        }
    }

    [Fact]
    public void TryLoad_KeepsTelemetryNullWhenExportDoesNotDefineIt()
    {
        var file = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.lua");
        try
        {
            File.WriteAllText(file, """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = {
    lastExportAt = 10.0,
    lastReason = "heartbeat",
    exportCount = 1,
  },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "heartbeat",
    exportCount = 1,
    generatedAtRealtime = 10.5,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    sourceVersion = "3",
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""");

            var document = ReaderBridgeSnapshotLoader.TryLoad(file, out var error);

            Assert.Null(error);
            Assert.NotNull(document);
            Assert.NotNull(document!.Current);
            Assert.Null(document.Current!.Telemetry);
        }
        finally
        {
            if (File.Exists(file))
            {
                File.Delete(file);
            }
        }
    }
}
