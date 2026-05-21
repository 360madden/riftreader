# Version: riftreader-promote-current-pid-proof-anchor-from-batch-v0.1.2
# Total-Character-Count: 11713
# Purpose: Safely promote the current PID coordinate proof anchor from the latest promotion-ready coordinate-anchor batch summary using existing repo helpers only. Fixes array-parameter invocation for ReadbackSummaryFile by using encoded PowerShell commands. Sends no movement.

[CmdletBinding()]
param(
  [string]$BatchSummaryFile
)

& {
  $ErrorActionPreference = "Stop"
  Set-StrictMode -Version Latest

  function ConvertTo-PowerShellSingleQuotedString {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
  }

  function New-EncodedPowerShellCommandArguments {
    param([Parameter(Mandatory = $true)][string]$CommandText)

    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($CommandText))
    return @(
      "-NoLogo",
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-EncodedCommand",
      $encoded
    )
  }

  function Invoke-CapturedProcess {
    param(
      [Parameter(Mandatory = $true)][string]$Label,
      [Parameter(Mandatory = $true)][string]$OutputDirectory,
      [Parameter(Mandatory = $true)][string]$FilePath,
      [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

    $StdoutFile = Join-Path $OutputDirectory "$Label.stdout.txt"
    $StderrFile = Join-Path $OutputDirectory "$Label.stderr.txt"
    $CommandFile = Join-Path $OutputDirectory "$Label.command.json"

    $Started = Get-Date

    $Psi = [System.Diagnostics.ProcessStartInfo]::new()
    $Psi.FileName = $FilePath
    $Psi.UseShellExecute = $false
    $Psi.RedirectStandardOutput = $true
    $Psi.RedirectStandardError = $true
    $Psi.CreateNoWindow = $true

    foreach ($Arg in $Arguments) {
      [void]$Psi.ArgumentList.Add($Arg)
    }

    $Proc = [System.Diagnostics.Process]::new()
    $Proc.StartInfo = $Psi

    if (-not $Proc.Start()) {
      throw "Failed to start $Label command: $FilePath"
    }

    $Stdout = $Proc.StandardOutput.ReadToEnd()
    $Stderr = $Proc.StandardError.ReadToEnd()
    $Proc.WaitForExit()

    $Completed = Get-Date

    $Stdout | Set-Content -LiteralPath $StdoutFile -Encoding UTF8
    $Stderr | Set-Content -LiteralPath $StderrFile -Encoding UTF8

    [ordered]@{
      label = $Label
      filePath = $FilePath
      arguments = @($Arguments)
      exitCode = $Proc.ExitCode
      startedAtUtc = $Started.ToUniversalTime().ToString("o")
      completedAtUtc = $Completed.ToUniversalTime().ToString("o")
      durationSeconds = ($Completed - $Started).TotalSeconds
      stdoutFile = $StdoutFile
      stderrFile = $StderrFile
    } | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $CommandFile -Encoding UTF8

    return [pscustomobject]@{
      Label = $Label
      ExitCode = [int]$Proc.ExitCode
      Stdout = [string]$Stdout
      Stderr = [string]$Stderr
      StdoutFile = $StdoutFile
      StderrFile = $StderrFile
      CommandFile = $CommandFile
    }
  }

  function Convert-JsonOrThrow {
    param(
      [Parameter(Mandatory = $true)][string]$Label,
      [Parameter(Mandatory = $true)][string]$Text,
      [Parameter(Mandatory = $true)][string]$StdoutFile,
      [Parameter(Mandatory = $true)][string]$StderrFile
    )

    try {
      return $Text | ConvertFrom-Json -Depth 140
    }
    catch {
      throw "$Label returned non-JSON stdout. stdout=$StdoutFile stderr=$StderrFile"
    }
  }

  function Get-Preview {
    param([string]$Text, [int]$Max = 2000)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    if ($Text.Length -le $Max) { return $Text }
    return $Text.Substring(0, $Max)
  }

  $RepoRoot = "C:\RIFT MODDING\RiftReader"
  Set-Location $RepoRoot

  $PromoteScript = Join-Path $RepoRoot "scripts\promote-riftscan-reference-match-to-proof-anchor.ps1"
  $AssertScript = Join-Path $RepoRoot "scripts\assert-current-proof-coord-anchor-readback.ps1"
  $ProofAnchorFile = Join-Path $RepoRoot "scripts\captures\telemetry-proof-coord-anchor.json"

  foreach ($RequiredPath in @($PromoteScript, $AssertScript)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
      throw "Required helper missing: $RequiredPath"
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($BatchSummaryFile)) {
    $ResolvedBatchSummaryFile = [System.IO.Path]::GetFullPath($BatchSummaryFile)
    if (-not (Test-Path -LiteralPath $ResolvedBatchSummaryFile -PathType Leaf)) {
      throw "BatchSummaryFile not found: $ResolvedBatchSummaryFile"
    }
    $BatchSummary = Get-Content -LiteralPath $ResolvedBatchSummaryFile -Raw | ConvertFrom-Json -Depth 140
    $BatchRecord = [pscustomobject]@{
      Directory = Split-Path -Parent $ResolvedBatchSummaryFile
      SummaryPath = $ResolvedBatchSummaryFile
      Summary = $BatchSummary
      LastWriteTime = (Get-Item -LiteralPath $ResolvedBatchSummaryFile).LastWriteTime
    }
    if ($BatchRecord.Summary.status -ne "promotion-candidate-found" -or -not [bool]$BatchRecord.Summary.ok) {
      throw "BatchSummaryFile is not promotion-ready. status=$($BatchRecord.Summary.status) ok=$($BatchRecord.Summary.ok)"
    }
  }
  else {
    $BatchRecords = Get-ChildItem ".\scripts\captures" -Directory -Filter "current-pid-coordinate-anchor-batch-*" |
      ForEach-Object {
        $SummaryPath = Join-Path $_.FullName "coordinate-anchor-batch-summary.json"
        if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
          try {
            $Summary = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json -Depth 140
            [pscustomobject]@{
              Directory = $_.FullName
              SummaryPath = $SummaryPath
              Summary = $Summary
              LastWriteTime = $_.LastWriteTime
            }
          }
          catch {
            Write-Warning "Skipping unreadable batch summary: $SummaryPath"
          }
        }
      } |
      Where-Object { $_.Summary.status -eq "promotion-candidate-found" -and [bool]$_.Summary.ok } |
      Sort-Object LastWriteTime -Descending

    $BatchRecord = $BatchRecords | Select-Object -First 1
    if ($null -eq $BatchRecord) {
      throw "No promotion-ready current-pid-coordinate-anchor-batch summary found."
    }
  }

  $BatchSummaryFile = [string]$BatchRecord.SummaryPath
  $BatchSummary = $BatchRecord.Summary

  $CandidateId = [string]$BatchSummary.topCandidate.candidateId
  $RiftPid = [int]$BatchSummary.target.processId
  $RiftHwnd = [string]$BatchSummary.target.targetWindowHandle
  $ProcessName = [string]$BatchSummary.target.processName
  $MinimumSupport = [int]$BatchSummary.minimumPromotionPoseSupport

  if ([string]::IsNullOrWhiteSpace($CandidateId)) { throw "Batch topCandidate.candidateId is missing." }
  if ([string]::IsNullOrWhiteSpace($RiftHwnd)) { throw "Batch target.targetWindowHandle is missing." }
  if ([string]::IsNullOrWhiteSpace($ProcessName)) { throw "Batch target.processName is missing." }
  if ($MinimumSupport -lt 2) { throw "Batch minimumPromotionPoseSupport is invalid: $MinimumSupport" }

  $Target = Get-Process -Id $RiftPid -ErrorAction Stop
  if ($Target.ProcessName -ne $ProcessName) {
    throw "Live target PID $RiftPid is '$($Target.ProcessName)', not '$ProcessName'."
  }

  $LiveHwnd = "0x{0:X}" -f ([int64]$Target.MainWindowHandle)
  if ($LiveHwnd -ne $RiftHwnd) {
    throw "Live target HWND mismatch. batch=$RiftHwnd live=$LiveHwnd"
  }

  $ReadbackSummaryFiles = @(
    $BatchSummary.poseResults |
      Where-Object { $_.status -eq "captured" -and $null -ne $_.proofPose.ReadbackSummaryFile } |
      ForEach-Object { [string]$_.proofPose.ReadbackSummaryFile }
  )

  if ($ReadbackSummaryFiles.Count -lt $MinimumSupport) {
    throw "Not enough readback summary files for promotion. got=$($ReadbackSummaryFiles.Count) required=$MinimumSupport"
  }

  foreach ($ReadbackFile in $ReadbackSummaryFiles) {
    if (-not (Test-Path -LiteralPath $ReadbackFile -PathType Leaf)) {
      throw "Readback summary file missing: $ReadbackFile"
    }
  }

  $PromoteRoot = Join-Path $RepoRoot ("scripts\captures\proof-anchor-promote-currentpid-$RiftPid-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  New-Item -ItemType Directory -Path $PromoteRoot -Force | Out-Null

  $PromotionResultFile = Join-Path $PromoteRoot "promotion-result.json"
  $AssertResultFile = Join-Path $PromoteRoot "assert-current-readback-result.json"

  Write-Host "=== PROMOTE CURRENT PROOF ANCHOR ==="
  Write-Host "Batch     : $BatchSummaryFile"
  Write-Host "Candidate : $CandidateId"
  Write-Host "PID/HWND  : $RiftPid / $RiftHwnd"
  Write-Host "Evidence  : $($ReadbackSummaryFiles.Count) readback summaries"
  Write-Host "RunRoot   : $PromoteRoot"

  $ReadbackArrayLiteral = "@(" + (($ReadbackSummaryFiles | ForEach-Object { ConvertTo-PowerShellSingleQuotedString -Value $_ }) -join ", ") + ")"

  $PromoteCommand = @"
`$ErrorActionPreference = 'Stop'
`$PromoteParams = @{
  ReadbackSummaryFile = $ReadbackArrayLiteral
  CandidateId = $(ConvertTo-PowerShellSingleQuotedString -Value $CandidateId)
  ProcessName = $(ConvertTo-PowerShellSingleQuotedString -Value $ProcessName)
  ProcessId = $RiftPid
  TargetWindowHandle = $(ConvertTo-PowerShellSingleQuotedString -Value $RiftHwnd)
  OutputFile = $(ConvertTo-PowerShellSingleQuotedString -Value $ProofAnchorFile)
  MinPoseCount = $MinimumSupport
  MinReferenceDisplacement = 1.0
  MaxDeltaError = 0.25
  MaxEvidenceAgeSeconds = 14400
  Json = `$true
}
& $(ConvertTo-PowerShellSingleQuotedString -Value $PromoteScript) @PromoteParams
"@

  $PromoteArgs = New-EncodedPowerShellCommandArguments -CommandText $PromoteCommand
  $PromoteRun = Invoke-CapturedProcess -Label "promotion" -OutputDirectory $PromoteRoot -FilePath "pwsh" -Arguments $PromoteArgs

  if ($PromoteRun.ExitCode -ne 0) {
    Write-Host "Promotion failed."
    Write-Host "stdout: $($PromoteRun.StdoutFile)"
    Write-Host "stderr: $($PromoteRun.StderrFile)"
    Write-Host "stdout preview:"
    Write-Host (Get-Preview -Text $PromoteRun.Stdout)
    Write-Host "stderr preview:"
    Write-Host (Get-Preview -Text $PromoteRun.Stderr)
    throw "Proof anchor promotion failed. Captured output under: $PromoteRoot"
  }

  $PromoteRun.Stdout | Set-Content -LiteralPath $PromotionResultFile -Encoding UTF8
  $PromoteSummary = Convert-JsonOrThrow -Label "Promotion" -Text $PromoteRun.Stdout -StdoutFile $PromoteRun.StdoutFile -StderrFile $PromoteRun.StderrFile

  if ($PromoteSummary.ProofValidationStatus -ne "validated") {
    throw "Promotion did not validate. ProofValidationStatus=$($PromoteSummary.ProofValidationStatus)"
  }

  Write-Host "Promotion status: $($PromoteSummary.ProofValidationStatus)"
  Write-Host "Anchor address  : $($PromoteSummary.CoordRegionAddress)"

  Write-Host "=== ASSERT CURRENT PROOF ANCHOR READBACK ==="

  $AssertCommand = @"
`$ErrorActionPreference = 'Stop'
`$AssertParams = @{
  ProcessName = $(ConvertTo-PowerShellSingleQuotedString -Value $ProcessName)
  ProcessId = $RiftPid
  TargetWindowHandle = $(ConvertTo-PowerShellSingleQuotedString -Value $RiftHwnd)
  ProofCoordAnchorFile = $(ConvertTo-PowerShellSingleQuotedString -Value $ProofAnchorFile)
  OutputRoot = $(ConvertTo-PowerShellSingleQuotedString -Value $PromoteRoot)
  ProofAnchorMaxAgeSeconds = 120
  ReadbackSampleCount = 4
  ReadbackIntervalMilliseconds = 100
  Json = `$true
}
& $(ConvertTo-PowerShellSingleQuotedString -Value $AssertScript) @AssertParams
"@

  $AssertArgs = New-EncodedPowerShellCommandArguments -CommandText $AssertCommand
  $AssertRun = Invoke-CapturedProcess -Label "assert-current-readback" -OutputDirectory $PromoteRoot -FilePath "pwsh" -Arguments $AssertArgs

  if ($AssertRun.ExitCode -ne 0) {
    Write-Host "Assert failed."
    Write-Host "stdout: $($AssertRun.StdoutFile)"
    Write-Host "stderr: $($AssertRun.StderrFile)"
    Write-Host "stdout preview:"
    Write-Host (Get-Preview -Text $AssertRun.Stdout)
    Write-Host "stderr preview:"
    Write-Host (Get-Preview -Text $AssertRun.Stderr)
    throw "Current proof anchor readback assertion failed. Captured output under: $PromoteRoot"
  }

  $AssertRun.Stdout | Set-Content -LiteralPath $AssertResultFile -Encoding UTF8
  $AssertSummary = Convert-JsonOrThrow -Label "Assert" -Text $AssertRun.Stdout -StdoutFile $AssertRun.StdoutFile -StderrFile $AssertRun.StderrFile

  Write-Host "Assert status  : $($AssertSummary.Status)"
  Write-Host "Movement gate  : $($AssertSummary.MovementAllowed)"
  Write-Host "Summary file   : $($AssertSummary.SummaryFile)"

  if ($AssertSummary.Status -ne "valid" -or -not [bool]$AssertSummary.MovementAllowed) {
    throw "Proof anchor assertion did not become movement-valid."
  }

  Write-Host "RIFTREADER_PROMOTE_CURRENT_PID_PROOF_ANCHOR_FROM_BATCH_DONE"
}

# END_OF_SCRIPT_MARKER
