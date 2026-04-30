using System.Text.Json;
using System.Reflection;
using RiftReader.Reader.Navigation;
using RiftReader.Reader.Models;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Tests.Navigation;

public sealed class WaypointNavigationConfigurationLoaderTests
{
    [Fact]
    public void TryLoad_RejectsDuplicateWaypointIds()
    {
        var filePath = CreateTempWaypointFile(
            """
            {
              "schemaVersion": 1,
              "movement": {
                "forwardKey": "w",
                "defaultPace": "keep",
                "forwardPulseMilliseconds": 250,
                "postPulseSampleDelayMilliseconds": 150,
                "startRadius": 2.0,
                "defaultArrivalRadius": 1.5,
                "noProgressWindowMilliseconds": 1500,
                "minimumProgressDistance": 0.35,
                "wrongWayToleranceDistance": 0.75,
                "maxTravelSeconds": 30
              },
              "waypoints": [
                { "id": "dup", "x": 0.0, "y": 0.0, "z": 0.0 },
                { "id": "dup", "x": 5.0, "y": 0.0, "z": 0.0 }
              ]
            }
            """);

        try
        {
            var configuration = WaypointNavigationConfigurationLoader.TryLoad(filePath, out var error);

            Assert.Null(configuration);
            Assert.Contains("duplicate waypoint id", error, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            DeleteTempWaypointFile(filePath);
        }
    }

    [Fact]
    public void TryLoad_RejectsMissingForwardKey()
    {
        var filePath = CreateTempWaypointFile(
            """
            {
              "schemaVersion": 1,
              "movement": {
                "defaultPace": "keep",
                "forwardPulseMilliseconds": 250,
                "postPulseSampleDelayMilliseconds": 150,
                "startRadius": 2.0,
                "defaultArrivalRadius": 1.5,
                "noProgressWindowMilliseconds": 1500,
                "minimumProgressDistance": 0.35,
                "wrongWayToleranceDistance": 0.75,
                "maxTravelSeconds": 30
              },
              "waypoints": [
                { "id": "start", "x": 0.0, "y": 0.0, "z": 0.0 }
              ]
            }
            """);

        try
        {
            var configuration = WaypointNavigationConfigurationLoader.TryLoad(filePath, out var error);

            Assert.Null(configuration);
            Assert.Contains("movement.forwardKey", error, StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            DeleteTempWaypointFile(filePath);
        }
    }

    private static string CreateTempWaypointFile(string json)
    {
        var tempDirectory = Path.Combine(Path.GetTempPath(), "RiftReader.Tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);

        var filePath = Path.Combine(tempDirectory, "waypoints.json");
        File.WriteAllText(filePath, json);
        return filePath;
    }

    private static void DeleteTempWaypointFile(string filePath)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            return;
        }

        if (File.Exists(filePath))
        {
            File.Delete(filePath);
        }

        var tempDirectory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(tempDirectory) && Directory.Exists(tempDirectory))
        {
            Directory.Delete(tempDirectory, recursive: true);
        }
    }
}

public sealed class NavigationMathTests
{
    [Fact]
    public void BuildSummary_ComputesExpectedVectorFields()
    {
        var destination = new WaypointDefinition(
            Id: "destination",
            Label: "Destination",
            Zone: null,
            X: 4d,
            Y: 7d,
            Z: 9d,
            ArrivalRadius: 6.5d,
            Pace: null);
        var current = new NavigationPoseSample("0x1234", 1d, 2d, 3d);

        var summary = NavigationMath.BuildSummary(
            processId: 42,
            processName: "rift_x64",
            waypointFile: @"C:\RIFT MODDING\RiftReader\scripts\navigation\waypoints.json",
            destinationWaypoint: destination,
            currentSample: current,
            anchorSource: "coord-trace-anchor",
            arrivalRadius: 6.5d);

        Assert.Equal("navigation-current-read", summary.Mode);
        Assert.Equal(3d, summary.DeltaX);
        Assert.Equal(5d, summary.DeltaY);
        Assert.Equal(6d, summary.DeltaZ);
        Assert.InRange(summary.PlanarDistance, 6.7082d, 6.7083d);
        Assert.Equal(5d, summary.HeightDelta);
        Assert.InRange(summary.WorldBearingRadians, 1.1071d, 1.1072d);
        Assert.InRange(summary.WorldBearingDegrees, 63.4349d, 63.4351d);
        Assert.False(summary.WithinArrivalRadius);
        Assert.Null(summary.Facing);
    }

    [Fact]
    public void BuildFacingSummary_ComputesExpectedHeadingDeltaFields()
    {
        var component = Math.Sqrt(0.5d);
        var orientation = new PlayerOrientationReadResult(
            Mode: "player-orientation-live",
            ArtifactFile: @"C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json",
            ArtifactLoadedAtUtc: new DateTimeOffset(2026, 4, 23, 6, 0, 0, TimeSpan.Zero),
            ArtifactGeneratedAtUtc: new DateTimeOffset(2026, 4, 23, 6, 0, 0, TimeSpan.Zero),
            SnapshotFile: null,
            SnapshotLoadedAtUtc: null,
            PlayerName: "Atank",
            PlayerLevel: 45,
            PlayerGuild: null,
            PlayerLocation: null,
            PlayerCoord: null,
            SelectedSourceAddress: "0x1234",
            SelectedEntryAddress: null,
            SelectedEntryIndex: null,
            SelectedEntryMatchesSelectedSource: false,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "live-behavior-backed-lead",
            BasisPrimaryForwardOffset: "0xD4",
            BasisDuplicateForwardOffset: null,
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0xD4.Forward",
                Vector: new ValidatorCoordinateSnapshot(component, 0d, component),
                YawRadians: Math.PI / 4d,
                YawDegrees: 45d,
                PitchRadians: 0d,
                PitchDegrees: 0d,
                Magnitude: 1d),
            BasisPrimaryEstimate: null,
            BasisDuplicateEstimate: null,
            BasisDuplicateDeltaMagnitude: null,
            BasisDuplicateAgreementStrong: null,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: Array.Empty<string>());

        var facing = NavigationMath.BuildFacingSummary(orientation, destinationBearingDegrees: 90d);

