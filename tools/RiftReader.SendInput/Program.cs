// Version: riftreader-sendinput-csharp-tool-v0.1.0
// Total-Character-Count: 28248
// Purpose: Pure C# SendInput key sender for RiftReader diagnostics. Provides exact target validation, foreground verification, VirtualKey and ScanCode input modes, and safe key release.

using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RiftReader.SendInput;

internal static class Program
{
    private const int SwRestore = 9;
    private const int SwShow = 5;
    private const int InputKeyboard = 1;
    private const int InputMouse = 0;
    private const uint KeyEventFExtendedKey = 0x0001;
    private const uint KeyEventFKeyUp = 0x0002;
    private const uint KeyEventFScanCode = 0x0008;
    private const uint MapVkToVsc = 0;
    private const uint MouseEventFMove = 0x0001;
    private const uint MouseEventFLeftDown = 0x0002;
    private const uint MouseEventFLeftUp = 0x0004;
    private const uint MouseEventFAbsolute = 0x8000;
    private const uint MouseEventFVirtualDesk = 0x4000;
    private const int SmCxVirtualScreen = 78;
    private const int SmCyVirtualScreen = 79;
    private const int SmXvVirtualScreen = 76;
    private const int SmYvVirtualScreen = 77;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    private static readonly HashSet<int> ExtendedVirtualKeys = new()
    {
        0x21, // PageUp
        0x22, // PageDown
        0x23, // End
        0x24, // Home
        0x25, // Left
        0x26, // Up
        0x27, // Right
        0x28, // Down
        0x2D, // Insert
        0x2E  // Delete
    };

    private static readonly Dictionary<string, int> NamedKeys = new(StringComparer.OrdinalIgnoreCase)
    {
        ["SPACE"] = 0x20,
        ["LEFT"] = 0x25,
        ["UP"] = 0x26,
        ["RIGHT"] = 0x27,
        ["DOWN"] = 0x28,
        ["ENTER"] = 0x0D,
        ["RETURN"] = 0x0D,
        ["ESC"] = 0x1B,
        ["ESCAPE"] = 0x1B,
        ["BACKSPACE"] = 0x08,
        ["TAB"] = 0x09,
        ["PAGEUP"] = 0x21,
        ["PAGEDOWN"] = 0x22
    };

