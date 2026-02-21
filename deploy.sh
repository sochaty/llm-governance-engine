#!/bin/bash
echo "🔥 Building LLM Governance Engine..."
docker-compose up -d --build

echo "📦 Pulling Local LLM (Llama 3.2)..."
docker exec -it $(docker ps -qf "name=ollama") ollama pull llama3.2

echo "✅ Success! Access the Dashboard at http://localhost:4200"
echo "✅ API Docs available at http://localhost:8000/docs"