        Assert.Equal("available", facing.Status);
        Assert.Equal("behavior-backed-memory-facing", facing.SourceKind);
        Assert.Equal("0x1234", facing.SelectedSourceAddress);
        Assert.Equal("0xD4", facing.BasisPrimaryForwardOffset);
        Assert.Equal("live-behavior-backed-lead", facing.ResolutionMode);
        Assert.Equal(45d, facing.YawDegrees);
        Assert.Equal(0d, facing.PitchDegrees);
        Assert.Equal(45d, facing.SignedBearingDeltaDegrees);
        Assert.Equal(45d, facing.AbsoluteBearingDeltaDegrees);
        Assert.Equal("right", facing.SuggestedTurnDirection);
        Assert.Null(facing.Reason);
    }

    [Fact]
    public void BuildFacingSummary_MapsForwardVectorIntoMovementSpaceBearing()
    {
        var orientation = new PlayerOrientationReadResult(
            Mode: "player-orientation-live",
            ArtifactFile: @"C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json",
            ArtifactLoadedAtUtc: new DateTimeOffset(2026, 4, 23, 6, 0, 0, TimeSpan.Zero),
            ArtifactGeneratedAtUtc: new DateTimeOffset(2026, 4, 23, 6, 0, 0, TimeSpan.Zero),
            SnapshotFile: null,
            SnapshotLoadedAtUtc: null,
            PlayerName: "Atank",
            PlayerLevel: 45,
            PlayerGuild: null,
            PlayerLocation: null,
            PlayerCoord: null,
            SelectedSourceAddress: "0x1234",
            SelectedEntryAddress: null,
            SelectedEntryIndex: null,
            SelectedEntryMatchesSelectedSource: false,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "live-behavior-backed-lead",
            BasisPrimaryForwardOffset: "0xD4",
            BasisDuplicateForwardOffset: null,
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0xD4.Forward",
                Vector: new ValidatorCoordinateSnapshot(1d, 0d, 0d),
                YawRadians: 0d,
                YawDegrees: 0d,
                PitchRadians: 0d,
                PitchDegrees: 0d,
                Magnitude: 1d),
            BasisPrimaryEstimate: null,
            BasisDuplicateEstimate: null,
            BasisDuplicateDeltaMagnitude: null,
            BasisDuplicateAgreementStrong: null,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: Array.Empty<string>());

        var facing = NavigationMath.BuildFacingSummary(orientation, destinationBearingDegrees: 90d);

        Assert.Equal("available", facing.Status);
        Assert.Equal(90d, facing.YawDegrees);
        Assert.Equal(0d, facing.SignedBearingDeltaDegrees);
        Assert.Equal(0d, facing.AbsoluteBearingDeltaDegrees);
        Assert.Equal("aligned", facing.SuggestedTurnDirection);
    }

    [Fact]
    public void BuildFacingSummary_ReturnsUnavailableWhenPreferredYawIsMissing()
    {
        var orientation = new PlayerOrientationReadResult(
            Mode: "player-orientation-read",
            ArtifactFile: "artifact.json",
            ArtifactLoadedAtUtc: DateTimeOffset.UtcNow,
            ArtifactGeneratedAtUtc: null,
            SnapshotFile: null,
            SnapshotLoadedAtUtc: null,
            PlayerName: "Atank",
            PlayerLevel: 45,
            PlayerGuild: null,
            PlayerLocation: null,
            PlayerCoord: null,
            SelectedSourceAddress: "0x1234",
            SelectedEntryAddress: null,
            SelectedEntryIndex: null,
            SelectedEntryMatchesSelectedSource: false,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "live-behavior-backed-lead",
            BasisPrimaryForwardOffset: "0xD4",
            BasisDuplicateForwardOffset: null,
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0xD4.Forward",
                Vector: null,
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: 0d,
                PitchDegrees: 0d,
                Magnitude: null),
            BasisPrimaryEstimate: null,
            BasisDuplicateEstimate: null,
            BasisDuplicateDeltaMagnitude: null,
            BasisDuplicateAgreementStrong: null,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: Array.Empty<string>());

        var facing = NavigationMath.BuildFacingSummary(orientation, destinationBearingDegrees: 90d);

        Assert.Equal("estimate-unavailable", facing.Status);
        Assert.Equal("behavior-backed-memory-facing", facing.SourceKind);
        Assert.Null(facing.AbsoluteBearingDeltaDegrees);
        Assert.Null(facing.SuggestedTurnDirection);
        Assert.Contains("usable movement-space yaw estimate", facing.Reason, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void BuildCandidateFacingSummary_ReportsOwnerArtifactAsNonCanonicalCandidate()
    {
        var orientation = CreateOwnerArtifactOrientation();

        var facing = NavigationMath.BuildCandidateFacingSummary(
            orientation,
            destinationBearingDegrees: 60d,
            status: "fallback-candidate",
            sourceKind: "owner-components-artifact-candidate-facing",
            reason: "Behavior-backed facing was read-failed; owner-components artifact is fallback candidate only, not canonical/actionable navigation truth.");

        Assert.Equal("fallback-candidate", facing.Status);
        Assert.Equal("owner-components-artifact-candidate-facing", facing.SourceKind);
        Assert.Equal("artifact-owner-components", facing.ResolutionMode);
        Assert.Equal("0x1234", facing.SelectedSourceAddress);
        Assert.Equal("0x60", facing.BasisPrimaryForwardOffset);
        Assert.Equal("0x94", facing.BasisDuplicateForwardOffset);
        Assert.Equal(90d, facing.YawDegrees);
        Assert.Equal(-30d, facing.SignedBearingDeltaDegrees);
        Assert.Equal(30d, facing.AbsoluteBearingDeltaDegrees);
        Assert.Equal("left", facing.SuggestedTurnDirection);
        Assert.Contains("fallback candidate only", facing.Reason, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("not canonical/actionable", facing.Reason, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void BuildTurnPlan_DoesNotUseFallbackCandidateAsActionableFacing()
    {
        var orientation = CreateOwnerArtifactOrientation();
        var facing = NavigationMath.BuildCandidateFacingSummary(
            orientation,
            destinationBearingDegrees: 60d,
            status: "fallback-candidate",
            sourceKind: "owner-components-artifact-candidate-facing",
            reason: "Owner-components artifact is fallback candidate only, not canonical/actionable navigation truth.");

        var turnPlan = NavigationMath.BuildTurnPlan(
            facing,
            destinationBearingDegrees: 60d,
            alignmentThresholdDegrees: 7.5d);

        Assert.Equal("unavailable", turnPlan.Status);
        Assert.Equal("owner-components-artifact-candidate-facing", turnPlan.SourceKind);
        Assert.Equal("artifact-owner-components", turnPlan.ResolutionMode);
        Assert.Equal(90d, turnPlan.CurrentYawDegrees);
        Assert.Equal(-30d, turnPlan.SignedBearingDeltaDegrees);
        Assert.Equal(30d, turnPlan.AbsoluteBearingDeltaDegrees);
        Assert.Null(turnPlan.SuggestedTurnDirection);
        Assert.False(turnPlan.WithinAlignmentThreshold);
        Assert.Contains("fallback candidate only", turnPlan.Reason, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void BuildTurnPlan_ReturnsAlignedWhenFacingIsWithinThreshold()
    {
        var facing = new NavigationFacingSummary(
            Status: "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: "live-behavior-backed-lead",
            SelectedSourceAddress: "0x1234",
            BasisPrimaryForwardOffset: "0xD4",
            BasisDuplicateForwardOffset: null,
            YawRadians: Math.PI / 4d,
            YawDegrees: 45d,
            PitchRadians: 0d,
            PitchDegrees: 0d,
            SignedBearingDeltaDegrees: 4.5d,
            AbsoluteBearingDeltaDegrees: 4.5d,
            SuggestedTurnDirection: "left",
            Reason: null);

        var turnPlan = NavigationMath.BuildTurnPlan(
            facing,
            destinationBearingDegrees: 49.5d,
            alignmentThresholdDegrees: 7.5d);

        Assert.Equal("aligned", turnPlan.Status);
        Assert.True(turnPlan.WithinAlignmentThreshold);
        Assert.Equal("aligned", turnPlan.SuggestedTurnDirection);
        Assert.Equal(7.5d, turnPlan.AlignmentThresholdDegrees);
    }

    private static PlayerOrientationReadResult CreateOwnerArtifactOrientation() =>
        new(
            Mode: "player-orientation",
            ArtifactFile: @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            ArtifactLoadedAtUtc: new DateTimeOffset(2026, 4, 30, 12, 0, 0, TimeSpan.Zero),
            ArtifactGeneratedAtUtc: new DateTimeOffset(2026, 4, 30, 11, 59, 0, TimeSpan.Zero),
            SnapshotFile: null,
            SnapshotLoadedAtUtc: null,
            PlayerName: "Atank",
            PlayerLevel: 45,
            PlayerGuild: null,
            PlayerLocation: "Sanctum Watch",
            PlayerCoord: null,
            SelectedSourceAddress: "0x1234",
            SelectedEntryAddress: "0x1234",
            SelectedEntryIndex: 1,
            SelectedEntryMatchesSelectedSource: true,
            SelectedEntryRoleHints: new[] { "selected-source", "orientation" },
            ResolutionMode: "artifact-owner-components",
            BasisPrimaryForwardOffset: "0x60",
            BasisDuplicateForwardOffset: "0x94",
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "Orientation60",
                Vector: new ValidatorCoordinateSnapshot(1d, 0d, 0d),
                YawRadians: 0d,
                YawDegrees: 0d,
                PitchRadians: 0d,
                PitchDegrees: 0d,
                Magnitude: 1d),
            BasisPrimaryEstimate: null,
            BasisDuplicateEstimate: null,
            BasisDuplicateDeltaMagnitude: null,
            BasisDuplicateAgreementStrong: null,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: Array.Empty<string>());
}

public sealed class NavigationPoseSourcePolicyTests
{
    [Fact]
    public void TryCreateWithPolicy_StrictCoordTrace_ReturnsTraceResultWithoutFallback()
    {
        var traceResult = new NavigationPoseSourceCreationResult(
            new FakePolicyPoseSource(),
            new NavigationPoseSample("0xTRACE", 1d, 2d, 3d));
        var cachedInvoked = false;
        var reacquiredInvoked = false;

        var result = NavigationPoseSourceFactory.TryCreateWithPolicy(
            NavigationPoseSourcePolicy.StrictCoordTrace,
            tryTraceAnchor: () => new NavigationPoseSourceResolutionStepResult(traceResult),
            tryCachedAnchor: () =>
            {
                cachedInvoked = true;
                return new NavigationPoseSourceResolutionStepResult(null);
            },
            tryReacquiredAnchor: () =>
            {
                reacquiredInvoked = true;
                return new NavigationPoseSourceResolutionStepResult(null);
            },
            out var error);

        Assert.Same(traceResult, result);
        Assert.Null(error);
        Assert.False(cachedInvoked);
        Assert.False(reacquiredInvoked);
    }

    [Fact]
    public void TryCreateWithPolicy_StrictCoordTrace_FailsClosedWithoutFallback()
    {
        var cachedInvoked = false;
        var reacquiredInvoked = false;

        var result = NavigationPoseSourceFactory.TryCreateWithPolicy(
            NavigationPoseSourcePolicy.StrictCoordTrace,
            tryTraceAnchor: () => new NavigationPoseSourceResolutionStepResult(null, "Trace anchor did not match current ReaderBridge coordinates."),
            tryCachedAnchor: () =>
            {
                cachedInvoked = true;
                return new NavigationPoseSourceResolutionStepResult(
                    new NavigationPoseSourceCreationResult(
                        new FakePolicyPoseSource(),
                        new NavigationPoseSample("0xCACHED", 4d, 5d, 6d)));
            },
            tryReacquiredAnchor: () =>
            {
                reacquiredInvoked = true;
                return new NavigationPoseSourceResolutionStepResult(
                    new NavigationPoseSourceCreationResult(
                        new FakePolicyPoseSource(),
                        new NavigationPoseSample("0xREACQUIRED", 7d, 8d, 9d)));
            },
            out var error);

        Assert.Null(result);
        Assert.Contains("coord trace", error, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("cached or reacquired anchors are not allowed", error, StringComparison.OrdinalIgnoreCase);
        Assert.False(cachedInvoked);
        Assert.False(reacquiredInvoked);
    }

    [Fact]
    public void TryCreateWithPolicy_AllowFallback_UsesCachedAnchorWhenTraceUnavailable()
    {
        var cachedResult = new NavigationPoseSourceCreationResult(
            new FakePolicyPoseSource(),
            new NavigationPoseSample("0xCACHED", 4d, 5d, 6d));
        var reacquiredInvoked = false;

        var result = NavigationPoseSourceFactory.TryCreateWithPolicy(
            NavigationPoseSourcePolicy.AllowFallback,
            tryTraceAnchor: () => new NavigationPoseSourceResolutionStepResult(null),
            tryCachedAnchor: () => new NavigationPoseSourceResolutionStepResult(cachedResult),
            tryReacquiredAnchor: () =>
            {
                reacquiredInvoked = true;
                return new NavigationPoseSourceResolutionStepResult(null);
            },
            out var error);

        Assert.Same(cachedResult, result);
        Assert.Null(error);
        Assert.False(reacquiredInvoked);
    }

    private sealed class FakePolicyPoseSource : INavigationPoseSource
    {
        public string AnchorSource => "fake-anchor";

        public string AddressHex => "0x1234";

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            sample = new NavigationPoseSample(AddressHex, 0d, 0d, 0d);
            error = null;
            return true;
        }
    }
}

public sealed class NavigationVectorSummaryTextFormatterTests
{
    [Fact]
    public void Format_IncludesUnavailableFacingSummaryDetails()
    {
        var destination = new WaypointDefinition(
            Id: "destination",
            Label: "Destination",
            Zone: null,
            X: 4d,
            Y: 7d,
            Z: 9d,
            ArrivalRadius: 6.5d,
            Pace: null);
        var current = new NavigationPoseSample("0x1234", 1d, 2d, 3d);
        var facing = NavigationMath.BuildUnavailableFacingSummary(
            status: "estimate-unavailable",
            message: "Actor-facing read did not return a usable yaw estimate for navigation alignment.");

        var summary = NavigationMath.BuildSummary(
            processId: 42,
            processName: "rift_x64",
            waypointFile: @"C:\RIFT MODDING\RiftReader\scripts\navigation\waypoints.json",
            destinationWaypoint: destination,
            currentSample: current,
            anchorSource: "player-current-cache",
            arrivalRadius: 6.5d,
            facing: facing);

        var text = NavigationVectorSummaryTextFormatter.Format(summary);

        Assert.Contains("Facing status:        estimate-unavailable", text, StringComparison.Ordinal);
        Assert.Contains("Facing source kind:   behavior-backed-memory-facing", text, StringComparison.Ordinal);
        Assert.Contains("Facing note:          Actor-facing read did not return a usable yaw estimate", text, StringComparison.Ordinal);
    }
}

public sealed class WaypointRoutePlannerTests
{
    [Fact]
    public void BuildPlan_CreatesOrderedSegmentsWithWaypointOverrides()
    {
        var movement = CreateMovement();
        var start = CreateWaypoint("point_a", 0d, 0d);
        var via = CreateWaypoint("point_b", 3d, 4d, arrivalRadius: 2.5d, pace: NavigationPace.Run);
        var destination = CreateWaypoint("point_c", 6d, 4d);

        var result = WaypointRoutePlanner.BuildPlan(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: movement,
            routeWaypoints: [start, via, destination]);

        Assert.Equal("success", result.Status);
        Assert.Empty(result.Issues);
        Assert.Equal(["point_a", "point_b", "point_c"], result.WaypointIds);
        Assert.Equal(2, result.SegmentCount);
        Assert.Equal(8d, result.TotalPlanarDistance, precision: 6);
        Assert.Collection(
            result.Segments,
            segment =>
            {
                Assert.Equal(1, segment.SegmentIndex);
                Assert.Equal("point_a", segment.StartWaypointId);
                Assert.Equal("point_b", segment.DestinationWaypointId);
                Assert.Equal(NavigationPace.Run, segment.Pace);
                Assert.Equal(2.5d, segment.ArrivalRadius);
                Assert.Equal(5d, segment.PlanarDistance, precision: 6);
            },
            segment =>
            {
                Assert.Equal(2, segment.SegmentIndex);
                Assert.Equal("point_b", segment.StartWaypointId);
                Assert.Equal("point_c", segment.DestinationWaypointId);
                Assert.Equal(NavigationPace.Keep, segment.Pace);
                Assert.Equal(1.5d, segment.ArrivalRadius);
                Assert.Equal(3d, segment.PlanarDistance, precision: 6);
            });
    }

    [Fact]
    public void BuildPlan_FailsClosedForRepeatedOrCrossZoneSegments()
    {
        var movement = CreateMovement();
        var start = CreateWaypoint("point_a", 0d, 0d, zone: "zone_a");
        var repeated = CreateWaypoint("point_a", 0d, 0d, zone: "zone_a");
        var destination = CreateWaypoint("point_b", 1d, 0d, zone: "zone_b");

        var result = WaypointRoutePlanner.BuildPlan(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: movement,
            routeWaypoints: [start, repeated, destination]);

        Assert.Equal("failure", result.Status);
        Assert.Contains(result.Issues, issue => issue.Contains("repeats waypoint 'point_a'", StringComparison.Ordinal));
        Assert.Contains(result.Issues, issue => issue.Contains("has no planar distance", StringComparison.Ordinal));
        Assert.Contains(result.Issues, issue => issue.Contains("crosses zones", StringComparison.Ordinal));
    }

    private static WaypointMovementSettings CreateMovement() =>
        new(
            ForwardKey: "w",
            RunKey: null,
            WalkKey: null,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: 250,
            PostPulseSampleDelayMilliseconds: 150,
            StartRadius: 1.5d,
            DefaultArrivalRadius: 1.5d,
            NoProgressWindowMilliseconds: 3000,
            MinimumProgressDistance: 0.05d,
            WrongWayToleranceDistance: 1d,
            MaxTravelSeconds: 30);

    private static WaypointDefinition CreateWaypoint(
        string id,
        double x,
        double z,
        double? arrivalRadius = null,
        string? pace = null,
        string? zone = null) =>
        new(
            Id: id,
            Label: id,
            Zone: zone,
            X: x,
            Y: 0d,
            Z: z,
            ArrivalRadius: arrivalRadius,
            Pace: pace);
}

public sealed class WaypointRouteNavigatorTests
{
    [Fact]
    public void Run_CompletesSegmentsAndUsesPreviousArrivalRadiusAsNextStartTolerance()
    {
        var routeWaypoints = new[]
        {
            CreateWaypoint("point_a", 0d),
            CreateWaypoint("point_b", 10d, arrivalRadius: 2.5d),
            CreateWaypoint("point_c", 20d)
        };
        var poseSource = new FakePoseSource(
            Success(0d),
            Success(8d),
            Success(8d),
            Success(18.8d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointRouteNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(startRadius: 1d),
            routeWaypoints: routeWaypoints,
            poseSource: poseSource,
            movementBackend: movementBackend);

        Assert.Equal("success", result.Status);
        Assert.Equal("arrived", result.StopReason);
        Assert.Equal(2, result.SegmentCount);
        Assert.Equal(2, result.CompletedSegmentCount);
        Assert.Null(result.FailedSegmentIndex);
        Assert.Equal(2, result.TotalPulseCount);
        Assert.Equal(1.2d, result.FinalPlanarDistance, precision: 6);
        Assert.Equal(["point_a", "point_b", "point_c"], result.WaypointIds);
        Assert.Collection(
            result.SegmentResults,
            segment =>
            {
                Assert.Equal("success", segment.Status);
                Assert.Equal("point_a", segment.StartWaypointId);
                Assert.Equal("point_b", segment.DestinationWaypointId);
                Assert.Equal(1d, segment.StartRadius);
                Assert.Equal(2.5d, segment.ArrivalRadius);
            },
            segment =>
            {
                Assert.Equal("success", segment.Status);
                Assert.Equal("point_b", segment.StartWaypointId);
                Assert.Equal("point_c", segment.DestinationWaypointId);
                Assert.Equal(2.5d, segment.StartRadius);
                Assert.Equal(1.5d, segment.ArrivalRadius);
            });
        Assert.Equal(2, movementBackend.Calls.Count);
        Assert.All(movementBackend.Calls, call => Assert.Equal("w", call.Key));
    }

    [Fact]
    public void Run_StopsAfterFirstFailedSegment()
    {
        var routeWaypoints = new[]
        {
            CreateWaypoint("point_a", 0d),
            CreateWaypoint("point_b", 10d),
            CreateWaypoint("point_c", 30d)
        };
        var poseSource = new FakePoseSource(
            Success(0d),
            Success(9d),
            Success(20d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointRouteNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            routeWaypoints: routeWaypoints,
            poseSource: poseSource,
            movementBackend: movementBackend);

        Assert.Equal("failure", result.Status);
        Assert.Equal("start-mismatch", result.StopReason);
        Assert.Equal(1, result.CompletedSegmentCount);
        Assert.Equal(2, result.FailedSegmentIndex);
        Assert.Equal(1, result.TotalPulseCount);
        Assert.Equal(10d, result.FinalPlanarDistance, precision: 6);
        Assert.Equal(2, result.SegmentResults.Count);
        Assert.Contains(result.Issues, issue => issue.Contains("Route segment 2 failed", StringComparison.Ordinal));
        Assert.Single(movementBackend.Calls);
        Assert.Equal(3, poseSource.ReadCalls);
    }

    [Fact]
    public void Run_FailsBeforeInputWhenPlanInvalid()
    {
        var routeWaypoints = new[]
        {
            CreateWaypoint("point_a", 0d),
            CreateWaypoint("point_a", 0d)
        };
        var poseSource = new FakePoseSource();
        var movementBackend = new FakeMovementBackend();

        var result = WaypointRouteNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            routeWaypoints: routeWaypoints,
            poseSource: poseSource,
            movementBackend: movementBackend);

        Assert.Equal("failure", result.Status);
        Assert.Equal("route-plan-invalid", result.StopReason);
        Assert.Null(result.FailedSegmentIndex);
        Assert.Equal(0, result.CompletedSegmentCount);
        Assert.Equal(0, result.TotalPulseCount);
        Assert.Empty(result.SegmentResults);
        Assert.Contains(result.Issues, issue => issue.Contains("repeats waypoint 'point_a'", StringComparison.Ordinal));
        Assert.Contains(result.Issues, issue => issue.Contains("has no planar distance", StringComparison.Ordinal));
        Assert.Equal(0, poseSource.ReadCalls);
        Assert.Empty(movementBackend.Calls);
    }

    [Fact]
    public void Run_AppliesTurnBeforeEachSegmentAndAttachesTurnResults()
    {
        var routeWaypoints = new[]
        {
            CreateWaypoint("point_a", 0d),
            CreateWaypoint("point_b", 10d, arrivalRadius: 2.5d),
            CreateWaypoint("point_c", 20d)
        };
        var poseSource = new FakePoseSource(
            Success(0d),
            Success(0d),
            Success(8d),
            Success(8d),
            Success(8d),
            Success(18.8d));
        var movementBackend = new FakeMovementBackend();
        var turnRequests = new List<NavigationRouteSegmentTurnRequest>();

        var result = WaypointRouteNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(startRadius: 1d),
            routeWaypoints: routeWaypoints,
            poseSource: poseSource,
            movementBackend: movementBackend,
            turnBeforeSegment: request =>
            {
                turnRequests.Add(request);
                return CreateTurnResult("noop", succeeded: true, request.CurrentSample, pulseCount: 0);
            });

        Assert.Equal("success", result.Status);
        Assert.Equal(2, result.CompletedSegmentCount);
        Assert.Equal(["point_b", "point_c"], turnRequests.Select(static request => request.DestinationWaypoint.Id).ToArray());
        Assert.All(result.SegmentResults, segment =>
        {
            Assert.NotNull(segment.TurnResult);
            Assert.Equal("noop", segment.TurnResult!.Status);
        });
        Assert.Equal(2, movementBackend.Calls.Count);
        Assert.Equal(6, poseSource.ReadCalls);
    }

    [Fact]
    public void Run_StopsBeforeForwardMovementWhenSegmentTurnFails()
    {
        var routeWaypoints = new[]
        {
            CreateWaypoint("point_a", 0d),
            CreateWaypoint("point_b", 10d),
            CreateWaypoint("point_c", 20d)
        };
        var poseSource = new FakePoseSource(Success(0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointRouteNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            routeWaypoints: routeWaypoints,
            poseSource: poseSource,
            movementBackend: movementBackend,
            turnBeforeSegment: request => CreateTurnResult(
                "unavailable",
                succeeded: false,
                request.CurrentSample,
                pulseCount: 0,
                reason: "Actor-facing truth was unavailable."));

        Assert.Equal("failure", result.Status);
        Assert.Equal("auto-turn-unavailable", result.StopReason);
        Assert.Equal(1, result.FailedSegmentIndex);
        Assert.Equal(0, result.CompletedSegmentCount);
        Assert.Equal(0, result.TotalPulseCount);
        Assert.Single(result.SegmentResults);
        Assert.Equal("auto-turn-unavailable", result.SegmentResults[0].StopReason);
        Assert.NotNull(result.SegmentResults[0].TurnResult);
        Assert.Contains(result.Issues, issue => issue.Contains("Route segment 1 failed", StringComparison.Ordinal));
        Assert.Empty(movementBackend.Calls);
        Assert.Equal(1, poseSource.ReadCalls);
    }

    private static WaypointMovementSettings CreateMovement(
        double startRadius = 2d,
        double defaultArrivalRadius = 1.5d) =>
        new(
            ForwardKey: "w",
            RunKey: null,
            WalkKey: null,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: 1,
            PostPulseSampleDelayMilliseconds: 0,
            StartRadius: startRadius,
            DefaultArrivalRadius: defaultArrivalRadius,
            NoProgressWindowMilliseconds: 1000,
            MinimumProgressDistance: 0.35d,
            WrongWayToleranceDistance: 1d,
            MaxTravelSeconds: 30);

    private static WaypointDefinition CreateWaypoint(
        string id,
        double x,
        double? arrivalRadius = null,
        string? pace = null) =>
        new(
            Id: id,
            Label: id,
            Zone: null,
            X: x,
            Y: 0d,
            Z: 0d,
            ArrivalRadius: arrivalRadius,
            Pace: pace);

    private static (bool Success, NavigationPoseSample Sample, string? Error) Success(double x) =>
        (true, new NavigationPoseSample("0x1234", x, 0d, 0d), null);

    private static NavigationTurnResult CreateTurnResult(
        string status,
        bool succeeded,
        NavigationPoseSample sample,
        int pulseCount,
        string? reason = null)
    {
        var position = new NavigationCoordinate(sample.X, sample.Y, sample.Z);
        var turnPlan = new NavigationTurnPlan(
            Status: succeeded ? "aligned" : "estimate-unavailable",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: "live-behavior-backed-lead",
            SelectedSourceAddress: sample.AddressHex,
            BasisPrimaryForwardOffset: "0xD4",
            DestinationBearingDegrees: 90d,
            CurrentYawDegrees: succeeded ? 90d : null,
            SignedBearingDeltaDegrees: succeeded ? 0d : null,
            AbsoluteBearingDeltaDegrees: succeeded ? 0d : null,
            SuggestedTurnDirection: succeeded ? "aligned" : null,
            AlignmentThresholdDegrees: 7.5d,
            WithinAlignmentThreshold: succeeded,
            Reason: reason);

        return new NavigationTurnResult(
            Status: status,
            Succeeded: succeeded,
            Attempted: pulseCount > 0,
            TurnKey: null,
            TurnDirection: succeeded ? "aligned" : null,
            ThresholdDegrees: 7.5d,
            PulseCount: pulseCount,
            WorseningPulseCount: 0,
            MaxWorseningPulses: 2,
            InitialPlan: turnPlan,
            FinalPlan: turnPlan,
            InitialPosition: position,
            FinalPosition: position,
            Samples: Array.Empty<NavigationTurnSample>(),
            Reason: reason,
            Events: Array.Empty<NavigationEvent>());
    }

    private sealed class FakePoseSource(
        params (bool Success, NavigationPoseSample Sample, string? Error)[] steps) : INavigationPoseSource
    {
        private readonly Queue<(bool Success, NavigationPoseSample Sample, string? Error)> _steps =
            new(steps);

        public string AnchorSource => "fake-anchor";

        public string AddressHex => "0x1234";

        public int ReadCalls { get; private set; }

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            ReadCalls++;
            if (_steps.Count == 0)
            {
                sample = new NavigationPoseSample(AddressHex, 0d, 0d, 0d);
                error = "No navigation pose samples remain.";
                return false;
            }

            var next = _steps.Dequeue();
            sample = next.Sample;
            error = next.Success ? null : next.Error ?? "Navigation pose read failed.";
            return next.Success;
        }
    }

    private sealed class FakeMovementBackend(
        IEnumerable<MovementCommandResult>? results = null) : IMovementBackend
    {
        private readonly Queue<MovementCommandResult> _results =
            new(results ?? Enumerable.Repeat(new MovementCommandResult(true, null), 32));

        public List<(string Key, int HoldMilliseconds)> Calls { get; } = [];

        public void PrepareForMovement()
        {
        }

        public MovementCommandResult PressKey(string key, int holdMilliseconds)
        {
            Calls.Add((key, holdMilliseconds));
            return _results.Count > 0
                ? _results.Dequeue()
                : new MovementCommandResult(true, null);
        }
    }
}

public sealed class NavigationRouteRunResultTextFormatterTests
{
    [Fact]
    public void Format_IncludesRouteAggregateAndSegmentSummaries()
    {
        var result = new NavigationRouteRunResult(
            Mode: "navigate-waypoint-route",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: "failure",
            StartWaypointId: "point_a",
            DestinationWaypointId: "point_c",
            WaypointIds: ["point_a", "point_b", "point_c"],
            SegmentCount: 2,
            CompletedSegmentCount: 1,
            FailedSegmentIndex: 2,
            StopReason: "start-mismatch",
            AnchorSource: "coord-trace-anchor",
            TotalPlanarDistance: 30d,
            FinalPlanarDistance: 10d,
            TotalPulseCount: 1,
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(20d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(30d, 0d, 0d),
            ElapsedMilliseconds: 150,
            SegmentResults:
            [
                CreateSegmentResult(
                    startWaypointId: "point_a",
                    destinationWaypointId: "point_b",
                    status: "success",
                    stopReason: "arrived",
                    pulseCount: 1,
                    finalPlanarDistance: 1d),
                CreateSegmentResult(
                    startWaypointId: "point_b",
                    destinationWaypointId: "point_c",
                    status: "failure",
                    stopReason: "start-mismatch",
                    pulseCount: 0,
                    finalPlanarDistance: 10d)
            ],
            Issues: ["Route segment 2 failed with stop reason 'start-mismatch'."]);

        var text = NavigationRouteRunResultTextFormatter.Format(result);

        Assert.Contains("Route:                point_a -> point_b -> point_c", text, StringComparison.Ordinal);
        Assert.Contains("Failed segment:       2", text, StringComparison.Ordinal);
        Assert.Contains("Total pulses:         1", text, StringComparison.Ordinal);
        Assert.Contains("Route segment 2 failed", text, StringComparison.Ordinal);
        Assert.Contains("2. point_b -> point_c status=failure reason=start-mismatch", text, StringComparison.Ordinal);
    }

    private static NavigationRunResult CreateSegmentResult(
        string startWaypointId,
        string destinationWaypointId,
        string status,
        string stopReason,
        int pulseCount,
        double finalPlanarDistance) =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: status,
            StartWaypointId: startWaypointId,
            DestinationWaypointId: destinationWaypointId,
            Pace: NavigationPace.Keep,
            AnchorSource: "coord-trace-anchor",
            StartRadius: 2d,
            ArrivalRadius: 1.5d,
            InitialPlanarDistance: 10d,
            FinalPlanarDistance: finalPlanarDistance,
            PulseCount: pulseCount,
            StopReason: stopReason,
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(10d, 0d, 0d),
            ElapsedMilliseconds: 75);
}

public sealed class WaypointNavigatorTests
{
    [Fact]
    public void Run_FailsWhenCurrentPositionIsOutsideStartRadius()
    {
        var poseSource = new FakePoseSource(
            Success(5d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("failure", result.Status);
        Assert.Equal("start-mismatch", result.StopReason);
        Assert.Equal(0, result.PulseCount);
        Assert.Empty(movementBackend.Calls);
    }

    [Fact]
    public void Run_PressesRunToggleBeforeForwardMovement()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(9.2d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(runKey: "r"),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Run,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("success", result.Status);
        Assert.Equal("arrived", result.StopReason);
        Assert.Equal(1, result.PulseCount);
        Assert.Collection(
            movementBackend.Calls,
            call =>
            {
                Assert.Equal("r", call.Key);
                Assert.Equal(120, call.HoldMilliseconds);
            },
            call =>
            {
                Assert.Equal("w", call.Key);
                Assert.Equal(1, call.HoldMilliseconds);
            });
    }

    [Fact]
    public void Run_ReachesDestinationWhenDistanceImproves()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(4.0d, 0d, 0d),
            Success(8.8d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("success", result.Status);
        Assert.Equal("arrived", result.StopReason);
        Assert.Equal(2, result.PulseCount);
        Assert.InRange(result.FinalPlanarDistance, 0d, 1.5d);
        Assert.NotNull(result.Events);
        Assert.Equal("initial-sample", result.Events![0].Type);
        Assert.Contains(result.Events!, navigationEvent => navigationEvent.Type == "progress-reset" && navigationEvent.PulseIndex == 1);
        var stopEvent = Assert.Single(result.Events!, navigationEvent => navigationEvent.Type == "stop");
        Assert.Equal("arrived", stopEvent.Status);
        Assert.Equal(2, stopEvent.PulseIndex);
    }

    [Fact]
    public void Run_StopsWhenProgressStalls()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(0.2d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(postPulseSampleDelayMilliseconds: 5, noProgressWindowMilliseconds: 1),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("failure", result.Status);
        Assert.Equal("no-progress", result.StopReason);
        Assert.Equal(1, result.PulseCount);
        Assert.NotNull(result.Events);
        var stopEvent = Assert.Single(result.Events!, navigationEvent => navigationEvent.Type == "stop");
        Assert.Equal("no-progress", stopEvent.Status);
        Assert.Equal(1, stopEvent.PulseIndex);
    }

    [Fact]
    public void Run_StopsWhenMovementGoesTheWrongWay()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(-1.0d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(postPulseSampleDelayMilliseconds: 0),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("failure", result.Status);
        Assert.Equal("moving-away", result.StopReason);
        Assert.Equal(1, result.PulseCount);
    }

    [Fact]
    public void Run_StopsWhenMovementInputFails()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d));
        var movementBackend = new FakeMovementBackend(
            new[]
            {
                new MovementCommandResult(false, "forward key failed")
            });

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("failure", result.Status);
        Assert.Equal("input-failed", result.StopReason);
        Assert.Equal(0, result.PulseCount);
        Assert.Single(movementBackend.Calls);
    }

    [Fact]
    public void Run_StopsWhenTelemetryIsLostAfterMovementStarts()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Failure("telemetry lost"));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        Assert.Equal("failure", result.Status);
        Assert.Equal("telemetry-lost", result.StopReason);
        Assert.Equal(1, result.PulseCount);
    }

    private static readonly WaypointDefinition StartWaypoint = new(
        Id: "start",
        Label: "Start",
        Zone: null,
        X: 0d,
        Y: 0d,
        Z: 0d,
        ArrivalRadius: 2d,
        Pace: null);

    private static readonly WaypointDefinition DestinationWaypoint = new(
        Id: "destination",
        Label: "Destination",
        Zone: null,
        X: 10d,
        Y: 0d,
        Z: 0d,
        ArrivalRadius: 1.5d,
        Pace: null);

    private static WaypointMovementSettings CreateMovement(
        string? runKey = null,
        string? walkKey = null,
        int forwardPulseMilliseconds = 1,
        int postPulseSampleDelayMilliseconds = 0,
        double startRadius = 2d,
        double defaultArrivalRadius = 1.5d,
        int noProgressWindowMilliseconds = 1000,
        double minimumProgressDistance = 0.35d,
        double wrongWayToleranceDistance = 0.75d,
        int maxTravelSeconds = 30) =>
        new(
            ForwardKey: "w",
            RunKey: runKey,
            WalkKey: walkKey,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: forwardPulseMilliseconds,
            PostPulseSampleDelayMilliseconds: postPulseSampleDelayMilliseconds,
            StartRadius: startRadius,
            DefaultArrivalRadius: defaultArrivalRadius,
            NoProgressWindowMilliseconds: noProgressWindowMilliseconds,
            MinimumProgressDistance: minimumProgressDistance,
            WrongWayToleranceDistance: wrongWayToleranceDistance,
            MaxTravelSeconds: maxTravelSeconds);

    private static (bool Success, NavigationPoseSample Sample, string? Error) Success(double x, double y, double z) =>
        (true, new NavigationPoseSample("0x1234", x, y, z), null);

    private static (bool Success, NavigationPoseSample Sample, string? Error) Failure(string error) =>
        (false, new NavigationPoseSample("0x1234", 0d, 0d, 0d), error);

    private sealed class FakePoseSource(
        params (bool Success, NavigationPoseSample Sample, string? Error)[] steps) : INavigationPoseSource
    {
        private readonly Queue<(bool Success, NavigationPoseSample Sample, string? Error)> _steps =
            new(steps);

        public string AnchorSource => "fake-anchor";

        public string AddressHex => "0x1234";

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            if (_steps.Count == 0)
            {
                sample = new NavigationPoseSample(AddressHex, 0d, 0d, 0d);
                error = "No navigation pose samples remain.";
                return false;
            }

            var next = _steps.Dequeue();
            sample = next.Sample;
            error = next.Success ? null : next.Error ?? "Navigation pose read failed.";
            return next.Success;
        }
    }

    private sealed class FakeMovementBackend(
        IEnumerable<MovementCommandResult>? results = null) : IMovementBackend
    {
        private readonly Queue<MovementCommandResult> _results =
            new(results ?? Enumerable.Repeat(new MovementCommandResult(true, null), 32));

        public List<(string Key, int HoldMilliseconds)> Calls { get; } = [];
        public int PrepareCalls { get; private set; }

        public void PrepareForMovement()
        {
            PrepareCalls++;
        }

        public MovementCommandResult PressKey(string key, int holdMilliseconds)
        {
            Calls.Add((key, holdMilliseconds));
            return _results.Count > 0
                ? _results.Dequeue()
                : new MovementCommandResult(true, null);
        }
    }
}

