static class OfflineFrameCommands
{
    public static OfflineFrameReport Run(Options options)
    {
        try
        {
            return options.Command switch
            {
                "convert" => Convert(options),
                "crop" => Crop(options),
                "diff" => Diff(options),
                _ => OfflineFrameReport.Blocked(options.Command, $"Unsupported offline command: {options.Command}"),
            };
        }
        catch (Exception ex)
        {
            return OfflineFrameReport.Blocked(options.Command, ex.Message, ex.GetType().Name);
        }
    }

    private static OfflineFrameReport Convert(Options options)
    {
        RawFrameMetadata metadata = ReadMetadata(Required(options.MetadataPath, "--metadata"));
        BgraFrame frame = ReadRawFrame(Required(options.RawPath, "--raw"), metadata);
        string png = Path.GetFullPath(Required(options.PngPath, "--png"));
        TextureSaver.WriteTopDownBgraPng(png, frame);
        return OfflineFrameReport.Passed(
            "convert",
            $"Converted raw BGRA to {png}.",
            width: frame.Width,
            height: frame.Height,
            outputPng: png);
    }

    private static OfflineFrameReport Crop(Options options)
    {
        (string rawPath, string metadataPath) = ResolveRawInputs(options);
        RawFrameMetadata metadata = ReadMetadata(metadataPath);
        BgraFrame frame = ReadRawFrame(rawPath, metadata);
        string profile = Required(options.Profile, "--profile");
        CropRectangle rectangle = CropProfileRegistry.Resolve(profile, frame.Width, frame.Height);
        if (rectangle.Width <= 0 || rectangle.Height <= 0)
        {
            return OfflineFrameReport.Blocked("crop", $"Crop profile {profile} resolved to an empty rectangle for {frame.Width}x{frame.Height}.");
        }

        BgraFrame cropped = TextureSaver.Crop(frame, rectangle);
        string outputRoot = Path.GetFullPath(options.OutputRoot ?? Path.Combine("scripts", "captures", $"rift-window-capture-offline-crop-{DateTime.Now:yyyyMMdd-HHmmss-fff}"));
        string outputPng = Path.GetFullPath(options.PngPath ?? Path.Combine(outputRoot, "images", "crops", $"{profile}.png"));
        TextureSaver.WriteTopDownBgraPng(outputPng, cropped);
        RawFrameWriteResult? raw = options.EmitRawBgra
            ? TextureSaver.WriteTopDownBgraRaw(Path.Combine(outputRoot, "raw", "crops", $"{profile}.bgra"), cropped)
            : null;

        return OfflineFrameReport.Passed(
            "crop",
            $"Cropped {profile} to {outputPng}.",
            width: cropped.Width,
            height: cropped.Height,
            outputPng: outputPng,
            outputRaw: raw?.RawPath,
            outputMetadata: raw?.MetadataPath,
            cropProfile: profile,
            x: rectangle.X,
            y: rectangle.Y);
    }

    private static OfflineFrameReport Diff(Options options)
    {
        RawFrameMetadata metadata = ReadMetadata(Required(options.MetadataPath, "--metadata"));
        BgraFrame before = ReadRawFrame(Required(options.BeforePath, "--before"), metadata);
        BgraFrame after = ReadRawFrame(Required(options.AfterPath, "--after"), metadata);
        if (before.Width != after.Width || before.Height != after.Height || before.StrideBytes != after.StrideBytes)
        {
            return OfflineFrameReport.Blocked("diff", "Before/after raw frames do not share dimensions and stride.");
        }

        long pixelCount = (long)before.Width * before.Height;
        long changedPixels = 0;
        double lumaDeltaSum = 0;
        double maxLumaDelta = 0;
        for (int i = 0; i < before.Pixels.Length; i += 4)
        {
            byte beforeB = before.Pixels[i];
            byte beforeG = before.Pixels[i + 1];
            byte beforeR = before.Pixels[i + 2];
            byte afterB = after.Pixels[i];
            byte afterG = after.Pixels[i + 1];
            byte afterR = after.Pixels[i + 2];
            if (beforeB != afterB || beforeG != afterG || beforeR != afterR || before.Pixels[i + 3] != after.Pixels[i + 3])
            {
                changedPixels++;
            }

            double beforeLuma = (0.2126 * beforeR) + (0.7152 * beforeG) + (0.0722 * beforeB);
            double afterLuma = (0.2126 * afterR) + (0.7152 * afterG) + (0.0722 * afterB);
            double delta = Math.Abs(afterLuma - beforeLuma);
            lumaDeltaSum += delta;
            maxLumaDelta = Math.Max(maxLumaDelta, delta);
        }

        return OfflineFrameReport.Passed(
            "diff",
            $"Compared {pixelCount} pixels.",
            width: before.Width,
            height: before.Height,
            changedPixelCount: changedPixels,
            changedPixelRatio: pixelCount == 0 ? 0 : changedPixels / (double)pixelCount,
            meanAbsoluteLumaDelta: pixelCount == 0 ? 0 : lumaDeltaSum / pixelCount,
            maxAbsoluteLumaDelta: maxLumaDelta);
    }

