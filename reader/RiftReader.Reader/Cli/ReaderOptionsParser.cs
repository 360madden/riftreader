using System.Globalization;

namespace RiftReader.Reader.Cli;

public static class ReaderOptionsParser
{
    private const string UsageText = """
Usage:
  RiftReader.Reader --pid <processId>
  RiftReader.Reader --process-name <name>
  RiftReader.Reader --pid <processId> --address <hexOrDecimal> --length <byteCount>

Notes:
  - PTS-only: use this reader only against the Rift Public Test Server.
  - Provide either --pid or --process-name, but not both.
  - Provide --address and --length together when you want a raw memory read.

Examples:
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234
  dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 1234 --address 0x7FF600001000 --length 64
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

                default:
                    return ReaderOptionsParseResult.Fail($"Unknown argument '{arg}'.", UsageText);
            }
        }

        if (processId.HasValue == !string.IsNullOrWhiteSpace(processName))
        {
            return ReaderOptionsParseResult.Fail("Specify either --pid or --process-name.", UsageText);
        }

        if (address.HasValue != length.HasValue)
        {
            return ReaderOptionsParseResult.Fail("Specify --address and --length together.", UsageText);
        }

        return ReaderOptionsParseResult.Success(
            new ReaderOptions(processId, processName, address, length),
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