    public static int Main(string[] args)
    {
        Options? options = null;
        try
        {
            options = Options.Parse(args);
            if (options.ShowHelp)
            {
                WriteUsage();
                return 0;
            }

            var target = TargetResolver.Resolve(options);
            var focus = FocusTarget(target.WindowHandle, target.ProcessId, options.FocusDelayMilliseconds);
            if (!focus.TargetProcessForeground)
            {
                throw new InvalidOperationException(
                    $"Target process is not foreground after focus attempt. Foreground PID={focus.ForegroundProcessId}; target PID={target.ProcessId}.");
            }

            object result;
            if (options.IsMouseClick)
            {
                var mouseResult = SendMouseLeftClick(target.WindowHandle, options);
                if (!options.NoRefocus && focus.PreviousForegroundWindow != nint.Zero &&
                    focus.PreviousForegroundWindow != target.WindowHandle)
                {
                    _ = Native.SetForegroundWindow(focus.PreviousForegroundWindow);
                }

                result = new
                {
                    schemaVersion = 1,
                    tool = "RiftReader.SendInput",
                    status = "sent",
                    ok = true,
                    target = new
                    {
                        processName = target.ProcessName,
                        processId = target.ProcessId,
                        windowHandle = FormatWindowHandle(target.WindowHandle),
                        title = target.WindowTitle
                    },
                    mouse = new
                    {
                        clientX = options.ClientX,
                        clientY = options.ClientY,
                        screenX = mouseResult.ScreenX,
                        screenY = mouseResult.ScreenY,
                        holdMilliseconds = options.HoldMilliseconds,
                        sentInputEvents = mouseResult.SentInputEvents,
                        backend = "SendInput-absolute-mouse"
                    },
                    input = new
                    {
                        mode = "MouseLeftClick",
                        holdMilliseconds = options.HoldMilliseconds,
                        sentInputEvents = mouseResult.SentInputEvents
                    },
                    focus,
                    safety = new
                    {
                        automaticEscUsed = false,
                        proofAnchorRequired = false,
                        movementVerificationPerformed = false,
                        cheatEngineUsed = false,
                        postMessageMouseUsed = false,
                        requiresForeground = true
                    }
                };
            }
            else
            {
                var key = ResolveKeyBinding(options.Key);
                var sendResult = SendKey(key, options);

                if (!options.NoRefocus && focus.PreviousForegroundWindow != nint.Zero &&
                    focus.PreviousForegroundWindow != target.WindowHandle)
                {
                    _ = Native.SetForegroundWindow(focus.PreviousForegroundWindow);
                }

                result = new
                {
                    schemaVersion = 1,
                    tool = "RiftReader.SendInput",
                    status = "sent",
                    ok = true,
                    target = new
                    {
                        processName = target.ProcessName,
                        processId = target.ProcessId,
                        windowHandle = FormatWindowHandle(target.WindowHandle),
                        title = target.WindowTitle
                    },
                    key = new
                    {
                        requested = options.Key,
                        virtualKey = key.VirtualKey,
                        virtualKeyHex = $"0x{key.VirtualKey:X2}",
                        scanCode = sendResult.ScanCode,
                        scanCodeHex = sendResult.ScanCode.HasValue ? $"0x{sendResult.ScanCode.Value:X}" : null,
                        shiftState = key.ShiftState
                    },
                    input = new
                    {
                        mode = options.InputMode.ToString(),
                        holdMilliseconds = options.HoldMilliseconds,
                        alt = options.Alt,
                        shift = options.Shift,
                        ctrl = options.Ctrl,
                        sentInputEvents = sendResult.SentInputEvents
                    },
                    focus,
                    safety = new
                    {
                        automaticEscUsed = false,
                        proofAnchorRequired = false,
                        movementVerificationPerformed = false,
                        cheatEngineUsed = false,
                        postMessageMouseUsed = false,
                        requiresForeground = true
                    }
                };
            }

            WriteResult(options, result);
            return 0;
        }
        catch (Exception ex)
        {
            var error = new
            {
                schemaVersion = 1,
                tool = "RiftReader.SendInput",
                status = "failed",
                ok = false,
                error = ex.Message,
                exceptionType = ex.GetType().FullName,
                inputMode = options?.InputMode.ToString(),
                key = options?.Key
            };

            if (options?.Json == true || args.Any(a => string.Equals(a, "--json", StringComparison.OrdinalIgnoreCase)))
            {
                Console.WriteLine(JsonSerializer.Serialize(error, JsonOptions));
            }
            else
            {
                Console.Error.WriteLine($"[RiftReader.SendInput] ERROR: {ex.Message}");
            }

            return 1;
        }
    }

    private static SendKeyResult SendKey(KeyBinding key, Options options)
    {
        var modifiersDown = new List<int>();
        var primaryDown = false;
        var sentEvents = 0;
        ushort? primaryScanCode = null;
        Exception? releaseFailure = null;

        void Press(int virtualKey)
        {
            var input = NewKeyboardInput(virtualKey, keyUp: false, options.InputMode, out var scanCode);
            SendInputChecked(input);
            sentEvents++;
            if (virtualKey == key.VirtualKey)
            {
                primaryScanCode = scanCode;
            }
        }

        void Release(int virtualKey)
        {
            var input = NewKeyboardInput(virtualKey, keyUp: true, options.InputMode, out _);
            SendInputChecked(input);
            sentEvents++;
        }

        try
        {
            if (options.Alt || (key.ShiftState & 4) != 0)
            {
                Press(0x12);
                modifiersDown.Add(0x12);
                Thread.Sleep(20);
            }

            if (options.Shift || (key.ShiftState & 1) != 0)
            {
                Press(0x10);
                modifiersDown.Add(0x10);
                Thread.Sleep(20);
            }

            if (options.Ctrl || (key.ShiftState & 2) != 0)
            {
                Press(0x11);
                modifiersDown.Add(0x11);
                Thread.Sleep(20);
            }

            Press(key.VirtualKey);
            primaryDown = true;
            Thread.Sleep(Math.Max(0, options.HoldMilliseconds));
            Release(key.VirtualKey);
            primaryDown = false;
        }
        finally
        {
            if (primaryDown)
            {
                try
                {
                    Release(key.VirtualKey);
                }
                catch (Exception ex)
                {
                    releaseFailure ??= ex;
                }
            }

            for (var index = modifiersDown.Count - 1; index >= 0; index--)
            {
                Thread.Sleep(20);
                try
                {
                    Release(modifiersDown[index]);
                }
                catch (Exception ex)
                {
                    releaseFailure ??= ex;
                }
            }
        }

        if (releaseFailure is not null)
        {
            throw new InvalidOperationException("SendInput key release failed after press attempt.", releaseFailure);
        }

        return new SendKeyResult(sentEvents, primaryScanCode);
    }

