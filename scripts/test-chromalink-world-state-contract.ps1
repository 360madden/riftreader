[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:7337',

    [string]$ManifestPath = '',

    [string]$SchemaPath = '',

    [string]$WorldStatePath = '',

    [switch]$SkipWorldState,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1
$expectedWorldStatePath = '/api/v1/riftreader/world-state'
$expectedSchemaPath = '/api/v1/riftreader/world-state/schema'
$expectedContractName = 'chromalink-riftreader-world-state'
$expectedContractSchemaVersion = 1
$expectedSchemaTitle = 'ChromaLink RiftReader World State'

function Resolve-EndpointUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Base,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return ('{0}{1}' -f $Base.TrimEnd('/'), $Path)
}

function Read-JsonDocument {
    param(
        [string]$Path,
        [string]$Url
    )

    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        $resolvedPath = [System.IO.Path]::GetFullPath($Path)
        if (-not (Test-Path -LiteralPath $resolvedPath)) {
            throw "JSON file not found: $resolvedPath"
        }

        return [pscustomobject]@{
            InputMode = 'file'
            Location = $resolvedPath
            Document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 128
        }
    }

    $response = Invoke-WebRequest -Method Get -Uri $Url -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 5
    if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -gt 299) {
        throw "HTTP GET failed: $Url status=$([int]$response.StatusCode)"
    }

    $content = if ($response.Content -is [byte[]]) {
        [System.Text.Encoding]::UTF8.GetString($response.Content)
    }
    else {
        [string]$response.Content
    }

    if ([string]::IsNullOrWhiteSpace($content)) {
        throw "HTTP GET returned an empty response: $Url"
    }

    return [pscustomobject]@{
        InputMode = 'http'
        Location = $Url
        Document = $content | ConvertFrom-Json -Depth 128
    }
}

function Get-PropertyValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }

        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-NestedValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $current = $InputObject
    foreach ($segment in $Path.Split('.')) {
        $current = Get-PropertyValue -InputObject $current -Name $segment
        if ($null -eq $current) {
            return $null
        }
    }

    return $current
}

function ConvertTo-DoubleOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        $number = [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            return $null
        }

        return $number
    }
    catch {
        return $null
    }
}

function Test-ManifestContract {
    param([object]$Document)

    $failures = [System.Collections.Generic.List[string]]::new()
    $endpoints = @(Get-PropertyValue -InputObject $Document -Name 'endpoints')
    $endpointPaths = @($endpoints | ForEach-Object { [string](Get-PropertyValue -InputObject $_ -Name 'path') })

    foreach ($requiredPath in @($expectedWorldStatePath, $expectedSchemaPath)) {
        if ($endpointPaths -notcontains $requiredPath) {
            $failures.Add("API manifest does not advertise required endpoint: $requiredPath") | Out-Null
        }
    }

    $localOnly = Get-PropertyValue -InputObject $Document -Name 'localOnly'
    if ($localOnly -ne $true) {
        $failures.Add("API manifest localOnly is not true; value=$localOnly.") | Out-Null
    }

    return $failures.ToArray()
}

function Test-SchemaContract {
    param([object]$Document)

    $failures = [System.Collections.Generic.List[string]]::new()
    $title = Get-PropertyValue -InputObject $Document -Name 'title'
    if ([string]$title -ne $expectedSchemaTitle) {
        $failures.Add("Schema title mismatch; expected '$expectedSchemaTitle', got '$title'.") | Out-Null
    }

    $contractNameConst = Get-NestedValue -InputObject $Document -Path '$defs.success.properties.contract.allOf'
    if ($null -eq $contractNameConst) {
        $failures.Add('Schema success contract allOf block is missing.') | Out-Null
    }
    else {
        $contractProperties = Get-NestedValue -InputObject @($contractNameConst)[1] -Path 'properties'
        $nameConst = Get-NestedValue -InputObject $contractProperties -Path 'name.const'
        $versionConst = Get-NestedValue -InputObject $contractProperties -Path 'schemaVersion.const'
        if ([string]$nameConst -ne $expectedContractName) {
            $failures.Add("Schema contract name const mismatch; expected '$expectedContractName', got '$nameConst'.") | Out-Null
        }
        if ([int]$versionConst -ne $expectedContractSchemaVersion) {
            $failures.Add("Schema contract version const mismatch; expected $expectedContractSchemaVersion, got $versionConst.") | Out-Null
        }
    }

    foreach ($field in @('headingAvailable', 'facingAvailable', 'routeAvailable', 'controlAvailable')) {
        $constValue = Get-NestedValue -InputObject $Document -Path ('$defs.navigation.properties.{0}.const' -f $field)
        if ($constValue -ne $false) {
            $failures.Add("Schema navigation.$field must be const false; value=$constValue.") | Out-Null
        }
    }

    $positionRequired = @(Get-NestedValue -InputObject $Document -Path '$defs.position.required')
    foreach ($axis in @('x', 'y', 'z')) {
        if ($positionRequired -notcontains $axis) {
            $failures.Add("Schema position.required is missing '$axis'.") | Out-Null
        }
    }

    return $failures.ToArray()
}

