namespace RiftReader.Reader.Models;

public record PlayerStatHubComponentReference(
    int ComponentIndex,
    string ComponentAddress,
    int Offset,
    string OffsetHex
);
