from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.synthesis.scorer import (
    compute_risk_score,
    compute_severity_counts,
    findings_by_agent,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from auditmind.config import settings
from auditmind.logger import get_logger

logger = get_logger(__name__)
SYSTEM_PROMPT = """
You are a senior engineering consultant writing an executive summary for a code audit report.
Your audience is a CTO or VP Engineering — technical but time-constrained.

Write a concise executive summary (200-300 words) covering:
1. Overall risk assessment (use the risk score provided)
2. The most critical findings and their business impact
3. Top 3 immediate actions the team should take
4. One positive observation if warranted

Tone: professional, direct, no fluff. Use plain paragraphs — no bullet points or markdown.
This text goes directly into a PDF report.
"""
def generate_executive_summary(
    findings: list[Finding],
    repo_context: RepoContext,
) -> str:
    """
    Uses a higher-capability model (Sonnet) for the executive summary
    since reasoning quality matters more here than speed.
    """
    if not findings:
        return (
            f"The automated audit of {repo_context.repo_name} found no issues "
            "across security, cost, performance, and compliance checks. "
            "The codebase appears well-structured and follows best practices."
        )

    risk_score = compute_risk_score(findings)
    counts = compute_severity_counts(findings)
    by_agent = findings_by_agent(findings)

    prompt = _build_prompt(findings, repo_context, risk_score, counts, by_agent)

    try:
        # use Sonnet for the summary — reasoning quality matters here
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model_pro,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
            max_output_tokens=1024,
        )
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        return response.content

    except Exception as e:
        logger.error(f"Executive summary generation failed: {e}")
        return _fallback_summary(repo_context, risk_score, counts)

def _build_prompt(
    findings: list[Finding],
    repo_context: RepoContext,
    risk_score: int,
    counts: dict,
    by_agent: dict,
) -> str:
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    high = [f for f in findings if f.severity == Severity.HIGH]

    lines = [
        f"Repository: {repo_context.repo_name}",
        f"Overall risk score: {risk_score}/100",
        f"Total findings: {len(findings)}",
        f"  Critical: {counts.get('critical', 0)}",
        f"  High:     {counts.get('high', 0)}",
        f"  Medium:   {counts.get('medium', 0)}",
        f"  Low:      {counts.get('low', 0)}",
        "",
        "=== CRITICAL FINDINGS ===",
    ]

    for f in critical[:5]:
        lines.append(f"  [{f.agent}] {f.title}: {f.description[:150]}")

    lines.append("\n=== HIGH SEVERITY FINDINGS ===")
    for f in high[:5]:
        lines.append(f"  [{f.agent}] {f.title}: {f.description[:150]}")

    lines.append("\n=== FINDINGS BY AGENT ===")
    for agent, agent_findings in by_agent.items():
        lines.append(f"  {agent}: {len(agent_findings)} findings")

    return "\n".join(lines)

def _fallback_summary(
    repo_context: RepoContext,
    risk_score: int,
    counts: dict,
) -> str:
    """Plain text fallback if LLM call fails."""
    level = (
        "critical" if risk_score >= 80 else
        "high" if risk_score >= 50 else
        "moderate" if risk_score >= 25 else
        "low"
    )
    return (
        f"The automated audit of {repo_context.repo_name} returned a risk score "
        f"of {risk_score}/100, indicating {level} overall risk. "
        f"The scan identified {counts.get('critical', 0)} critical, "
        f"{counts.get('high', 0)} high, {counts.get('medium', 0)} medium, "
        f"and {counts.get('low', 0)} low severity findings across security, "
        f"cost, performance, and compliance domains. "
        f"Immediate attention is recommended for all critical and high severity items."
    )