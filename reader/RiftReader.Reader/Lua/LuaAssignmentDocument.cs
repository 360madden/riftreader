namespace RiftReader.Reader.Lua;

internal sealed record LuaAssignmentDocument(
    string VariableName,
    object? Value);
