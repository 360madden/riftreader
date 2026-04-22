using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Formatting;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Tests.Formatting;

public sealed class PlayerOrientationReadTextFormatterTests
{
    [Fact]
    public void Format_IncludesLiveResolutionModeAndBasisOffsets()
    {
        var result = new PlayerOrientationReadResult(
            Mode: "player-orientation-live",
            ArtifactFile: @"C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json",
            ArtifactLoadedAtUtc: new DateTimeOffset(2026, 4, 22, 6, 4, 25, TimeSpan.Zero),
            ArtifactGeneratedAtUtc: new DateTimeOffset(2026, 4, 22, 4, 42, 26, TimeSpan.Zero),
            SnapshotFile: @"C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\Saved\rift315.1@gmail.com\Deepwood\Atank\SavedVariables\ReaderBridgeExport.lua",
            SnapshotLoadedAtUtc: new DateTimeOffset(2026, 4, 22, 6, 4, 25, TimeSpan.Zero),
            PlayerName: "Atank",
            PlayerLevel: 45,
            PlayerGuild: "The Regulators",
            PlayerLocation: "Sanctum Watch",
            PlayerCoord: new ValidatorCoordinateSnapshot(7185.919921875, 871.77996826172, 3071.7600097656),
            SelectedSourceAddress: "0x24F595F8D10",
            SelectedEntryAddress: null,
            SelectedEntryIndex: null,
            SelectedEntryMatchesSelectedSource: false,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "live-behavior-backed-lead",
            BasisPrimaryForwardOffset: "0x60",
            BasisDuplicateForwardOffset: "0x94",
            PreferredEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0x60.Forward",
                Vector: new ValidatorCoordinateSnapshot(-0.8380997776985168, 0.0, 0.5455169081687927),
                YawRadians: 2.56458687918028,
                YawDegrees: 146.9400043716572,
                PitchRadians: 0.0,
                PitchDegrees: 0.0,
                Magnitude: 0.9999999672381706),
            BasisPrimaryEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0x60.Forward",
                Vector: new ValidatorCoordinateSnapshot(-0.8380997776985168, 0.0, 0.5455169081687927),
                YawRadians: 2.56458687918028,
                YawDegrees: 146.9400043716572,
                PitchRadians: 0.0,
                PitchDegrees: 0.0,
                Magnitude: 0.9999999672381706),
            BasisDuplicateEstimate: new PlayerOrientationVectorEstimate(
                Name: "Basis@0x94.Forward",
                Vector: new ValidatorCoordinateSnapshot(-0.8381058573722839, 0.0, 0.5455074906349182),
                YawRadians: 2.564598088579368,
                YawDegrees: 146.94064662291584,
                PitchRadians: 0.0,
                PitchDegrees: 0.0,
                Magnitude: 0.9999999252502655),
            BasisDuplicateDeltaMagnitude: 1.1209477123925813E-05,
            BasisDuplicateAgreementStrong: true,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: Array.Empty<string>());

        var text = PlayerOrientationReadTextFormatter.Format(result);

        Assert.Contains("Resolution mode:              live-behavior-backed-lead (current-session source lead)", text, StringComparison.Ordinal);
        Assert.Contains("Basis offsets:                primary 0x60 | duplicate 0x94", text, StringComparison.Ordinal);
    }

    [Fact]
    public void Format_LabelsArtifactModeAsLegacy()
    {
        var result = new PlayerOrientationReadResult(
            Mode: "player-orientation",
            ArtifactFile: @"C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json",
            ArtifactLoadedAtUtc: new DateTimeOffset(2026, 4, 22, 6, 4, 25, TimeSpan.Zero),
            ArtifactGeneratedAtUtc: new DateTimeOffset(2026, 4, 13, 1, 9, 1, TimeSpan.Zero),
            SnapshotFile: null,
            SnapshotLoadedAtUtc: null,
            PlayerName: null,
            PlayerLevel: null,
            PlayerGuild: null,
            PlayerLocation: null,
            PlayerCoord: null,
            SelectedSourceAddress: "0x1FDA0D13170",
            SelectedEntryAddress: "0x1FDA0D13170",
            SelectedEntryIndex: 6,
            SelectedEntryMatchesSelectedSource: true,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "artifact-owner-components",
            BasisPrimaryForwardOffset: "0x60",
            BasisDuplicateForwardOffset: "0x94",
            PreferredEstimate: null,
            BasisPrimaryEstimate: null,
            BasisDuplicateEstimate: null,
            BasisDuplicateDeltaMagnitude: null,
            BasisDuplicateAgreementStrong: null,
            Estimates: Array.Empty<PlayerOrientationVectorEstimate>(),
            Notes: new[] { "LEGACY artifact-only mode: this path reads historical owner/source artifacts and must not be treated as current live truth without a matching live process selector." });

        var text = PlayerOrientationReadTextFormatter.Format(result);

        Assert.Contains("Resolution mode:              artifact-owner-components (LEGACY historical artifact path; not current live truth)", text, StringComparison.Ordinal);
        Assert.Contains("LEGACY artifact-only mode", text, StringComparison.Ordinal);
    }
}
