from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auditmind.api.routes import audit, report, health
from auditmind.api.middleware import RequestLoggingMiddleware
from auditmind.config import settings

app = FastAPI(
    title="AuditMind",
    description="Autonomous multi-agent code and infra audit system",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(health.router, tags=["health"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
app.include_router(report.router, prefix="/api/v1", tags=["report"])