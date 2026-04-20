Set-StrictMode -Version Latest

function Get-LogEventTimeUtc {
    return [DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ', [System.Globalization.CultureInfo]::InvariantCulture)
}

function New-LogRunId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source
    )

    $normalizedSource = ($Source.Trim().ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($normalizedSource)) {
        $normalizedSource = 'run'
    }

    $timestamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMdd-HHmmss-fff', [System.Globalization.CultureInfo]::InvariantCulture)
    return '{0}-{1}' -f $normalizedSource, $timestamp
}

function New-StructuredLogEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [string]$RunId,

        [Parameter(Mandatory = $true)]
        [string]$Message,

        [object]$Data = $null,

        [hashtable]$LegacyFields
    )

    $entry = [ordered]@{
        eventTimeUtc = Get-LogEventTimeUtc
        level        = $Level.Trim().ToLowerInvariant()
        source       = $Source.Trim()
        runId        = $RunId.Trim()
        message      = $Message.Trim()
    }

    if ($null -ne $Data) {
        $entry['data'] = $Data
    }

    if ($null -ne $LegacyFields) {
        foreach ($key in $LegacyFields.Keys) {
            if (-not $entry.Contains($key)) {
                $entry[$key] = $LegacyFields[$key]
            }
        }
    }

    return $entry
}

function Write-StructuredLogLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [hashtable]$Entry
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        [System.IO.File]::WriteAllText($Path, '', [System.Text.UTF8Encoding]::new($false))
    }

    $jsonLine = $Entry | ConvertTo-Json -Compress -Depth 20
    [System.IO.File]::AppendAllText($Path, $jsonLine + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}
