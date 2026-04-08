using System.Text;

namespace RiftReader.Reader.Formatting;

public static class HexDumpFormatter
{
    public static string Format(ReadOnlySpan<byte> bytes, nint baseAddress, int bytesPerLine = 16)
    {
        if (bytesPerLine <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(bytesPerLine));
        }

        if (bytes.IsEmpty)
        {
            return "<empty>";
        }

        var builder = new StringBuilder();
        var baseAddressValue = baseAddress.ToInt64();

        for (var index = 0; index < bytes.Length; index += bytesPerLine)
        {
            var lineLength = Math.Min(bytesPerLine, bytes.Length - index);
            var line = bytes.Slice(index, lineLength);

            builder.Append($"0x{baseAddressValue + index:X16}: ");

            for (var i = 0; i < bytesPerLine; i++)
            {
                if (i < line.Length)
                {
                    builder.Append($"{line[i]:X2} ");
                }
                else
                {
                    builder.Append("   ");
                }
            }

            builder.Append(" | ");

            for (var i = 0; i < line.Length; i++)
            {
                var value = line[i];
                builder.Append(value is >= 32 and <= 126 ? (char)value : '.');
            }

            if (index + bytesPerLine < bytes.Length)
            {
                builder.AppendLine();
            }
        }

        return builder.ToString();
    }
}
