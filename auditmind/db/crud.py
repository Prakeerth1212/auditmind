import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from auditmind.db.models import AuditRun, FindingRecord
from auditmind.orchestrator.state import Finding
from auditmind.synthesis.scorer import compute_risk_score

async def create_audit_run(
    db: AsyncSession,
    repo_url: str,
    repo_name: str,
) -> AuditRun:
    run = AuditRun(
        id=uuid.uuid4(),
        repo_url=repo_url,
        repo_name=repo_name,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run

async def get_audit_run(
    db: AsyncSession,
    audit_id: uuid.UUID,
) -> AuditRun | None:
    result = await db.execute(
        select(AuditRun).where(AuditRun.id == audit_id)
    )
    return result.scalar_one_or_none()

async def list_audit_runs(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[AuditRun]:
    result = await db.execute(
        select(AuditRun)
        .order_by(desc(AuditRun.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())

async def update_audit_status(
    db: AsyncSession,
    audit_id: uuid.UUID,
    status: str,
    error: str | None = None,
) -> None:
    run = await get_audit_run(db, audit_id)
    if run:
        run.status = status
        run.error = error
        if status in ("done", "failed"):
            run.completed_at = datetime.utcnow()
        await db.commit()

async def save_findings(
    db: AsyncSession,
    audit_id: uuid.UUID,
    findings: list[Finding],
    executive_summary: str,
    report_path: str | None,
) -> None:
    run = await get_audit_run(db, audit_id)
    if not run:
        return

    # save each finding as a DB record
    for f in findings:
        record = FindingRecord(
            id=uuid.uuid4(),
            audit_run_id=audit_id,
            agent=f.agent,
            title=f.title,
            description=f.description,
            severity=f.severity.value,
            file_path=f.file_path,
            line_number=f.line_number,
            recommendation=f.recommendation,
            raw_output=f.raw_output,
        )
        db.add(record)

    run.risk_score = compute_risk_score(findings)
    run.executive_summary = executive_summary
    run.report_path = report_path
    run.status = "done"
    run.completed_at = datetime.utcnow()

    await db.commit()

async def get_findings_for_run(
    db: AsyncSession,
    audit_id: uuid.UUID,
) -> list[FindingRecord]:
    result = await db.execute(
        select(FindingRecord)
        .where(FindingRecord.audit_run_id == audit_id)
        .order_by(FindingRecord.severity)
    )
    return list(result.scalars().all())