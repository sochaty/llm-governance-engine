# deploy.ps1
Write-Host "🔥 Initializing Enterprise LLM Engine..." -ForegroundColor Cyan

# 0. Stop and remove existing containers, networks, and images (Optional: add -v to remove volumes)
Write-Host "🛑 Stopping any running containers..." -ForegroundColor Red
docker compose down --remove-orphans

# 1. Start Docker Containers
docker compose up -d --build

# 2. Wait for Ollama to be ready
Write-Host "⏳ Waiting for Ollama container to start..." -ForegroundColor Yellow
$retryCount = 0
$maxRetries = 10
$containerName = "ollama-service"
$found = $false

while ($retryCount -lt $maxRetries) {
    $containerStatus = docker ps -qf "name=$containerName"
    if ($containerStatus) {
        Write-Host "✅ Container $containerName found!" -ForegroundColor Green
        $found = $true
        break
    }
    Write-Host "..."
    Start-Sleep -Seconds 2
    $retryCount++
}

# 3. Pull the Model
if ($found) {
    Write-Host "⏳ Pulling the model into Ollama..." -ForegroundColor Yellow
    docker exec $containerName ollama pull llama3.2
} else {
    Write-Host "❌ Container $containerName not found after $maxRetries attempts." -ForegroundColor Red
}

Write-Host ""
Write-Host "------------------------------------------------" -ForegroundColor White
Write-Host "✅ FRONTEND: http://localhost:4200" -ForegroundColor Green
Write-Host "✅ API DOCS: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "------------------------------------------------" -ForegroundColor White