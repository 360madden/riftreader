using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotFormatterRegressionTests
{
    [Fact]
    public void PartialCoordDelta_FormatsWithUnknownDurationAndNoSpeedSuffix()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 31, lastReason = "partial-delta", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "partial-delta",
    generatedAtRealtime = 31,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Delta", level = 1 },
    playerCoordDelta = { distance = 1.25 },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(PartialCoordDelta_FormatsWithUnknownDurationAndNoSpeedSuffix), fixtureText);
        var text = ReaderBridgeSnapshotTextFormatter.Format(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Contains("Player motion:           1.250 over ?s", text, StringComparison.Ordinal);
        Assert.DoesNotContain("/s)", text, StringComparison.Ordinal);
    }

    [Fact]
    public void TargetResource_NoneKindWithoutValues_FormatsAsNoneNa()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 32, lastReason = "target-resource-none", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "target-resource-none",
    generatedAtRealtime = 32,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    target = { id = "t", name = "Target", level = 2, resourceKind = "none" },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(TargetResource_NoneKindWithoutValues_FormatsAsNoneNa), fixtureText);
        var text = ReaderBridgeSnapshotTextFormatter.Format(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Contains("Target resource:         none n/a", text, StringComparison.Ordinal);
    }

    [Fact]
    public void PlayerResource_WithMissingMax_FormatsWithUnknownMax()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 33, lastReason = "player-resource-missing-max", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "player-resource-missing-max",
    generatedAtRealtime = 33,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1, resourceKind = "Power", resource = 40 },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(PlayerResource_WithMissingMax_FormatsWithUnknownMax), fixtureText);
        var text = ReaderBridgeSnapshotTextFormatter.Format(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Contains("Player resource:         Power 40/?", text, StringComparison.Ordinal);
    }

    [Fact]
    public void MissingSourceVersion_FormatsWithQuestionMarkFallback()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 34, lastReason = "missing-source-version", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "missing-source-version",
    generatedAtRealtime = 34,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingSourceVersion_FormatsWithQuestionMarkFallback), fixtureText);
        var text = ReaderBridgeSnapshotTextFormatter.Format(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Contains("Source addon:            ReaderBridge v?", text, StringComparison.Ordinal);
    }

    [Fact]
    public void MissingExportVersion_FormatsWithQuestionMarkFallback()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 35, lastReason = "missing-export-version", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "missing-export-version",
    generatedAtRealtime = 35,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    sourceVersion = "1.2.3",
    exportAddon = "ReaderBridgeExport",
    player = { id = "p", name = "Player", level = 1 },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingExportVersion_FormatsWithQuestionMarkFallback), fixtureText);
        var text = ReaderBridgeSnapshotTextFormatter.Format(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Contains("Export addon:            ReaderBridgeExport v?", text, StringComparison.Ordinal);
    }
}
