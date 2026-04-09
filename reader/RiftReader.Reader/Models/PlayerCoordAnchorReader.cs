using System.Globalization;
using System.Text.RegularExpressions;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public static partial class PlayerCoordAnchorReader
{
    private const int DefaultLevelOffsetFromCoordBase = -144;
    private const int DefaultHealthOffsetFromCoordBase = -136;
    private const int DefaultCoordXOffsetFromCoordBase = 0;
    private const int DefaultCoordYOffsetFromCoordBase = 4;
    private const int DefaultCoordZOffsetFromCoordBase = 8;

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
        var traceReader = traceDocument.Reader;
        var traceMatchesProcess =
            traceReader?.ProcessId == processId &&
            string.Equals(traceReader.ProcessName, processName, StringComparison.OrdinalIgnoreCase);

        var matchedOffset = TryParseInt32(trace.MatchedOffset);
        var accessDisplacement = TryParseAccessDisplacement(trace.AccessOperand);
        int? inferredCoordBaseRelativeOffset = null;

        if (accessDisplacement.HasValue && matchedOffset.HasValue)
        {
            inferredCoordBaseRelativeOffset = accessDisplacement.Value - matchedOffset.Value;
        }

        var resolvedAnchor = TryResolveObjectAnchor(traceDocument);

        return new PlayerCoordAnchorReadResult(
            Mode: "player-coord-anchor-read",
            ProcessId: processId,
            ProcessName: processName,
            SourceFile: sourceFile,
            TraceProcessId: traceReader?.ProcessId,
            TraceProcessName: traceReader?.ProcessName,
            TraceMatchesProcess: traceMatchesProcess,
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
            BaseRegister: resolvedAnchor?.BaseRegister,
            BaseRegisterValue: resolvedAnchor?.BaseRegisterValue,
            ObjectBaseAddress: resolvedAnchor is null ? null : $"0x{resolvedAnchor.ObjectBaseAddress:X}",
            LevelRelativeOffset: resolvedAnchor?.LevelOffset,
            HealthRelativeOffset: resolvedAnchor?.HealthOffset,
            CoordXRelativeOffset: resolvedAnchor?.CoordXOffset,
            CoordYRelativeOffset: resolvedAnchor?.CoordYOffset,
            CoordZRelativeOffset: resolvedAnchor?.CoordZOffset,
            ModulePattern: modulePattern);
    }

    public static PlayerCoordResolvedAnchor? TryResolveObjectAnchor(PlayerCoordTraceAnchorDocument traceDocument)
    {
        ArgumentNullException.ThrowIfNull(traceDocument);

        var trace = traceDocument.Trace;
        if (trace is null)
        {
            return null;
        }

        var coordBaseRelativeOffset = TryResolveCoordBaseRelativeOffset(trace);
        if (!coordBaseRelativeOffset.HasValue)
        {
            return null;
        }

        var baseRegister = TryParseBaseRegister(trace.AccessOperand);
        if (string.IsNullOrWhiteSpace(baseRegister) ||
            trace.Registers is null ||
            !trace.Registers.TryGetValue(baseRegister.ToUpperInvariant(), out var registerValueText) ||
            !TryParseAddress(registerValueText, out var objectBaseAddress))
        {
            return null;
        }

        return new PlayerCoordResolvedAnchor(
            BaseRegister: baseRegister.ToUpperInvariant(),
            BaseRegisterValue: $"0x{objectBaseAddress:X}",
            ObjectBaseAddress: objectBaseAddress,
            CoordBaseRelativeOffset: coordBaseRelativeOffset.Value,
            CoordXOffset: coordBaseRelativeOffset.Value + DefaultCoordXOffsetFromCoordBase,
            CoordYOffset: coordBaseRelativeOffset.Value + DefaultCoordYOffsetFromCoordBase,
            CoordZOffset: coordBaseRelativeOffset.Value + DefaultCoordZOffsetFromCoordBase,
            LevelOffset: coordBaseRelativeOffset.Value + DefaultLevelOffsetFromCoordBase,
            HealthOffset: coordBaseRelativeOffset.Value + DefaultHealthOffsetFromCoordBase);
    }

    private static int? TryResolveCoordBaseRelativeOffset(PlayerCoordTraceAnchorTrace trace)
    {
        ArgumentNullException.ThrowIfNull(trace);

        var matchedOffset = TryParseInt32(trace.MatchedOffset);
        var accessDisplacement = TryParseAccessDisplacement(trace.AccessOperand);
        if (!matchedOffset.HasValue || !accessDisplacement.HasValue)
        {
            return null;
        }

        return accessDisplacement.Value - matchedOffset.Value;
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

    private static bool TryParseAddress(string? value, out long address)
    {
        address = 0;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var token = value.Trim();
        if (token.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            token = token[2..];
        }

        return long.TryParse(token, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address);
    }

    private static string? TryParseBaseRegister(string? accessOperand)
    {
        if (string.IsNullOrWhiteSpace(accessOperand))
        {
            return null;
        }

        var match = AccessBaseRegisterRegex().Match(accessOperand);
        return match.Success ? match.Groups["register"].Value : null;
    }

    [GeneratedRegex("^[0-9A-Fa-f]+$", RegexOptions.Compiled)]
    private static partial Regex HexTextRegex();

    [GeneratedRegex(@"\[(?:[^\]]*?)(?<sign>[+-])(?<value>[0-9A-Fa-f]{1,16})\]", RegexOptions.Compiled)]
    private static partial Regex AccessDisplacementRegex();

    [GeneratedRegex(@"\[\s*(?<register>[A-Za-z0-9]+)", RegexOptions.Compiled)]
    private static partial Regex AccessBaseRegisterRegex();
}
