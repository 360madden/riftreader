using RiftReader.Reader.Cli;

namespace RiftReader.Reader.Tests.Cli;

public sealed class ReaderOptionsParserTests
{
    [Fact]
    public void Parse_AcceptsReadPlayerOrientationWithProcessAttach()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-player-orientation",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.ReadPlayerOrientation);
        Assert.Equal("rift_x64", options.ProcessName);
        Assert.Null(options.ProcessId);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_AcceptsCaptureNavigationWaypointMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--capture-navigation-waypoint", "point_a",
            "--waypoint-label", "Point A",
            "--waypoint-zone", "test_zone",
            "--waypoint-arrival-radius", "2.5",
            "--waypoint-pace", "keep",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.CaptureNavigationWaypoint);
        Assert.Equal("point_a", options.CaptureNavigationWaypointId);
        Assert.Equal("Point A", options.WaypointLabel);
        Assert.Equal("test_zone", options.WaypointZone);
        Assert.Equal(2.5d, options.WaypointArrivalRadius);
        Assert.Equal("keep", options.WaypointPace);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_RejectsWaypointLabelOutsideCaptureNavigationWaypointMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--waypoint-label", "Point A"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--waypoint-label can only be used with --capture-navigation-waypoint.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Parse_AcceptsTelemetryHostMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--run-telemetry-host",
            "--telemetry-poll-interval-ms", "125",
            "--telemetry-output-file", @"C:\temp\telemetry.latest.json",
            "--telemetry-event-log-file", @"C:\temp\telemetry.events.ndjson",
            "--telemetry-proof-anchor-file", @"C:\temp\telemetry-proof-anchor.json",
            "--telemetry-diagnostics",
            "--telemetry-diagnostics-log-file", @"C:\temp\telemetry.discovery.ndjson"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.RunTelemetryHost);
        Assert.Equal(125, options.TelemetryPollIntervalMilliseconds);
        Assert.True(options.TelemetryDiagnostics);
        Assert.Equal(@"C:\temp\telemetry.latest.json", options.TelemetryOutputFile);
        Assert.Equal(@"C:\temp\telemetry.events.ndjson", options.TelemetryEventLogFile);
        Assert.Equal(@"C:\temp\telemetry.discovery.ndjson", options.TelemetryDiagnosticsLogFile);
        Assert.Equal(@"C:\temp\telemetry-proof-anchor.json", options.TelemetryProofAnchorFile);
    }

    [Fact]
    public void Parse_AcceptsTelemetryPreflightMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--telemetry-preflight",
            "--telemetry-proof-anchor-file", @"C:\temp\telemetry-proof-anchor.json",
            "--telemetry-diagnostics",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.TelemetryPreflight);
        Assert.False(options.RunTelemetryHost);
        Assert.True(options.TelemetryDiagnostics);
        Assert.Equal(@"C:\temp\telemetry-proof-anchor.json", options.TelemetryProofAnchorFile);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_AcceptsNavigateWaypointsWithAutoTurnOptions()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--navigate-waypoints",
            "--start-waypoint", "point_a",
            "--destination-waypoint", "point_b",
            "--auto-turn-before-move",
            "--auto-turn-within-degrees", "7.5",
            "--turn-left-key", "q",
            "--turn-right-key", "e",
            "--turn-pulse-ms", "90",
            "--turn-post-sample-delay-ms", "120",
            "--turn-settle-delay-ms", "350",
            "--turn-max-pulses", "8",
            "--turn-worsening-tolerance", "0.75",
            "--turn-max-worsening-pulses", "3",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.NavigateWaypoints);
        Assert.True(options.AutoTurnBeforeMove);
        Assert.Equal(7.5d, options.AutoTurnWithinDegrees);
        Assert.Equal("q", options.TurnLeftKey);
        Assert.Equal("e", options.TurnRightKey);
        Assert.Equal(90, options.TurnPulseMilliseconds);
        Assert.Equal(120, options.TurnPostSampleDelayMilliseconds);
        Assert.Equal(350, options.TurnSettleDelayMilliseconds);
        Assert.Equal(8, options.TurnMaxPulses);
        Assert.Equal(0.75d, options.TurnWorseningToleranceDegrees);
        Assert.Equal(3, options.TurnMaxWorseningPulses);
    }

    [Fact]
    public void Parse_RejectsAutoTurnTuningWithoutAutoTurnFlag()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--navigate-waypoints",
            "--start-waypoint", "point_a",
            "--destination-waypoint", "point_b",
            "--turn-pulse-ms", "90"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("Auto-turn tuning switches require --auto-turn-before-move.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }
}
