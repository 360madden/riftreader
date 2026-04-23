using RiftReader.Reader.Navigation;
using RiftReader.Reader.Models;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;

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
        Assert.Equal("left", facing.SuggestedTurnDirection);
        Assert.Null(facing.Reason);
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
                Vector: new ValidatorCoordinateSnapshot(1d, 0d, 0d),
                YawRadians: null,
                YawDegrees: null,
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

        Assert.Equal("estimate-unavailable", facing.Status);
        Assert.Equal("behavior-backed-memory-facing", facing.SourceKind);
        Assert.Null(facing.AbsoluteBearingDeltaDegrees);
        Assert.Null(facing.SuggestedTurnDirection);
        Assert.Contains("usable yaw estimate", facing.Reason, StringComparison.OrdinalIgnoreCase);
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
