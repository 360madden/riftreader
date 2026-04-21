using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerActorOrientationReadTextFormatter
{
    public static string Format(PlayerActorOrientationReadResult result)
    {
        var lines = new List<string>
        {
            $"Process:                 {result.ProcessName} ({result.ProcessId})",
            $"ReaderBridge source:     {result.ReaderBridgeSourceFile}",
            $"Trace source:            {result.TraceSourceFile ?? "n/a"}",
            $"Trace available:         {FormatBool(result.TraceAvailable)}",
            $"Trace matches process:   {FormatBool(result.TraceMatchesProcess)}",
            $"Coord bootstrap:         {result.CoordBootstrapSource}",
            $"Resolution source:       {result.ResolutionSource}",
            $"Player:                  {result.PlayerName ?? "n/a"}",
            $"Player coords:           {FormatVector(result.PlayerCoord)}",
            $"Selected address:        {result.SelectedAddress}",
            $"Parent address:          {result.ParentAddress}",
            $"Parent family:           {result.ParentFamilyId ?? "n/a"}",
            $"Root address/source:     {result.RootAddress} | {result.RootSource}",
            $"Hop depth / ptr offset:  {result.HopDepth} / {result.PointerOffset}",
            $"Basis forward offset:    {result.BasisPrimaryForwardOffset}",
            $"Score:                   {result.Score} (raw {result.RawScore?.ToString(CultureInfo.InvariantCulture) ?? "n/a"}, penalty {result.LedgerPenalty.ToString(CultureInfo.InvariantCulture)})",
            $"Yaw / pitch (deg):       {FormatAngle(result.PreferredEstimate.YawDegrees)} / {FormatAngle(result.PreferredEstimate.PitchDegrees)}",
            $"Forward row:             {FormatVector(result.Basis.Forward)}",
            $"Up row:                  {FormatVector(result.Basis.Up)}",
            $"Right row:               {FormatVector(result.Basis.Right)}",
            $"Basis orthonormal:       {FormatBool(result.Basis.IsOrthonormal)}",
            $"Determinant:             {FormatNullable(result.Basis.Determinant)}",
            $"Coord source object:     {result.CoordSourceObjectAddress ?? "n/a"} @ {result.CoordSourceRegister ?? "n/a"} + {FormatOffset(result.CoordSourceRelativeOffset)}",
            $"Pointer-hop candidates:  {result.PointerHopCandidateCount}",
            $"Local candidates:        {result.CandidateCount}",
            $"Diagnostics:             coordHits={result.Diagnostics.CoordHitCount}, roots={result.Diagnostics.PointerRootCount}, children={result.Diagnostics.UniqueChildPointerCount}, childReadFailures={result.Diagnostics.ChildReadFailures}",
            $"Notes:                   {FormatNotes(result.Notes)}"
        };

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatAngle(double? value) =>
        value?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatNullable(double? value) =>
        value?.ToString("0.000000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatOffset(int? value) =>
        value.HasValue ? $"0x{value.Value:X}" : "n/a";

    private static string FormatVector(RiftReader.Reader.AddonSnapshots.ValidatorCoordinateSnapshot vector)
    {
        if (vector.X is null || vector.Y is null || vector.Z is null)
        {
            return "n/a";
        }

        return $"{vector.X.Value:0.00000}, {vector.Y.Value:0.00000}, {vector.Z.Value:0.00000}";
    }

    private static string FormatNotes(IReadOnlyList<string> notes) =>
        notes.Count == 0 ? "none" : string.Join("; ", notes);
}
