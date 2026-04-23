namespace RiftReader.Reader.Navigation;

public static class NavigationAutoTurner
{
    public static NavigationTurnResult Execute(
        NavigationPoseSample currentSample,
        INavigationPoseSource poseSource,
        IMovementBackend movementBackend,
        NavigationAutoTurnOptions options,
        Func<NavigationPoseSample, NavigationTurnPlan> turnPlanFactory)
    {
        ArgumentNullException.ThrowIfNull(poseSource);
        ArgumentNullException.ThrowIfNull(movementBackend);
        ArgumentNullException.ThrowIfNull(options);
        ArgumentNullException.ThrowIfNull(turnPlanFactory);

        var events = new List<NavigationEvent>();

        if (!options.Enabled)
        {
            var disabledPlan = NavigationMath.BuildUnavailableTurnPlan(
                destinationBearingDegrees: 0d,
                alignmentThresholdDegrees: options.WithinDegrees,
                reason: "Auto-turn was not enabled for this navigation run.");
            var disabledPosition = ToCoordinate(currentSample);
            events.Add(CreateEvent(
                type: "disabled",
                elapsedMilliseconds: 0,
                status: "disabled",
                position: disabledPosition,
                detail: disabledPlan.Reason));

            return new NavigationTurnResult(
                Status: "disabled",
                Succeeded: true,
                Attempted: false,
                TurnKey: null,
                TurnDirection: null,
                ThresholdDegrees: options.WithinDegrees,
                PulseCount: 0,
                WorseningPulseCount: 0,
                MaxWorseningPulses: options.MaxWorseningPulses,
                InitialPlan: disabledPlan,
                FinalPlan: disabledPlan,
                InitialPosition: disabledPosition,
                FinalPosition: disabledPosition,
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: disabledPlan.Reason,
                Events: events.ToArray());
        }

        var stopwatch = System.Diagnostics.Stopwatch.StartNew();
        var initialPlan = turnPlanFactory(currentSample);
        var initialPosition = ToCoordinate(currentSample);
        events.Add(CreateEvent(
            type: "initial-plan",
            elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
            status: initialPlan.Status,
            position: initialPosition,
            signedBearingDeltaDegrees: initialPlan.SignedBearingDeltaDegrees,
            absoluteBearingDeltaDegrees: initialPlan.AbsoluteBearingDeltaDegrees,
            detail: initialPlan.Reason));

        if (!IsPlanUsable(initialPlan))
        {
            return BuildFailure(
                status: "unavailable",
                attempted: false,
                turnKey: null,
                turnDirection: initialPlan.SuggestedTurnDirection,
                thresholdDegrees: options.WithinDegrees,
                pulseCount: 0,
                worseningPulseCount: 0,
                maxWorseningPulses: options.MaxWorseningPulses,
                initialPlan: initialPlan,
                finalPlan: initialPlan,
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                samples: Array.Empty<NavigationTurnSample>(),
                reason: initialPlan.Reason ?? "Actor-facing truth was unavailable for auto-turn alignment.",
                events: events);
        }

        if (initialPlan.WithinAlignmentThreshold ||
            string.Equals(initialPlan.SuggestedTurnDirection, "aligned", StringComparison.OrdinalIgnoreCase))
        {
            events.Add(CreateEvent(
                type: "noop",
                elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                status: "aligned",
                position: initialPosition,
                signedBearingDeltaDegrees: initialPlan.SignedBearingDeltaDegrees,
                absoluteBearingDeltaDegrees: initialPlan.AbsoluteBearingDeltaDegrees,
                detail: "Initial facing was already within the alignment threshold."));
            return new NavigationTurnResult(
                Status: "noop",
                Succeeded: true,
                Attempted: false,
                TurnKey: null,
                TurnDirection: "aligned",
                ThresholdDegrees: options.WithinDegrees,
                PulseCount: 0,
                WorseningPulseCount: 0,
                MaxWorseningPulses: options.MaxWorseningPulses,
                InitialPlan: initialPlan,
                FinalPlan: initialPlan,
                InitialPosition: initialPosition,
                FinalPosition: initialPosition,
                Samples: Array.Empty<NavigationTurnSample>(),
                Reason: null,
                Events: events.ToArray());
        }

        movementBackend.PrepareForMovement();
        events.Add(CreateEvent(
            type: "prepare-for-movement",
            elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
            status: "complete",
            position: initialPosition,
            detail: "Live interaction was armed before auto-turn input."));

        var turnPlan = initialPlan;
        var turnDirection = ResolveTurnDirection(turnPlan);
        var turnKey = ResolveTurnKey(turnDirection, options);
        if (turnKey is null)
        {
            return BuildFailure(
                status: "direction-unavailable",
                attempted: false,
                turnKey: null,
                turnDirection: turnDirection,
                thresholdDegrees: options.WithinDegrees,
                pulseCount: 0,
                worseningPulseCount: 0,
                maxWorseningPulses: options.MaxWorseningPulses,
                initialPlan: initialPlan,
                finalPlan: turnPlan,
                initialPosition: initialPosition,
                finalPosition: initialPosition,
                samples: Array.Empty<NavigationTurnSample>(),
                reason: "Auto-turn required a usable left/right turn direction but the current plan was not directional.",
                events: events);
        }

        events.Add(CreateEvent(
            type: "direction-resolved",
            elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
            status: turnDirection,
            key: turnKey,
            position: initialPosition,
            signedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
            absoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
            detail: "Resolved the first directional turn key for auto-turn."));

        var samples = new List<NavigationTurnSample>(capacity: Math.Max(options.MaxTurnPulses, 1));
        var previousDelta = turnPlan.AbsoluteBearingDeltaDegrees ?? double.PositiveInfinity;
        var worseningPulseCount = 0;
        var latestPosition = initialPosition;

        for (var pulseIndex = 1; pulseIndex <= options.MaxTurnPulses; pulseIndex++)
        {
            var commandResult = movementBackend.PressKey(turnKey, options.TurnPulseMilliseconds);
            if (!commandResult.IsSuccess)
            {
                events.Add(CreateEvent(
                    type: "pulse-input",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "input-failed",
                    pulseIndex: pulseIndex,
                    key: turnKey,
                    position: latestPosition,
                    detail: commandResult.ErrorMessage ?? "Auto-turn movement input failed."));
                return BuildFailure(
                    status: "input-failed",
                    attempted: true,
                    turnKey: turnKey,
                    turnDirection: turnDirection,
                    thresholdDegrees: options.WithinDegrees,
                    pulseCount: pulseIndex - 1,
                    worseningPulseCount: worseningPulseCount,
                    maxWorseningPulses: options.MaxWorseningPulses,
                    initialPlan: initialPlan,
                    finalPlan: turnPlan,
                    initialPosition: initialPosition,
                    finalPosition: latestPosition,
                    samples: samples,
                    reason: commandResult.ErrorMessage ?? "Auto-turn movement input failed.",
                    events: events);
            }

            if (options.PostTurnSampleDelayMilliseconds > 0)
            {
                Thread.Sleep(options.PostTurnSampleDelayMilliseconds);
            }

            if (!poseSource.TryReadCurrent(out var updatedSample, out var poseError))
            {
                events.Add(CreateEvent(
                    type: "pulse-sample",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "telemetry-lost",
                    pulseIndex: pulseIndex,
                    key: turnKey,
                    position: latestPosition,
                    detail: poseError ?? "Navigation pose source was unavailable after an auto-turn pulse."));
                return BuildFailure(
                    status: "telemetry-lost",
                    attempted: true,
                    turnKey: turnKey,
                    turnDirection: turnDirection,
                    thresholdDegrees: options.WithinDegrees,
                    pulseCount: pulseIndex,
                    worseningPulseCount: worseningPulseCount,
                    maxWorseningPulses: options.MaxWorseningPulses,
                    initialPlan: initialPlan,
                    finalPlan: turnPlan,
                    initialPosition: initialPosition,
                    finalPosition: latestPosition,
                    samples: samples,
                    reason: poseError ?? "Navigation pose source was unavailable after an auto-turn pulse.",
                    events: events);
            }

            latestPosition = ToCoordinate(updatedSample);
            turnPlan = turnPlanFactory(updatedSample);
            samples.Add(new NavigationTurnSample(
                PulseIndex: pulseIndex,
                Key: turnKey,
                Position: latestPosition,
                YawDegrees: turnPlan.CurrentYawDegrees,
                SignedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
                AbsoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
                SuggestedTurnDirection: turnPlan.SuggestedTurnDirection,
                SelectedSourceAddress: turnPlan.SelectedSourceAddress,
                BasisPrimaryForwardOffset: turnPlan.BasisPrimaryForwardOffset));
            events.Add(CreateEvent(
                type: "pulse-sample",
                elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                status: turnPlan.Status,
                pulseIndex: pulseIndex,
                key: turnKey,
                position: latestPosition,
                signedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
                absoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
                detail: $"Observed auto-turn pulse {pulseIndex}."));

            if (!IsPlanUsable(turnPlan))
            {
                return BuildFailure(
                    status: "facing-unavailable",
                    attempted: true,
                    turnKey: turnKey,
                    turnDirection: turnDirection,
                    thresholdDegrees: options.WithinDegrees,
                    pulseCount: pulseIndex,
                    worseningPulseCount: worseningPulseCount,
                    maxWorseningPulses: options.MaxWorseningPulses,
                    initialPlan: initialPlan,
                    finalPlan: turnPlan,
                    initialPosition: initialPosition,
                    finalPosition: latestPosition,
                    samples: samples,
                    reason: turnPlan.Reason ?? "Actor-facing truth became unavailable after an auto-turn pulse.",
                    events: events);
            }

            if (turnPlan.WithinAlignmentThreshold ||
                string.Equals(turnPlan.SuggestedTurnDirection, "aligned", StringComparison.OrdinalIgnoreCase))
            {
                if (options.SettleDelayMilliseconds > 0)
                {
                    Thread.Sleep(options.SettleDelayMilliseconds);
                }

                events.Add(CreateEvent(
                    type: "complete",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "complete",
                    pulseIndex: pulseIndex,
                    key: turnKey,
                    position: latestPosition,
                    signedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
                    absoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
                    detail: "Auto-turn reached the alignment threshold."));

                return new NavigationTurnResult(
                    Status: "complete",
                    Succeeded: true,
                    Attempted: true,
                    TurnKey: turnKey,
                    TurnDirection: turnPlan.SuggestedTurnDirection,
                    ThresholdDegrees: options.WithinDegrees,
                    PulseCount: pulseIndex,
                    WorseningPulseCount: worseningPulseCount,
                    MaxWorseningPulses: options.MaxWorseningPulses,
                    InitialPlan: initialPlan,
                    FinalPlan: turnPlan,
                    InitialPosition: initialPosition,
                    FinalPosition: latestPosition,
                    Samples: samples.ToArray(),
                    Reason: null,
                    Events: events.ToArray());
            }

            var currentDelta = turnPlan.AbsoluteBearingDeltaDegrees ?? double.PositiveInfinity;
            if (currentDelta > (previousDelta + options.WorseningToleranceDegrees))
            {
                worseningPulseCount++;
            }
            else
            {
                worseningPulseCount = 0;
            }

            if (worseningPulseCount >= options.MaxWorseningPulses)
            {
                events.Add(CreateEvent(
                    type: "stop",
                    elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
                    status: "worsening",
                    pulseIndex: pulseIndex,
                    key: turnKey,
                    position: latestPosition,
                    signedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
                    absoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
                    detail: $"Auto-turn worsened for {worseningPulseCount} consecutive pulses."));
                return BuildFailure(
                    status: "worsening",
                    attempted: true,
                    turnKey: turnKey,
                    turnDirection: turnPlan.SuggestedTurnDirection,
                    thresholdDegrees: options.WithinDegrees,
                    pulseCount: pulseIndex,
                    worseningPulseCount: worseningPulseCount,
                    maxWorseningPulses: options.MaxWorseningPulses,
                    initialPlan: initialPlan,
                    finalPlan: turnPlan,
                    initialPosition: initialPosition,
                    finalPosition: latestPosition,
                    samples: samples,
                    reason: $"Auto-turn worsened for {worseningPulseCount} consecutive pulses.",
                    events: events);
            }

            turnDirection = ResolveTurnDirection(turnPlan) ?? turnDirection;
            turnKey = ResolveTurnKey(turnDirection, options) ?? turnKey;
            previousDelta = currentDelta;
        }

        events.Add(CreateEvent(
            type: "stop",
            elapsedMilliseconds: stopwatch.ElapsedMilliseconds,
            status: "incomplete",
            pulseIndex: options.MaxTurnPulses,
            key: turnKey,
            position: latestPosition,
            signedBearingDeltaDegrees: turnPlan.SignedBearingDeltaDegrees,
            absoluteBearingDeltaDegrees: turnPlan.AbsoluteBearingDeltaDegrees,
            detail: $"Auto-turn failed to reach the {options.WithinDegrees:0.###} degree threshold after {options.MaxTurnPulses} pulses."));

        return BuildFailure(
            status: "incomplete",
            attempted: true,
            turnKey: turnKey,
            turnDirection: turnDirection,
            thresholdDegrees: options.WithinDegrees,
            pulseCount: options.MaxTurnPulses,
            worseningPulseCount: worseningPulseCount,
            maxWorseningPulses: options.MaxWorseningPulses,
            initialPlan: initialPlan,
            finalPlan: turnPlan,
            initialPosition: initialPosition,
            finalPosition: latestPosition,
            samples: samples,
            reason: $"Auto-turn failed to reach the {options.WithinDegrees:0.###} degree threshold after {options.MaxTurnPulses} pulses.",
            events: events);
    }

