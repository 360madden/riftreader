using RiftReader.Reader.AddonSnapshots;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class ReaderBridgeSnapshotParserBoundaryTests
{
    [Fact]
    public void EmptyRootAssignmentFile_IsRejected()
    {
        using var fixture = ReaderBridgeTempFixture.Create(nameof(EmptyRootAssignmentFile_IsRejected), string.Empty);
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixture.Path, out var error);

        Assert.Null(document);
        Assert.Contains("Unable to parse the root Lua variable name", error, StringComparison.Ordinal);
    }

    [Fact]
    public void CorruptedLuaAssignmentSyntax_IsRejected()
    {
        const string fixtureText = "ReaderBridgeExport_State = {";

        using var fixture = ReaderBridgeTempFixture.Create(nameof(CorruptedLuaAssignmentSyntax_IsRejected), fixtureText);
        var document = ReaderBridgeSnapshotLoader.TryLoad(fixture.Path, out var error);

        Assert.Null(document);
        Assert.Contains("Unexpected end of input", error, StringComparison.Ordinal);
    }
}
