# auditmind/api/routes/report.py

import os
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from auditmind.db.crud import get_audit_run, get_findings_for_run
from auditmind.api.deps import DatabaseDep

router = APIRouter()


@router.get("/report/{audit_id}/pdf")
async def download_pdf(
    audit_id: str,
    db: DatabaseDep,
):
    """Streams the generated PDF report as a file download."""
    try:
        uid = uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID")

    run = await get_audit_run(db, uid)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found")

    if run.status != "done":
        raise HTTPException(
            status_code=404,
            detail="Report not ready — audit still in progress",
        )

    if not run.report_path or not os.path.exists(run.report_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    return FileResponse(
        path=run.report_path,
        media_type="application/pdf",
        filename=f"auditmind_{run.repo_name}_{audit_id[:8]}.pdf",
    )


@router.get("/report/{audit_id}/json")
async def get_json_report(
    audit_id: str,
    db: DatabaseDep,
):
    """Returns a full structured JSON report — useful for integrations."""
    try:
        uid = uuid.UUID(audit_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit ID")

    run = await get_audit_run(db, uid)
    if not run:
        raise HTTPException(status_code=404, detail="Audit run not found")

    findings = await get_findings_for_run(db, uid)

    # group by agent
    by_agent: dict = {}
    for f in findings:
        by_agent.setdefault(f.agent, []).append({
            "title": f.title,
            "description": f.description,
            "severity": f.severity,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "recommendation": f.recommendation,
        })

    return {
        "audit_id": audit_id,
        "repo_name": run.repo_name,
        "repo_url": run.repo_url,
        "risk_score": run.risk_score,
        "executive_summary": run.executive_summary,
        "severity_breakdown": {
            agent: {
                sev: sum(1 for f in flist if f["severity"] == sev)
                for sev in ["critical", "high", "medium", "low", "info"]
            }
            for agent, flist in by_agent.items()
        },
        "findings_by_agent": by_agent,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }