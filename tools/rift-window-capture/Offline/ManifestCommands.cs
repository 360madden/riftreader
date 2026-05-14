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
        string? runLog = null;
        string? summary = null;
        bool manifestExists = File.Exists(manifestPath);
        bool jsonParsed = false;
        bool artifactPathsExist = false;

        if (!manifestExists)
        {
            blockers.Add($"Manifest not found: {manifestPath}");
            return new ManifestInspectionReport(options.Command, false, manifestPath, false, false, null, null, null, null, null, null, false, blockers.ToArray(), warnings.ToArray());
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
        }

        artifactPathsExist =
            (runLog is null || File.Exists(runLog)) &&
            (summary is null || File.Exists(summary)) &&
            (outputImage is null || File.Exists(outputImage));

        bool ok = blockers.Count == 0;
        return new ManifestInspectionReport(options.Command, ok, manifestPath, manifestExists, jsonParsed, schema, status, runId, runLog, summary, outputImage, artifactPathsExist, blockers.ToArray(), warnings.ToArray());
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
    bool ArtifactPathsExist,
    string[] Blockers,
    string[] Warnings);
