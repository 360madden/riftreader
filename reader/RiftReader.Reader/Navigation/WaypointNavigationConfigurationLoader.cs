using System.Text.Json;

namespace RiftReader.Reader.Navigation;

public static class WaypointNavigationConfigurationLoader
{
    private const int SupportedSchemaVersion = 1;
    private const string ForwardKeyMovementBearingKind = "forward-key-movement-bearing";

    public static WaypointNavigationConfiguration? TryLoad(string? filePath, out string? error)
    {
        error = null;

        var sourceFile = NavigationPathResolver.ResolveWaypointFile(filePath);
        if (!File.Exists(sourceFile))
        {
            error = $"Navigation waypoint file was not found: '{sourceFile}'.";
            return null;
        }

        NavigationWaypointFileDocument? document;
        try
        {
            var json = File.ReadAllText(sourceFile);
            document = JsonSerializer.Deserialize<NavigationWaypointFileDocument>(
                json,
                new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
        }
        catch (Exception ex)
        {
            error = $"Unable to load navigation waypoint file '{sourceFile}': {ex.Message}";
            return null;
        }

        if (document is null)
        {
            error = $"Navigation waypoint file '{sourceFile}' did not contain a readable document.";
            return null;
        }

        if (document.SchemaVersion != SupportedSchemaVersion)
        {
            error = $"Navigation waypoint file '{sourceFile}' must use schemaVersion {SupportedSchemaVersion}.";
            return null;
        }

        if (document.Movement is null)
        {
            error = $"Navigation waypoint file '{sourceFile}' did not contain a movement section.";
            return null;
        }

        if (document.Waypoints is null || document.Waypoints.Count == 0)
        {
            error = $"Navigation waypoint file '{sourceFile}' did not contain any waypoints.";
            return null;
        }

        var navigationBearingKind = document.Provenance?.NavigationBearingKind;
        if (!string.IsNullOrWhiteSpace(navigationBearingKind) &&
            !string.Equals(navigationBearingKind.Trim(), ForwardKeyMovementBearingKind, StringComparison.OrdinalIgnoreCase))
        {
            error = $"Navigation waypoint file '{sourceFile}' contains unsupported provenance.navigationBearingKind '{navigationBearingKind}'. Expected '{ForwardKeyMovementBearingKind}'.";
            return null;
        }

        if (string.IsNullOrWhiteSpace(document.Movement.ForwardKey))
        {
            error = $"Navigation waypoint file '{sourceFile}' must define movement.forwardKey.";
            return null;
        }

        if (!NavigationPace.TryNormalize(document.Movement.DefaultPace ?? NavigationPace.Keep, out var defaultPace))
        {
            error = $"Navigation waypoint file '{sourceFile}' contains unsupported movement.defaultPace '{document.Movement.DefaultPace}'.";
            return null;
        }

        if (!TryRequirePositive(document.Movement.ForwardPulseMilliseconds, "movement.forwardPulseMilliseconds", sourceFile, out var forwardPulseMilliseconds, out error) ||
            !TryRequireNonNegative(document.Movement.PostPulseSampleDelayMilliseconds, "movement.postPulseSampleDelayMilliseconds", sourceFile, out var postPulseSampleDelayMilliseconds, out error) ||
            !TryRequirePositive(document.Movement.StartRadius, "movement.startRadius", sourceFile, out var startRadius, out error) ||
            !TryRequirePositive(document.Movement.DefaultArrivalRadius, "movement.defaultArrivalRadius", sourceFile, out var defaultArrivalRadius, out error) ||
            !TryRequirePositive(document.Movement.NoProgressWindowMilliseconds, "movement.noProgressWindowMilliseconds", sourceFile, out var noProgressWindowMilliseconds, out error) ||
            !TryRequirePositive(document.Movement.MinimumProgressDistance, "movement.minimumProgressDistance", sourceFile, out var minimumProgressDistance, out error) ||
            !TryRequirePositive(document.Movement.WrongWayToleranceDistance, "movement.wrongWayToleranceDistance", sourceFile, out var wrongWayToleranceDistance, out error) ||
            !TryRequirePositive(document.Movement.MaxTravelSeconds, "movement.maxTravelSeconds", sourceFile, out var maxTravelSeconds, out error))
        {
            return null;
        }

        var waypoints = new Dictionary<string, WaypointDefinition>(StringComparer.OrdinalIgnoreCase);
        foreach (var waypoint in document.Waypoints)
        {
            if (waypoint is null)
            {
                error = $"Navigation waypoint file '{sourceFile}' contained a null waypoint entry.";
                return null;
            }

            if (string.IsNullOrWhiteSpace(waypoint.Id))
            {
                error = $"Navigation waypoint file '{sourceFile}' contained a waypoint without an id.";
                return null;
            }

            if (!waypoint.X.HasValue || !waypoint.Y.HasValue || !waypoint.Z.HasValue)
            {
                error = $"Navigation waypoint '{waypoint.Id}' in '{sourceFile}' must define x, y, and z.";
                return null;
            }

            if (waypoint.ArrivalRadius.HasValue && waypoint.ArrivalRadius.Value <= 0d)
            {
                error = $"Navigation waypoint '{waypoint.Id}' in '{sourceFile}' must use a positive arrivalRadius when provided.";
                return null;
            }

            string? waypointPace = null;
            if (!string.IsNullOrWhiteSpace(waypoint.Pace))
            {
                if (!NavigationPace.TryNormalize(waypoint.Pace, out waypointPace))
                {
                    error = $"Navigation waypoint '{waypoint.Id}' in '{sourceFile}' contains unsupported pace '{waypoint.Pace}'.";
                    return null;
                }
            }

            var normalizedId = waypoint.Id.Trim();
            if (waypoints.ContainsKey(normalizedId))
            {
                error = $"Navigation waypoint file '{sourceFile}' contains duplicate waypoint id '{normalizedId}'.";
                return null;
            }

            var definition = new WaypointDefinition(
                Id: normalizedId,
                Label: string.IsNullOrWhiteSpace(waypoint.Label) ? normalizedId : waypoint.Label.Trim(),
                Zone: string.IsNullOrWhiteSpace(waypoint.Zone) ? null : waypoint.Zone.Trim(),
                X: waypoint.X.Value,
                Y: waypoint.Y.Value,
                Z: waypoint.Z.Value,
                ArrivalRadius: waypoint.ArrivalRadius,
                Pace: waypointPace);

            waypoints.Add(normalizedId, definition);
        }

        error = null;
        return new WaypointNavigationConfiguration(
            SourceFile: sourceFile,
            SchemaVersion: SupportedSchemaVersion,
            Movement: new WaypointMovementSettings(
                ForwardKey: document.Movement.ForwardKey!.Trim(),
                RunKey: NormalizeOptionalKey(document.Movement.RunKey),
                WalkKey: NormalizeOptionalKey(document.Movement.WalkKey),
                DefaultPace: defaultPace,
                ForwardPulseMilliseconds: forwardPulseMilliseconds,
                PostPulseSampleDelayMilliseconds: postPulseSampleDelayMilliseconds,
                StartRadius: startRadius,
                DefaultArrivalRadius: defaultArrivalRadius,
                NoProgressWindowMilliseconds: noProgressWindowMilliseconds,
                MinimumProgressDistance: minimumProgressDistance,
                WrongWayToleranceDistance: wrongWayToleranceDistance,
                MaxTravelSeconds: maxTravelSeconds),
            Waypoints: waypoints);
    }

    private static string? NormalizeOptionalKey(string? value) =>
        string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    private static bool TryRequirePositive(int? value, string fieldName, string sourceFile, out int normalized, out string? error)
    {
        normalized = 0;
        if (!value.HasValue || value.Value <= 0)
        {
            error = $"Navigation waypoint file '{sourceFile}' must define a positive {fieldName}.";
            return false;
        }

        normalized = value.Value;
        error = null;
        return true;
    }

    private static bool TryRequirePositive(double? value, string fieldName, string sourceFile, out double normalized, out string? error)
    {
        normalized = 0d;
        if (!value.HasValue || value.Value <= 0d)
        {
            error = $"Navigation waypoint file '{sourceFile}' must define a positive {fieldName}.";
            return false;
        }

        normalized = value.Value;
        error = null;
        return true;
    }

    private static bool TryRequireNonNegative(int? value, string fieldName, string sourceFile, out int normalized, out string? error)
    {
        normalized = 0;
        if (!value.HasValue || value.Value < 0)
        {
            error = $"Navigation waypoint file '{sourceFile}' must define a non-negative {fieldName}.";
            return false;
        }

        normalized = value.Value;
        error = null;
        return true;
    }
}
