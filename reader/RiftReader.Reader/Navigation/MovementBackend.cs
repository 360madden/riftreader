using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;

namespace RiftReader.Reader.Navigation;

public interface IMovementBackend
{
    string BackendKind => MovementBackendKinds.Unknown;

    void PrepareForMovement();

    MovementCommandResult PressKey(string key, int holdMilliseconds);
}

public sealed record MovementCommandResult(
    bool IsSuccess,
    string? ErrorMessage);

public static class MovementBackendKinds
{
    public const string Unknown = "unknown";
    public const string NotCreated = "not-created";
    public const string NativeWindowMessage = "native-window-message";
    public const string PowerShellWindowMessage = "powershell-window-message";
    public const string PowerShellSendInputForeground = "powershell-sendinput-foreground";
}

public static class MovementBackendFactory
{
    public static IMovementBackend Create(
        string scriptFile,
        string targetProcessName,
        int? targetProcessId = null,
        string? targetWindowHandle = null)
    {
        return string.IsNullOrWhiteSpace(targetWindowHandle)
            ? new PowerShellMovementBackend(scriptFile, targetProcessName, targetProcessId)
            : new WindowMessageMovementBackend(targetProcessName, targetProcessId, targetWindowHandle);
    }
}

public sealed class WindowMessageMovementBackend : IMovementBackend
{
    private const int LiveInteractionCountdownSeconds = 10;
    private const int InterKeyDelayMilliseconds = 20;
    private const uint WindowMessageKeyDown = 0x0100;
    private const uint WindowMessageKeyUp = 0x0101;
    private const uint MapVirtualKeyVirtualKeyToScanCode = 0;
    private const int VirtualKeyShift = 0x10;
    private const int VirtualKeyControl = 0x11;
    private const int VirtualKeyMenu = 0x12;
    private static readonly IReadOnlyDictionary<string, int> NamedKeys = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
    {
        ["SPACE"] = 0x20,
        ["LEFT"] = 0x25,
        ["UP"] = 0x26,
        ["RIGHT"] = 0x27,
        ["DOWN"] = 0x28
    };

    private readonly string _targetProcessName;
    private readonly int? _targetProcessId;
    private readonly string _targetWindowHandle;
    private readonly IWindowMessageNativeMethods _nativeMethods;
    private readonly Func<int, string?> _processNameResolver;
    private readonly Action<int> _sleep;
    private bool _liveInteractionArmed;

    public WindowMessageMovementBackend(
        string targetProcessName,
        int? targetProcessId,
        string targetWindowHandle)
        : this(
            targetProcessName,
            targetProcessId,
            targetWindowHandle,
            User32WindowMessageNativeMethods.Instance,
            ResolveProcessName,
            Thread.Sleep)
    {
    }

    internal WindowMessageMovementBackend(
        string targetProcessName,
        int? targetProcessId,
        string targetWindowHandle,
        IWindowMessageNativeMethods nativeMethods,
        Func<int, string?> processNameResolver,
        Action<int> sleep)
    {
        _targetProcessName = targetProcessName;
        _targetProcessId = targetProcessId;
        _targetWindowHandle = targetWindowHandle;
        _nativeMethods = nativeMethods;
        _processNameResolver = processNameResolver;
        _sleep = sleep;
    }

    public string BackendKind => MovementBackendKinds.NativeWindowMessage;

    public void PrepareForMovement()
    {
        if (_liveInteractionArmed)
        {
            return;
        }

        RunLiveInteractionCountdown();
        _liveInteractionArmed = true;
    }

