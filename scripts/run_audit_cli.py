# scripts/run_audit_cli.py

"""
CLI runner for local development and demos.
Usage:
    python scripts/run_audit_cli.py https://github.com/user/repo
"""

import asyncio
import sys
import uuid
import json
from datetime import datetime
from auditmind.orchestrator.graph import audit_graph
from auditmind.orchestrator.state import AgentStatus
from auditmind.synthesis.scorer import compute_risk_score
from auditmind.logger import get_logger

logger = get_logger(__name__)


async def run_audit(repo_url: str):
    audit_id = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"  AuditMind CLI")
    print(f"  Repo:     {repo_url}")
    print(f"  Audit ID: {audit_id}")
    print(f"  Started:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

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

    print("⏳ Running agents...\n")
    final_state = await audit_graph.ainvoke(initial_state)

    if final_state.get("error"):
        print(f"❌ Audit failed: {final_state['error']}")
        sys.exit(1)

    # --- print results ---
    findings = final_state["deduplicated_findings"]
    counts = final_state["severity_counts"]
    risk_score = compute_risk_score(findings)

    print(f"\n{'='*60}")
    print(f"  AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"  Risk Score:  {risk_score}/100")
    print(f"  Critical:    {counts.get('critical', 0)}")
    print(f"  High:        {counts.get('high', 0)}")
    print(f"  Medium:      {counts.get('medium', 0)}")
    print(f"  Low:         {counts.get('low', 0)}")
    print(f"  Total:       {len(findings)}")
    print(f"{'='*60}\n")

    print("EXECUTIVE SUMMARY")
    print("-" * 60)
    print(final_state["executive_summary"])
    print()

    # print critical + high findings
    critical_high = [
        f for f in findings
        if f.severity.value in ("critical", "high")
    ]
    if critical_high:
        print(f"TOP FINDINGS ({len(critical_high)} critical/high)")
        print("-" * 60)
        for f in critical_high:
            print(f"[{f.severity.value.upper()}] [{f.agent}] {f.title}")
            print(f"  {f.description[:120]}")
            if f.recommendation:
                print(f"  → {f.recommendation[:100]}")
            if f.file_path:
                loc = f.file_path
                if f.line_number:
                    loc += f":{f.line_number}"
                print(f"  📄 {loc}")
            print()

    if final_state.get("report_path"):
        print(f"📄 PDF report saved to: {final_state['report_path']}")

    return final_state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_audit_cli.py <github_repo_url>")
        print("Example: python scripts/run_audit_cli.py https://github.com/Prakeerth1212/P4")
        sys.exit(1)

    repo_url = sys.argv[1]
    asyncio.run(run_audit(repo_url))