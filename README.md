<div align="center">

# LLM Governance Engine

**The open-source policy enforcement layer for enterprise LLM deployments.**

Every other tool monitors LLMs. This one enforces rules on them.

[![CI Pipeline](https://github.com/sochaty/llm-governance-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/sochaty/llm-governance-engine/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Angular](https://img.shields.io/badge/Angular-21-DD0031?logo=angular&logoColor=white)](https://angular.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

[**Quick Start**](#quick-start) · [**Features**](#features) · [**Policy Engine**](#policy-engine) · [**API Reference**](#api-reference) · [**Roadmap**](#roadmap) · [**Contributing**](#contributing)

</div>

---

## Why LLM Governance Engine?

Enterprises are deploying LLMs at scale and discovering three problems simultaneously:

| Problem | Existing Tools | This Project |
|---|---|---|
| PII leaks to cloud models | Detect after the fact | **Block before the model call** |
| Runaway cloud spend | Dashboard after the bill arrives | **Budget circuit breakers in the inference path** |
| No audit trail for compliance | Manual documentation | **Automatic signed audit log, PDF export** |

**The difference**: LangSmith, Arize, and Helicone observe your LLMs. The Governance Engine *enforces policy on them* — a YAML file that says "if PII confidence > 0.7 and model is cloud, block the request and alert Slack" is evaluated in under 5ms before any token leaves your network.

---

## Features

### 🔒 Policy Engine (Phase 4)
- **Policy-as-Code** — YAML rules express governance intent: `pii_detected`, `safety_score_below`, `cost_exceeds`, `model_is`
- **Pre-inference enforcement** — rules evaluated before the prompt reaches any LLM
- **Three actions**: `block` (HTTP 403 + structured error), `warn` (log + continue), `alert` (webhook + continue)
- **Hot-reload** — `POST /api/v1/policies/reload` applies new rules without restarting the server
- **CloudEvents 1.0 webhooks** — violations delivered to Slack, Teams, PagerDuty, or any HTTP endpoint with 3-attempt exponential backoff
- **Persistent audit log** — every violation stored in PostgreSQL with prompt preview, provider, severity, and webhook delivery status
- **Compliance templates** — `policies/hipaa.yaml` and `policies/gdpr.yaml` shipped out of the box

### 🔍 PII Detection & Safety Scoring
- **Microsoft Presidio** — detects 15+ entity types: email, phone, SSN, credit card, person name, and more
- **Per-entity confidence scoring** — policy thresholds operate on Presidio's confidence scores, not just boolean flags
- **Safety score** (0.0–1.0) derived from PII confidence inversion; stored on every benchmark record
- **Custom recognizer support** — add your own regex/NLP patterns for internal identifiers

### 📊 Cloud vs. Local Cost Sovereignty
- **Real-time streaming benchmarks** — run identical prompts against GPT-4o (cloud) and Llama 3.2 (local) simultaneously
- **10-dimension governance radar** — Speed, Cost Efficiency, Throughput, Safety, PII Protection, Faithfulness, Context Efficiency, GPU Optimization, Sustainability, Reliability
- **ROI calculation** — per-run cost delta (cloud spend minus local $0.00) accumulates into a total savings counter
- **GPU/VRAM telemetry** — optional NVML integration; schema includes `gpu_mem_usage` and `energy_watts`

### 🗂️ Audit & Compliance
- **Full audit trail** — every inference stored with prompt, response preview, latency, cost, PII flag, safety score, model version
- **One-click PDF reports** — generate a governance report for any audit record directly from the History view
- **Searchable history** — filter by prompt text or provider; paginated table with 50-record windows

---

## Quick Start

**Requirements:** Docker Desktop 4.x or later. An API key for at least one cloud provider is recommended but not required — you can run local-only with Ollama.

### Step 1 — Clone and create your env file

```bash
git clone https://github.com/sochaty/llm-governance-engine.git
cd llm-governance-engine
cp .env.example .env
```

Open `.env` and fill in at least one cloud provider key. Leave the others blank — the Settings page lets you add or rotate keys later without restarting the stack:

```env
# At minimum, add one of these:
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
GROQ_API_KEY=gsk_...

# Optional: generate a Fernet key to encrypt keys stored via the Settings UI
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SETTINGS_SECRET_KEY=
```

### Step 2 — Start the full stack

```bash
docker compose up --build
```

Everything starts in order — PostgreSQL, then the FastAPI backend (with a health-check gate), then the Angular/nginx frontend.

| Service       | URL                             |
|---------------|---------------------------------|
| Dashboard     | http://localhost:4200           |
| API docs      | http://localhost:8000/docs      |
| Ollama API    | http://localhost:11434          |

> **First run takes 3–5 minutes** — Docker pulls the Ollama image and the Angular build compiles. Subsequent starts are fast.

### Step 3 — Pull a local model (one-time)

The Governance Engine benchmarks cloud and local models side-by-side. Pull a local model to run the full comparison:

```bash
# Pull Llama 3.2 (2 GB) — takes 2–5 min on a decent connection
curl -X POST "http://localhost:8000/api/v1/models/local/pull?model_name=llama3.2"

# Or use the Model Selector panel on the Dashboard to browse and pull via the UI
```

### Step 4 — Configure cloud providers via the Settings UI

Navigate to **⚙ Settings** in the top nav. Enter your API keys — they are encrypted with Fernet before being stored in PostgreSQL, and the page shows the source (database / environment variable / unset) for each key.

You can also swap default models and timeouts from this page. Changes take effect on the next benchmark request — no restart required.

### Step 5 — Trigger your first governance block

Open the **Dashboard**, paste this prompt, and click **▶ Run Benchmark**:

```
My email is john@acme.com and my SSN is 123-45-6789. Help me debug this.
```

The cloud panel will show a red **CRITICAL** governance alert. The request was blocked by the default PII policy before any token left your network. Check `GET /api/v1/policies/violations` to see the recorded violation, or open **Audit Vault** to see it in the governance trail.

### Running backend tests locally

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # smaller model, fine for local dev
python -m pytest
```

Tests run against an in-memory SQLite database — no Docker or PostgreSQL required. The suite enforces a **90% coverage gate**: the build fails if coverage drops below this threshold.

---

## Policy Engine

The policy engine is the core of Phase 4. It evaluates a set of YAML-defined rules against every inference request *before* the prompt reaches any model.

### How it works

```
HTTP Request (prompt + provider)
        │
        ▼
PolicyEnforcementMiddleware
  ├─ AuditService.scan_for_pii_details(prompt)   → PIIScanResult
  ├─ Build GovernanceContext
  ├─ DefaultPolicyEngine.evaluate(context)        → PolicyVerdict
  │    ├─ Rule 1: pii_detected @ threshold=0.7  → BLOCK (fires)
  │    ├─ Rule 2: safety_score_below @ 0.5       → warn  (skipped)
  │    └─ Rule 3: pii_detected @ threshold=0.85  → alert (skipped)
  │
  ├─ verdict.passed = False → HTTP 403 + webhook (async)
  └─ verdict.passed = True  → LLMOrchestrator → stream tokens
```

### Writing policies

```yaml
# policies/default.yaml
version: "1.0"
name: "default"

rules:
  - id: pii-cloud-block
    name: "Block PII from cloud models"
    condition: pii_detected
    threshold: 0.7          # minimum Presidio confidence to trigger
    models: [cloud, gpt-4o] # omit to apply to all models
    action: block
    severity: critical
    webhook_url: null       # set to your Slack/Teams webhook URL

  - id: low-safety-warn
    name: "Warn on low safety score"
    condition: safety_score_below
    threshold: 0.5
    action: warn
    severity: medium
```

**Supported conditions:**

| Condition | Triggers when |
|---|---|
| `pii_detected` | Presidio finds PII with confidence ≥ `threshold` |
| `safety_score_below` | Computed safety score < `threshold` |
| `cost_exceeds` | Estimated per-request cost > `threshold` USD |
| `model_is` | Request targets a model in the `models` list |

**Supported actions:**

| Action | Effect |
|---|---|
| `block` | Returns HTTP 403 with structured error body; fires webhook; request never reaches the model |
| `warn` | Logs warning; fires webhook; request proceeds normally |
| `alert` | Fires webhook; request proceeds normally; violation recorded in DB |

### Compliance templates

Switch to a stricter policy without changing code:

```bash
# HIPAA — blocks PII ≥ 0.5 confidence from all cloud providers
curl -X POST "http://localhost:8000/api/v1/policies/reload?path=policies/hipaa.yaml"

# GDPR — blocks personal data ≥ 0.6 confidence from EU-external providers
curl -X POST "http://localhost:8000/api/v1/policies/reload?path=policies/gdpr.yaml"

# Back to default
curl -X POST "http://localhost:8000/api/v1/policies/reload"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Angular 21 Frontend                   │
│  Dashboard (radar chart, live stream, violation banner)  │
│  History   (audit table, PDF export)                     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│                  FastAPI Backend (Python 3.12)            │
│                                                          │
│  /api/benchmark/*   ←── PolicyEnforcementMiddleware      │
│                              │                           │
│                     GovernanceContext                    │
│                              │                           │
│                    DefaultPolicyEngine                   │
│                    (evaluates YAML rules)                │
│                              │                           │
│              passed? ────────┴──── blocked?             │
│                 │                       │                │
│         LLMOrchestrator          HTTP 403 + webhook      │
│      (stream tokens via OpenAI/Ollama)                   │
│                 │                                        │
│         AuditService (Presidio PII + safety score)       │
│                 │                                        │
│       BenchmarkResult + PolicyViolation → PostgreSQL     │
└──────────────────────────────────────────────────────────┘
         │                              │
   OpenAI API                     Ollama (local)
   (cloud inference)              (edge inference)
```

---

## Project Structure

```
llm-governance-engine/
├── backend/
│   └── app/
│       ├── main.py                        # FastAPI app, router registration
│       ├── core/database.py               # PostgreSQL async session
│       ├── models/
│       │   ├── benchmark.py               # BenchmarkResult ORM (15 columns)
│       │   └── policy_violation.py        # PolicyViolation ORM
│       ├── services/
│       │   ├── llm_orchestrator.py        # Stream from OpenAI/Ollama, record metrics
│       │   └── audit_service.py           # Presidio PII scanning, PIIScanResult
│       ├── governance/policy/
│       │   ├── schema.py                  # PolicyRule, GovernanceContext, PolicyVerdict
│       │   ├── engine.py                  # DefaultPolicyEngine (Chain of Responsibility)
│       │   ├── loader.py                  # YAML → GovernancePolicy
│       │   ├── webhook.py                 # CloudEvents 1.0 delivery with retry
│       │   └── enforcement.py             # FastAPI Depends — pre-inference gate
│       └── api/
│           ├── benchmark_router.py        # /api/benchmark/stream|history|stats
│           └── governance_router.py       # /api/v1/policies + /violations
├── frontend/
│   └── src/app/
│       ├── core/services/llm.service.ts   # Streaming fetch; GovernanceBlockedError
│       └── features/
│           ├── dashboard/                 # Live benchmarks, violation banners, radar chart
│           └── history/                   # Audit vault, PDF export
├── policies/
│   ├── default.yaml                       # 3 rules: PII block, safety warn, local alert
│   ├── hipaa.yaml                         # HIPAA-aligned PHI enforcement
│   └── gdpr.yaml                          # GDPR-aligned personal data enforcement
├── docker-compose.yml                     # db, ollama, backend, frontend
└── .github/workflows/ci.yml              # pytest + vitest on every PR
```

---

## API Reference

### Benchmark

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/benchmark/stream` | Stream LLM response (enforces active policy; returns 403 on violation) |
| `GET` | `/api/benchmark/history` | Last 50 benchmark records |
| `GET` | `/api/benchmark/stats` | Aggregate stats: total savings, avg latency, request count |

**Query params for `/stream`:**

| Param | Required | Example |
|---|---|---|
| `prompt` | Yes | `Explain recursion` |
| `provider` | No (default: `cloud`) | `cloud` or `local` |

### Governance

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/policies` | List active policy rules |
| `POST` | `/api/v1/policies/reload` | Hot-reload from disk (`?path=policies/hipaa.yaml`) |
| `GET` | `/api/v1/policies/violations` | Paginated violation history (`?severity=critical&limit=50`) |

### 403 Violation Response

When a `block` rule fires, the response body is:

```json
{
  "detail": {
    "error": "governance_violation",
    "rule_id": "pii-cloud-block",
    "rule_name": "Block PII from cloud models",
    "severity": "critical",
    "message": "PII detected (confidence 0.85): EMAIL_ADDRESS, PHONE_NUMBER"
  }
}
```

---

## Configuration

All configuration via environment variables (`.env` in project root or Docker Compose `environment:`).

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key (required for cloud provider) |
| `CLOUD_MODEL_NAME` | `gpt-4o` | Cloud model name |
| `LOCAL_MODEL_NAME` | `llama3.2:latest` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://ollama-service:11434/v1` | Ollama base URL |
| `DATABASE_URL` | — | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `GOVERNANCE_POLICY_PATH` | `policies/default.yaml` | Active policy file |
| `CLOUD_TIMEOUT` | `30.0` | Cloud model timeout (seconds) |
| `LOCAL_TIMEOUT` | `120.0` | Local model timeout (seconds) |

---

## Roadmap

| Phase | Feature | Status |
|---|---|---|
| **Phase 1** | Multi-model real-time streaming (FastAPI + Angular) | ✅ Complete |
| **Phase 2** | PII detection (Presidio) + safety scoring | ✅ Complete |
| **Phase 3** | GPU/VRAM telemetry, cost ROI, audit PDF export | ✅ Complete |
| **Phase 4** | Policy Engine — YAML rules, pre-inference enforcement, webhooks | ✅ Complete |
| **Phase 5** | Enterprise Auth — OAuth2/OIDC, RBAC, multi-tenant workspaces | 🔜 Planned |
| **Phase 6** | Advanced Evaluation — RAGAS hallucination scoring, pluggable model registry | 🔜 Planned |
| **Phase 7** | FinOps Dashboard — budget circuit breakers, cost anomaly detection | 🔜 Planned |
| **Phase 8** | Observability — OpenTelemetry, Prometheus metrics, pre-built Grafana dashboards | 🔜 Planned |

---

## Running Tests

```bash
cd backend
# Install dependencies
pip install -r requirements.txt

# Run full test suite (51 tests, ~25 seconds, no external services required)
pytest tests/ -v
```

Test coverage includes:
- **Policy engine** — all condition types, model filters, multi-violation scenarios
- **Webhook delivery** — CloudEvents format, retry logic, connection error handling
- **Audit service** — PII detection, safety scoring, exception handling
- **Orchestrator** — benchmark recording, cost logic, DB failure resilience
- **API endpoints** — health check, stream validation, history, stats

---

## Contributing

Contributions are welcome. Here's how to get started:

1. Fork the repository
2. Create a branch: `git checkout -b feat/your-feature`
3. Make your changes with tests
4. Run the test suite: `pytest tests/ -v`
5. Open a pull request against `main`

**Good first issues** to tackle:
- Add a Python SDK client for the governance API
- Add a TypeScript/Node.js SDK client
- Add a Slack webhook template for policy violations
- Add a PagerDuty webhook template
- Add German or French PII recognizers (Presidio supports custom languages)
- Add Azure OpenAI adapter to the model registry
- Add an Amazon Bedrock adapter to the model registry

---

## License

MIT © 2026 [Sourish Chakraborty](https://github.com/sochaty)
