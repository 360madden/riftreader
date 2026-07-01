using System.Text.Json;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Tests.Navigation;

public sealed class PowerShellMovementBackendTests
{
    // The fixture script records arguments without sleeping; this only extends
    // the backend subprocess timeout for slow PowerShell startup under CI load.
    private const int FixtureHoldMilliseconds = 12_000;

    [Fact]
    public void Create_UsesNativeWindowMessageBackendWhenExactWindowHandleIsAvailable()
    {
        var backend = MovementBackendFactory.Create(
            "unused.ps1",
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A");

        Assert.IsType<WindowMessageMovementBackend>(backend);
        Assert.Equal(MovementBackendKinds.NativeWindowMessage, backend.BackendKind);
    }

    [Fact]
    public void Create_KeepsPowerShellFallbackWhenNoExactWindowHandleIsAvailable()
    {
        var backend = MovementBackendFactory.Create(
            "unused.ps1",
            "rift_x64",
            targetProcessId: 49504);

        Assert.IsType<PowerShellMovementBackend>(backend);
        Assert.Equal(MovementBackendKinds.PowerShellSendInputForeground, backend.BackendKind);
    }

    [Fact]
    public void NativePressKey_PostsDownAndUpToEffectiveWindowHandle()
    {
        var nativeMethods = new FakeWindowMessageNativeMethods
        {
            OwnerProcessId = 49504,
            TargetThreadId = 17,
            EffectiveTargetHandle = 0x6000,
            VirtualKeyScan = 0x57,
            ScanCode = 0x11
        };
        var backend = new WindowMessageMovementBackend(
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A",
            nativeMethods,
            _ => "rift_x64",
            _ => { });

        var result = backend.PressKey("w", 250);

        Assert.Equal(MovementBackendKinds.NativeWindowMessage, backend.BackendKind);
        Assert.True(result.IsSuccess, result.ErrorMessage);
        Assert.Collection(
            nativeMethods.PostedMessages,
            down =>
            {
                Assert.Equal(0x6000, down.WindowHandle);
                Assert.Equal(0x0100u, down.Message);
                Assert.Equal(0x57, down.WParam);
                Assert.Equal(1u | (0x11u << 16), ToUInt32(down.LParam));
            },
            up =>
            {
                Assert.Equal(0x6000, up.WindowHandle);
                Assert.Equal(0x0101u, up.Message);
                Assert.Equal(0x57, up.WParam);
                Assert.Equal(1u | (0x11u << 16) | 0xC0000000u, ToUInt32(up.LParam));
            });
    }

    [Fact]
    public void NativePressKey_FailsClosedWhenWindowHandleBelongsToDifferentPid()
    {
        var nativeMethods = new FakeWindowMessageNativeMethods
        {
            OwnerProcessId = 12345,
            TargetThreadId = 17,
            EffectiveTargetHandle = 0x6000,
            VirtualKeyScan = 0x57,
            ScanCode = 0x11
        };
        var backend = new WindowMessageMovementBackend(
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A",
            nativeMethods,
            _ => "rift_x64",
            _ => { });

        var result = backend.PressKey("w", 250);

        Assert.False(result.IsSuccess);
        Assert.Contains("not requested PID 49504", result.ErrorMessage);
        Assert.Empty(nativeMethods.PostedMessages);
    }

    [Fact]
    public void NativePressKey_RetriesKeyUpWhenPrimaryReleaseFails()
    {
        var nativeMethods = new FakeWindowMessageNativeMethods
        {
            OwnerProcessId = 49504,
            TargetThreadId = 17,
            EffectiveTargetHandle = 0x6000,
            VirtualKeyScan = 0x57,
            ScanCode = 0x11,
            FailedKeyUpPostsRemaining = 1,
            LastWin32Error = 5
        };
        var backend = new WindowMessageMovementBackend(
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A",
            nativeMethods,
            _ => "rift_x64",
            _ => { });

        var result = backend.PressKey("w", 250);

        Assert.False(result.IsSuccess);
        Assert.Contains("PostMessage failed", result.ErrorMessage);
        Assert.Collection(
            nativeMethods.PostedMessages,
            down => Assert.Equal(0x0100u, down.Message),
            retryUp => Assert.Equal(0x0101u, retryUp.Message));
    }

    [Fact]
    public void PressKey_UsesWindowMessageBackendWhenExactWindowHandleIsAvailable()
    {
        using var fixture = new MovementScriptFixture();
        var backend = new PowerShellMovementBackend(
            fixture.ScriptFile,
            "rift_x64",
            targetProcessId: 49504,
            targetWindowHandle: "0x5121A");

        var result = backend.PressKey("w", FixtureHoldMilliseconds);

        Assert.True(result.IsSuccess, result.ErrorMessage);
        using var document = fixture.ReadInvocation();
        var root = document.RootElement;
        Assert.Equal("w", root.GetProperty("Key").GetString());
        Assert.Equal(FixtureHoldMilliseconds, root.GetProperty("HoldMilliseconds").GetInt32());
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

        var result = backend.PressKey("w", FixtureHoldMilliseconds);

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

    private static uint ToUInt32(nint value)
    {
        return unchecked((uint)(int)value);
    }

    private sealed class FakeWindowMessageNativeMethods : IWindowMessageNativeMethods
    {
        public uint OwnerProcessId { get; init; }

        public uint TargetThreadId { get; init; }

        public nint EffectiveTargetHandle { get; init; }

        public short VirtualKeyScan { get; init; }

        public uint ScanCode { get; init; }

        public int FailedKeyUpPostsRemaining { get; set; }

        public int LastWin32Error { get; init; }

        public List<PostedMessage> PostedMessages { get; } = [];

        public bool IsWindow(nint windowHandle)
        {
            return windowHandle != nint.Zero;
        }

        public uint GetWindowThreadProcessId(nint windowHandle, out uint processId)
        {
            processId = OwnerProcessId;
            return TargetThreadId;
        }

        public nint GetEffectiveTargetHandle(nint topWindowHandle, uint targetThreadId, int targetProcessId)
        {
            return EffectiveTargetHandle == nint.Zero
                ? topWindowHandle
                : EffectiveTargetHandle;
        }

        public short VkKeyScan(char character)
        {
            return VirtualKeyScan;
        }

        public uint MapVirtualKey(uint code, uint mapType)
        {
            return ScanCode;
        }

        public bool PostMessage(nint windowHandle, uint message, nint wParam, nint lParam)
        {
            if (message == 0x0101u && FailedKeyUpPostsRemaining > 0)
            {
                FailedKeyUpPostsRemaining--;
                return false;
            }

            PostedMessages.Add(new PostedMessage(windowHandle, message, wParam, lParam));
            return true;
        }

        public int GetLastWin32Error()
        {
            return LastWin32Error;
        }
    }

    private sealed record PostedMessage(nint WindowHandle, uint Message, nint WParam, nint LParam);
}
