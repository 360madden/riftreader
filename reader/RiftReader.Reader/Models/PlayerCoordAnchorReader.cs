using System.Globalization;
using System.Text.RegularExpressions;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public static partial class PlayerCoordAnchorReader
{
    public static PlayerCoordAnchorReadResult Read(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string sourceFile,
        PlayerCoordTraceAnchorDocument traceDocument,
        ModulePatternScanResult? modulePattern)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(traceDocument);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceFile);

        var trace = traceDocument.Trace
            ?? throw new InvalidOperationException("The coord trace document did not contain a trace payload.");

        var matchedOffset = TryParseInt32(trace.MatchedOffset);
        var accessDisplacement = TryParseAccessDisplacement(trace.AccessOperand);
        int? inferredCoordBaseRelativeOffset = null;

        if (accessDisplacement.HasValue && matchedOffset.HasValue)
        {
            inferredCoordBaseRelativeOffset = accessDisplacement.Value - matchedOffset.Value;
        }

        return new PlayerCoordAnchorReadResult(
            Mode: "player-coord-anchor-read",
            ProcessId: processId,
            ProcessName: processName,
            SourceFile: sourceFile,
            VerificationMethod: trace.VerificationMethod,
            CandidateAddress: trace.CandidateAddress,
            CandidateSource: trace.CandidateSource,
            TargetAddress: trace.TargetAddress,
            EffectiveAddress: trace.EffectiveAddress,
            AccessOperand: trace.AccessOperand,
            AccessType: trace.AccessType,
            MatchedOffset: matchedOffset,
            AccessDisplacement: accessDisplacement,
            InferredCoordBaseRelativeOffset: inferredCoordBaseRelativeOffset,
            ModuleName: trace.ModuleName,
            ModuleBase: trace.ModuleBase,
            ModuleOffset: trace.ModuleOffset,
            InstructionAddress: trace.InstructionAddress,
            InstructionSymbol: trace.InstructionSymbol,
            Instruction: trace.Instruction,
            Pattern: trace.NormalizedPattern ?? NormalizePattern(trace.InstructionBytes),
            ModulePattern: modulePattern);
    }

    private static int? TryParseInt32(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static string? NormalizePattern(string? byteText)
    {
        if (string.IsNullOrWhiteSpace(byteText))
        {
            return null;
        }

        var hex = Regex.Replace(byteText, "\\s+", string.Empty).Trim();
        if (hex.Length == 0 || (hex.Length % 2) != 0 || !HexTextRegex().IsMatch(hex))
        {
            return null;
        }

        return string.Join(' ', Enumerable.Range(0, hex.Length / 2).Select(index => hex.Substring(index * 2, 2).ToUpperInvariant()));
    }

    private static int? TryParseAccessDisplacement(string? accessOperand)
    {
        if (string.IsNullOrWhiteSpace(accessOperand))
        {
            return null;
        }

        var match = AccessDisplacementRegex().Match(accessOperand);
        if (!match.Success)
        {
            return null;
        }

        var sign = match.Groups["sign"].Value == "-" ? -1 : 1;
        var token = match.Groups["value"].Value;
        if (!int.TryParse(token, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var parsed))
        {
            return null;
        }

        return sign * parsed;
    }

    [GeneratedRegex("^[0-9A-Fa-f]+$", RegexOptions.Compiled)]
    private static partial Regex HexTextRegex();

    [GeneratedRegex(@"\[(?:[^\]]*?)(?<sign>[+-])(?<value>[0-9A-Fa-f]{1,16})\]", RegexOptions.Compiled)]
    private static partial Regex AccessDisplacementRegex();
}
