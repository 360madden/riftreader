static class ManifestCommands
{
    public static ManifestInspectionReport Run(Options options)
    {
        string manifestPath = Path.GetFullPath(options.ManifestPath ?? throw new InvalidOperationException("--manifest is required."));
        List<string> blockers = [];
        List<string> warnings = [];
        string? schema = null;
        string? status = null;
        string? runId = null;
        string? outputImage = null;
        string? outputRaw = null;
        string? outputRawMetadata = null;
        List<string> cropImages = [];
        List<string> cropRaws = [];
        List<string> cropRawMetadata = [];
        string? runLog = null;
        string? summary = null;
        bool manifestExists = File.Exists(manifestPath);
        bool jsonParsed = false;
        bool artifactPathsExist = false;

        if (!manifestExists)
        {
            blockers.Add($"Manifest not found: {manifestPath}");
            return new ManifestInspectionReport(options.Command, false, manifestPath, false, false, null, null, null, null, null, null, null, null, 0, false, blockers.ToArray(), warnings.ToArray());
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(manifestPath, Encoding.UTF8));
            JsonElement root = document.RootElement;
            jsonParsed = true;
            schema = ReadString(root, "schema");
            status = ReadString(root, "status");
            runId = ReadString(root, "runId");
            if (!string.Equals(schema, "rift-window-capture-manifest/v1", StringComparison.Ordinal))
            {
                blockers.Add($"Unexpected manifest schema: {schema ?? "<missing>"}");
            }

            if (string.IsNullOrWhiteSpace(status))
            {
                blockers.Add("Manifest is missing status.");
            }

            if (root.TryGetProperty("artifacts", out JsonElement artifacts))
            {
                runLog = ResolveArtifact(manifestPath, ReadString(artifacts, "runLogJsonl"));
                summary = ResolveArtifact(manifestPath, ReadString(artifacts, "summaryMarkdown"));
                outputImage = ResolveArtifact(manifestPath, ReadString(artifacts, "fullWindowImage"));
                outputRaw = ResolveArtifact(manifestPath, ReadString(artifacts, "fullWindowRaw"));
                outputRawMetadata = ResolveArtifact(manifestPath, ReadString(artifacts, "fullWindowRawMetadata"));
                if (artifacts.TryGetProperty("crops", out JsonElement crops) && crops.ValueKind == JsonValueKind.Array)
                {
                    foreach (JsonElement crop in crops.EnumerateArray())
                    {
                        AddIfNotNull(cropImages, ResolveArtifact(manifestPath, ReadString(crop, "imageOutput")));
                        AddIfNotNull(cropRaws, ResolveArtifact(manifestPath, ReadString(crop, "rawOutput")));
                        AddIfNotNull(cropRawMetadata, ResolveArtifact(manifestPath, ReadString(crop, "rawMetadata")));
                    }
                }
            }
            else
            {
                blockers.Add("Manifest is missing artifacts object.");
            }
        }
        catch (Exception ex)
        {
            blockers.Add($"Manifest JSON parse failed: {ex.Message}");
        }

        if (options.Command == "validate" && jsonParsed)
        {
            if (runLog is null || !File.Exists(runLog))
            {
                blockers.Add("Run log JSONL artifact is missing.");
            }
            else if (!JsonlLooksValid(runLog, out string? jsonlError))
            {
                blockers.Add($"Run log JSONL is invalid: {jsonlError}");
            }

            if (summary is null || !File.Exists(summary))
            {
                blockers.Add("Summary Markdown artifact is missing.");
            }

            if (string.Equals(status, "passed", StringComparison.OrdinalIgnoreCase))
            {
                if (outputImage is null || !File.Exists(outputImage))
                {
                    blockers.Add("Passed capture manifest is missing fullWindowImage artifact.");
                }
                else if (new FileInfo(outputImage).Length <= 0)
                {
                    blockers.Add("fullWindowImage artifact is empty.");
                }

                if (outputRaw is not null && (!File.Exists(outputRaw) || new FileInfo(outputRaw).Length <= 0))
                {
                    blockers.Add("fullWindowRaw artifact is missing or empty.");
                }

                if (outputRawMetadata is not null && !File.Exists(outputRawMetadata))
                {
                    blockers.Add("fullWindowRawMetadata artifact is missing.");
                }

                foreach (string cropImage in cropImages)
                {
                    if (!File.Exists(cropImage) || new FileInfo(cropImage).Length <= 0)
                    {
                        blockers.Add($"Crop image artifact is missing or empty: {cropImage}");
                    }
                }

                foreach (string cropRaw in cropRaws)
                {
                    if (!File.Exists(cropRaw) || new FileInfo(cropRaw).Length <= 0)
                    {
                        blockers.Add($"Crop raw artifact is missing or empty: {cropRaw}");
                    }
                }

                foreach (string cropMetadata in cropRawMetadata)
                {
                    if (!File.Exists(cropMetadata))
                    {
                        blockers.Add($"Crop raw metadata artifact is missing: {cropMetadata}");
                    }
                }
            }
        }
        else if (options.Command == "inspect")
        {
            if (runLog is not null && !File.Exists(runLog))
            {
                warnings.Add("Run log artifact path does not exist.");
            }

            if (summary is not null && !File.Exists(summary))
            {
                warnings.Add("Summary artifact path does not exist.");
            }

            if (outputImage is not null && !File.Exists(outputImage))
            {
                warnings.Add("fullWindowImage artifact path does not exist.");
            }

            if (outputRaw is not null && !File.Exists(outputRaw))
            {
                warnings.Add("fullWindowRaw artifact path does not exist.");
            }

            if (outputRawMetadata is not null && !File.Exists(outputRawMetadata))
            {
                warnings.Add("fullWindowRawMetadata artifact path does not exist.");
            }

            foreach (string cropImage in cropImages.Where(path => !File.Exists(path)))
            {
                warnings.Add($"Crop image artifact path does not exist: {cropImage}");
            }

            foreach (string cropRaw in cropRaws.Where(path => !File.Exists(path)))
            {
                warnings.Add($"Crop raw artifact path does not exist: {cropRaw}");
            }

            foreach (string cropMetadata in cropRawMetadata.Where(path => !File.Exists(path)))
            {
                warnings.Add($"Crop raw metadata artifact path does not exist: {cropMetadata}");
            }
        }

        artifactPathsExist =
            (runLog is null || File.Exists(runLog)) &&
            (summary is null || File.Exists(summary)) &&
            (outputImage is null || File.Exists(outputImage)) &&
            (outputRaw is null || File.Exists(outputRaw)) &&
            (outputRawMetadata is null || File.Exists(outputRawMetadata)) &&
            cropImages.All(File.Exists) &&
            cropRaws.All(File.Exists) &&
            cropRawMetadata.All(File.Exists);

        bool ok = blockers.Count == 0;
        return new ManifestInspectionReport(options.Command, ok, manifestPath, manifestExists, jsonParsed, schema, status, runId, runLog, summary, outputImage, outputRaw, outputRawMetadata, cropImages.Count, artifactPathsExist, blockers.ToArray(), warnings.ToArray());
    }

    private static string? ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static string? ResolveArtifact(string manifestPath, string? artifactPath)
    {
        if (string.IsNullOrWhiteSpace(artifactPath))
        {
            return null;
        }

        return Path.IsPathRooted(artifactPath)
            ? Path.GetFullPath(artifactPath)
            : Path.GetFullPath(Path.Combine(Path.GetDirectoryName(manifestPath) ?? Environment.CurrentDirectory, artifactPath));
    }

    private static void AddIfNotNull(List<string> values, string? value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            values.Add(value);
        }
    }

    private static bool JsonlLooksValid(string path, out string? error)
    {
        int lineNumber = 0;
        foreach (string line in File.ReadLines(path, Encoding.UTF8))
        {
            lineNumber++;
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                using JsonDocument _ = JsonDocument.Parse(line);
            }
            catch (Exception ex)
            {
                error = $"line {lineNumber}: {ex.Message}";
                return false;
            }
        }

        error = null;
        return true;
    }
}

sealed record ManifestInspectionReport(
    string Command,
    bool Ok,
    string Manifest,
    bool ManifestExists,
    bool JsonParsed,
    string? Schema,
    string? Status,
    string? RunId,
    string? RunLog,
    string? Summary,
    string? FullWindowImage,
    string? FullWindowRaw,
    string? FullWindowRawMetadata,
    int CropCount,
    bool ArtifactPathsExist,
    string[] Blockers,
    string[] Warnings);
