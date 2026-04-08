namespace RiftReader.Reader.Scanning;

public sealed record StringHitContext(
    string WindowStart,
    int WindowLength,
    string BytesHex,
    string AsciiPreview,
    string Utf16Preview);
