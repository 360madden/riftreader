using System.Text.Json;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Tests.Navigation;

public sealed class PowerShellMovementBackendTests
{
    [Fact]
    public void PressKey_UsesWindowMessageBackendWhenExactWindowHandleIsAvailable()
    {
        using var fixture = new MovementScriptFixture();
        var backend = new PowerShellMovementBackend(
            fixture.ScriptFile,
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A");

        var result = backend.PressKey("w", 250);

        Assert.True(result.IsSuccess, result.ErrorMessage);
        using var document = fixture.ReadInvocation();
        var root = document.RootElement;
        Assert.Equal("w", root.GetProperty("Key").GetString());
        Assert.Equal(250, root.GetProperty("HoldMilliseconds").GetInt32());
        Assert.Equal("rift_x64", root.GetProperty("TargetProcessName").GetString());
        Assert.Equal(49504, root.GetProperty("TargetProcessId").GetInt32());
        Assert.Equal("0x5121A", root.GetProperty("TargetWindowHandle").GetString());
        Assert.True(root.GetProperty("SkipBackgroundFocus").GetBoolean());
        Assert.True(root.GetProperty("UseWindowMessage").GetBoolean());
        Assert.False(root.GetProperty("RequireTargetForeground").GetBoolean());
    }

    [Fact]
    public void PressKey_RequiresForegroundWhenNoExactWindowHandleIsAvailable()
    {
        using var fixture = new MovementScriptFixture();
        var backend = new PowerShellMovementBackend(
            fixture.ScriptFile,
            "rift_x64",
            targetProcessId: 49504);

        var result = backend.PressKey("w", 250);

        Assert.True(result.IsSuccess, result.ErrorMessage);
        using var document = fixture.ReadInvocation();
        var root = document.RootElement;
        Assert.True(root.GetProperty("SkipBackgroundFocus").GetBoolean());
        Assert.True(root.GetProperty("RequireTargetForeground").GetBoolean());
        Assert.False(root.GetProperty("UseWindowMessage").GetBoolean());
        Assert.Equal(string.Empty, root.GetProperty("TargetWindowHandle").GetString());
    }

    private sealed class MovementScriptFixture : IDisposable
    {
        private readonly string _directory;
        private readonly string _outputFile;
        private readonly string? _previousOutputFile;

        public MovementScriptFixture()
        {
            _directory = Path.Combine(Path.GetTempPath(), "riftreader-movement-backend-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_directory);
            ScriptFile = Path.Combine(_directory, "capture-movement-args.ps1");
            _outputFile = Path.Combine(_directory, "invocation.json");
            _previousOutputFile = Environment.GetEnvironmentVariable("RIFT_READER_MOVEMENT_BACKEND_TEST_OUTPUT");
            Environment.SetEnvironmentVariable("RIFT_READER_MOVEMENT_BACKEND_TEST_OUTPUT", _outputFile);

            File.WriteAllText(
                ScriptFile,
                """
                param(
                    [string]$Key,
                    [int]$HoldMilliseconds,
                    [string]$TargetProcessName,
                    [int]$TargetProcessId,
                    [string]$TargetWindowHandle,
                    [switch]$SkipBackgroundFocus,
                    [switch]$RequireTargetForeground,
                    [switch]$UseWindowMessage
                )

                [ordered]@{
                    Key = $Key
                    HoldMilliseconds = $HoldMilliseconds
                    TargetProcessName = $TargetProcessName
                    TargetProcessId = $TargetProcessId
                    TargetWindowHandle = $TargetWindowHandle
                    SkipBackgroundFocus = [bool]$SkipBackgroundFocus
                    RequireTargetForeground = [bool]$RequireTargetForeground
                    UseWindowMessage = [bool]$UseWindowMessage
                } | ConvertTo-Json -Compress | Set-Content -LiteralPath $env:RIFT_READER_MOVEMENT_BACKEND_TEST_OUTPUT -Encoding UTF8
                """);
        }

        public string ScriptFile { get; }

        public JsonDocument ReadInvocation()
        {
            Assert.True(File.Exists(_outputFile), $"Expected movement test output file '{_outputFile}' to exist.");
            return JsonDocument.Parse(File.ReadAllText(_outputFile));
        }

        public void Dispose()
        {
            Environment.SetEnvironmentVariable("RIFT_READER_MOVEMENT_BACKEND_TEST_OUTPUT", _previousOutputFile);
            try
            {
                Directory.Delete(_directory, recursive: true);
            }
            catch
            {
                // Best-effort cleanup only.
            }
        }
    }
}
