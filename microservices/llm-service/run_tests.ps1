# Run all unit tests with detailed output
$env:PYTHONPATH = "e:\code\experimental\RAG\microservices\llm-service"
Write-Host "Running unit tests..." -ForegroundColor Cyan
python -m pytest tests/unit -v
$unit_exit_code = $LASTEXITCODE

if ($env:OLLAMA_INTEGRATION_TESTS -eq "true") {
    Write-Host "`nRunning integration tests with Ollama..." -ForegroundColor Yellow
    Write-Host "Note: Ensure Ollama is running at http://localhost:11434 or set OLLAMA_BASE_URL env var" -ForegroundColor Yellow
    python -m pytest tests/integration -v
    $integration_exit_code = $LASTEXITCODE
} else {
    Write-Host "`nSkipping integration tests. Set OLLAMA_INTEGRATION_TESTS=true to run them." -ForegroundColor Yellow
    $integration_exit_code = 0
}

if ($unit_exit_code -eq 0 -and $integration_exit_code -eq 0) {
    Write-Host "`nAll tests passed successfully!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`nTests failed! Check the output above for details." -ForegroundColor Red
    exit 1
}
