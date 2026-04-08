namespace RiftReader.Reader.Scanning;

public static class StringScanTextFormatter
{
    public static string Format(StringScanResult result)
    {
        var lines = new List<string>
        {
            $"Process:             {result.ProcessName} ({result.ProcessId})",
            $"Search text:         {result.SearchText}",
            $"Search source:       {result.SearchSource}",
            $"Encoding:            {result.Encoding}",
            $"Context bytes:       {result.ContextBytes}",
            $"Max hits:            {result.MaxHits}",
            $"Hits found:          {result.HitCount}"
        };

        if (result.Hits.Count == 0)
        {
            lines.Add("Matches:             none");
            return string.Join(Environment.NewLine, lines);
        }

        lines.Add("Matches:");

        for (var index = 0; index < result.Hits.Count; index++)
        {
            var hit = result.Hits[index];
            lines.Add($"  {index + 1,2}. {hit.AddressHex}  [{hit.Encoding}]  region {hit.RegionBaseHex} ({hit.RegionSize} bytes)");

            if (!string.IsNullOrWhiteSpace(hit.Classification))
            {
                lines.Add($"      kind  : {hit.Classification}");
            }

            if (hit.Context is not null)
            {
                lines.Add($"      window: {hit.Context.WindowStart} ({hit.Context.WindowLength} bytes)");
                lines.Add($"      ascii : {hit.Context.AsciiPreview}");
                lines.Add($"      utf16 : {hit.Context.Utf16Preview}");
                lines.Add($"      bytes : {hit.Context.BytesHex}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }
}
