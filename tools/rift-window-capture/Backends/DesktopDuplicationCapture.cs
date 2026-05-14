static class DesktopDuplicationCapture
{
    public static QualityReport CaptureNearestMonitor(D3DObjects d3d, IntPtr monitor, string output, string? rawOutput, string? cropImageRoot, string? cropRawRoot, string[] cropProfiles, int timeoutMs, int captureAttempts, bool emitPng)
    {
        using IDXGIOutput1 output1 = FindOutputForMonitor(d3d.Device, monitor, out OutputDescription outputDescription);
        using IDXGIOutputDuplication duplication = output1.DuplicateOutput(d3d.Device);
        OutduplDescription duplicationDescription = duplication.Description;

        QualityReport? best = null;
        Exception? lastException = null;
        int completedAttempts = 0;

        for (int attempt = 1; attempt <= captureAttempts; attempt++)
        {
            bool frameAcquired = false;
            IDXGIResource? desktopResource = null;
            try
            {
                Result result = duplication.AcquireNextFrame((uint)timeoutMs, out OutduplFrameInfo frameInfo, out desktopResource);
                result.CheckError();
                frameAcquired = true;
                completedAttempts++;

                using ID3D11Texture2D desktopTexture = desktopResource.QueryInterface<ID3D11Texture2D>();
                string attemptOutput = captureAttempts == 1 ? output : TextureSaver.CreateAttemptOutputPath(output, attempt, emitPng);
                string? attemptRawOutput = rawOutput is null
                    ? null
                    : captureAttempts == 1
                        ? rawOutput
                        : TextureSaver.CreateAttemptRawOutputPath(rawOutput, attempt);
                string[] attemptCropProfiles = captureAttempts == 1 ? cropProfiles : [];
                QualityReport quality = TextureSaver.SaveTextureToImage(d3d, desktopTexture, attemptOutput, emitPng, attemptRawOutput, cropImageRoot, cropRawRoot, attemptCropProfiles) with
                {
                    CaptureAttemptCount = captureAttempts,
                    CompletedAttemptCount = completedAttempts,
                    SelectedAttempt = attempt,
                    DesktopDuplicationDeviceName = outputDescription.DeviceName,
                    DesktopDuplicationDesktopCoordinates = outputDescription.DesktopCoordinates.ToString(),
                    DesktopDuplicationRotation = outputDescription.Rotation.ToString(),
                    DesktopDuplicationModeDescription = duplicationDescription.ModeDescription.ToString(),
                    DesktopDuplicationModeFormat = duplicationDescription.ModeDescription.Format.ToString(),
                    DesktopDuplicationDesktopImageInSystemMemory = duplicationDescription.DesktopImageInSystemMemory,
                    DesktopDuplicationAccumulatedFrames = (int)frameInfo.AccumulatedFrames,
                    DesktopDuplicationProtectedContentMaskedOut = frameInfo.ProtectedContentMaskedOut,
                    DesktopDuplicationPointerVisible = frameInfo.PointerPosition.Visible,
                    DesktopDuplicationPointerPosition = frameInfo.PointerPosition.Position.ToString(),
                };

                if (best is null || IsBetter(quality, best))
                {
                    best = quality;
                }
            }
            catch (Exception ex) when (best is not null)
            {
                lastException = ex;
                break;
            }
            finally
            {
                desktopResource?.Dispose();
                if (frameAcquired)
                {
                    duplication.ReleaseFrame().CheckError();
                }
            }
        }

        if (best is null)
        {
            throw lastException ?? new InvalidOperationException("DXGI Desktop Duplication did not return a frame.");
        }

        string finalOutput = TextureSaver.NormalizeImageOutputPath(output, emitPng);
        if (!string.Equals(best.Output, finalOutput, StringComparison.OrdinalIgnoreCase))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(finalOutput) ?? Environment.CurrentDirectory);
            File.Copy(best.Output, finalOutput, overwrite: true);
            best = best with { Output = finalOutput };
        }

        if (rawOutput is not null)
        {
            string finalRawOutput = Path.ChangeExtension(Path.GetFullPath(rawOutput), ".bgra");
            string finalRawMetadata = Path.ChangeExtension(finalRawOutput, ".frame.json");
            if (best.RawOutput is not null && !string.Equals(best.RawOutput, finalRawOutput, StringComparison.OrdinalIgnoreCase))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(finalRawOutput) ?? Environment.CurrentDirectory);
                File.Copy(best.RawOutput, finalRawOutput, overwrite: true);
            }

            if (best.RawMetadata is not null && !string.Equals(best.RawMetadata, finalRawMetadata, StringComparison.OrdinalIgnoreCase))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(finalRawMetadata) ?? Environment.CurrentDirectory);
                File.Copy(best.RawMetadata, finalRawMetadata, overwrite: true);
            }

            best = best with { RawOutput = finalRawOutput, RawMetadata = finalRawMetadata };
        }

        return best with
        {
            CompletedAttemptCount = completedAttempts,
            LastAttemptError = lastException?.Message,
        };
    }

    private static bool IsBetter(QualityReport candidate, QualityReport incumbent)
    {
        if (candidate.Usable != incumbent.Usable)
        {
            return candidate.Usable;
        }

        if (candidate.ContentBlackPixelRatio != incumbent.ContentBlackPixelRatio)
        {
            return candidate.ContentBlackPixelRatio < incumbent.ContentBlackPixelRatio;
        }

        return candidate.ContentLumaStdDev > incumbent.ContentLumaStdDev;
    }

    private static IDXGIOutput1 FindOutputForMonitor(ID3D11Device device, IntPtr monitor, out OutputDescription matchedDescription)
    {
        using IDXGIDevice dxgiDevice = device.QueryInterface<IDXGIDevice>();
        dxgiDevice.GetAdapter(out IDXGIAdapter adapter).CheckError();
        using (adapter)
        {
            for (uint i = 0; ; i++)
            {
                Result result = adapter.EnumOutputs(i, out IDXGIOutput output);
                if (result.Failure)
                {
                    break;
                }

                OutputDescription description = output.Description;
                if (description.Monitor == monitor)
                {
                    try
                    {
                        matchedDescription = description;
                        return output.QueryInterface<IDXGIOutput1>();
                    }
                    finally
                    {
                        output.Dispose();
                    }
                }

                output.Dispose();
            }
        }

        matchedDescription = default;
        throw new InvalidOperationException("No DXGI output matched the Rift window's nearest monitor.");
    }
}
