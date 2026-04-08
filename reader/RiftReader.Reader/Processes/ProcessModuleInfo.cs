namespace RiftReader.Reader.Processes;

public sealed record ProcessModuleInfo(
    string ModuleName,
    string FileName,
    string BaseAddressHex,
    long BaseAddress,
    int ModuleMemorySize);
