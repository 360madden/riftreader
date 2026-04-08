namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureSignal(
    string Name,
    string Value,
    int RelativeOffset);