    private static Native.Input NewKeyboardInput(int virtualKey, bool keyUp, InputMode inputMode, out ushort? scanCode)
    {
        var input = new Native.Input
        {
            Type = InputKeyboard,
            U = new Native.InputUnion
            {
                Ki = new Native.KeyboardInput
                {
                    Time = 0,
                    ExtraInfo = nint.Zero
                }
            }
        };

        scanCode = null;
        if (inputMode == InputMode.ScanCode)
        {
            var mappedScanCode = Native.MapVirtualKey((uint)virtualKey, MapVkToVsc);
            if (mappedScanCode == 0)
            {
                throw new InvalidOperationException($"No scan-code mapping was found for virtual key 0x{virtualKey:X2}.");
            }

            var flags = KeyEventFScanCode;
            if (ExtendedVirtualKeys.Contains(virtualKey))
            {
                flags |= KeyEventFExtendedKey;
            }

            if (keyUp)
            {
                flags |= KeyEventFKeyUp;
            }

            input.U.Ki.VirtualKey = 0;
            input.U.Ki.ScanCode = checked((ushort)mappedScanCode);
            input.U.Ki.Flags = flags;
            scanCode = checked((ushort)mappedScanCode);
            return input;
        }

        input.U.Ki.VirtualKey = checked((ushort)virtualKey);
        input.U.Ki.ScanCode = 0;
        input.U.Ki.Flags = keyUp ? KeyEventFKeyUp : 0;
        return input;
    }

    private static void SendInputChecked(Native.Input input)
    {
        SendInputChecked(new[] { input });
    }

    private static void SendInputChecked(Native.Input[] inputs)
    {
        var inputSize = Marshal.SizeOf<Native.Input>();
        var sent = Native.SendInput((uint)inputs.Length, inputs, inputSize);
        if (sent == inputs.Length)
        {
            return;
        }

        var error = Marshal.GetLastWin32Error();
        var message = new Win32Exception(error).Message;
        throw new InvalidOperationException($"SendInput sent {sent} of {inputs.Length} events. LastWin32Error={error} ({message}).");
    }

    private static MouseClickResult SendMouseLeftClick(nint windowHandle, Options options)
    {
        if (options.ClientX is null || options.ClientY is null)
        {
            throw new ArgumentException("Mouse click requires --client-x and --client-y.");
        }

        // Clicks must stay in the client area only (never non-client chrome: title bar, edges, close).
        if (!Native.GetClientRect(windowHandle, out var clientRect))
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException($"GetClientRect failed. LastWin32Error={error} ({new Win32Exception(error).Message}).");
        }

        var clientWidth = clientRect.Right - clientRect.Left;
        var clientHeight = clientRect.Bottom - clientRect.Top;
        if (clientWidth < 32 || clientHeight < 32)
        {
            throw new InvalidOperationException($"Client area too small for safe click: {clientWidth}x{clientHeight}.");
        }

        // Inset margin so we never land on borders even with 1px rounding.
        const int margin = 8;
        var x = options.ClientX.Value;
        var y = options.ClientY.Value;
        if (x < margin || y < margin || x >= clientWidth - margin || y >= clientHeight - margin)
        {
            throw new InvalidOperationException(
                $"Client click ({x},{y}) is outside safe inset inside client {clientWidth}x{clientHeight} (margin={margin}). " +
                "Use client-center for C2M tests; never click near edges/chrome.");
        }