    public MovementCommandResult PressKey(string key, int holdMilliseconds)
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return new MovementCommandResult(false, "Movement key was blank.");
        }

        if (holdMilliseconds < 0)
        {
            return new MovementCommandResult(false, "Movement hold duration cannot be negative.");
        }

        try
        {
            var target = ResolveTargetWindow();
            var binding = ResolveKeyBinding(key.Trim());
            PressKey(target.EffectiveWindowHandle, binding, holdMilliseconds);
            return new MovementCommandResult(true, null);
        }
        catch (Exception ex)
        {
            return new MovementCommandResult(false, ex.Message);
        }
    }

    private WindowMessageTarget ResolveTargetWindow()
    {
        if (!TryParseWindowHandle(_targetWindowHandle, out var windowHandle) || windowHandle == nint.Zero)
        {
            throw new InvalidOperationException($"Target window handle '{_targetWindowHandle}' is not a valid HWND.");
        }

        if (!_nativeMethods.IsWindow(windowHandle))
        {
            throw new InvalidOperationException($"Target window handle '{_targetWindowHandle}' is not a valid window.");
        }

        var targetThreadId = _nativeMethods.GetWindowThreadProcessId(windowHandle, out var ownerProcessId);
        if (ownerProcessId == 0)
        {
            throw new InvalidOperationException($"Target window handle '{_targetWindowHandle}' did not resolve an owner process.");
        }

        if (_targetProcessId is > 0 && ownerProcessId != _targetProcessId.Value)
        {
            throw new InvalidOperationException($"Target window handle '{_targetWindowHandle}' belongs to PID {ownerProcessId}, not requested PID {_targetProcessId.Value}.");
        }

        var processName = _processNameResolver((int)ownerProcessId);
        var expectedName = Path.GetFileNameWithoutExtension(_targetProcessName);
        if (!string.IsNullOrWhiteSpace(expectedName) &&
            !string.Equals(processName, expectedName, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"Target window handle '{_targetWindowHandle}' belongs to process '{processName}' [{ownerProcessId}], not '{expectedName}'.");
        }

        var effectiveTargetHandle = _nativeMethods.GetEffectiveTargetHandle(windowHandle, targetThreadId, (int)ownerProcessId);
        return new WindowMessageTarget(windowHandle, effectiveTargetHandle);
    }

    private KeyBinding ResolveKeyBinding(string keyText)
    {
        if (NamedKeys.TryGetValue(keyText, out var namedVirtualKey))
        {
            return new KeyBinding(namedVirtualKey, ShiftState: 0);
        }

        if (keyText.Length != 1)
        {
            throw new InvalidOperationException("Native window-message movement supports a single character key like W, A, S, D, 1, or named keys Space/Left/Up/Right/Down.");
        }

        var vkScan = _nativeMethods.VkKeyScan(keyText[0]);
        if (vkScan == -1)
        {
            throw new InvalidOperationException($"No virtual-key mapping was found for character '{keyText[0]}'.");
        }

        var vkScanInt = vkScan;
        return new KeyBinding(
            VirtualKey: vkScanInt & 0xFF,
            ShiftState: (vkScanInt >> 8) & 0xFF);
    }

    private void PressKey(nint windowHandle, KeyBinding binding, int holdMilliseconds)
    {
        var modifiersDown = new List<int>();
        var primaryKeyDown = false;
        Exception? releaseFailure = null;

        try
        {
            PressModifierIfNeeded(binding.ShiftState, 1, VirtualKeyShift, windowHandle, modifiersDown);
            PressModifierIfNeeded(binding.ShiftState, 2, VirtualKeyControl, windowHandle, modifiersDown);
            PressModifierIfNeeded(binding.ShiftState, 4, VirtualKeyMenu, windowHandle, modifiersDown);

            PostKeyDown(windowHandle, binding.VirtualKey);
            primaryKeyDown = true;
            _sleep(holdMilliseconds);
            PostKeyUp(windowHandle, binding.VirtualKey);
            primaryKeyDown = false;
        }
        finally
        {
            if (primaryKeyDown)
            {
                releaseFailure ??= TryPostKeyUp(windowHandle, binding.VirtualKey);
            }

            for (var index = modifiersDown.Count - 1; index >= 0; index--)
            {
                _sleep(InterKeyDelayMilliseconds);
                releaseFailure ??= TryPostKeyUp(windowHandle, modifiersDown[index]);
            }
        }

        if (releaseFailure is not null)
        {
            throw new InvalidOperationException("Native window-message movement failed while releasing key state.", releaseFailure);
        }
    }

    private void PressModifierIfNeeded(
        int shiftState,
        int shiftMask,
        int virtualKey,
        nint windowHandle,
        ICollection<int> modifiersDown)
    {
        if ((shiftState & shiftMask) == 0)
        {
            return;
        }

        PostKeyDown(windowHandle, virtualKey);
        modifiersDown.Add(virtualKey);
        _sleep(InterKeyDelayMilliseconds);
    }

    private void PostKeyDown(nint windowHandle, int virtualKey)
    {
        PostKey(windowHandle, WindowMessageKeyDown, virtualKey, keyUp: false);
    }

    private void PostKeyUp(nint windowHandle, int virtualKey)
    {
        PostKey(windowHandle, WindowMessageKeyUp, virtualKey, keyUp: true);
    }

    private Exception? TryPostKeyUp(nint windowHandle, int virtualKey)
    {
        try
        {
            PostKeyUp(windowHandle, virtualKey);
            return null;
        }
        catch (Exception ex)
        {
            return ex;
        }
    }

    private void PostKey(nint windowHandle, uint message, int virtualKey, bool keyUp)
    {
        var lParam = NewKeyLParam(virtualKey, keyUp);
        if (_nativeMethods.PostMessage(windowHandle, message, (nint)virtualKey, lParam))
        {
            return;
        }

        var lastError = _nativeMethods.GetLastWin32Error();
        var lastErrorMessage = new Win32Exception(lastError).Message;
        throw new InvalidOperationException($"PostMessage failed for virtual key {virtualKey}. LastWin32Error={lastError} ({lastErrorMessage}).");
    }

    private nint NewKeyLParam(int virtualKey, bool keyUp)
    {
        var scanCode = _nativeMethods.MapVirtualKey((uint)virtualKey, MapVirtualKeyVirtualKeyToScanCode);
        var value = 1u | (scanCode << 16);
        if (keyUp)
        {
            value |= 0xC0000000u;
        }

        return unchecked((nint)(int)value);
    }

    private static bool TryParseWindowHandle(string? handleText, out nint handle)
    {
        handle = nint.Zero;
        if (string.IsNullOrWhiteSpace(handleText))
        {
            return false;
        }

        var trimmed = handleText.Trim();
        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            if (!ulong.TryParse(
                trimmed[2..],
                NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture,
                out var rawHex))
            {
                return false;
            }

            handle = unchecked((nint)(long)rawHex);
            return true;
        }

        if (!long.TryParse(trimmed, NumberStyles.Integer, CultureInfo.InvariantCulture, out var rawDecimal))
        {
            return false;
        }

        handle = (nint)rawDecimal;
        return true;
    }

    private static string ResolveProcessName(int processId)
    {
        return Process.GetProcessById(processId).ProcessName;
    }

    private void RunLiveInteractionCountdown()
    {
        Console.Error.WriteLine("[Navigation] Live movement will start in 10 seconds.");
        Console.Error.WriteLine($"[Navigation] Using native exact-HWND window-message input for {_targetWindowHandle}.");
        for (var remaining = LiveInteractionCountdownSeconds; remaining >= 1; remaining--)
        {
            Console.Error.WriteLine($"[Navigation] Starting in {remaining}...");
            _sleep(1000);
        }
    }

    private sealed record KeyBinding(int VirtualKey, int ShiftState);

    private sealed record WindowMessageTarget(nint TopWindowHandle, nint EffectiveWindowHandle);
}

