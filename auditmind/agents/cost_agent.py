import json
from auditmind.agents.base_agent import BaseAgent
from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.tools.terraform_tool import parse_terraform_files

SYSTEM_PROMPT = """
You are a cloud cost optimisation engineer reviewing infrastructure configurations.
You will receive parsed Terraform resource data including expensive instances,
missing cost allocation tags, open security groups, and resource counts.

Your job:
1. Identify genuine cost inefficiencies — not theoretical ones
2. Estimate rough monthly cost impact where possible
3. Write specific, actionable recommendations

Respond ONLY with a valid JSON array. No preamble, no markdown, no explanation.
Each object must have exactly these fields:
{
  "title": "short issue name",
  "description": "what the cost issue is and its estimated impact",
  "severity": "critical|high|medium|low|info",
  "file_path": "relative file path or null",
  "line_number": null,
  "recommendation": "specific action to reduce cost"
}
"""
class CostAgent(BaseAgent):
    agent_name = "cost"

    def _analyse(self, repo_context: RepoContext) -> list[Finding]:
        # --- step 1: bail early if no terraform files ---
        if not repo_context.terraform_files:
            return [self._make_finding(
                title="No Terraform files found",
                description="No infrastructure-as-code files were detected. "
                            "Cost analysis requires Terraform (.tf) files.",
                severity=Severity.INFO,
            )]

        # --- step 2: parse terraform files ---
        tf_data = parse_terraform_files(repo_context.terraform_files)

        if not tf_data["resources"]:
            return [self._make_finding(
                title="No Terraform resources parsed",
                description="Terraform files were found but no resource blocks could be extracted.",
                severity=Severity.INFO,
            )]

        summary = self._build_summary(tf_data)
        raw_response = self._ask_llm(SYSTEM_PROMPT, summary)
        return self._parse_llm_response(raw_response, tf_data)

    def _build_summary(self, tf_data: dict) -> str:
        lines = [
            f"Total resources: {len(tf_data['resources'])}",
            "",
            "=== EXPENSIVE INSTANCE TYPES ===",
        ]

        if tf_data["expensive_instances"]:
            for item in tf_data["expensive_instances"]:
                lines.append(
                    f"  {item['resource']} uses {item['instance_type']} "
                    f"(file: {item['file']})"
                )
        else:
            lines.append("  None detected")

        lines.append("\n=== MISSING COST ALLOCATION TAGS ===")
        if tf_data["missing_tags"]:
            for item in tf_data["missing_tags"][:20]:
                lines.append(
                    f"  {item['resource']} missing: {', '.join(item['missing_tags'])} "
                    f"(file: {item['file']})"
                )
        else:
            lines.append("  All resources properly tagged")

        lines.append("\n=== OPEN SECURITY GROUP INGRESS (0.0.0.0/0) ===")
        if tf_data["open_ingress_rules"]:
            for item in tf_data["open_ingress_rules"]:
                lines.append(f"  {item['resource']} (file: {item['file']})")
        else:
            lines.append("  None detected")

        lines.append(f"\n=== RESOURCE TYPE BREAKDOWN ===")
        type_counts: dict[str, int] = {}
        for r in tf_data["resources"]:
            type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
        for rtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {rtype}: {count}")

        return "\n".join(lines)

    def _parse_llm_response(
        self,
        raw_response: str,
        tf_data: dict,
    ) -> list[Finding]:
        try:
            cleaned = raw_response.strip().strip("```json").strip("```").strip()
            parsed = json.loads(cleaned)

            return [
                self._make_finding(
                    title=item.get("title", "Cost issue"),
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
            return self._fallback_parse(tf_data)

    def _fallback_parse(self, tf_data: dict) -> list[Finding]:
        findings = []

        for item in tf_data["expensive_instances"]:
            findings.append(self._make_finding(
                title=f"Expensive instance: {item['instance_type']}",
                description=f"{item['resource']} uses a high-cost instance type.",
                severity=Severity.HIGH,
                file_path=item["file"],
                recommendation="Evaluate if a smaller instance type meets your workload needs.",
                raw_output=item,
            ))

        for item in tf_data["open_ingress_rules"]:
            findings.append(self._make_finding(
                title="Open security group ingress",
                description=f"{item['resource']} allows inbound traffic from 0.0.0.0/0.",
                severity=Severity.HIGH,
                file_path=item["file"],
                recommendation="Restrict ingress to known IP ranges or VPC CIDR blocks.",
                raw_output=item,
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