        var clientPoint = new Native.Point(x, y);
        if (!Native.ClientToScreen(windowHandle, ref clientPoint))
        {
            var error = Marshal.GetLastWin32Error();
            throw new InvalidOperationException($"ClientToScreen failed. LastWin32Error={error} ({new Win32Exception(error).Message}).");
        }

        var screenX = clientPoint.X;
        var screenY = clientPoint.Y;
        var virtualLeft = Native.GetSystemMetrics(SmXvVirtualScreen);
        var virtualTop = Native.GetSystemMetrics(SmYvVirtualScreen);
        var virtualWidth = Math.Max(1, Native.GetSystemMetrics(SmCxVirtualScreen));
        var virtualHeight = Math.Max(1, Native.GetSystemMetrics(SmCyVirtualScreen));

        // Map screen pixels to SendInput absolute range 0..65535 over the virtual desktop.
        var absX = (int)Math.Round(((screenX - virtualLeft) * 65535.0) / Math.Max(1, virtualWidth - 1));
        var absY = (int)Math.Round(((screenY - virtualTop) * 65535.0) / Math.Max(1, virtualHeight - 1));
        absX = Math.Clamp(absX, 0, 65535);
        absY = Math.Clamp(absY, 0, 65535);

        var move = new Native.Input
        {
            Type = InputMouse,
            U = new Native.InputUnion
            {
                Mi = new Native.MouseInput
                {
                    Dx = absX,
                    Dy = absY,
                    MouseData = 0,
                    Flags = MouseEventFMove | MouseEventFAbsolute | MouseEventFVirtualDesk,
                    Time = 0,
                    ExtraInfo = nint.Zero
                }
            }
        };
        var down = new Native.Input
        {
            Type = InputMouse,
            U = new Native.InputUnion
            {
                Mi = new Native.MouseInput
                {
                    Dx = absX,
                    Dy = absY,
                    MouseData = 0,
                    Flags = MouseEventFLeftDown | MouseEventFAbsolute | MouseEventFVirtualDesk,
                    Time = 0,
                    ExtraInfo = nint.Zero
                }
            }
        };
        var up = new Native.Input
        {
            Type = InputMouse,
            U = new Native.InputUnion
            {
                Mi = new Native.MouseInput
                {
                    Dx = absX,
                    Dy = absY,
                    MouseData = 0,
                    Flags = MouseEventFLeftUp | MouseEventFAbsolute | MouseEventFVirtualDesk,
                    Time = 0,
                    ExtraInfo = nint.Zero
                }
            }
        };

        SendInputChecked(new[] { move });
        Thread.Sleep(20);
        SendInputChecked(new[] { down });
        Thread.Sleep(Math.Max(1, options.HoldMilliseconds));
        SendInputChecked(new[] { up });