public sealed class NavigationAutoTurnerTests
{
    [Fact]
    public void Execute_ReturnsNoopWhenInitialPlanIsAlreadyAligned()
    {
        var movementBackend = new FakeMovementBackend();
        var poseSource = new FakePoseSource(Success(0d, 0d, 0d));
        var options = CreateAutoTurnOptions();
        var planner = new FakeTurnPlanFactory(
            CreateTurnPlan(deltaDegrees: 2d, turnDirection: "left", thresholdDegrees: 7.5d));

        var result = NavigationAutoTurner.Execute(
            currentSample: new NavigationPoseSample("0x1234", 0d, 0d, 0d),
            poseSource: poseSource,
            movementBackend: movementBackend,
            options: options,
            turnPlanFactory: planner.Build);

        Assert.True(result.Succeeded);
        Assert.False(result.Attempted);
        Assert.Equal("noop", result.Status);
        Assert.Empty(movementBackend.Calls);
        Assert.NotNull(result.Events);
        Assert.Equal("initial-plan", result.Events![0].Type);
        Assert.Equal("noop", result.Events![1].Type);
    }

    [Fact]
    public void Execute_CompletesAfterTurnPulseImprovesAlignment()
    {
        var movementBackend = new FakeMovementBackend();
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(0d, 0d, 0d));
        var options = CreateAutoTurnOptions();
        var planner = new FakeTurnPlanFactory(
            CreateTurnPlan(deltaDegrees: 25d, turnDirection: "left", thresholdDegrees: 7.5d),
            CreateTurnPlan(deltaDegrees: 3d, turnDirection: "aligned", thresholdDegrees: 7.5d));

