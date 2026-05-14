static class TextureSaver
{
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

    public static QualityReport SaveFrameToImage(D3DObjects d3d, WgiD3D.IDirect3DSurface surface, string output, bool emitPng, string? rawOutput, string? cropImageRoot, string? cropRawRoot, string[] cropProfiles)
    {
        using ID3D11Texture2D source = Direct3D11Helpers.GetTexture2D(surface);
        return SaveTextureToImage(d3d, source, output, emitPng, rawOutput, cropImageRoot, cropRawRoot, cropProfiles);
    }

    public static QualityReport SaveTextureToImage(D3DObjects d3d, ID3D11Texture2D source, string output, bool emitPng, string? rawOutput, string? cropImageRoot, string? cropRawRoot, string[] cropProfiles)
    {
        Texture2DDescription sourceDescription = source.Description;
        int width = (int)sourceDescription.Width;
        int height = (int)sourceDescription.Height;

        Texture2DDescription stagingDescription = new(
            Format.B8G8R8A8_UNorm,
            (uint)width,
            (uint)height,
            1,
            1,
            BindFlags.None,
            ResourceUsage.Staging,
            CpuAccessFlags.Read,
            1,
            0,
            ResourceOptionFlags.None);

        using ID3D11Texture2D staging = d3d.Device.CreateTexture2D(stagingDescription);
        d3d.Context.CopyResource(staging, source);

        d3d.Context.Map(staging, 0, MapMode.Read, Vortice.Direct3D11.MapFlags.None, out MappedSubresource mapped).CheckError();
        try
        {
            return SaveMappedBgraImage(mapped, width, height, output, emitPng, rawOutput, cropImageRoot, cropRawRoot, cropProfiles) with
            {
                SourceTextureFormat = sourceDescription.Format.ToString(),
                SourceTextureUsage = sourceDescription.Usage.ToString(),
                SourceTextureBindFlags = sourceDescription.BindFlags.ToString(),
                SourceTextureCpuAccessFlags = sourceDescription.CPUAccessFlags.ToString(),
                SourceTextureMiscFlags = sourceDescription.MiscFlags.ToString(),
            };
        }
        finally
        {
            d3d.Context.Unmap(staging, 0);
        }
    }

    private static QualityReport SaveMappedBgraImage(MappedSubresource mapped, int width, int height, string output, bool emitPng, string? rawOutput, string? cropImageRoot, string? cropRawRoot, string[] cropProfiles)
    {
        long pixelCount = (long)width * height;
        long blackPixels = 0;
        long transparentPixels = 0;
        double lumaSum = 0;
        double lumaSquaredSum = 0;
        const int contentTop = 40;
        long contentPixelCount = 0;
        long contentBlackPixels = 0;
        long contentTransparentPixels = 0;
        double contentLumaSum = 0;
        double contentLumaSquaredSum = 0;
        byte[] row = new byte[width * 4];
        byte[] image = new byte[checked(width * height * 4)];

        for (int y = 0; y < height; y++)
        {
            IntPtr sourceRow = IntPtr.Add(mapped.DataPointer, y * (int)mapped.RowPitch);
            Marshal.Copy(sourceRow, row, 0, row.Length);
            Buffer.BlockCopy(row, 0, image, y * row.Length, row.Length);

            for (int x = 0; x < row.Length; x += 4)
            {
                byte b = row[x];
                byte g = row[x + 1];
                byte r = row[x + 2];
                byte a = row[x + 3];
                if (a == 0)
                {
                    transparentPixels++;
                }

                if (r < 4 && g < 4 && b < 4)
                {
                    blackPixels++;
                }

                double luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
                lumaSum += luma;
                lumaSquaredSum += luma * luma;

                if (y >= contentTop)
                {
                    contentPixelCount++;
                    if (a == 0)
                    {
                        contentTransparentPixels++;
                    }

                    if (r < 4 && g < 4 && b < 4)
                    {
                        contentBlackPixels++;
                    }

                    contentLumaSum += luma;
                    contentLumaSquaredSum += luma * luma;
                }
            }
        }

        BgraFrame frame = new(width, height, width * 4, "BGRA32", "top-down", image);
        string actualOutput = NormalizeImageOutputPath(output, emitPng);
        if (string.Equals(Path.GetExtension(actualOutput), ".png", StringComparison.OrdinalIgnoreCase))
        {
            WriteTopDownBgraPng(actualOutput, frame);
        }
        else
        {
            WriteTopDownBgraBmp(actualOutput, frame);
        }

        RawFrameWriteResult? raw = rawOutput is null ? null : WriteTopDownBgraRaw(rawOutput, frame);
        CropOutput[] cropOutputs = WriteCropOutputs(frame, cropProfiles, cropImageRoot, cropRawRoot);

        double mean = pixelCount == 0 ? 0 : lumaSum / pixelCount;
        double variance = pixelCount == 0 ? 0 : Math.Max(0, (lumaSquaredSum / pixelCount) - (mean * mean));
        double stdDev = Math.Sqrt(variance);
        double blackRatio = pixelCount == 0 ? 1 : blackPixels / (double)pixelCount;
        double transparentRatio = pixelCount == 0 ? 1 : transparentPixels / (double)pixelCount;
        double contentMean = contentPixelCount == 0 ? 0 : contentLumaSum / contentPixelCount;
        double contentVariance = contentPixelCount == 0 ? 0 : Math.Max(0, (contentLumaSquaredSum / contentPixelCount) - (contentMean * contentMean));
        double contentStdDev = Math.Sqrt(contentVariance);
        double contentBlackRatio = contentPixelCount == 0 ? 1 : contentBlackPixels / (double)contentPixelCount;
        double contentTransparentRatio = contentPixelCount == 0 ? 1 : contentTransparentPixels / (double)contentPixelCount;
        bool usable = contentPixelCount > 0 && contentTransparentRatio < 0.95 && contentBlackRatio < 0.98 && contentStdDev >= 2.0;

        return new QualityReport(width, height, frame.StrideBytes, frame.PixelFormat, frame.Orientation, blackRatio, transparentRatio, stdDev, contentBlackRatio, contentTransparentRatio, contentStdDev, usable, actualOutput)
        {
            RawOutput = raw?.RawPath,
            RawMetadata = raw?.MetadataPath,
            CropOutputs = cropOutputs,
        };
    }

    private static void WriteTopDownBgraBmp(string output, BgraFrame frame)
    {
        output = Path.GetFullPath(output);
        string parent = Path.GetDirectoryName(output) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        int imageBytes = checked(frame.Width * frame.Height * 4);
        int fileBytes = checked(14 + 40 + imageBytes);

        using FileStream stream = new(output, FileMode.Create, FileAccess.Write, FileShare.Read);
        using BinaryWriter writer = new(stream, Encoding.UTF8, leaveOpen: false);
        writer.Write((byte)'B');
        writer.Write((byte)'M');
        writer.Write(fileBytes);
        writer.Write(0);
        writer.Write(14 + 40);
        writer.Write(40);
        writer.Write(frame.Width);
        writer.Write(-frame.Height);
        writer.Write((ushort)1);
        writer.Write((ushort)32);
        writer.Write(0);
        writer.Write(imageBytes);
        writer.Write(2835);
        writer.Write(2835);
        writer.Write(0);
        writer.Write(0);
        writer.Write(frame.Pixels);
    }

    private static void WriteTopDownBgraPng(string output, BgraFrame frame)
    {
        output = Path.GetFullPath(output);
        string parent = Path.GetDirectoryName(output) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        using Bitmap bitmap = new(frame.Width, frame.Height, PixelFormat.Format32bppArgb);
        Rectangle rectangle = new(0, 0, frame.Width, frame.Height);
        BitmapData data = bitmap.LockBits(rectangle, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try
        {
            int rowBytes = checked(frame.Width * 4);
            for (int y = 0; y < frame.Height; y++)
            {
                IntPtr destination = IntPtr.Add(data.Scan0, y * data.Stride);
                Marshal.Copy(frame.Pixels, y * rowBytes, destination, rowBytes);
            }
        }
        finally
        {
            bitmap.UnlockBits(data);
        }

        bitmap.Save(output, ImageFormat.Png);
    }

    private static RawFrameWriteResult WriteTopDownBgraRaw(string output, BgraFrame frame)
    {
        string rawPath = Path.ChangeExtension(Path.GetFullPath(output), ".bgra");
        string metadataPath = Path.ChangeExtension(rawPath, ".frame.json");
        string parent = Path.GetDirectoryName(rawPath) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        File.WriteAllBytes(rawPath, frame.Pixels);
        RawFrameMetadata metadata = new(
            "rift-window-capture-raw-frame/v1",
            Path.GetFileName(rawPath),
            DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            frame.Width,
            frame.Height,
            frame.StrideBytes,
            frame.PixelFormat,
            frame.Orientation,
            "none",
            "bgra-top-down");
        File.WriteAllText(metadataPath, JsonSerializer.Serialize(metadata, CaptureJsonContext.Default.RawFrameMetadata), Utf8NoBom);
        return new RawFrameWriteResult(rawPath, metadataPath);
    }

    private static CropOutput[] WriteCropOutputs(BgraFrame frame, string[] cropProfiles, string? cropImageRoot, string? cropRawRoot)
    {
        string[] profiles = cropProfiles
            .Select(CropProfileRegistry.Normalize)
            .Distinct(StringComparer.Ordinal)
            .Where(profile => !string.Equals(profile, "full-window", StringComparison.Ordinal))
            .ToArray();
        if (profiles.Length == 0)
        {
            return [];
        }

        string imageRoot = Path.GetFullPath(cropImageRoot ?? Path.Combine(Environment.CurrentDirectory, "crops"));
        Directory.CreateDirectory(imageRoot);
        if (cropRawRoot is not null)
        {
            Directory.CreateDirectory(cropRawRoot);
        }

        List<CropOutput> outputs = [];
        foreach (string profile in profiles)
        {
            CropRectangle rectangle = CropProfileRegistry.Resolve(profile, frame.Width, frame.Height);
            if (rectangle.Width <= 0 || rectangle.Height <= 0)
            {
                continue;
            }

            BgraFrame cropped = Crop(frame, rectangle);
            string imageOutput = Path.Combine(imageRoot, $"{profile}.png");
            WriteTopDownBgraPng(imageOutput, cropped);
            RawFrameWriteResult? raw = cropRawRoot is null
                ? null
                : WriteTopDownBgraRaw(Path.Combine(cropRawRoot, $"{profile}.bgra"), cropped);
            outputs.Add(new CropOutput(profile, rectangle.X, rectangle.Y, rectangle.Width, rectangle.Height, Path.GetFullPath(imageOutput), raw?.RawPath, raw?.MetadataPath));
        }

        return outputs.ToArray();
    }

    private static BgraFrame Crop(BgraFrame frame, CropRectangle rectangle)
    {
        int stride = checked(rectangle.Width * 4);
        byte[] pixels = new byte[checked(stride * rectangle.Height)];
        for (int y = 0; y < rectangle.Height; y++)
        {
            int sourceOffset = ((rectangle.Y + y) * frame.StrideBytes) + (rectangle.X * 4);
            int destinationOffset = y * stride;
            Buffer.BlockCopy(frame.Pixels, sourceOffset, pixels, destinationOffset, stride);
        }

        return new BgraFrame(rectangle.Width, rectangle.Height, stride, frame.PixelFormat, frame.Orientation, pixels);
    }

    public static string NormalizeImageOutputPath(string output, bool emitPng)
    {
        string full = Path.GetFullPath(output);
        string extension = Path.GetExtension(full);
        if (emitPng || string.Equals(extension, ".png", StringComparison.OrdinalIgnoreCase))
        {
            return Path.ChangeExtension(full, ".png");
        }

        return Path.ChangeExtension(full, ".bmp");
    }

    public static string CreateAttemptOutputPath(string output, int attempt, bool emitPng)
    {
        string imageOutput = NormalizeImageOutputPath(output, emitPng);
        string directory = Path.GetDirectoryName(imageOutput) ?? Environment.CurrentDirectory;
        string fileName = Path.GetFileNameWithoutExtension(imageOutput);
        string extension = Path.GetExtension(imageOutput);
        return Path.Combine(directory, $"{fileName}.attempt{attempt}{extension}");
    }

    public static string CreateAttemptRawOutputPath(string rawOutput, int attempt)
    {
        string rawPath = Path.ChangeExtension(Path.GetFullPath(rawOutput), ".bgra");
        string directory = Path.GetDirectoryName(rawPath) ?? Environment.CurrentDirectory;
        string fileName = Path.GetFileNameWithoutExtension(rawPath);
        return Path.Combine(directory, $"{fileName}.attempt{attempt}.bgra");
    }
}

sealed record BgraFrame(int Width, int Height, int StrideBytes, string PixelFormat, string Orientation, byte[] Pixels);

sealed record RawFrameWriteResult(string RawPath, string MetadataPath);

sealed record RawFrameMetadata(
    string Schema,
    string RawFrame,
    string CreatedAtUtc,
    int Width,
    int Height,
    int StrideBytes,
    string PixelFormat,
    string Orientation,
    string RowPadding,
    string Layout);

sealed record QualityReport(
    int Width,
    int Height,
    int StrideBytes,
    string PixelFormat,
    string Orientation,
    double BlackPixelRatio,
    double TransparentPixelRatio,
    double LumaStdDev,
    double ContentBlackPixelRatio,
    double ContentTransparentPixelRatio,
    double ContentLumaStdDev,
    bool Usable,
    string Output)
{
    public string? RawOutput { get; init; }
    public string? RawMetadata { get; init; }
    public CropOutput[] CropOutputs { get; init; } = [];
    public string? SourceTextureFormat { get; init; }
    public string? SourceTextureUsage { get; init; }
    public string? SourceTextureBindFlags { get; init; }
    public string? SourceTextureCpuAccessFlags { get; init; }
    public string? SourceTextureMiscFlags { get; init; }
    public int? CaptureAttemptCount { get; init; }
    public int? CompletedAttemptCount { get; init; }
    public int? SelectedAttempt { get; init; }
    public string? LastAttemptError { get; init; }
    public string? DesktopDuplicationDeviceName { get; init; }
    public string? DesktopDuplicationDesktopCoordinates { get; init; }
    public string? DesktopDuplicationRotation { get; init; }
    public string? DesktopDuplicationModeDescription { get; init; }
    public string? DesktopDuplicationModeFormat { get; init; }
    public bool? DesktopDuplicationDesktopImageInSystemMemory { get; init; }
    public int? DesktopDuplicationAccumulatedFrames { get; init; }
    public bool? DesktopDuplicationProtectedContentMaskedOut { get; init; }
    public bool? DesktopDuplicationPointerVisible { get; init; }
    public string? DesktopDuplicationPointerPosition { get; init; }
}