        return new MouseClickResult(
            SentInputEvents: 3,
            ScreenX: screenX,
            ScreenY: screenY,
            AbsoluteX: absX,
            AbsoluteY: absY);
    }

    private static KeyBinding ResolveKeyBinding(string keyText)
    {
        if (string.IsNullOrWhiteSpace(keyText))
        {
            throw new ArgumentException("Key cannot be blank.");
        }

        var trimmed = keyText.Trim();
        if (NamedKeys.TryGetValue(trimmed, out var namedVirtualKey))
        {
            return new KeyBinding(trimmed, namedVirtualKey, ShiftState: 0);
        }

        if (trimmed.Length != 1)
        {
            throw new ArgumentException("Key must be a single character or one of: Space, Left, Up, Right, Down, Enter, Esc, Backspace, Tab, PageUp, PageDown.");
        }

        var vkScan = Native.VkKeyScan(trimmed[0]);
        if (vkScan == -1)
        {
            throw new ArgumentException($"No virtual-key mapping was found for '{trimmed[0]}'.");
        }

        return new KeyBinding(
            Requested: trimmed,
            VirtualKey: vkScan & 0xFF,
            ShiftState: (vkScan >> 8) & 0xFF);
    }

    private static FocusResult FocusTarget(nint windowHandle, int targetProcessId, int focusDelayMilliseconds)
    {
        var previousForeground = Native.GetForegroundWindow();
        var foregroundBefore = previousForeground;
        _ = Native.GetWindowThreadProcessId(foregroundBefore, out var foregroundBeforeProcessId);
        var foregroundBeforeThreadId = foregroundBefore == nint.Zero
            ? 0
            : Native.GetWindowThreadProcessId(foregroundBefore, out _);
        var targetThreadId = Native.GetWindowThreadProcessId(windowHandle, out var ownerProcessId);
        if (ownerProcessId != targetProcessId)
        {
            throw new InvalidOperationException($"Window {FormatWindowHandle(windowHandle)} belongs to PID {ownerProcessId}, not PID {targetProcessId}.");
        }

        // Never SW_RESTORE on a normal/maximized window — that un-maximizes and can look like a
        // "resize" or land clicks on chrome. Only restore when minimized.
        var wasIconic = Native.IsIconic(windowHandle);
        var wasZoomed = Native.IsZoomed(windowHandle);

        var currentThreadId = Native.GetCurrentThreadId();
        var attachedForeground = false;
        var attachedTarget = false;

        try
        {
            if (foregroundBeforeThreadId != 0 && foregroundBeforeThreadId != currentThreadId)
            {
                attachedForeground = Native.AttachThreadInput(currentThreadId, foregroundBeforeThreadId, true);
            }

            if (targetThreadId != 0 && targetThreadId != currentThreadId)
            {
                attachedTarget = Native.AttachThreadInput(currentThreadId, targetThreadId, true);
            }

            if (wasIconic)
            {
                _ = Native.ShowWindow(windowHandle, SwRestore);
            }
            else if (!Native.IsWindowVisible(windowHandle))
            {
                _ = Native.ShowWindow(windowHandle, SwShow);
            }

            // Activate without changing maximize/normal geometry.
            _ = Native.SetForegroundWindow(windowHandle);
            Thread.Sleep(Math.Max(0, focusDelayMilliseconds));
        }
        finally
        {
            if (attachedTarget)
            {
                _ = Native.AttachThreadInput(currentThreadId, targetThreadId, false);
            }

            if (attachedForeground)
            {
                _ = Native.AttachThreadInput(currentThreadId, foregroundBeforeThreadId, false);
            }
        }

        var foregroundAfter = Native.GetForegroundWindow();
        _ = Native.GetWindowThreadProcessId(foregroundAfter, out var foregroundAfterProcessId);
        return new FocusResult(
            PreviousForegroundWindow: previousForeground,
            ForegroundBeforeWindow: foregroundBefore,
            ForegroundBeforeProcessId: (int)foregroundBeforeProcessId,
            ForegroundAfterWindow: foregroundAfter,
            ForegroundProcessId: (int)foregroundAfterProcessId,
            ExactHwndForeground: foregroundAfter == windowHandle,
            TargetProcessForeground: foregroundAfterProcessId == targetProcessId,
            WasIconic: wasIconic,
            WasZoomed: wasZoomed,
            UsedShowRestore: wasIconic);
    }

    private static void WriteResult(Options options, object result)
    {
        if (options.Json)
        {
            Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
            return;
        }

        var json = JsonSerializer.Serialize(result, JsonOptions);
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        Console.WriteLine("[RiftReader.SendInput] SUCCESS");
        Console.WriteLine($"Target : {root.GetProperty("target").GetProperty("processName").GetString()} [{root.GetProperty("target").GetProperty("processId").GetInt32()}] {root.GetProperty("target").GetProperty("windowHandle").GetString()}");
        if (root.TryGetProperty("key", out var keyEl))
        {
            Console.WriteLine($"Key    : {keyEl.GetProperty("requested").GetString()} ({keyEl.GetProperty("virtualKeyHex").GetString()})");
        }
        else if (root.TryGetProperty("mouse", out var mouseEl))
        {
            Console.WriteLine($"Mouse  : client=({mouseEl.GetProperty("clientX").GetInt32()},{mouseEl.GetProperty("clientY").GetInt32()}) screen=({mouseEl.GetProperty("screenX").GetInt32()},{mouseEl.GetProperty("screenY").GetInt32()})");
        }
        Console.WriteLine($"Mode   : {root.GetProperty("input").GetProperty("mode").GetString()}");
    }

    private static string FormatWindowHandle(nint handle)
    {
        return handle == nint.Zero ? "0x0" : $"0x{handle.ToInt64():X}";
    }

    private static void WriteUsage()
    {
        Console.WriteLine("RiftReader.SendInput");
        Console.WriteLine("Usage:");
        Console.WriteLine("  # Keyboard (ScanCode preferred for movement keys)");
        Console.WriteLine("  dotnet run --project tools/RiftReader.SendInput/RiftReader.SendInput.csproj -- --key w --pid 1234 --hwnd 0x123456 --input-mode ScanCode --json");
        Console.WriteLine("  # Mouse left-click at client coords (requires foreground focus; NOT PostMessage)");
        Console.WriteLine("  dotnet run --project tools/RiftReader.SendInput/RiftReader.SendInput.csproj -- --client-x 400 --client-y 300 --pid 1234 --hwnd 0x123456 --hold-ms 40 --json");
    }

    private sealed record KeyBinding(string Requested, int VirtualKey, int ShiftState);

    private sealed record SendKeyResult(int SentInputEvents, ushort? ScanCode);

    private sealed record MouseClickResult(int SentInputEvents, int ScreenX, int ScreenY, int AbsoluteX, int AbsoluteY);
}

