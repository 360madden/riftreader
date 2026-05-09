using System.Globalization;
using RiftReader.Reader.Navigation;
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
  RiftReader.Reader [--pid <processId> | --process-name <name>] --read-player-orientation [--owner-components-file <path>] [--json]
  RiftReader.Reader --process-name <name> --capture-readerbridge-best-family [--capture-label <text>] [--capture-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --read-player-current [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --find-player-orientation-candidate [--readerbridge-snapshot-file <path>] [--orientation-candidate-ledger-file <path>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --read-player-coord-anchor [--player-coord-trace-file <path>] [--json]
  RiftReader.Reader --process-name <name> --read-target-current [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --read-navigation-current --destination-waypoint <id> [--navigation-waypoint-file <path>] [--arrival-radius <distance>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --plan-navigation-route --start-waypoint <id> [--via-waypoint <id> ...] --destination-waypoint <id> [--navigation-waypoint-file <path>] [--json]
  RiftReader.Reader --process-name <name> --navigate-waypoint-route --start-waypoint <id> [--via-waypoint <id> ...] --destination-waypoint <id> [--navigation-waypoint-file <path>] [--auto-turn-before-move] [--auto-turn-within-degrees <degrees>] [--turn-left-key <key>] [--turn-right-key <key>] [--turn-pulse-ms <ms>] [--turn-post-sample-delay-ms <ms>] [--turn-settle-delay-ms <ms>] [--turn-max-pulses <count>] [--turn-worsening-tolerance <degrees>] [--turn-max-worsening-pulses <count>] [--json]
  RiftReader.Reader --process-name <name> --capture-navigation-waypoint <id> [--navigation-waypoint-file <path>] [--waypoint-label <text>] [--waypoint-zone <text>] [--waypoint-arrival-radius <distance>] [--waypoint-pace run|walk|keep] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --import-tomtom-waypoints --tomtom-saved-variables-file <path> [--navigation-waypoint-file <path>] [--tomtom-list <name> ...] [--tomtom-zone <zoneId>] [--tomtom-default-y <value>] [--tomtom-id-prefix <prefix>] [--tomtom-arrival-radius <distance>] [--tomtom-pace run|walk|keep] [--json]
  RiftReader.Reader --process-name <name> --navigate-waypoints --start-waypoint <id> --destination-waypoint <id> [--navigation-waypoint-file <path>] [--pace run|walk|keep] [--arrival-radius <distance>] [--max-travel-seconds <seconds>] [--auto-turn-before-move] [--auto-turn-within-degrees <degrees>] [--turn-left-key <key>] [--turn-right-key <key>] [--turn-pulse-ms <ms>] [--turn-post-sample-delay-ms <ms>] [--turn-settle-delay-ms <ms>] [--turn-max-pulses <count>] [--turn-worsening-tolerance <degrees>] [--turn-max-worsening-pulses <count>] [--verbose-navigation-events] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --session-summary --session-directory <path> [--json]
  RiftReader.Reader --process-name <name> --record-session --session-watchset-file <path> --session-output-directory <path> [--session-marker-input-file <path>] [--session-sample-count <count>] [--session-interval-ms <ms>] [--session-label <text>] [--json]
  RiftReader.Reader --process-name <name> --telemetry-preflight [--telemetry-proof-anchor-file <path>] [--telemetry-diagnostics] [--json]
  RiftReader.Reader --process-name <name> --run-telemetry-host [--telemetry-poll-interval-ms <ms>] [--telemetry-output-file <path>] [--telemetry-event-log-file <path>] [--telemetry-diagnostics-log-file <path>] [--telemetry-proof-anchor-file <path>] [--telemetry-diagnostics]
  RiftReader.Reader --process-name <name> --scan-string <text> [--scan-encoding ascii|utf16|both] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-int32 <value> [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-float <value> [--scan-tolerance <epsilon>] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-double <value> [--scan-tolerance <epsilon>] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-player-name [--scan-encoding ascii|utf16|both] [--scan-context <bytes>] [--max-hits <count>]
  RiftReader.Reader --process-name <name> --scan-readerbridge-player-coords [--scan-tolerance <epsilon>] [--scan-context <bytes>] [--max-hits <count>]
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
  - Use --read-player-orientation with --pid/--process-name for the current live behavior-backed actor-facing source. Without a live process selector, it falls back to the LEGACY historical owner-component artifact path.
  - Use --capture-readerbridge-best-family to read the current live values for the top grouped player-signature family and optionally append them to a TSV file.
  - Use --read-player-current to read the current best player-family sample directly from memory and compare it against the latest ReaderBridge export.
  - Use --find-player-orientation-candidate to do a single-process read-only search for live actor/source candidates near current player coordinate hits.
  - Use --readerbridge-snapshot-file with modes that need an explicit ReaderBridge/bootstrap snapshot; by itself it prints that snapshot.
  - Use --orientation-candidate-ledger-file to downrank candidates that prior live stimulus runs already marked as stable but nonresponsive.
  - Use --read-target-current to read the current target snapshot from memory and compare it against the latest ReaderBridge export.
  - Use --read-navigation-current with --destination-waypoint to summarize the live vector from the current player position to a configured waypoint.
  - Use --plan-navigation-route with --start-waypoint, optional repeated --via-waypoint, and --destination-waypoint to validate a v3 multi-segment route plan without sending movement input.
  - Use --navigate-waypoint-route with --start-waypoint, optional repeated --via-waypoint, and --destination-waypoint to execute the v3 chained route path with active movement input; add --auto-turn-before-move to align before each segment.
  - Use --capture-navigation-waypoint to record the current live position into the waypoint JSON so point A / point B runs do not require manual coordinate edits.
  - Use --import-tomtom-waypoints to convert TomTomGlobal.PickupLocations saved variables into RiftReader waypoint JSON. TomTom only stores X/Z; --tomtom-default-y supplies the imported Y value.
  - Use --navigate-waypoints with --start-waypoint and --destination-waypoint to run the manual-facing waypoint navigator that pulses forward movement until arrival or a fail-closed stop condition.
  - Add --auto-turn-before-move when you want the reader to use current actor-facing truth to align heading before forward movement begins.
  - Add --verbose-navigation-events when you want the text formatter to print the full navigation/auto-turn event timeline instead of just the latest summary.
  - Use --read-player-coord-anchor to validate the latest coord-trace artifact against the live process and derive a first code-path-backed coord anchor summary.
  - Use --session-summary to inspect a recorded offline session package without attaching to a live process.
  - Use --record-session to sample named memory regions from a watchset into an owned session folder for offline decoding work.
  - Use --telemetry-preflight to print one merged telemetry readiness snapshot without entering the continuous host loop.
  - Use --run-telemetry-host to publish an always-on merged telemetry snapshot and structured NDJSON logs for local tools.
  - Use --telemetry-proof-anchor-file to preload a freshly validated proof coord anchor cache so the host can publish memory-backed coords immediately when available.
  - Use --session-marker-input-file with --record-session when you want manual or script-driven markers appended during the live recording window.
  - Use --scan-string to search process memory for a text value.
  - Use --scan-int32, --scan-float, or --scan-double to search process memory for numeric values.
  - Use --scan-tolerance with floating-point scans when the stored value may differ slightly from the printed decimal.
  - Use --scan-readerbridge-player-name to load the latest ReaderBridge export and scan the process for the current player name.
  - Use --scan-readerbridge-player-coords to load the latest ReaderBridge export and scan for a contiguous float triplet of the current player coordinates. Add --scan-tolerance when the stored values may differ slightly from the exported decimals.
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
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-orientation --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --read-player-orientation --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --capture-readerbridge-best-family --capture-label baseline --capture-file .\scripts\captures\player-signature-captures.tsv
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --find-player-orientation-candidate --max-hits 8 --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-navigation-current --destination-waypoint example_destination --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --plan-navigation-route --start-waypoint example_start --via-waypoint example_mid --destination-waypoint example_destination --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --navigate-waypoint-route --start-waypoint example_start --via-waypoint example_mid --destination-waypoint example_destination --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --capture-navigation-waypoint point_a --waypoint-label "Point A" --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --import-tomtom-waypoints --tomtom-saved-variables-file .\TomTom.lua --navigation-waypoint-file .\scripts\navigation\tomtom-waypoints.json --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --navigate-waypoints --start-waypoint example_start --destination-waypoint example_destination --pace keep --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --navigate-waypoints --start-waypoint example_start --destination-waypoint example_destination --pace keep --auto-turn-before-move --auto-turn-within-degrees 7.5 --verbose-navigation-events
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --session-summary --session-directory .\scripts\sessions\20260409-baseline --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session --session-watchset-file .\scripts\sessions\watchset.json --session-output-directory .\scripts\sessions\20260409-baseline --session-marker-input-file .\scripts\sessions\baseline.markers.ndjson --session-sample-count 20 --session-interval-ms 500 --session-label baseline --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --telemetry-preflight --telemetry-proof-anchor-file .\scripts\captures\telemetry-proof-coord-anchor.json --telemetry-diagnostics --json
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --run-telemetry-host --telemetry-poll-interval-ms 100 --telemetry-proof-anchor-file .\scripts\captures\telemetry-proof-coord-anchor.json --telemetry-diagnostics
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-string Atank --scan-encoding both --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-int32 17027 --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-float 7389.71 --scan-tolerance 0.01 --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-name --scan-context 32 --max-hits 16
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --scan-readerbridge-player-coords --scan-tolerance 0.05 --scan-context 32 --max-hits 16
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
        var readNavigationCurrent = false;
        var planNavigationRoute = false;
        var navigateWaypointRoute = false;
        var captureNavigationWaypoint = false;
        string? captureNavigationWaypointId = null;
        var navigateWaypoints = false;
        var recordSession = false;
        var sessionSummary = false;
        string? navigationWaypointFile = null;
        string? startWaypointId = null;
        var viaWaypointIds = new List<string>();
        string? destinationWaypointId = null;
        string? pace = null;
        double? arrivalRadius = null;
        int? maxTravelSeconds = null;
        var autoTurnBeforeMove = false;
        double? autoTurnWithinDegrees = null;
        string? turnLeftKey = null;
        string? turnRightKey = null;
        int? turnPulseMilliseconds = null;
        int? turnPostSampleDelayMilliseconds = null;
        int? turnSettleDelayMilliseconds = null;
        int? turnMaxPulses = null;
        double? turnWorseningToleranceDegrees = null;
        int? turnMaxWorseningPulses = null;
        var verboseNavigationEvents = false;
        string? waypointLabel = null;
        string? waypointZone = null;
        double? waypointArrivalRadius = null;
        string? waypointPace = null;
        string? sessionDirectory = null;
        string? sessionWatchsetFile = null;
        string? sessionOutputDirectory = null;
        string? sessionMarkerInputFile = null;
        var sessionSampleCount = 1;
        var sessionIntervalMilliseconds = 500;
        string? sessionLabel = null;
        string? playerCoordTraceFile = null;
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
        string? orientationCandidateLedgerFile = null;
        var rankStatHubs = false;
        var cheatEngineStatHubs = false;
        var readTargetCurrent = false;
        var telemetryPreflight = false;
        var runTelemetryHost = false;
        var telemetryPollIntervalMilliseconds = 100;
        var telemetryDiagnostics = false;
        string? telemetryOutputFile = null;
        string? telemetryEventLogFile = null;
        string? telemetryDiagnosticsLogFile = null;
        string? telemetryProofAnchorFile = null;
        var jsonOutput = false;
        var importTomTomWaypoints = false;
        string? tomTomSavedVariablesFile = null;
        var tomTomListNames = new List<string>();
        string? tomTomZone = null;
        double? tomTomDefaultY = null;
        string? tomTomIdPrefix = null;
        double? tomTomArrivalRadius = null;
        string? tomTomPace = null;

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

                case "--telemetry-preflight":
                    telemetryPreflight = true;
                    break;

                case "--run-telemetry-host":
                    runTelemetryHost = true;
                    break;

                case "--telemetry-poll-interval-ms":
                    if (!TryReadNext(args, ref index, out var telemetryPollIntervalValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --telemetry-poll-interval-ms.", UsageText);
                    }

                    if (!int.TryParse(telemetryPollIntervalValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out telemetryPollIntervalMilliseconds) || telemetryPollIntervalMilliseconds <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid telemetry poll interval '{telemetryPollIntervalValue}'.", UsageText);
                    }

                    break;

                case "--telemetry-output-file":
                    if (!TryReadNext(args, ref index, out var telemetryOutputFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --telemetry-output-file.", UsageText);
                    }

                    telemetryOutputFile = string.IsNullOrWhiteSpace(telemetryOutputFileValue) ? null : telemetryOutputFileValue.Trim();
                    break;

                case "--telemetry-event-log-file":
                    if (!TryReadNext(args, ref index, out var telemetryEventLogFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --telemetry-event-log-file.", UsageText);
                    }

                    telemetryEventLogFile = string.IsNullOrWhiteSpace(telemetryEventLogFileValue) ? null : telemetryEventLogFileValue.Trim();
                    break;

                case "--telemetry-diagnostics-log-file":
                    if (!TryReadNext(args, ref index, out var telemetryDiagnosticsLogFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --telemetry-diagnostics-log-file.", UsageText);
                    }

                    telemetryDiagnosticsLogFile = string.IsNullOrWhiteSpace(telemetryDiagnosticsLogFileValue) ? null : telemetryDiagnosticsLogFileValue.Trim();
                    break;

                case "--telemetry-proof-anchor-file":
                    if (!TryReadNext(args, ref index, out var telemetryProofAnchorFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --telemetry-proof-anchor-file.", UsageText);
                    }

                    telemetryProofAnchorFile = string.IsNullOrWhiteSpace(telemetryProofAnchorFileValue) ? null : telemetryProofAnchorFileValue.Trim();
                    break;

                case "--telemetry-diagnostics":
                    telemetryDiagnostics = true;
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

                case "--orientation-candidate-ledger-file":
                    if (!TryReadNext(args, ref index, out var orientationCandidateLedgerFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --orientation-candidate-ledger-file.", UsageText);
                    }

                    orientationCandidateLedgerFile = orientationCandidateLedgerFileValue;
                    break;

                case "--read-player-coord-anchor":
                    readPlayerCoordAnchor = true;
                    break;

                case "--read-target-current":
                    readTargetCurrent = true;
                    break;

                case "--read-navigation-current":
                    readNavigationCurrent = true;
                    break;

                case "--plan-navigation-route":
                    planNavigationRoute = true;
                    break;

                case "--navigate-waypoint-route":
                    navigateWaypointRoute = true;
                    break;

                case "--capture-navigation-waypoint":
                    if (!TryReadNext(args, ref index, out var captureNavigationWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --capture-navigation-waypoint.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(captureNavigationWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Navigation waypoint id must not be blank.", UsageText);
                    }

                    captureNavigationWaypoint = true;
                    captureNavigationWaypointId = captureNavigationWaypointValue.Trim();
                    break;

                case "--navigate-waypoints":
                    navigateWaypoints = true;
                    break;

                case "--import-tomtom-waypoints":
                    importTomTomWaypoints = true;
                    break;

                case "--tomtom-saved-variables-file":
                    if (!TryReadNext(args, ref index, out var tomTomSavedVariablesFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-saved-variables-file.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(tomTomSavedVariablesFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("TomTom saved variables file must not be blank.", UsageText);
                    }

                    tomTomSavedVariablesFile = tomTomSavedVariablesFileValue;
                    break;

                case "--tomtom-list":
                    if (!TryReadNext(args, ref index, out var tomTomListValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-list.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(tomTomListValue))
                    {
                        return ReaderOptionsParseResult.Fail("TomTom list name must not be blank.", UsageText);
                    }

                    tomTomListNames.Add(tomTomListValue.Trim());
                    break;

                case "--tomtom-zone":
                    if (!TryReadNext(args, ref index, out var tomTomZoneValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-zone.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(tomTomZoneValue))
                    {
                        return ReaderOptionsParseResult.Fail("TomTom zone must not be blank.", UsageText);
                    }

                    tomTomZone = tomTomZoneValue.Trim();
                    break;

                case "--tomtom-default-y":
                    if (!TryReadNext(args, ref index, out var tomTomDefaultYValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-default-y.", UsageText);
                    }

                    if (!double.TryParse(tomTomDefaultYValue, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedTomTomDefaultY) ||
                        !double.IsFinite(parsedTomTomDefaultY))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid TomTom default Y '{tomTomDefaultYValue}'.", UsageText);
                    }

                    tomTomDefaultY = parsedTomTomDefaultY;
                    break;

                case "--tomtom-id-prefix":
                    if (!TryReadNext(args, ref index, out var tomTomIdPrefixValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-id-prefix.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(tomTomIdPrefixValue))
                    {
                        return ReaderOptionsParseResult.Fail("TomTom id prefix must not be blank.", UsageText);
                    }

                    tomTomIdPrefix = tomTomIdPrefixValue.Trim();
                    break;

                case "--tomtom-arrival-radius":
                    if (!TryReadNext(args, ref index, out var tomTomArrivalRadiusValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-arrival-radius.", UsageText);
                    }

                    if (!double.TryParse(tomTomArrivalRadiusValue, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedTomTomArrivalRadius) ||
                        !double.IsFinite(parsedTomTomArrivalRadius) ||
                        parsedTomTomArrivalRadius <= 0d)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid TomTom arrival radius '{tomTomArrivalRadiusValue}'.", UsageText);
                    }

                    tomTomArrivalRadius = parsedTomTomArrivalRadius;
                    break;

                case "--tomtom-pace":
                    if (!TryReadNext(args, ref index, out var tomTomPaceValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --tomtom-pace.", UsageText);
                    }

                    if (!NavigationPace.TryNormalize(tomTomPaceValue, out var normalizedTomTomPace))
                    {
                        return ReaderOptionsParseResult.Fail($"Unsupported TomTom pace '{tomTomPaceValue}'. Use run, walk, or keep.", UsageText);
                    }

                    tomTomPace = normalizedTomTomPace;
                    break;

                case "--navigation-waypoint-file":
                    if (!TryReadNext(args, ref index, out var navigationWaypointFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --navigation-waypoint-file.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(navigationWaypointFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Navigation waypoint file must not be blank.", UsageText);
                    }

                    navigationWaypointFile = navigationWaypointFileValue;
                    break;

                case "--start-waypoint":
                    if (!TryReadNext(args, ref index, out var startWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --start-waypoint.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(startWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Start waypoint id must not be blank.", UsageText);
                    }

                    startWaypointId = startWaypointValue.Trim();
                    break;

                case "--via-waypoint":
                    if (!TryReadNext(args, ref index, out var viaWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --via-waypoint.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(viaWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Via waypoint id must not be blank.", UsageText);
                    }

                    viaWaypointIds.Add(viaWaypointValue.Trim());
                    break;

                case "--destination-waypoint":
                    if (!TryReadNext(args, ref index, out var destinationWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --destination-waypoint.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(destinationWaypointValue))
                    {
                        return ReaderOptionsParseResult.Fail("Destination waypoint id must not be blank.", UsageText);
                    }

                    destinationWaypointId = destinationWaypointValue.Trim();
                    break;

                case "--waypoint-label":
                    if (!TryReadNext(args, ref index, out var waypointLabelValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --waypoint-label.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(waypointLabelValue))
                    {
                        return ReaderOptionsParseResult.Fail("Waypoint label must not be blank.", UsageText);
                    }

                    waypointLabel = waypointLabelValue.Trim();
                    break;

                case "--waypoint-zone":
                    if (!TryReadNext(args, ref index, out var waypointZoneValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --waypoint-zone.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(waypointZoneValue))
                    {
                        return ReaderOptionsParseResult.Fail("Waypoint zone must not be blank.", UsageText);
                    }

                    waypointZone = waypointZoneValue.Trim();
                    break;

                case "--waypoint-arrival-radius":
                    if (!TryReadNext(args, ref index, out var waypointArrivalRadiusValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --waypoint-arrival-radius.", UsageText);
                    }

                    if (!double.TryParse(waypointArrivalRadiusValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedWaypointArrivalRadius) || parsedWaypointArrivalRadius <= 0d)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid waypoint arrival radius '{waypointArrivalRadiusValue}'.", UsageText);
                    }

                    waypointArrivalRadius = parsedWaypointArrivalRadius;
                    break;

                case "--waypoint-pace":
                    if (!TryReadNext(args, ref index, out var waypointPaceValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --waypoint-pace.", UsageText);
                    }

                    if (!NavigationPace.TryNormalize(waypointPaceValue, out var normalizedWaypointPace))
                    {
                        return ReaderOptionsParseResult.Fail($"Unsupported waypoint pace '{waypointPaceValue}'. Use run, walk, or keep.", UsageText);
                    }

                    waypointPace = normalizedWaypointPace;
                    break;

                case "--pace":
                    if (!TryReadNext(args, ref index, out var paceValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --pace.", UsageText);
                    }

                    if (!NavigationPace.TryNormalize(paceValue, out var normalizedPace))
                    {
                        return ReaderOptionsParseResult.Fail($"Unsupported pace '{paceValue}'. Use run, walk, or keep.", UsageText);
                    }

                    pace = normalizedPace;
                    break;

                case "--arrival-radius":
                    if (!TryReadNext(args, ref index, out var arrivalRadiusValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --arrival-radius.", UsageText);
                    }

                    if (!double.TryParse(arrivalRadiusValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedArrivalRadius) || parsedArrivalRadius <= 0d)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid arrival radius '{arrivalRadiusValue}'.", UsageText);
                    }

                    arrivalRadius = parsedArrivalRadius;
                    break;

                case "--max-travel-seconds":
                    if (!TryReadNext(args, ref index, out var maxTravelSecondsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --max-travel-seconds.", UsageText);
                    }

                    if (!int.TryParse(maxTravelSecondsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedMaxTravelSeconds) || parsedMaxTravelSeconds <= 0)
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid max travel seconds '{maxTravelSecondsValue}'.", UsageText);
                    }

                    maxTravelSeconds = parsedMaxTravelSeconds;
                    break;

                case "--auto-turn-before-move":
                    autoTurnBeforeMove = true;
                    break;

                case "--auto-turn-within-degrees":
                    if (!TryReadNext(args, ref index, out var autoTurnWithinDegreesValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --auto-turn-within-degrees.", UsageText);
                    }

                    if (!double.TryParse(autoTurnWithinDegreesValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedAutoTurnWithinDegrees))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid auto-turn within degrees '{autoTurnWithinDegreesValue}'.", UsageText);
                    }

                    autoTurnWithinDegrees = parsedAutoTurnWithinDegrees;
                    break;

                case "--turn-left-key":
                    if (!TryReadNext(args, ref index, out var turnLeftKeyValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-left-key.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(turnLeftKeyValue))
                    {
                        return ReaderOptionsParseResult.Fail("--turn-left-key must not be blank.", UsageText);
                    }

                    turnLeftKey = turnLeftKeyValue.Trim();
                    break;

                case "--turn-right-key":
                    if (!TryReadNext(args, ref index, out var turnRightKeyValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-right-key.", UsageText);
                    }

                    if (string.IsNullOrWhiteSpace(turnRightKeyValue))
                    {
                        return ReaderOptionsParseResult.Fail("--turn-right-key must not be blank.", UsageText);
                    }

                    turnRightKey = turnRightKeyValue.Trim();
                    break;

                case "--turn-pulse-ms":
                    if (!TryReadNext(args, ref index, out var turnPulseMillisecondsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-pulse-ms.", UsageText);
                    }

                    if (!int.TryParse(turnPulseMillisecondsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedTurnPulseMilliseconds))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn pulse milliseconds '{turnPulseMillisecondsValue}'.", UsageText);
                    }

                    turnPulseMilliseconds = parsedTurnPulseMilliseconds;
                    break;

                case "--turn-post-sample-delay-ms":
                    if (!TryReadNext(args, ref index, out var turnPostSampleDelayMillisecondsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-post-sample-delay-ms.", UsageText);
                    }

                    if (!int.TryParse(turnPostSampleDelayMillisecondsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedTurnPostSampleDelayMilliseconds))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn post sample delay milliseconds '{turnPostSampleDelayMillisecondsValue}'.", UsageText);
                    }

                    turnPostSampleDelayMilliseconds = parsedTurnPostSampleDelayMilliseconds;
                    break;

                case "--turn-settle-delay-ms":
                    if (!TryReadNext(args, ref index, out var turnSettleDelayMillisecondsValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-settle-delay-ms.", UsageText);
                    }

                    if (!int.TryParse(turnSettleDelayMillisecondsValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedTurnSettleDelayMilliseconds))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn settle delay milliseconds '{turnSettleDelayMillisecondsValue}'.", UsageText);
                    }

                    turnSettleDelayMilliseconds = parsedTurnSettleDelayMilliseconds;
                    break;

                case "--turn-max-pulses":
                    if (!TryReadNext(args, ref index, out var turnMaxPulsesValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-max-pulses.", UsageText);
                    }

                    if (!int.TryParse(turnMaxPulsesValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedTurnMaxPulses))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn max pulses '{turnMaxPulsesValue}'.", UsageText);
                    }

                    turnMaxPulses = parsedTurnMaxPulses;
                    break;

                case "--turn-worsening-tolerance":
                    if (!TryReadNext(args, ref index, out var turnWorseningToleranceDegreesValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-worsening-tolerance.", UsageText);
                    }

                    if (!double.TryParse(turnWorseningToleranceDegreesValue, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out var parsedTurnWorseningToleranceDegrees))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn worsening tolerance '{turnWorseningToleranceDegreesValue}'.", UsageText);
                    }

                    turnWorseningToleranceDegrees = parsedTurnWorseningToleranceDegrees;
                    break;

                case "--turn-max-worsening-pulses":
                    if (!TryReadNext(args, ref index, out var turnMaxWorseningPulsesValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --turn-max-worsening-pulses.", UsageText);
                    }

                    if (!int.TryParse(turnMaxWorseningPulsesValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedTurnMaxWorseningPulses))
                    {
                        return ReaderOptionsParseResult.Fail($"Invalid turn max worsening pulses '{turnMaxWorseningPulsesValue}'.", UsageText);
                    }

                    turnMaxWorseningPulses = parsedTurnMaxWorseningPulses;
                    break;

                case "--verbose-navigation-events":
                    verboseNavigationEvents = true;
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
                    readPlayerCoordAnchor = true;
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

        var explicitOperationRequested =
            sessionSummary ||
            rankOwnerComponents ||
            rankStatHubs ||
            cheatEngineStatHubs ||
            readPlayerOrientation ||
            readAddonSnapshot ||
            readReaderBridgeSnapshot ||
            captureNavigationWaypoint ||
            planNavigationRoute ||
            navigateWaypointRoute ||
            navigateWaypoints ||
            readPlayerCurrent ||
            readPlayerCoordAnchor ||
            readTargetCurrent ||
            readNavigationCurrent ||
            captureReaderBridgeBestFamily ||
            writeCheatEngineProbe ||
            recordSession ||
            listModules ||
            scanRequested ||
            findPlayerOrientationCandidate ||
            telemetryPreflight ||
            runTelemetryHost ||
            importTomTomWaypoints ||
            address.HasValue ||
            length.HasValue;

        if (!readReaderBridgeSnapshot &&
            !string.IsNullOrWhiteSpace(readerBridgeSnapshotFile) &&
            !explicitOperationRequested)
        {
            readReaderBridgeSnapshot = true;
        }

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

        var tomTomImportOptionProvided =
            tomTomSavedVariablesFile is not null ||
            tomTomListNames.Count > 0 ||
            tomTomZone is not null ||
            tomTomDefaultY.HasValue ||
            tomTomIdPrefix is not null ||
            tomTomArrivalRadius.HasValue ||
            tomTomPace is not null;

        if (tomTomImportOptionProvided && !importTomTomWaypoints)
        {
            return ReaderOptionsParseResult.Fail("TomTom import switches require --import-tomtom-waypoints.", UsageText);
        }

        if (importTomTomWaypoints)
        {
            if (string.IsNullOrWhiteSpace(tomTomSavedVariablesFile))
            {
                return ReaderOptionsParseResult.Fail("--import-tomtom-waypoints requires --tomtom-saved-variables-file.", UsageText);
            }

            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--import-tomtom-waypoints cannot be combined with process attach or raw memory-read switches.", UsageText);
            }

            if (sessionSummary ||
                rankOwnerComponents ||
                rankStatHubs ||
                cheatEngineStatHubs ||
                readPlayerOrientation ||
                readAddonSnapshot ||
                readReaderBridgeSnapshot ||
                captureNavigationWaypoint ||
                planNavigationRoute ||
                navigateWaypointRoute ||
                navigateWaypoints ||
                readPlayerCurrent ||
                readPlayerCoordAnchor ||
                readTargetCurrent ||
                readNavigationCurrent ||
                captureReaderBridgeBestFamily ||
                writeCheatEngineProbe ||
                recordSession ||
                listModules ||
                scanRequested ||
                telemetryPreflight ||
                runTelemetryHost)
            {
                return ReaderOptionsParseResult.Fail("--import-tomtom-waypoints cannot be combined with other reader, snapshot, scan, navigation movement, telemetry, or session modes.", UsageText);
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
                    ScanTolerance: scanTolerance,
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
                    JsonOutput: jsonOutput,
                    NavigationWaypointFile: navigationWaypointFile,
                    ImportTomTomWaypoints: true,
                    TomTomSavedVariablesFile: tomTomSavedVariablesFile,
                    TomTomListNames: tomTomListNames.ToArray(),
                    TomTomZone: tomTomZone,
                    TomTomDefaultY: tomTomDefaultY,
                    TomTomIdPrefix: tomTomIdPrefix,
                    TomTomArrivalRadius: tomTomArrivalRadius,
                    TomTomPace: tomTomPace),
                UsageText);
        }

        if (planNavigationRoute &&
            (sessionSummary ||
             rankOwnerComponents ||
             rankStatHubs ||
             cheatEngineStatHubs ||
             readPlayerOrientation ||
             readAddonSnapshot ||
             readReaderBridgeSnapshot ||
             captureNavigationWaypoint ||
             navigateWaypointRoute || navigateWaypoints ||
             readPlayerCurrent ||
             readPlayerCoordAnchor ||
             readTargetCurrent ||
             readNavigationCurrent ||
             captureReaderBridgeBestFamily ||
             writeCheatEngineProbe ||
             recordSession ||
             listModules ||
             scanRequested ||
             telemetryPreflight ||
             runTelemetryHost ||
             address.HasValue ||
             length.HasValue))
        {
            return ReaderOptionsParseResult.Fail("--plan-navigation-route cannot be combined with other reader, snapshot, scan, navigation movement, telemetry, or raw memory modes.", UsageText);
        }

        if (scanTolerance > 0d && !scanFloat.HasValue && !scanDouble.HasValue && !scanReaderBridgePlayerCoords)
        {
            return ReaderOptionsParseResult.Fail("--scan-tolerance can only be used with --scan-float, --scan-double, or --scan-readerbridge-player-coords.", UsageText);
        }

        if ((telemetryOutputFile is not null || telemetryEventLogFile is not null || telemetryDiagnosticsLogFile is not null || telemetryProofAnchorFile is not null || telemetryDiagnostics) && !runTelemetryHost && !telemetryPreflight)
        {
            return ReaderOptionsParseResult.Fail("Telemetry output, proof-anchor, and diagnostics switches can only be used with --run-telemetry-host or --telemetry-preflight.", UsageText);
        }

        if ((runTelemetryHost || telemetryPreflight) &&
            (sessionSummary ||
             rankOwnerComponents ||
             rankStatHubs ||
             cheatEngineStatHubs ||
             readPlayerOrientation ||
             readAddonSnapshot ||
             readReaderBridgeSnapshot ||
             captureNavigationWaypoint ||
             navigateWaypointRoute || navigateWaypoints ||
             readPlayerCurrent ||
             readPlayerCoordAnchor ||
             readTargetCurrent ||
             readNavigationCurrent ||
             captureReaderBridgeBestFamily ||
             writeCheatEngineProbe ||
             recordSession ||
             listModules ||
             scanRequested ||
             address.HasValue ||
             length.HasValue))
        {
            return ReaderOptionsParseResult.Fail("Telemetry modes cannot be combined with other reader, snapshot, scan, navigation, or raw memory modes.", UsageText);
        }

        if ((runTelemetryHost || telemetryPreflight) && !processId.HasValue && string.IsNullOrWhiteSpace(processName))
        {
            return ReaderOptionsParseResult.Fail("Telemetry modes require --pid or --process-name.", UsageText);
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

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-target-current.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-navigation-current.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && captureNavigationWaypoint)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --capture-navigation-waypoint.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && (navigateWaypointRoute || navigateWaypoints))
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with navigation movement modes.", UsageText);
        }

        if ((readAddonSnapshot || readReaderBridgeSnapshot) && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("Snapshot modes cannot be combined with --read-player-coord-anchor.", UsageText);
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

        if (findPlayerOrientationCandidate &&
            (sessionSummary || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs || readPlayerOrientation || captureNavigationWaypoint || readAddonSnapshot || readReaderBridgeSnapshot))
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with session-summary, ranking, orientation, waypoint-capture, or snapshot modes.", UsageText);
        }

        if (captureNavigationWaypoint &&
            (sessionSummary || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs || readPlayerOrientation))
        {
            return ReaderOptionsParseResult.Fail("--capture-navigation-waypoint cannot be combined with session-summary, ranking, or orientation modes.", UsageText);
        }

        if (sessionSummary)
        {
            if (processId.HasValue || !string.IsNullOrWhiteSpace(processName) || address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--session-summary cannot be combined with process attach or memory-read switches.", UsageText);
            }

            if (listModules || scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || readPlayerCoordAnchor || readTargetCurrent || readNavigationCurrent || navigateWaypointRoute || navigateWaypoints || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs || readPlayerOrientation)
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

        if (readPlayerOrientation)
        {
            if (address.HasValue || length.HasValue)
            {
                return ReaderOptionsParseResult.Fail("--read-player-orientation cannot be combined with memory-read switches.", UsageText);
            }

            if (listModules || scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || readPlayerCoordAnchor || readTargetCurrent || readNavigationCurrent || navigateWaypointRoute || navigateWaypoints || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || rankOwnerComponents || rankStatHubs || cheatEngineStatHubs)
            {
                return ReaderOptionsParseResult.Fail("--read-player-orientation cannot be combined with scan, probe, capture, snapshot, or other reader modes.", UsageText);
            }

            return ReaderOptionsParseResult.Success(
                new ReaderOptions(
                    ProcessId: processId,
                    ProcessName: processName,
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

            if (scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || readPlayerCoordAnchor || readTargetCurrent || readNavigationCurrent || navigateWaypointRoute || navigateWaypoints || recordSession || readAddonSnapshot || readReaderBridgeSnapshot || readPlayerOrientation)
            {
                return ReaderOptionsParseResult.Fail("--rank-owner-components cannot be combined with scan, probe, capture, snapshot, navigation, or other reader modes.", UsageText);
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

        if (sessionWatchsetFile is not null && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-watchset-file can only be used with --record-session.", UsageText);
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

        if (navigationWaypointFile is not null && !readNavigationCurrent && !planNavigationRoute && !navigateWaypointRoute && !captureNavigationWaypoint && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--navigation-waypoint-file can only be used with --read-navigation-current, --plan-navigation-route, --navigate-waypoint-route, --capture-navigation-waypoint, or --navigate-waypoints.", UsageText);
        }

        if (startWaypointId is not null && !planNavigationRoute && !navigateWaypointRoute && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--start-waypoint can only be used with --plan-navigation-route, --navigate-waypoint-route, or --navigate-waypoints.", UsageText);
        }

        if (viaWaypointIds.Count > 0 && !planNavigationRoute && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--via-waypoint can only be used with --plan-navigation-route or --navigate-waypoint-route.", UsageText);
        }

        if (destinationWaypointId is not null && !readNavigationCurrent && !planNavigationRoute && !navigateWaypointRoute && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--destination-waypoint can only be used with --read-navigation-current, --plan-navigation-route, --navigate-waypoint-route, or --navigate-waypoints.", UsageText);
        }

        if (pace is not null && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--pace can only be used with --navigate-waypoints.", UsageText);
        }

        if (arrivalRadius.HasValue && !readNavigationCurrent && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--arrival-radius can only be used with --read-navigation-current or --navigate-waypoints.", UsageText);
        }

        if (maxTravelSeconds.HasValue && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--max-travel-seconds can only be used with --navigate-waypoints.", UsageText);
        }

        if (autoTurnBeforeMove && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--auto-turn-before-move can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (autoTurnWithinDegrees.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--auto-turn-within-degrees can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnLeftKey is not null && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-left-key can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnRightKey is not null && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-right-key can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnPulseMilliseconds.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-pulse-ms can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnPostSampleDelayMilliseconds.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-post-sample-delay-ms can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnSettleDelayMilliseconds.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-settle-delay-ms can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnMaxPulses.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-max-pulses can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnWorseningToleranceDegrees.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-worsening-tolerance can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (turnMaxWorseningPulses.HasValue && !navigateWaypoints && !navigateWaypointRoute)
        {
            return ReaderOptionsParseResult.Fail("--turn-max-worsening-pulses can only be used with --navigate-waypoints or --navigate-waypoint-route.", UsageText);
        }

        if (verboseNavigationEvents && !navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--verbose-navigation-events can only be used with --navigate-waypoints.", UsageText);
        }

        if (!autoTurnBeforeMove &&
            (autoTurnWithinDegrees.HasValue ||
             turnLeftKey is not null ||
             turnRightKey is not null ||
             turnPulseMilliseconds.HasValue ||
             turnPostSampleDelayMilliseconds.HasValue ||
             turnSettleDelayMilliseconds.HasValue ||
             turnMaxPulses.HasValue ||
             turnWorseningToleranceDegrees.HasValue ||
             turnMaxWorseningPulses.HasValue))
        {
            return ReaderOptionsParseResult.Fail("Auto-turn tuning switches require --auto-turn-before-move.", UsageText);
        }

        if (waypointLabel is not null && !captureNavigationWaypoint)
        {
            return ReaderOptionsParseResult.Fail("--waypoint-label can only be used with --capture-navigation-waypoint.", UsageText);
        }

        if (waypointZone is not null && !captureNavigationWaypoint)
        {
            return ReaderOptionsParseResult.Fail("--waypoint-zone can only be used with --capture-navigation-waypoint.", UsageText);
        }

        if (waypointArrivalRadius.HasValue && !captureNavigationWaypoint)
        {
            return ReaderOptionsParseResult.Fail("--waypoint-arrival-radius can only be used with --capture-navigation-waypoint.", UsageText);
        }

        if (waypointPace is not null && !captureNavigationWaypoint)
        {
            return ReaderOptionsParseResult.Fail("--waypoint-pace can only be used with --capture-navigation-waypoint.", UsageText);
        }

        if (sessionLabel is not null && !recordSession)
        {
            return ReaderOptionsParseResult.Fail("--session-label can only be used with --record-session.", UsageText);
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

        if (readNavigationCurrent && string.IsNullOrWhiteSpace(destinationWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--read-navigation-current requires --destination-waypoint.", UsageText);
        }

        if (planNavigationRoute && string.IsNullOrWhiteSpace(startWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--plan-navigation-route requires --start-waypoint.", UsageText);
        }

        if (planNavigationRoute && string.IsNullOrWhiteSpace(destinationWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--plan-navigation-route requires --destination-waypoint.", UsageText);
        }

        if (navigateWaypointRoute && string.IsNullOrWhiteSpace(startWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoint-route requires --start-waypoint.", UsageText);
        }

        if (navigateWaypointRoute && string.IsNullOrWhiteSpace(destinationWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoint-route requires --destination-waypoint.", UsageText);
        }

        if (captureNavigationWaypoint && string.IsNullOrWhiteSpace(captureNavigationWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--capture-navigation-waypoint requires a waypoint id.", UsageText);
        }

        if (navigateWaypoints && string.IsNullOrWhiteSpace(startWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoints requires --start-waypoint.", UsageText);
        }

        if (navigateWaypoints && string.IsNullOrWhiteSpace(destinationWaypointId))
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoints requires --destination-waypoint.", UsageText);
        }

        if (navigateWaypointRoute && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoint-route cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (navigateWaypointRoute &&
            (scanRequested ||
             address.HasValue ||
             length.HasValue ||
             listModules ||
             writeCheatEngineProbe ||
             captureReaderBridgeBestFamily ||
             readPlayerCurrent ||
             findPlayerOrientationCandidate ||
             readTargetCurrent ||
             readNavigationCurrent ||
             captureNavigationWaypoint ||
             readPlayerCoordAnchor ||
             recordSession))
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoint-route cannot be combined with other reader, scan, navigation, coord-anchor, record-session, or raw memory-read modes.", UsageText);
        }

        if (scanRequested && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("Scan mode cannot be combined with raw memory-read switches.", UsageText);
        }

        if (findPlayerOrientationCandidate && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with scan switches.", UsageText);
        }

        if (findPlayerOrientationCandidate && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with raw memory-read switches.", UsageText);
        }

        if (orientationCandidateLedgerFile is not null && !findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--orientation-candidate-ledger-file can only be used with --find-player-orientation-candidate.", UsageText);
        }

        if (captureNavigationWaypoint &&
            (listModules || scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || readPlayerCurrent || findPlayerOrientationCandidate || readTargetCurrent || readNavigationCurrent || navigateWaypointRoute || navigateWaypoints || readPlayerCoordAnchor || recordSession || address.HasValue))
        {
            return ReaderOptionsParseResult.Fail("--capture-navigation-waypoint cannot be combined with list-modules, scan, probe, capture, navigation, coord-anchor, record-session, or raw memory-read switches.", UsageText);
        }

        if (listModules && (scanRequested || writeCheatEngineProbe || captureReaderBridgeBestFamily || findPlayerOrientationCandidate || readPlayerCoordAnchor || readNavigationCurrent || navigateWaypointRoute || navigateWaypoints || recordSession || address.HasValue))
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with scan, probe, capture, navigation, coord-anchor, record-session, or raw memory-read switches.", UsageText);
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

        if (readPlayerCurrent && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with scan switches.", UsageText);
        }

        if (findPlayerOrientationCandidate && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-player-current.", UsageText);
        }

        if (readTargetCurrent && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with scan switches.", UsageText);
        }

        if (readNavigationCurrent && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-navigation-current cannot be combined with scan switches.", UsageText);
        }

        if (navigateWaypoints && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoints cannot be combined with scan switches.", UsageText);
        }

        if (readPlayerCoordAnchor && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with scan switches.", UsageText);
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

        if (readPlayerCurrent && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readTargetCurrent && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readNavigationCurrent && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-navigation-current cannot be combined with raw memory-read switches.", UsageText);
        }

        if (navigateWaypoints && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoints cannot be combined with raw memory-read switches.", UsageText);
        }

        if (readPlayerCoordAnchor && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with raw memory-read switches.", UsageText);
        }

        if (recordSession && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--record-session cannot be combined with raw memory-read switches.", UsageText);
        }

        if (captureLabel is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-label can only be used with --capture-readerbridge-best-family.", UsageText);
        }

        if (captureFile is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-file can only be used with --capture-readerbridge-best-family.", UsageText);
        }

        if (playerCoordTraceFile is not null && !readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--player-coord-trace-file can only be used with --read-player-coord-anchor.", UsageText);
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

        if (listModules && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --read-navigation-current.", UsageText);
        }

        if (listModules && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (listModules && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (listModules && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--list-modules cannot be combined with --record-session.", UsageText);
        }

        if (writeCheatEngineProbe && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-player-current.", UsageText);
        }

        if (writeCheatEngineProbe && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if (writeCheatEngineProbe && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-target-current.", UsageText);
        }

        if (writeCheatEngineProbe && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-navigation-current.", UsageText);
        }

        if (writeCheatEngineProbe && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (writeCheatEngineProbe && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readPlayerCurrent)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-player-current.", UsageText);
        }

        if (captureReaderBridgeBestFamily && findPlayerOrientationCandidate)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --find-player-orientation-candidate.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-target-current.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-navigation-current.", UsageText);
        }

        if (captureReaderBridgeBestFamily && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (captureReaderBridgeBestFamily && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (readPlayerCurrent && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (findPlayerOrientationCandidate && readPlayerCoordAnchor)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-player-coord-anchor.", UsageText);
        }

        if (findPlayerOrientationCandidate && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-target-current.", UsageText);
        }

        if (findPlayerOrientationCandidate && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --read-navigation-current.", UsageText);
        }

        if (findPlayerOrientationCandidate && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (readPlayerCurrent && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --read-target-current.", UsageText);
        }

        if (readPlayerCurrent && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --read-navigation-current.", UsageText);
        }

        if (readPlayerCurrent && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (readPlayerCoordAnchor && readTargetCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --read-target-current.", UsageText);
        }

        if (readTargetCurrent && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with --read-navigation-current.", UsageText);
        }

        if (readTargetCurrent && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (readNavigationCurrent && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--read-navigation-current cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (readPlayerCoordAnchor && readNavigationCurrent)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --read-navigation-current.", UsageText);
        }

        if (readPlayerCoordAnchor && navigateWaypoints)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --navigate-waypoints.", UsageText);
        }

        if (writeCheatEngineProbe && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with --record-session.", UsageText);
        }

        if (captureReaderBridgeBestFamily && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with --record-session.", UsageText);
        }

        if (readPlayerCurrent && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-player-current cannot be combined with --record-session.", UsageText);
        }

        if (findPlayerOrientationCandidate && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--find-player-orientation-candidate cannot be combined with --record-session.", UsageText);
        }

        if (readTargetCurrent && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-target-current cannot be combined with --record-session.", UsageText);
        }

        if (readNavigationCurrent && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-navigation-current cannot be combined with --record-session.", UsageText);
        }

        if (navigateWaypoints && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--navigate-waypoints cannot be combined with --record-session.", UsageText);
        }

        if (readPlayerCoordAnchor && recordSession)
        {
            return ReaderOptionsParseResult.Fail("--read-player-coord-anchor cannot be combined with --record-session.", UsageText);
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
                    ReaderBridgeSnapshotFile: readerBridgeSnapshotFile,
                    JsonOutput: jsonOutput,
                    FindPlayerOrientationCandidate: findPlayerOrientationCandidate,
                    OrientationCandidateLedgerFile: orientationCandidateLedgerFile,
                    ReadNavigationCurrent: readNavigationCurrent,
                    PlanNavigationRoute: planNavigationRoute,
                    NavigateWaypointRoute: navigateWaypointRoute,
                    NavigateWaypoints: navigateWaypoints,
                    NavigationWaypointFile: navigationWaypointFile,
                    StartWaypointId: startWaypointId,
                    ViaWaypointIds: viaWaypointIds.ToArray(),
                    DestinationWaypointId: destinationWaypointId,
                    Pace: pace,
                    ArrivalRadius: arrivalRadius,
                    MaxTravelSeconds: maxTravelSeconds,
                    AutoTurnBeforeMove: autoTurnBeforeMove,
                    AutoTurnWithinDegrees: autoTurnWithinDegrees,
                    TurnLeftKey: turnLeftKey,
                    TurnRightKey: turnRightKey,
                    TurnPulseMilliseconds: turnPulseMilliseconds,
                    TurnPostSampleDelayMilliseconds: turnPostSampleDelayMilliseconds,
                    TurnSettleDelayMilliseconds: turnSettleDelayMilliseconds,
                    TurnMaxPulses: turnMaxPulses,
                    TurnWorseningToleranceDegrees: turnWorseningToleranceDegrees,
                    TurnMaxWorseningPulses: turnMaxWorseningPulses,
                    CaptureNavigationWaypoint: captureNavigationWaypoint,
                    CaptureNavigationWaypointId: captureNavigationWaypointId,
                    WaypointLabel: waypointLabel,
                    WaypointZone: waypointZone,
                    WaypointArrivalRadius: waypointArrivalRadius,
                    WaypointPace: waypointPace,
                    TelemetryPreflight: telemetryPreflight,
                    RunTelemetryHost: runTelemetryHost,
                    TelemetryPollIntervalMilliseconds: telemetryPollIntervalMilliseconds,
                    TelemetryDiagnostics: telemetryDiagnostics,
                    TelemetryOutputFile: telemetryOutputFile,
                    TelemetryEventLogFile: telemetryEventLogFile,
                    TelemetryDiagnosticsLogFile: telemetryDiagnosticsLogFile,
                    TelemetryProofAnchorFile: telemetryProofAnchorFile,
                    VerboseNavigationEvents: verboseNavigationEvents),
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
