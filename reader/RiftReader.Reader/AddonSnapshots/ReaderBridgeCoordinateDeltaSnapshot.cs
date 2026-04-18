namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeCoordinateDeltaSnapshot(
    double? Dx,
    double? Dy,
    double? Dz,
    double? Distance,
    double? Dt,
    double? Speed);
