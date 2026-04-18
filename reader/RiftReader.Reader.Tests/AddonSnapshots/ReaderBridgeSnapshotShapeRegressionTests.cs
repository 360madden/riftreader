using RiftReader.Reader.AddonSnapshots;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotShapeRegressionTests
{
    [Fact]
    public void NonTableCurrentValue_MapsToNullCurrent()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = {
    lastExportAt = 21,
    lastReason = "current-not-table",
    exportCount = 4,
  },
  current = "bad-current",
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NonTableCurrentValue_MapsToNullCurrent), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal(1, document.SchemaVersion);
        Assert.Equal("current-not-table", document.LastReason);
        Assert.Null(document.Current);
    }

    [Fact]
    public void NonTableSessionValue_PreservesDocumentWithEmptySessionMetadata()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = "bad-session",
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "bad-session",
    generatedAtRealtime = 22,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "NoSession", level = 1 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NonTableSessionValue_PreservesDocumentWithEmptySessionMetadata), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Null(document.LastExportAt);
        Assert.Null(document.LastReason);
        Assert.Null(document.ExportCount);
        Assert.NotNull(document.Current);
        Assert.Equal("NoSession", document.Current!.Player!.Name);
    }

    [Fact]
    public void MissingCurrentSchemaVersion_LeavesSnapshotSchemaNull()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 23, lastReason = "missing-current-schema", exportCount = 1 },
  current = {
    status = "ready",
    exportReason = "missing-current-schema",
    generatedAtRealtime = 23,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "MissingSchema", level = 1 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingCurrentSchemaVersion_LeavesSnapshotSchemaNull), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal(1, document.SchemaVersion);
        Assert.NotNull(document.Current);
        Assert.Null(document.Current!.SchemaVersion);
    }

    [Fact]
    public void WrongTypeCurrentSchemaVersion_LeavesSnapshotSchemaNull()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 24, lastReason = "bad-current-schema", exportCount = 1 },
  current = {
    schemaVersion = "one",
    status = "ready",
    exportReason = "bad-current-schema",
    generatedAtRealtime = 24,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "BadSchema", level = 1 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(WrongTypeCurrentSchemaVersion_LeavesSnapshotSchemaNull), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal(1, document.SchemaVersion);
        Assert.NotNull(document.Current);
        Assert.Null(document.Current!.SchemaVersion);
    }

    [Fact]
    public void RootAndCurrentSchemaVersions_CanDifferWithoutBreakingLoad()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 25, lastReason = "schema-mismatch", exportCount = 1 },
  current = {
    schemaVersion = 99,
    status = "ready",
    exportReason = "schema-mismatch",
    generatedAtRealtime = 25,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "SchemaMismatch", level = 1 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(RootAndCurrentSchemaVersions_CanDifferWithoutBreakingLoad), fixtureText);
        var document = ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path);

        Assert.Equal(1, document.SchemaVersion);
        Assert.Equal(99, document.Current!.SchemaVersion);
    }

    [Fact]
    public void NonNumericRelationCounts_AreIgnored()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 26, lastReason = "relation-count-types", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "relation-count-types",
    generatedAtRealtime = 26,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Relations", level = 1 },
    nearbySummary = {
      scannedCount = 3,
      relationCounts = {
        hostile = "1",
        friendly = true,
        neutral = 2,
      },
    },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NonNumericRelationCounts_AreIgnored), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.NearbySummary);
        Assert.Single(snapshot.NearbySummary!.RelationCounts);
        Assert.Equal(2, snapshot.NearbySummary.RelationCounts["neutral"]);
    }

    [Fact]
    public void MalformedNearbyUnitEntries_AreSkipped()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 27, lastReason = "bad-nearby", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "bad-nearby",
    generatedAtRealtime = 27,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Nearby", level = 1 },
    nearbyUnits = {
      "bad-entry",
      { id = "u1", name = "Good Unit" },
      42,
    },
    playerStats = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MalformedNearbyUnitEntries_AreSkipped), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.NearbyUnits);
        Assert.Equal("Good Unit", snapshot.NearbyUnits[0].Name);
    }

    [Fact]
    public void MalformedPartyUnitEntries_AreSkipped()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 28, lastReason = "bad-party", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "bad-party",
    generatedAtRealtime = 28,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Party", level = 1 },
    partyUnits = {
      false,
      { id = "g1", name = "Good Party Unit" },
      "bad-entry",
    },
    playerStats = {},
    nearbyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MalformedPartyUnitEntries_AreSkipped), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.PartyUnits);
        Assert.Equal("Good Party Unit", snapshot.PartyUnits[0].Name);
    }

    [Fact]
    public void MalformedAuraEntries_AreSkippedWhilePartialTablesStillMap()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 29, lastReason = "bad-aura", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "bad-aura",
    generatedAtRealtime = 29,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Aura", level = 1 },
    playerBuffs = {
      "bad-entry",
      { id = "buff1", name = "Good Buff" },
      123,
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MalformedAuraEntries_AreSkippedWhilePartialTablesStillMap), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Good Buff", snapshot.PlayerBuffs[0].Name);
    }

    [Fact]
    public void OrientationProbeScalarCandidates_FallBackToValueOnlyEntries()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 30, lastReason = "scalar-probe", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "scalar-probe",
    generatedAtRealtime = 30,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Probe", level = 1 },
    orientationProbe = {
      statCandidates = {
        "headingGuess",
        90,
      },
    },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(OrientationProbeScalarCandidates_FallBackToValueOnlyEntries), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.OrientationProbe);
        Assert.Equal(2, snapshot.OrientationProbe!.StatCandidates.Count);
        Assert.Null(snapshot.OrientationProbe.StatCandidates[0].Key);
        Assert.Equal("headingGuess", snapshot.OrientationProbe.StatCandidates[0].Value);
        Assert.Null(snapshot.OrientationProbe.StatCandidates[1].Key);
        Assert.Equal("90", snapshot.OrientationProbe.StatCandidates[1].Value);
    }

    [Fact]
    public void MissingPlayerStatsAndSummaries_TogetherStayEmptyAndNull()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 41, lastReason = "multi-gap-stats-summary", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "multi-gap-stats-summary",
    generatedAtRealtime = 41,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Sparse", level = 1 },
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingPlayerStatsAndSummaries_TogetherStayEmptyAndNull), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Empty(snapshot.PlayerStats);
        Assert.Null(snapshot.NearbySummary);
        Assert.Null(snapshot.PartySummary);
    }

    [Fact]
    public void MissingBuffLinesAndStructuredBuffs_TogetherStayEmpty()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 42, lastReason = "multi-gap-buffs", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "multi-gap-buffs",
    generatedAtRealtime = 42,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "NoBuffs", level = 1 },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingBuffLinesAndStructuredBuffs_TogetherStayEmpty), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Empty(snapshot.PlayerBuffLines);
        Assert.Empty(snapshot.PlayerDebuffLines);
        Assert.Empty(snapshot.TargetBuffLines);
        Assert.Empty(snapshot.TargetDebuffLines);
        Assert.Empty(snapshot.PlayerBuffs);
        Assert.Empty(snapshot.PlayerDebuffs);
        Assert.Empty(snapshot.TargetBuffs);
        Assert.Empty(snapshot.TargetDebuffs);
    }

    [Fact]
    public void MissingTargetBlock_WithLegacyTargetLines_DoesNotCreateTarget()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 43, lastReason = "target-lines-no-target", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "target-lines-no-target",
    generatedAtRealtime = 43,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "NoTarget", level = 1 },
    targetBuffLines = { "Legacy Target Buff" },
    targetDebuffLines = { "Legacy Target Debuff" },
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(MissingTargetBlock_WithLegacyTargetLines_DoesNotCreateTarget), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Null(snapshot.Target);
        Assert.Single(snapshot.TargetBuffLines);
        Assert.Single(snapshot.TargetDebuffLines);
    }

    [Fact]
    public void TargetWithoutTargetId_StillLoadsTargetBody()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 44, lastReason = "target-no-id", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "target-no-id",
    generatedAtRealtime = 44,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    target = { name = "BodyOnly", level = 2 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(TargetWithoutTargetId_StillLoadsTargetBody), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.Target);
        Assert.Null(snapshot.Target!.Id);
        Assert.Equal("BodyOnly", snapshot.Target.Name);
    }

    [Fact]
    public void PartyUnitsWithoutPartySummary_StillLoad()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 45, lastReason = "party-no-summary", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "party-no-summary",
    generatedAtRealtime = 45,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    partyUnits = { { id = "g1", name = "Party Member" } },
    playerStats = {},
    nearbyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(PartyUnitsWithoutPartySummary_StillLoad), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Null(snapshot.PartySummary);
        Assert.Single(snapshot.PartyUnits);
    }

    [Fact]
    public void NearbyUnitsWithoutNearbySummary_StillLoad()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 46, lastReason = "nearby-no-summary", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "nearby-no-summary",
    generatedAtRealtime = 46,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    nearbyUnits = { { id = "u1", name = "Nearby Unit" } },
    playerStats = {},
    partyUnits = {},
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
  },
}
""";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NearbyUnitsWithoutNearbySummary_StillLoad), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Null(snapshot.NearbySummary);
        Assert.Single(snapshot.NearbyUnits);
    }

    [Fact]
    public void SummaryCountsAsStrings_AreIgnored()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 47, lastReason = "summary-string-counts", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "summary-string-counts",
    generatedAtRealtime = 47,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Player", level = 1 },
    nearbySummary = {
      scannedCount = "3",
      exportedCount = "2",
      playerCount = "1",
      combatCount = "1",
      pvpCount = "0",
      relationCounts = {},
    },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(SummaryCountsAsStrings_AreIgnored), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.NearbySummary);
        Assert.Null(snapshot.NearbySummary!.ScannedCount);
        Assert.Null(snapshot.NearbySummary.ExportedCount);
        Assert.Null(snapshot.NearbySummary.PlayerCount);
        Assert.Null(snapshot.NearbySummary.CombatCount);
        Assert.Null(snapshot.NearbySummary.PvpCount);
    }

    [Fact]
    public void NumericUnitIds_AreIgnoredInsteadOfCoerced()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 48, lastReason = "numeric-unit-id", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "numeric-unit-id",
    generatedAtRealtime = 48,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = 12345, name = "NumericId", level = 1 },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(NumericUnitIds_AreIgnoredInsteadOfCoerced), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.NotNull(snapshot.Player);
        Assert.Null(snapshot.Player!.Id);
        Assert.Equal("NumericId", snapshot.Player.Name);
    }

    [Fact]
    public void AuraFlags_NonListObjectMapsToEmptyFlags()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 49, lastReason = "flags-object", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "flags-object",
    generatedAtRealtime = 49,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Aura", level = 1 },
    playerBuffs = {
      {
        id = "buff1",
        name = "Buff",
        flags = { note = "not-a-list" },
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(AuraFlags_NonListObjectMapsToEmptyFlags), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Empty(snapshot.PlayerBuffs[0].Flags);
    }

    [Fact]
    public void AuraFlags_EmptyListStaysEmpty()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 50, lastReason = "flags-empty", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "flags-empty",
    generatedAtRealtime = 50,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "Aura", level = 1 },
    playerBuffs = {
      {
        id = "buff1",
        name = "Buff",
        flags = {},
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

        using var fixture = ReaderBridgeTempFixture.Create(nameof(AuraFlags_EmptyListStaysEmpty), fixtureText);
        var snapshot = AssertSnapshot(ReaderBridgeSnapshotLoaderTestSupport.LoadFixture(fixture.Path));

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Empty(snapshot.PlayerBuffs[0].Flags);
    }

    private static ReaderBridgeSnapshot AssertSnapshot(ReaderBridgeSnapshotDocument document)
    {
        Assert.NotNull(document.Current);
        return document.Current!;
    }
}
