import re
import json
from pathlib import Path
from auditmind.agents.base_agent import BaseAgent
from auditmind.orchestrator.state import Finding, RepoContext, Severity

SYSTEM_PROMPT = """
You are a compliance engineer reviewing a codebase against SOC 2 Type II and GDPR requirements.
You will receive a structured compliance check report covering logging, authentication,
data handling, rate limiting, and security headers.

Your job:
1. Assess each failed check in real-world context
2. Identify which compliance framework it violates (SOC 2 / GDPR / both)
3. Write specific, actionable remediation steps

Respond ONLY with a valid JSON array. No preamble, no markdown, no explanation.
Each object must have exactly these fields:
{
  "title": "short compliance issue name",
  "description": "what is missing and which framework requires it",
  "severity": "critical|high|medium|low|info",
  "file_path": "relative file path or null",
  "line_number": null,
  "recommendation": "specific code or config change needed"
}
"""
class ComplianceChecker:

    def __init__(self, repo_context: RepoContext):
        self.ctx = repo_context
        self.all_source = self._load_all_source()
        self.py_source = self._load_python_source()
        self.results: list[dict] = []

    def _load_all_source(self) -> str:
        """Concatenate all text files for pattern matching."""
        combined = []
        all_files = (
            self.ctx.python_files
            + self.ctx.yaml_files
            + self.ctx.docker_files
        )
        for f in all_files:
            try:
                combined.append(Path(f).read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
        return "\n".join(combined)

    def _load_python_source(self) -> str:
        combined = []
        for f in self.ctx.python_files:
            try:
                combined.append(Path(f).read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
        return "\n".join(combined)

    def run_all_checks(self) -> list[dict]:
        checks = [
            self._check_logging_present,
            self._check_structured_logging,
            self._check_no_plaintext_passwords,
            self._check_no_hardcoded_secrets,
            self._check_rate_limiting,
            self._check_authentication_present,
            self._check_https_enforced,
            self._check_security_headers,
            self._check_pii_logging,
            self._check_error_handling,
            self._check_input_validation,
            self._check_dependency_pinning,
            self._check_cors_configured,
            self._check_data_retention_policy,
        ]
        for check in checks:
            try:
                result = check()
                self.results.append(result)
            except Exception:
                pass
        return self.results

    # --- individual checks ---

    def _check_logging_present(self) -> dict:
        has_logging = any(
            kw in self.py_source
            for kw in ["import logging", "from logging", "logger =", "getLogger"]
        )
        return {
            "check": "logging_present",
            "passed": has_logging,
            "frameworks": ["SOC 2 CC7.2"],
            "detail": "Logging module detected" if has_logging
                      else "No logging detected — audit trails required by SOC 2",
        }

    def _check_structured_logging(self) -> dict:
        has_structured = any(
            kw in self.py_source
            for kw in ["structlog", "python-json-logger", "JSONFormatter", "json_logger"]
        )
        return {
            "check": "structured_logging",
            "passed": has_structured,
            "frameworks": ["SOC 2 CC7.2", "GDPR Art.30"],
            "detail": "Structured logging detected" if has_structured
                      else "No structured logging — JSON logs required for audit trail compliance",
        }

    def _check_no_plaintext_passwords(self) -> dict:
        patterns = [
            r'password\s*=\s*["\'][^"\']{4,}["\']',
            r'passwd\s*=\s*["\'][^"\']{4,}["\']',
            r'secret\s*=\s*["\'][^"\']{4,}["\']',
        ]
        found = any(
            re.search(p, self.py_source, re.IGNORECASE)
            for p in patterns
        )
        return {
            "check": "no_plaintext_passwords",
            "passed": not found,
            "frameworks": ["SOC 2 CC6.1", "GDPR Art.32"],
            "detail": "No plaintext passwords found" if not found
                      else "Possible plaintext credentials found in source code",
        }

    def _check_no_hardcoded_secrets(self) -> dict:
        patterns = [
            r'api_key\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']',
            r'token\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']',
            r'sk-[A-Za-z0-9]{32,}',
            r'ghp_[A-Za-z0-9]{36}',
            r'AKIA[A-Z0-9]{16}',         # AWS access key
        ]
        found_patterns = []
        for p in patterns:
            if re.search(p, self.all_source, re.IGNORECASE):
                found_patterns.append(p)

        return {
            "check": "no_hardcoded_secrets",
            "passed": len(found_patterns) == 0,
            "frameworks": ["SOC 2 CC6.1", "GDPR Art.32"],
            "detail": "No hardcoded secrets detected" if not found_patterns
                      else f"Possible hardcoded secrets detected ({len(found_patterns)} patterns matched)",
        }

    def _check_rate_limiting(self) -> dict:
        has_rate_limit = any(
            kw in self.all_source
            for kw in [
                "slowapi", "ratelimit", "rate_limit", "RateLimiter",
                "throttle", "fastapi-limiter", "redis_rate",
            ]
        )
        return {
            "check": "rate_limiting",
            "passed": has_rate_limit,
            "frameworks": ["SOC 2 CC6.6"],
            "detail": "Rate limiting detected" if has_rate_limit
                      else "No rate limiting detected — APIs are vulnerable to abuse and brute force",
        }

    def _check_authentication_present(self) -> dict:
        has_auth = any(
            kw in self.all_source
            for kw in [
                "jwt", "oauth", "bearer", "api_key", "firebase",
                "Depends(get_current_user", "HTTPBearer", "APIKeyHeader",
            ]
        )
        return {
            "check": "authentication_present",
            "passed": has_auth,
            "frameworks": ["SOC 2 CC6.1"],
            "detail": "Authentication mechanism detected" if has_auth
                      else "No authentication detected on API endpoints",
        }

    def _check_https_enforced(self) -> dict:
        has_https = any(
            kw in self.all_source
            for kw in [
                "https://", "ssl=True", "HTTPS", "tls", "certfile",
                "HTTPSRedirectMiddleware",
            ]
        )
        return {
            "check": "https_enforced",
            "passed": has_https,
            "frameworks": ["SOC 2 CC6.7", "GDPR Art.32"],
            "detail": "HTTPS / TLS references found" if has_https
                      else "No HTTPS enforcement detected — data in transit not protected",
        }

    def _check_security_headers(self) -> dict:
        headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Strict-Transport-Security",
            "Content-Security-Policy",
        ]
        found = [h for h in headers if h in self.all_source]
        return {
            "check": "security_headers",
            "passed": len(found) >= 2,
            "frameworks": ["SOC 2 CC6.7"],
            "detail": f"Security headers found: {found}" if found
                      else "No security headers configured (HSTS, CSP, X-Frame-Options, etc.)",
        }

    def _check_pii_logging(self) -> dict:
        pii_patterns = [
            r'log.*email', r'log.*password', r'log.*phone',
            r'log.*ssn', r'log.*credit_card', r'log.*dob',
        ]
        found = any(
            re.search(p, self.py_source, re.IGNORECASE)
            for p in pii_patterns
        )
        return {
            "check": "no_pii_in_logs",
            "passed": not found,
            "frameworks": ["GDPR Art.5", "GDPR Art.25"],
            "detail": "No PII logging patterns detected" if not found
                      else "Possible PII (email/password/phone) being logged — GDPR violation risk",
        }

    def _check_error_handling(self) -> dict:
        has_handler = any(
            kw in self.all_source
            for kw in [
                "exception_handler", "HTTPException", "@app.exception_handler",
                "add_exception_handler", "status_code=500",
            ]
        )
        return {
            "check": "error_handling",
            "passed": has_handler,
            "frameworks": ["SOC 2 CC7.2"],
            "detail": "Error handling detected" if has_handler
                      else "No global error handler — stack traces may leak to clients",
        }

    def _check_input_validation(self) -> dict:
        has_validation = any(
            kw in self.all_source
            for kw in ["pydantic", "BaseModel", "validator", "Field(", "Schema("]
        )
        return {
            "check": "input_validation",
            "passed": has_validation,
            "frameworks": ["SOC 2 CC6.1"],
            "detail": "Input validation (Pydantic) detected" if has_validation
                      else "No input validation library detected — injection risk",
        }

    def _check_dependency_pinning(self) -> dict:
        has_pinned = any(
            kw in self.all_source
            for kw in ["==", "requirements.txt", "pyproject.toml", "poetry.lock", "Pipfile.lock"]
        )
        return {
            "check": "dependency_pinning",
            "passed": has_pinned,
            "frameworks": ["SOC 2 CC7.1"],
            "detail": "Pinned dependencies detected" if has_pinned
                      else "Dependencies not pinned — supply chain risk",
        }

    def _check_cors_configured(self) -> dict:
        has_cors = any(
            kw in self.all_source
            for kw in ["CORSMiddleware", "allow_origins", "CORS", "cors"]
        )
        return {
            "check": "cors_configured",
            "passed": has_cors,
            "frameworks": ["SOC 2 CC6.6"],
            "detail": "CORS configuration detected" if has_cors
                      else "No CORS configuration found — all origins may be allowed by default",
        }

    def _check_data_retention_policy(self) -> dict:
        has_retention = any(
            kw in self.all_source
            for kw in [
                "retention", "ttl", "expire", "delete_after",
                "purge", "data_retention", "TTL",
            ]
        )
        return {
            "check": "data_retention_policy",
            "passed": has_retention,
            "frameworks": ["GDPR Art.5(1)(e)", "GDPR Art.17"],
            "detail": "Data retention / expiry logic detected" if has_retention
                      else "No data retention policy found — GDPR right to erasure requires this",
        }

