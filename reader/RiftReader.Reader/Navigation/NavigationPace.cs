namespace RiftReader.Reader.Navigation;

public static class NavigationPace
{
    public const string Keep = "keep";
    public const string Run = "run";
    public const string Walk = "walk";

    public static bool TryNormalize(string? value, out string normalized)
    {
        normalized = Keep;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        switch (value.Trim().ToLowerInvariant())
        {
            case Keep:
                normalized = Keep;
                return true;

            case Run:
                normalized = Run;
                return true;

            case Walk:
                normalized = Walk;
                return true;

            default:
                return false;
        }
    }
}
