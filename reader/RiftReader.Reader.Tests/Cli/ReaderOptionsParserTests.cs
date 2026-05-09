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
    public void Parse_AcceptsFindPlayerOrientationCandidateWithLedgerFile()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--find-player-orientation-candidate",
            "--orientation-candidate-ledger-file", @"C:\temp\orientation-candidate-ledger.ndjson",
            "--max-hits", "8",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.FindPlayerOrientationCandidate);
        Assert.Equal("rift_x64", options.ProcessName);
        Assert.Equal(@"C:\temp\orientation-candidate-ledger.ndjson", options.OrientationCandidateLedgerFile);
        Assert.Equal(8, options.MaxHits);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_AcceptsFindPlayerOrientationCandidateWithExplicitReaderBridgeSnapshotFile()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--pid", "49504",
            "--readerbridge-snapshot-file", @"C:\temp\readerbridge-bootstrap.lua",
            "--find-player-orientation-candidate",
            "--max-hits", "16",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.FindPlayerOrientationCandidate);
        Assert.False(options.ReadReaderBridgeSnapshot);
        Assert.Equal(49504, options.ProcessId);
        Assert.Equal(@"C:\temp\readerbridge-bootstrap.lua", options.ReaderBridgeSnapshotFile);
        Assert.Equal(16, options.MaxHits);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_TreatsReaderBridgeSnapshotFileAloneAsSnapshotMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--readerbridge-snapshot-file", @"C:\temp\readerbridge-bootstrap.lua",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.ReadReaderBridgeSnapshot);
        Assert.Equal(@"C:\temp\readerbridge-bootstrap.lua", options.ReaderBridgeSnapshotFile);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_RejectsOrientationCandidateLedgerFileOutsideFindPlayerOrientationCandidateMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-player-current",
            "--orientation-candidate-ledger-file", @"C:\temp\orientation-candidate-ledger.ndjson"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--orientation-candidate-ledger-file can only be used with --find-player-orientation-candidate.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
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
    public void Parse_AcceptsReaderBridgeCoordScanTolerance()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--scan-readerbridge-player-coords",
            "--scan-tolerance", "0.05",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.ScanReaderBridgePlayerCoords);
        Assert.Equal(0.05d, options.ScanTolerance);
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
            "--navigation-run-summary-file", @"C:\temp\navigation-run.json",
            "--verbose-navigation-events",
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
        Assert.Equal(@"C:\temp\navigation-run.json", options.NavigationRunSummaryFile);
        Assert.True(options.VerboseNavigationEvents);
    }

    [Fact]
    public void Parse_AcceptsNavigationRoutePlanWithViaWaypoints()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--plan-navigation-route",
            "--start-waypoint", "point_a",
            "--via-waypoint", "point_b",
            "--via-waypoint", "point_c",
            "--destination-waypoint", "point_d",
            "--navigation-waypoint-file", @"C:\temp\waypoints.json",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.PlanNavigationRoute);
        Assert.False(options.NavigateWaypointRoute);
        Assert.False(options.NavigateWaypoints);
        Assert.Equal("point_a", options.StartWaypointId);
        Assert.Equal(["point_b", "point_c"], options.ViaWaypointIds);
        Assert.Equal("point_d", options.DestinationWaypointId);
        Assert.Equal(@"C:\temp\waypoints.json", options.NavigationWaypointFile);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_AcceptsNavigateWaypointRouteWithViaWaypoints()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--navigate-waypoint-route",
            "--start-waypoint", "point_a",
            "--via-waypoint", "point_b",
            "--destination-waypoint", "point_c",
            "--navigation-waypoint-file", @"C:\temp\waypoints.json",
            "--navigation-run-summary-file", @"C:\temp\route-run.json",
            "--auto-turn-before-move",
            "--auto-turn-within-degrees", "6.5",
            "--turn-max-pulses", "4",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.NavigateWaypointRoute);
        Assert.False(options.PlanNavigationRoute);
        Assert.False(options.NavigateWaypoints);
        Assert.Equal("point_a", options.StartWaypointId);
        Assert.Equal(["point_b"], options.ViaWaypointIds);
        Assert.Equal("point_c", options.DestinationWaypointId);
        Assert.Equal(@"C:\temp\waypoints.json", options.NavigationWaypointFile);
        Assert.Equal(@"C:\temp\route-run.json", options.NavigationRunSummaryFile);
        Assert.True(options.AutoTurnBeforeMove);
        Assert.Equal(6.5d, options.AutoTurnWithinDegrees);
        Assert.Equal(4, options.TurnMaxPulses);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_RejectsNavigationRunSummaryFileOutsideMovementModes()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-navigation-current",
            "--destination-waypoint", "point_b",
            "--navigation-run-summary-file", @"C:\temp\navigation-run.json"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--navigation-run-summary-file can only be used with --navigate-waypoints or --navigate-waypoint-route.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Parse_RejectsViaWaypointOutsideRouteModes()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--navigate-waypoints",
            "--start-waypoint", "point_a",
            "--via-waypoint", "point_b",
            "--destination-waypoint", "point_c"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--via-waypoint can only be used with --plan-navigation-route or --navigate-waypoint-route.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Parse_RejectsNavigateWaypointRouteWithSingleSegmentNavigation()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--navigate-waypoint-route",
            "--navigate-waypoints",
            "--start-waypoint", "point_a",
            "--destination-waypoint", "point_c"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--navigate-waypoint-route cannot be combined with --navigate-waypoints.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
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

    [Fact]
    public void Parse_RejectsVerboseNavigationEventsOutsideWaypointNavigationMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-navigation-current",
            "--destination-waypoint", "point_b",
            "--verbose-navigation-events"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--verbose-navigation-events can only be used with --navigate-waypoints.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Parse_AcceptsTomTomWaypointImportMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--import-tomtom-waypoints",
            "--tomtom-saved-variables-file", @"C:\temp\TomTom.lua",
            "--navigation-waypoint-file", @"C:\temp\tomtom-waypoints.json",
            "--tomtom-list", "wood",
            "--tomtom-list", "Rare Mobs",
            "--tomtom-zone", "z123",
            "--tomtom-default-y", "818.25",
            "--tomtom-id-prefix", "tt",
            "--tomtom-arrival-radius", "4.5",
            "--tomtom-pace", "keep",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        var options = Assert.IsType<ReaderOptions>(result.Options);
        Assert.True(options.ImportTomTomWaypoints);
        Assert.Equal(@"C:\temp\TomTom.lua", options.TomTomSavedVariablesFile);
        Assert.Equal(@"C:\temp\tomtom-waypoints.json", options.NavigationWaypointFile);
        Assert.Equal(["wood", "Rare Mobs"], options.TomTomListNames);
        Assert.Equal("z123", options.TomTomZone);
        Assert.Equal(818.25d, options.TomTomDefaultY);
        Assert.Equal("tt", options.TomTomIdPrefix);
        Assert.Equal(4.5d, options.TomTomArrivalRadius);
        Assert.Equal("keep", options.TomTomPace);
        Assert.True(options.JsonOutput);
    }

    [Fact]
    public void Parse_RejectsTomTomImportSwitchesWithoutImportMode()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--tomtom-saved-variables-file", @"C:\temp\TomTom.lua"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("TomTom import switches require --import-tomtom-waypoints.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Parse_RejectsTomTomImportWithoutSavedVariablesFile()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--import-tomtom-waypoints"
        ]);

        Assert.False(result.IsSuccess);
        Assert.Contains("--import-tomtom-waypoints requires --tomtom-saved-variables-file.", result.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }
}
