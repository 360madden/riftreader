namespace RiftReader.Reader.AddonSnapshots;

public sealed record ValidatorSnapshot(
    long? Sequence,
    string? Reason,
    double? CapturedAt,
    string? PlayerUnit,
    string? Name,
    int? Level,
    long? Health,
    long? HealthMax,
    long? Mana,
    long? ManaMax,
    long? Energy,
    long? EnergyMax,
    long? Power,
    long? Charge,
    long? ChargeMax,
    long? Combo,
    string? Role,
    bool? Combat,
    string? Zone,
    string? LocationName,
    ValidatorCoordinateSnapshot? Coord);
