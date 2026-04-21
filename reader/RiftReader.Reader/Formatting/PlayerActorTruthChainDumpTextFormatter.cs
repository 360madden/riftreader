using System.Globalization;
using RiftReader.Reader.Models;
using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Formatting;

public static class PlayerActorTruthChainDumpTextFormatter
{
    public static string Format(PlayerActorTruthChainDumpResult result)
    {
        var lines = new List<string>
        {
            $"Process:                 {result.ProcessName} ({result.ProcessId})",
            $"ReaderBridge source:     {result.ReaderBridgeSourceFile}",
            $"Trace source:            {result.TraceSourceFile ?? "n/a"}",
            $"Window length:           {result.WindowLength}",
            $"Pointer width:           {result.PointerWidth}",
            $"Pointer scan max hits:   {result.PointerScanMaxHits}",
            $"Second-hop seeds:        {result.SecondHopSeedLimitPerSurface} per surface",
            $"Second-hop max hits:     {result.SecondHopPointerScanMaxHits}",
            $"Stability samples:       {result.StabilitySampleCount} @ {result.StabilitySampleDelayMilliseconds} ms",
            $"Unified truth object:    {result.UnifiedTruthObjectAddress ?? "n/a"}",
            $"Unified truth hits:      {result.UnifiedTruthObservationCount}",
            $"Coord object:            {result.Truth.Coordinates.ObjectBaseAddress ?? "n/a"}",
            $"Orientation object:      {result.Truth.Orientation.SelectedAddress}",
            $"Orientation parent:      {result.Truth.Orientation.ParentAddress}",
            $"Orientation root:        {result.Truth.Orientation.RootAddress}",
            $"Yaw / pitch (deg):       {FormatAngle(result.Truth.Orientation.PreferredEstimate.YawDegrees)} / {FormatAngle(result.Truth.Orientation.PreferredEstimate.PitchDegrees)}",
            $"Coord backrefs:          {result.CoordObjectBackrefs.HitCount}",
            $"Orientation backrefs:    {result.OrientationObjectBackrefs.HitCount}",
            $"Parent backrefs:         {result.OrientationParentBackrefs.HitCount}",
            $"Slot correlations:       {result.SlotCorrelations.Count}",
            $"Parent candidates:       {result.ParentContainerCandidates.Count}",
            $"Root families:           {result.RootFamilyCandidates.Count}",
            $"Shared ancestors:        {result.SharedAncestorCandidates.Count}",
            $"Notes:                   {FormatNotes(result.Notes)}"
        };

        if (result.BestContainerChain is not null)
        {
            lines.Add($"Best chain:              parent={result.BestContainerChain.ParentAddress ?? "n/a"} ({result.BestContainerChain.ParentObservationCount}/{result.BestContainerChain.StabilitySampleCount}), root={result.BestContainerChain.RootAddress ?? "n/a"} ({result.BestContainerChain.RootObservationCount}/{result.BestContainerChain.StabilitySampleCount})");
        }

        if (result.BestRootFamily is not null)
        {
            lines.Add($"Best root family:        {result.BestRootFamily.RegionBase} ({result.BestRootFamily.ObservationCount}/{result.BestRootFamily.StabilitySampleCount}, distinct={result.BestRootFamily.DistinctAddressCount}, avgMatch={result.BestRootFamily.AverageMatchingBytes:0.0})");
        }

        if (result.RootFamilySummary is not null)
        {
            lines.Add($"Canonical root instance: {result.RootFamilySummary.CanonicalInstanceAddress}");
            lines.Add($"Root family summary:     {result.RootFamilySummary.RegionBase} canonicalObs={result.RootFamilySummary.CanonicalInstanceObservationCount}/{result.RootFamilySummary.StabilitySampleCount} rep={result.RootFamilySummary.RepresentativeAddress}");
        }

        AppendWindow(lines, result.CoordObjectWindow);
        AppendWindow(lines, result.OrientationObjectWindow);
        AppendWindow(lines, result.OrientationParentWindow);
        AppendWindow(lines, result.OrientationRootWindow);
        AppendPointerSummary(lines, "coord-object", result.CoordObjectBackrefs);
        AppendPointerSummary(lines, "orientation-object", result.OrientationObjectBackrefs);
        AppendPointerSummary(lines, "orientation-parent", result.OrientationParentBackrefs);
        AppendStabilitySummary(lines, result.StabilityObservations);
        AppendSlotCorrelationSummary(lines, result.SlotCorrelations);
        AppendParentCandidateSummary(lines, result.ParentContainerCandidates);
        AppendRootFamilySummary(lines, result.RootFamilyCandidates);
        AppendSharedAncestorSummary(lines, result.SharedAncestorCandidates);

        return string.Join(Environment.NewLine, lines);
    }

    private static void AppendWindow(List<string> lines, PlayerActorTruthObjectWindow? window)
    {
        if (window is null)
        {
            return;
        }

        lines.Add($"{window.Label} window:      {window.WindowStart} ({window.WindowLength} bytes) -> {window.TargetAddress}");
        lines.Add($"{window.Label} ascii:       {window.AsciiPreview}");
        lines.Add($"{window.Label} utf16:       {window.Utf16Preview}");

        foreach (var slot in window.PointerSlots.Take(6))
        {
            lines.Add($"{window.Label} ptr {slot.OffsetHex,6}: {slot.ValueHex} [{slot.Classification}{FormatRegion(slot.TargetRegionBase)}]");
        }
    }

