from collections import defaultdict
from auditmind.orchestrator.state import Finding, Severity
from auditmind.logger import get_logger
logger = get_logger(__name__)

SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 20,
    Severity.MEDIUM: 8,
    Severity.LOW: 3,
    Severity.INFO: 0,
}

def compute_severity_counts(findings: list[Finding]) -> dict[str, int]:
    """
    Returns finding counts per severity level.
    Used for the report summary and dashboard charts.
    """
    counts = {s.value: 0 for s in Severity}
    for f in findings:
        counts[f.severity.value] += 1
    return counts

def compute_risk_score(findings: list[Finding]) -> int:
    """
    Computes an overall risk score 0-100 for the repo.
    Higher = more risk.
    Capped at 100.
    """
    raw = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings)
    return min(raw, 100)

def rank_findings(findings: list[Finding]) -> list[Finding]:
    """
    Sorts findings by severity descending, then by agent name for consistency.
    """
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    return sorted(
        findings,
        key=lambda f: (severity_order.get(f.severity, 99), f.agent),
    )

def findings_by_agent(findings: list[Finding]) -> dict[str, list[Finding]]:
    """
    Groups findings by agent name.
    Used for per-agent sections in the PDF report.
    """
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        groups[f.agent].append(f)
    return dict(groups)