        var result = NavigationAutoTurner.Execute(
            currentSample: new NavigationPoseSample("0x1234", 0d, 0d, 0d),
            poseSource: poseSource,
            movementBackend: movementBackend,
            options: options,
            turnPlanFactory: planner.Build);

        Assert.True(result.Succeeded);
        Assert.True(result.Attempted);
        Assert.Equal("complete", result.Status);
        Assert.Equal(1, result.PulseCount);
        Assert.NotNull(result.Events);
        Assert.Contains(result.Events!, navigationEvent => navigationEvent.Type == "pulse-sample" && navigationEvent.PulseIndex == 1);
        Assert.Equal("complete", result.Events![^1].Type);
        Assert.True(result.Events![^1].ElapsedMilliseconds >= 0);
        Assert.Collection(
            movementBackend.Calls,
            call =>
            {
                Assert.Equal("a", call.Key);
                Assert.Equal(75, call.HoldMilliseconds);
            });
    }

    [Fact]
    public void Execute_FailsClosedWhenAlignmentKeepsWorsening()
    {
        var movementBackend = new FakeMovementBackend();
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(0d, 0d, 0d),
            Success(0d, 0d, 0d));
        var options = CreateAutoTurnOptions(maxWorseningPulses: 2, worseningToleranceDegrees: 0.5d);
        var planner = new FakeTurnPlanFactory(
            CreateTurnPlan(deltaDegrees: 20d, turnDirection: "left", thresholdDegrees: 7.5d),
            CreateTurnPlan(deltaDegrees: 21d, turnDirection: "left", thresholdDegrees: 7.5d),
            CreateTurnPlan(deltaDegrees: 22d, turnDirection: "left", thresholdDegrees: 7.5d));

        var result = NavigationAutoTurner.Execute(
            currentSample: new NavigationPoseSample("0x1234", 0d, 0d, 0d),
            poseSource: poseSource,
            movementBackend: movementBackend,
            options: options,
            turnPlanFactory: planner.Build);

        Assert.False(result.Succeeded);
        Assert.True(result.Attempted);
        Assert.Equal("worsening", result.Status);
        Assert.Equal(2, result.PulseCount);
        Assert.Equal(2, result.WorseningPulseCount);
        Assert.Equal(2, movementBackend.Calls.Count);
        Assert.NotNull(result.Events);
        Assert.Equal("stop", result.Events![^1].Type);
        Assert.Equal("worsening", result.Events![^1].Status);
    }

    private static NavigationAutoTurnOptions CreateAutoTurnOptions(
        double withinDegrees = 7.5d,
        double worseningToleranceDegrees = 0.5d,
        int maxWorseningPulses = 2) =>
        new(
            Enabled: true,
            WithinDegrees: withinDegrees,
            TurnLeftKey: "a",
            TurnRightKey: "d",
            TurnPulseMilliseconds: 75,
            PostTurnSampleDelayMilliseconds: 0,
            SettleDelayMilliseconds: 0,
            MaxTurnPulses: 12,
            WorseningToleranceDegrees: worseningToleranceDegrees,
            MaxWorseningPulses: maxWorseningPulses);

    private static NavigationTurnPlan CreateTurnPlan(
        double deltaDegrees,
        string turnDirection,
        double thresholdDegrees) =>
        new(
            Status: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees
                ? "aligned"
                : "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: "live-behavior-backed-lead",
            SelectedSourceAddress: "0x1234",
            BasisPrimaryForwardOffset: "0xD4",
            DestinationBearingDegrees: 90d,
            CurrentYawDegrees: 45d,
            SignedBearingDeltaDegrees: turnDirection switch
            {
                "right" => -deltaDegrees,
                "aligned" => 0d,
                _ => deltaDegrees
            },
            AbsoluteBearingDeltaDegrees: deltaDegrees,
            SuggestedTurnDirection: turnDirection,
            AlignmentThresholdDegrees: thresholdDegrees,
            WithinAlignmentThreshold: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees,
            Reason: null);

    private sealed class FakeTurnPlanFactory(params NavigationTurnPlan[] plans)
    {
        private readonly Queue<NavigationTurnPlan> _plans = new(plans);

        public NavigationTurnPlan Build(NavigationPoseSample _)
        {
            if (_plans.Count == 0)
            {
                throw new InvalidOperationException("No navigation turn plans remain.");
            }

            return _plans.Dequeue();
        }
    }

    private static (bool Success, NavigationPoseSample Sample, string? Error) Success(double x, double y, double z) =>
        (true, new NavigationPoseSample("0x1234", x, y, z), null);

    private sealed class FakePoseSource(
        params (bool Success, NavigationPoseSample Sample, string? Error)[] steps) : INavigationPoseSource
    {
        private readonly Queue<(bool Success, NavigationPoseSample Sample, string? Error)> _steps =
            new(steps);

        public string AnchorSource => "fake-anchor";

        public string AddressHex => "0x1234";

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            if (_steps.Count == 0)
            {
                sample = new NavigationPoseSample(AddressHex, 0d, 0d, 0d);
                error = "No navigation pose samples remain.";
                return false;
            }

            var next = _steps.Dequeue();
            sample = next.Sample;
            error = next.Success ? null : next.Error ?? "Navigation pose read failed.";
            return next.Success;
        }
    }

    private sealed class FakeMovementBackend(
        IEnumerable<MovementCommandResult>? results = null) : IMovementBackend
    {
        private readonly Queue<MovementCommandResult> _results =
            new(results ?? Enumerable.Repeat(new MovementCommandResult(true, null), 32));

        public List<(string Key, int HoldMilliseconds)> Calls { get; } = [];

        public void PrepareForMovement()
        {
        }

        public MovementCommandResult PressKey(string key, int holdMilliseconds)
        {
            Calls.Add((key, holdMilliseconds));
            return _results.Count > 0
                ? _results.Dequeue()
                : new MovementCommandResult(true, null);
        }
    }
}

