import mlflow
from auditmind.config import settings
from auditmind.synthesis.scorer import compute_risk_score
from auditmind.logger import get_logger

logger = get_logger(__name__)

mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
mlflow.set_experiment("auditmind-audits")


def track_audit_run(
    audit_id: str,
    repo_url: str,
    final_state: dict,
):
    """
    Logs each audit run as an MLflow run with:
    - params: repo name, agent config
    - metrics: finding counts, risk score, agent latencies
    - artifacts: nothing yet (PDF could be logged here later)
    """
    try:
        counts = final_state.get("severity_counts", {})
        findings = final_state.get("deduplicated_findings", [])
        risk_score = compute_risk_score(findings)

        with mlflow.start_run(run_name=f"audit-{audit_id[:8]}"):
            # params — what was audited
            mlflow.log_params({
                "audit_id": audit_id,
                "repo_url": repo_url,
                "repo_name": repo_url.split("/")[-1],
            })

            # metrics — findings breakdown
            mlflow.log_metrics({
                "risk_score": risk_score,
                "total_findings": len(findings),
                "critical_count": counts.get("critical", 0),
                "high_count": counts.get("high", 0),
                "medium_count": counts.get("medium", 0),
                "low_count": counts.get("low", 0),
                "info_count": counts.get("info", 0),
            })

            # per-agent finding counts
            agent_counts: dict[str, int] = {}
            for f in findings:
                agent_counts[f.agent] = agent_counts.get(f.agent, 0) + 1

            for agent, count in agent_counts.items():
                mlflow.log_metric(f"{agent}_findings", count)

        logger.info(f"MLflow tracked: audit {audit_id[:8]} | risk={risk_score}")

    except Exception as e:
        # never let MLflow tracking break the main flow
        logger.warning(f"MLflow tracking failed (non-fatal): {e}")