using RiftReader.Reader.Cli;
using Xunit;

namespace RiftReader.Reader.Tests.Cli;

public sealed class ReaderOptionsParserTests
{
    [Fact]
    public void Parse_ReadPlayerActorTruth_WithKnownOptions_Succeeds()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-player-actor-truth",
            "--player-coord-trace-file", "coord-trace.json",
            "--orientation-candidate-ledger-file", "ledger.ndjson",
            "--max-hits", "8",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        Assert.False(result.ShowUsage);
        Assert.NotNull(result.Options);
        Assert.Equal("rift_x64", result.Options!.ProcessName);
        Assert.True(result.Options.ReadPlayerActorTruth);
        Assert.Equal("coord-trace.json", result.Options.PlayerCoordTraceFile);
        Assert.Equal("ledger.ndjson", result.Options.OrientationCandidateLedgerFile);
        Assert.Equal(8, result.Options.MaxHits);
        Assert.True(result.Options.JsonOutput);
    }

    [Fact]
    public void Parse_DumpPlayerActorTruthChain_WithKnownOptions_Succeeds()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--dump-player-actor-truth-chain",
            "--player-coord-trace-file", "coord-trace.json",
            "--orientation-candidate-ledger-file", "ledger.ndjson",
            "--scan-context", "128",
            "--pointer-width", "8",
            "--max-hits", "12",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        Assert.False(result.ShowUsage);
        Assert.NotNull(result.Options);
        Assert.True(result.Options!.DumpPlayerActorTruthChain);
        Assert.Equal(128, result.Options.ScanContextBytes);
        Assert.Equal(8, result.Options.PointerWidth);
        Assert.Equal(12, result.Options.MaxHits);
        Assert.True(result.Options.JsonOutput);
    }

    [Fact]
    public void Parse_DebugTraceSummary_WithTraceDirectoryOnly_Succeeds()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--debug-trace-summary",
            "--trace-directory", ".\\scripts\\captures\\debug-traces\\20260417-coord",
            "--json"
        ]);

        Assert.True(result.IsSuccess);
        Assert.False(result.ShowUsage);
        Assert.NotNull(result.Options);
        Assert.True(result.Options!.DebugTraceSummary);
        Assert.Equal(".\\scripts\\captures\\debug-traces\\20260417-coord", result.Options.DebugTraceDirectory);
        Assert.True(result.Options.JsonOutput);
        Assert.Null(result.Options.ProcessName);
        Assert.Null(result.Options.ProcessId);
    }

    [Fact]
    public void Parse_DebugTraceSummary_WithProcessAttach_Fails()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--debug-trace-summary",
            "--trace-directory", ".\\scripts\\captures\\debug-traces\\20260417-coord"
        ]);

        Assert.False(result.IsSuccess);
        Assert.True(result.ShowUsage);
        Assert.Contains("--debug-trace-summary cannot be combined with attach", result.ErrorMessage);
    }

    [Fact]
    public void Parse_ReadPlayerActorTruth_AndDumpTruthChainTogether_Fails()
    {
        var result = ReaderOptionsParser.Parse(
        [
            "--process-name", "rift_x64",
            "--read-player-actor-truth",
            "--dump-player-actor-truth-chain"
        ]);

        Assert.False(result.IsSuccess);
        Assert.True(result.ShowUsage);
        Assert.Contains("--read-player-actor-truth cannot be combined with", result.ErrorMessage);
        Assert.Contains("other actor/coord reader modes", result.ErrorMessage);
    }
}
