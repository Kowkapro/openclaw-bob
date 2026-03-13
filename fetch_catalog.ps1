$allModels = @()
$offset = 0
$limit = 100

do {
    $url = "https://polza.ai/api/v1/models/catalog?limit=$limit&offset=$offset"
    $resp = Invoke-RestMethod -Uri $url -Headers @{'Authorization'="Bearer $env:POLZA_API_KEY"}
    $batch = $resp.data
    if ($batch.Count -eq 0) { break }
    $allModels += $batch
    $offset += $limit
    Write-Host "Fetched $($allModels.Count) models so far..."
} while ($batch.Count -eq $limit)

Write-Host "Total: $($allModels.Count) models"

$wrapper = @{ data = $allModels }
$wrapper | ConvertTo-Json -Depth 10 -Compress | Set-Content 'd:/Claude Code/Projects/Ai-agent/polza_catalog_full.json'
