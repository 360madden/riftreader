using RiftReader.Reader.AddonSnapshots;
using Xunit;

namespace RiftReader.Reader.Tests.AddonSnapshots;

public sealed class SavedVariablesFileLocatorTests
{
    [Fact]
    public void ResolveExplicitPath_ReturnsNormalizedFullPath_ForExistingFile()
    {
        var root = Path.Combine(Path.GetTempPath(), "RiftReader", "locator-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var filePath = Path.Combine(root, "fixture path with spaces.lua");
        File.WriteAllText(filePath, "ReaderBridgeExport_State = {}");

        try
        {
            var relativePath = Path.GetRelativePath(Directory.GetCurrentDirectory(), filePath);
            var resolved = SavedVariablesFileLocator.ResolveExplicitPath(relativePath, out var error);

            Assert.NotNull(resolved);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
            Assert.Equal(Path.GetFullPath(filePath), resolved);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public void ResolveExplicitPath_ReturnsMissingFileError_ForMissingFile()
    {
        var missingPath = Path.Combine(Path.GetTempPath(), "RiftReader", "locator-tests", Guid.NewGuid().ToString("N"), "missing.lua");

        var resolved = SavedVariablesFileLocator.ResolveExplicitPath(missingPath, out var error);

        Assert.Null(resolved);
        Assert.Contains("Addon snapshot file was not found", error, StringComparison.Ordinal);
        Assert.Contains(Path.GetFullPath(missingPath), error, StringComparison.Ordinal);
    }
}
