using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotLoaderTests
{
    private const int FrozenSchemaVersion = 1;

    [Fact]
    public void FrozenFixture_ParsesCurrentSchema()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.frozen.lua");
        var snapshot = AssertSnapshot(document);

        Assert.Equal(FrozenSchemaVersion, document.SchemaVersion);
        Assert.Equal("manual-freeze", document.LastReason);
        Assert.Equal(17, document.ExportCount);
        Assert.Equal(FrozenSchemaVersion, snapshot.SchemaVersion);
        Assert.Equal("ready", snapshot.Status);
        Assert.Equal("ReaderBridgeExport", snapshot.ExportAddon);
        Assert.Equal("0.1.0-test", snapshot.ExportVersion);
        Assert.Equal("player.alpha", snapshot.PlayerId);
        Assert.Equal("npc.beta", snapshot.TargetId);

        Assert.NotNull(snapshot.Player);
        Assert.Equal("Atank", snapshot.Player!.Name);
        Assert.True(snapshot.Player.Player);
        Assert.True(snapshot.Player.Mounted);
        Assert.Equal(120000, snapshot.Player.HpCap);
        Assert.Equal("skull", snapshot.Player.Mark);
        Assert.Equal(7389.71, snapshot.Player.Coord!.X);
        Assert.Equal("Sweeping Strike", snapshot.Player.Cast!.AbilityName);

        Assert.NotNull(snapshot.Target);
        Assert.Equal("Training Dummy", snapshot.Target!.Name);
        Assert.Equal(4.5, snapshot.Target.Distance);

        Assert.NotNull(snapshot.OrientationProbe);
        Assert.Single(snapshot.OrientationProbe!.Player!.DetailCandidates);
        Assert.Single(snapshot.OrientationProbe.Target!.StateCandidates);
        Assert.Single(snapshot.OrientationProbe.StatCandidates);

        Assert.Equal(2, snapshot.PlayerStats.Count);
        Assert.Equal(1234.5, snapshot.PlayerStats["attackPower"]);
        Assert.Equal(678.9, snapshot.PlayerStats["critPower"]);

        Assert.NotNull(snapshot.PlayerCoordDelta);
        Assert.NotNull(snapshot.PlayerCoordDelta!.Speed);
        Assert.Equal(1.8032806258, snapshot.PlayerCoordDelta.Speed!.Value, 10);

        Assert.Equal(2, snapshot.NearbyUnits.Count);
        Assert.Equal("Training Dummy", snapshot.NearbyUnits[0].Name);
        Assert.Equal("Friend", snapshot.NearbyUnits[1].Name);

        Assert.NotNull(snapshot.NearbySummary);
        Assert.Equal(3, snapshot.NearbySummary!.ScannedCount);
        Assert.Equal(1, snapshot.NearbySummary.RelationCounts["hostile"]);
        Assert.Equal(1, snapshot.NearbySummary.RelationCounts["friendly"]);

        Assert.Single(snapshot.PartyUnits);
        Assert.NotNull(snapshot.PartySummary);
        Assert.Equal("Healz", snapshot.PartySummary!.NearestName);

        Assert.Equal(2, snapshot.PlayerBuffLines.Count);
        Assert.Empty(snapshot.PlayerDebuffLines);
        Assert.Empty(snapshot.TargetBuffLines);
        Assert.Single(snapshot.TargetDebuffLines);

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Guarded Steel", snapshot.PlayerBuffs[0].Name);
        Assert.Empty(snapshot.PlayerDebuffs);
        Assert.Empty(snapshot.TargetBuffs);
        Assert.Single(snapshot.TargetDebuffs);
        Assert.Single(snapshot.TargetDebuffs[0].Flags);
    }

    [Fact]
    public void DirectApiGoldenFixture_ParsesAndPreservesOrdering()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.directapi-golden.lua");
        var snapshot = AssertSnapshot(document);

        Assert.Equal("DirectAPI", snapshot.SourceMode);
        Assert.Equal("DirectHero", snapshot.Player!.Name);
        Assert.Equal("Bogling", snapshot.Target!.Name);
        Assert.Equal(2, snapshot.PlayerBuffLines.Count);
        Assert.Equal("Battle Fury", snapshot.PlayerBuffLines[0]);
        Assert.Equal("Aegis", snapshot.PlayerBuffLines[1]);
        Assert.Equal(2, snapshot.NearbyUnits.Count);
        Assert.Equal("Bogling", snapshot.NearbyUnits[0].Name);
        Assert.Equal("Scout", snapshot.NearbyUnits[1].Name);
        Assert.Equal(2, snapshot.PartyUnits.Count);
        Assert.Equal("Healer", snapshot.PartyUnits[0].Name);
        Assert.Equal("Tank", snapshot.PartyUnits[1].Name);
        Assert.Empty(snapshot.TargetBuffs[0].Flags);
    }

    [Fact]
    public void ThinLiveFixture_ParsesAndKeepsEmptyCollectionsStable()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.thin-live.lua");
        var snapshot = AssertSnapshot(document);

        Assert.Equal(FrozenSchemaVersion, document.SchemaVersion);
        Assert.Equal("save-begin", document.LastReason);
        Assert.Equal(931, document.ExportCount);
        Assert.Equal("DirectAPI", snapshot.SourceMode);
        Assert.Equal("Atank", snapshot.Player!.Name);
        Assert.Equal("Thedeor's Circle", snapshot.Player.LocationName);
        Assert.Empty(snapshot.NearbyUnits);
        Assert.Empty(snapshot.PartyUnits);
        Assert.Empty(snapshot.PlayerBuffs);
        Assert.Empty(snapshot.PlayerDebuffs);
        Assert.Empty(snapshot.TargetBuffs);
        Assert.Empty(snapshot.TargetDebuffs);
    }

    [Fact]
    public void ZeroValuedFields_ArePreserved()
    {
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.thin-live.lua"));

        Assert.Equal(0, snapshot.Player!.Charge);
        Assert.Equal(0, snapshot.Player.ChargeMax);
        Assert.Equal(0, snapshot.Player.ChargePct);
        Assert.Equal(0, snapshot.Player.Planar);
        Assert.Equal(0, snapshot.Player.PlanarPct);
        Assert.Equal(0, snapshot.Player.Cast!.ProgressPct);
    }

    [Fact]
    public void WaitingForPlayerFixture_FormatsWithoutPlayerSections()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.waiting-for-player.lua");
        var snapshot = AssertSnapshot(document);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.Equal("waiting-for-player", snapshot.Status);
        Assert.DoesNotContain("Player:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Target:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Player buffs:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void ReaderBridgeSparseFixture_ParsesPartialProbe()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.readerbridge-sparse.lua");
        var snapshot = AssertSnapshot(document);

        Assert.Equal("ReaderBridge", snapshot.SourceMode);
        Assert.NotNull(snapshot.OrientationProbe);
        Assert.NotNull(snapshot.OrientationProbe!.Player);
        Assert.Empty(snapshot.OrientationProbe.Player!.DetailCandidates);
        Assert.Empty(snapshot.OrientationProbe.Player.StateCandidates);
        Assert.NotNull(snapshot.OrientationProbe.Target);
        Assert.Empty(snapshot.OrientationProbe.StatCandidates);
    }

    [Theory]
    [InlineData("ReaderBridgeExport.thin-live.lua")]
    [InlineData("ReaderBridgeExport.waiting-for-player.lua")]
    [InlineData("ReaderBridgeExport.readerbridge-sparse.lua")]
    public void SparseFixtures_FormatWithoutEmptySectionNoise(string fixtureName)
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixtureName);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.DoesNotContain("Nearby units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Party units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Player aura detail:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Target aura detail:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void InvalidScalarTypes_AreIgnoredInsteadOfCoerced()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 18, lastReason = "bad-scalars", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "bad-scalars",
    generatedAtRealtime = 18,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = {
      id = "p",
      name = "BadScalars",
      level = "70",
      combat = "true",
      hp = "100",
      charge = "9",
    },
    playerStats = {
      attackPower = "1234.5",
      critPower = true,
    },
    nearbySummary = {
      scannedCount = "3",
      relationCounts = {
        hostile = "1",
        friendly = true,
      },
    },
    playerBuffs = {
      {
        id = "buff1",
        name = "Bad Buff",
        remaining = "12.5",
        stack = "2",
      },
    },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(InvalidScalarTypes_AreIgnoredInsteadOfCoerced), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Equal("BadScalars", snapshot.Player!.Name);
        Assert.Null(snapshot.Player.Level);
        Assert.Null(snapshot.Player.Combat);
        Assert.Null(snapshot.Player.Hp);
        Assert.Null(snapshot.Player.Charge);
        Assert.Empty(snapshot.PlayerStats);
        Assert.NotNull(snapshot.NearbySummary);
        Assert.Null(snapshot.NearbySummary!.ScannedCount);
        Assert.Empty(snapshot.NearbySummary.RelationCounts);
        Assert.Single(snapshot.PlayerBuffs);
        Assert.Null(snapshot.PlayerBuffs[0].Remaining);
        Assert.Null(snapshot.PlayerBuffs[0].Stack);
    }

    [Fact]
    public void PlayerFlags_FormatInStablePriorityOrder()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 19, lastReason = "flag-order", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "flag-order",
    generatedAtRealtime = 19,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = {
      id = "p",
      name = "Flaggy",
      level = 70,
      combat = true,
      pvp = true,
      mounted = true,
      aggro = true,
      tagged = true,
      hp = 10,
      hpMax = 20,
    },
    playerStats = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(PlayerFlags_FormatInStablePriorityOrder), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.Contains("Player flags:            combat, pvp, mounted, aggro, tagged", text, StringComparison.Ordinal);
    }

    [Fact]
    public void TargetlessSummaryPresent_FormatsSummaryWithoutTargetSection()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 20, lastReason = "targetless-summary", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "targetless-summary",
    generatedAtRealtime = 20,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "SummaryOnly", level = 1 },
    nearbySummary = { scannedCount = 5, exportedCount = 2, playerCount = 1, combatCount = 1, pvpCount = 0, relationCounts = {} },
    partySummary = { exportedCount = 1, combatCount = 0, pvpCount = 0, relationCounts = {} },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(TargetlessSummaryPresent_FormatsSummaryWithoutTargetSection), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.DoesNotContain("Target:", text, StringComparison.Ordinal);
        Assert.Contains("Nearby units:            scanned 5, exported 2, players 1, combat 1", text, StringComparison.Ordinal);
        Assert.Contains("Party units:             exported 1, combat 0, pvp 0", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FrozenFormatterOutput_MatchesGoldenText()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.NormalizeForGolden(
            ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.frozen.lua"),
            "ReaderBridgeExport.frozen.lua");
        var text = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.frozen.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void DirectApiFormatterOutput_MatchesGoldenText()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.NormalizeForGolden(
            ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.directapi-golden.lua"),
            "ReaderBridgeExport.directapi-golden.lua");
        var text = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.directapi-golden.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void ReaderBridgeSnapshotCli_ParsesFrozenFixture()
    {
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath("ReaderBridgeExport.frozen.lua");
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        using var json = System.Text.Json.JsonDocument.Parse(result.StandardOutput);
        var root = json.RootElement;
        Assert.Equal(FrozenSchemaVersion, root.GetProperty("SchemaVersion").GetInt32());
        Assert.Equal("manual-freeze", root.GetProperty("LastReason").GetString());
        Assert.Equal("Atank", root.GetProperty("Current").GetProperty("Player").GetProperty("Name").GetString());
        Assert.Equal("ReaderBridge", root.GetProperty("Current").GetProperty("SourceMode").GetString());
    }

    [Fact]
    public void ReaderBridgeSnapshotCli_TextMode_MatchesGoldenOutput()
    {
        const string fixtureName = "ReaderBridgeExport.directapi-golden.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expectedFormatterText = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.directapi-golden.expected.txt");
        var expectedCliText = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(
            $"RiftReader.Reader{Environment.NewLine}" +
            "Use this tool only against Rift client processes you explicitly intend to inspect." +
            $"{Environment.NewLine}{Environment.NewLine}{expectedFormatterText}");

        Assert.Equal(
            expectedCliText,
            ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliText(result.StandardOutput, fixturePath, fixtureName));
    }

    [Fact]
    public void MissingCurrentSnapshot_DocumentLoadsWithNullCurrent()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = {
    lastExportAt = 18,
    lastReason = "missing-current",
    exportCount = 3,
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingCurrentSnapshot_DocumentLoadsWithNullCurrent), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal(FrozenSchemaVersion, document.SchemaVersion);
        Assert.Equal("missing-current", document.LastReason);
        Assert.Null(document.Current);
    }

    [Fact]
    public void WrongRootVariable_IsRejected()
    {
        const string fixtureText = """
WrongRoot = {
  schemaVersion = 1,
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(WrongRootVariable_IsRejected), fixtureText);
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixture.Path, out var error);

        Assert.Null(document);
        Assert.Contains("Unexpected root variable", error, StringComparison.Ordinal);
        Assert.Contains("ReaderBridgeExport_State", error, StringComparison.Ordinal);
    }

    [Fact]
    public void NonTableRootValue_IsRejected()
    {
        const string fixtureText = """
ReaderBridgeExport_State = "bad-root"
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NonTableRootValue_IsRejected), fixtureText);
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixture.Path, out var error);

        Assert.Null(document);
        Assert.Contains("Unexpected root value", error, StringComparison.Ordinal);
    }

    [Fact]
    public void ExtraFields_AreIgnoredWithoutBreakingKnownFields()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  extraRoot = "ignore-me",
  session = {
    lastExportAt = 99,
    lastReason = "extra-fields",
    exportCount = 5,
    mystery = { deep = true },
  },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "extra-fields",
    generatedAtRealtime = 99,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = {
      id = "player.extra",
      name = "Extra",
      level = 1,
      unexpectedScalar = "ignore-me",
      unexpectedTable = {
        nested = 123,
      },
    },
    nearbyUnits = {
      {
        id = "u1",
        name = "Unit One",
        relation = "friendly",
        bonus = "ignored",
      },
    },
    futureBlock = {
      anything = "goes",
    },
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(ExtraFields_AreIgnoredWithoutBreakingKnownFields), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal("Extra", document.Current!.Player!.Name);
        Assert.Single(document.Current.NearbyUnits);
        Assert.Equal("Unit One", document.Current.NearbyUnits[0].Name);
    }

    [Fact]
    public void MissingPlayerStats_MapsToEmptyDictionary()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 11, lastReason = "missing-stats", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "missing-stats",
    generatedAtRealtime = 11,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "NoStats", level = 1 },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingPlayerStats_MapsToEmptyDictionary), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Empty(snapshot.PlayerStats);
    }

    [Fact]
    public void MissingBuffLineArrays_MapsToEmptyLists()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 12, lastReason = "missing-buff-lines", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "missing-buff-lines",
    generatedAtRealtime = 12,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "NoLines", level = 1 },
    playerBuffs = { { id = "b1", name = "Structured Only" } },
    playerDebuffs = {},
    targetBuffs = {},
    targetDebuffs = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingBuffLineArrays_MapsToEmptyLists), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Empty(snapshot.PlayerBuffLines);
        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Structured Only", snapshot.PlayerBuffs[0].Name);
    }

    [Fact]
    public void AuraMissingFixture_BackCompatMapsStructuredAuraCollectionsToEmpty()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.legacy-aura-missing.lua");
        var snapshot = AssertSnapshot(document);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.Single(snapshot.PlayerBuffLines);
        Assert.Empty(snapshot.PlayerBuffs);
        Assert.DoesNotContain("Player aura detail:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void SummaryMissingFixture_BackCompatFormatsWithoutSummarySections()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.legacy-summary-missing.lua");
        var snapshot = AssertSnapshot(document);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.Null(snapshot.NearbySummary);
        Assert.Null(snapshot.PartySummary);
        Assert.DoesNotContain("Nearby units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Party units:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void EmptyRelationCounts_MapToEmptyDictionary()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 15, lastReason = "empty-relations", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "empty-relations",
    generatedAtRealtime = 15,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Relations", level = 1 },
    nearbySummary = {
      scannedCount = 0,
      exportedCount = 0,
      playerCount = 0,
      combatCount = 0,
      pvpCount = 0,
      relationCounts = {},
    },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(EmptyRelationCounts_MapToEmptyDictionary), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.NearbySummary);
        Assert.Empty(snapshot.NearbySummary!.RelationCounts);
    }

    [Fact]
    public void PartialOrientationProbe_MissingNestedTablesMapsToEmptyCandidateLists()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 16, lastReason = "partial-probe", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "partial-probe",
    generatedAtRealtime = 16,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Probe", level = 1 },
    orientationProbe = {
      player = {
        source = "player",
        unitAvailable = true,
      },
      target = {
        source = "target",
      },
    },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(PartialOrientationProbe_MissingNestedTablesMapsToEmptyCandidateLists), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.OrientationProbe);
        Assert.Empty(snapshot.OrientationProbe!.Player!.DetailCandidates);
        Assert.Empty(snapshot.OrientationProbe.Player.StateCandidates);
        Assert.Empty(snapshot.OrientationProbe.Target!.DetailCandidates);
        Assert.Empty(snapshot.OrientationProbe.StatCandidates);
    }

    [Fact]
    public void NestedUnknownAuraFields_AreIgnored()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 17, lastReason = "nested-aura-extra", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "nested-aura-extra",
    generatedAtRealtime = 17,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Aura", level = 1 },
    playerBuffs = {
      {
        id = "buff1",
        name = "Future Buff",
        remaining = 10,
        duration = 15,
        flags = { "A", "B" },
        unknownNested = { x = 1, y = 2 },
      },
    },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NestedUnknownAuraFields_AreIgnored), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Future Buff", snapshot.PlayerBuffs[0].Name);
        Assert.Equal(2, snapshot.PlayerBuffs[0].Flags.Count);
    }

    private static ReaderBridgeSnapshot AssertSnapshot(ReaderBridgeSnapshotDocument document)
    {
        Assert.NotNull(document.Current);
        return document.Current!;
    }

}
