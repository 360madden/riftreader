using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using RiftReader.Reader.Cli;
using RiftReader.Reader.Models;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Debugging;

public static class DebugTraceRequestBuilder
{
    public const int SchemaVersion = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true
    };

    public static bool IsDebugTraceMode(ReaderOptions options) =>
        options.DebugTraceInstruction ||
        options.DebugTraceMemoryWrite ||
        options.DebugTraceMemoryAccess ||
        options.DebugTracePlayerCoordWrite;

    public static DebugTraceRequest? TryBuild(ReaderOptions options, Process process, ProcessTarget target, out string? error)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(process);
        ArgumentNullException.ThrowIfNull(target);

        error = null;

        var mode = ResolveMode(options);
        if (mode is null)
        {
            error = "A public debug trace mode was not selected.";
            return null;
        }

        var outputDirectory = ResolveOutputDirectory(options.DebugOutputDirectory, mode, options.DebugLabel);
        var targetSpec = new DebugTraceTargetSpec(
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ModuleName: target.ModuleName,
            MainWindowTitle: target.MainWindowTitle,
            ProcessStartTimeUtc: TryGetProcessStartTimeUtc(process));

        DebugTraceBreakpointSpec breakpoint;
        if (options.DebugTracePlayerCoordWrite)
        {
            var traceDocument = PlayerCoordTraceAnchorLoader.TryLoad(options.PlayerCoordTraceFile, out var traceError);
            if (traceDocument?.Trace is null || string.IsNullOrWhiteSpace(traceDocument.SourceFile))
            {
                error = traceError ?? "Unable to load the player coord trace anchor for the debug-trace preset.";
                return null;
            }

            breakpoint = BuildPlayerCoordBreakpoint(traceDocument);
        }
        else
        {
            breakpoint = BuildExplicitBreakpoint(options, mode);
        }

        return new DebugTraceRequest(
            SchemaVersion: SchemaVersion,
            Mode: mode,
            Target: targetSpec,
            Breakpoint: breakpoint,
            Capture: new DebugTraceCaptureOptions(
                StackBytes: options.DebugCaptureStackBytes,
                MemoryWindowBytes: options.DebugCaptureMemoryWindowBytes),
            Limits: new DebugTraceLimits(
                TimeoutMilliseconds: options.DebugTimeoutMilliseconds,
                MaxHits: options.DebugMaxHits,
                MaxEvents: options.DebugMaxEvents),
            Capabilities: BuildCapabilities(options),
            OutputDirectory: outputDirectory,
            Label: options.DebugLabel,
            MarkerInputFile: options.DebugMarkerInputFile,
            PresetName: options.DebugTracePlayerCoordWrite ? "player-coord-write" : null,
            PlayerCoordTraceFile: options.PlayerCoordTraceFile,
            ReaderBridgeSnapshotFile: options.ReaderBridgeSnapshotFile,
            JsonOutput: options.JsonOutput);
    }

    public static string WriteRequestFile(DebugTraceRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        Directory.CreateDirectory(request.OutputDirectory);
        var requestFile = Path.Combine(request.OutputDirectory, "debug-request.json");
        File.WriteAllText(requestFile, JsonSerializer.Serialize(request, JsonOptions));
        return requestFile;
    }

    public static DebugTraceRequest? TryLoadRequest(string? requestFile, out string? error)
    {
        if (string.IsNullOrWhiteSpace(requestFile))
        {
            error = "A debug request file is required.";
            return null;
        }

        var fullPath = Path.GetFullPath(requestFile);
        if (!File.Exists(fullPath))
        {
            error = $"Debug request file '{fullPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(fullPath);
            var request = JsonSerializer.Deserialize<DebugTraceRequest>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

            if (request is null)
            {
                error = $"Debug request file '{fullPath}' did not contain a valid document.";
                return null;
            }

            error = null;
            return request with { OutputDirectory = Path.GetFullPath(request.OutputDirectory) };
        }
        catch (Exception ex)
        {
            error = $"Unable to load debug request file '{fullPath}': {ex.Message}";
            return null;
        }
    }

    private static DebugTraceBreakpointSpec BuildExplicitBreakpoint(ReaderOptions options, string mode)
    {
        var kind = mode switch
        {
            "debug-trace-memory-write" => "memory-write",
            "debug-trace-memory-access" => "memory-access",
            _ => "instruction"
        };

        var resolutionMode = options.DebugAddress.HasValue
            ? "absolute-address"
            : "module-relative";

        return new DebugTraceBreakpointSpec(
            Kind: kind,
            ResolutionMode: resolutionMode,
            Address: options.DebugAddress.HasValue ? FormatAddress(options.DebugAddress.Value) : null,
            ModuleName: options.DebugModuleName,
            ModuleOffset: options.DebugModuleOffset.HasValue ? FormatAddress(options.DebugModuleOffset.Value) : null,
            Width: options.DebugWidth,
            Pattern: null,
            SourceFile: null,
            AccessType: kind,
            Metadata: null);
    }

    private static DebugTraceBreakpointSpec BuildPlayerCoordBreakpoint(PlayerCoordTraceAnchorDocument traceDocument)
    {
        var trace = traceDocument.Trace!;
        var metadata = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(trace.Instruction))
        {
            metadata["instruction"] = trace.Instruction;
        }

        if (!string.IsNullOrWhiteSpace(trace.InstructionBytes))
        {
            metadata["instructionBytes"] = NormalizeHexBytes(trace.InstructionBytes) ?? trace.InstructionBytes;
        }

        if (!string.IsNullOrWhiteSpace(trace.EffectiveAddress))
        {
            metadata["effectiveAddress"] = trace.EffectiveAddress;
        }

        if (!string.IsNullOrWhiteSpace(trace.TargetAddress))
        {
            metadata["targetAddress"] = trace.TargetAddress;
        }

        return new DebugTraceBreakpointSpec(
            Kind: "instruction",
            ResolutionMode: "player-coord-trace",
            Address: NormalizeAddress(trace.InstructionAddress),
            ModuleName: trace.ModuleName,
            ModuleOffset: NormalizeAddress(trace.ModuleOffset),
            Width: 4,
            Pattern: !string.IsNullOrWhiteSpace(trace.NormalizedPattern)
                ? trace.NormalizedPattern
                : NormalizeHexBytes(trace.InstructionBytes),
            SourceFile: traceDocument.SourceFile,
            AccessType: trace.AccessType,
            Metadata: metadata);
    }

    private static string? ResolveMode(ReaderOptions options)
    {
        if (options.DebugTraceInstruction) return "debug-trace-instruction";
        if (options.DebugTraceMemoryWrite) return "debug-trace-memory-write";
        if (options.DebugTraceMemoryAccess) return "debug-trace-memory-access";
        if (options.DebugTracePlayerCoordWrite) return "debug-trace-player-coord-write";
        return null;
    }

    private static DebugTraceCapabilities BuildCapabilities(ReaderOptions options) =>
        new(
            PreflightValidation: true,
            RegisterCapture: !options.DebugDisableRegisterCapture,
            StackCapture: !options.DebugDisableStackCapture,
            MemoryWindows: !options.DebugDisableMemoryWindows,
            InstructionDecode: !options.DebugDisableInstructionDecode,
            InstructionFingerprint: !options.DebugDisableInstructionFingerprint,
            HitClustering: !options.DebugDisableHitClustering,
            FollowUpSuggestions: !options.DebugDisableFollowUpSuggestions,
            Artifacts: true);

    private static string ResolveOutputDirectory(string? explicitPath, string mode, string? label)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        var safeLabel = string.IsNullOrWhiteSpace(label)
            ? mode
            : string.Concat(label.Where(static ch => !Path.GetInvalidFileNameChars().Contains(ch))).Trim();
        if (string.IsNullOrWhiteSpace(safeLabel))
        {
            safeLabel = mode;
        }

        var traceId = $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmss}-{safeLabel}";
        return Path.Combine(repoRoot, "scripts", "captures", "debug-traces", traceId);
    }

    private static string? TryGetProcessStartTimeUtc(Process process)
    {
        try
        {
            return process.StartTime.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);
        }
        catch
        {
            return null;
        }
    }

    private static string? TryFindRepoRoot(string startDirectory)
    {
        if (string.IsNullOrWhiteSpace(startDirectory))
        {
            return null;
        }

        var current = new DirectoryInfo(startDirectory);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }

    private static string? NormalizeAddress(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? $"0x{value[2..].Trim().ToUpperInvariant()}"
            : value.Trim();
    }

    private static string? NormalizeHexBytes(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var compact = value.Replace(" ", string.Empty, StringComparison.OrdinalIgnoreCase);
        if (compact.Length == 0 || compact.Length % 2 != 0)
        {
            return value.Trim();
        }

        return string.Join(' ', Enumerable.Range(0, compact.Length / 2)
            .Select(index => compact.Substring(index * 2, 2).ToUpperInvariant()));
    }

    private static string FormatAddress(nint address)
    {
        var numeric = address.ToInt64();
        return $"0x{numeric:X}";
    }
}
