using System.Globalization;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Cli;

public static class ReaderOptionsParser
{
    private const string UsageText = """
Usage:
  RiftReader.Reader --pid <processId>
  RiftReader.Reader --process-name <name>
  RiftReader.Reader --process-name <name> --list-modules [--json]
  RiftReader.Reader --process-name <name> --scan-module-pattern "<aa bb ?? cc>" [--scan-module-name <module>] [--scan-context <bytes>] [--json]
  RiftReader.Reader --pid <processId> --address <hexOrDecimal> --length <byteCount>
  RiftReader.Reader --process-name <name> --cheatengine-probe [--cheatengine-probe-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --rank-owner-components [--owner-components-file <path>] [--json]
  RiftReader.Reader --rank-stat-hubs [--owner-components-file <path>] [--json]
  RiftReader.Reader --read-player-orientation [--owner-components-file <path>] [--json]
  RiftReader.Reader --process-name <name> --capture-readerbridge-best-family [--capture-label <text>] [--capture-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --read-player-current [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --find-player-orientation-candidate [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --read-player-coord-anchor [--player-coord-trace-file <path>] [--json]
  RiftReader.Reader --process-name <name> --read-target-current [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --post-update-triage [--player-coord-trace-file <path>] [--session-watchset-file <path>] [--recovery-bundle-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --sample-triage-watch-regions [--recovery-bundle-file <path>] [--max-hits <count>] [--json]
  RiftReader.Reader --session-summary --session-directory <path> [--json]
  RiftReader.Reader --process-name <name> --record-session --session-watchset-file <path> --session-output-directory <path> [--session-marker-input-file <path>] [--session-sample-count <count>] [--session-interval-ms <ms>] [--session-label <text>] [--json]
  RiftReader.Reader --process-name <name> --scan-string <text> [--scan-encoding ascii|utf16|both] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-int32 <value> [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-float <value> [--scan-tolerance <epsilon>] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-double <value> [--scan-tolerance <epsilon>] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-player-name [--scan-encoding ascii|utf16|both] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-player-coords [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-player-signature [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-identity [--scan-encoding ascii|utf16|both] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-pointer <hexOrDecimalAddress> [--pointer-width 4|8] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --addon-snapshot [--addon-snapshot-file <path>] [--json]
  RiftReader.Reader --readerbridge-snapshot [--readerbridge-snapshot-file <path>] [--json]

Notes:
  - Use this reader only against Rift client processes you explicitly intend to inspect.
  - Provide either --pid or --process-name, but not both.
  - Provide --address and --length together when you want a raw memory read.
  - Use --list-modules to inspect the module list for the attached process.
  - Use --scan-module-pattern to run a signature/AOB scan against a specific module or the main module by default.
  - Use --cheatengine-probe to generate a Cheat Engine Lua helper script from the latest ReaderBridge export and the current best grouped player signature families.
  - Use --rank-owner-components to score the current owner-component artifact against the latest ReaderBridge snapshot and rank likely stat-bearing components.
  - Use --rank-stat-hubs to walk the identity-component graph and identify shared memory hubs that store player stats.
  - Use --read-player-orientation to derive candidate yaw/pitch values from the selected source component's orientation vectors in the latest owner-component artifact.
  - Use --capture-readerbridge-best-family to read the current live values for the top grouped player-signature family and optionally append them to a TSV file.
  - Use --read-player-current to read the current best player-family sample directly from memory and compare it against the latest ReaderBridge export.
  - Use --find-player-orientation-candidate to do a single-process read-only search for the live actor/source object near current player coordinate hits.
  - Use --read-target-current to read the current target snapshot from memory and compare it against the latest ReaderBridge export.
  - Use --read-player-coord-anchor to validate the latest coord-trace artifact against the live process and derive a first code-path-backed coord anchor summary.
  - Use --post-update-triage to run a single-attach recovery pass that validates surviving anchors, clusters current structure families, scores live yaw candidates against saved session evidence, and emits a recovery bundle.
  - --post-update-triage writes the bundle to .\scripts\captures\post-update-triage-bundle.json by default; use --recovery-bundle-file to override the path.
  - Use --sample-triage-watch-regions to read only the suggested watch regions from the latest triage bundle so the top stable yaw candidates can be sampled without rerunning broader discovery.
  - Use --session-summary to inspect a recorded offline session package without attaching to a live process.
  - Use --record-session to sample named memory regions from a watchset into an owned session folder for offline decoding work.
  - Use --session-marker-input-file with --record-session when you want manual or script-driven markers appended during the live recording window.
  - Use --scan-string to search process memory for a text value.
  - Use --scan-int32, --scan-float, or --scan-double to search process memory for numeric values.
  - Use --scan-tolerance with floating-point scans when the stored value may differ slightly from the printed decimal.
  - Use --scan-readerbridge-player-name to load the latest ReaderBridge export and scan the process for the current player name.
  - Use --scan-readerbridge-player-coords to load the latest ReaderBridge export and scan for an exact contiguous float triplet of the current player coordinates.
  - Use --scan-readerbridge-player-signature to rank coordinate hits by nearby exported player fields such as health, level, and location text.
  - Use --scan-readerbridge-identity to derive a likely character identity string such as Name@Shard from the latest ReaderBridge export path and scan for it.
  - Use --scan-pointer to search process memory for references to a target address.
  - Use --scan-context to capture bytes around each hit for quick triage.
  - Use --addon-snapshot to normalize the latest RiftReaderValidator saved snapshot for comparison work.
  - Use --readerbridge-snapshot to normalize the latest ReaderBridge export snapshot for richer comparison work.
  - Use --json to print machine-readable output.

Examples:
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --list-modules
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-module-pattern "48 8B ?? ?? ?? ?? ?? 48 85 C0" --scan-module-name rift_x64.exe --scan-context 32
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234 --address 0x7FF600001000 --length 64
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --rank-owner-components --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --capture-readerbridge-best-family --capture-label baseline --capture-file .\scripts\captures\player-signature-captures.tsv
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --find-player-orientation-candidate --max-hits 8 --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --post-update-triage --recovery-bundle-file .\scripts\captures\post-update-triage-bundle.json --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --sample-triage-watch-regions --max-hits 6 --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --session-summary --session-directory .\scripts\sessions\20260409-baseline --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session --session-watchset-file .\scripts\sessions\watchset.json --session-output-directory .\scripts\sessions\20260409-baseline --session-marker-input-file .\scripts\sessions\baseline.markers.ndjson --session-sample-count 20 --session-interval-ms 500 --session-label baseline --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-string Atank --scan-encoding both --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-int32 17027 --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-float 7389.71 --scan-tolerance 0.01 --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-name --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-coords --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-signature --scan-context 96 --max-hits 12
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-identity --scan-encoding ascii --scan-context 32 --max-hits 8
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-pointer 0x2039DD70 --pointer-width 8 --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --addon-snapshot --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json
""";

