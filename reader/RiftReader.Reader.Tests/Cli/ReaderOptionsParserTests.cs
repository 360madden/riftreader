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
    }
}
