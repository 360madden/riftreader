using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using Iced.Intel;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Processes;
using Register = Iced.Intel.Register;

namespace RiftReader.Reader.Debugging;

public static class DebugTraceWorker
{
    private const int SchemaVersion = 1;
    private const int MarkerPollSliceMilliseconds = 50;
    private const int InstructionReadBytes = 16;

    private static readonly JsonSerializerOptions PrettyJsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    private static readonly JsonSerializerOptions NdjsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public static int Execute(DebugTraceRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        var outputDirectory = Path.GetFullPath(request.OutputDirectory);
        Directory.CreateDirectory(outputDirectory);

        var traceId = new DirectoryInfo(outputDirectory).Name;
        var requestFile = Path.Combine(outputDirectory, "debug-request.json");
        var packageManifestFile = Path.Combine(outputDirectory, "package-manifest.json");
        var manifestFile = Path.Combine(outputDirectory, "debug-trace-manifest.json");
        var eventsFile = Path.Combine(outputDirectory, "events.ndjson");
        var hitsFile = Path.Combine(outputDirectory, "hits.ndjson");
        var markersFile = Path.Combine(outputDirectory, "markers.ndjson");
        var modulesFile = Path.Combine(outputDirectory, "modules.json");
        var instructionFingerprintsFile = Path.Combine(outputDirectory, "instruction-fingerprints.json");
        var hitClustersFile = Path.Combine(outputDirectory, "hit-clusters.json");
        var followUpSuggestionsFile = Path.Combine(outputDirectory, "follow-up-suggestions.json");
        var failureLedgerFile = ResolveFailureLedgerFile(outputDirectory);
        var tempManifestFile = manifestFile + ".tmp";
        var tempPackageManifestFile = packageManifestFile + ".tmp";
        var tempEventsFile = eventsFile + ".tmp";
        var tempHitsFile = hitsFile + ".tmp";
        var tempMarkersFile = markersFile + ".tmp";
        var tempModulesFile = modulesFile + ".tmp";
        var tempInstructionFingerprintsFile = instructionFingerprintsFile + ".tmp";
        var tempHitClustersFile = hitClustersFile + ".tmp";
        var tempFollowUpSuggestionsFile = followUpSuggestionsFile + ".tmp";

        var startedAtUtc = DateTimeOffset.UtcNow;
        var stopwatch = Stopwatch.StartNew();
        var warnings = new List<string>();
        var modules = Array.Empty<ProcessModuleInfo>();
        var memoryRegions = Array.Empty<ProcessMemoryRegion>();
        var hitRecords = new List<DebugTraceHitRecord>();
        var eventCount = 0;
        var hitCount = 0;
        var markerInputProcessedLineCount = 0;
        var interrupted = false;
        var abnormalExit = false;
        var attachActive = false;
        var attachOutcome = "not-started";
        var detachOutcome = "not-started";
        var cleanupOutcome = "not-started";
        var privilegeState = IsElevated() ? "elevated" : "standard";
        var targetArchitecture = "unknown";
        string? failureMessage = null;
        string? stopReason = null;
        var armedThreads = new HashSet<int>();
        var currentResolvedBreakpoint = default(ResolvedBreakpoint);
        var processId = request.Target.ProcessId;
        var processName = request.Target.ProcessName;
        string? moduleName = request.Target.ModuleName;
        string? mainWindowTitle = request.Target.MainWindowTitle;
        string? processStartTimeUtc = request.Target.ProcessStartTimeUtc;

        ConsoleCancelEventHandler? cancelHandler = null;
        var cancellationRequested = false;
        cancelHandler = (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cancellationRequested = true;
        };
        Console.CancelKeyPress += cancelHandler;
        AddCapabilityWarnings(request.Capabilities, warnings);

        try
        {
            {
                using var eventWriter = new StreamWriter(tempEventsFile, append: false);
                using var hitWriter = new StreamWriter(tempHitsFile, append: false);
                using var markerWriter = new StreamWriter(tempMarkersFile, append: false);

                RecordMarker(
                    markerWriter,
                    traceId,
                    "trace-start",
                    startedAtUtc,
                    0,
                    eventIndex: null,
                    hitIndex: null,
                    request.Label,
                    "Debug trace worker started.",
                    "system",
                    null);

                Process process;
                try
                {
                    process = Process.GetProcessById(request.Target.ProcessId);
                    processName = process.ProcessName;
                    moduleName ??= SafeGetMainModuleName(process);
                    mainWindowTitle ??= SafeGetMainWindowTitle(process);
                    processStartTimeUtc ??= SafeGetProcessStartTimeUtc(process);
                }
                catch (Exception ex)
                {
                    throw new InvalidOperationException($"Unable to resolve PID {request.Target.ProcessId} for debug tracing: {ex.Message}", ex);
                }

                var target = ProcessTarget.FromProcess(process);
                using var reader = ProcessMemoryReader.TryOpen(target, out var readerError)
                    ?? throw new InvalidOperationException(readerError ?? "Unable to open the process for debug trace memory capture.");

                modules = ProcessModuleLocator.ListModules(process).ToArray();
                memoryRegions = reader.EnumerateMemoryRegions().ToArray();
                targetArchitecture = DetermineTargetArchitecture(reader, process);
                currentResolvedBreakpoint = ResolveBreakpoint(request, process, reader, warnings);
                ValidateResolvedBreakpoint(request, currentResolvedBreakpoint, memoryRegions);
                WriteJsonArray(tempModulesFile, modules);

            RecordEvent(
                eventWriter,
                traceId,
                stopwatch.ElapsedMilliseconds,
                ref eventCount,
                "preflight",
                "preflight-complete",
                threadId: null,
                debugEventCode: null,
                exceptionCode: null,
                firstChance: null,
                breakpointId: "primary",
                hitIndex: null,
                moduleRelativeRip: null,
                rawRip: currentResolvedBreakpoint.AddressHex,
                moduleName: currentResolvedBreakpoint.ModuleName,
                moduleOffset: currentResolvedBreakpoint.ModuleOffsetHex,
                statusCode: "preflight-ok",
                message: $"Resolved {currentResolvedBreakpoint.Kind} breakpoint at {currentResolvedBreakpoint.AddressHex}.");

            var cleanupSweepPerformed = TryCleanupFromPriorFailure(process.Id, warnings);
            cleanupOutcome = cleanupSweepPerformed ? "pre-attach-sweep-ok" : "pre-attach-sweep-skipped";

            if (!DebugWindowsNativeMethods.DebugActiveProcess(process.Id))
            {
                throw new InvalidOperationException($"DebugActiveProcess failed: {FormatWin32Error()}");
            }

            attachActive = true;
            attachOutcome = "attached";

            if (!DebugWindowsNativeMethods.DebugSetProcessKillOnExit(false))
            {
                warnings.Add($"DebugSetProcessKillOnExit(false) failed: {FormatWin32Error()}");
            }

            foreach (var threadId in EnumerateThreadIds(process.Id))
            {
                ArmThreadBreakpoint(threadId, currentResolvedBreakpoint, warnings);
                armedThreads.Add(threadId);
            }

            RecordMarker(
                markerWriter,
                traceId,
                "breakpoints-armed",
                DateTimeOffset.UtcNow,
                stopwatch.ElapsedMilliseconds,
                eventIndex: eventCount,
                hitIndex: null,
                request.Label,
                $"Armed {armedThreads.Count} thread(s) for {currentResolvedBreakpoint.Kind} tracing.",
                "system",
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["address"] = currentResolvedBreakpoint.AddressHex,
                    ["module"] = currentResolvedBreakpoint.ModuleName ?? "<absolute>"
                });

            var done = false;
            while (!done)
            {
                DrainMarkerInputFile(
                    markerWriter,
                    request.MarkerInputFile,
                    ref markerInputProcessedLineCount,
                    request.Label,
                    eventCount,
                    hitCount,
                    stopwatch,
                    traceId);

                if (cancellationRequested)
                {
                    interrupted = true;
                    stopReason = "operator-cancelled";
                    break;
                }

                if (stopwatch.ElapsedMilliseconds >= request.Limits.TimeoutMilliseconds)
                {
                    stopReason = "timeout";
                    break;
                }

                if (!DebugWindowsNativeMethods.WaitForDebugEvent(out var debugEvent, MarkerPollSliceMilliseconds))
                {
                    var lastError = (uint)Marshal.GetLastWin32Error();
                    if (lastError == DebugWindowsNativeMethods.ErrorSemTimeout)
                    {
                        continue;
                    }

                    throw new InvalidOperationException($"WaitForDebugEvent failed: {FormatWin32Error((int)lastError)}");
                }

                var shouldStopAfterContinue = false;
                var continueStatus = DebugWindowsNativeMethods.DebugContinue;
                eventCount++;

                var eventTimestamp = DateTimeOffset.UtcNow;
                switch (debugEvent.dwDebugEventCode)
                {
                    case DebugWindowsNativeMethods.DebugEventType.CreateThread:
                        ArmThreadBreakpoint(debugEvent.dwThreadId, currentResolvedBreakpoint, warnings);
                        armedThreads.Add(debugEvent.dwThreadId);
                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            "thread-create",
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            null,
                            null,
                            "primary",
                            null,
                            null,
                            null,
                            null,
                            null,
                            "thread-armed",
                            $"Armed debug registers on thread {debugEvent.dwThreadId}.");
                        SafeCloseHandle(debugEvent.u.CreateThread.hThread);
                        break;

                    case DebugWindowsNativeMethods.DebugEventType.CreateProcess:
                        SafeCloseHandle(debugEvent.u.CreateProcessInfo.hFile);
                        SafeCloseHandle(debugEvent.u.CreateProcessInfo.hProcess);
                        SafeCloseHandle(debugEvent.u.CreateProcessInfo.hThread);
                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            "process-create",
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            null,
                            null,
                            "primary",
                            null,
                            null,
                            null,
                            null,
                            null,
                            "debug-attach-bootstrap",
                            "Observed create-process bootstrap event during attach.");
                        break;

                    case DebugWindowsNativeMethods.DebugEventType.LoadDll:
                        SafeCloseHandle(debugEvent.u.LoadDll.hFile);
                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            "load-dll",
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            null,
                            null,
                            "primary",
                            null,
                            null,
                            null,
                            null,
                            null,
                            "dll-load",
                            null);
                        break;

                    case DebugWindowsNativeMethods.DebugEventType.ExitProcess:
                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            "exit-process",
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            null,
                            null,
                            "primary",
                            null,
                            null,
                            null,
                            null,
                            null,
                            "target-exit",
                            $"Target process exited with code {debugEvent.u.ExitProcess.dwExitCode}.");
                        stopReason = "target-exit";
                        shouldStopAfterContinue = true;
                        break;

