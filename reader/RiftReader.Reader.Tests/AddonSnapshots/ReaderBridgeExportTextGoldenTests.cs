using RiftReader.Reader.Formatting;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeExportTextGoldenTests
{
    [Fact]
    public void WaitingForPlayerFormatterOutput_MatchesGoldenText()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.NormalizeForGolden(
            ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.waiting-for-player.lua"),
            "ReaderBridgeExport.waiting-for-player.lua");

        var text = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.waiting-for-player.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void ThinLiveFormatterOutput_MatchesGoldenText()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.NormalizeForGolden(
            ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.thin-live.lua"),
            "ReaderBridgeExport.thin-live.lua");

        var text = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.thin-live.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void ReaderBridgeSparseFormatterOutput_MatchesGoldenText()
    {
        var document = ReaderBridgeSnapshotLoaderTestSupport.NormalizeForGolden(
            ReaderBridgeSnapshotLoaderTestSupport.LoadFixture("ReaderBridgeExport.readerbridge-sparse.lua"),
            "ReaderBridgeExport.readerbridge-sparse.lua");

        var text = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(ReaderBridgeSnapshotTextFormatter.Format(document));
        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.readerbridge-sparse.expected.txt");

        Assert.Equal(expected, text);
    }

    [Fact]
    public void WaitingForPlayerCliTextOutput_MatchesGoldenText()
    {
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath("ReaderBridgeExport.waiting-for-player.lua")
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expectedFormatterText = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.waiting-for-player.expected.txt");
        var expectedCliText = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(
            $"RiftReader.Reader{Environment.NewLine}" +
            "Use this tool only against Rift client processes you explicitly intend to inspect." +
            $"{Environment.NewLine}{Environment.NewLine}{expectedFormatterText}");

        Assert.Equal(
            expectedCliText,
            ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliText(
                result.StandardOutput,
                ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath("ReaderBridgeExport.waiting-for-player.lua"),
                "ReaderBridgeExport.waiting-for-player.lua"));
    }

    [Fact]
    public void ThinLiveCliTextOutput_MatchesGoldenText()
    {
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath("ReaderBridgeExport.thin-live.lua")
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expectedFormatterText = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedText("ReaderBridgeExport.thin-live.expected.txt");
        var expectedCliText = ReaderBridgeSnapshotLoaderTestSupport.NormalizeText(
            $"RiftReader.Reader{Environment.NewLine}" +
            "Use this tool only against Rift client processes you explicitly intend to inspect." +
            $"{Environment.NewLine}{Environment.NewLine}{expectedFormatterText}");

        Assert.Equal(
            expectedCliText,
            ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliText(
                result.StandardOutput,
                ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath("ReaderBridgeExport.thin-live.lua"),
                "ReaderBridgeExport.thin-live.lua"));
    }
}
