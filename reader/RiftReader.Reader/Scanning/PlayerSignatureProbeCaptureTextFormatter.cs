namespace RiftReader.Reader.Scanning;

public static class PlayerSignatureProbeCaptureTextFormatter
{
    public static string Format(PlayerSignatureProbeCapture capture)
    {
        var lines = new List<string>
        {
            $"Process:             {capture.ProcessName} ({capture.ProcessId})",
            $"Search label:        {capture.SearchLabel}",
            $"Family:              {capture.FamilyId}",
            $"Kind:                {capture.FamilyNotes}",
            $"Signature:           {capture.Signature}",
            $"Selection source:    {capture.SelectionSource}",
            $"Confirmation file:   {capture.ConfirmationFile ?? "n/a"}",
            $"CE confirmed hits:   {capture.CeConfirmedSampleCount}",
            $"Label:               {capture.Label ?? "n/a"}",
            $"Output file:         {capture.OutputFile ?? "n/a"}",
            $"Samples:             {capture.HitCount}"
        };

        for (var index = 0; index < capture.Samples.Count; index++)
        {
            var sample = capture.Samples[index];
            lines.Add($"  {index + 1,2}. {sample.AddressHex}  lvl {sample.Level?.ToString() ?? "n/a"}  hp {sample.Health?.ToString() ?? "n/a"}  xyz {FormatFloat(sample.CoordX)}, {FormatFloat(sample.CoordY)}, {FormatFloat(sample.CoordZ)}  loc {sample.Location ?? "n/a"}  name {sample.Name ?? "n/a"}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatFloat(float? value) =>
        value.HasValue
            ? value.Value.ToString("0.00000", System.Globalization.CultureInfo.InvariantCulture)
            : "n/a";
}
