namespace RiftReader.Reader.Scanning;

public static class PlayerSignatureScanTextFormatter
{
    public static string Format(PlayerSignatureScanResult result)
    {
        var lines = new List<string>
        {
            $"Process:             {result.ProcessName} ({result.ProcessId})",
            $"Search label:        {result.SearchLabel}",
            $"Inspection radius:   {result.InspectionRadius}",
            $"Candidates ranked:   {result.CandidateCount}",
            $"Raw hits:            {result.RawHitCount}",
            $"Families:            {result.FamilyCount}",
            $"Max hits:            {result.MaxHits}",
            $"Hits found:          {result.HitCount}"
        };

        if (result.Hits.Count == 0)
        {
            lines.Add("Matches:             none");
            return string.Join(Environment.NewLine, lines);
        }

        if (result.Families.Count > 0)
        {
            lines.Add("Families:");

            for (var index = 0; index < result.Families.Count; index++)
            {
                var family = result.Families[index];
                lines.Add($"  {index + 1,2}. {family.FamilyId}  hits {family.HitCount}  best-score {family.BestScore}  rep {family.RepresentativeAddressHex}");
                lines.Add($"      kind : {family.Notes}");
                lines.Add($"      shape: {family.Signature}");
                lines.Add($"      seen : {string.Join(", ", family.SampleAddresses)}");
            }
        }

        lines.Add("Representatives:");

        for (var index = 0; index < result.Hits.Count; index++)
        {
            var hit = result.Hits[index];
            lines.Add($"  {index + 1,2}. {hit.AddressHex}  score {hit.Score}  family {hit.FamilyId} ({hit.FamilyHitCount} hits)  region {hit.RegionBaseHex} ({hit.RegionSize} bytes)");

            foreach (var signal in hit.Signals)
            {
                lines.Add($"      + {signal.Name} @ {signal.RelativeOffset:+#;-#;0}: {signal.Value}");
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
