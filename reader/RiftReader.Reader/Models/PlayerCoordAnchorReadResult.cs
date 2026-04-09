using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Models;

public sealed record PlayerCoordAnchorReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SourceFile,
    string? VerificationMethod,
    string? CandidateAddress,
    string? CandidateSource,
    string? TargetAddress,
    string? EffectiveAddress,
    string? AccessOperand,
    string? AccessType,
    int? MatchedOffset,
    int? AccessDisplacement,
    int? InferredCoordBaseRelativeOffset,
    string? ModuleName,
    string? ModuleBase,
    string? ModuleOffset,
    string? InstructionAddress,
    string? InstructionSymbol,
    string? Instruction,
    string? Pattern,
    ModulePatternScanResult? ModulePattern);
