[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$File,

    [string]$Kind = 'note',
    [string]$Label,
    [string]$Message,
    [string]$Source = 'manual',
    [string[]]$Metadata,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function ConvertTo-MarkerKind {
    param(
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'note'
    }

    $normalized = ($Value.Trim().ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return 'note'
    }

    return $normalized
}

function ConvertTo-MetadataMap {
    param(
        [string[]]$Pairs
    )

    $result = [ordered]@{}
    foreach ($pair in @($Pairs)) {
        if ([string]::IsNullOrWhiteSpace($pair)) {
            continue
        }

        $splitIndex = $pair.IndexOf('=')
        if ($splitIndex -lt 1 -or $splitIndex -ge ($pair.Length - 1)) {
            throw "Metadata entry '$pair' must use key=value format."
        }

        $key = $pair.Substring(0, $splitIndex).Trim()
        $value = $pair.Substring($splitIndex + 1).Trim()
        if ([string]::IsNullOrWhiteSpace($key) -or [string]::IsNullOrWhiteSpace($value)) {
            throw "Metadata entry '$pair' must use non-empty key=value format."
        }

        $result[$key] = $value
    }

    return $result
}

$resolvedFile = [System.IO.Path]::GetFullPath($File)
$directory = Split-Path -Path $resolvedFile -Parent
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedFile)) {
    [System.IO.File]::WriteAllText($resolvedFile, '', [System.Text.UTF8Encoding]::new($false))
}

$metadataMap = ConvertTo-MetadataMap -Pairs $Metadata
$marker = [ordered]@{
    Kind = ConvertTo-MarkerKind -Value $Kind
    Label = $(if ([string]::IsNullOrWhiteSpace($Label)) { $null } else { $Label.Trim() })
    Message = $(if ([string]::IsNullOrWhiteSpace($Message)) { $null } else { $Message.Trim() })
    Source = $(if ([string]::IsNullOrWhiteSpace($Source)) { $null } else { $Source.Trim() })
    Metadata = $(if ($metadataMap.Count -gt 0) { $metadataMap } else { $null })
}

$jsonLine = ($marker | ConvertTo-Json -Compress -Depth 8)
[System.IO.File]::AppendAllText($resolvedFile, $jsonLine + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

if ($Json) {
    [ordered]@{
        Mode = 'append-session-marker'
        File = $resolvedFile
        Marker = $marker
    } | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host ("Appended session marker to {0}" -f $resolvedFile) -ForegroundColor Green
Write-Host ("Kind:    {0}" -f $marker.Kind)
Write-Host ("Source:  {0}" -f $(if ($null -eq $marker.Source) { 'n/a' } else { $marker.Source }))
if ($null -ne $marker.Label) {
    Write-Host ("Label:   {0}" -f $marker.Label)
}
if ($null -ne $marker.Message) {
    Write-Host ("Message: {0}" -f $marker.Message)
}