    public static ReaderOptionsParseResult Parse(string[] args)
    {
        if (args.Length == 0 || args.Any(IsHelpSwitch))
        {
            return ReaderOptionsParseResult.DisplayUsage(UsageText);
        }

        int? processId = null;
        string? processName = null;
        nint? address = null;
        int? length = null;
        var listModules = false;
        string? scanModuleName = null;
        string? scanModulePattern = null;
        var writeCheatEngineProbe = false;
        string? cheatEngineProbeFile = null;
        var rankOwnerComponents = false;
        string? ownerComponentsFile = null;
        var readPlayerOrientation = false;
        var captureReaderBridgeBestFamily = false;
        var readPlayerCurrent = false;
        var findPlayerOrientationCandidate = false;
        var readPlayerCoordAnchor = false;
        var postUpdateTriage = false;
        var sampleTriageWatchRegions = false;
        var recordSession = false;
        var sessionSummary = false;
        string? sessionDirectory = null;
        string? sessionWatchsetFile = null;
        string? sessionOutputDirectory = null;
        string? sessionMarkerInputFile = null;
        var sessionSampleCount = 1;
        var sessionIntervalMilliseconds = 500;
        string? sessionLabel = null;
        string? playerCoordTraceFile = null;
        string? recoveryBundleFile = null;
        string? captureLabel = null;
        string? captureFile = null;
        string? scanString = null;
        nint? scanPointer = null;
        int? scanInt32 = null;
        float? scanFloat = null;
        double? scanDouble = null;
        var scanTolerance = 0d;
        var pointerWidth = IntPtr.Size;
        var scanEncoding = StringScanEncoding.Both;
        var scanContextBytes = 0;
        var maxHits = 16;
        var scanReaderBridgePlayerName = false;
        var scanReaderBridgePlayerCoords = false;
        var scanReaderBridgePlayerSignature = false;
        var scanReaderBridgeIdentity = false;
        var readAddonSnapshot = false;
        string? addonSnapshotFile = null;
        var readReaderBridgeSnapshot = false;
        string? readerBridgeSnapshotFile = null;
        var rankStatHubs = false;
        var cheatEngineStatHubs = false;
        var readTargetCurrent = false;
        var jsonOutput = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];