public sealed class PowerShellMovementBackend(
    string scriptFile,
    string targetProcessName,
    int? targetProcessId = null,
    string? targetWindowHandle = null) : IMovementBackend
{
    private const int MinimumCommandTimeoutMilliseconds = 5000;
    private const int LiveInteractionCountdownSeconds = 10;
    private bool _liveInteractionArmed;

    public string BackendKind => string.IsNullOrWhiteSpace(targetWindowHandle)
        ? MovementBackendKinds.PowerShellSendInputForeground
        : MovementBackendKinds.PowerShellWindowMessage;

    public void PrepareForMovement()
    {
        if (_liveInteractionArmed)
        {
            return;
        }

        RunLiveInteractionCountdown();
        _liveInteractionArmed = true;
    }

    public MovementCommandResult PressKey(string key, int holdMilliseconds)
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return new MovementCommandResult(false, "Movement key was blank.");
        }

        if (!File.Exists(scriptFile))
        {
            return new MovementCommandResult(false, $"Movement helper script was not found: '{scriptFile}'.");
        }

        using var process = new Process
        {
            StartInfo = BuildStartInfo(key.Trim(), holdMilliseconds)
        };

        try
        {
            process.Start();
        }
        catch (Exception ex)
        {
            return new MovementCommandResult(false, $"Unable to start PowerShell movement helper: {ex.Message}");
        }

        var timeoutMilliseconds = Math.Max(MinimumCommandTimeoutMilliseconds, holdMilliseconds + 4000);
        if (!process.WaitForExit(timeoutMilliseconds))
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Best effort only.
            }

            return new MovementCommandResult(false, $"Movement helper timed out after {timeoutMilliseconds} ms.");
        }

        var output = new StringBuilder();
        var standardOutput = process.StandardOutput.ReadToEnd().Trim();
        var standardError = process.StandardError.ReadToEnd().Trim();

        if (!string.IsNullOrWhiteSpace(standardOutput))
        {
            output.Append(standardOutput);
        }

        if (!string.IsNullOrWhiteSpace(standardError))
        {
            if (output.Length > 0)
            {
                output.Append(' ');
            }

            output.Append(standardError);
        }

        return process.ExitCode == 0
            ? new MovementCommandResult(true, null)
            : new MovementCommandResult(false, string.IsNullOrWhiteSpace(output.ToString()) ? $"Movement helper exited with code {process.ExitCode}." : output.ToString());
    }

    private ProcessStartInfo BuildStartInfo(string key, int holdMilliseconds)
    {
        var hasExactWindowTarget = !string.IsNullOrWhiteSpace(targetWindowHandle);
        var startInfo = new ProcessStartInfo
        {
            FileName = "pwsh",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(scriptFile);
        startInfo.ArgumentList.Add("-Key");
        startInfo.ArgumentList.Add(key);
        startInfo.ArgumentList.Add("-HoldMilliseconds");
        startInfo.ArgumentList.Add(holdMilliseconds.ToString(CultureInfo.InvariantCulture));
        startInfo.ArgumentList.Add("-TargetProcessName");
        startInfo.ArgumentList.Add(targetProcessName);
        if (targetProcessId is > 0)
        {
            startInfo.ArgumentList.Add("-TargetProcessId");
            startInfo.ArgumentList.Add(targetProcessId.Value.ToString(CultureInfo.InvariantCulture));
        }

        if (hasExactWindowTarget)
        {
            startInfo.ArgumentList.Add("-TargetWindowHandle");
            startInfo.ArgumentList.Add(targetWindowHandle!);
        }

        startInfo.ArgumentList.Add("-SkipBackgroundFocus");
        if (hasExactWindowTarget)
        {
            startInfo.ArgumentList.Add("-UseWindowMessage");
        }
        else
        {
            startInfo.ArgumentList.Add("-RequireTargetForeground");
        }

        return startInfo;
    }

    private void RunLiveInteractionCountdown()
    {
        Console.Error.WriteLine("[Navigation] Live movement will start in 10 seconds.");
        if (!string.IsNullOrWhiteSpace(targetWindowHandle))
        {
            Console.Error.WriteLine($"[Navigation] Using exact-HWND window-message input for {targetWindowHandle}.");
        }
        else
        {
            Console.Error.WriteLine("[Navigation] Keep the Rift window focused. Movement will abort if focus is lost.");
        }

        for (var remaining = LiveInteractionCountdownSeconds; remaining >= 1; remaining--)
        {
            Console.Error.WriteLine($"[Navigation] Starting in {remaining}...");
            Thread.Sleep(1000);
        }
    }
}

