Write-Host "🚀 Starting LLM Governance Engine..." -ForegroundColor Cyan
docker-compose up -d --build

Write-Host "📦 Initializing Local LLM (Llama 3.2)..." -ForegroundColor Yellow
docker exec -it $(docker ps -qf "name=ollama") ollama pull llama3.2

Write-Host "✅ Success! UI: http://localhost:4200 | API: http://localhost:8000/docs" -ForegroundColor Green