class ComplianceAgent(BaseAgent):
    agent_name = "compliance"
    def _analyse(self, repo_context: RepoContext) -> list[Finding]:
        checker = ComplianceChecker(repo_context)
        results = checker.run_all_checks()
        failed = [r for r in results if not r["passed"]]
        passed = [r for r in results if r["passed"]]
        if not failed:
            return [self._make_finding(
                title="All compliance checks passed",
                description=f"All {len(passed)} compliance checks passed.",
                severity=Severity.INFO,
            )]
        summary = self._build_summary(failed, passed)
        raw_response = self._ask_llm(SYSTEM_PROMPT, summary)
        return self._parse_llm_response(raw_response, failed)

    def _build_summary(self, failed: list[dict], passed: list[dict]) -> str:
        lines = [
            f"Compliance scan complete: {len(failed)} failed, {len(passed)} passed",
            "",
            "=== FAILED CHECKS ===",
        ]
        for item in failed:
            lines.append(
                f"  [{', '.join(item['frameworks'])}] "
                f"{item['check']}: {item['detail']}"
            )

        lines.append("\n=== PASSED CHECKS ===")
        for item in passed:
            lines.append(f"  {item['check']}: {item['detail']}")

        return "\n".join(lines)

    def _parse_llm_response(
        self,
        raw_response: str,
        failed_checks: list[dict],
    ) -> list[Finding]:
        try:
            cleaned = raw_response.strip().strip("```json").strip("```").strip()
            parsed = json.loads(cleaned)

            return [
                self._make_finding(
                    title=item.get("title", "Compliance issue"),
                    description=item.get("description", ""),
                    severity=self._map_severity(item.get("severity", "medium")),
                    file_path=item.get("file_path"),
                    line_number=None,
                    recommendation=item.get("recommendation"),
                    raw_output=item,
                )
                for item in parsed
                if isinstance(item, dict)
            ]

        except (json.JSONDecodeError, TypeError):
            return self._fallback_parse(failed_checks)

    def _fallback_parse(self, failed_checks: list[dict]) -> list[Finding]:
        severity_map = {
            "no_hardcoded_secrets": Severity.CRITICAL,
            "no_plaintext_passwords": Severity.CRITICAL,
            "authentication_present": Severity.HIGH,
            "https_enforced": Severity.HIGH,
            "rate_limiting": Severity.HIGH,
            "no_pii_in_logs": Severity.HIGH,
            "logging_present": Severity.MEDIUM,
            "structured_logging": Severity.MEDIUM,
            "security_headers": Severity.MEDIUM,
            "error_handling": Severity.MEDIUM,
            "cors_configured": Severity.MEDIUM,
            "input_validation": Severity.MEDIUM,
            "dependency_pinning": Severity.LOW,
            "data_retention_policy": Severity.LOW,
        }
        findings = []
        for check in failed_checks:
            findings.append(self._make_finding(
                title=check["check"].replace("_", " ").title(),
                description=check["detail"],
                severity=severity_map.get(check["check"], Severity.MEDIUM),
                raw_output=check,
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