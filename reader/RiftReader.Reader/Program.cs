using RiftReader.Reader.Cli;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader;

internal static class Program
{
    private static int Main(string[] args)
    {
        var parseResult = ReaderOptionsParser.Parse(args);

        if (parseResult.ShowUsage)
        {
            WriteUsage(parseResult);
            return parseResult.ExitCode;
        }

        if (!parseResult.IsSuccess || parseResult.Options is null)
        {
            Console.Error.WriteLine(parseResult.ErrorMessage ?? "Unable to parse command line arguments.");
            Console.Error.WriteLine();
            WriteUsage(parseResult);
            return parseResult.ExitCode;
        }

        var options = parseResult.Options;

        Console.WriteLine("RiftReader.Reader");
        Console.WriteLine("PTS-only scope: use this tool only against the Rift Public Test Server.");
        Console.WriteLine();

        var locator = new ProcessLocator();

        string? lookupError;
        using var process = options.ProcessId.HasValue
            ? locator.FindById(options.ProcessId.Value, out lookupError)
            : locator.FindByName(options.ProcessName!, out lookupError);

        if (process is null)
        {
            Console.Error.WriteLine(lookupError ?? "Unable to resolve the target process.");
            return 1;
        }

        var target = ProcessTarget.FromProcess(process);

        Console.WriteLine($"Attached to PID {target.ProcessId} ({target.ProcessName}).");

        if (!string.IsNullOrWhiteSpace(target.ModuleName))
        {
            Console.WriteLine($"Module: {target.ModuleName}");
        }

        if (!string.IsNullOrWhiteSpace(target.MainWindowTitle))
        {
            Console.WriteLine($"Window: {target.MainWindowTitle}");
        }

        Console.WriteLine();

        if (!options.Address.HasValue || !options.Length.HasValue)
        {
            Console.WriteLine("Attach verified. No memory read was requested.");
            Console.WriteLine("Next step: add pointer maps and typed readers for the PTS structures you want to inspect.");
            return 0;
        }

        using var reader = ProcessMemoryReader.TryOpen(target, out var openError);

        if (reader is null)
        {
            Console.Error.WriteLine(openError ?? "Unable to open a memory-reading handle for the target process.");
            return 1;
        }

        if (!reader.TryReadBytes(options.Address.Value, options.Length.Value, out var bytes, out var readError))
        {
            Console.Error.WriteLine(readError ?? "Memory read failed.");
            return 1;
        }

        Console.WriteLine($"Read {bytes.Length} bytes from 0x{options.Address.Value.ToInt64():X}.");
        Console.WriteLine();
        Console.WriteLine(HexDumpFormatter.Format(bytes, options.Address.Value));

        return 0;
    }

    private static void WriteUsage(ReaderOptionsParseResult parseResult)
    {
        Console.WriteLine(parseResult.UsageText);
    }
}
