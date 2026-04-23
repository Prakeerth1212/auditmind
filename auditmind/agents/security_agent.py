import json
from auditmind.agents.base_agent import BaseAgent
from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.tools.bandit_tool import run_bandit
from auditmind.tools.semgrep_tool import run_semgrep

SYSTEM_PROMPT = """
You are a senior application security engineer performing a code audit.
You will receive raw output from Bandit and Semgrep security scanners.

Your job:
1. Review each issue found by the tools
2. Assess its real-world severity — ignore false positives
3. Write a clear, actionable recommendation for each genuine issue

Respond ONLY with a valid JSON array. No preamble, no markdown, no explanation.
Each object must have exactly these fields:
{
  "title": "short issue name",
  "description": "what the vulnerability is and why it matters",
  "severity": "critical|high|medium|low|info",
  "file_path": "relative file path or null",
  "line_number": integer or null,
  "recommendation": "specific fix the developer should apply"
}
"""
class SecurityAgent(BaseAgent):
    agent_name = "security"

    def _analyse(self, repo_context: RepoContext) -> list[Finding]:
        findings = []

        # --- step 1: run both tools ---
        bandit_output = run_bandit(repo_context.local_path)
        semgrep_output = run_semgrep(repo_context.local_path)

        # --- step 2: bail early if both tools found nothing ---
        bandit_issues = bandit_output.get("results", [])
        semgrep_issues = semgrep_output.get("results", [])

        if not bandit_issues and not semgrep_issues:
            findings.append(self._make_finding(
                title="No security issues detected",
                description="Bandit and semgrep found no issues in the scanned files.",
                severity=Severity.INFO,
            ))
            return findings
        tool_summary = self._build_tool_summary(bandit_issues, semgrep_issues)
        raw_response = self._ask_llm(SYSTEM_PROMPT, tool_summary)
        findings = self._parse_llm_response(raw_response, bandit_issues, semgrep_issues)
        return findings

    def _build_tool_summary(
        self,
        bandit_issues: list[dict],
        semgrep_issues: list[dict],
    ) -> str:
        """
        Condenses raw tool output into a prompt-friendly string.
        Caps at 30 issues each to stay within context limits.
        """
        lines = ["=== BANDIT FINDINGS ==="]
        for issue in bandit_issues[:30]:
            lines.append(
                f"[{issue.get('issue_severity', 'UNKNOWN')}] "
                f"{issue.get('issue_text', '')} | "
                f"file: {issue.get('filename', '')} "
                f"line: {issue.get('line_number', '?')} | "
                f"test: {issue.get('test_id', '')} — {issue.get('test_name', '')}"
            )

        lines.append("\n=== SEMGREP FINDINGS ===")
        for issue in semgrep_issues[:30]:
            meta = issue.get("extra", {})
            lines.append(
                f"[{meta.get('severity', 'UNKNOWN')}] "
                f"{meta.get('message', '')} | "
                f"file: {issue.get('path', '')} "
                f"line: {issue.get('start', {}).get('line', '?')} | "
                f"rule: {issue.get('check_id', '')}"
            )

        return "\n".join(lines)

    def _parse_llm_response(
        self,
        raw_response: str,
        bandit_issues: list[dict],
        semgrep_issues: list[dict],
    ) -> list[Finding]:
        """
        Parses the LLM JSON response into Finding objects.
        Falls back to raw tool output if LLM response is malformed.
        """
        try:
            # strip any accidental markdown fences
            cleaned = raw_response.strip().strip("```json").strip("```").strip()
            parsed = json.loads(cleaned)

            return [
                self._make_finding(
                    title=item.get("title", "Security issue"),
                    description=item.get("description", ""),
                    severity=self._map_severity(item.get("severity", "medium")),
                    file_path=item.get("file_path"),
                    line_number=item.get("line_number"),
                    recommendation=item.get("recommendation"),
                    raw_output=item,
                )
                for item in parsed
                if isinstance(item, dict)
            ]

        except (json.JSONDecodeError, TypeError):
            # fallback: convert raw bandit output directly
            return self._fallback_parse(bandit_issues, semgrep_issues)

    def _fallback_parse(
        self,
        bandit_issues: list[dict],
        semgrep_issues: list[dict],
    ) -> list[Finding]:
        """Used when LLM returns malformed JSON."""
        findings = []
        for issue in bandit_issues[:20]:
            findings.append(self._make_finding(
                title=issue.get("test_name", "Security issue"),
                description=issue.get("issue_text", ""),
                severity=self._map_severity(issue.get("issue_severity", "medium")),
                file_path=issue.get("filename"),
                line_number=issue.get("line_number"),
                raw_output=issue,
            ))
        return findings

    def _map_severity(self, raw: str) -> Severity:
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "med": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
            "informational": Severity.INFO,
        }
        return mapping.get(raw.lower(), Severity.MEDIUM)