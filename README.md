# 🛡️ LLM Governance Engine (2026)
### **The Multi-Model Insight Bridge: Enterprise-Grade Observability & PII Guardrails**

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Angular](https://img.shields.io/badge/Frontend-Angular_18-DD0031?style=flat-square&logo=angular&logoColor=white)](https://angular.io/)
[![Security](https://img.shields.io/badge/Security-PII_Scanning-blueviolet?style=flat-square)](https://github.com/microsoft/presidio)
[![Ollama](https://img.shields.io/badge/Local_AI-Ollama-white?style=flat-square&logo=ollama)](https://ollama.com/)

The **LLM Governance Engine** is an advanced evaluation and monitoring framework designed to bridge the gap between **Cloud-based Frontier Models** (e.g., GPT-4o) and **Private Local Inference** (e.g., Llama 3.2). 

This platform serves as a "Security Gateway," ensuring that every interaction is audited for PII (Personally Identifiable Information) leaks, hardware efficiency, and cost-effectiveness—providing a unified dashboard for AI governance.



---

## 🏗️ System Architecture

The project follows a modern, decoupled architecture centered around an **Asynchronous Orchestration** pattern.

* **Frontend (Angular 18+):** Reactive UI utilizing RxJS and Signals for real-time token streaming and dynamic Radar Chart visualizations.
* **Backend (FastAPI):** High-performance Python engine managing the "Multi-Model Insight Bridge," orchestrating requests to both OpenAI and local Ollama instances.
* **Audit Layer (Microsoft Presidio):** In-flight scanning of prompts and responses to detect and score sensitive data leaks.
* **Telemetry (NVML/PSUtil):** Direct hardware integration to monitor VRAM and GPU utilization for local models, with graceful CPU fallback.
* **Persistence (PostgreSQL):** Robust storage for all benchmark metadata, safety scores, and historical audit logs.



---

## 🚀 Quick Start

### **1. Prerequisites**
* **Docker Desktop** (with Compose)
* **NVIDIA Drivers** (Optional, for GPU monitoring features)
* **OpenAI API Key** (for Cloud benchmarking)

### **2. Setup Environment**
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=your_actual_key_here
CLOUD_MODEL_NAME=gpt-4o
LOCAL_MODEL_NAME=llama3.2:latest
OLLAMA_BASE_URL=http://ollama-service:11434/v1
DATABASE_URL=postgresql+asyncpg://admin:password123@db:5432/llm_governance
```
### **3. Run the Stack**

```bash
# Build and launch all services in detached mode
docker-compose up --build -d
```
* **Dashboard UI:** http://localhost:4200

* **Interactive API Docs:** http://localhost:8000/docs

* **Ollama API:** http://localhost:11434

---

## 💎 Key Governance Features

### 📊 Real-Time Benchmark Radar

Compare models across 5 critical dimensions: Latency, Cost, Security, Faithfulness, and Hardware Intensity. The chart updates dynamically as tokens stream in, allowing for immediate ROI visualization.

### 🛡️ PII Guardrails

Automatic detection of 15+ sensitive entities (Emails, SSNs, Credit Cards) using Microsoft Presidio. The engine provides a normalized **Safety Score** based on detection confidence, effectively acting as a data-loss prevention (DLP) layer for LLMs.

### ⚡ Telemetry & ROI Tracking

* **GPU VRAM Monitoring:** Tracks real-time memory pressure for local models to optimize infrastructure allocation.

* **Cost Projection:** Calculates exact Cloud API expenses vs. the $0/token economy of local hardware.

* **Energy Metrics:** Estimates power consumption (Watts) to help meet corporate sustainability goals.

### 📄 One-Click Audit Reports

Export any benchmark session to a professional PDF report. These reports include full prompt/response pairs, security flags, and performance metadata, ready for compliance review.

---

## 📂 Project Structure

```
├── backend/
│   ├── app/
|   |   ├── api/
│   │   ├── core/           # Database setup and lifespan logic
│   │   ├── models/         # SQLAlchemy benchmark schemas
│   │   ├── services/       
│   │   │   ├── audit_service.py     # PII & Safety logic
│   │   │   └── llm_orchestrator.py  # Provider logic & streaming
│   │   └── main.py         # FastAPI routes
├── frontend/
│   ├── src/app/
│   │   ├── core/services       # Dashboard & History components
│   │   └── features/       # API and PDF generation services
└── docker-compose.yml       # Full stack containerization
```
---

## 📈 2026 Roadmap

- [x] **Phase 1: Foundation** - Multi-Model Streaming Orchestration (FastAPI + Angular).
- [x] **Phase 2: Security** - Microsoft Presidio PII Integration & Real-time Guardrails.
- [x] **Phase 3: Telemetry** - GPU/VRAM Hardware Monitoring & NVML Integration.
- [ ] **Phase 4: Advanced Eval** - RAG Faithfulness & Hallucination Scoring (RAGAS Integration).
- [ ] **Phase 5: Sustainability** - CO2 Emission tracking per inference session.
- [ ] **Phase 6: Enterprise Auth** - Multi-User Role-Based Access Control (RBAC) & OAuth2.