internal sealed record FocusResult(
    [property: JsonIgnore] nint PreviousForegroundWindow,
    [property: JsonIgnore] nint ForegroundBeforeWindow,
    int ForegroundBeforeProcessId,
    [property: JsonIgnore] nint ForegroundAfterWindow,
    int ForegroundProcessId,
    bool ExactHwndForeground,
    bool TargetProcessForeground,
    bool WasIconic = false,
    bool WasZoomed = false,
    bool UsedShowRestore = false)
{
    public string PreviousForegroundWindowHex => Format(PreviousForegroundWindow);

    public string ForegroundBeforeWindowHex => Format(ForegroundBeforeWindow);

    public string ForegroundAfterWindowHex => Format(ForegroundAfterWindow);

    private static string Format(nint handle) => handle == nint.Zero ? "0x0" : $"0x{handle.ToInt64():X}";
}

internal enum InputMode
{
    VirtualKey,
    ScanCode
}

internal sealed class Options
{
    public string Key { get; private init; } = string.Empty;

    public int HoldMilliseconds { get; private init; } = 250;

    public string ProcessName { get; private init; } = "rift_x64";

    public int? TargetProcessId { get; private init; }

    public string? TargetWindowHandle { get; private init; }

    public string? TitleContains { get; private init; }

    public int FocusDelayMilliseconds { get; private init; } = 500;

    public int? ClientX { get; private init; }

    public int? ClientY { get; private init; }

    public bool IsMouseClick => ClientX is not null && ClientY is not null;

    public bool Alt { get; private init; }

    public bool Shift { get; private init; }

    public bool Ctrl { get; private init; }

    public bool NoRefocus { get; private init; }

    public bool Json { get; private init; }

    public bool ShowHelp { get; private init; }

    public InputMode InputMode { get; private init; } = InputMode.ScanCode;

    public static Options Parse(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var flags = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (!arg.StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException($"Unexpected positional argument: {arg}");
            }

            var name = arg[2..];
            if (IsFlag(name))
            {
                flags.Add(name);
                continue;
            }

            if (index + 1 >= args.Length)
            {
                throw new ArgumentException($"Missing value for --{name}.");
            }

            values[name] = args[++index];
        }

        if (flags.Contains("help"))
        {
            return new Options { ShowHelp = true };
        }

        var hasKey = values.TryGetValue("key", out var key) && !string.IsNullOrWhiteSpace(key);
        var hasClientX = values.TryGetValue("client-x", out var clientXText);
        var hasClientY = values.TryGetValue("client-y", out var clientYText);
        if (hasClientX != hasClientY)
        {
            throw new ArgumentException("Mouse click requires both --client-x and --client-y.");
        }

        var isMouse = hasClientX && hasClientY;
        if (!hasKey && !isMouse)
        {
            throw new ArgumentException("Either --key (keyboard) or --client-x/--client-y (mouse click) is required.");
        }

        if (hasKey && isMouse)
        {
            throw new ArgumentException("Provide either --key or --client-x/--client-y, not both.");
        }