internal interface IWindowMessageNativeMethods
{
    bool IsWindow(nint windowHandle);

    uint GetWindowThreadProcessId(nint windowHandle, out uint processId);

    nint GetEffectiveTargetHandle(nint topWindowHandle, uint targetThreadId, int targetProcessId);

    short VkKeyScan(char character);

    uint MapVirtualKey(uint code, uint mapType);

    bool PostMessage(nint windowHandle, uint message, nint wParam, nint lParam);

    int GetLastWin32Error();
}

internal sealed class User32WindowMessageNativeMethods : IWindowMessageNativeMethods
{
    internal static readonly User32WindowMessageNativeMethods Instance = new();

    private User32WindowMessageNativeMethods()
    {
    }

    public bool IsWindow(nint windowHandle)
    {
        return IsWindowNative(windowHandle);
    }

    public uint GetWindowThreadProcessId(nint windowHandle, out uint processId)
    {
        return GetWindowThreadProcessIdNative(windowHandle, out processId);
    }

    public nint GetEffectiveTargetHandle(nint topWindowHandle, uint targetThreadId, int targetProcessId)
    {
        var guiThreadInfo = new GuiThreadInfo
        {
            CbSize = Marshal.SizeOf<GuiThreadInfo>()
        };

        if (!GetGUIThreadInfo(targetThreadId, ref guiThreadInfo) || guiThreadInfo.HwndFocus == nint.Zero)
        {
            return topWindowHandle;
        }

        _ = GetWindowThreadProcessIdNative(guiThreadInfo.HwndFocus, out var focusProcessId);
        return focusProcessId == targetProcessId
            ? guiThreadInfo.HwndFocus
            : topWindowHandle;
    }

