sealed record CropRectangle(int X, int Y, int Width, int Height);

static class CropProfileRegistry
{
    public static readonly string[] Supported =
    [
        "full-window",
        "content",
        "top-strip",
        "bottom-strip",
        "telemetry-strip",
    ];

    public static string Normalize(string value)
    {
        string normalized = value.Trim().ToLowerInvariant();
        if (!Supported.Contains(normalized, StringComparer.Ordinal))
        {
            throw new ArgumentException($"Unsupported --crop profile: {value}. Supported: {string.Join(", ", Supported)}.");
        }

        return normalized;
    }

    public static CropRectangle Resolve(string profile, int frameWidth, int frameHeight)
    {
        int safeWidth = Math.Max(0, frameWidth);
        int safeHeight = Math.Max(0, frameHeight);
        int stripHeight = Math.Min(96, safeHeight);
        return Normalize(profile) switch
        {
            "full-window" => new CropRectangle(0, 0, safeWidth, safeHeight),
            "content" => ResolveContent(safeWidth, safeHeight),
            "top-strip" => new CropRectangle(0, 0, safeWidth, stripHeight),
            "bottom-strip" => new CropRectangle(0, Math.Max(0, safeHeight - stripHeight), safeWidth, stripHeight),
            "telemetry-strip" => new CropRectangle(0, 0, safeWidth, stripHeight),
            _ => throw new ArgumentOutOfRangeException(nameof(profile), profile, "Unsupported crop profile."),
        };
    }

    private static CropRectangle ResolveContent(int frameWidth, int frameHeight)
    {
        int top = Math.Min(40, frameHeight);
        return new CropRectangle(0, top, frameWidth, Math.Max(0, frameHeight - top));
    }
}

sealed record CropOutput(
    string Profile,
    int X,
    int Y,
    int Width,
    int Height,
    string ImageOutput,
    string? RawOutput,
    string? RawMetadata);
