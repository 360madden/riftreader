using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.CheatEngine;

public sealed record CheatEngineProbeExportResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string OutputFile,
    string ReaderBridgeSourceFile,
    string? PlayerName,
    int? PlayerLevel,
    long? PlayerHealth,
    long? PlayerHealthMax,
    string? LocationName,
    string? CoordText,
    int FamilyCount,
    int HitCount,
    IReadOnlyList<PlayerSignatureFamilySummary> Families);