        return new Options
        {
            Key = hasKey ? key! : string.Empty,
            HoldMilliseconds = GetInt(values, "hold-ms", isMouse ? 40 : 250),
            ProcessName = GetString(values, "process-name", "rift_x64"),
            TargetProcessId = values.TryGetValue("pid", out var pidText) ? int.Parse(pidText, CultureInfo.InvariantCulture) : null,
            TargetWindowHandle = values.TryGetValue("hwnd", out var hwnd) ? hwnd : null,
            TitleContains = values.TryGetValue("title-contains", out var titleContains) ? titleContains : null,
            FocusDelayMilliseconds = GetInt(values, "focus-delay-ms", 500),
            ClientX = isMouse ? int.Parse(clientXText!, CultureInfo.InvariantCulture) : null,
            ClientY = isMouse ? int.Parse(clientYText!, CultureInfo.InvariantCulture) : null,
            Alt = flags.Contains("alt"),
            Shift = flags.Contains("shift"),
            Ctrl = flags.Contains("ctrl"),
            NoRefocus = flags.Contains("no-refocus"),
            Json = flags.Contains("json"),
            InputMode = ParseInputMode(GetString(values, "input-mode", "ScanCode"))
        };
    }

    private static bool IsFlag(string name)
    {
        return name.Equals("alt", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("shift", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("ctrl", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("no-refocus", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("json", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("help", StringComparison.OrdinalIgnoreCase);
    }

    private static string GetString(Dictionary<string, string> values, string name, string defaultValue)
    {
        return values.TryGetValue(name, out var value) ? value : defaultValue;
    }

    private static int GetInt(Dictionary<string, string> values, string name, int defaultValue)
    {
        return values.TryGetValue(name, out var value)
            ? int.Parse(value, CultureInfo.InvariantCulture)
            : defaultValue;
    }

    private static InputMode ParseInputMode(string value)
    {
        if (value.Equals("VirtualKey", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("virtual-key", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("vk", StringComparison.OrdinalIgnoreCase))
        {
            return InputMode.VirtualKey;
        }

        if (value.Equals("ScanCode", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("scan-code", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("scancode", StringComparison.OrdinalIgnoreCase))
        {
            return InputMode.ScanCode;
        }

        throw new ArgumentException("--input-mode must be VirtualKey or ScanCode.");
    }
}

internal static class TargetResolver
{
    public static TargetInfo Resolve(Options options)
    {
        if (!string.IsNullOrWhiteSpace(options.TargetWindowHandle))
        {
            var handle = ParseWindowHandle(options.TargetWindowHandle);
            if (!Native.IsWindow(handle))
            {
                throw new InvalidOperationException($"Target HWND {options.TargetWindowHandle} is not a valid window.");
            }

            _ = Native.GetWindowThreadProcessId(handle, out var ownerPid);
            if (ownerPid == 0)
            {
                throw new InvalidOperationException($"Target HWND {options.TargetWindowHandle} did not resolve to a process.");
            }

            if (options.TargetProcessId is not null && ownerPid != options.TargetProcessId.Value)
            {
                throw new InvalidOperationException($"Target HWND {options.TargetWindowHandle} belongs to PID {ownerPid}, not PID {options.TargetProcessId.Value}.");
            }

            var process = Process.GetProcessById((int)ownerPid);
            ValidateProcess(process, options.ProcessName);
            var title = GetWindowTitle(handle);
            ValidateTitle(title, options.TitleContains);
            return new TargetInfo(process.ProcessName, process.Id, handle, title);
        }

        if (options.TargetProcessId is not null)
        {
            var process = Process.GetProcessById(options.TargetProcessId.Value);
            ValidateProcess(process, options.ProcessName);
            if (process.MainWindowHandle == nint.Zero || !Native.IsWindow(process.MainWindowHandle))
            {
                throw new InvalidOperationException($"PID {process.Id} does not expose a valid main window handle.");
            }

            var title = GetWindowTitle(process.MainWindowHandle);
            ValidateTitle(title, options.TitleContains);
            return new TargetInfo(process.ProcessName, process.Id, process.MainWindowHandle, title);
        }

        var expectedName = Path.GetFileNameWithoutExtension(options.ProcessName);
        var matches = Process.GetProcessesByName(expectedName)
            .Where(process => process.MainWindowHandle != nint.Zero)
            .OrderByDescending(process => SafeStartTimeUtc(process))
            .ToArray();

        if (matches.Length != 1)
        {
            throw new InvalidOperationException($"Expected exactly one windowed {expectedName} process; found {matches.Length}.");
        }

        var selected = matches[0];
        var selectedTitle = GetWindowTitle(selected.MainWindowHandle);
        ValidateTitle(selectedTitle, options.TitleContains);
        return new TargetInfo(selected.ProcessName, selected.Id, selected.MainWindowHandle, selectedTitle);
    }

    private static DateTime SafeStartTimeUtc(Process process)
    {
        try
        {
            return process.StartTime.ToUniversalTime();
        }
        catch
        {
            return DateTime.MinValue;
        }
    }

    private static void ValidateProcess(Process process, string expectedName)
    {
        var normalized = Path.GetFileNameWithoutExtension(expectedName);
        if (!process.ProcessName.Equals(normalized, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"Resolved PID {process.Id} is {process.ProcessName}, not {normalized}.");
        }
    }

    private static void ValidateTitle(string title, string? titleContains)
    {
        if (!string.IsNullOrWhiteSpace(titleContains) &&
            title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
        {
            throw new InvalidOperationException($"Window title '{title}' does not contain '{titleContains}'.");
        }
    }

    private static nint ParseWindowHandle(string handleText)
    {
        var trimmed = handleText.Trim();
        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            var raw = ulong.Parse(trimmed[2..], NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture);
            return unchecked((nint)(long)raw);
        }

        return (nint)long.Parse(trimmed, CultureInfo.InvariantCulture);
    }

    private static string GetWindowTitle(nint handle)
    {
        var length = Native.GetWindowTextLength(handle);
        if (length <= 0)
        {
            return string.Empty;
        }

        var builder = new StringBuilder(length + 1);
        _ = Native.GetWindowText(handle, builder, builder.Capacity);
        return builder.ToString();
    }
}

internal sealed record TargetInfo(string ProcessName, int ProcessId, nint WindowHandle, string WindowTitle)
{
    public string WindowHandleHex => WindowHandle == nint.Zero ? "0x0" : $"0x{WindowHandle.ToInt64():X}";
}

internal static class Native
{
    [StructLayout(LayoutKind.Sequential)]
    public struct Input
    {
        public uint Type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion
    {
        [FieldOffset(0)] public MouseInput Mi;
        [FieldOffset(0)] public KeyboardInput Ki;
        [FieldOffset(0)] public HardwareInput Hi;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MouseInput
    {
        public int Dx;
        public int Dy;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct HardwareInput
    {
        public uint Message;
        public ushort ParamL;
        public ushort ParamH;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint inputCount, Input[] inputs, int inputSize);

    [DllImport("user32.dll", EntryPoint = "VkKeyScanW", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern short VkKeyScan(char character);

    [DllImport("user32.dll", EntryPoint = "MapVirtualKeyW", SetLastError = true)]
    public static extern uint MapVirtualKey(uint code, uint mapType);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ShowWindow(nint windowHandle, int commandShow);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool BringWindowToTop(nint windowHandle);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetForegroundWindow(nint windowHandle);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern nint GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(nint windowHandle);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(nint windowHandle, out uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint GetCurrentThreadId();

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool AttachThreadInput(uint attachThreadId, uint attachToThreadId, bool attach);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLength(nint windowHandle);

    [StructLayout(LayoutKind.Sequential)]
    public struct Point
    {
        public int X;
        public int Y;

        public Point(int x, int y)
        {
            X = x;
            Y = y;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool ClientToScreen(nint windowHandle, ref Point point);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetClientRect(nint windowHandle, out Rect rect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetSystemMetrics(int index);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsIconic(nint windowHandle);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsZoomed(nint windowHandle);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(nint windowHandle);

    [DllImport("user32.dll", EntryPoint = "GetWindowTextW", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(nint windowHandle, StringBuilder text, int maxCount);
}

// END_OF_SCRIPT_MARKER
