using System.Diagnostics;

namespace RiftReader.Reader.Navigation;

public static class WaypointNavigator
{
    private const int PaceToggleHoldMilliseconds = 120;

    public static NavigationRunResult Run(
        int processId,
        string processName,
        string waypointFile,
        WaypointMovementSettings movement,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        INavigationPoseSource poseSource,
        IMovementBackend movementBackend,
        string pace,
        double arrivalRadius,
        int maxTravelSeconds)
    {
        ArgumentNullException.ThrowIfNull(movement);
        ArgumentNullException.ThrowIfNull(startWaypoint);
        ArgumentNullException.ThrowIfNull(destinationWaypoint);
        ArgumentNullException.ThrowIfNull(poseSource);
        ArgumentNullException.ThrowIfNull(movementBackend);

        if (!poseSource.TryReadCurrent(out var current, out _))
        {
            return BuildFailure(
                processId,
                processName,
                waypointFile,
                startWaypoint,
                destinationWaypoint,
                pace,
                poseSource.AnchorSource,
                movement.StartRadius,
                arrivalRadius,
                pulseCount: 0,
                stopReason: "telemetry-lost",
                initialPosition: startWaypoint.Coordinate,
                finalPosition: startWaypoint.Coordinate,
                elapsedMilliseconds: 0);
        }

        var initialPosition = new NavigationCoordinate(current.X, current.Y, current.Z);
        var startDeltaX = startWaypoint.X - current.X;
        var startDeltaZ = startWaypoint.Z - current.Z;
        var startPlanarDistance = NavigationMath.ComputePlanarDistance(startDeltaX, startDeltaZ);

        var initialDeltaX = destinationWaypoint.X - current.X;
        var initialDeltaZ = destinationWaypoint.Z - current.Z;
        var initialPlanarDistance = NavigationMath.ComputePlanarDistance(initialDeltaX, initialDeltaZ);

        if (startPlanarDistance > movement.StartRadius)
        {
            return BuildFailure(
                processId,
                processName,
                waypointFile,
                startWaypoint,
                destinationWaypoint,
                pace,
                poseSource.AnchorSource,
                movement.StartRadius,
                arrivalRadius,
                pulseCount: 0,
                stopReason: "start-mismatch",
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0,
                initialPlanarDistance: initialPlanarDistance,
                finalPlanarDistance: initialPlanarDistance);
        }

        if (initialPlanarDistance <= arrivalRadius)
        {
            return BuildSuccess(
                processId,
                processName,
                waypointFile,
                startWaypoint,
                destinationWaypoint,
                pace,
                poseSource.AnchorSource,
                movement.StartRadius,
                arrivalRadius,
                initialPlanarDistance,
                initialPlanarDistance,
                pulseCount: 0,
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0);
        }

        var paceKey = ResolvePaceKey(movement, pace);
        if (paceKey is false)
        {
            return BuildFailure(
                processId,
                processName,
                waypointFile,
                startWaypoint,
                destinationWaypoint,
                pace,
                poseSource.AnchorSource,
                movement.StartRadius,
                arrivalRadius,
                pulseCount: 0,
                stopReason: "input-failed",
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0,
                initialPlanarDistance: initialPlanarDistance,
                finalPlanarDistance: initialPlanarDistance);
        }

        if (paceKey is string toggleKey)
        {
            var paceCommand = movementBackend.PressKey(toggleKey, PaceToggleHoldMilliseconds);
            if (!paceCommand.IsSuccess)
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount: 0,
                    stopReason: "input-failed",
                    initialPosition: initialPosition,
                    finalPosition: initialPosition,
                    elapsedMilliseconds: 0,
                    initialPlanarDistance: initialPlanarDistance,
                    finalPlanarDistance: initialPlanarDistance);
            }
        }

        var stopwatch = Stopwatch.StartNew();
        var pulseCount = 0;
        var currentPlanarDistance = initialPlanarDistance;
        var lastWindowResetAtMilliseconds = 0L;
        var lastWindowResetDistance = initialPlanarDistance;
        var latestPosition = initialPosition;

        while (true)
        {
            if (stopwatch.ElapsedMilliseconds > (maxTravelSeconds * 1000L))
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount,
                    "timeout",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance);
            }

            var pulseCommand = movementBackend.PressKey(movement.ForwardKey, movement.ForwardPulseMilliseconds);
            if (!pulseCommand.IsSuccess)
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount,
                    "input-failed",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance);
            }

            pulseCount++;

            if (movement.PostPulseSampleDelayMilliseconds > 0)
            {
                Thread.Sleep(movement.PostPulseSampleDelayMilliseconds);
            }

            if (!poseSource.TryReadCurrent(out current, out _))
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount,
                    "telemetry-lost",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance);
            }

            latestPosition = new NavigationCoordinate(current.X, current.Y, current.Z);
            var deltaX = destinationWaypoint.X - current.X;
            var deltaZ = destinationWaypoint.Z - current.Z;
            currentPlanarDistance = NavigationMath.ComputePlanarDistance(deltaX, deltaZ);

            if (currentPlanarDistance <= arrivalRadius)
            {
                return BuildSuccess(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    pulseCount,
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds);
            }

            var windowDistanceIncrease = currentPlanarDistance - lastWindowResetDistance;
            if (windowDistanceIncrease > movement.WrongWayToleranceDistance)
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount,
                    "moving-away",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance);
            }

            var progress = lastWindowResetDistance - currentPlanarDistance;
            if (progress >= movement.MinimumProgressDistance)
            {
                lastWindowResetDistance = currentPlanarDistance;
                lastWindowResetAtMilliseconds = stopwatch.ElapsedMilliseconds;
                continue;
            }

            if ((stopwatch.ElapsedMilliseconds - lastWindowResetAtMilliseconds) >= movement.NoProgressWindowMilliseconds)
            {
                return BuildFailure(
                    processId,
                    processName,
                    waypointFile,
                    startWaypoint,
                    destinationWaypoint,
                    pace,
                    poseSource.AnchorSource,
                    movement.StartRadius,
                    arrivalRadius,
                    pulseCount,
                    "no-progress",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance);
            }
        }
    }

    private static object? ResolvePaceKey(WaypointMovementSettings movement, string pace)
    {
        if (string.Equals(pace, NavigationPace.Keep, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        if (string.Equals(pace, NavigationPace.Run, StringComparison.OrdinalIgnoreCase))
        {
            return string.IsNullOrWhiteSpace(movement.RunKey)
                ? false
                : movement.RunKey;
        }

        if (string.Equals(pace, NavigationPace.Walk, StringComparison.OrdinalIgnoreCase))
        {
            return string.IsNullOrWhiteSpace(movement.WalkKey)
                ? false
                : movement.WalkKey;
        }

        return false;
    }

    private static NavigationRunResult BuildSuccess(
        int processId,
        string processName,
        string waypointFile,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        string pace,
        string anchorSource,
        double startRadius,
        double arrivalRadius,
        double initialPlanarDistance,
        double finalPlanarDistance,
        int pulseCount,
        NavigationCoordinate initialPosition,
        NavigationCoordinate finalPosition,
        long elapsedMilliseconds) =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: processId,
            ProcessName: processName,
            WaypointFile: waypointFile,
            Status: "success",
            StartWaypointId: startWaypoint.Id,
            DestinationWaypointId: destinationWaypoint.Id,
            Pace: pace,
            AnchorSource: anchorSource,
            StartRadius: startRadius,
            ArrivalRadius: arrivalRadius,
            InitialPlanarDistance: initialPlanarDistance,
            FinalPlanarDistance: finalPlanarDistance,
            PulseCount: pulseCount,
            StopReason: "arrived",
            InitialPosition: initialPosition,
            FinalPosition: finalPosition,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: elapsedMilliseconds);

    private static NavigationRunResult BuildFailure(
        int processId,
        string processName,
        string waypointFile,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        string pace,
        string anchorSource,
        double startRadius,
        double arrivalRadius,
        int pulseCount,
        string stopReason,
        NavigationCoordinate initialPosition,
        NavigationCoordinate finalPosition,
        long elapsedMilliseconds,
        double? initialPlanarDistance = null,
        double? finalPlanarDistance = null) =>
        new(
            Mode: "navigate-waypoints",
            ProcessId: processId,
            ProcessName: processName,
            WaypointFile: waypointFile,
            Status: "failure",
            StartWaypointId: startWaypoint.Id,
            DestinationWaypointId: destinationWaypoint.Id,
            Pace: pace,
            AnchorSource: anchorSource,
            StartRadius: startRadius,
            ArrivalRadius: arrivalRadius,
            InitialPlanarDistance: initialPlanarDistance ?? 0d,
            FinalPlanarDistance: finalPlanarDistance ?? 0d,
            PulseCount: pulseCount,
            StopReason: stopReason,
            InitialPosition: initialPosition,
            FinalPosition: finalPosition,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: elapsedMilliseconds);
}
