[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,
        [Parameter(Mandatory = $true)]
        $Expected,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Depth = 40
    )

    $command = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($command.Parameters.ContainsKey('Depth')) {
        return $Text | ConvertFrom-Json -Depth $Depth
    }

    return $Text | ConvertFrom-Json
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$importer = Join-Path $repoRoot 'scripts\import-riftscan-coordinate-candidates.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-riftscan-import-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $jsonlFile = Join-Path $tempRoot 'vec3-truth-candidates.jsonl'
    $jsonlOut = Join-Path $tempRoot 'jsonl-watchset.json'
    $jsonlLines = @(
        '{"schema_version":"riftscan.vec3_truth_candidate.v1","candidate_id":"vec3-truth-000001","base_address_hex":"0x1000","offset_hex":"0x48","classification":"position_like_vec3_candidate","score_total":42.5,"truth_readiness":"strong_candidate","corroboration_status":"not_requested","validation_status":"behavior_consistent_candidate","confidence_level":"high","stimulus_label":"passive_idle","value_preview":[1.25,2.5,3.75],"value_sequence_summary":"samples=2;delta=0;preview=1.25|2.5|3.75","evidence_summary":"fixture top"}',
        '{"schema_version":"riftscan.vec3_truth_candidate.v1","candidate_id":"vec3-truth-000002","base_address_hex":"0x2000","offset_hex":"0x88","classification":"position_like_vec3_candidate","score_total":40.0,"truth_readiness":"strong_candidate","evidence_summary":"fixture second"}'
    )
    Set-Content -LiteralPath $jsonlFile -Value $jsonlLines -Encoding UTF8

    & $importer -CandidateFile $jsonlFile -OutputFile $jsonlOut -ProcessId 1234 -TargetWindowHandle 0x123 -TopCount 1 -ContextBytes 16 -Json | Out-Null

    $jsonlWatchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $jsonlOut -Raw) -Depth 40
    Assert-Equal -Actual $jsonlWatchset.Mode -Expected 'riftscan-coordinate-candidate-watchset' -Message 'Unexpected JSONL watchset mode.'
    Assert-Equal -Actual $jsonlWatchset.CandidateCount -Expected 1 -Message 'TopCount should cap JSONL candidates.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].CandidateId -Expected 'vec3-truth-000001' -Message 'Highest score JSONL candidate should be selected.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].AddressHex -Expected '0x1048' -Message 'Candidate absolute address should be base plus offset.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].AbsoluteAddressHex -Expected '0x1048' -Message 'Candidate absolute address alias should be populated.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].XOffsetHex -Expected '0x48' -Message 'Candidate X offset should use offset_hex.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].YOffsetHex -Expected '0x4C' -Message 'Candidate Y offset should default to X+4.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].ZOffsetHex -Expected '0x50' -Message 'Candidate Z offset should default to X+8.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].ValidationStatus -Expected 'behavior_consistent_candidate' -Message 'Candidate validation status should be preserved.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].ConfidenceLevel -Expected 'high' -Message 'Candidate confidence level should be preserved.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].StimulusLabel -Expected 'passive_idle' -Message 'Candidate stimulus label should be preserved.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].ValuePreview[0] -Expected 1.25 -Message 'Candidate value preview should be preserved.'
    Assert-Equal -Actual $jsonlWatchset.Candidates[0].ValueSequenceSummary -Expected 'samples=2;delta=0;preview=1.25|2.5|3.75' -Message 'Candidate value summary should be preserved.'
    Assert-Equal -Actual $jsonlWatchset.Regions[0].Address -Expected '0x1038' -Message 'Region should include requested pre-context.'
    Assert-Equal -Actual $jsonlWatchset.Regions[0].Length -Expected 44 -Message 'Region length should be pre-context plus vec3 plus post-context.'
    Assert-True -Condition ([bool]$jsonlWatchset.NoCheatEngine) -Message 'Watchset must mark NoCheatEngine=true.'
    Assert-True -Condition (-not [bool]$jsonlWatchset.MovementAllowed) -Message 'Watchset must block movement.'
    Assert-Equal -Actual $jsonlWatchset.CanonicalCoordSource -Expected 'none-candidate-watchset-only' -Message 'Candidate watchset must not claim canonical coord truth.'

    $promotionFile = Join-Path $tempRoot 'vec3-truth-promotion.json'
    $promotionOut = Join-Path $tempRoot 'promotion-watchset.json'
    $promotion = [ordered]@{
        schema_version = 'riftscan.vec3_truth_promotion.v1'
        success = $true
        recommended_manual_review_candidate_id = 'vec3-promoted-000001'
        promoted_candidates = @(
            [ordered]@{
                schema_version = 'riftscan.vec3_promoted_truth_candidate.v1'
                candidate_id = 'vec3-promoted-000001'
                base_address_hex = '0x3000'
                offset_hex = '0x48'
                x_offset_hex = '0x48'
                y_offset_hex = '0x4C'
                z_offset_hex = '0x50'
                classification = 'position_like_vec3_candidate'
                best_score_total = 75.25
                truth_readiness = 'corroborated_candidate'
                promotion_status = 'corroborated_candidate'
                corroboration_status = 'corroborated'
                evidence_summary = 'fixture promoted'
            },
            [ordered]@{
                schema_version = 'riftscan.vec3_promoted_truth_candidate.v1'
                candidate_id = 'vec3-promoted-blocked'
                base_address_hex = '0x4000'
                offset_hex = '0x48'
                x_offset_hex = '0x48'
                classification = 'position_like_vec3_candidate'
                best_score_total = 99.0
                truth_readiness = 'blocked_conflict'
                promotion_status = 'blocked_conflict'
                corroboration_status = 'conflicted'
            }
        )
    }
    $promotion | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $promotionFile -Encoding UTF8

    & $importer -CandidateFile $promotionFile -OutputFile $promotionOut -TopCount 4 -ContextBytes 0 -Json | Out-Null

    $promotionWatchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $promotionOut -Raw) -Depth 40
    Assert-Equal -Actual $promotionWatchset.CandidateCount -Expected 1 -Message 'Blocked promotion candidates should be excluded by default.'
    Assert-Equal -Actual $promotionWatchset.Candidates[0].CandidateId -Expected 'vec3-promoted-000001' -Message 'Expected unblocked promoted candidate.'
    Assert-Equal -Actual $promotionWatchset.Candidates[0].AddressHex -Expected '0x3048' -Message 'Promotion candidate absolute address should be base plus x_offset_hex.'
    Assert-Equal -Actual $promotionWatchset.Candidates[0].AbsoluteAddressHex -Expected '0x3048' -Message 'Promotion candidate absolute address alias should be populated.'
    Assert-Equal -Actual $promotionWatchset.Candidates[0].YOffsetHex -Expected '0x4C' -Message 'Promotion candidate should preserve provided Y offset.'
    Assert-Equal -Actual $promotionWatchset.Candidates[0].ZOffsetHex -Expected '0x50' -Message 'Promotion candidate should preserve provided Z offset.'
    Assert-Equal -Actual $promotionWatchset.Regions[0].Length -Expected 12 -Message 'Zero-context region should be exactly vec3 length.'
    Assert-True -Condition (-not [bool]$promotionWatchset.MovementAllowed) -Message 'Promotion-derived watchset must still block movement.'

    $addonMatchFile = Join-Path $tempRoot 'addon-coordinate-matches.json'
    $addonMatchOut = Join-Path $tempRoot 'addon-match-watchset.json'
    $addonMatch = [ordered]@{
        result_schema_version = 'riftscan.rift_session_addon_coordinate_match_result.v1'
        success = $true
        candidates = @(
            [ordered]@{
                candidate_id = 'rift-addon-coordinate-candidate-000001'
                source_region_id = 'region-000001'
                source_base_address_hex = '0x5000'
                source_offset_hex = '0xC0'
                source_absolute_address_hex = '0x50C0'
                axis_order = 'xyz'
                support_count = 3
                best_max_abs_distance = 0.003
                best_memory_x = 10.25
                best_memory_y = 20.5
                best_memory_z = 30.75
                validation_status = 'candidate_unverified'
                evidence_summary = 'fixture addon coordinate match'
            }
        )
    }
    $addonMatch | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $addonMatchFile -Encoding UTF8

    & $importer -CandidateFile $addonMatchFile -OutputFile $addonMatchOut -TopCount 4 -ContextBytes 16 -Json | Out-Null

    $addonMatchWatchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $addonMatchOut -Raw) -Depth 40
    Assert-Equal -Actual $addonMatchWatchset.CandidateCount -Expected 1 -Message 'Addon coordinate match candidate should be imported directly.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].CandidateId -Expected 'rift-addon-coordinate-candidate-000001' -Message 'Addon match candidate id should be preserved.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].AddressHex -Expected '0x50C0' -Message 'Addon match absolute address should be base plus source offset.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].XOffsetHex -Expected '0xC0' -Message 'Addon match X offset should use source_offset_hex.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].YOffsetHex -Expected '0xC4' -Message 'Addon match Y offset should default to source_offset_hex+4.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].ZOffsetHex -Expected '0xC8' -Message 'Addon match Z offset should default to source_offset_hex+8.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].Classification -Expected 'addon_coordinate_match_candidate' -Message 'Addon match candidates should get a useful classification fallback.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].Score -Expected 3 -Message 'Addon match candidate score should use support_count when no explicit score exists.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].AxisOrder -Expected 'xyz' -Message 'Addon match candidate axis order should be preserved.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].SupportCount -Expected 3 -Message 'Addon match support count should be preserved.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].BestMaxAbsDistance -Expected 0.003 -Message 'Addon match best distance should be preserved.'
    Assert-Equal -Actual $addonMatchWatchset.Candidates[0].ValuePreview[2] -Expected 30.75 -Message 'Addon match candidate value preview should be derived from best memory xyz.'
    Assert-Equal -Actual $addonMatchWatchset.Regions[0].Address -Expected '0x50B0' -Message 'Addon match region should include requested pre-context.'

    $addonRankFile = Join-Path $tempRoot 'addon-coordinate-rank-matches.json'
    $addonRankOut = Join-Path $tempRoot 'addon-rank-watchset.json'
    $addonRank = [ordered]@{
        result_schema_version = 'riftscan.rift_session_addon_coordinate_match_result.v1'
        success = $true
        candidates = @(
            [ordered]@{
                candidate_id = 'aaa-worse-distance'
                source_region_id = 'region-000002'
                source_base_address_hex = '0x6000'
                source_offset_hex = '0xC0'
                source_absolute_address_hex = '0x60C0'
                axis_order = 'xyz'
                support_count = 3
                observation_support_count = 1
                best_max_abs_distance = 1.5
            },
            [ordered]@{
                candidate_id = 'zzz-better-distance'
                source_region_id = 'region-000003'
                source_base_address_hex = '0x7000'
                source_offset_hex = '0xC0'
                source_absolute_address_hex = '0x70C0'
                axis_order = 'xyz'
                support_count = 3
                observation_support_count = 1
                best_max_abs_distance = 0.01
            }
        )
    }
    $addonRank | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $addonRankFile -Encoding UTF8

    & $importer -CandidateFile $addonRankFile -OutputFile $addonRankOut -TopCount 1 -ContextBytes 16 -Json | Out-Null

    $addonRankWatchset = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $addonRankOut -Raw) -Depth 40
    Assert-Equal -Actual $addonRankWatchset.Candidates[0].CandidateId -Expected 'zzz-better-distance' -Message 'Addon match ranking should prefer lower best_max_abs_distance when support is tied.'

    $badAxisFile = Join-Path $tempRoot 'addon-coordinate-bad-axis.json'
    $badAxisOut = Join-Path $tempRoot 'addon-bad-axis-watchset.json'
    $badAxis = [ordered]@{
        result_schema_version = 'riftscan.rift_session_addon_coordinate_match_result.v1'
        success = $true
        candidates = @(
            [ordered]@{
                candidate_id = 'bad-axis'
                source_region_id = 'region-000004'
                source_base_address_hex = '0x8000'
                source_offset_hex = '0xC0'
                axis_order = 'xzy'
                support_count = 3
            }
        )
    }
    $badAxis | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $badAxisFile -Encoding UTF8

    $badAxisFailed = $false
    $badAxisMessage = ''
    try {
        & $importer -CandidateFile $badAxisFile -OutputFile $badAxisOut -TopCount 1 -ContextBytes 16 -Json | Out-Null
    }
    catch {
        $badAxisFailed = $true
        $badAxisMessage = $_.Exception.Message
    }

    Assert-True -Condition $badAxisFailed -Message 'Importer should fail closed for unsupported axis_order.'
    Assert-True -Condition ($badAxisMessage -like '*unsupported axis_order*') -Message 'Unsupported axis failure should mention axis_order.'

    Write-Host 'RiftScan coordinate candidate importer regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
