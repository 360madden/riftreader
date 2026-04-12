namespace RiftReader.Reader.Scanning;

public sealed record TargetSignatureProbeSample(
    int SampleIndex,
    long Address,
    string AddressHex,
    int? Level,
    int? Health,
    string? Name,
    float? CoordX,
    float? CoordY,
    float? CoordZ,
    float? Distance);
