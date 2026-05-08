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
        var events = new List<NavigationEvent>();

        if (!poseSource.TryReadCurrent(out var current, out _))
        {
            events.Add(CreateEvent(
                type: "stop",
                elapsedMilliseconds: 0,
                status: "telemetry-lost",
                position: startWaypoint.Coordinate,
                detail: "Initial navigation pose sample could not be read."));
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
                elapsedMilliseconds: 0,
                events: events);
        }

        var initialPosition = new NavigationCoordinate(current.X, current.Y, current.Z);
        var startDeltaX = startWaypoint.X - current.X;
        var startDeltaZ = startWaypoint.Z - current.Z;
        var startPlanarDistance = NavigationMath.ComputePlanarDistance(startDeltaX, startDeltaZ);

        var initialDeltaX = destinationWaypoint.X - current.X;
        var initialDeltaZ = destinationWaypoint.Z - current.Z;
        var initialPlanarDistance = NavigationMath.ComputePlanarDistance(initialDeltaX, initialDeltaZ);
        events.Add(CreateEvent(
            type: "initial-sample",
            elapsedMilliseconds: 0,
            status: "observed",
            position: initialPosition,
            planarDistance: initialPlanarDistance,
            detail: "Captured the initial navigation pose sample."));

        if (startPlanarDistance > movement.StartRadius)
        {
            events.Add(CreateEvent(
                type: "stop",
                elapsedMilliseconds: 0,
                status: "start-mismatch",
                position: initialPosition,
                planarDistance: initialPlanarDistance,
                detail: "Current position was outside the configured start radius."));
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
                finalPlanarDistance: initialPlanarDistance,
                events: events);
        }

        if (initialPlanarDistance <= arrivalRadius)
        {
            events.Add(CreateEvent(
                type: "stop",
                elapsedMilliseconds: 0,
                status: "arrived",
                position: initialPosition,
                planarDistance: initialPlanarDistance,
                detail: "Initial position was already within the arrival radius."));
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
                elapsedMilliseconds: 0,
                events: events);
        }

        var paceKey = ResolvePaceKey(movement, pace);
        if (paceKey is false)
        {
            events.Add(CreateEvent(
                type: "stop",
                elapsedMilliseconds: 0,
                status: "input-failed",
                position: initialPosition,
                planarDistance: initialPlanarDistance,
                detail: $"Unable to resolve a movement key for pace '{pace}'."));
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
                finalPlanarDistance: initialPlanarDistance,
                events: events);
        }

        movementBackend.PrepareForMovement();
        events.Add(CreateEvent(
            type: "prepare-for-movement",
            elapsedMilliseconds: 0,
            status: "complete",
            position: initialPosition,
            planarDistance: initialPlanarDistance,
            detail: "Live interaction was armed before forward movement."));

        if (paceKey is string toggleKey)
        {
            var paceCommand = movementBackend.PressKey(toggleKey, PaceToggleHoldMilliseconds);
            if (!paceCommand.IsSuccess)
            {
                events.Add(CreateEvent(
                    type: "pace-toggle",
                    elapsedMilliseconds: 0,
                    status: "input-failed",
                    key: toggleKey,
                    position: initialPosition,
                    planarDistance: initialPlanarDistance,
                    detail: paceCommand.ErrorMessage ?? "Pace toggle input failed."));
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
                    finalPlanarDistance: initialPlanarDistance,
                    events: events);
            }

            events.Add(CreateEvent(
                type: "pace-toggle",
                elapsedMilliseconds: 0,
                status: "complete",
                key: toggleKey,
                position: initialPosition,
                planarDistance: initialPlanarDistance,
                detail: $"Applied pace toggle for '{pace}'."));
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
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "timeout",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Navigation exceeded the maximum travel time."));
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
                    currentPlanarDistance,
                    events);
            }

            var pulseCommand = movementBackend.PressKey(movement.ForwardKey, movement.ForwardPulseMilliseconds);
            if (!pulseCommand.IsSuccess)
            {
                events.Add(CreateEvent(
                    type: "forward-pulse-input",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "input-failed",
                    pulseIndex: pulseCount + 1,
                    key: movement.ForwardKey,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: pulseCommand.ErrorMessage ?? "Forward movement input failed."));
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
                    currentPlanarDistance,
                    events);
            }

            pulseCount++;
            events.Add(CreateEvent(
                type: "forward-pulse-input",
                elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                status: "complete",
                pulseIndex: pulseCount,
                key: movement.ForwardKey,
                position: latestPosition,
                planarDistance: currentPlanarDistance,
                detail: $"Sent forward movement pulse for {movement.ForwardPulseMilliseconds} ms."));

            if (movement.PostPulseSampleDelayMilliseconds > 0)
            {
                Thread.Sleep(movement.PostPulseSampleDelayMilliseconds);
            }

            if (!poseSource.TryReadCurrent(out current, out _))
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "telemetry-lost",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Navigation pose sample was unavailable after a forward pulse."));
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
                    currentPlanarDistance,
                    events);
            }

            latestPosition = new NavigationCoordinate(current.X, current.Y, current.Z);
            var deltaX = destinationWaypoint.X - current.X;
            var deltaZ = destinationWaypoint.Z - current.Z;
            currentPlanarDistance = NavigationMath.ComputePlanarDistance(deltaX, deltaZ);
            events.Add(CreateEvent(
                type: "forward-pulse-sample",
                elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                status: "observed",
                pulseIndex: pulseCount,
                key: movement.ForwardKey,
                position: latestPosition,
                planarDistance: currentPlanarDistance,
                detail: $"Observed position after forward pulse {pulseCount}."));

            if (currentPlanarDistance <= arrivalRadius)
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "arrived",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Destination waypoint reached within the arrival radius."));
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
                    stopwatch.ElapsedMilliseconds,
                    events);
            }

            var windowDistanceIncrease = currentPlanarDistance - lastWindowResetDistance;
            if (windowDistanceIncrease > movement.WrongWayToleranceDistance)
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "moving-away",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Planar distance increased beyond the wrong-way tolerance."));
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
                    currentPlanarDistance,
                    events);
            }

            if (windowDistanceIncrease >= movement.MinimumProgressDistance)
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "moving-away",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Planar distance increased by at least the minimum progress threshold."));
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
                    currentPlanarDistance,
                    events);
            }

            var progress = lastWindowResetDistance - currentPlanarDistance;
            if (progress >= movement.MinimumProgressDistance)
            {
                lastWindowResetDistance = currentPlanarDistance;
                lastWindowResetAtMilliseconds = stopwatch.ElapsedMilliseconds;
                events.Add(CreateEvent(
                    type: "progress-reset",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "observed",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: $"Progress window reset after improving distance by {progress:0.###}."));
                continue;
            }

            if ((stopwatch.ElapsedMilliseconds - lastWindowResetAtMilliseconds) >= movement.NoProgressWindowMilliseconds)
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "no-progress",
                    pulseIndex: pulseCount,
                    position: latestPosition,
                    planarDistance: currentPlanarDistance,
                    detail: "Planar distance did not improve within the configured no-progress window."));
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
                    currentPlanarDistance,
                    events);
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
        long elapsedMilliseconds,
        IReadOnlyList<NavigationEvent> events) =>
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
            ElapsedMilliseconds: elapsedMilliseconds,
            Events: events.ToArray());

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
        double? finalPlanarDistance = null,
        IReadOnlyList<NavigationEvent>? events = null) =>
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
            ElapsedMilliseconds: elapsedMilliseconds,
            Events: events?.ToArray());

    private static NavigationEvent CreateEvent(
        string type,
        long elapsedMilliseconds,
        string? status = null,
        int? pulseIndex = null,
        string? key = null,
        NavigationCoordinate? position = null,
        double? planarDistance = null,
        string? detail = null) =>
        new(
            Stage: "navigation",
            Type: type,
            ElapsedMilliseconds: elapsedMilliseconds,
            Status: status,
            PulseIndex: pulseIndex,
            Key: key,
            Position: position,
            PlanarDistance: planarDistance,
            Detail: detail);
}
