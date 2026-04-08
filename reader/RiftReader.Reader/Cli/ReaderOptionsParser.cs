using System.Globalization;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Cli;

public static class ReaderOptionsParser
{
    private const string UsageText = """
Usage:
  RiftReader.Reader --pid <processId>
  RiftReader.Reader --process-name <name>
  RiftReader.Reader --pid <processId> --address <hexOrDecimal> --length <byteCount>
  RiftReader.Reader --process-name <name> --cheatengine-probe [--cheatengine-probe-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
  RiftReader.Reader --process-name <name> --capture-readerbridge-best-family [--capture-label <text>] [--capture-file <path>] [--scan-context <bytes>] [--max-hits <count>] [--json]
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
  - Use --cheatengine-probe to generate a Cheat Engine Lua helper script from the latest ReaderBridge export and the current best grouped player signature families.
  - Use --capture-readerbridge-best-family to read the current live values for the top grouped player-signature family and optionally append them to a TSV file.
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
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234 --address 0x7FF600001000 --length 64
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --cheatengine-probe --scan-context 192 --max-hits 8
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --capture-readerbridge-best-family --capture-label baseline --capture-file .\scripts\captures\player-signature-captures.tsv
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
        var writeCheatEngineProbe = false;
        string? cheatEngineProbeFile = null;
        var captureReaderBridgeBestFamily = false;
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

                case "--cheatengine-probe-file":
                    if (!TryReadNext(args, ref index, out var cheatEngineProbeFileValue))
                    {
                        return ReaderOptionsParseResult.Fail("Missing value for --cheatengine-probe-file.", UsageText);
                    }

                    cheatEngineProbeFile = cheatEngineProbeFileValue;
                    writeCheatEngineProbe = true;
                    break;

                case "--capture-readerbridge-best-family":
                    captureReaderBridgeBestFamily = true;
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

        if (readAddonSnapshot && readReaderBridgeSnapshot)
        {
            return ReaderOptionsParseResult.Fail("Choose either --addon-snapshot or --readerbridge-snapshot, not both.", UsageText);
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
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    CaptureReaderBridgeBestFamily: false,
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
                    WriteCheatEngineProbe: false,
                    CheatEngineProbeFile: null,
                    CaptureReaderBridgeBestFamily: false,
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

        if (scanRequested && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("Scan mode cannot be combined with raw memory-read switches.", UsageText);
        }

        if (writeCheatEngineProbe && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with scan switches.", UsageText);
        }

        if (captureReaderBridgeBestFamily && scanRequested)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with scan switches.", UsageText);
        }

        if (writeCheatEngineProbe && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--cheatengine-probe cannot be combined with raw memory-read switches.", UsageText);
        }

        if (captureReaderBridgeBestFamily && address.HasValue)
        {
            return ReaderOptionsParseResult.Fail("--capture-readerbridge-best-family cannot be combined with raw memory-read switches.", UsageText);
        }

        if (captureLabel is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-label can only be used with --capture-readerbridge-best-family.", UsageText);
        }

        if (captureFile is not null && !captureReaderBridgeBestFamily)
        {
            return ReaderOptionsParseResult.Fail("--capture-file can only be used with --capture-readerbridge-best-family.", UsageText);
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
                WriteCheatEngineProbe: writeCheatEngineProbe,
                CheatEngineProbeFile: cheatEngineProbeFile,
                CaptureReaderBridgeBestFamily: captureReaderBridgeBestFamily,
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
                JsonOutput: jsonOutput),
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