    private static NavigationTurnResult BuildFailure(
        string status,
        bool attempted,
        string? turnKey,
        string? turnDirection,
        double thresholdDegrees,
        int pulseCount,
        int worseningPulseCount,
        int maxWorseningPulses,
        NavigationTurnPlan initialPlan,
        NavigationTurnPlan finalPlan,
        NavigationCoordinate initialPosition,
        NavigationCoordinate finalPosition,
        IReadOnlyList<NavigationTurnSample> samples,
        string reason,
        IReadOnlyList<NavigationEvent> events) =>
        new(
            Status: status,
            Succeeded: false,
            Attempted: attempted,
            TurnKey: turnKey,
            TurnDirection: turnDirection,
            ThresholdDegrees: thresholdDegrees,
            PulseCount: pulseCount,
            WorseningPulseCount: worseningPulseCount,
            MaxWorseningPulses: maxWorseningPulses,
            InitialPlan: initialPlan,
            FinalPlan: finalPlan,
            InitialPosition: initialPosition,
            FinalPosition: finalPosition,
            Samples: samples,
            Reason: reason,
            Events: events.ToArray());

    private static bool IsPlanUsable(NavigationTurnPlan plan) =>
        string.Equals(plan.Status, "available", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(plan.Status, "aligned", StringComparison.OrdinalIgnoreCase);

    private static string? ResolveTurnDirection(NavigationTurnPlan plan)
    {
        if (plan.WithinAlignmentThreshold)
        {
            return "aligned";
        }

        return string.Equals(plan.SuggestedTurnDirection, "left", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(plan.SuggestedTurnDirection, "right", StringComparison.OrdinalIgnoreCase)
            ? plan.SuggestedTurnDirection!.ToLowerInvariant()
            : null;
    }

    private static string? ResolveTurnKey(string? direction, NavigationAutoTurnOptions options) =>
        direction switch
        {
            "left" => options.TurnLeftKey,
            "right" => options.TurnRightKey,
            _ => null
        };

    private static NavigationEvent CreateEvent(
        string type,
        long elapsedMilliseconds,
        string? status = null,
        int? pulseIndex = null,
        string? key = null,
        NavigationCoordinate? position = null,
        double? signedBearingDeltaDegrees = null,
        double? absoluteBearingDeltaDegrees = null,
        string? detail = null) =>
        new(
            Stage: "auto-turn",
            Type: type,
            ElapsedMilliseconds: elapsedMilliseconds,
            Status: status,
            PulseIndex: pulseIndex,
            Key: key,
            Position: position,
            SignedBearingDeltaDegrees: signedBearingDeltaDegrees,
            AbsoluteBearingDeltaDegrees: absoluteBearingDeltaDegrees,
            Detail: detail);

    private static NavigationCoordinate ToCoordinate(NavigationPoseSample sample) =>
        new(sample.X, sample.Y, sample.Z);
}