                    case DebugWindowsNativeMethods.DebugEventType.Exception:
                    {
                        var exceptionCode = debugEvent.u.Exception.ExceptionRecord.ExceptionCode;
                        var firstChance = debugEvent.u.Exception.dwFirstChance != 0;

                        if (exceptionCode == DebugWindowsNativeMethods.ExceptionBreakpoint)
                        {
                            RecordEvent(
                                eventWriter,
                                traceId,
                                stopwatch.ElapsedMilliseconds,
                                ref eventCount,
                                "runtime",
                                "breakpoint-bootstrap",
                                debugEvent.dwThreadId,
                                (uint)debugEvent.dwDebugEventCode,
                                exceptionCode,
                                firstChance,
                                "primary",
                                null,
                                null,
                                FormatAddress(debugEvent.u.Exception.ExceptionRecord.ExceptionAddress),
                                null,
                                null,
                                "attach-breakpoint",
                                "Observed debugger attach breakpoint.");
                            continueStatus = DebugWindowsNativeMethods.DebugContinue;
                            break;
                        }

                        if (exceptionCode == DebugWindowsNativeMethods.ExceptionSingleStep)
                        {
                            var hit = CaptureSingleStepHit(
                                reader,
                                modules,
                                memoryRegions,
                                request,
                                traceId,
                                debugEvent.dwThreadId,
                                currentResolvedBreakpoint,
                                stopwatch,
                                warnings);

                            if (hit is not null)
                            {
                                hitCount++;
                                hit = hit with { HitIndex = hitCount };
                                hitRecords.Add(hit);
                                WriteNdjson(hitWriter, hit);

                                RecordMarker(
                                    markerWriter,
                                    traceId,
                                    "trace-hit",
                                    eventTimestamp,
                                    stopwatch.ElapsedMilliseconds,
                                    eventIndex: eventCount,
                                    hitIndex: hitCount,
                                    request.Label,
                                    $"Recorded {currentResolvedBreakpoint.Kind} hit #{hitCount}.",
                                    "system",
                                    new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                                    {
                                        ["threadId"] = debugEvent.dwThreadId.ToString(CultureInfo.InvariantCulture),
                                        ["rip"] = hit.RawRip ?? "<unknown>"
                                    });

                                RecordEvent(
                                    eventWriter,
                                    traceId,
                                    stopwatch.ElapsedMilliseconds,
                                    ref eventCount,
                                    "runtime",
                                    "single-step-hit",
                                    debugEvent.dwThreadId,
                                    (uint)debugEvent.dwDebugEventCode,
                                    exceptionCode,
                                    firstChance,
                                    "primary",
                                    hitCount,
                                    hit.ModuleRelativeRip,
                                    hit.RawRip,
                                    ExtractModuleName(hit.ModuleRelativeRip),
                                    ExtractModuleOffset(hit.ModuleRelativeRip),
                                    "hit-recorded",
                                    hit.InstructionText);

                                if (hitCount >= request.Limits.MaxHits)
                                {
                                    stopReason = "max-hits";
                                    shouldStopAfterContinue = true;
                                }
                            }
                            else
                            {
                                RecordEvent(
                                    eventWriter,
                                    traceId,
                                    stopwatch.ElapsedMilliseconds,
                                    ref eventCount,
                                    "runtime",
                                    "single-step-nonmatch",
                                    debugEvent.dwThreadId,
                                    (uint)debugEvent.dwDebugEventCode,
                                    exceptionCode,
                                    firstChance,
                                    "primary",
                                    null,
                                    null,
                                    FormatAddress(debugEvent.u.Exception.ExceptionRecord.ExceptionAddress),
                                    null,
                                    null,
                                    "single-step-ignored",
                                    "Single-step event did not match the active hardware breakpoint.");
                            }

                            continueStatus = DebugWindowsNativeMethods.DebugContinue;
                            break;
                        }

                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            "exception",
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            exceptionCode,
                            firstChance,
                            "primary",
                            null,
                            null,
                            FormatAddress(debugEvent.u.Exception.ExceptionRecord.ExceptionAddress),
                            null,
                            null,
                            "exception-not-handled",
                            null);
                        continueStatus = DebugWindowsNativeMethods.DebugExceptionNotHandled;
                        break;
                    }

                    default:
                        RecordEvent(
                            eventWriter,
                            traceId,
                            stopwatch.ElapsedMilliseconds,
                            ref eventCount,
                            "runtime",
                            debugEvent.dwDebugEventCode.ToString(),
                            debugEvent.dwThreadId,
                            (uint)debugEvent.dwDebugEventCode,
                            null,
                            null,
                            "primary",
                            null,
                            null,
                            null,
                            null,
                            null,
                            "event-observed",
                            null);
                        break;
                }

                if (!DebugWindowsNativeMethods.ContinueDebugEvent(debugEvent.dwProcessId, debugEvent.dwThreadId, continueStatus))
                {
                    warnings.Add($"ContinueDebugEvent failed for thread {debugEvent.dwThreadId}: {FormatWin32Error()}");
                }

                if (eventCount >= request.Limits.MaxEvents)
                {
                    stopReason = "max-events";
                    shouldStopAfterContinue = true;
                }

                if (shouldStopAfterContinue)
                {
                    done = true;
                }
            }

            RecordMarker(
                markerWriter,
                traceId,
                interrupted ? "trace-interrupted" : "trace-stop",
                DateTimeOffset.UtcNow,
                stopwatch.ElapsedMilliseconds,
                eventIndex: eventCount,
                hitIndex: hitCount == 0 ? null : hitCount,
                request.Label,
                interrupted
                    ? "Debug trace interrupted by the operator."
                    : $"Debug trace stopped ({stopReason ?? "completed"}).",
                "system",
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["stopReason"] = stopReason ?? "completed",
                    ["hitCount"] = hitCount.ToString(CultureInfo.InvariantCulture),
                    ["eventCount"] = eventCount.ToString(CultureInfo.InvariantCulture)
                });

                var instructionFingerprints = request.Capabilities.InstructionFingerprint
                    ? BuildInstructionFingerprints(traceId, hitRecords)
                    : Array.Empty<DebugInstructionFingerprintRecord>();
                var hitClusters = request.Capabilities.HitClustering
                    ? BuildHitClusters(traceId, hitRecords)
                    : Array.Empty<DebugHitClusterRecord>();
                var followUpSuggestions = request.Capabilities.FollowUpSuggestions
                    ? BuildFollowUpSuggestions(traceId, hitRecords)
                    : Array.Empty<DebugFollowUpSuggestionRecord>();
                WriteJsonArray(tempInstructionFingerprintsFile, instructionFingerprints);
                WriteJsonArray(tempHitClustersFile, hitClusters);
                WriteJsonArray(tempFollowUpSuggestionsFile, followUpSuggestions);
            }

            PromoteTempFile(tempModulesFile, modulesFile);
            PromoteTempFile(tempEventsFile, eventsFile);
            PromoteTempFile(tempHitsFile, hitsFile);
            PromoteTempFile(tempMarkersFile, markersFile);
            PromoteTempFile(tempInstructionFingerprintsFile, instructionFingerprintsFile);
            PromoteTempFile(tempHitClustersFile, hitClustersFile);
            PromoteTempFile(tempFollowUpSuggestionsFile, followUpSuggestionsFile);
        }
        catch (Exception ex)
        {
            abnormalExit = true;
            failureMessage = ex.Message;
            warnings.Add(ex.Message);
        }
        finally
        {
            try
            {
                if (attachActive)
                {
                    foreach (var threadId in armedThreads.ToArray())
                    {
                        ClearThreadBreakpoint(threadId, warnings);
                    }

                    if (DebugWindowsNativeMethods.DebugActiveProcessStop(processId))
                    {
                        detachOutcome = "detached";
                    }
                    else
                    {
                        detachOutcome = $"detach-failed: {FormatWin32Error()}";
                        warnings.Add(detachOutcome);
                    }
                }
                else
                {
                    detachOutcome = "not-attached";
                }
            }
            catch (Exception ex)
            {
                detachOutcome = $"detach-exception: {ex.Message}";
                warnings.Add(detachOutcome);
            }

            cleanupOutcome = cleanupOutcome is "not-started" ? "cleanup-complete" : cleanupOutcome;

            if (cancelHandler is not null)
            {
                Console.CancelKeyPress -= cancelHandler;
            }
        }

        var completedAtUtc = DateTimeOffset.UtcNow;
        var missingFiles = BuildMissingFiles(
            requestFile,
            eventsFile,
            hitsFile,
            markersFile,
            modulesFile,
            instructionFingerprintsFile,
            hitClustersFile,
            followUpSuggestionsFile);
        var integrityStatus = failureMessage is not null
            ? "failed"
            : missingFiles.Count > 0
                ? "warning"
                : warnings.Count > 0 || interrupted
                    ? "warning"
                    : "ok";
        attachOutcome = failureMessage is not null && attachOutcome == "not-started"
            ? "attach-not-started"
            : attachOutcome;

        if (abnormalExit && !File.Exists(tempMarkersFile) && !File.Exists(markersFile))
        {
            File.WriteAllText(
                tempMarkersFile,
                JsonSerializer.Serialize(
                    new DebugTraceMarkerRecord(
                        Kind: "trace-abnormal-exit",
                        RecordedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                        ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                        EventIndex: eventCount,
                        HitIndex: hitCount == 0 ? null : hitCount,
                        Label: request.Label,
                        Message: failureMessage ?? "Worker exited abnormally.",
                        Source: "system",
                        Metadata: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                        {
                            ["status"] = "failed"
                        }),
                    NdjsonOptions) + Environment.NewLine);
            PromoteTempFile(tempMarkersFile, markersFile);
        }

        var result = new DebugTraceResult(
            SchemaVersion: SchemaVersion,
            Mode: request.Mode,
            TraceId: traceId,
            OutputDirectory: outputDirectory,
            ProcessId: processId,
            ProcessName: processName,
            ModuleName: moduleName,
            MainWindowTitle: mainWindowTitle,
            ProcessStartTimeUtc: processStartTimeUtc,
            BreakpointKind: request.Breakpoint.Kind,
            BreakpointResolutionMode: request.Breakpoint.ResolutionMode,
            BreakpointAddress: currentResolvedBreakpoint.AddressHex ?? request.Breakpoint.Address,
            BreakpointModuleName: currentResolvedBreakpoint.ModuleName ?? request.Breakpoint.ModuleName,
            BreakpointModuleOffset: currentResolvedBreakpoint.ModuleOffsetHex ?? request.Breakpoint.ModuleOffset,
            BreakpointWidth: request.Breakpoint.Width,
            PresetName: request.PresetName,
            Label: request.Label,
            StartedAtUtc: startedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            CompletedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
            ManifestFile: manifestFile,
            PackageManifestFile: packageManifestFile,
            EventsFile: eventsFile,
            HitsFile: hitsFile,
            MarkersFile: markersFile,
            ModulesFile: modulesFile,
            FailureLedgerFile: failureLedgerFile,
            InstructionFingerprintsFile: instructionFingerprintsFile,
            HitClustersFile: hitClustersFile,
            FollowUpSuggestionsFile: followUpSuggestionsFile,
            Interrupted: interrupted,
            AbnormalExit: abnormalExit,
            IntegrityStatus: integrityStatus,
            AttachOutcome: attachOutcome,
            DetachOutcome: detachOutcome,
            CleanupOutcome: cleanupOutcome,
            PrivilegeState: privilegeState,
            TargetArchitecture: targetArchitecture,
            Capabilities: request.Capabilities,
            RequestedHitCount: request.Limits.MaxHits,
            RecordedHitCount: hitCount,
            EventCount: eventCount,
            FailureMessage: failureMessage,
            MissingFiles: missingFiles,
            Modules: modules,
            Warnings: warnings
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray());

        var package = new DebugTracePackageManifestDocument(
            SchemaVersion: SchemaVersion,
            Mode: request.Mode,
            Status: failureMessage is null ? "completed" : "failed",
            IntegrityStatus: integrityStatus,
            GeneratedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
            TraceId: traceId,
            Label: request.Label,
            TraceDirectory: outputDirectory,
            RequestFile: requestFile,
            RecordingManifestFile: manifestFile,
            EventsFile: eventsFile,
            HitsFile: hitsFile,
            MarkersFile: markersFile,
            ModulesFile: modulesFile,
            FailureLedgerFile: failureLedgerFile,
            InstructionFingerprintsFile: instructionFingerprintsFile,
            HitClustersFile: hitClustersFile,
            FollowUpSuggestionsFile: followUpSuggestionsFile,
            ProcessId: processId,
            ProcessName: processName,
            HitCount: hitCount,
            EventCount: eventCount,
            Interrupted: interrupted,
            AbnormalExit: abnormalExit,
            MissingFiles: missingFiles,
            FailureMessage: failureMessage,
            Warnings: result.Warnings);

        File.WriteAllText(tempManifestFile, JsonSerializer.Serialize(result, PrettyJsonOptions));
        PromoteTempFile(tempManifestFile, manifestFile);
        File.WriteAllText(tempPackageManifestFile, JsonSerializer.Serialize(package, PrettyJsonOptions));
        PromoteTempFile(tempPackageManifestFile, packageManifestFile);
        AppendFailureLedger(
            failureLedgerFile,
            new DebugTraceFailureLedgerRecord(
                RecordedAtUtc: completedAtUtc.ToString("O", CultureInfo.InvariantCulture),
                TraceId: traceId,
                ProcessId: processId,
                ProcessName: processName,
                Mode: request.Mode,
                OutputDirectory: outputDirectory,
                Status: failureMessage is null ? "completed" : "failed",
                AbnormalExit: abnormalExit,
                FailureMessage: failureMessage));

        return failureMessage is null ? 0 : 1;
    }

    private static DebugTraceHitRecord? CaptureSingleStepHit(
        ProcessMemoryReader reader,
        IReadOnlyList<ProcessModuleInfo> modules,
        IReadOnlyList<ProcessMemoryRegion> memoryRegions,
        DebugTraceRequest request,
        string traceId,
        int threadId,
        ResolvedBreakpoint breakpoint,
        Stopwatch stopwatch,
        List<string> warnings)
    {
        var threadHandle = OpenThreadForContext(threadId);
        try
        {
            var context = GetContext(threadHandle);

            if ((context.Dr6 & 0x1UL) == 0 && breakpoint.Kind != "instruction")
            {
                return null;
            }

            var rip = unchecked((long)context.Rip);
            var ripAddress = new nint(rip);
            var normalizedRip = NormalizeModuleRelativeAddress(ripAddress, modules);
            var instructionBytes = TryReadWindow(reader, ripAddress, InstructionReadBytes, label: "instruction");
            var decode = request.Capabilities.InstructionDecode
                ? DecodeInstruction(ripAddress, instructionBytes.BytesHex)
                : null;
            var effectiveAddress = decode.HasValue
                ? TryComputeEffectiveAddress(decode.Value.Instruction, context)
                : null;
            var watchedAddress = breakpoint.Kind == "instruction"
                ? effectiveAddress
                : breakpoint.Address;
            var watchedValue = watchedAddress.HasValue
                ? TryReadWindow(reader, watchedAddress.Value, Math.Max(breakpoint.Width ?? 1, 1), label: "watched")
                : default;
            var stackWindow = request.Capabilities.StackCapture && request.Capture.StackBytes > 0
                ? TryReadWindow(reader, unchecked((nint)(long)context.Rsp), request.Capture.StackBytes, "stack")
                : default;
            var ripWindow = request.Capabilities.MemoryWindows && request.Capture.MemoryWindowBytes > 0
                ? TryReadWindow(reader, ripAddress, request.Capture.MemoryWindowBytes, "rip-window")
                : default;
            var effectiveWindow = request.Capabilities.MemoryWindows && effectiveAddress.HasValue && request.Capture.MemoryWindowBytes > 0
                ? TryReadWindow(reader, effectiveAddress.Value, request.Capture.MemoryWindowBytes, "effective-address-window")
                : default;
            var baseRegister = decode.HasValue && decode.Value.BaseRegister is not Register.None
                ? decode.Value.BaseRegister
                : Register.None;
            var baseRegisterValue = baseRegister is not Register.None
                ? TryGetRegisterValue(context, baseRegister)
                : null;
            var baseWindow = request.Capabilities.MemoryWindows && baseRegisterValue.HasValue && request.Capture.MemoryWindowBytes > 0
                ? TryReadWindow(reader, unchecked((nint)(long)baseRegisterValue.Value), Math.Min(request.Capture.MemoryWindowBytes, 64), "base-register-window")
                : default;

            var memoryWindows = new List<DebugMemoryWindowRecord>();
            if (request.Capabilities.MemoryWindows && request.Capture.MemoryWindowBytes > 0)
            {
                memoryWindows.Add(ToMemoryWindowRecord(ripWindow, "rip-window", modules, context));
                if (effectiveWindow.BytesHex is not null || effectiveWindow.Error is not null)
                {
                    memoryWindows.Add(ToMemoryWindowRecord(effectiveWindow, "effective-address-window", modules, context));
                }

                if (baseWindow.BytesHex is not null || baseWindow.Error is not null)
                {
                    memoryWindows.Add(ToMemoryWindowRecord(baseWindow, "base-register-window", modules, context));
                }
            }

            var registerSnapshot = request.Capabilities.RegisterCapture
                ? BuildRegisterSnapshot(context)
                : null;
            var pointerClassifications = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (effectiveAddress.HasValue)
            {
                pointerClassifications["effectiveAddress"] = ClassifyAddress(effectiveAddress.Value, modules, memoryRegions, context);
            }

            if (baseRegisterValue.HasValue)
            {
                pointerClassifications[$"base:{baseRegister}"] = ClassifyAddress(unchecked((nint)(long)baseRegisterValue.Value), modules, memoryRegions, context);
            }

            var callerFingerprint = BuildCallerFingerprint(reader, modules, context);
            var stackFingerprint = stackWindow.Bytes is { Length: > 0 }
                ? Convert.ToHexString(SHA256.HashData(stackWindow.Bytes))
                : null;
            var instructionFingerprint = !request.Capabilities.InstructionFingerprint || normalizedRip is null || !decode.HasValue || decode.Value.InstructionBytes is null
                ? null
                : $"{normalizedRip}|{decode.Value.InstructionBytes}";

            var confidenceNotes = new List<string>();
            if (breakpoint.Kind == "instruction")
            {
                confidenceNotes.Add("Execute breakpoint fired before the traced instruction retired; destination bytes are a pre-write view.");
            }
            else
            {
                confidenceNotes.Add("Hardware data breakpoint fired after the watched access retired; watched bytes represent the post-access view.");
            }

            return new DebugTraceHitRecord(
                HitIndex: 0,
                TraceId: traceId,
                RecordedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                BreakpointKind: breakpoint.Kind,
                ThreadId: threadId,
                ModuleRelativeRip: normalizedRip,
                RawRip: FormatAddress(ripAddress),
                InstructionText: decode.HasValue ? decode.Value.InstructionText : null,
                InstructionBytes: decode.HasValue ? decode.Value.InstructionBytes : null,
                InstructionWindowBytes: ripWindow.BytesHex,
                Registers: registerSnapshot,
                StackWindowBytes: stackWindow.BytesHex,
                EffectiveAddress: effectiveAddress.HasValue ? FormatAddress(effectiveAddress.Value) : null,
                WatchedAddress: watchedAddress.HasValue ? FormatAddress(watchedAddress.Value) : breakpoint.AddressHex,
                WatchedWidth: breakpoint.Width,
                MemoryWindows: memoryWindows,
                ValueBefore: breakpoint.Kind == "instruction" ? watchedValue.BytesHex : null,
                ValueAfter: breakpoint.Kind == "instruction" ? null : watchedValue.BytesHex,
                CallerFingerprint: callerFingerprint,
                StackFingerprint: stackFingerprint,
                InstructionFingerprint: instructionFingerprint,
                PointerClassifications: pointerClassifications,
                Warnings: BuildHitWarnings(watchedValue.Error, decode.HasValue ? decode.Value.Error : null, warnings),
                ConfidenceNotes: confidenceNotes);
        }
        finally
        {
            SafeCloseHandle(threadHandle);
        }
    }

    private static void ValidateResolvedBreakpoint(
        DebugTraceRequest request,
        ResolvedBreakpoint breakpoint,
        IReadOnlyList<ProcessMemoryRegion> memoryRegions)
    {
        if (!Environment.Is64BitProcess)
        {
            throw new InvalidOperationException("The native debug trace worker requires a 64-bit host process.");
        }

        if (!string.Equals(breakpoint.TargetArchitecture, "x64", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"The native debug trace worker only supports x64 targets. Resolved target architecture: {breakpoint.TargetArchitecture}.");
        }

        if (!memoryRegions.Any(region => region.ContainsAddress(breakpoint.Address) && region.IsCommitted && region.IsReadable))
        {
            throw new InvalidOperationException($"Resolved debug breakpoint address {breakpoint.AddressHex} is not inside a readable committed region.");
        }

        if ((request.Mode is "debug-trace-memory-write" or "debug-trace-memory-access") && !request.Breakpoint.Width.HasValue)
        {
            throw new InvalidOperationException("Memory watch debug trace requests require a width.");
        }
    }

    private static ResolvedBreakpoint ResolveBreakpoint(DebugTraceRequest request, Process process, ProcessMemoryReader reader, List<string> warnings)
    {
        var architecture = DetermineTargetArchitecture(reader, process);
        if (string.Equals(request.Breakpoint.ResolutionMode, "player-coord-trace", StringComparison.OrdinalIgnoreCase))
        {
            var traceDocument = Models.PlayerCoordTraceAnchorLoader.TryLoad(request.PlayerCoordTraceFile ?? request.Breakpoint.SourceFile, out var traceError);
            if (traceDocument?.Trace is null)
            {
                throw new InvalidOperationException(traceError ?? "Unable to load the player coord trace artifact for the debug preset.");
            }

            if (string.IsNullOrWhiteSpace(traceDocument.Trace.ModuleName) || string.IsNullOrWhiteSpace(traceDocument.Trace.ModuleOffset))
            {
                throw new InvalidOperationException("The player coord trace artifact does not contain a module-relative instruction anchor.");
            }

            var module = ProcessModuleLocator.FindModule(process, traceDocument.Trace.ModuleName, out var moduleError)
                ?? throw new InvalidOperationException(moduleError ?? $"Unable to resolve module '{traceDocument.Trace.ModuleName}' for the player coord trace preset.");
            var moduleOffset = ParseAddress(traceDocument.Trace.ModuleOffset);
            var absoluteAddress = unchecked((nint)(module.BaseAddress.ToInt64() + moduleOffset.ToInt64()));

            if (!string.IsNullOrWhiteSpace(traceDocument.Trace.NormalizedPattern))
            {
                var scanResult = Scanning.ModulePatternScanner.Scan(
                    process,
                    reader,
                    process.Id,
                    process.ProcessName,
                    module.ModuleName,
                    module.FileName,
                    module.BaseAddress.ToInt64(),
                    module.ModuleMemorySize,
                    traceDocument.Trace.NormalizedPattern,
                    contextBytes: 0);

                if (!scanResult.Found)
                {
                    throw new InvalidOperationException("The player coord trace pattern did not match the live target module.");
                }
            }

            return new ResolvedBreakpoint(
                Kind: "instruction",
                Address: absoluteAddress,
                AddressHex: FormatAddress(absoluteAddress),
                ModuleName: module.ModuleName,
                ModuleOffsetHex: FormatAddress(moduleOffset),
                Width: request.Breakpoint.Width,
                TargetArchitecture: architecture);
        }

        if (request.Breakpoint.Address is not null)
        {
            var address = ParseAddress(request.Breakpoint.Address);
            return new ResolvedBreakpoint(
                Kind: request.Breakpoint.Kind,
                Address: address,
                AddressHex: FormatAddress(address),
                ModuleName: null,
                ModuleOffsetHex: null,
                Width: request.Breakpoint.Width,
                TargetArchitecture: architecture);
        }

        if (!string.IsNullOrWhiteSpace(request.Breakpoint.ModuleName) && !string.IsNullOrWhiteSpace(request.Breakpoint.ModuleOffset))
        {
            var module = ProcessModuleLocator.FindModule(process, request.Breakpoint.ModuleName, out var moduleError)
                ?? throw new InvalidOperationException(moduleError ?? $"Unable to resolve module '{request.Breakpoint.ModuleName}'.");
            var moduleOffset = ParseAddress(request.Breakpoint.ModuleOffset);
            var absoluteAddress = unchecked((nint)(module.BaseAddress.ToInt64() + moduleOffset.ToInt64()));
            return new ResolvedBreakpoint(
                Kind: request.Breakpoint.Kind,
                Address: absoluteAddress,
                AddressHex: FormatAddress(absoluteAddress),
                ModuleName: module.ModuleName,
                ModuleOffsetHex: FormatAddress(moduleOffset),
                Width: request.Breakpoint.Width,
                TargetArchitecture: architecture);
        }

        throw new InvalidOperationException("Unable to resolve a debug breakpoint from the request.");
    }

    private static string DetermineTargetArchitecture(ProcessMemoryReader reader, Process process)
    {
        try
        {
            var processHandle = reader.ProcessHandle;
            if (processHandle == 0)
            {
                return "unknown";
            }

            if (DebugWindowsNativeMethods.IsWow64Process2(processHandle, out var processMachine, out _))
            {
                return processMachine == DebugWindowsNativeMethods.ImageFileMachineUnknown ? "x64" : "wow64";
            }

            if (DebugWindowsNativeMethods.IsWow64Process(processHandle, out var wow64))
            {
                return wow64 ? "wow64" : "x64";
            }
        }
        catch
        {
            // ignored
        }

        return Environment.Is64BitOperatingSystem ? "x64" : "unknown";
    }

    private static IEnumerable<int> EnumerateThreadIds(int processId)
    {
        var snapshot = DebugWindowsNativeMethods.CreateToolhelp32Snapshot(DebugWindowsNativeMethods.Th32CsSnapThread, 0);
        if (snapshot == 0 || snapshot == -1)
        {
            throw new InvalidOperationException($"CreateToolhelp32Snapshot failed: {FormatWin32Error()}");
        }

        try
        {
            var entry = new DebugWindowsNativeMethods.THREADENTRY32
            {
                dwSize = (uint)Marshal.SizeOf<DebugWindowsNativeMethods.THREADENTRY32>()
            };

            if (!DebugWindowsNativeMethods.Thread32First(snapshot, ref entry))
            {
                yield break;
            }

            do
            {
                if (entry.th32OwnerProcessID == processId)
                {
                    yield return unchecked((int)entry.th32ThreadID);
                }
            }
            while (DebugWindowsNativeMethods.Thread32Next(snapshot, ref entry));
        }
        finally
        {
            DebugWindowsNativeMethods.CloseHandle(snapshot);
        }
    }

    private static void ArmThreadBreakpoint(int threadId, ResolvedBreakpoint breakpoint, List<string> warnings)
    {
        var threadHandle = OpenThreadForContext(threadId);
        var suspended = SuspendThread(threadHandle);
        try
        {
            var context = GetContext(threadHandle);
            context.Dr0 = unchecked((ulong)(long)breakpoint.Address);
            context.Dr6 = 0;
            context.Dr7 = ConfigureDebugControl(context.Dr7, breakpoint.Kind, breakpoint.Width ?? 1, enabled: true);

            if (!DebugWindowsNativeMethods.SetThreadContext(threadHandle, ref context))
            {
                throw new InvalidOperationException($"SetThreadContext failed for thread {threadId}: {FormatWin32Error()}");
            }
        }
        catch (Exception ex)
        {
            warnings.Add($"Unable to arm thread {threadId}: {ex.Message}");
        }
        finally
        {
            ResumeThread(threadHandle, suspended);
            SafeCloseHandle(threadHandle);
        }
    }

    private static void ClearThreadBreakpoint(int threadId, List<string> warnings)
    {
        try
        {
            var threadHandle = OpenThreadForContext(threadId);
            var suspended = SuspendThread(threadHandle);
            try
            {
                var context = GetContext(threadHandle);
                context.Dr0 = 0;
                context.Dr6 = 0;
                context.Dr7 = ConfigureDebugControl(context.Dr7, "instruction", 1, enabled: false);

                if (!DebugWindowsNativeMethods.SetThreadContext(threadHandle, ref context))
                {
                    warnings.Add($"SetThreadContext(clear) failed for thread {threadId}: {FormatWin32Error()}");
                }
            }
            finally
            {
                ResumeThread(threadHandle, suspended);
                SafeCloseHandle(threadHandle);
            }
        }
        catch (Exception ex)
        {
            warnings.Add($"Unable to clear thread {threadId}: {ex.Message}");
        }
    }

    private static nint OpenThreadForContext(int threadId)
    {
        var threadHandle = DebugWindowsNativeMethods.OpenThread(
            DebugWindowsNativeMethods.ThreadAccessRights.GetContext |
            DebugWindowsNativeMethods.ThreadAccessRights.SetContext |
            DebugWindowsNativeMethods.ThreadAccessRights.SuspendResume |
            DebugWindowsNativeMethods.ThreadAccessRights.QueryInformation,
            inheritHandle: false,
            threadId);

        if (threadHandle == 0)
        {
            throw new InvalidOperationException($"OpenThread failed for TID {threadId}: {FormatWin32Error()}");
        }

        return threadHandle;
    }

    private static uint SuspendThread(nint threadHandle)
    {
        var result = DebugWindowsNativeMethods.SuspendThread(threadHandle);
        if (result == uint.MaxValue)
        {
            throw new InvalidOperationException($"SuspendThread failed: {FormatWin32Error()}");
        }

        return result;
    }

    private static void ResumeThread(nint threadHandle, uint suspendCount)
    {
        if (suspendCount == uint.MaxValue)
        {
            return;
        }

        var result = DebugWindowsNativeMethods.ResumeThread(threadHandle);
        if (result == uint.MaxValue)
        {
            throw new InvalidOperationException($"ResumeThread failed: {FormatWin32Error()}");
        }
    }

    private static DebugWindowsNativeMethods.CONTEXT GetContext(nint threadHandle)
    {
        var context = DebugWindowsNativeMethods.CONTEXT.Create(DebugWindowsNativeMethods.ContextAll);
        if (!DebugWindowsNativeMethods.GetThreadContext(threadHandle, ref context))
        {
            throw new InvalidOperationException($"GetThreadContext failed: {FormatWin32Error()}");
        }

        return context;
    }

    private static ulong ConfigureDebugControl(ulong current, string kind, int width, bool enabled)
    {
        current &= ~0xFUL;
        current &= ~(0xFUL << 16);

        if (!enabled)
        {
            return current;
        }

        current |= 0x1UL;
        var rw = kind switch
        {
            "memory-write" => 0x1UL,
            "memory-access" => 0x3UL,
            _ => 0x0UL
        };

        var len = width switch
        {
            1 => 0x0UL,
            2 => 0x1UL,
            8 => 0x2UL,
            4 => 0x3UL,
            _ => 0x0UL
        };

        current |= (rw | (len << 2)) << 16;
        return current;
    }

    private static (Instruction Instruction, string InstructionText, string InstructionBytes, string? Error, Register BaseRegister)? DecodeInstruction(nint ripAddress, string? bytesHex)
    {
        if (string.IsNullOrWhiteSpace(bytesHex))
        {
            return null;
        }

        try
        {
            var bytes = Convert.FromHexString(bytesHex.Replace(" ", string.Empty, StringComparison.OrdinalIgnoreCase));
            var decoder = Decoder.Create(64, new ByteArrayCodeReader(bytes));
            decoder.IP = unchecked((ulong)(long)ripAddress);
            var instruction = decoder.Decode();
            var formatter = new IntelFormatter();
            var output = new StringOutput();
            formatter.Format(in instruction, output);
            return (instruction, output.ToString(), Convert.ToHexString(bytes[..instruction.Length]), null, instruction.MemoryBase);
        }
        catch (Exception ex)
        {
            return (default, "<decode-failed>", bytesHex, ex.Message, Register.None);
        }
    }

    private static nint? TryComputeEffectiveAddress(Instruction instruction, DebugWindowsNativeMethods.CONTEXT context)
    {
        var isIpRelative = instruction.MemoryBase is Register.RIP or Register.EIP;
        if (instruction.MemoryBase == Register.None && instruction.MemoryIndex == Register.None && !isIpRelative)
        {
            return null;
        }

        long address;
        if (isIpRelative)
        {
            address = unchecked((long)instruction.IPRelativeMemoryAddress);
        }
        else
        {
            address = 0;
            if (TryGetRegisterValue(context, instruction.MemoryBase) is { } baseValue)
            {
                address += unchecked((long)baseValue);
            }

            if (TryGetRegisterValue(context, instruction.MemoryIndex) is { } indexValue)
            {
                address += unchecked((long)(indexValue * (ulong)instruction.MemoryIndexScale));
            }

            if (instruction.MemoryDisplacement64 != 0)
            {
                address += unchecked((long)instruction.MemoryDisplacement64);
            }
        }

        return unchecked((nint)address);
    }

    private static ulong? TryGetRegisterValue(DebugWindowsNativeMethods.CONTEXT context, Register register)
    {
        return register switch
        {
            Register.RAX or Register.EAX or Register.AX or Register.AL or Register.AH => context.Rax,
            Register.RBX or Register.EBX or Register.BX or Register.BL or Register.BH => context.Rbx,
            Register.RCX or Register.ECX or Register.CX or Register.CL or Register.CH => context.Rcx,
            Register.RDX or Register.EDX or Register.DX or Register.DL or Register.DH => context.Rdx,
            Register.RSI or Register.ESI or Register.SI or Register.SIL => context.Rsi,
            Register.RDI or Register.EDI or Register.DI or Register.DIL => context.Rdi,
            Register.RBP or Register.EBP or Register.BP or Register.BPL => context.Rbp,
            Register.RSP or Register.ESP or Register.SP or Register.SPL => context.Rsp,
            Register.R8 or Register.R8D or Register.R8W or Register.R8L => context.R8,
            Register.R9 or Register.R9D or Register.R9W or Register.R9L => context.R9,
            Register.R10 or Register.R10D or Register.R10W or Register.R10L => context.R10,
            Register.R11 or Register.R11D or Register.R11W or Register.R11L => context.R11,
            Register.R12 or Register.R12D or Register.R12W or Register.R12L => context.R12,
            Register.R13 or Register.R13D or Register.R13W or Register.R13L => context.R13,
            Register.R14 or Register.R14D or Register.R14W or Register.R14L => context.R14,
            Register.R15 or Register.R15D or Register.R15W or Register.R15L => context.R15,
            Register.RIP => context.Rip,
            _ => null
        };
    }

    private static IReadOnlyDictionary<string, string> BuildRegisterSnapshot(DebugWindowsNativeMethods.CONTEXT context) =>
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["RIP"] = FormatAddress(unchecked((nint)(long)context.Rip)),
            ["RSP"] = FormatAddress(unchecked((nint)(long)context.Rsp)),
            ["RBP"] = FormatAddress(unchecked((nint)(long)context.Rbp)),
            ["RAX"] = FormatAddress(unchecked((nint)(long)context.Rax)),
            ["RBX"] = FormatAddress(unchecked((nint)(long)context.Rbx)),
            ["RCX"] = FormatAddress(unchecked((nint)(long)context.Rcx)),
            ["RDX"] = FormatAddress(unchecked((nint)(long)context.Rdx)),
            ["RSI"] = FormatAddress(unchecked((nint)(long)context.Rsi)),
            ["RDI"] = FormatAddress(unchecked((nint)(long)context.Rdi)),
            ["R8"] = FormatAddress(unchecked((nint)(long)context.R8)),
            ["R9"] = FormatAddress(unchecked((nint)(long)context.R9)),
            ["R10"] = FormatAddress(unchecked((nint)(long)context.R10)),
            ["R11"] = FormatAddress(unchecked((nint)(long)context.R11)),
            ["R12"] = FormatAddress(unchecked((nint)(long)context.R12)),
            ["R13"] = FormatAddress(unchecked((nint)(long)context.R13)),
            ["R14"] = FormatAddress(unchecked((nint)(long)context.R14)),
            ["R15"] = FormatAddress(unchecked((nint)(long)context.R15)),
            ["DR0"] = FormatAddress(unchecked((nint)(long)context.Dr0)),
            ["DR6"] = $"0x{context.Dr6:X}",
            ["DR7"] = $"0x{context.Dr7:X}"
        };

    private static string? BuildCallerFingerprint(ProcessMemoryReader reader, IReadOnlyList<ProcessModuleInfo> modules, DebugWindowsNativeMethods.CONTEXT context)
    {
        if (!reader.TryReadBytes(unchecked((nint)(long)context.Rsp), sizeof(ulong), out var bytes, out _))
        {
            return null;
        }

        var returnAddress = unchecked((nint)(long)BitConverter.ToUInt64(bytes, 0));
        var normalized = NormalizeModuleRelativeAddress(returnAddress, modules) ?? FormatAddress(returnAddress);
        return $"{normalized}|rsp={FormatAddress(unchecked((nint)(long)context.Rsp))}";
    }

    private static IReadOnlyList<string>? BuildHitWarnings(string? watchedError, string? decodeError, List<string> warnings)
    {
        var hitWarnings = new List<string>();
        if (!string.IsNullOrWhiteSpace(watchedError))
        {
            hitWarnings.Add(watchedError);
        }

        if (!string.IsNullOrWhiteSpace(decodeError))
        {
            hitWarnings.Add($"Decode warning: {decodeError}");
        }

        if (warnings.Count > 0)
        {
            hitWarnings.AddRange(warnings.TakeLast(Math.Min(3, warnings.Count)));
        }

        return hitWarnings.Count == 0 ? null : hitWarnings.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
    }

    private static DebugMemoryReadResult TryReadWindow(ProcessMemoryReader reader, nint address, int length, string label)
    {
        if (address == 0 || length <= 0)
        {
            return new DebugMemoryReadResult(label, address, length, null, Array.Empty<byte>(), "Window capture skipped.");
        }

        if (!reader.TryReadBytes(address, length, out var bytes, out var error))
        {
            return new DebugMemoryReadResult(label, address, length, null, Array.Empty<byte>(), error);
        }

        return new DebugMemoryReadResult(label, address, bytes.Length, Convert.ToHexString(bytes), bytes, null);
    }

    private static DebugMemoryWindowRecord ToMemoryWindowRecord(DebugMemoryReadResult result, string label, IReadOnlyList<ProcessModuleInfo> modules, DebugWindowsNativeMethods.CONTEXT context) =>
        new(
            Label: label,
            Address: FormatAddress(result.Address),
            Length: result.Length,
            BytesHex: result.BytesHex,
            Classification: ClassifyAddress(result.Address, modules, Array.Empty<ProcessMemoryRegion>(), context),
            Error: result.Error);

    private static string ClassifyAddress(nint address, IReadOnlyList<ProcessModuleInfo> modules, IReadOnlyList<ProcessMemoryRegion> regions, DebugWindowsNativeMethods.CONTEXT context)
    {
        if (modules.Any(module => AddressInModule(address, module)))
        {
            return "module";
        }

        var stackBase = unchecked((long)context.Rsp) - (1024 * 1024);
        var stackTop = unchecked((long)context.Rsp) + (1024 * 1024);
        var value = address.ToInt64();
        if (value >= stackBase && value <= stackTop)
        {
            return "stack";
        }

        if (regions.Any(region => region.ContainsAddress(address)))
        {
            return "heap-like";
        }

        return "unknown";
    }

    private static IReadOnlyList<DebugInstructionFingerprintRecord> BuildInstructionFingerprints(string traceId, IReadOnlyList<DebugTraceHitRecord> hits) =>
        hits
            .Where(static hit => !string.IsNullOrWhiteSpace(hit.ModuleRelativeRip))
            .GroupBy(hit => $"{hit.ModuleRelativeRip}|{hit.InstructionText}|{hit.InstructionBytes}", StringComparer.OrdinalIgnoreCase)
            .Select(group =>
            {
                var first = group.First();
                var moduleRelativeRip = first.ModuleRelativeRip!;
                var splitIndex = moduleRelativeRip.IndexOf('+');
                var moduleName = splitIndex > 0 ? moduleRelativeRip[..splitIndex] : moduleRelativeRip;
                var moduleOffset = splitIndex > 0 ? moduleRelativeRip[(splitIndex + 1)..] : "n/a";
                return new DebugInstructionFingerprintRecord(
                    TraceId: traceId,
                    ModuleName: moduleName,
                    ModuleOffset: moduleOffset,
                    ModuleRelativeRip: moduleRelativeRip,
                    InstructionText: first.InstructionText,
                    InstructionBytes: first.InstructionBytes,
                    Pattern: first.InstructionBytes,
                    HitCount: group.Count());
            })
            .OrderByDescending(static record => record.HitCount)
            .ThenBy(static record => record.ModuleRelativeRip, StringComparer.OrdinalIgnoreCase)
            .ToArray();

    private static IReadOnlyList<DebugHitClusterRecord> BuildHitClusters(string traceId, IReadOnlyList<DebugTraceHitRecord> hits) =>
        hits
            .GroupBy(static hit => $"{hit.ModuleRelativeRip ?? "<rip>"}|{hit.EffectiveAddress ?? "<eff>"}|{hit.CallerFingerprint ?? "<caller>"}")
            .Select(group => new DebugHitClusterRecord(
                TraceId: traceId,
                ClusterKey: group.Key,
                ModuleRelativeRip: group.First().ModuleRelativeRip,
                EffectiveAddress: group.First().EffectiveAddress,
                HitCount: group.Count(),
                ThreadIds: group.Select(static hit => hit.ThreadId).Distinct().OrderBy(static id => id).ToArray(),
                HitIndices: group.Select(static hit => hit.HitIndex).OrderBy(static index => index).ToArray(),
                CallerFingerprint: group.First().CallerFingerprint))
            .OrderByDescending(static cluster => cluster.HitCount)
            .ToArray();

    private static IReadOnlyList<DebugFollowUpSuggestionRecord> BuildFollowUpSuggestions(string traceId, IReadOnlyList<DebugTraceHitRecord> hits)
    {
        var suggestions = new List<DebugFollowUpSuggestionRecord>();
        foreach (var hit in hits)
        {
            if (!string.IsNullOrWhiteSpace(hit.EffectiveAddress))
            {
                suggestions.Add(new DebugFollowUpSuggestionRecord(
                    TraceId: traceId,
                    Kind: "watch-effective-address",
                    Address: hit.EffectiveAddress,
                    Length: hit.WatchedWidth ?? 16,
                    Reason: "Observed as a live effective address during a breakpoint hit.",
                    RelatedOffset: null,
                    Confidence: "high"));
            }

            if (hit.PointerClassifications is not null)
            {
                foreach (var pointer in hit.PointerClassifications.Where(static pair => pair.Key.StartsWith("base:", StringComparison.OrdinalIgnoreCase)))
                {
                    if (hit.Registers is not null && hit.Registers.TryGetValue(pointer.Key["base:".Length..].ToUpperInvariant(), out var registerValue))
                    {
                        suggestions.Add(new DebugFollowUpSuggestionRecord(
                            TraceId: traceId,
                            Kind: "watch-object-base",
                            Address: registerValue,
                            Length: 64,
                            Reason: $"Observed via {pointer.Key}.",
                            RelatedOffset: hit.EffectiveAddress,
                            Confidence: pointer.Value));
                    }
                }
            }
        }

        return suggestions
            .GroupBy(static suggestion => $"{suggestion.Kind}|{suggestion.Address}|{suggestion.Length}|{suggestion.RelatedOffset}")
            .Select(static group => group.First())
            .Take(32)
            .ToArray();
    }

    private static bool TryCleanupFromPriorFailure(int processId, List<string> warnings)
    {
        var ledgerFile = ResolveFailureLedgerFile(Directory.GetCurrentDirectory());
        if (!File.Exists(ledgerFile))
        {
            return false;
        }

        try
        {
            var lastEntry = File.ReadLines(ledgerFile)
                .Where(static line => !string.IsNullOrWhiteSpace(line))
                .Select(line => JsonSerializer.Deserialize<DebugTraceFailureLedgerRecord>(line, NdjsonOptions))
                .Where(entry => entry is not null && entry.ProcessId == processId)
                .LastOrDefault();

            if (lastEntry is null || !lastEntry.AbnormalExit)
            {
                return false;
            }

            warnings.Add($"Detected a prior abnormal debug worker exit for PID {processId}; performing a pre-attach breakpoint cleanup sweep.");
            foreach (var threadId in EnumerateThreadIds(processId))
            {
                ClearThreadBreakpoint(threadId, warnings);
            }

            return true;
        }
        catch (Exception ex)
        {
            warnings.Add($"Unable to inspect the prior debug failure ledger: {ex.Message}");
            return false;
        }
    }

    private static void DrainMarkerInputFile(
        StreamWriter markerWriter,
        string? markerInputFile,
        ref int processedLineCount,
        string? label,
        int eventIndex,
        int hitIndex,
        Stopwatch stopwatch,
        string traceId)
    {
        if (string.IsNullOrWhiteSpace(markerInputFile))
        {
            return;
        }

        var fullPath = Path.GetFullPath(markerInputFile);
        if (!File.Exists(fullPath))
        {
            return;
        }

        string[] lines;
        try
        {
            lines = File.ReadAllLines(fullPath);
        }
        catch
        {
            return;
        }

        if (processedLineCount >= lines.Length)
        {
            return;
        }

        for (var index = processedLineCount; index < lines.Length; index++)
        {
            if (string.IsNullOrWhiteSpace(lines[index]))
            {
                continue;
            }

            try
            {
                var marker = JsonSerializer.Deserialize<DebugExternalMarkerInputRecord>(lines[index], NdjsonOptions);
                if (marker is null)
                {
                    continue;
                }

                RecordMarker(
                    markerWriter,
                    traceId,
                    string.IsNullOrWhiteSpace(marker.Kind) ? "external-marker" : marker.Kind,
                    DateTimeOffset.UtcNow,
                    stopwatch.ElapsedMilliseconds,
                    eventIndex,
                    hitIndex == 0 ? null : hitIndex,
                    label ?? marker.Label,
                    marker.Message,
                    string.IsNullOrWhiteSpace(marker.Source) ? "external" : marker.Source,
                    marker.Metadata);
            }
            catch
            {
                // Ignore malformed external marker lines to avoid destabilizing the worker.
            }
        }

        processedLineCount = lines.Length;
    }

    private static void RecordEvent(
        StreamWriter writer,
        string traceId,
        long elapsedMilliseconds,
        ref int eventIndex,
        string phase,
        string eventKind,
        int? threadId,
        uint? debugEventCode,
        uint? exceptionCode,
        bool? firstChance,
        string? breakpointId,
        int? hitIndex,
        string? moduleRelativeRip,
        string? rawRip,
        string? moduleName,
        string? moduleOffset,
        string? statusCode,
        string? message)
    {
        var record = new DebugTraceEventRecord(
            EventIndex: eventIndex,
            TraceId: traceId,
            RecordedAtUtc: DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ElapsedMilliseconds: elapsedMilliseconds,
            Phase: phase,
            EventKind: eventKind,
            ThreadId: threadId,
            DebugEventCode: debugEventCode,
            ExceptionCode: exceptionCode,
            FirstChance: firstChance,
            BreakpointId: breakpointId,
            HitIndex: hitIndex,
            ModuleRelativeRip: moduleRelativeRip,
            RawRip: rawRip,
            ModuleName: moduleName,
            ModuleOffset: moduleOffset,
            StatusCode: statusCode,
            Message: message);

        WriteNdjson(writer, record);
    }

    private static void RecordMarker(
        StreamWriter writer,
        string traceId,
        string kind,
        DateTimeOffset timestamp,
        long elapsedMilliseconds,
        int? eventIndex,
        int? hitIndex,
        string? label,
        string? message,
        string? source,
        IReadOnlyDictionary<string, string>? metadata)
    {
        WriteNdjson(
            writer,
            new DebugTraceMarkerRecord(
                Kind: kind,
                RecordedAtUtc: timestamp.ToString("O", CultureInfo.InvariantCulture),
                ElapsedMilliseconds: elapsedMilliseconds,
                EventIndex: eventIndex,
                HitIndex: hitIndex,
                Label: label,
                Message: message,
                Source: source,
                Metadata: metadata));
    }

    private static void WriteNdjson<T>(StreamWriter writer, T record)
    {
        writer.WriteLine(JsonSerializer.Serialize(record, NdjsonOptions));
        writer.Flush();
    }

    private static void WriteJsonArray<T>(string filePath, IReadOnlyCollection<T> values)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(filePath)!);
        File.WriteAllText(filePath, JsonSerializer.Serialize(values, PrettyJsonOptions));
    }

    private static void PromoteTempFile(string tempFile, string finalFile)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(finalFile)!);
        if (File.Exists(finalFile))
        {
            File.Delete(finalFile);
        }

        File.Move(tempFile, finalFile);
    }

    private static IReadOnlyList<string> BuildMissingFiles(params string[] paths) =>
        paths
            .Where(static path => !string.IsNullOrWhiteSpace(path))
            .Where(static path => !File.Exists(path))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

    private static void AppendFailureLedger(string filePath, DebugTraceFailureLedgerRecord record)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(filePath)!);
        File.AppendAllText(filePath, JsonSerializer.Serialize(record, NdjsonOptions) + Environment.NewLine);
    }

    private static string ResolveFailureLedgerFile(string startDirectory)
    {
        var current = new DirectoryInfo(Path.GetFullPath(startDirectory));
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return Path.Combine(current.FullName, "scripts", "captures", "debug-traces", "native-debug-failure-ledger.ndjson");
            }

            current = current.Parent;
        }

        return Path.Combine(Path.GetFullPath(startDirectory), "native-debug-failure-ledger.ndjson");
    }

    private static bool AddressInModule(nint address, ProcessModuleInfo module)
    {
        var value = address.ToInt64();
        return value >= module.BaseAddress && value < module.BaseAddress + module.ModuleMemorySize;
    }

    private static string? NormalizeModuleRelativeAddress(nint address, IReadOnlyList<ProcessModuleInfo> modules)
    {
        var module = modules.FirstOrDefault(module => AddressInModule(address, module));
        if (module is null)
        {
            return null;
        }

        var offset = address.ToInt64() - module.BaseAddress;
        return $"{module.ModuleName}+0x{offset:X}";
    }

    private static nint ParseAddress(string value)
    {
        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            return unchecked((nint)long.Parse(value[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture));
        }

        return unchecked((nint)long.Parse(value, NumberStyles.Integer, CultureInfo.InvariantCulture));
    }

    private static string FormatAddress(nint address) => $"0x{address.ToInt64():X}";

    private static string ExtractModuleName(string? moduleRelativeRip)
    {
        if (string.IsNullOrWhiteSpace(moduleRelativeRip))
        {
            return null!;
        }

        var splitIndex = moduleRelativeRip.IndexOf('+');
        return splitIndex > 0 ? moduleRelativeRip[..splitIndex] : moduleRelativeRip;
    }

    private static string ExtractModuleOffset(string? moduleRelativeRip)
    {
        if (string.IsNullOrWhiteSpace(moduleRelativeRip))
        {
            return null!;
        }

        var splitIndex = moduleRelativeRip.IndexOf('+');
        return splitIndex > 0 ? moduleRelativeRip[(splitIndex + 1)..] : moduleRelativeRip;
    }

    private static string SafeGetMainModuleName(Process process)
    {
        try
        {
            return process.MainModule?.ModuleName ?? process.ProcessName;
        }
        catch
        {
            return process.ProcessName;
        }
    }

    private static string? SafeGetMainWindowTitle(Process process)
    {
        try
        {
            return string.IsNullOrWhiteSpace(process.MainWindowTitle) ? null : process.MainWindowTitle;
        }
        catch
        {
            return null;
        }
    }

    private static string? SafeGetProcessStartTimeUtc(Process process)
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

    private static bool IsElevated()
    {
        try
        {
            using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
            var principal = new System.Security.Principal.WindowsPrincipal(identity);
            return principal.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
        }
        catch
        {
            return false;
        }
    }

    private static void AddCapabilityWarnings(DebugTraceCapabilities capabilities, List<string> warnings)
    {
        if (!capabilities.RegisterCapture) warnings.Add("Register capture disabled for this trace request.");
        if (!capabilities.StackCapture) warnings.Add("Stack capture disabled for this trace request.");
        if (!capabilities.MemoryWindows) warnings.Add("Memory window capture disabled for this trace request.");
        if (!capabilities.InstructionDecode) warnings.Add("Instruction decode disabled for this trace request.");
        if (!capabilities.InstructionFingerprint) warnings.Add("Instruction fingerprint analyzer disabled for this trace request.");
        if (!capabilities.HitClustering) warnings.Add("Hit clustering analyzer disabled for this trace request.");
        if (!capabilities.FollowUpSuggestions) warnings.Add("Follow-up suggestion analyzer disabled for this trace request.");
    }

    private static void SafeCloseHandle(nint handle)
    {
        if (handle != 0)
        {
            DebugWindowsNativeMethods.CloseHandle(handle);
        }
    }

    private static string FormatWin32Error() =>
        FormatWin32Error(Marshal.GetLastWin32Error());

    private static string FormatWin32Error(int errorCode) =>
        $"{new Win32Exception(errorCode).Message} (Win32: {errorCode})";

    private readonly record struct ResolvedBreakpoint(
        string Kind,
        nint Address,
        string AddressHex,
        string? ModuleName,
        string? ModuleOffsetHex,
        int? Width,
        string TargetArchitecture);

    private readonly record struct DebugMemoryReadResult(
        string Label,
        nint Address,
        int Length,
        string? BytesHex,
        byte[] Bytes,
        string? Error);

    private sealed record DebugTraceFailureLedgerRecord(
        string RecordedAtUtc,
        string TraceId,
        int ProcessId,
        string ProcessName,
        string Mode,
        string OutputDirectory,
        string Status,
        bool AbnormalExit,
        string? FailureMessage);
}