    private static (string RawPath, string MetadataPath) ResolveRawInputs(Options options)
    {
        if (!string.IsNullOrWhiteSpace(options.ManifestPath))
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(Path.GetFullPath(options.ManifestPath), Encoding.UTF8));
            JsonElement artifacts = document.RootElement.GetProperty("artifacts");
            string manifestDirectory = Path.GetDirectoryName(Path.GetFullPath(options.ManifestPath)) ?? Environment.CurrentDirectory;
            string raw = ResolveManifestArtifact(manifestDirectory, artifacts.GetProperty("fullWindowRaw").GetString());
            string metadata = ResolveManifestArtifact(manifestDirectory, artifacts.GetProperty("fullWindowRawMetadata").GetString());
            return (raw, metadata);
        }

        return (Path.GetFullPath(Required(options.RawPath, "--raw")), Path.GetFullPath(Required(options.MetadataPath, "--metadata")));
    }

    private static string ResolveManifestArtifact(string manifestDirectory, string? artifact)
    {
        if (string.IsNullOrWhiteSpace(artifact))
        {
            throw new InvalidOperationException("Manifest does not contain required raw frame artifacts. Capture with --emit-raw-bgra first.");
        }

        return Path.IsPathRooted(artifact)
            ? Path.GetFullPath(artifact)
            : Path.GetFullPath(Path.Combine(manifestDirectory, artifact));
    }

    private static RawFrameMetadata ReadMetadata(string path)
    {
        path = Path.GetFullPath(path);
        if (!File.Exists(path))
        {
            throw new FileNotFoundException($"Raw frame metadata not found: {path}", path);
        }

        RawFrameMetadata? metadata = JsonSerializer.Deserialize(File.ReadAllText(path, Encoding.UTF8), CaptureJsonContext.Default.RawFrameMetadata);
        return metadata ?? throw new InvalidOperationException($"Raw frame metadata parsed as null: {path}");
    }

    private static BgraFrame ReadRawFrame(string path, RawFrameMetadata metadata)
    {
        path = Path.GetFullPath(path);
        if (!File.Exists(path))
        {
            throw new FileNotFoundException($"Raw frame not found: {path}", path);
        }

        byte[] pixels = File.ReadAllBytes(path);
        int expectedBytes = checked(metadata.Height * metadata.StrideBytes);
        if (pixels.Length != expectedBytes)
        {
            throw new InvalidOperationException($"Raw frame byte length {pixels.Length} does not match metadata height*stride {expectedBytes}.");
        }

        return new BgraFrame(metadata.Width, metadata.Height, metadata.StrideBytes, metadata.PixelFormat, metadata.Orientation, pixels);
    }

    private static string Required(string? value, string name) =>
        string.IsNullOrWhiteSpace(value) ? throw new InvalidOperationException($"{name} is required.") : value;
}

sealed record OfflineFrameReport(
    string Command,
    bool Ok,
    string Status,
    string Message,
    string? ErrorType,
    int? Width,
    int? Height,
    string? OutputPng,
    string? OutputRaw,
    string? OutputMetadata,
    string? CropProfile,
    int? X,
    int? Y,
    long? ChangedPixelCount,
    double? ChangedPixelRatio,
    double? MeanAbsoluteLumaDelta,
    double? MaxAbsoluteLumaDelta,
    string[] Blockers,
    string[] Warnings)
{
    public static OfflineFrameReport Passed(
        string command,
        string message,
        int? width = null,
        int? height = null,
        string? outputPng = null,
        string? outputRaw = null,
        string? outputMetadata = null,
        string? cropProfile = null,
        int? x = null,
        int? y = null,
        long? changedPixelCount = null,
        double? changedPixelRatio = null,
        double? meanAbsoluteLumaDelta = null,
        double? maxAbsoluteLumaDelta = null) =>
        new(command, true, "passed", message, null, width, height, outputPng, outputRaw, outputMetadata, cropProfile, x, y, changedPixelCount, changedPixelRatio, meanAbsoluteLumaDelta, maxAbsoluteLumaDelta, [], []);

    public static OfflineFrameReport Blocked(string command, string blocker, string? errorType = null) =>
        new(command, false, "blocked", blocker, errorType, null, null, null, null, null, null, null, null, null, null, null, null, [blocker], []);
}
