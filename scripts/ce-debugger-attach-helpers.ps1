Set-StrictMode -Version Latest

function Get-TraceStatusValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Status,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Status.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Test-CeDebuggerAttachFailureStatus {
    param(
        [psobject]$Status
    )

    if ($null -eq $Status) {
        return $false
    }

    $statusValue = [string](Get-TraceStatusValue -Status $Status -Name 'Status')
    if ([string]::IsNullOrWhiteSpace($statusValue)) {
        $statusValue = [string](Get-TraceStatusValue -Status $Status -Name 'status')
    }

    if ($statusValue -ne 'error') {
        return $false
    }

    $stageValue = [string](Get-TraceStatusValue -Status $Status -Name 'Stage')
    if ([string]::IsNullOrWhiteSpace($stageValue)) {
        $stageValue = [string](Get-TraceStatusValue -Status $Status -Name 'stage')
    }

    return @('debug-attach', 'debug-ready') -contains $stageValue
}

function Join-TraceNotes {
    param(
        [string[]]$Parts
    )

    $cleanParts = @($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($cleanParts.Count -le 0) {
        return $null
    }

    return ($cleanParts -join '; ')
}

function Write-CeDebuggerAttachLedgerEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [psobject]$Status,

        [string]$StatusFile,
        [string]$LedgerFile = (Join-Path $PSScriptRoot 'captures\ce-debugger-attach-failures.csv'),
        [string]$Notes
    )

    if (-not (Test-CeDebuggerAttachFailureStatus -Status $Status)) {
        return $false
    }

    $loggerScript = Join-Path $PSScriptRoot 'log-ce-debugger-failure.ps1'
    if (-not (Test-Path -LiteralPath $loggerScript)) {
        Write-Warning ("CE attach-failure logger script was not found: {0}" -f $loggerScript)
        return $false
    }

    $errorText = [string](Get-TraceStatusValue -Status $Status -Name 'Error')
    if ([string]::IsNullOrWhiteSpace($errorText)) {
        $errorText = [string](Get-TraceStatusValue -Status $Status -Name 'error')
    }

    $stageValue = [string](Get-TraceStatusValue -Status $Status -Name 'Stage')
    if ([string]::IsNullOrWhiteSpace($stageValue)) {
        $stageValue = [string](Get-TraceStatusValue -Status $Status -Name 'stage')
    }

    if ([string]::IsNullOrWhiteSpace($errorText)) {
        if ([string]::IsNullOrWhiteSpace($stageValue)) {
            $errorText = 'CE debugger attach failed.'
        }
        else {
            $errorText = "CE debugger trace failed during stage '$stageValue'."
        }
    }

    $joinedNotes = Join-TraceNotes -Parts @(
        $(if (-not [string]::IsNullOrWhiteSpace($stageValue)) { "stage=$stageValue" }),
        $Notes
    )

    try {
        & $loggerScript `
            -ScriptName (Split-Path -Leaf $ScriptPath) `
            -ErrorText $errorText `
            -LedgerFile $LedgerFile `
            -StatusFile $StatusFile `
            -Notes $joinedNotes | Out-Null
        return $true
    }
    catch {
        Write-Warning ("Unable to append CE debugger attach failure ledger entry: {0}" -f $_.Exception.Message)
        return $false
    }
}
