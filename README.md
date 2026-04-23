# AuditMind 🔍

> Autonomous multi-agent system that audits GitHub repositories for security vulnerabilities, cost inefficiencies, performance anti-patterns, and compliance gaps — and generates a professional PDF report.

---

## What it does

Point AuditMind at any GitHub repo URL. Four specialised AI agents fan out in parallel, each analysing a different dimension of the codebase:

| Agent           | Tools                         | What it finds                                                       |
| --------------- | ----------------------------- | ------------------------------------------------------------------- |
| **Security**    | Bandit, Semgrep, Gemini       | OWASP top-10, hardcoded secrets, injection risks                    |
| **Performance** | Python AST walker             | N+1 queries, nested loops, mutable defaults, string concat in loops |
| **Compliance**  | 14-point SOC2/GDPR checklist  | Missing auth, rate limiting, PII in logs, data retention            |
| **Cost**        | Terraform parser, pricing API | Over-provisioned instances, missing cost tags, open ingress         |

Findings are deduplicated across agents, severity-scored (0–100 risk score), and synthesised into an LLM-written executive summary — exported as a structured PDF report.

---

## Architecture

```
GitHub Repo URL
      ↓
  Ingestion (clone + file parser)
      ↓
  LangGraph Orchestrator
  ├── Security Agent  (Bandit + Semgrep + LLM)
  ├── Performance Agent  (AST walker + LLM)
  ├── Compliance Agent  (checklist + LLM)
  └── Cost Agent  (Terraform parser + LLM)
      ↓
  Synthesis (dedup + scoring + executive summary)
      ↓
  PDF Report + JSON API + PostgreSQL
```

---

## Tech stack

- **Orchestration** — LangGraph (StateGraph), LangChain
- **LLM** — Google Gemini 2.0 Flash
- **Static analysis** — Bandit, Semgrep, Python AST
- **Backend** — FastAPI, PostgreSQL, SQLAlchemy, Alembic
- **Workers** — Celery + Redis
- **MLOps** — MLflow experiment tracking
- **Report** — ReportLab PDF generation
- **Infra** — Docker Compose

---

## Quickstart

```bash
# 1. clone
git clone https://github.com/Prakeerth1212/auditmind.git
cd auditmind

# 2. install
pip install -e .
pip install bandit semgrep

# 3. configure
cp .env.example .env
# fill in GEMINI_API_KEY and GITHUB_TOKEN

# 4. set up database
alembic upgrade head

# 5. run an audit
python scripts/run_audit_cli.py https://github.com/your-target-repo
```

### Full stack (API + worker + dashboard)

```bash
docker compose up --build
```

---

## Sample output

```
============================================================
  AUDIT COMPLETE
============================================================
  Risk Score:  62/100
  Critical:    2
  High:        5
  Medium:      8
  Low:         4
  Total:       19
============================================================

EXECUTIVE SUMMARY
The audit of target-repo identified critical security vulnerabilities
including hardcoded API keys and shell injection risks. Eight compliance
gaps were detected against SOC 2 CC6.1 and GDPR Art.32 controls...
```

---

## Project structure

```
auditmind/
├── auditmind/
│   ├── agents/          # 4 specialised LangChain agents
│   ├── orchestrator/    # LangGraph StateGraph + supervisor
│   ├── tools/           # Bandit, Semgrep, AST, Terraform wrappers
│   ├── synthesis/       # Dedup, scoring, executive summary
│   ├── ingestion/       # GitHub clone + file parser
│   ├── report/          # PDF + JSON report generation
│   ├── api/             # FastAPI routes
│   ├── db/              # SQLAlchemy models + CRUD
│   └── worker/          # Celery async task runner
├── mlflow_tracking/     # Experiment tracking
├── tests/
├── docker/
└── scripts/
```

---

## API

```
POST /api/v1/audit          → trigger audit, returns audit_id
GET  /api/v1/audit/{id}     → poll status + risk score
GET  /api/v1/audit/{id}/findings  → all findings JSON
GET  /api/v1/report/{id}/pdf      → download PDF report
GET  /api/v1/report/{id}/json     → structured JSON report
```

---

## B2B use case

Any SaaS company preparing for SOC 2 certification or Series A due diligence pays $5k–$50k for a manual security audit. AuditMind automates the initial sweep in minutes, giving engineering teams a prioritised findings report they can act on immediately.

---

_Built with LangGraph, Gemini, FastAPI, and Python_