public sealed class NavigationRunResultTextFormatterTests
{
    [Fact]
    public void Format_DefaultOutputStaysCompact()
    {
        var result = CreateResult();

        var text = NavigationRunResultTextFormatter.Format(result);

        Assert.Contains("Turn event count:     1", text, StringComparison.Ordinal);
        Assert.Contains("Turn last event:      t=120ms auto-turn/stop [worsening] pulse=2 key=a delta=26.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn worsened for 2 consecutive pulses.", text, StringComparison.Ordinal);
        Assert.Contains("Event count:          1", text, StringComparison.Ordinal);
        Assert.Contains("Last event:           t=0ms navigation/stop [auto-turn-worsening] dist=10.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn failed before forward movement could start.", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Turn events:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Events:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_AnchorUnavailableShowsTopLevelStopWithoutTurnSection()
    {
        var result = BuildNavigationAnchorUnavailableResult();

        var text = NavigationRunResultTextFormatter.Format(result);

        Assert.Contains("Status:               failure", text, StringComparison.Ordinal);
        Assert.Contains("Stop reason:          anchor-unavailable", text, StringComparison.Ordinal);
        Assert.Contains("Anchor source:        none", text, StringComparison.Ordinal);
        Assert.Contains("Event count:          1", text, StringComparison.Ordinal);
        Assert.Contains("Last event:           t=0ms navigation/stop [anchor-unavailable] pos=0.00000, 0.00000, 0.00000 note=A validated coord-trace navigation anchor was unavailable for this run.", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Turn status:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Turn event count:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_AnchorUnavailableVerboseIncludesTopLevelTimeline()
    {
        var result = BuildNavigationAnchorUnavailableResult();

        var text = NavigationRunResultTextFormatter.Format(result, includeEventTimeline: true);

        Assert.Contains("Event count:          1", text, StringComparison.Ordinal);
        Assert.Contains("Last event:           t=0ms navigation/stop [anchor-unavailable] pos=0.00000, 0.00000, 0.00000 note=A validated coord-trace navigation anchor was unavailable for this run.", text, StringComparison.Ordinal);
        Assert.Contains("Events:", text, StringComparison.Ordinal);
        Assert.Contains("  - t=0ms navigation/stop [anchor-unavailable] pos=0.00000, 0.00000, 0.00000 note=A validated coord-trace navigation anchor was unavailable for this run.", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Turn events:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_IncludesNavigationAndTurnEventTimelinesWhenVerbose()
    {
        var result = CreateResult();

        var text = NavigationRunResultTextFormatter.Format(result, includeEventTimeline: true);

        Assert.Contains("Turn event count:     1", text, StringComparison.Ordinal);
        Assert.Contains("Turn last event:      t=120ms auto-turn/stop [worsening] pulse=2 key=a delta=26.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn worsened for 2 consecutive pulses.", text, StringComparison.Ordinal);
        Assert.Contains("Turn events:", text, StringComparison.Ordinal);
        Assert.Contains("  - t=120ms auto-turn/stop [worsening] pulse=2 key=a delta=26.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn worsened for 2 consecutive pulses.", text, StringComparison.Ordinal);
        Assert.Contains("Event count:          1", text, StringComparison.Ordinal);
        Assert.Contains("Last event:           t=0ms navigation/stop [auto-turn-worsening] dist=10.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn failed before forward movement could start.", text, StringComparison.Ordinal);
        Assert.Contains("Events:", text, StringComparison.Ordinal);
        Assert.Contains("  - t=0ms navigation/stop [auto-turn-worsening] dist=10.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn failed before forward movement could start.", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_SuccessWithTurnResultShowsBothCompactSummaries()
    {
        var result = CreateSuccessfulTurnResult();

        var text = NavigationRunResultTextFormatter.Format(result);

        Assert.Contains("Status:               success", text, StringComparison.Ordinal);
        Assert.Contains("Stop reason:          arrived", text, StringComparison.Ordinal);
        Assert.Contains("Turn status:          complete", text, StringComparison.Ordinal);
        Assert.Contains("Turn last event:      t=75ms auto-turn/complete [complete] pulse=1 key=a delta=3.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn reached the alignment threshold.", text, StringComparison.Ordinal);
        Assert.Contains("Event count:          3", text, StringComparison.Ordinal);
        Assert.Contains("Last event:           t=150ms navigation/stop [arrived] pulse=2 dist=1.20000 pos=8.80000, 0.00000, 0.00000 note=Destination waypoint reached within the arrival radius.", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Turn events:", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Events:", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_SuccessWithTurnResultVerboseIncludesBothEventTimelines()
    {
        var result = CreateSuccessfulTurnResult();

        var text = NavigationRunResultTextFormatter.Format(result, includeEventTimeline: true);

        Assert.Contains("Turn event count:     1", text, StringComparison.Ordinal);
        Assert.Contains("Turn last event:      t=75ms auto-turn/complete [complete] pulse=1 key=a delta=3.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn reached the alignment threshold.", text, StringComparison.Ordinal);
        Assert.Contains("Turn events:", text, StringComparison.Ordinal);
        Assert.Contains("  - t=75ms auto-turn/complete [complete] pulse=1 key=a delta=3.00000 pos=0.00000, 0.00000, 0.00000 note=Auto-turn reached the alignment threshold.", text, StringComparison.Ordinal);
        Assert.Contains("Event count:          3", text, StringComparison.Ordinal);
        Assert.Contains("Events:", text, StringComparison.Ordinal);
        Assert.Contains("  - t=80ms navigation/progress-reset [observed] pulse=1 dist=6.00000 pos=4.00000, 0.00000, 0.00000 note=Progress window reset after improving distance by 4.", text, StringComparison.Ordinal);
        Assert.Contains("  - t=150ms navigation/stop [arrived] pulse=2 dist=1.20000 pos=8.80000, 0.00000, 0.00000 note=Destination waypoint reached within the arrival radius.", text, StringComparison.Ordinal);
    }

    private static NavigationRunResult CreateResult() =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: "failure",
            StartWaypointId: "start",
            DestinationWaypointId: "destination",
            Pace: "keep",
            AnchorSource: "coord-trace-anchor",
            StartRadius: 2d,
            ArrivalRadius: 1.5d,
            InitialPlanarDistance: 10d,
            FinalPlanarDistance: 10d,
            PulseCount: 0,
            StopReason: "auto-turn-worsening",
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(10d, 0d, 0d),
            ElapsedMilliseconds: 0,
            TurnResult: new NavigationTurnResult(
                Status: "worsening",
                Succeeded: false,
                Attempted: true,
                TurnKey: "a",
                TurnDirection: "left",
                ThresholdDegrees: 7.5d,
                PulseCount: 2,
                WorseningPulseCount: 2,
                MaxWorseningPulses: 2,
                InitialPlan: CreateTurnPlan(deltaDegrees: 25d, turnDirection: "left", thresholdDegrees: 7.5d),
                FinalPlan: CreateTurnPlan(deltaDegrees: 26d, turnDirection: "left", thresholdDegrees: 7.5d),
                InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
                FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: "Auto-turn worsened for 2 consecutive pulses.",
                Events: new[]
                {
                    new NavigationEvent(
                        "auto-turn",
                        "stop",
                        120,
                        Status: "worsening",
                        PulseIndex: 2,
                        Key: "a",
                        Position: new NavigationCoordinate(0d, 0d, 0d),
                        AbsoluteBearingDeltaDegrees: 26d,
                        Detail: "Auto-turn worsened for 2 consecutive pulses.")
                }),
            Events: new[]
            {
                new NavigationEvent(
                    "navigation",
                    "stop",
                    0,
                    Status: "auto-turn-worsening",
                    Position: new NavigationCoordinate(0d, 0d, 0d),
                    PlanarDistance: 10d,
                    Detail: "Auto-turn failed before forward movement could start.")
            });

    private static NavigationRunResult CreateSuccessfulTurnResult() =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: "success",
            StartWaypointId: "start",
            DestinationWaypointId: "destination",
            Pace: "keep",
            AnchorSource: "coord-trace-anchor",
            StartRadius: 2d,
            ArrivalRadius: 1.5d,
            InitialPlanarDistance: 10d,
            FinalPlanarDistance: 1.2d,
            PulseCount: 2,
            StopReason: "arrived",
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(8.8d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(10d, 0d, 0d),
            ElapsedMilliseconds: 150,
            TurnResult: new NavigationTurnResult(
                Status: "complete",
                Succeeded: true,
                Attempted: true,
                TurnKey: "a",
                TurnDirection: "left",
                ThresholdDegrees: 7.5d,
                PulseCount: 1,
                WorseningPulseCount: 0,
                MaxWorseningPulses: 2,
                InitialPlan: CreateTurnPlan(deltaDegrees: 25d, turnDirection: "left", thresholdDegrees: 7.5d),
                FinalPlan: CreateTurnPlan(deltaDegrees: 3d, turnDirection: "aligned", thresholdDegrees: 7.5d),
                InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
                FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: null,
                Events: new[]
                {
                    new NavigationEvent(
                        "auto-turn",
                        "complete",
                        75,
                        Status: "complete",
                        PulseIndex: 1,
                        Key: "a",
                        Position: new NavigationCoordinate(0d, 0d, 0d),
                        AbsoluteBearingDeltaDegrees: 3d,
                        Detail: "Auto-turn reached the alignment threshold.")
                }),
            Events: new[]
            {
                new NavigationEvent(
                    "navigation",
                    "initial-sample",
                    0,
                    Status: "observed",
                    Position: new NavigationCoordinate(0d, 0d, 0d),
                    PlanarDistance: 10d,
                    Detail: "Captured the initial navigation pose sample."),
                new NavigationEvent(
                    "navigation",
                    "progress-reset",
                    80,
                    Status: "observed",
                    PulseIndex: 1,
                    Position: new NavigationCoordinate(4d, 0d, 0d),
                    PlanarDistance: 6d,
                    Detail: "Progress window reset after improving distance by 4."),
                new NavigationEvent(
                    "navigation",
                    "stop",
                    150,
                    Status: "arrived",
                    PulseIndex: 2,
                    Position: new NavigationCoordinate(8.8d, 0d, 0d),
                    PlanarDistance: 1.2d,
                    Detail: "Destination waypoint reached within the arrival radius.")
            });

    private static NavigationTurnPlan CreateTurnPlan(
        double deltaDegrees,
        string turnDirection,
        double thresholdDegrees) =>
        new(
            Status: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees
                ? "aligned"
                : "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: "live-behavior-backed-lead",
            SelectedSourceAddress: "0x1234",
            BasisPrimaryForwardOffset: "0xD4",
            DestinationBearingDegrees: 90d,
            CurrentYawDegrees: 45d,
            SignedBearingDeltaDegrees: turnDirection switch
            {
                "right" => -deltaDegrees,
                "aligned" => 0d,
                _ => deltaDegrees
            },
            AbsoluteBearingDeltaDegrees: deltaDegrees,
            SuggestedTurnDirection: turnDirection,
            AlignmentThresholdDegrees: thresholdDegrees,
            WithinAlignmentThreshold: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees,
            Reason: null);

    private static NavigationRunResult BuildNavigationAnchorUnavailableResult()
    {
        var programType = typeof(JsonOutput).Assembly.GetType("RiftReader.Reader.Program", throwOnError: true)!;
        var builder = programType.GetMethod(
            "BuildNavigationAnchorUnavailableResult",
            BindingFlags.NonPublic | BindingFlags.Static);

        Assert.NotNull(builder);

        var result = builder!.Invoke(
            null,
            new object?[]
            {
                new ProcessTarget(100, "rift_x64", "rift_x64.exe", null),
                "waypoints.json",
                new WaypointDefinition("start", "Start", null, 0d, 0d, 0d, 2d, null),
                new WaypointDefinition("destination", "Destination", null, 10d, 0d, 0d, 1.5d, null),
                "keep",
                1.5d,
                2d,
                "anchor-unavailable"
            });

        return Assert.IsType<NavigationRunResult>(result);
    }
}

public sealed class NavigationRunResultJsonOutputTests
{
    [Fact]
    public void Serialize_IncludesNavigationAndTurnEventPayloads()
    {
        var result = CreateResult();

        var json = JsonOutput.Serialize(result);

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        Assert.Equal("failure", root.GetProperty("Status").GetString());
        Assert.Equal("auto-turn-worsening", root.GetProperty("StopReason").GetString());

        var events = root.GetProperty("Events");
        Assert.Equal(JsonValueKind.Array, events.ValueKind);
        Assert.Single(events.EnumerateArray());
        var navigationEvent = events[0];
        Assert.Equal("navigation", navigationEvent.GetProperty("Stage").GetString());
        Assert.Equal("stop", navigationEvent.GetProperty("Type").GetString());
        Assert.Equal("auto-turn-worsening", navigationEvent.GetProperty("Status").GetString());
        Assert.Equal(10d, navigationEvent.GetProperty("PlanarDistance").GetDouble());
        Assert.Equal("Auto-turn failed before forward movement could start.", navigationEvent.GetProperty("Detail").GetString());

        var turnResult = root.GetProperty("TurnResult");
        Assert.Equal("worsening", turnResult.GetProperty("Status").GetString());
        var turnEvents = turnResult.GetProperty("Events");
        Assert.Single(turnEvents.EnumerateArray());
        var turnEvent = turnEvents[0];
        Assert.Equal("auto-turn", turnEvent.GetProperty("Stage").GetString());
        Assert.Equal("stop", turnEvent.GetProperty("Type").GetString());
        Assert.Equal("a", turnEvent.GetProperty("Key").GetString());
        Assert.Equal(26d, turnEvent.GetProperty("AbsoluteBearingDeltaDegrees").GetDouble());
        Assert.Equal("Auto-turn worsened for 2 consecutive pulses.", turnEvent.GetProperty("Detail").GetString());
    }

    [Fact]
    public void Serialize_AnchorUnavailableFailureIncludesTopLevelStopEvent()
    {
        var result = BuildNavigationAnchorUnavailableResult();

        var json = JsonOutput.Serialize(result);

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        Assert.Equal("failure", root.GetProperty("Status").GetString());
        Assert.Equal("anchor-unavailable", root.GetProperty("StopReason").GetString());
        Assert.Equal("none", root.GetProperty("AnchorSource").GetString());

        var events = root.GetProperty("Events");
        Assert.Single(events.EnumerateArray());
        var stopEvent = events[0];
        Assert.Equal("navigation", stopEvent.GetProperty("Stage").GetString());
        Assert.Equal("stop", stopEvent.GetProperty("Type").GetString());
        Assert.Equal("anchor-unavailable", stopEvent.GetProperty("Status").GetString());
        Assert.Equal("A validated coord-trace navigation anchor was unavailable for this run.", stopEvent.GetProperty("Detail").GetString());
        Assert.False(root.TryGetProperty("TurnResult", out _));
    }

    [Fact]
    public void Serialize_SuccessfulNavigationIncludesProgressResetAndArrivalEvents()
    {
        var poseSource = new FakePoseSource(
            Success(0d, 0d, 0d),
            Success(4.0d, 0d, 0d),
            Success(8.8d, 0d, 0d));
        var movementBackend = new FakeMovementBackend();

        var result = WaypointNavigator.Run(
            processId: 100,
            processName: "rift_x64",
            waypointFile: "waypoints.json",
            movement: CreateMovement(),
            startWaypoint: StartWaypoint,
            destinationWaypoint: DestinationWaypoint,
            poseSource: poseSource,
            movementBackend: movementBackend,
            pace: NavigationPace.Keep,
            arrivalRadius: 1.5d,
            maxTravelSeconds: 30);

        var json = JsonOutput.Serialize(result);

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        Assert.Equal("success", root.GetProperty("Status").GetString());
        Assert.Equal("arrived", root.GetProperty("StopReason").GetString());
        Assert.Equal(2, root.GetProperty("PulseCount").GetInt32());

        var events = root.GetProperty("Events").EnumerateArray().ToArray();
        Assert.Contains(events, navigationEvent =>
            navigationEvent.GetProperty("Type").GetString() == "progress-reset" &&
            navigationEvent.GetProperty("PulseIndex").GetInt32() == 1);
        Assert.Contains(events, navigationEvent =>
            navigationEvent.GetProperty("Type").GetString() == "stop" &&
            navigationEvent.GetProperty("Status").GetString() == "arrived" &&
            navigationEvent.GetProperty("PulseIndex").GetInt32() == 2);
    }

    [Fact]
    public void Serialize_SuccessWithTurnResultIncludesBothEventStreams()
    {
        var result = CreateSuccessfulTurnResult();

        var json = JsonOutput.Serialize(result);

        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        Assert.Equal("success", root.GetProperty("Status").GetString());
        Assert.Equal("arrived", root.GetProperty("StopReason").GetString());

        var events = root.GetProperty("Events").EnumerateArray().ToArray();
        Assert.Equal(3, events.Length);
        Assert.Equal("progress-reset", events[1].GetProperty("Type").GetString());
        Assert.Equal("arrived", events[2].GetProperty("Status").GetString());

        var turnResult = root.GetProperty("TurnResult");
        Assert.Equal("complete", turnResult.GetProperty("Status").GetString());
        var turnEvents = turnResult.GetProperty("Events").EnumerateArray().ToArray();
        Assert.Single(turnEvents);
        Assert.Equal("complete", turnEvents[0].GetProperty("Type").GetString());
        Assert.Equal(3d, turnEvents[0].GetProperty("AbsoluteBearingDeltaDegrees").GetDouble());
    }

    private static NavigationRunResult CreateResult() =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: "failure",
            StartWaypointId: "start",
            DestinationWaypointId: "destination",
            Pace: "keep",
            AnchorSource: "coord-trace-anchor",
            StartRadius: 2d,
            ArrivalRadius: 1.5d,
            InitialPlanarDistance: 10d,
            FinalPlanarDistance: 10d,
            PulseCount: 0,
            StopReason: "auto-turn-worsening",
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(10d, 0d, 0d),
            ElapsedMilliseconds: 0,
            TurnResult: new NavigationTurnResult(
                Status: "worsening",
                Succeeded: false,
                Attempted: true,
                TurnKey: "a",
                TurnDirection: "left",
                ThresholdDegrees: 7.5d,
                PulseCount: 2,
                WorseningPulseCount: 2,
                MaxWorseningPulses: 2,
                InitialPlan: CreateTurnPlan(deltaDegrees: 25d, turnDirection: "left", thresholdDegrees: 7.5d),
                FinalPlan: CreateTurnPlan(deltaDegrees: 26d, turnDirection: "left", thresholdDegrees: 7.5d),
                InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
                FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: "Auto-turn worsened for 2 consecutive pulses.",
                Events: new[]
                {
                    new NavigationEvent(
                        "auto-turn",
                        "stop",
                        120,
                        Status: "worsening",
                        PulseIndex: 2,
                        Key: "a",
                        Position: new NavigationCoordinate(0d, 0d, 0d),
                        AbsoluteBearingDeltaDegrees: 26d,
                        Detail: "Auto-turn worsened for 2 consecutive pulses.")
                }),
            Events: new[]
            {
                new NavigationEvent(
                    "navigation",
                    "stop",
                    0,
                    Status: "auto-turn-worsening",
                    Position: new NavigationCoordinate(0d, 0d, 0d),
                    PlanarDistance: 10d,
                    Detail: "Auto-turn failed before forward movement could start.")
            });

    private static NavigationRunResult CreateSuccessfulTurnResult() =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: 100,
            ProcessName: "rift_x64",
            WaypointFile: "waypoints.json",
            Status: "success",
            StartWaypointId: "start",
            DestinationWaypointId: "destination",
            Pace: "keep",
            AnchorSource: "coord-trace-anchor",
            StartRadius: 2d,
            ArrivalRadius: 1.5d,
            InitialPlanarDistance: 10d,
            FinalPlanarDistance: 1.2d,
            PulseCount: 2,
            StopReason: "arrived",
            InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
            FinalPosition: new NavigationCoordinate(8.8d, 0d, 0d),
            DestinationPosition: new NavigationCoordinate(10d, 0d, 0d),
            ElapsedMilliseconds: 150,
            TurnResult: new NavigationTurnResult(
                Status: "complete",
                Succeeded: true,
                Attempted: true,
                TurnKey: "a",
                TurnDirection: "left",
                ThresholdDegrees: 7.5d,
                PulseCount: 1,
                WorseningPulseCount: 0,
                MaxWorseningPulses: 2,
                InitialPlan: CreateTurnPlan(deltaDegrees: 25d, turnDirection: "left", thresholdDegrees: 7.5d),
                FinalPlan: CreateTurnPlan(deltaDegrees: 3d, turnDirection: "aligned", thresholdDegrees: 7.5d),
                InitialPosition: new NavigationCoordinate(0d, 0d, 0d),
                FinalPosition: new NavigationCoordinate(0d, 0d, 0d),
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: null,
                Events: new[]
                {
                    new NavigationEvent(
                        "auto-turn",
                        "complete",
                        75,
                        Status: "complete",
                        PulseIndex: 1,
                        Key: "a",
                        Position: new NavigationCoordinate(0d, 0d, 0d),
                        AbsoluteBearingDeltaDegrees: 3d,
                        Detail: "Auto-turn reached the alignment threshold.")
                }),
            Events: new[]
            {
                new NavigationEvent(
                    "navigation",
                    "initial-sample",
                    0,
                    Status: "observed",
                    Position: new NavigationCoordinate(0d, 0d, 0d),
                    PlanarDistance: 10d,
                    Detail: "Captured the initial navigation pose sample."),
                new NavigationEvent(
                    "navigation",
                    "progress-reset",
                    80,
                    Status: "observed",
                    PulseIndex: 1,
                    Position: new NavigationCoordinate(4d, 0d, 0d),
                    PlanarDistance: 6d,
                    Detail: "Progress window reset after improving distance by 4."),
                new NavigationEvent(
                    "navigation",
                    "stop",
                    150,
                    Status: "arrived",
                    PulseIndex: 2,
                    Position: new NavigationCoordinate(8.8d, 0d, 0d),
                    PlanarDistance: 1.2d,
                    Detail: "Destination waypoint reached within the arrival radius.")
            });

    private static NavigationTurnPlan CreateTurnPlan(
        double deltaDegrees,
        string turnDirection,
        double thresholdDegrees) =>
        new(
            Status: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees
                ? "aligned"
                : "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: "live-behavior-backed-lead",
            SelectedSourceAddress: "0x1234",
            BasisPrimaryForwardOffset: "0xD4",
            DestinationBearingDegrees: 90d,
            CurrentYawDegrees: 45d,
            SignedBearingDeltaDegrees: turnDirection switch
            {
                "right" => -deltaDegrees,
                "aligned" => 0d,
                _ => deltaDegrees
            },
            AbsoluteBearingDeltaDegrees: deltaDegrees,
            SuggestedTurnDirection: turnDirection,
            AlignmentThresholdDegrees: thresholdDegrees,
            WithinAlignmentThreshold: string.Equals(turnDirection, "aligned", StringComparison.OrdinalIgnoreCase) || deltaDegrees <= thresholdDegrees,
            Reason: null);

    private static WaypointMovementSettings CreateMovement(
        string? runKey = null,
        string? walkKey = null,
        int forwardPulseMilliseconds = 1,
        int postPulseSampleDelayMilliseconds = 0,
        double startRadius = 2d,
        double defaultArrivalRadius = 1.5d,
        int noProgressWindowMilliseconds = 1000,
        double minimumProgressDistance = 0.35d,
        double wrongWayToleranceDistance = 0.75d,
        int maxTravelSeconds = 30) =>
        new(
            ForwardKey: "w",
            RunKey: runKey,
            WalkKey: walkKey,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: forwardPulseMilliseconds,
            PostPulseSampleDelayMilliseconds: postPulseSampleDelayMilliseconds,
            StartRadius: startRadius,
            DefaultArrivalRadius: defaultArrivalRadius,
            NoProgressWindowMilliseconds: noProgressWindowMilliseconds,
            MinimumProgressDistance: minimumProgressDistance,
            WrongWayToleranceDistance: wrongWayToleranceDistance,
            MaxTravelSeconds: maxTravelSeconds);

    private static readonly WaypointDefinition StartWaypoint = new(
        Id: "start",
        Label: "Start",
        Zone: null,
        X: 0d,
        Y: 0d,
        Z: 0d,
        ArrivalRadius: 2d,
        Pace: null);

    private static readonly WaypointDefinition DestinationWaypoint = new(
        Id: "destination",
        Label: "Destination",
        Zone: null,
        X: 10d,
        Y: 0d,
        Z: 0d,
        ArrivalRadius: 1.5d,
        Pace: null);

    private static (bool Success, NavigationPoseSample Sample, string? Error) Success(double x, double y, double z) =>
        (true, new NavigationPoseSample("0x1234", x, y, z), null);

    private static NavigationRunResult BuildNavigationAnchorUnavailableResult()
    {
        var programType = typeof(JsonOutput).Assembly.GetType("RiftReader.Reader.Program", throwOnError: true)!;
        var builder = programType.GetMethod(
            "BuildNavigationAnchorUnavailableResult",
            BindingFlags.NonPublic | BindingFlags.Static);

        Assert.NotNull(builder);

        var target = new ProcessTarget(100, "rift_x64", "rift_x64.exe", null);
        var startWaypoint = new WaypointDefinition(
            Id: "start",
            Label: "Start",
            Zone: null,
            X: 0d,
            Y: 0d,
            Z: 0d,
            ArrivalRadius: 2d,
            Pace: null);
        var destinationWaypoint = new WaypointDefinition(
            Id: "destination",
            Label: "Destination",
            Zone: null,
            X: 10d,
            Y: 0d,
            Z: 0d,
            ArrivalRadius: 1.5d,
            Pace: null);

        var result = builder!.Invoke(
            null,
            new object?[]
            {
                target,
                "waypoints.json",
                startWaypoint,
                destinationWaypoint,
                "keep",
                1.5d,
                2d,
                "anchor-unavailable"
            });

        return Assert.IsType<NavigationRunResult>(result);
    }

    private sealed class FakePoseSource(
        params (bool Success, NavigationPoseSample Sample, string? Error)[] steps) : INavigationPoseSource
    {
        private readonly Queue<(bool Success, NavigationPoseSample Sample, string? Error)> _steps =
            new(steps);

        public string AnchorSource => "fake-anchor";

        public string AddressHex => "0x1234";

        public bool TryReadCurrent(out NavigationPoseSample sample, out string? error)
        {
            if (_steps.Count == 0)
            {
                sample = new NavigationPoseSample(AddressHex, 0d, 0d, 0d);
                error = "No navigation pose samples remain.";
                return false;
            }

            var next = _steps.Dequeue();
            sample = next.Sample;
            error = next.Success ? null : next.Error ?? "Navigation pose read failed.";
            return next.Success;
        }
    }

    private sealed class FakeMovementBackend(
        IEnumerable<MovementCommandResult>? results = null) : IMovementBackend
    {
        private readonly Queue<MovementCommandResult> _results =
            new(results ?? Enumerable.Repeat(new MovementCommandResult(true, null), 32));

        public void PrepareForMovement()
        {
        }

        public MovementCommandResult PressKey(string key, int holdMilliseconds) =>
            _results.Count > 0
                ? _results.Dequeue()
                : new MovementCommandResult(true, null);
    }
}
