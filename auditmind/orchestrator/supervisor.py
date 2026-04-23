import uuid
import tempfile
from auditmind.orchestrator.state import AuditState, AgentStatus, RepoContext
from auditmind.ingestion.github_client import clone_repo
from auditmind.ingestion.file_parser import list_files_by_type
from auditmind.agents.security_agent import SecurityAgent
from auditmind.agents.cost_agent import CostAgent
from auditmind.agents.performance_agent import PerformanceAgent
from auditmind.agents.compliance_agent import ComplianceAgent
from auditmind.synthesis.deduplicator import deduplicate
from auditmind.synthesis.scorer import compute_severity_counts
from auditmind.synthesis.summariser import generate_executive_summary
from auditmind.report.pdf_generator import generate_pdf
from auditmind.logger import get_logger

logger = get_logger(__name__)

def ingest_repo(state: AuditState) -> dict:
    logger.info(f"Ingesting repo: {state['repo_url']}")
    try:
        local_path = tempfile.mkdtemp(prefix="auditmind_")
        clone_repo(state["repo_url"], local_path)
        files = list_files_by_type(local_path)

        repo_context = RepoContext(
            repo_url=state["repo_url"],
            repo_name=state["repo_url"].split("/")[-1],
            local_path=local_path,
            **files,
        )
        return {
            "repo_context": repo_context,
            "security_status": AgentStatus.PENDING,
            "cost_status": AgentStatus.PENDING,
            "performance_status": AgentStatus.PENDING,
            "compliance_status": AgentStatus.PENDING,
            "findings": [],
            "error": None,
        }
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return {"error": str(e), "repo_context": None}

def should_continue(state: AuditState) -> str:
    return "error" if state.get("error") else "continue"

def run_security_agent(state: AuditState) -> dict:
    logger.info("Running security agent")
    agent = SecurityAgent()
    findings = agent.run(state["repo_context"])
    logger.info(f"Security agent returned {len(findings)} findings")
    for f in findings:
        logger.info(f"  [{f.severity.value}] {f.title}")
    return {
        "findings": findings,
        "security_status": AgentStatus.DONE,
    }

def run_cost_agent(state: AuditState) -> dict:
    logger.info("Running cost agent")
    agent = CostAgent()
    findings = agent.run(state["repo_context"])
    logger.info(f"Cost agent returned {len(findings)} findings")
    return {
        "findings": findings,
        "cost_status": AgentStatus.DONE,
    }

def run_performance_agent(state: AuditState) -> dict:
    logger.info("Running performance agent")
    agent = PerformanceAgent()
    findings = agent.run(state["repo_context"])
    logger.info(f"Performance agent returned {len(findings)} findings")
    for f in findings:
        logger.info(f"  [{f.severity.value}] {f.title}")
    return {
        "findings": findings,
        "performance_status": AgentStatus.DONE,
    }

def run_compliance_agent(state: AuditState) -> dict:
    logger.info("Running compliance agent")
    agent = ComplianceAgent()
    findings = agent.run(state["repo_context"])
    logger.info(f"Compliance agent returned {len(findings)} findings")
    for f in findings:
        logger.info(f"  [{f.severity.value}] {f.title}")
    return {
        "findings": findings,
        "compliance_status": AgentStatus.DONE,
    }

def synthesise_findings(state: AuditState) -> dict:
    logger.info(f"Synthesising {len(state['findings'])} findings")
    deduped = deduplicate(state["findings"])
    counts = compute_severity_counts(deduped)
    summary = generate_executive_summary(deduped, state["repo_context"])
    return {
        "deduplicated_findings": deduped,
        "severity_counts": counts,
        "executive_summary": summary,
    }

def generate_report(state: AuditState) -> dict:
    logger.info("Generating PDF report")
    path = generate_pdf(
        audit_id=state["audit_id"],
        repo_context=state["repo_context"],
        findings=state["deduplicated_findings"],
        severity_counts=state["severity_counts"],
        executive_summary=state["executive_summary"],
    )
    return {"report_path": path}