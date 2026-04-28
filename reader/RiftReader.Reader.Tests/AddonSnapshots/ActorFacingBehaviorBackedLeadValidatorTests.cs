using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ActorFacingBehaviorBackedLeadValidatorTests
{
    [Fact]
    public void Validate_RejectsLeadWhenProcessNameDoesNotMatch()
    {
        var lead = new ActorFacingBehaviorBackedLeadDocument(
            Mode: "actor-facing-behavior-backed-lead",
            GeneratedAtUtc: new DateTimeOffset(2026, 4, 22, 4, 42, 25, TimeSpan.Zero),
            ValidatedAtUtc: new DateTimeOffset(2026, 4, 22, 4, 42, 26, TimeSpan.Zero),
            ProcessName: "rift_x64",
            SourceAddress: "0x24F595F8D10",
            BasisForwardOffset: "0x60",
            BasisDuplicateForwardOffset: "0x94",
            Status: "preferred-solved-lead",
            OperationalStatus: "behavior-backed-lead",
            PreferredLead: true,
            SolvedActorFacing: true,
            CanonicalActorYaw: true,
            Notes: Array.Empty<string>())
        {
            SourceFile = @"C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json"
        };

        var result = ActorFacingBehaviorBackedLeadValidator.Validate(
            lead,
            processName: "other_process",
            processId: 34088,
            processStartTimeUtc: new DateTimeOffset(2026, 4, 22, 4, 19, 33, TimeSpan.Zero));

        Assert.False(result.IsValid);
        Assert.Contains("targets process 'rift_x64'", result.Error, StringComparison.Ordinal);
        Assert.Contains("live process is 'other_process'", result.Error, StringComparison.Ordinal);
    }

    [Fact]
    public void Validate_RejectsLeadWhenValidationPredatesProcessStart()
    {
        var lead = new ActorFacingBehaviorBackedLeadDocument(
            Mode: "actor-facing-behavior-backed-lead",
            GeneratedAtUtc: new DateTimeOffset(2026, 4, 22, 4, 42, 25, TimeSpan.Zero),
            ValidatedAtUtc: new DateTimeOffset(2026, 4, 22, 4, 42, 26, TimeSpan.Zero),
            ProcessName: "rift_x64",
            SourceAddress: "0x24F595F8D10",
            BasisForwardOffset: "0x60",
            BasisDuplicateForwardOffset: "0x94",
            Status: "preferred-solved-lead",
            OperationalStatus: "behavior-backed-lead",
            PreferredLead: true,
            SolvedActorFacing: true,
            CanonicalActorYaw: true,
            Notes: Array.Empty<string>())
        {
            SourceFile = @"C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json"
        };

        var result = ActorFacingBehaviorBackedLeadValidator.Validate(
            lead,
            processName: "rift_x64",
            processId: 34088,
            processStartTimeUtc: new DateTimeOffset(2026, 4, 22, 4, 50, 0, TimeSpan.Zero));

        Assert.False(result.IsValid);
        Assert.Contains("is stale for live PID 34088", result.Error, StringComparison.Ordinal);
        Assert.Contains("2026-04-22T04:42:26.0000000+00:00", result.Error, StringComparison.Ordinal);
        Assert.Contains("2026-04-22T04:50:00.0000000+00:00", result.Error, StringComparison.Ordinal);
    }
}
