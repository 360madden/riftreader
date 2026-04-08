using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Scanning;

public sealed record ModuleListResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    int ModuleCount,
    IReadOnlyList<ProcessModuleInfo> Modules);
