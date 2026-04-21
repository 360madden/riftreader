namespace RiftReader.Reader.Models;

public sealed record PlayerActorTruthReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ReaderBridgeSourceFile,
    string? TraceSourceFile,
    bool TraceAvailable,
    bool TraceMatchesProcess,
    string CoordBootstrapSource,
    string OrientationResolutionSource,
    PlayerActorCoordReadResult Coordinates,
    PlayerActorOrientationReadResult Orientation,
    IReadOnlyList<string> Notes);
