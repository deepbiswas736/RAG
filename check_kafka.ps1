# Simple check for Kafka consumers

Write-Host "Checking Kafka Topics:"
docker exec rag_kafka kafka-topics --list --bootstrap-server kafka:29092

Write-Host "`nChecking Consumer Groups:"
docker exec rag_kafka kafka-consumer-groups --list --bootstrap-server kafka:29092

Write-Host "`nChecking LLM Service Status:"
curl -s http://localhost/api/llm/health | ConvertFrom-Json | ConvertTo-Json

Write-Host "`nChecking Metadata Consumer Status:"
curl -s http://localhost/api/llm/metadata/status | ConvertFrom-Json | ConvertTo-Json

Write-Host "`nCalling Metadata Fix API:"
curl -s -X POST http://localhost/api/llm/metadata/fix | ConvertFrom-Json | ConvertTo-Json

Write-Host "`nRestarting LLM Service:"
docker restart rag_llm-service
Start-Sleep -Seconds 10

Write-Host "`nChecking Consumer Groups Again:"
docker exec rag_kafka kafka-consumer-groups --list --bootstrap-server kafka:29092
