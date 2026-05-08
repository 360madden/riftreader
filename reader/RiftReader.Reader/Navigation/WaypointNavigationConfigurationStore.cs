using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RiftReader.Reader.Navigation;

public static class WaypointNavigationConfigurationStore
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions ReadOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private static readonly JsonSerializerOptions WriteOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public static WaypointDefinition? TryUpsertWaypoint(
        string? filePath,
        string waypointId,
        NavigationPoseSample sample,
        string? label,
        string? zone,
        double? arrivalRadius,
        string? pace,
        out string resolvedFile,
        out bool created,
        out string? error)
    {
        resolvedFile = NavigationPathResolver.ResolveWaypointFile(filePath);
        created = false;
        error = null;

        if (string.IsNullOrWhiteSpace(waypointId))
        {
            error = "Waypoint id must not be blank.";
            return null;
        }

        if (arrivalRadius.HasValue && arrivalRadius.Value <= 0d)
        {
            error = "Waypoint arrival radius must be positive when provided.";
            return null;
        }

        string? normalizedPace = null;
        if (!string.IsNullOrWhiteSpace(pace) &&
            !NavigationPace.TryNormalize(pace, out normalizedPace))
        {
            error = $"Unsupported waypoint pace '{pace}'. Use run, walk, or keep.";
            return null;
        }

        WaypointNavigationConfiguration? existingConfiguration = null;
        NavigationWaypointFileDocument document;

        if (File.Exists(resolvedFile))
        {
            existingConfiguration = WaypointNavigationConfigurationLoader.TryLoad(resolvedFile, out error);
            if (existingConfiguration is null)
            {
                return null;
            }

            if (!TryLoadDocument(resolvedFile, out document, out error))
            {
                return null;
            }
        }
        else
        {
            document = CreateDefaultDocument();
        }

        var normalizedId = waypointId.Trim();
        var existingWaypoint = existingConfiguration is not null &&
                               existingConfiguration.Waypoints.TryGetValue(normalizedId, out var resolvedExistingWaypoint)
            ? resolvedExistingWaypoint
            : null;

        var existingWaypoints = document.Waypoints?.ToList() ?? [];
        var existingIndex = existingWaypoints.FindIndex(candidate =>
            string.Equals(candidate?.Id?.Trim(), normalizedId, StringComparison.OrdinalIgnoreCase));

        created = existingIndex < 0;

        var capturedWaypoint = new NavigationWaypointDocument(
            Id: normalizedId,
            Label: NormalizeOptional(label) ?? existingWaypoint?.Label ?? normalizedId,
            Zone: NormalizeOptional(zone) ?? existingWaypoint?.Zone,
            X: sample.X,
            Y: sample.Y,
            Z: sample.Z,
            ArrivalRadius: arrivalRadius ?? existingWaypoint?.ArrivalRadius,
            Pace: normalizedPace ?? existingWaypoint?.Pace);

        if (existingIndex >= 0)
        {
            existingWaypoints[existingIndex] = capturedWaypoint;
        }
        else
        {
            existingWaypoints.Add(capturedWaypoint);
        }

        var updatedDocument = new NavigationWaypointFileDocument(
            SchemaVersion: document.SchemaVersion ?? SupportedSchemaVersion,
            Provenance: document.Provenance,
            Movement: document.Movement ?? CreateDefaultMovement(),
            Waypoints: existingWaypoints);

        try
        {
            var directory = Path.GetDirectoryName(resolvedFile);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var json = JsonSerializer.Serialize(updatedDocument, WriteOptions);
            File.WriteAllText(resolvedFile, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        }
        catch (Exception ex)
        {
            error = $"Unable to write navigation waypoint file '{resolvedFile}': {ex.Message}";
            return null;
        }

        var writtenConfiguration = WaypointNavigationConfigurationLoader.TryLoad(resolvedFile, out error);
        if (writtenConfiguration is null ||
            !writtenConfiguration.Waypoints.TryGetValue(normalizedId, out var waypoint))
        {
            error ??= $"Waypoint '{normalizedId}' was not found after writing '{resolvedFile}'.";
            return null;
        }

        error = null;
        return waypoint;
    }

    private static bool TryLoadDocument(
        string filePath,
        out NavigationWaypointFileDocument document,
        out string? error)
    {
        try
        {
            var json = File.ReadAllText(filePath);
            var parsed = JsonSerializer.Deserialize<NavigationWaypointFileDocument>(json, ReadOptions);
            if (parsed is null)
            {
                document = default!;
                error = $"Navigation waypoint file '{filePath}' did not contain a readable document.";
                return false;
            }

            document = parsed;
            error = null;
            return true;
        }
        catch (Exception ex)
        {
            document = default!;
            error = $"Unable to load navigation waypoint file '{filePath}': {ex.Message}";
            return false;
        }
    }

    private static NavigationWaypointFileDocument CreateDefaultDocument() =>
        new(
            SchemaVersion: SupportedSchemaVersion,
            Provenance: null,
            Movement: CreateDefaultMovement(),
            Waypoints: []);

    private static NavigationMovementOptionsDocument CreateDefaultMovement() =>
        new(
            ForwardKey: "w",
            RunKey: null,
            WalkKey: null,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: 250,
            PostPulseSampleDelayMilliseconds: 150,
            StartRadius: 2.0d,
            DefaultArrivalRadius: 1.5d,
            NoProgressWindowMilliseconds: 1500,
            MinimumProgressDistance: 0.35d,
            WrongWayToleranceDistance: 0.75d,
            MaxTravelSeconds: 30);

    private static string? NormalizeOptional(string? value) =>
        string.IsNullOrWhiteSpace(value) ? null : value.Trim();
}
