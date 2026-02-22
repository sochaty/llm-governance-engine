from fastapi import FastAPI, Depends, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from .services.llm_orchestrator import LLMOrchestrator

# Enable Load environment variables from .env file for local development
from dotenv import load_dotenv

load_dotenv(override=True) 
# Note: In production, environment variables should be set securely and not stored in .env files.

app = FastAPI(title="LLM Governance Engine API")

# Enable CORS for Angular (Port 4200)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection
def get_orchestrator():
    return LLMOrchestrator()

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/benchmark/stream")
async def stream_llm(
    prompt: str = Query(..., min_length=1),
    provider: str = Query("cloud", regex="^(cloud|local)$"),
    orchestrator: LLMOrchestrator = Depends(get_orchestrator)
):
    """
    Endpoint that streams tokens back to the client.
    """
    return StreamingResponse(
        orchestrator.get_streaming_response(prompt, provider),
        media_type="text/event-stream"
    )