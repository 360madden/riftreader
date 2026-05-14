static class Defaults
{
    public const int TimeoutMs = 2_500;
    public static readonly TimeSpan ProcessStartTolerance = TimeSpan.FromSeconds(2);

    public static string CreateDefaultOutputPath()
    {
        string root = Path.Combine(Path.GetTempPath(), "RiftReader-window-capture", "wgc");
        return Path.Combine(root, $"capture-{DateTime.Now:yyyyMMdd-HHmmss-fff}.bmp");
    }

    public static string CreateDefaultBenchmarkOutputRoot()
    {
        string root = Path.Combine(Path.GetTempPath(), "RiftReader-window-capture", "benchmark");
        return Path.Combine(root, $"benchmark-{DateTime.Now:yyyyMMdd-HHmmss-fff}");
    }
}
