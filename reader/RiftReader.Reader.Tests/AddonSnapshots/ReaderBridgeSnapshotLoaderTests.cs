using System.Diagnostics;
using System.Text.Json;
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
        var fixturePath = GetFixturePath("ReaderBridgeExport.frozen.lua");

        var document = ReaderBridgeSnapshotLoader.TryLoad(fixturePath, out var error);

        Assert.NotNull(document);
        Assert.True(string.IsNullOrWhiteSpace(error), error);
        Assert.Equal(FrozenSchemaVersion, document!.SchemaVersion);
        Assert.Equal("manual-freeze", document.LastReason);
        Assert.Equal(17, document.ExportCount);

        var snapshot = document.Current;
        Assert.NotNull(snapshot);
        Assert.Equal(FrozenSchemaVersion, snapshot!.SchemaVersion);
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
    public void SparseFixture_MissingCollections_MapToEmptyContainers()
    {
        const string fixtureText = """
ReaderBridgeExport_State = {
  schemaVersion = 1,
  session = {
    lastExportAt = 42,
    lastReason = "sparse",
    exportCount = 2,
  },
  current = {
    schemaVersion = 1,
    status = "waiting-for-player",
    exportReason = "sparse",
    generatedAtRealtime = 42,
    sourceMode = "ReaderBridge",
    sourceAddon = "ReaderBridge",
    exportAddon = "ReaderBridgeExport",
    exportVersion = "0.1.0-test",
  },
}
""";

        var fixturePath = WriteTempFixture(nameof(SparseFixture_MissingCollections_MapToEmptyContainers), fixtureText);

        try
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(fixturePath, out var error);

            Assert.NotNull(document);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
            Assert.NotNull(document!.Current);
            Assert.Equal(FrozenSchemaVersion, document.Current!.SchemaVersion);
            Assert.Empty(document.Current.PlayerStats);
            Assert.Empty(document.Current.NearbyUnits);
            Assert.Empty(document.Current.PartyUnits);
            Assert.Empty(document.Current.PlayerBuffLines);
            Assert.Empty(document.Current.PlayerDebuffLines);
            Assert.Empty(document.Current.TargetBuffLines);
            Assert.Empty(document.Current.TargetDebuffLines);
            Assert.Empty(document.Current.PlayerBuffs);
            Assert.Empty(document.Current.PlayerDebuffs);
            Assert.Empty(document.Current.TargetBuffs);
            Assert.Empty(document.Current.TargetDebuffs);
        }
        finally
        {
            TryDeleteFile(fixturePath);
        }
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
    public void ThinLiveFixture_ParsesAndKeepsEmptyCollectionsStable()
    {
        var fixturePath = GetFixturePath("ReaderBridgeExport.thin-live.lua");

        var document = ReaderBridgeSnapshotLoader.TryLoad(fixturePath, out var error);

        Assert.NotNull(document);
        Assert.True(string.IsNullOrWhiteSpace(error), error);
        Assert.NotNull(document!.Current);
        Assert.Equal(FrozenSchemaVersion, document.SchemaVersion);
        Assert.Equal("save-begin", document.LastReason);
        Assert.Equal(931, document.ExportCount);

        var snapshot = document.Current!;
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

        var fixturePath = WriteTempFixture(nameof(ExtraFields_AreIgnoredWithoutBreakingKnownFields), fixtureText);

        try
        {
            var document = ReaderBridgeSnapshotLoader.TryLoad(fixturePath, out var error);

            Assert.NotNull(document);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
            Assert.NotNull(document!.Current);
            Assert.Equal("Extra", document.Current!.Player!.Name);
            Assert.Single(document.Current.NearbyUnits);
            Assert.Equal("Unit One", document.Current.NearbyUnits[0].Name);
        }
        finally
        {
            TryDeleteFile(fixturePath);
        }
    }

    [Fact]
    public void Formatter_HandlesThinSnapshotWithoutEmptySectionNoise()
    {
        var fixturePath = GetFixturePath("ReaderBridgeExport.thin-live.lua");
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixturePath, out var error);

        Assert.NotNull(document);
        Assert.True(string.IsNullOrWhiteSpace(error), error);

        var text = ReaderBridgeSnapshotTextFormatter.Format(document!);

        Assert.Contains("Player:                  Atank (Lv45)", text);
        Assert.Contains("Player buffs:            Rested | Track Fish", text);
        Assert.DoesNotContain("Nearby units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Party units:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Player aura detail:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Target aura detail:", text, StringComparison.Ordinal);
    }

    private static string GetFixturePath(string fileName) =>
        Path.Combine(
            FindRepoRoot(),
            "reader",
            "RiftReader.Reader.Tests",
            "AddonSnapshots",
            "Fixtures",
            fileName);

    private static string WriteTempFixture(string testName, string content)
    {
        var path = Path.Combine(
            Path.GetTempPath(),
            "RiftReader",
            "readerbridge-tests",
            $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmssfff}-{testName}-{Guid.NewGuid():N}.lua");
        var directory = Path.GetDirectoryName(path)!;
        Directory.CreateDirectory(directory);
        File.WriteAllText(path, content);
        return path;
    }

    private static void TryDeleteFile(string filePath)
    {
        try
        {
            if (File.Exists(filePath))
            {
                File.Delete(filePath);
            }
        }
        catch
        {
            // Best-effort cleanup only.
        }
    }

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
}
