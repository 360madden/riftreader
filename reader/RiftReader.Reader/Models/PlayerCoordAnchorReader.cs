using System.Globalization;
using System.Text.RegularExpressions;
using RiftReader.Reader.AddonSnapshots;
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
        ReaderBridgeSnapshotDocument? snapshotDocument,
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

        var comparison = BuildComparison(reader, snapshotDocument, resolvedAnchor);

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
            ReaderBridgeSourceFile: comparison?.ReaderBridgeSourceFile,
            MemorySample: comparison?.Memory,
            Expected: comparison?.Expected,
            Match: comparison?.Match,
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

    private static PlayerCoordAnchorComparison? BuildComparison(
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        PlayerCoordResolvedAnchor? resolvedAnchor)
    {
        if (snapshotDocument?.Current?.Player is not { } player || resolvedAnchor is null)
        {
            return null;
        }

        var memory = ReadSampleAt(
            reader,
            resolvedAnchor.ObjectBaseAddress,
            resolvedAnchor.LevelOffset,
            resolvedAnchor.HealthOffset,
            resolvedAnchor.CoordXOffset,
            resolvedAnchor.CoordYOffset,
            resolvedAnchor.CoordZOffset);

        if (memory is null)
        {
            return null;
        }

        var expected = new PlayerCurrentReadExpected(
            Name: player.Name,
            Location: player.LocationName,
            Level: player.Level,
            Health: player.Hp,
            HealthMax: player.HpMax,
            CoordX: player.Coord?.X,
            CoordY: player.Coord?.Y,
            CoordZ: player.Coord?.Z);

        float? deltaX = memory.CoordX.HasValue && expected.CoordX.HasValue
            ? memory.CoordX.Value - (float)expected.CoordX.Value
            : null;
        float? deltaY = memory.CoordY.HasValue && expected.CoordY.HasValue
            ? memory.CoordY.Value - (float)expected.CoordY.Value
            : null;
        float? deltaZ = memory.CoordZ.HasValue && expected.CoordZ.HasValue
            ? memory.CoordZ.Value - (float)expected.CoordZ.Value
            : null;

        var match = new PlayerCurrentReadMatch(
            LevelMatches: memory.Level.HasValue && expected.Level.HasValue && memory.Level.Value == expected.Level.Value,
            HealthMatches: memory.Health.HasValue && expected.Health.HasValue && memory.Health.Value == expected.Health.Value,
            CoordMatchesWithinTolerance:
                deltaX.HasValue && MathF.Abs(deltaX.Value) <= 0.25f &&
                deltaY.HasValue && MathF.Abs(deltaY.Value) <= 0.25f &&
                deltaZ.HasValue && MathF.Abs(deltaZ.Value) <= 0.25f,
            DeltaX: deltaX,
            DeltaY: deltaY,
            DeltaZ: deltaZ);

        return new PlayerCoordAnchorComparison(
            snapshotDocument.SourceFile,
            memory,
            expected,
            match);
    }

    private static PlayerCurrentReadSample? ReadSampleAt(
        ProcessMemoryReader reader,
        long baseAddress,
        int levelOffset,
        int healthOffset,
        int coordXOffset,
        int coordYOffset,
        int coordZOffset)
    {
        var level = TryReadInt32(reader, baseAddress + levelOffset);
        var health = TryReadInt32(reader, baseAddress + healthOffset);
        var coordX = TryReadFloat(reader, baseAddress + coordXOffset);
        var coordY = TryReadFloat(reader, baseAddress + coordYOffset);
        var coordZ = TryReadFloat(reader, baseAddress + coordZOffset);

        if (!coordX.HasValue || !coordY.HasValue || !coordZ.HasValue)
        {
            return null;
        }

        return new PlayerCurrentReadSample(
            AddressHex: $"0x{baseAddress:X}",
            Level: level,
            Health: health,
            Name: null,
            Location: null,
            CoordX: coordX,
            CoordY: coordY,
            CoordZ: coordZ);
    }

    private static int? TryReadInt32(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(int), out var bytes, out _) || bytes.Length != sizeof(int))
        {
            return null;
        }

        return BitConverter.ToInt32(bytes, 0);
    }

    private static float? TryReadFloat(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(float), out var bytes, out _) || bytes.Length != sizeof(float))
        {
            return null;
        }

        return BitConverter.ToSingle(bytes, 0);
    }

    [GeneratedRegex("^[0-9A-Fa-f]+$", RegexOptions.Compiled)]
    private static partial Regex HexTextRegex();

    [GeneratedRegex(@"\[(?:[^\]]*?)(?<sign>[+-])(?<value>[0-9A-Fa-f]{1,16})\]", RegexOptions.Compiled)]
    private static partial Regex AccessDisplacementRegex();

    [GeneratedRegex(@"\[\s*(?<register>[A-Za-z0-9]+)", RegexOptions.Compiled)]
    private static partial Regex AccessBaseRegisterRegex();

    private sealed record PlayerCoordAnchorComparison(
        string ReaderBridgeSourceFile,
        PlayerCurrentReadSample Memory,
        PlayerCurrentReadExpected Expected,
        PlayerCurrentReadMatch Match);
}
