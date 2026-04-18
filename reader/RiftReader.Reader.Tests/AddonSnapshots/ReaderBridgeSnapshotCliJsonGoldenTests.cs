using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotCliJsonGoldenTests
{
    [Fact]
    public void FrozenCliJsonOutput_MatchesGoldenJson()
    {
        const string fixtureName = "ReaderBridgeExport.frozen.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedJson("ReaderBridgeExport.frozen.expected.json");
        var actual = ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliJson(result.StandardOutput, fixtureName);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void WaitingForPlayerCliJsonOutput_MatchesGoldenJson()
    {
        const string fixtureName = "ReaderBridgeExport.waiting-for-player.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedJson("ReaderBridgeExport.waiting-for-player.expected.json");
        var actual = ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliJson(result.StandardOutput, fixtureName);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void ThinLiveCliJsonOutput_MatchesGoldenJson()
    {
        const string fixtureName = "ReaderBridgeExport.thin-live.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedJson("ReaderBridgeExport.thin-live.expected.json");
        var actual = ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliJson(result.StandardOutput, fixtureName);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void ReaderBridgeSparseCliJsonOutput_MatchesGoldenJson()
    {
        const string fixtureName = "ReaderBridgeExport.readerbridge-sparse.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedJson("ReaderBridgeExport.readerbridge-sparse.expected.json");
        var actual = ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliJson(result.StandardOutput, fixtureName);

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void DirectApiGoldenCliJsonOutput_MatchesGoldenJson()
    {
        const string fixtureName = "ReaderBridgeExport.directapi-golden.lua";
        var fixturePath = ReaderBridgeSnapshotLoaderTestSupport.GetFixturePath(fixtureName);
        var result = ReaderBridgeSnapshotLoaderTestSupport.RunReader(
            [
                "--readerbridge-snapshot",
                "--readerbridge-snapshot-file", fixturePath,
                "--json"
            ]);

        Assert.Equal(0, result.ExitCode);
        Assert.True(string.IsNullOrWhiteSpace(result.StandardError), result.StandardError);

        var expected = ReaderBridgeSnapshotLoaderTestSupport.ReadExpectedJson("ReaderBridgeExport.directapi-golden.expected.json");
        var actual = ReaderBridgeSnapshotLoaderTestSupport.NormalizeCliJson(result.StandardOutput, fixtureName);

        Assert.Equal(expected, actual);
    }
}
