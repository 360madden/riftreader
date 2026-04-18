using System.Diagnostics;
using System.Text.RegularExpressions;
using System.Text.Json;
using System.Text.Json.Nodes;
using RiftReader.Reader.AddonSnapshots;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

internal static class ReaderBridgeSnapshotLoaderTestSupport
{
    internal static readonly DateTimeOffset GoldenLoadedAtUtc = new(2026, 4, 18, 0, 0, 0, TimeSpan.Zero);

    internal static ReaderBridgeSnapshotDocument LoadFixture(string fixtureNameOrPath)
    {
        var path = fixtureNameOrPath.EndsWith(".lua", StringComparison.OrdinalIgnoreCase) && File.Exists(fixtureNameOrPath)
            ? fixtureNameOrPath
            : GetFixturePath(fixtureNameOrPath);

        var document = ReaderBridgeSnapshotLoader.TryLoad(path, out var error);
        Assert.NotNull(document);
        Assert.True(string.IsNullOrWhiteSpace(error), error);
        return document!;
    }

    internal static ReaderBridgeSnapshotDocument NormalizeForGolden(ReaderBridgeSnapshotDocument document, string fixtureName) =>
        document with
        {
            SourceFile = fixtureName,
            LoadedAtUtc = GoldenLoadedAtUtc
        };

    internal static string ReadExpectedText(string fileName) =>
        NormalizeText(File.ReadAllText(GetFixturePath(fileName)));

    internal static string ReadExpectedJson(string fileName) =>
        NormalizeText(File.ReadAllText(GetFixturePath(fileName)));

    internal static string NormalizeCliText(string text, string fixturePath, string fixtureName)
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

    internal static string NormalizeCliJson(string text, string fixtureName)
    {
        var node = JsonNode.Parse(text) as JsonObject
            ?? throw new InvalidOperationException("Expected CLI JSON output to be an object.");

        node["SourceFile"] = fixtureName;
        node["LoadedAtUtc"] = GoldenLoadedAtUtc.ToString("O");

        return NormalizeText(node.ToJsonString(new JsonSerializerOptions
        {
            WriteIndented = true
        }));
    }

    internal static string NormalizeText(string value) =>
        value.Replace("\r\n", "\n", StringComparison.Ordinal).TrimEnd();

    internal static string GetFixturePath(string fileName) =>
        Path.Combine(
            FindRepoRoot(),
            "reader",
            "RiftReader.Reader.Tests",
            "AddonSnapshots",
            "Fixtures",
            fileName);

    internal static CommandResult RunReader(IReadOnlyList<string> args)
    {
        var repoRoot = FindRepoRoot();
        var projectPath = Path.Combine(repoRoot, "reader", "RiftReader.Reader", "RiftReader.Reader.csproj");
        var command = BuildDotnetRunArguments(projectPath, args);
        return RunProcess("dotnet", command, repoRoot, timeoutMilliseconds: 20_000);
    }

    internal static string FindRepoRoot()
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

    internal static string Quote(string value) =>
        $"\"{value.Replace("\"", "\\\"", StringComparison.Ordinal)}\"";

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

    internal readonly record struct CommandResult(int ExitCode, string StandardOutput, string StandardError);
}

internal sealed class ReaderBridgeTempFixture : IDisposable
{
    private ReaderBridgeTempFixture(string path)
    {
        Path = path;
    }

    public string Path { get; }

    public static ReaderBridgeTempFixture Create(string testName, string content)
    {
        var path = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "RiftReader",
            "readerbridge-tests",
            $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmssfff}-{testName}-{Guid.NewGuid():N}.lua");
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
        return new ReaderBridgeTempFixture(path);
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
