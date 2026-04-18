using System.Diagnostics;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSmokeScriptTests
{
    [Fact]
    public void MissingSnapshotFile_FailsWithStableError()
    {
        var missingPath = Path.Combine(
            Path.GetTempPath(),
            "RiftReader",
            "readerbridge-tests",
            $"{Guid.NewGuid():N}",
            "missing export.lua");

        var result = RunSmokeScript(["-SnapshotFile", missingPath, "-Json", "-NoBuild"]);

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("Snapshot file was not found", result.StandardError, StringComparison.Ordinal);
        Assert.DoesNotContain("System.Management.Automation", result.StandardError, StringComparison.Ordinal);
    }

    [Fact]
    public void MissingSnapshotFile_ReturnsExitCodeOne()
    {
        var missingPath = Path.Combine(
            Path.GetTempPath(),
            "RiftReader",
            "readerbridge-tests",
            $"{Guid.NewGuid():N}",
            "missing export.lua");

        var result = RunSmokeScript(["-SnapshotFile", missingPath, "-Json", "-NoBuild"]);

        Assert.Equal(1, result.ExitCode);
    }

    [Fact]
    public void MissingSnapshotFile_WritesOnlyStableMessageToStdErr()
    {
        var missingPath = Path.Combine(
            Path.GetTempPath(),
            "RiftReader",
            "readerbridge-tests",
            $"{Guid.NewGuid():N}",
            "missing export.lua");

        var result = RunSmokeScript(["-SnapshotFile", missingPath, "-Json", "-NoBuild"]);
        var expected = $"Snapshot file was not found: {Path.GetFullPath(missingPath)}";

        Assert.True(string.IsNullOrWhiteSpace(result.StandardOutput), result.StandardOutput);
        Assert.Equal(expected, result.StandardError.Trim());
    }

    [Fact]
    public void CorruptedFixtureFile_FailsWithParseError()
    {
        using var fixture = ReaderBridgeTempFixture.Create(nameof(CorruptedFixtureFile_FailsWithParseError), "ReaderBridgeExport_State = {");
        var result = RunSmokeScript(["-SnapshotFile", fixture.Path, "-Json", "-NoBuild"]);
        var combined = $"{result.StandardOutput}{Environment.NewLine}{result.StandardError}";

        Assert.NotEqual(0, result.ExitCode);
        Assert.Contains("Unexpected end of input while parsing a Lua value.", combined, StringComparison.Ordinal);
    }

    private static CommandResult RunSmokeScript(IReadOnlyList<string> args)
    {
        var repoRoot = ReaderBridgeSnapshotLoaderTestSupport.FindRepoRoot();
        var scriptPath = Path.Combine(repoRoot, "scripts", "smoke-readerbridge-export.ps1");
        var suffix = string.Join(" ", args.Select(Quote));
        return RunProcess(
            "pwsh",
            $"-NoProfile -ExecutionPolicy Bypass -File {Quote(scriptPath)} {suffix}",
            repoRoot,
            timeoutMilliseconds: 20_000);
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
                // Ignore cleanup failures after timeout.
            }

            throw new TimeoutException($"Process '{fileName} {arguments}' timed out after {timeoutMilliseconds}ms.");
        }

        Task.WaitAll(stdoutTask, stderrTask);

        return new CommandResult(
            process.ExitCode,
            stdoutTask.GetAwaiter().GetResult(),
            stderrTask.GetAwaiter().GetResult());
    }

    private static string Quote(string value) =>
        $"\"{value.Replace("\"", "\\\"", StringComparison.Ordinal)}\"";

    private readonly record struct CommandResult(int ExitCode, string StandardOutput, string StandardError);
}
