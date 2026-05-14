[JsonSerializable(typeof(QualityReport))]
[JsonSerializable(typeof(RawFrameMetadata))]
[JsonSerializable(typeof(CaptureReport))]
[JsonSerializable(typeof(CaptureRunManifest))]
[JsonSerializable(typeof(ManifestInspectionReport))]
[JsonSerializable(typeof(OfflineFrameReport))]
[JsonSerializable(typeof(BenchmarkReport))]
[JsonSourceGenerationOptions(WriteIndented = true, PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
partial class CaptureJsonContext : JsonSerializerContext;
