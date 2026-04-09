using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public sealed record PlayerOrientationVectorEstimate(
    string Name,
    ValidatorCoordinateSnapshot? Vector,
    double? YawRadians,
    double? YawDegrees,
    double? PitchRadians,
    double? PitchDegrees,
    double? Magnitude);
