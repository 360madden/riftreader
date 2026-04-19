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
        INavigationFacingSource? facingSource,
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
                turnPulseCount: 0,
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
        var initialFacing = TryReadFacingSummary(facingSource, initialDeltaX, initialDeltaZ, out _);

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
                turnPulseCount: 0,
                stopReason: "start-mismatch",
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0,
                initialPlanarDistance: initialPlanarDistance,
                finalPlanarDistance: initialPlanarDistance,
                initialFacing: initialFacing,
                finalFacing: initialFacing);
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
                turnPulseCount: 0,
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0,
                initialFacing: initialFacing,
                finalFacing: initialFacing);
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
                turnPulseCount: 0,
                stopReason: "input-failed",
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                elapsedMilliseconds: 0,
                initialPlanarDistance: initialPlanarDistance,
                finalPlanarDistance: initialPlanarDistance,
                initialFacing: initialFacing,
                finalFacing: initialFacing);
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
                    turnPulseCount: 0,
                    stopReason: "input-failed",
                    initialPosition: initialPosition,
                    finalPosition: initialPosition,
                    elapsedMilliseconds: 0,
                    initialPlanarDistance: initialPlanarDistance,
                    finalPlanarDistance: initialPlanarDistance,
                    initialFacing: initialFacing,
                    finalFacing: initialFacing);
            }
        }

        var stopwatch = Stopwatch.StartNew();
        var pulseCount = 0;
        var turnPulseCount = 0;
        var currentPlanarDistance = initialPlanarDistance;
        var lastWindowResetAtMilliseconds = 0L;
        var lastWindowResetDistance = initialPlanarDistance;
        var latestPosition = initialPosition;
        var latestFacing = initialFacing;

        while (true)
        {
            if (stopwatch.ElapsedMilliseconds > (maxTravelSeconds * 1000L))
            {
                latestFacing ??= TryReadFacingSummary(facingSource, destinationWaypoint.X - current.X, destinationWaypoint.Z - current.Z, out _);
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
                    turnPulseCount,
                    "timeout",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    initialFacing,
                    latestFacing);
            }

            if (movement.HasTurnKeys)
            {
                var deltaX = destinationWaypoint.X - current.X;
                var deltaZ = destinationWaypoint.Z - current.Z;
                var alignment = TryAlignFacing(
                    movement,
                    movementBackend,
                    facingSource,
                    deltaX,
                    deltaZ);
                turnPulseCount += alignment.TurnPulseCount;
                latestFacing = alignment.Facing;

                if (!alignment.IsSuccess)
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
                        turnPulseCount,
                        alignment.StopReason,
                        initialPosition,
                        latestPosition,
                        stopwatch.ElapsedMilliseconds,
                        initialPlanarDistance,
                        currentPlanarDistance,
                        initialFacing,
                        latestFacing);
                }
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
                    turnPulseCount,
                    "input-failed",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    initialFacing,
                    latestFacing);
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
                    turnPulseCount,
                    "telemetry-lost",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    initialFacing,
                    latestFacing);
            }

            latestPosition = new NavigationCoordinate(current.X, current.Y, current.Z);
            var postMoveDeltaX = destinationWaypoint.X - current.X;
            var postMoveDeltaZ = destinationWaypoint.Z - current.Z;
            currentPlanarDistance = NavigationMath.ComputePlanarDistance(postMoveDeltaX, postMoveDeltaZ);
            latestFacing = TryReadFacingSummary(facingSource, postMoveDeltaX, postMoveDeltaZ, out _) ?? latestFacing;

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
                    turnPulseCount,
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialFacing,
                    latestFacing);
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
                    turnPulseCount,
                    "moving-away",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    initialFacing,
                    latestFacing);
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
                    turnPulseCount,
                    "no-progress",
                    initialPosition,
                    latestPosition,
                    stopwatch.ElapsedMilliseconds,
                    initialPlanarDistance,
                    currentPlanarDistance,
                    initialFacing,
                    latestFacing);
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

    private static NavigationFacingSummary? TryReadFacingSummary(
        INavigationFacingSource? facingSource,
        double targetDeltaX,
        double targetDeltaZ,
        out string? error)
    {
        error = null;
        if (facingSource is null)
        {
            return null;
        }

        if (!facingSource.TryReadCurrent(out var sample, out error))
        {
            return null;
        }

        return NavigationMath.BuildFacingSummary(sample, targetDeltaX, targetDeltaZ);
    }

    private static FacingAlignmentResult TryAlignFacing(
        WaypointMovementSettings movement,
        IMovementBackend movementBackend,
        INavigationFacingSource? facingSource,
        double targetDeltaX,
        double targetDeltaZ)
    {
        if (!movement.HasTurnKeys)
        {
            return FacingAlignmentResult.Success(null, 0);
        }

        if (facingSource is null)
        {
            return FacingAlignmentResult.Fail("facing-unavailable", null, 0);
        }

        var turnPulses = 0;
        NavigationFacingSummary? latestFacing = null;

        for (var attempt = 0; attempt <= movement.MaxTurnPulsesPerCycle; attempt++)
        {
            latestFacing = TryReadFacingSummary(facingSource, targetDeltaX, targetDeltaZ, out _);
            if (latestFacing is null)
            {
                return FacingAlignmentResult.Fail("facing-unavailable", null, turnPulses);
            }

            if (latestFacing.CoordValidated == false || !latestFacing.IntegrityPass)
            {
                return FacingAlignmentResult.Fail("facing-unavailable", latestFacing, turnPulses);
            }

            if (Math.Abs(latestFacing.SignedTurnErrorDegrees) <= movement.TurnAlignmentToleranceDegrees)
            {
                return FacingAlignmentResult.Success(latestFacing, turnPulses);
            }

            if (attempt >= movement.MaxTurnPulsesPerCycle)
            {
                break;
            }

            var turnKey = latestFacing.SignedTurnErrorDegrees >= 0d
                ? movement.TurnLeftKey
                : movement.TurnRightKey;
            if (string.IsNullOrWhiteSpace(turnKey))
            {
                return FacingAlignmentResult.Fail("facing-unavailable", latestFacing, turnPulses);
            }

            var turnCommand = movementBackend.PressKey(turnKey, movement.TurnPulseMilliseconds);
            if (!turnCommand.IsSuccess)
            {
                return FacingAlignmentResult.Fail("turn-input-failed", latestFacing, turnPulses);
            }

            turnPulses++;

            if (movement.PostTurnSampleDelayMilliseconds > 0)
            {
                Thread.Sleep(movement.PostTurnSampleDelayMilliseconds);
            }
        }

        return FacingAlignmentResult.Fail("turn-no-progress", latestFacing, turnPulses);
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
        int turnPulseCount,
        NavigationCoordinate initialPosition,
        NavigationCoordinate finalPosition,
        long elapsedMilliseconds,
        NavigationFacingSummary? initialFacing,
        NavigationFacingSummary? finalFacing) =>
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
            TurnPulseCount: turnPulseCount,
            StopReason: "arrived",
            InitialPosition: initialPosition,
            FinalPosition: finalPosition,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: elapsedMilliseconds,
            InitialFacing: initialFacing,
            FinalFacing: finalFacing);

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
        int turnPulseCount,
        string stopReason,
        NavigationCoordinate initialPosition,
        NavigationCoordinate finalPosition,
        long elapsedMilliseconds,
        double? initialPlanarDistance = null,
        double? finalPlanarDistance = null,
        NavigationFacingSummary? initialFacing = null,
        NavigationFacingSummary? finalFacing = null) =>
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
            TurnPulseCount: turnPulseCount,
            StopReason: stopReason,
            InitialPosition: initialPosition,
            FinalPosition: finalPosition,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: elapsedMilliseconds,
            InitialFacing: initialFacing,
            FinalFacing: finalFacing);

    private sealed record FacingAlignmentResult(
        bool IsSuccess,
        string StopReason,
        NavigationFacingSummary? Facing,
        int TurnPulseCount)
    {
        public static FacingAlignmentResult Success(NavigationFacingSummary? facing, int turnPulseCount) =>
            new(true, string.Empty, facing, turnPulseCount);

        public static FacingAlignmentResult Fail(string stopReason, NavigationFacingSummary? facing, int turnPulseCount) =>
            new(false, stopReason, facing, turnPulseCount);
    }
}
