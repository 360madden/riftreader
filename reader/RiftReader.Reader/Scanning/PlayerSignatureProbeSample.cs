namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureProbeSample(
    int SampleIndex,
    long Address,
    string AddressHex,
    int? Level,
    int? Health,
    string? Name,
    string? Location,
    float? CoordX,
    float? CoordY,
    float? CoordZ);
