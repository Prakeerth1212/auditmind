# auditmind/api/routes/audit.py

import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from auditmind.db.crud import (
    create_audit_run,
    get_audit_run,
    list_audit_runs,
    update_audit_status,
    save_findings,
    get_findings_for_run,
)
from auditmind.api.deps import DatabaseDep
from auditmind.ingestion.github_client import get_repo_name
from auditmind.worker.tasks import run_audit_task
from auditmind.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class AuditRequest(BaseModel):
    repo_url: str
    # HttpUrl validates format but we keep str for flexibility


class AuditResponse(BaseModel):
    audit_id: str
    status: str
    message: str


@router.post("/audit", response_model=AuditResponse)
async def create_audit(
    body: AuditRequest,
    db: DatabaseDep,
):
    """
    Accepts a GitHub repo URL, creates an audit run,
    dispatches the job to Celery, and returns immediately.
    """
    repo_name = get_repo_name(body.repo_url)

    # create DB record
    run = await create_audit_run(db, body.repo_url, repo_name)

    # dispatch to Celery worker — non-blocking
    run_audit_task.delay(str(run.id), body.repo_url)

    logger.info(f"Audit dispatched: {run.id} for {body.repo_url}")

    return AuditResponse(
        audit_id=str(run.id),
        status="pending",
        message=f"Audit started for {repo_name}. Poll /api/v1/audit/{run.id} for status.",
    )


@router.get("/audit/{audit_id}")
async def get_audit(
    audit_id: str,
    db: DatabaseDep,
):
    """Returns current status + metadata of an audit run."""
    try:
        uid = uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID format")

    run = await get_audit_run(db, uid)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found")

    return {
        "audit_id": str(run.id),
        "repo_url": run.repo_url,
        "repo_name": run.repo_name,
        "status": run.status,
        "risk_score": run.risk_score,
        "executive_summary": run.executive_summary,
        "report_path": run.report_path,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/audit/{audit_id}/findings")
async def get_findings(
    audit_id: str,
    db: DatabaseDep,
):
    """Returns all findings for a completed audit run."""
    try:
        uid = uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID format")

    run = await get_audit_run(db, uid)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found")

    if run.status not in ("done", "failed"):
        raise HTTPException(
            status_code=202,
            detail=f"Audit is still {run.status}. Try again shortly.",
        )

    findings = await get_findings_for_run(db, uid)

    return {
        "audit_id": audit_id,
        "total": len(findings),
        "findings": [
            {
                "id": str(f.id),
                "agent": f.agent,
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "recommendation": f.recommendation,
            }
            for f in findings
        ],
    }


@router.get("/audits")
async def list_audits(
    db: DatabaseDep,
    limit: int = 20,
    offset: int = 0,
):
    """Lists recent audit runs for the dashboard."""
    runs = await list_audit_runs(db, limit=limit, offset=offset)
    return {
        "runs": [
            {
                "audit_id": str(r.id),
                "repo_name": r.repo_name,
                "status": r.status,
                "risk_score": r.risk_score,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]
    }