    public short VkKeyScan(char character)
    {
        return VkKeyScanNative(character);
    }

    public uint MapVirtualKey(uint code, uint mapType)
    {
        return MapVirtualKeyNative(code, mapType);
    }

    public bool PostMessage(nint windowHandle, uint message, nint wParam, nint lParam)
    {
        return PostMessageNative(windowHandle, message, wParam, lParam);
    }

    public int GetLastWin32Error()
    {
        return Marshal.GetLastWin32Error();
    }

    [DllImport("user32.dll", EntryPoint = "IsWindow", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowNative(nint hWnd);

    [DllImport("user32.dll", EntryPoint = "GetWindowThreadProcessId", SetLastError = true)]
    private static extern uint GetWindowThreadProcessIdNative(nint hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll", EntryPoint = "GetGUIThreadInfo", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetGUIThreadInfo(uint idThread, ref GuiThreadInfo lpgui);

    [DllImport("user32.dll", EntryPoint = "VkKeyScanW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern short VkKeyScanNative(char ch);

    [DllImport("user32.dll", EntryPoint = "MapVirtualKeyW", SetLastError = true)]
    private static extern uint MapVirtualKeyNative(uint uCode, uint uMapType);

    [DllImport("user32.dll", EntryPoint = "PostMessageW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessageNative(nint hWnd, uint msg, nint wParam, nint lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct GuiThreadInfo
    {
        public int CbSize;
        public uint Flags;
        public nint HwndActive;
        public nint HwndFocus;
        public nint HwndCapture;
        public nint HwndMenuOwner;
        public nint HwndMoveSize;
        public nint HwndCaret;
        public Rect RcCaret;
    }
}
