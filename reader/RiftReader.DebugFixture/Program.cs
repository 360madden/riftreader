using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace RiftReader.DebugFixture;

public static class FixtureAssemblyMarker;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (!TryParseArgs(args, out var options, out var error))
        {
            Console.Error.WriteLine(error);
            return 1;
        }

        var readyFile = Path.GetFullPath(options.ReadyFile);
        Directory.CreateDirectory(Path.GetDirectoryName(readyFile)!);

        var stateAddress = Marshal.AllocHGlobal(sizeof(int));
        try
        {
            Marshal.WriteInt32(stateAddress, 0);

            PrepareForBreakpoint(nameof(ReadValue));
            PrepareForBreakpoint(nameof(WriteValue));

            for (var index = 0; index < 64; index++)
            {
                var current = ReadValue(stateAddress);
                WriteValue(stateAddress, current + 1);
            }

            var process = Process.GetCurrentProcess();
            var metadata = new FixtureReadyRecord(
                ProcessId: Environment.ProcessId,
                ProcessName: process.ProcessName,
                ModuleName: process.MainModule?.ModuleName ?? Path.GetFileName(Environment.ProcessPath) ?? "unknown",
                MemoryAddress: FormatAddress(stateAddress),
                ReadMethodAddress: FormatAddress(GetMethodAddress(nameof(ReadValue))),
                WriteMethodAddress: FormatAddress(GetMethodAddress(nameof(WriteValue))),
                InitialValue: Marshal.ReadInt32(stateAddress));

            File.WriteAllText(
                readyFile,
                JsonSerializer.Serialize(
                    metadata,
                    new JsonSerializerOptions
                    {
                        WriteIndented = true
                    }));

            Console.WriteLine(JsonSerializer.Serialize(metadata));

            while (true)
            {
                var current = ReadValue(stateAddress);
                WriteValue(stateAddress, unchecked(current + 1));
                Thread.SpinWait(20_000);
            }
        }
        finally
        {
            Marshal.FreeHGlobal(stateAddress);
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
    private static int ReadValue(nint address) =>
        Marshal.ReadInt32(address);

    [MethodImpl(MethodImplOptions.NoInlining | MethodImplOptions.NoOptimization)]
    private static void WriteValue(nint address, int value) =>
        Marshal.WriteInt32(address, value);

    private static void PrepareForBreakpoint(string methodName)
    {
        var method = typeof(Program).GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException($"Unable to resolve fixture method '{methodName}'.");
        RuntimeHelpers.PrepareMethod(method.MethodHandle);
    }

    private static nint GetMethodAddress(string methodName)
    {
        var method = typeof(Program).GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException($"Unable to resolve fixture method '{methodName}'.");
        return method.MethodHandle.GetFunctionPointer();
    }

    private static bool TryParseArgs(string[] args, out FixtureOptions options, out string? error)
    {
        string? readyFile = null;
        for (var index = 0; index < args.Length; index++)
        {
            if (string.Equals(args[index], "--ready-file", StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 >= args.Length || string.IsNullOrWhiteSpace(args[index + 1]))
                {
                    options = default;
                    error = "Missing value for --ready-file.";
                    return false;
                }

                readyFile = args[++index];
                continue;
            }

            options = default;
            error = $"Unknown argument '{args[index]}'.";
            return false;
        }

        if (string.IsNullOrWhiteSpace(readyFile))
        {
            options = default;
            error = "--ready-file is required.";
            return false;
        }

        options = new FixtureOptions(Path.GetFullPath(readyFile));
        error = null;
        return true;
    }

    private static string FormatAddress(nint address) =>
        $"0x{address.ToInt64():X}";

    private readonly record struct FixtureOptions(string ReadyFile);

    private sealed record FixtureReadyRecord(
        int ProcessId,
        string ProcessName,
        string ModuleName,
        string MemoryAddress,
        string ReadMethodAddress,
        string WriteMethodAddress,
        int InitialValue);
}
