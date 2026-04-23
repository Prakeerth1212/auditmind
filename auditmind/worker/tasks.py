import asyncio
import uuid
from auditmind.worker.celery_app import celery_app
from auditmind.orchestrator.graph import audit_graph
from auditmind.orchestrator.state import AgentStatus
from auditmind.db.session import AsyncSessionLocal
from auditmind.db.crud import (
    update_audit_status,
    save_findings,
    get_audit_run,
)
from auditmind.ingestion.github_client import cleanup_repo
from auditmind.mlflow_tracking.tracker import track_audit_run
from auditmind.logger import get_logger
logger = get_logger(__name__)

@celery_app.task(
    name="auditmind.run_audit",
    bind=True,
    max_retries=3,
)
def run_audit_task(self, audit_id: str, repo_url: str):
    """
    Celery task — runs the full LangGraph audit pipeline.
    Executed in the worker container, not the API container.
    """
    logger.info(f"[task] starting audit {audit_id} for {repo_url}")

    try:
        asyncio.run(_run_audit_async(audit_id, repo_url))
    except Exception as exc:
        logger.error(f"[task] audit {audit_id} failed: {exc}")
        asyncio.run(_mark_failed(audit_id, str(exc)))

        # retry with exponential backoff: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

async def _run_audit_async(audit_id: str, repo_url: str):
    async with AsyncSessionLocal() as db:
        # mark as running
        await update_audit_status(db, uuid.UUID(audit_id), "running")

    initial_state = {
        "audit_id": audit_id,
        "repo_url": repo_url,
        "repo_context": None,
        "security_status": AgentStatus.PENDING,
        "cost_status": AgentStatus.PENDING,
        "performance_status": AgentStatus.PENDING,
        "compliance_status": AgentStatus.PENDING,
        "findings": [],
        "deduplicated_findings": [],
        "severity_counts": {},
        "executive_summary": "",
        "report_path": None,
        "error": None,
    }

    logger.info(f"[task] invoking LangGraph for {audit_id}")
    final_state = await audit_graph.ainvoke(initial_state)

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])

    async with AsyncSessionLocal() as db:
        await save_findings(
            db=db,
            audit_id=uuid.UUID(audit_id),
            findings=final_state["deduplicated_findings"],
            executive_summary=final_state["executive_summary"],
            report_path=final_state["report_path"],
        )

    track_audit_run(
        audit_id=audit_id,
        repo_url=repo_url,
        final_state=final_state,
    )

    if final_state.get("repo_context"):
        cleanup_repo(final_state["repo_context"].local_path)

    logger.info(f"[task] audit {audit_id} complete — "
                f"risk score: {final_state.get('severity_counts')}")

async def _mark_failed(audit_id: str, error: str):
    async with AsyncSessionLocal() as db:
        await update_audit_status(
            db, uuid.UUID(audit_id), "failed", error=error
        )