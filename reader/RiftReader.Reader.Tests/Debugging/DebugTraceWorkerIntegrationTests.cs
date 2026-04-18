using System.Diagnostics;
using System.Text.Json;
using RiftReader.Reader.Debugging;
using Xunit;

namespace RiftReader.Reader.Tests.Debugging;

public sealed class DebugTraceWorkerIntegrationTests
{
    [Fact]
    public void MemoryWriteTrace_RecordsHitAgainstFixture()
    {
        using var fixture = DebugFixtureHost.Start();
        var outputDirectory = CreateTempDirectory(nameof(MemoryWriteTrace_RecordsHitAgainstFixture));

        try
        {
            var result = RunReader(
                [
                    "--pid", fixture.Metadata.ProcessId.ToString(),
                    "--debug-trace-memory-write",
                    "--debug-address", fixture.Metadata.MemoryAddress,
                    "--debug-width", "4",
                    "--debug-timeout-ms", "5000",
                    "--debug-max-hits", "1",
                    "--debug-output-directory", outputDirectory,
                    "--json"
                ]);

            Assert.Equal(0, result.ExitCode);

            var inspection = DebugTracePackageLoader.TryInspect(outputDirectory, out var error);
            Assert.NotNull(inspection);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
            Assert.NotNull(inspection!.TraceManifest);
            Assert.Equal("memory-write", inspection.TraceManifest!.BreakpointKind);
            Assert.True(inspection.TraceManifest.RecordedHitCount >= 1, result.StandardError + Environment.NewLine + result.StandardOutput);
            Assert.Contains(inspection.Hits, hit => string.Equals(hit.WatchedAddress, fixture.Metadata.MemoryAddress, StringComparison.OrdinalIgnoreCase));
        }
        finally
        {
            TryDeleteDirectory(outputDirectory);
        }
    }

    [Fact]
    public void MemoryAccessTrace_RecordsHitAgainstFixture()
    {
        using var fixture = DebugFixtureHost.Start();
        var outputDirectory = CreateTempDirectory(nameof(MemoryAccessTrace_RecordsHitAgainstFixture));

        try
        {
            var result = RunReader(
                [
                    "--pid", fixture.Metadata.ProcessId.ToString(),
                    "--debug-trace-memory-access",
                    "--debug-address", fixture.Metadata.MemoryAddress,
                    "--debug-width", "4",
                    "--debug-timeout-ms", "5000",
                    "--debug-max-hits", "1",
                    "--debug-output-directory", outputDirectory,
                    "--json"
                ]);

            Assert.Equal(0, result.ExitCode);

            var inspection = DebugTracePackageLoader.TryInspect(outputDirectory, out var error);
            Assert.NotNull(inspection);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
            Assert.NotNull(inspection!.TraceManifest);
            Assert.Equal("memory-access", inspection.TraceManifest!.BreakpointKind);
            Assert.True(inspection.TraceManifest.RecordedHitCount >= 1, result.StandardError + Environment.NewLine + result.StandardOutput);
            Assert.Contains(inspection.Hits, hit => string.Equals(hit.WatchedAddress, fixture.Metadata.MemoryAddress, StringComparison.OrdinalIgnoreCase));
        }
        finally
        {
            TryDeleteDirectory(outputDirectory);
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

    private static string CreateTempDirectory(string testName)
    {
        var directory = Path.Combine(Path.GetTempPath(), "RiftReader", "debug-trace-tests", $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmssfff}-{testName}-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        return directory;
    }

    private static void TryDeleteDirectory(string directory)
    {
        try
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
        catch
        {
            // Best-effort cleanup only.
        }
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

    private sealed class DebugFixtureHost : IDisposable
    {
        private readonly Process _process;

        private DebugFixtureHost(Process process, FixtureMetadata metadata)
        {
            _process = process;
            Metadata = metadata;
        }

        public FixtureMetadata Metadata { get; }

        public static DebugFixtureHost Start()
        {
            var repoRoot = FindRepoRoot();
            var readyFile = Path.Combine(CreateTempDirectory("fixture"), "fixture-ready.json");
            var projectPath = Path.Combine(repoRoot, "reader", "RiftReader.DebugFixture", "RiftReader.DebugFixture.csproj");
            var arguments = $"run --project {Quote(projectPath)} --no-build -- --ready-file {Quote(readyFile)}";

            var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "dotnet",
                    Arguments = arguments,
                    WorkingDirectory = repoRoot,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                }
            };

            if (!process.Start())
            {
                throw new InvalidOperationException("Unable to start the debug fixture process.");
            }

            var deadline = DateTime.UtcNow.AddSeconds(15);
            while (DateTime.UtcNow < deadline)
            {
                if (process.HasExited)
                {
                    var stdout = process.StandardOutput.ReadToEnd();
                    var stderr = process.StandardError.ReadToEnd();
                    throw new InvalidOperationException($"The debug fixture exited early with code {process.ExitCode}.{Environment.NewLine}{stdout}{Environment.NewLine}{stderr}");
                }

                if (File.Exists(readyFile))
                {
                    var json = File.ReadAllText(readyFile);
                    var metadata = JsonSerializer.Deserialize<FixtureMetadata>(json, new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    });

                    if (metadata is null)
                    {
                        throw new InvalidOperationException($"The debug fixture ready file '{readyFile}' did not contain valid metadata.");
                    }

                    return new DebugFixtureHost(process, metadata);
                }

                Thread.Sleep(100);
            }

            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Ignore cleanup failures after timeout.
            }

            throw new TimeoutException("Timed out waiting for the debug fixture ready file.");
        }

        public void Dispose()
        {
            if (_process.HasExited)
            {
                _process.Dispose();
                return;
            }

            try
            {
                _process.Kill(entireProcessTree: true);
                _process.WaitForExit(5_000);
            }
            catch
            {
                // Ignore cleanup failures during test teardown.
            }
            finally
            {
                _process.Dispose();
            }
        }
    }

    private sealed record FixtureMetadata(
        int ProcessId,
        string ProcessName,
        string ModuleName,
        string MemoryAddress,
        string ReadMethodAddress,
        string WriteMethodAddress,
        int InitialValue);
}
