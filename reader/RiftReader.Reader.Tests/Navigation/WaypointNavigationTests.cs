using RiftReader.Reader.Navigation;

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
