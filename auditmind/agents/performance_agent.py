import json
from auditmind.agents.base_agent import BaseAgent
from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.tools.ast_tool import analyse_python_files, ASTIssue

SYSTEM_PROMPT = """
You are a senior Python performance engineer reviewing code for runtime inefficiencies.
You will receive a list of static analysis findings from an AST walker.

Your job:
1. Assess each finding in context — not every N+1 or nested loop is critical
2. Estimate the real-world performance impact (high traffic vs internal scripts differ)
3. Write specific, copy-pasteable recommendations

Respond ONLY with a valid JSON array. No preamble, no markdown, no explanation.
Each object must have exactly these fields:
{
  "title": "short issue name",
  "description": "what the performance issue is and its likely impact",
  "severity": "critical|high|medium|low|info",
  "file_path": "relative file path or null",
  "line_number": integer or null,
  "recommendation": "specific code-level fix"
}
"""

SEVERITY_DEFAULTS = {
    "n_plus_one_query": Severity.HIGH,
    "string_concat_in_loop": Severity.MEDIUM,
    "bare_except": Severity.MEDIUM,
    "mutable_default_arg": Severity.LOW,
    "nested_loop": Severity.MEDIUM,
    "global_in_loop": Severity.LOW,
}

class PerformanceAgent(BaseAgent):
    agent_name = "performance"

    def _analyse(self, repo_context: RepoContext) -> list[Finding]:
        # --- step 1: bail if no Python files ---
        if not repo_context.python_files:
            return [self._make_finding(
                title="No Python files found",
                description="Performance analysis requires Python source files.",
                severity=Severity.INFO,
            )]

        ast_issues = analyse_python_files(repo_context.python_files)

        if not ast_issues:
            return [self._make_finding(
                title="No performance issues detected",
                description="AST analysis found no common performance anti-patterns.",
                severity=Severity.INFO,
            )]

        summary = self._build_summary(ast_issues)
        raw_response = self._ask_llm(SYSTEM_PROMPT, summary)
        return self._parse_llm_response(raw_response, ast_issues)

    def _build_summary(self, issues: list[ASTIssue]) -> str:
        lines = [f"Total AST issues found: {len(issues)}", ""]

        # group by issue type for clarity
        by_type: dict[str, list[ASTIssue]] = {}
        for issue in issues:
            by_type.setdefault(issue.issue_type, []).append(issue)

        for issue_type, items in by_type.items():
            lines.append(f"=== {issue_type.upper()} ({len(items)} occurrences) ===")
            for item in items[:10]:  # cap per type
                lines.append(
                    f"  file: {item.file_path} | line: {item.line_number} | "
                    f"{item.description[:120]} | snippet: `{item.code_snippet}`"
                )

        return "\n".join(lines)

    def _parse_llm_response(
        self,
        raw_response: str,
        ast_issues: list[ASTIssue],
    ) -> list[Finding]:
        try:
            cleaned = raw_response.strip().strip("```json").strip("```").strip()
            parsed = json.loads(cleaned)

            return [
                self._make_finding(
                    title=item.get("title", "Performance issue"),
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
            return self._fallback_parse(ast_issues)

    def _fallback_parse(self, ast_issues: list[ASTIssue]) -> list[Finding]:
        findings = []
        for issue in ast_issues[:20]:
            findings.append(self._make_finding(
                title=issue.issue_type.replace("_", " ").title(),
                description=issue.description,
                severity=SEVERITY_DEFAULTS.get(issue.issue_type, Severity.MEDIUM),
                file_path=issue.file_path,
                line_number=issue.line_number,
                raw_output={"code_snippet": issue.code_snippet},
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
        }
        return mapping.get(raw.lower(), Severity.MEDIUM)