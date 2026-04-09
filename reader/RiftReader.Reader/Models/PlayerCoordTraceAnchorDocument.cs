namespace RiftReader.Reader.Models;

public sealed record PlayerCoordTraceAnchorDocument(
    string? Mode,
    string? GeneratedAtUtc,
    PlayerCoordTraceAnchorReaderSummary? Reader,
    PlayerCoordTraceAnchorTrace? Trace,
    string? OutputFile,
    string? SourceFile);

public sealed record PlayerCoordTraceAnchorReaderSummary(
    string? Mode,
    int? ProcessId,
    string? ProcessName);

public sealed record PlayerCoordTraceAnchorTrace(
    string? Status,
    string? VerificationMethod,
    string? CandidateAddress,
    string? CandidateSource,
    string? TargetAddress,
    int? HitCount,
    string? InstructionAddress,
    string? InstructionSymbol,
    string? Instruction,
    string? InstructionBytes,
    string? NormalizedPattern,
    string? InstructionOpcode,
    string? InstructionExtra,
    string? InstructionSize,
    string? WriteOperand,
    string? AccessOperand,
    string? AccessType,
    string? EffectiveAddress,
    string? AccessMatchesTarget,
    string? MatchedOffset,
    string? ModuleName,
    string? ModuleBase,
    string? ModuleOffset,
    Dictionary<string, string>? Registers);
