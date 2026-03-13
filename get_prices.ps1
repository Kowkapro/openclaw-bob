$json = Get-Content -Raw 'd:/Claude Code/Projects/Ai-agent/polza_catalog.json'
$obj = $json | ConvertFrom-Json
$list = $obj.data

Write-Output "Total models: $($list.Count)"
Write-Output ""
Write-Output "MODEL | INPUT_RUB_1M | OUTPUT_RUB_1M | CTX"
Write-Output "------|-------------|--------------|----"

foreach ($m in $list) {
    $id = $m.id
    if ($id -match 'minimax|deepseek/deepseek-v3|deepseek/deepseek-chat|claude|gemini-2\.5|gemini-3\.1-flash-lite|glm-5|glm-4\.7|gpt-5-nano|gpt-5-mini|gpt-5$|kimi-k2\.5|qwen3\.5-flash|qwen3\.5-122b|qwen3\.5-397b') {
        $p = $m.top_provider.pricing
        $ctx = $m.top_provider.context_length
        Write-Output "$id | $($p.prompt_per_million) | $($p.completion_per_million) | $ctx"
    }
}