function Test-WorldStateContract {
    param([object]$Document)

    $failures = [System.Collections.Generic.List[string]]::new()
    $artifactKind = Get-PropertyValue -InputObject $Document -Name 'artifactKind'
    if ([string]$artifactKind -ne 'riftreader-world-state') {
        $failures.Add("World-state artifactKind mismatch; expected 'riftreader-world-state', got '$artifactKind'.") | Out-Null
    }

    $contractName = Get-NestedValue -InputObject $Document -Path 'contract.name'
    $contractVersion = Get-NestedValue -InputObject $Document -Path 'contract.schemaVersion'
    if ([string]$contractName -ne $expectedContractName) {
        $failures.Add("World-state contract name mismatch; expected '$expectedContractName', got '$contractName'.") | Out-Null
    }
    if ([int]$contractVersion -ne $expectedContractSchemaVersion) {
        $failures.Add("World-state contract version mismatch; expected $expectedContractSchemaVersion, got $contractVersion.") | Out-Null
    }

    foreach ($field in @('headingAvailable', 'facingAvailable', 'routeAvailable', 'controlAvailable')) {
        $value = Get-NestedValue -InputObject $Document -Path ('navigation.{0}' -f $field)
        if ($value -ne $false) {
            $failures.Add("World-state navigation.$field must be false; value=$value.") | Out-Null
        }
    }

    $position = Get-NestedValue -InputObject $Document -Path 'player.position'
    if ($null -eq $position) {
        $failures.Add('World-state player.position is missing.') | Out-Null
    }
    else {
        foreach ($axis in @('x', 'y', 'z')) {
            if ($null -eq (ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name $axis))) {
                $failures.Add("World-state player.position.$axis is missing or non-numeric.") | Out-Null
            }
        }
    }

    $navigationPlayerPositionAvailable = Get-NestedValue -InputObject $Document -Path 'navigation.playerPositionAvailable'
    if ($navigationPlayerPositionAvailable -ne $true) {
        $failures.Add("World-state navigation.playerPositionAvailable is not true; value=$navigationPlayerPositionAvailable.") | Out-Null
    }

    return $failures.ToArray()
}

$manifestUrl = Resolve-EndpointUrl -Base $BaseUrl -Path '/api/v1'
$schemaUrl = Resolve-EndpointUrl -Base $BaseUrl -Path $expectedSchemaPath
$worldStateUrl = Resolve-EndpointUrl -Base $BaseUrl -Path $expectedWorldStatePath

$failures = [System.Collections.Generic.List[string]]::new()
$manifestInfo = $null
$schemaInfo = $null
$worldStateInfo = $null

try {
    $manifestInfo = Read-JsonDocument -Path $ManifestPath -Url $manifestUrl
    foreach ($failure in @(Test-ManifestContract -Document $manifestInfo.Document)) {
        $failures.Add($failure) | Out-Null
    }
}
catch {
    $failures.Add($_.Exception.Message) | Out-Null
}

try {
    $schemaInfo = Read-JsonDocument -Path $SchemaPath -Url $schemaUrl
    foreach ($failure in @(Test-SchemaContract -Document $schemaInfo.Document)) {
        $failures.Add($failure) | Out-Null
    }
}
catch {
    $failures.Add($_.Exception.Message) | Out-Null
}

if (-not $SkipWorldState) {
    try {
        $worldStateInfo = Read-JsonDocument -Path $WorldStatePath -Url $worldStateUrl
        foreach ($failure in @(Test-WorldStateContract -Document $worldStateInfo.Document)) {
            $failures.Add($failure) | Out-Null
        }
    }
    catch {
        $failures.Add($_.Exception.Message) | Out-Null
    }
}

$status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'chromalink-world-state-contract'
    status = $status
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    baseUrl = $BaseUrl.TrimEnd('/')
    manifest = if ($null -eq $manifestInfo) { $null } else { [ordered]@{ inputMode = $manifestInfo.InputMode; location = $manifestInfo.Location } }
    schema = if ($null -eq $schemaInfo) { $null } else { [ordered]@{ inputMode = $schemaInfo.InputMode; location = $schemaInfo.Location } }
    worldState = if ($SkipWorldState -or $null -eq $worldStateInfo) { $null } else { [ordered]@{ inputMode = $worldStateInfo.InputMode; location = $worldStateInfo.Location } }
    skipWorldState = [bool]$SkipWorldState
    expectedContractName = $expectedContractName
    expectedContractSchemaVersion = $expectedContractSchemaVersion
    failures = $failures.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 16
}
else {
    $color = if ($status -eq 'pass') { 'Green' } else { 'Red' }
    Write-Host ("ChromaLink world-state contract: {0}" -f $status) -ForegroundColor $color
    foreach ($failure in @($result.failures)) {
        Write-Host ("- {0}" -f $failure) -ForegroundColor Red
    }
}

if ($status -ne 'pass') {
    exit 1
}