            switch (arg)
            {
                case "--pid":
                case "-p":
                    if (!TryReadNext(args, ref index, out var pidValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --pid.", UsageText);
                    }

                    if (!int.TryParse(pidValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedPid) || parsedPid <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid process id '{pidValue}'.", UsageText);
                    }

                    processId = parsedPid;
                    break;

                case "--process-name":
                case "-n":
                    if (!TryReadNext(args, ref index, out var processNameValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --process-name.", UsageText);
                    }

                    processName = processNameValue;
                    break;

                case "--address":
                case "-a":
                    if (!TryReadNext(args, ref index, out var addressValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --address.", UsageText);
                    }

                    if (!TryParseAddress(addressValue, out var parsedAddress))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid address '{addressValue}'.", UsageText);
                    }

                    address = parsedAddress;
                    break;

                case "--list-modules":
                    listModules = true;
                    break;

                case "--scan-module-pattern":
                    if (!TryReadNext(args, ref index, out var scanModulePatternValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-module-pattern.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(scanModulePatternValue))
                    {
                        return ReaderOptionsParseResult.Fail("Module scan pattern must not be blank.", UsageText);
                    }

                    scanModulePattern = scanModulePatternValue;
                    break;

                case "--scan-module-name":
                    if (!TryReadNext(args, ref index, out var scanModuleNameValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-module-name.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(scanModuleNameValue))
                    {
                        return ReaderOptionsParseResult.Fail("Module name must not be blank.", UsageText);
                    }

                    scanModuleName = scanModuleNameValue;
                    break;

                case "--length":
                case "-l":
                    if (!TryReadNext(args, ref index, out var lengthValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --length.", UsageText);
                    }

                    if (!int.TryParse(lengthValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedLength) || parsedLength <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid length '{lengthValue}'.", UsageText);
                    }

                    length = parsedLength;
                    break;

                case "--cheatengine-probe":
                    writeCheatEngineProbe = true;
                    break;

                case "--record-session":
                    recordSession = true;
                    break;

                case "--session-watchset-file":
                    if (!TryReadNext(args, ref index, out var sessionWatchsetFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-watchset-file.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(sessionWatchsetFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Session watchset file must not be blank.", UsageText);
                    }

                    sessionWatchsetFile = sessionWatchsetFileValue;
                    break;

                case "--session-output-directory":
                    if (!TryReadNext(args, ref index, out var sessionOutputDirectoryValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-output-directory.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(sessionOutputDirectoryValue))
                    {
                        return ReaderOptionsParseResult.Fail("Session output directory must not be blank.", UsageText);
                    }

                    sessionOutputDirectory = sessionOutputDirectoryValue;
                    break;

                case "--session-marker-input-file":
                    if (!TryReadNext(args, ref index, out var sessionMarkerInputFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-marker-input-file.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(sessionMarkerInputFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Session marker input file must not be blank.", UsageText);
                    }

                    sessionMarkerInputFile = sessionMarkerInputFileValue;
                    break;

                case "--session-sample-count":
                    if (!TryReadNext(args, ref index, out var sessionSampleCountValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-sample-count.", UsageText);
                    }

                    if (!int.TryParse(sessionSampleCountValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out sessionSampleCount) || sessionSampleCount <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid session sample count '{sessionSampleCountValue}'.", UsageText);
                    }

                    break;

                case "--session-interval-ms":
                    if (!TryReadNext(args, ref index, out var sessionIntervalMillisecondsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-interval-ms.", UsageText);
                    }

                    if (!int.TryParse(sessionIntervalMillisecondsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out sessionIntervalMilliseconds) || sessionIntervalMilliseconds < 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid session interval '{sessionIntervalMillisecondsValue}'.", UsageText);
                    }

                    break;

                case "--session-label":
                    if (!TryReadNext(args, ref index, out var sessionLabelValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-label.", UsageText);
                    }

                    sessionLabel = string.IsNullOrWhiteSpace(sessionLabelValue)
                        ? null
                        : sessionLabelValue.Trim();
                    break;

                case "--cheatengine-probe-file":
                    if (!TryReadNext(args, ref index, out var cheatEngineProbeFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --cheatengine-probe-file.", UsageText);
                    }

                    cheatEngineProbeFile = cheatEngineProbeFileValue;
                    writeCheatEngineProbe = true;
                    break;

                case "--rank-owner-components":
                    rankOwnerComponents = true;
                    break;
                case "--rank-stat-hubs":
                    rankStatHubs = true;
                    break;
                case "--cheatengine-stat-hubs":
                    cheatEngineStatHubs = true;
                    break;

                case "--read-player-orientation":
                    readPlayerOrientation = true;
                    break;

                case "--owner-components-file":
                    if (!TryReadNext(args, ref index, out var ownerComponentsFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --owner-components-file.", UsageText);
                    }

                    ownerComponentsFile = ownerComponentsFileValue;
                    break;

                case "--capture-readerbridge-best-family":
                    captureReaderBridgeBestFamily = true;
                    break;

                case "--read-player-current":
                    readPlayerCurrent = true;
                    break;

                case "--find-player-orientation-candidate":
                    findPlayerOrientationCandidate = true;
                    break;

                case "--read-player-coord-anchor":
                    readPlayerCoordAnchor = true;
                    break;

                case "--read-target-current":
                    readTargetCurrent = true;
                    break;

                case "--post-update-triage":
                    postUpdateTriage = true;
                    break;

                case "--sample-triage-watch-regions":
                    sampleTriageWatchRegions = true;
                    break;

                case "--session-summary":
                    sessionSummary = true;
                    break;

                case "--session-directory":
                    if (!TryReadNext(args, ref index, out var sessionDirectoryValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --session-directory.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(sessionDirectoryValue))
                    {
                        return ReaderOptionsParseResult.Fail("Session directory must not be blank.", UsageText);
                    }

                    sessionDirectory = sessionDirectoryValue;
                    break;

                case "--player-coord-trace-file":
                    if (!TryReadNext(args, ref index, out var playerCoordTraceFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --player-coord-trace-file.", UsageText);
                    }

                    playerCoordTraceFile = playerCoordTraceFileValue;
                    if (!postUpdateTriage)
                    {
                        readPlayerCoordAnchor = true;
                    }
                    break;

                case "--recovery-bundle-file":
                    if (!TryReadNext(args, ref index, out var recoveryBundleFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --recovery-bundle-file.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(recoveryBundleFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Recovery bundle file must not be blank.", UsageText);
                    }

                    recoveryBundleFile = recoveryBundleFileValue;
                    break;

                case "--capture-label":
                    if (!TryReadNext(args, ref index, out var captureLabelValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --capture-label.", UsageText);
                    }

                    captureLabel = captureLabelValue;
                    break;

                case "--capture-file":
                    if (!TryReadNext(args, ref index, out var captureFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --capture-file.", UsageText);
                    }

                    captureFile = captureFileValue;
                    break;

                case "--scan-string":
                    if (!TryReadNext(args, ref index, out var scanStringValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-string.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(scanStringValue))
                    {
                        return ReaderOptionsParseResult.Fail("Scan text must not be blank.", UsageText);
                    }

                    scanString = scanStringValue;
                    break;

                case "--scan-pointer":
                    if (!TryReadNext(args, ref index, out var scanPointerValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-pointer.", UsageText);
                    }

                    if (!TryParseAddress(scanPointerValue, out var parsedPointer))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid pointer address '{scanPointerValue}'.", UsageText);
                    }

                    scanPointer = parsedPointer;
                    break;

                case "--scan-int32":
                    if (!TryReadNext(args, ref index, out var scanInt32Value))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-int32.", UsageText);
                    }

                    if (!int.TryParse(scanInt32Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedInt32))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid int32 value '{scanInt32Value}'.", UsageText);
                    }

                    scanInt32 = parsedInt32;
                    break;

                case "--scan-float":
                    if (!TryReadNext(args, ref index, out var scanFloatValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-float.", UsageText);
                    }

                    if (!float.TryParse(scanFloatValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedFloat) || !float.IsFinite(parsedFloat))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid float value '{scanFloatValue}'.", UsageText);
                    }

                    scanFloat = parsedFloat;
                    break;

                case "--scan-double":
                    if (!TryReadNext(args, ref index, out var scanDoubleValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-double.", UsageText);
                    }

                    if (!double.TryParse(scanDoubleValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedDouble) || !double.IsFinite(parsedDouble))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid double value '{scanDoubleValue}'.", UsageText);
                    }

                    scanDouble = parsedDouble;
                    break;

                case "--scan-tolerance":
                    if (!TryReadNext(args, ref index, out var scanToleranceValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-tolerance.", UsageText);
                    }

                    if (!double.TryParse(scanToleranceValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out scanTolerance) || scanTolerance < 0 || !double.IsFinite(scanTolerance))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid scan-tolerance value '{scanToleranceValue}'.", UsageText);
                    }

                    break;

                case "--scan-encoding":
                    if (!TryReadNext(args, ref index, out var scanEncodingValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-encoding.", UsageText);
                    }

                    if (!TryParseScanEncoding(scanEncodingValue, out scanEncoding))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid scan encoding '{scanEncodingValue}'. Use ascii, utf16, or both.", UsageText);
                    }

                    break;

                case "--pointer-width":
                    if (!TryReadNext(args, ref index, out var pointerWidthValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --pointer-width.", UsageText);
                    }

                    if (!int.TryParse(pointerWidthValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out pointerWidth) || (pointerWidth != 4 && pointerWidth != 8))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid pointer-width value '{pointerWidthValue}'. Use 4 or 8.", UsageText);
                    }

                    break;

                case "--max-hits":
                    if (!TryReadNext(args, ref index, out var maxHitsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --max-hits.", UsageText);
                    }

                    if (!int.TryParse(maxHitsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out maxHits) || maxHits <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid max-hits value '{maxHitsValue}'.", UsageText);
                    }

                    break;

                case "--scan-context":
                    if (!TryReadNext(args, ref index, out var scanContextValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --scan-context.", UsageText);
                    }

                    if (!int.TryParse(scanContextValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out scanContextBytes) || scanContextBytes < 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid scan-context value '{scanContextValue}'.", UsageText);
                    }

                    break;

                case "--scan-readerbridge-player-name":
                    scanReaderBridgePlayerName = true;
                    break;

                case "--scan-readerbridge-player-coords":
                    scanReaderBridgePlayerCoords = true;
                    break;

                case "--scan-readerbridge-player-signature":
                    scanReaderBridgePlayerSignature = true;
                    break;

                case "--scan-readerbridge-identity":
                    scanReaderBridgeIdentity = true;
                    break;

                case "--addon-snapshot":
                    readAddonSnapshot = true;
                    break;

                case "--addon-snapshot-file":
                    if (!TryReadNext(args, ref index, out var addonSnapshotFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --addon-snapshot-file.", UsageText);
                    }

                    addonSnapshotFile = addonSnapshotFileValue;
                    readAddonSnapshot = true;
                    break;

                case "--readerbridge-snapshot":
                    readReaderBridgeSnapshot = true;
                    break;

                case "--readerbridge-snapshot-file":
                    if (!TryReadNext(args, ref index, out var readerBridgeSnapshotFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --readerbridge-snapshot-file.", UsageText);
                    }

                    readerBridgeSnapshotFile = readerBridgeSnapshotFileValue;
                    readReaderBridgeSnapshot = true;
                    break;

                case "--json":
                    jsonOutput = true;
                    break;

                default:
                    return ReaderOptionsParseResult.Fail($"Unknown argument '{arg}'.", UsageText);
            }
        }

        var scanRequested =
            !string.IsNullOrWhiteSpace(scanString) ||
            !string.IsNullOrWhiteSpace(scanModulePattern) ||
            scanReaderBridgePlayerName ||
            scanReaderBridgePlayerCoords ||
            scanReaderBridgePlayerSignature ||
            scanReaderBridgeIdentity ||
            scanPointer.HasValue ||
            scanInt32.HasValue ||
            scanFloat.HasValue ||
            scanDouble.HasValue;

        var scanTargetCount = 0;
        if (!string.IsNullOrWhiteSpace(scanString)) scanTargetCount++;
        if (scanReaderBridgePlayerName) scanTargetCount++;
        if (scanReaderBridgePlayerCoords) scanTargetCount++;
        if (scanReaderBridgePlayerSignature) scanTargetCount++;
        if (scanReaderBridgeIdentity) scanTargetCount++;
        if (scanPointer.HasValue) scanTargetCount++;
        if (scanInt32.HasValue) scanTargetCount++;
        if (scanFloat.HasValue) scanTargetCount++;
        if (scanDouble.HasValue) scanTargetCount++;

        if (scanTargetCount > 1)
        {
            return ReaderOptionsParseResult.Fail("Choose only one scan target: --scan-string, --scan-int32, --scan-float, --scan-double, --scan-readerbridge-player-name, --scan-readerbridge-player-coords, --scan-readerbridge-player-signature, --scan-readerbridge-identity, or --scan-pointer.", UsageText);
        }

        if (scanTolerance > 0d && !scanFloat.HasValue && !scanDouble.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--scan-tolerance can only be used with --scan-float or --scan-double.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with scan switches.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && writeCheatEngineProbe)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --cheatengine-probe.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --capture-readerbridge-best-family.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-player-current.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-target-current.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --post-update-triage.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && sampleTriageWatchRegions)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --sample-triage-watch-regions.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && rankOwnerComponents)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --rank-owner-components.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readPlayerOrientation)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-player-orientation.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && rankStatHubs)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --rank-stat-hubs.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && recordSession)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --record-session.", UsageText);
        }

        if (ownerComponentsFile is not null && !rankOwnerComponents && !readPlayerOrientation && !rankStatHubs)
        {
            return ReaderOptionsParseResult.Fail("--owner-components-file can only be used with --rank-owner-components, --rank-stat-hubs, or --read-player-orientation.", UsageText);
        }

        if (sessionSummary)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--session-summary cannot be combined with process attach or memory-read switches.", UsageText);
            }

            if (listModules || scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || readPlayerCoordAnchor || postUpdateTriage || sampleTriageWatchRegions || readTargetCurrent || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs || readPlayerOrientation)
            {
                return ReaderOptionsParseResult.Fail("--session-summary cannot be combined with scan, snapshot, live reader, or record-session modes.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: null,
                    ProcessName: null,
                    Address: null,
                    Length: null,
                    ListModules: false,
                    ScanModuleName: null,
                    ScanModulePattern: null,
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    RankOwnerComponents: false,
                    OwnerComponentsFile: null,
                    RankStatHubs: false,
                    CheatEngineStatHubs: false,
                    ReadPlayerOrientation: false,
                    CaptureReaderBridgeBestFamily: false,
                    ReadPlayerCurrent: false,
                    FindPlayerOrientationCandidate: false,
                    ReadPlayerCoordAnchor: false,
                    ReadTargetCurrent: false,
                    SessionSummary: true,
                    SessionDirectory: sessionDirectory,
                    RecordSession: false,
                    SessionWatchsetFile: null,
                    SessionOutputDirectory: null,
                    SessionMarkerInputFile: null,
                    SessionSampleCount: 1,
                    SessionIntervalMilliseconds: 500,
                    SessionLabel: null,
                    PlayerCoordTraceFile: null,
                    CaptureLabel: null,
                    CaptureFile: null,
                    ScanString: null,
                    ScanPointer: null,
                    ScanInt32: null,
                    ScanFloat: null,
                    ScanDouble: null,
                    ScanTolerance: 0d,
                    PointerWidth: IntPtr.Size,
                    ScanEncoding: StringScanEncoding.Both,
                    ScanContextBytes: 0,
                    MaxHits: 16,
                    ScanReaderBridgePlayerName: false,
                    ScanReaderBridgePlayerCoords: false,
                    ScanReaderBridgePlayerSignature: false,
                    ScanReaderBridgeIdentity: false,
                    ReadAddonSnapshot: false,
                    AddonSnapshotFile: null,
                    ReadReaderBridgeSnapshot: false,
                    ReaderBridgeSnapshotFile: null,
                    JsonOutput: jsonOutput),
                UsageText);
        }

        if (cheatEngineStatHubs && !rankStatHubs)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-stat-hubs can only be used with --rank-stat-hubs.", UsageText);
        }

        if (rankOwnerComponents && rankStatHubs)
        {
            return ReaderOptionsParseResult.Fail("--rank-owner-components cannot be combined with --rank-stat-hubs.", UsageText);
        }

        if (rankOwnerComponents && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--rank-owner-components cannot be combined with --post-update-triage.", UsageText);
        }

        if (rankStatHubs && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--rank-stat-hubs cannot be combined with --post-update-triage.", UsageText);
        }

        if (readPlayerOrientation)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--read-player-orientation cannot be combined with process attach or memory-read switches.", UsageText);
            }

            if (listModules || scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || readPlayerCoordAnchor || postUpdateTriage || sampleTriageWatchRegions || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs)
            {
                return ReaderOptionsParseResult.Fail("--read-player-orientation cannot be combined with scan, probe, capture, snapshot, or other reader modes.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: null,
                    ProcessName: null,
                    Address: null,
                    Length: null,
                    ListModules: false,
                    ScanModuleName: null,
                    ScanModulePattern: null,
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    RankOwnerComponents: false,
                    OwnerComponentsFile: ownerComponentsFile,
                    RankStatHubs: false,
                    CheatEngineStatHubs: false,
                    ReadPlayerOrientation: true,
                    CaptureReaderBridgeBestFamily: false,
                    ReadPlayerCurrent: false,
                    FindPlayerOrientationCandidate: false,
                    ReadPlayerCoordAnchor: false,
                    ReadTargetCurrent: false,
                    SessionSummary: false,
                    SessionDirectory: null,
                    RecordSession: false,
                    SessionWatchsetFile: null,
                    SessionOutputDirectory: null,
                    SessionMarkerInputFile: null,
                    SessionSampleCount: 1,
                    SessionIntervalMilliseconds: 500,
                    SessionLabel: null,
                    PlayerCoordTraceFile: null,
                    CaptureLabel: null,
                    CaptureFile: null,
                    ScanString: null,
                    ScanPointer: null,
                    ScanInt32: null,
                    ScanFloat: null,
                    ScanDouble: null,
                    ScanTolerance: 0d,
                    PointerWidth: IntPtr.Size,
                    ScanEncoding: StringScanEncoding.Both,
                    ScanContextBytes: 0,
                    MaxHits: 16,
                    ScanReaderBridgePlayerName: false,
                    ScanReaderBridgePlayerCoords: false,
                    ScanReaderBridgePlayerSignature: false,
                    ScanReaderBridgeIdentity: false,
                    ReadAddonSnapshot: false,
                    AddonSnapshotFile: null,
                    ReadReaderBridgeSnapshot: false,
                    ReaderBridgeSnapshotFile: null,
                    JsonOutput: jsonOutput),
                UsageText);
        }

        if (readAddonSnapshot && readReaderBridgeSnapshot)
        {
            return ReaderOptionsParseResult.Fail("Choose either --addon-snapshot or --readerbridge-snapshot, not both.", UsageText);
        }

        if (rankOwnerComponents && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--rank-owner-components cannot be combined with --record-session.", UsageText);
        }

        if (rankStatHubs && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--rank-stat-hubs cannot be combined with --record-session.", UsageText);
        }

        if (rankOwnerComponents)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--rank-owner-components cannot be combined with process attach or memory-read switches.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: null,
                    ProcessName: null,
                    Address: null,
                    Length: null,
                    ListModules: false,
                    ScanModuleName: null,
                    ScanModulePattern: null,
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    RankOwnerComponents: true,
                    OwnerComponentsFile: ownerComponentsFile,
                    RankStatHubs: false,
                    CheatEngineStatHubs: false,
                    ReadPlayerOrientation: false,
                    CaptureReaderBridgeBestFamily: false,
                    ReadPlayerCurrent: false,
                    FindPlayerOrientationCandidate: false,
                    ReadPlayerCoordAnchor: false,
                    ReadTargetCurrent: false,
                    SessionSummary: false,
                    SessionDirectory: null,
                    RecordSession: false,
                    SessionWatchsetFile: null,
                    SessionOutputDirectory: null,
                    SessionMarkerInputFile: null,
                    SessionSampleCount: 1,
                    SessionIntervalMilliseconds: 500,
                    SessionLabel: null,
                    PlayerCoordTraceFile: null,
                    CaptureLabel: null,
                    CaptureFile: null,
                    ScanString: null,
                    ScanPointer: null,
                    ScanInt32: null,
                    ScanFloat: null,
                    ScanDouble: null,
                    ScanTolerance: 0d,
                    PointerWidth: IntPtr.Size,
                    ScanEncoding: StringScanEncoding.Both,
                    ScanContextBytes: 0,
                    MaxHits: 16,
                    ScanReaderBridgePlayerName: false,
                    ScanReaderBridgePlayerCoords: false,
                    ScanReaderBridgePlayerSignature: false,
                    ScanReaderBridgeIdentity: false,
                    ReadAddonSnapshot: false,
                    AddonSnapshotFile: null,
                    ReadReaderBridgeSnapshot: false,
                    ReaderBridgeSnapshotFile: null,
                    JsonOutput: jsonOutput),
                UsageText);
        }

        if (readAddonSnapshot)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("Addon snapshot mode cannot be combined with process attach or memory-read switches.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: null,
                    ProcessName: null,
                    Address: null,
                    Length: null,
                    ListModules: false,
                    ScanModuleName: null,
                    ScanModulePattern: null,
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    RankOwnerComponents: false,
                    OwnerComponentsFile: null,
                    RankStatHubs: false,
                    CheatEngineStatHubs: false,
                    ReadPlayerOrientation: false,
                    CaptureReaderBridgeBestFamily: false,
                    ReadPlayerCurrent: false,
                    FindPlayerOrientationCandidate: false,
                    ReadPlayerCoordAnchor: false,
                    ReadTargetCurrent: false,
                    SessionSummary: false,
                    SessionDirectory: null,
                    RecordSession: false,
                    SessionWatchsetFile: null,
                    SessionOutputDirectory: null,
                    SessionMarkerInputFile: null,
                    SessionSampleCount: 1,
                    SessionIntervalMilliseconds: 500,
                    SessionLabel: null,
                    PlayerCoordTraceFile: null,
                    CaptureLabel: null,
                    CaptureFile: null,
                    ScanString: null,
                    ScanPointer: null,
                    ScanInt32: null,
                    ScanFloat: null,
                    ScanDouble: null,
                    ScanTolerance: 0d,
                    PointerWidth: IntPtr.Size,
                    ScanEncoding: StringScanEncoding.Both,
                    ScanContextBytes: 0,
                    MaxHits: 16,
                    ScanReaderBridgePlayerName: false,
                    ScanReaderBridgePlayerCoords: false,
                    ScanReaderBridgePlayerSignature: false,
                    ScanReaderBridgeIdentity: false,
                    ReadAddonSnapshot: true,
                    AddonSnapshotFile: addonSnapshotFile,
                    ReadReaderBridgeSnapshot: false,
                    ReaderBridgeSnapshotFile: null,
                    JsonOutput: jsonOutput),
                UsageText);
        }

        if (readReaderBridgeSnapshot)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("ReaderBridge snapshot mode cannot be combined with process attach or memory-read switches.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: null,
                    ProcessName: null,
                    Address: null,
                    Length: null,
                    ListModules: false,
                    ScanModuleName: null,
                    ScanModulePattern: null,
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    RankOwnerComponents: false,
                    OwnerComponentsFile: null,
                    RankStatHubs: false,
                    CheatEngineStatHubs: false,
                    ReadPlayerOrientation: false,
                    CaptureReaderBridgeBestFamily: false,
                    ReadPlayerCurrent: false,
                    FindPlayerOrientationCandidate: false,
                    ReadPlayerCoordAnchor: false,
                    ReadTargetCurrent: false,
                    SessionSummary: false,
                    SessionDirectory: null,
                    RecordSession: false,
                    SessionWatchsetFile: null,
                    SessionOutputDirectory: null,
                    SessionMarkerInputFile: null,
                    SessionSampleCount: 1,
                    SessionIntervalMilliseconds: 500,
                    SessionLabel: null,
                    PlayerCoordTraceFile: null,
                    CaptureLabel: null,
                    CaptureFile: null,
                    ScanString: null,
                    ScanPointer: null,
                    ScanInt32: null,
                    ScanFloat: null,
                    ScanDouble: null,
                    ScanTolerance: 0d,
                    PointerWidth: IntPtr.Size,
                    ScanEncoding: StringScanEncoding.Both,
                    ScanContextBytes: 0,
                    MaxHits: 16,
                    ScanReaderBridgePlayerName: false,
                    ScanReaderBridgePlayerCoords: false,
                    ScanReaderBridgePlayerSignature: false,
                    ScanReaderBridgeIdentity: false,
                    ReadAddonSnapshot: false,
                    AddonSnapshotFile: null,
                    ReadReaderBridgeSnapshot: true,
                    ReaderBridgeSnapshotFile: readerBridgeSnapshotFile,
                    JsonOutput: jsonOutput),
                UsageText);
        }

        if (processId.HasValue == !string.IsNullOrWhiteSpace(processName))
        {
            return ReaderOptionsParseResult.Fail("Specify either --pid or --process-name.", UsageText);
        }

        if (sessionWatchsetFile is not null && !recordSession && !postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--session-watchset-file can only be used with --record-session or --post-update-triage.", UsageText);
        }

        if (sessionOutputDirectory is not null && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-output-directory can only be used with --record-session.", UsageText);
        }

        if (sessionMarkerInputFile is not null && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-marker-input-file can only be used with --record-session.", UsageText);
        }

        if (sessionDirectory is not null && !sessionSummary)
        {
            return ReaderOptionsParseResult.Fail("--session-directory can only be used with --session-summary.", UsageText);
        }

        if (sessionLabel is not null && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-label can only be used with --record-session.", UsageText);
        }

        if (recoveryBundleFile is not null && !postUpdateTriage && !sampleTriageWatchRegions)
        {
            return ReaderOptionsParseResult.Fail("--recovery-bundle-file can only be used with --post-update-triage or --sample-triage-watch-regions.", UsageText);
        }

        if ((sessionSampleCount != 1 || sessionIntervalMilliseconds != 500) && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-sample-count and --session-interval-ms can only be used with --record-session.", UsageText);
        }

        if (recordSession && string.IsNullOrWhiteSpace(sessionWatchsetFile))
        {
            return ReaderOptionsParseResult.Fail("--record-session requires --session-watchset-file.", UsageText);
        }

        if (recordSession && string.IsNullOrWhiteSpace(sessionOutputDirectory))
        {
            return ReaderOptionsParseResult.Fail("--record-session requires --session-output-directory.", UsageText);
        }

        if (sessionSummary && string.IsNullOrWhiteSpace(sessionDirectory))
        {
            return ReaderOptionsParseResult.Fail("--session-summary requires --session-directory.", UsageText);
        }

        if (scanRequested && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("Scan mode cannot be combined with raw memory-read switches.", UsageText);
        }

        if (listModules && (scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCoordAnchor || postUpdateTriage || sampleTriageWatchRegions || recordSession || address.HasValue))
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with scan, probe, capture, coord-anchor, post-update-triage, sample-triage-watch-regions, record-session, or raw memory-read switches.", UsageText);
        }

        if (scanModuleName is not null && string.IsNullOrWhiteSpace(scanModulePattern))
        {
            return ReaderOptionsParseResult.Fail("--scan-module-name can only be used with --scan-module-pattern.", UsageText);
        }

        if (writeCheatEngineProbe && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with scan switches.", UsageText);
        }

        if (captureReaderBridgeBestFamily && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with scan switches.", UsageText);
        }

        if (findPlayerOrientationCandidate && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with scan switches.", UsageText);
        }

        if (readPlayerCurrent && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with scan switches.", UsageText);
        }

        if (readTargetCurrent && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with scan switches.", UsageText);
        }

        if (readPlayerCoordAnchor && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with scan switches.", UsageText);
        }

        if (postUpdateTriage && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--post-update-triage cannot be combined with scan switches.", UsageText);
        }

        if (recordSession && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--record-session cannot be combined with scan switches.", UsageText);
        }

        if (writeCheatEngineProbe && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with raw memory-read switches.", UsageText);
        }

        if (captureReaderBridgeBestFamily && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with raw memory-read switches.", UsageText);
        }

        if (findPlayerOrientationCandidate && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readPlayerCurrent && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readTargetCurrent && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readPlayerCoordAnchor && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with raw memory-read switches.", UsageText);
        }

        if (postUpdateTriage && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--post-update-triage cannot be combined with raw memory-read switches.", UsageText);
        }

        if (recordSession && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--record-session cannot be combined with raw memory-read switches.", UsageText);
        }

        if (postUpdateTriage && (writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || findPlayerOrientationCandidate || readPlayerCoordAnchor || readTargetCurrent))
        {
            return ReaderOptionsParseResult.Fail("--post-update-triage cannot be combined with other live reader modes.", UsageText);
        }

        if (sampleTriageWatchRegions && (writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || findPlayerOrientationCandidate || readPlayerCoordAnchor || postUpdateTriage || readTargetCurrent))
        {
            return ReaderOptionsParseResult.Fail("--sample-triage-watch-regions cannot be combined with other live reader modes.", UsageText);
        }

        if (captureLabel is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-label can only be used with --capture-readerbridge-best-family.", UsageText);
        }

        if (captureFile is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-file can only be used with --capture-readerbridge-best-family.", UsageText);
        }

        if (playerCoordTraceFile is not null && !readPlayerCoordAnchor && !postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--player-coord-trace-file can only be used with --read-player-coord-anchor or --post-update-triage.", UsageText);
        }

        if (listModules && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if (listModules && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --read-player-current.", UsageText);
        }

        if (listModules && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --read-target-current.", UsageText);
        }

        if (listModules && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (listModules && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --post-update-triage.", UsageText);
        }

        if (listModules && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --record-session.", UsageText);
        }

        if (writeCheatEngineProbe && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if (writeCheatEngineProbe && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-player-current.", UsageText);
        }

        if (writeCheatEngineProbe && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-target-current.", UsageText);
        }

        if (writeCheatEngineProbe && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (captureReaderBridgeBestFamily && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-player-current.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-target-current.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (captureReaderBridgeBestFamily && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --post-update-triage.", UsageText);
        }

        if (findPlayerOrientationCandidate && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (findPlayerOrientationCandidate && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --post-update-triage.", UsageText);
        }

        if (readPlayerCurrent && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (readPlayerCurrent && postUpdateTriage)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --post-update-triage.", UsageText);
        }

        if (findPlayerOrientationCandidate && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-target-current.", UsageText);
        }

        if (readPlayerCurrent && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --read-target-current.", UsageText);
        }

        if (readPlayerCoordAnchor && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --read-target-current.", UsageText);
        }

        if (postUpdateTriage && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--post-update-triage cannot be combined with --read-target-current.", UsageText);
        }

        if (writeCheatEngineProbe && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --record-session.", UsageText);
        }

        if (captureReaderBridgeBestFamily && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --record-session.", UsageText);
        }

        if (findPlayerOrientationCandidate && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --record-session.", UsageText);
        }

        if (readPlayerCurrent && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --record-session.", UsageText);
        }

        if (readTargetCurrent && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with --record-session.", UsageText);
        }

        if (readPlayerCoordAnchor && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --record-session.", UsageText);
        }

        if (postUpdateTriage && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--post-update-triage cannot be combined with --record-session.", UsageText);
        }

        if (sampleTriageWatchRegions && (listModules || scanRequested || address.HasValue || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs || readPlayerOrientation))
        {
            return ReaderOptionsParseResult.Fail("--sample-triage-watch-regions cannot be combined with scan, raw memory-read, snapshot, ranking, or record-session modes.", UsageText);
        }

        if (address.HasValue != length.HasValue)
        {
            return ReaderOptionsParseResult.Fail("Specify --address and --length together.", UsageText);
        }

        return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: processId,
                    ProcessName: processName,
                    Address: address,
                    Length: length,
                    ListModules: listModules,
                    ScanModuleName: scanModuleName,
                    ScanModulePattern: scanModulePattern,
                    WriteCheatEngineProbe: writeCheatEngineProbe,
                    CheatEngineProbeFile: cheatEngineProbeFile,
                    RankOwnerComponents: false,
                    OwnerComponentsFile: null,
                    RankStatHubs: rankStatHubs,
                    CheatEngineStatHubs: cheatEngineStatHubs,
                    ReadPlayerOrientation: false,
                    CaptureReaderBridgeBestFamily: captureReaderBridgeBestFamily,
                    ReadPlayerCurrent: readPlayerCurrent,
                    FindPlayerOrientationCandidate: findPlayerOrientationCandidate,
                    ReadPlayerCoordAnchor: readPlayerCoordAnchor,
                    ReadTargetCurrent: readTargetCurrent,
                    SessionSummary: false,
                    SessionDirectory: null,
                    RecordSession: recordSession,
                    SessionWatchsetFile: sessionWatchsetFile,
                    SessionOutputDirectory: sessionOutputDirectory,
                    SessionMarkerInputFile: sessionMarkerInputFile,
                    SessionSampleCount: sessionSampleCount,
                    SessionIntervalMilliseconds: sessionIntervalMilliseconds,
                    SessionLabel: sessionLabel,
                    PlayerCoordTraceFile: playerCoordTraceFile,
                    CaptureLabel: captureLabel,
                    CaptureFile: captureFile,
                    ScanString: scanString,
                    ScanPointer: scanPointer,
                    ScanInt32: scanInt32,
                    ScanFloat: scanFloat,
                    ScanDouble: scanDouble,
                    ScanTolerance: scanTolerance,
                    PointerWidth: pointerWidth,
                    ScanEncoding: scanEncoding,
                    ScanContextBytes: scanContextBytes,
                    MaxHits: maxHits,
                    ScanReaderBridgePlayerName: scanReaderBridgePlayerName,
                    ScanReaderBridgePlayerCoords: scanReaderBridgePlayerCoords,
                    ScanReaderBridgePlayerSignature: scanReaderBridgePlayerSignature,
                    ScanReaderBridgeIdentity: scanReaderBridgeIdentity,
                    ReadAddonSnapshot: false,
                    AddonSnapshotFile: null,
                    ReadReaderBridgeSnapshot: false,
                    ReaderBridgeSnapshotFile: null,
                    JsonOutput: jsonOutput,
                    PostUpdateTriage: postUpdateTriage,
                    RecoveryBundleFile: recoveryBundleFile,
                    SampleTriageWatchRegions: sampleTriageWatchRegions),
            UsageText);
    }

    private static bool IsHelpSwitch(string value) =>
        string.Equals(value, "--help", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "-h", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(value, "/?", StringComparison.OrdinalIgnoreCase);

    private static bool TryReadNext(IReadOnlyList<string> args, ref int index, out string value)
    {
        if (index + 1 >= args.Count)
        {
            value = string.Empty;
            return false;
        }

        value = args[++index];
        return true;
    }

    private static bool TryParseAddress(string value, out nint address)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            address = 0;
            return false;
        }

        long parsedValue;

        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            if (!long.TryParse(value[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out parsedValue))
            {
                address = 0;
                return false;
            }
        }
        else if (!long.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out parsedValue))
        {
            address = 0;
            return false;
        }

        if (parsedValue <= 0)
        {
            address = 0;
            return false;
        }

        try
        {
            address = checked((nint)parsedValue);
            return true;
        }
        catch (OverflowException)
        {
            address = 0;
            return false;
        }
    }

    private static bool TryParseScanEncoding(string value, out StringScanEncoding encoding)
    {
        switch (value.Trim().ToLowerInvariant())
        {
            case "ascii":
                encoding = StringScanEncoding.Ascii;
                return true;

            case "utf16":
            case "unicode":
            case "utf-16":
                encoding = StringScanEncoding.Utf16;
                return true;

            case "both":
                encoding = StringScanEncoding.Both;
                return true;

            default:
                encoding = StringScanEncoding.Both;
                return false;
        }
    }
}

public sealed record ReaderOptionsParseResult(
    bool IsSuccess,
    bool ShowUsage,
    int ExitCode,
    string UsageText,
    string? ErrorMessage,
    ReaderOptions? Options)
{
    public static ReaderOptionsParseResult Success(ReaderOptions options, string usageText) =>
        new(true, false, 0, usageText, null, options);

    public static ReaderOptionsParseResult Fail(string errorMessage, string usageText) =>
        new(false, true, 1, usageText, errorMessage, null);

    public static ReaderOptionsParseResult DisplayUsage(string usageText) =>
        new(true, true, 0, usageText, null, null);
}
