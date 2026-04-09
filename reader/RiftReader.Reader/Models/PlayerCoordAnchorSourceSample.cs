namespace RiftReader.Reader.Models;

public sealed record PlayerCoordAnchorSourceSample(
    string AddressHex,
    float? CoordX,
    float? CoordY,
    float? CoordZ);
