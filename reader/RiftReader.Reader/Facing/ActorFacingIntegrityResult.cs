namespace RiftReader.Reader.Facing;

public sealed record ActorFacingIntegrityResult(
    bool DeterminantPass,
    bool RowMagnitudesPass,
    bool CrossRowDotProductsPass,
    bool DuplicateBasisPass,
    bool Pass,
    IReadOnlyList<string> Notes);
