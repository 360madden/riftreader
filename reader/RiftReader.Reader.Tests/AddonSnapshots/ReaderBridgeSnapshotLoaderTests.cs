using System.Diagnostics;
using System.Text.Json;
using System.Text.RegularExpressions;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotLoaderTests
{
    private const int FrozenSchemaVersion = 1;
    private static readonly DateTimeOffset GoldenLoadedAtUtc = new(2026, 4, 18, 0, 0, 0, TimeSpan.Zero);

    [Fact]
    public void FrozenFixture_ParsesCurrentSchema()
    {
        var document = LoadFixture("ReaderBridgeExport.frozen.lua");
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
        var document = LoadFixture("ReaderBridgeExport.directapi-golden.lua");
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
        var document = LoadFixture("ReaderBridgeExport.thin-live.lua");
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
        var snapshot = AssertSnapshot(LoadFixture("ReaderBridgeExport.thin-live.lua"));

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
        var document = LoadFixture("ReaderBridgeExport.waiting-for-player.lua");
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
        var document = LoadFixture("ReaderBridgeExport.readerbridge-sparse.lua");
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
        var document = LoadFixture(fixtureName);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.DoesNotContain("Nearby units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Party units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Player aura detail:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Target aura detail:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void FrozenFormatterOutput_MatchesGoldenText()
    {
        var document = NormalizeForGolden(LoadFixture("ReaderBridgeExport.frozen.lua"), "ReaderBridgeExport.frozen.lua");
        var text = NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReadExpectedText("ReaderBridgeExport.frozen.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void DirectApiFormatterOutput_MatchesGoldenText()
    {
        var document = NormalizeForGolden(LoadFixture("ReaderBridgeExport.directapi-golden.lua"), "ReaderBridgeExport.directapi-golden.lua");
        var text = NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReadExpectedText("ReaderBridgeExport.directapi-golden.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void ReaderBridgeSnapshotCli_ParsesFrozenFixture()
    {
        var fixturePath = GetFixturePath("ReaderBridgeExport.frozen.lua");
        var result = RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        using var json = JsonDocument.Parse(result.StandardOutput);
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
        var fixturePath = GetFixturePath(fixtureName);
        var result = RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expectedFormatterText = ReadExpectedText("ReaderBridgeExport.directapi-golden.expected.txt");
        var expectedCliText = NormalizeText(
            $"RiftReader.Reader{Environment.NewLine}" +
            "Use this tool only against Rift client processes you explicitly intend to inspect." +
            $"{Environment.NewLine}{Environment.NewLine}{expectedFormatterText}");

        Assert.Equal(expectedCliText, NormalizeCliText(result.StandardOutput, fixturePath, fixtureName));
    }

    [Fact]
    public void WrongRootVariable_IsRejected()
    {
        const string fixtureText = """
WrongRoot = {
  schemaVersion = 1,
}
""";

        using var fixture = TempFixture.Create(nameof(WrongRootVariable_IsRejected), fixtureText);
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixture.Path, out var error);

        Assert.Null(document);
        Assert.Contains("Unexpected root variable", error, StringComparison.Ordinal);
        Assert.Contains("ReaderBridgeExport_State", error, StringComparison.Ordinal);
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

        using var fixture = TempFixture.Create(nameof(ExtraFields_AreIgnoredWithoutBreakingKnownFields), fixtureText);
        var document = LoadFixture(fixture.Path);

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

        using var fixture = TempFixture.Create(nameof(MissingPlayerStats_MapsToEmptyDictionary), fixtureText);
        var snapshot = AssertSnapshot(LoadFixture(fixture.Path));

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

        using var fixture = TempFixture.Create(nameof(MissingBuffLineArrays_MapsToEmptyLists), fixtureText);
        var snapshot = AssertSnapshot(LoadFixture(fixture.Path));

        Assert.Empty(snapshot.PlayerBuffLines);
        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Structured Only", snapshot.PlayerBuffs[0].Name);
    }

    [Fact]
    public void AuraMissingFixture_BackCompatMapsStructuredAuraCollectionsToEmpty()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 13, lastReason = "aura-missing", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "aura-missing",
    generatedAtRealtime = 13,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "LegacyAura", level = 1 },
    playerBuffLines = { "Legacy Buff" },
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
    nearbyUnits = {},
    partyUnits = {},
  },
}
""";

        using var fixture = TempFixture.Create(nameof(AuraMissingFixture_BackCompatMapsStructuredAuraCollectionsToEmpty), fixtureText);
        var document = LoadFixture(fixture.Path);
        var snapshot = AssertSnapshot(document);
        var text = ReaderBridgeSnapshotTextFormatter.Format(document);

        Assert.Single(snapshot.PlayerBuffLines);
        Assert.Empty(snapshot.PlayerBuffs);
        Assert.DoesNotContain("Player aura detail:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void SummaryMissingFixture_BackCompatFormatsWithoutSummarySections()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = { lastExportAt = 14, lastReason = "summary-missing", exportCount = 1 },
  current = {
    schemaVersion = 1,
    status = "ready",
    exportReason = "summary-missing",
    generatedAtRealtime = 14,
    sourceMode = "DirectAPI",
    sourceAddon = "RiftAPI",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
    player = { id = "p", name = "LegacySummary", level = 1 },
    nearbyUnits = { { id = "u1", name = "Unit One" } },
    partyUnits = { { id = "g1", name = "Unit Two" } },
    playerBuffLines = {},
    playerDebuffLines = {},
    targetBuffLines = {},
    targetDebuffLines = {},
    playerStats = {},
  },
}
""";

        using var fixture = TempFixture.Create(nameof(SummaryMissingFixture_BackCompatFormatsWithoutSummarySections), fixtureText);
        var document = LoadFixture(fixture.Path);
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

        using var fixture = TempFixture.Create(nameof(EmptyRelationCounts_MapToEmptyDictionary), fixtureText);
        var snapshot = AssertSnapshot(LoadFixture(fixture.Path));

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

        using var fixture = TempFixture.Create(nameof(PartialOrientationProbe_MissingNestedTablesMapsToEmptyCandidateLists), fixtureText);
        var snapshot = AssertSnapshot(LoadFixture(fixture.Path));

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

        using var fixture = TempFixture.Create(nameof(NestedUnknownAuraFields_AreIgnored), fixtureText);
        var snapshot = AssertSnapshot(LoadFixture(fixture.Path));

        Assert.Single(snapshot.PlayerBuffs);
        Assert.Equal("Future Buff", snapshot.PlayerBuffs[0].Name);
        Assert.Equal(2, snapshot.PlayerBuffs[0].Flags.Count);
    }

    private static ReaderBridgeSnapshotDocument LoadFixture(string fixtureNameOrPath)
    {
        var path = fixtureNameOrPath.EndsWith(".lua", StringComparison.OrdinalIgnoreCase) && File.Exists(fixtureNameOrPath)
            ? fixtureNameOrPath
            : GetFixturePath(fixtureNameOrPath);

        var document = ReaderBridgeSnapshotLoader.TryLoad(path, out var error);
        Assert.NotNull(document);
        Assert.True(string.IsNullOrWhiteSpace(error), error);
        return document!;
    }

    private static ReaderBridgeSnapshotDocument NormalizeForGolden(ReaderBridgeSnapshotDocument document, string fixtureName) =>
        document with
        {
            SourceFile = fixtureName,
            LoadedAtUtc = GoldenLoadedAtUtc
        };

    private static ReaderBridgeSnapshot AssertSnapshot(ReaderBridgeSnapshotDocument document)
    {
        Assert.NotNull(document.Current);
        return document.Current!;
    }

    private static string ReadExpectedText(string fileName) =>
        NormalizeText(File.ReadAllText(GetFixturePath(fileName)));

    private static string NormalizeCliText(string text, string fixturePath, string fixtureName)
    {
        var normalized = NormalizeText(text)
            .Replace(fixturePath.Replace('\\', '/'), fixtureName, StringComparison.Ordinal)
            .Replace(fixturePath, fixtureName, StringComparison.Ordinal);

        return Regex.Replace(
            normalized,
            @"Loaded at \(UTC\):\s+.+",
            $"Loaded at (UTC):         {GoldenLoadedAtUtc:O}",
            RegexOptions.CultureInvariant);
    }

    private static string NormalizeText(string value) =>
        value.Replace("\r\n", "\n", StringComparison.Ordinal).TrimEnd();

    private static string GetFixturePath(string fileName) =>
        Path.Combine(
            FindRepoRoot(),
            "reader",
            "RiftReader.Reader.Tests",
            "AddonSnapshots",
            "Fixtures",
            fileName);

    private static CommandResult RunReader(IReadOnlyList<string> args)
    {
        var repoRoot = FindRepoRoot();
        var projectPath = Path.Combine(repoRoot, "reader", "RiftReader.Reader", "RiftReader.Reader.csproj");
        var command = BuildDotnetRunArguments(projectPath, args);
        return RunProcess("dotnet", command, repoRoot, timeoutMilliseconds: 20_000);
    }

    private static string BuildDotnetRunArguments(string projectPath, IReadOnlyList<string> args)
    {
        var suffix = string.Join(" ", args.Select(Quote));
        return $"run --project {Quote(projectPath)} --no-build -- {suffix}";
    }

    private static CommandResult RunProcess(string fileName, string arguments, string workingDirectory, int timeoutMilliseconds)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                WorkingDirectory = workingDirectory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            }
        };

        if (!process.Start())
        {
            throw new InvalidOperationException($"Unable to start '{fileName} {arguments}'.");
        }

        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();

        if (!process.WaitForExit(timeoutMilliseconds))
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Ignore cleanup failures in timeout handling.
            }

            throw new TimeoutException($"Process '{fileName} {arguments}' timed out after {timeoutMilliseconds}ms.");
        }

        Task.WaitAll(stdoutTask, stderrTask);

        return new CommandResult(
            process.ExitCode,
            stdoutTask.GetAwaiter().GetResult(),
            stderrTask.GetAwaiter().GetResult());
    }

    private static string FindRepoRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        throw new InvalidOperationException("Unable to locate the repository root from the test output directory.");
    }

    private static string Quote(string value) =>
        $"\"{value.Replace("\"", "\\\"", StringComparison.Ordinal)}\"";

    private readonly record struct CommandResult(int ExitCode, string StandardOutput, string StandardError);

    private sealed class TempFixture : IDisposable
    {
        private TempFixture(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempFixture Create(string testName, string content)
        {
            var path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "RiftReader",
                "readerbridge-tests",
                $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmssfff}-{testName}-{Guid.NewGuid():N}.lua");
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
            return new TempFixture(path);
        }

        public void Dispose()
        {
            try
            {
                if (File.Exists(Path))
                {
                    File.Delete(Path);
                }
            }
            catch
            {
                // Best-effort cleanup only.
            }
        }
    }
}