    private static void AppendPointerSummary(List<string> lines, string label, PointerScanResult result)
    {
        lines.Add($"{label} pointer hits:    {result.HitCount}");
        foreach (var hit in result.Hits.Take(4))
        {
            lines.Add($"  hit {hit.AddressHex} in {hit.RegionBaseHex} (+{(hit.Address - hit.RegionBase).ToString(CultureInfo.InvariantCulture)})");
        }
    }

    private static void AppendSlotCorrelationSummary(List<string> lines, IReadOnlyList<PlayerActorTruthSlotCorrelation> correlations)
    {
        if (correlations.Count == 0)
        {
            lines.Add("slot correlations:       none");
            return;
        }

        lines.Add("slot correlations:");
        foreach (var correlation in correlations.Take(6))
        {
            lines.Add($"  {correlation.ValueHex} score={correlation.Score} surfaces={string.Join(',', correlation.Surfaces)}{FormatRegion(correlation.TargetRegionBase)}");

            foreach (var reference in correlation.References.Take(4))
            {
                lines.Add($"    {reference.Surface} {reference.OffsetHex} @ {reference.SlotAddress} [{reference.Classification}]");
            }
        }
    }

    private static void AppendSharedAncestorSummary(List<string> lines, IReadOnlyList<PlayerActorTruthSharedAncestorCandidate> candidates)
    {
        if (candidates.Count == 0)
        {
            lines.Add("shared ancestors:        none");
            return;
        }

        lines.Add("shared ancestors:");
        foreach (var candidate in candidates.Take(5))
        {
            lines.Add($"  {candidate.Address} score={candidate.Score} surfaces={string.Join(',', candidate.Surfaces)} firstHop={candidate.FirstHopReferenceCount} secondHop={candidate.SecondHopReferenceCount}");

            foreach (var path in candidate.Paths.Take(4))
            {
                lines.Add($"    {path.Surface}: {path.FirstHopAddress} <- {path.SecondHopAddress}");
            }
        }
    }

    private static void AppendParentCandidateSummary(List<string> lines, IReadOnlyList<PlayerActorTruthParentContainerCandidate> candidates)
    {
        if (candidates.Count == 0)
        {
            lines.Add("parent candidates:      none");
            return;
        }

        lines.Add("parent candidates:");
        foreach (var candidate in candidates.Take(6))
        {
            lines.Add($"  {candidate.Address} score={candidate.Score} direct={FormatBool(candidate.IsDirectParent)} root={FormatBool(candidate.IsOrientationRoot)} parentObs={candidate.ObservedAsParentCount} rootObs={candidate.ObservedAsRootCount} backrefs={candidate.ParentBackrefCount} secondHop={candidate.ParentSecondHopCount} slots={candidate.ParentWindowSlotCount}{FormatRegion(candidate.RegionBase)}");
            lines.Add($"    sources: {string.Join(',', candidate.Sources)}");

            if (!string.IsNullOrWhiteSpace(candidate.AsciiPreview))
            {
                lines.Add($"    ascii: {candidate.AsciiPreview}");
            }
        }
    }

    private static void AppendRootFamilySummary(List<string> lines, IReadOnlyList<PlayerActorTruthRootFamilyCandidate> candidates)
    {
        if (candidates.Count == 0)
        {
            lines.Add("root families:          none");
            return;
        }

        lines.Add("root families:");
        foreach (var candidate in candidates.Take(5))
        {
            lines.Add($"  {candidate.RegionBase} score={candidate.Score} obs={candidate.ObservationCount}/{candidate.StabilitySampleCount} distinct={candidate.DistinctAddressCount} rep={candidate.RepresentativeAddress} repObs={candidate.RepresentativeObservationCount} match={candidate.MinimumMatchingBytes}/{candidate.MaximumMatchingBytes}/{candidate.AverageMatchingBytes:0.0}");
            lines.Add($"    members: {string.Join(',', candidate.MemberAddresses)}");

            if (!string.IsNullOrWhiteSpace(candidate.RepresentativeAsciiPreview))
            {
                lines.Add($"    ascii: {candidate.RepresentativeAsciiPreview}");
            }
        }
    }

    private static void AppendStabilitySummary(List<string> lines, IReadOnlyList<PlayerActorTruthChainObservation> observations)
    {
        if (observations.Count == 0)
        {
            lines.Add("stability observations:  none");
            return;
        }

        lines.Add("stability observations:");
        foreach (var observation in observations.Take(6))
        {
            lines.Add($"  #{observation.SampleIndex}: unified={observation.UnifiedTruthObjectAddress ?? "n/a"} parent={observation.OrientationParentAddress} root={observation.OrientationRootAddress}");
        }
    }

    private static string FormatAngle(double? value) =>
        value?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatNotes(IReadOnlyList<string> notes) =>
        notes.Count == 0 ? "none" : string.Join("; ", notes);

    private static string FormatRegion(string? regionBase) =>
        string.IsNullOrWhiteSpace(regionBase) ? string.Empty : $" -> {regionBase}";
}
