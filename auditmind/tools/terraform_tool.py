import os
import re
from pathlib import Path
from auditmind.logger import get_logger

logger = get_logger(__name__)

EXPENSIVE_INSTANCES = {
    "aws": [
        "x1e", "x1", "u-", "p4", "p3", "p2",          # memory / GPU optimised
        "c5n", "c6gn",                                   # network optimised
        "m5.24xlarge", "m6i.24xlarge",                  # massive general purpose
        "r5.24xlarge", "r6i.24xlarge",                  # massive memory
    ],
    "gcp": [
        "n2-highmem-96", "n2-highcpu-96",
        "m2-ultramem", "m1-ultramem",
        "a2-highgpu",
    ],
}

MISSING_TAGS = ["environment", "team", "cost_center", "project"]

def parse_terraform_files(tf_files: list[str]) -> dict:
    """
    Parses .tf files and extracts:
    - resource blocks with their types and config
    - missing required tags
    - expensive instance types
    - unused / orphaned resources
    """
    results = {
        "resources": [],
        "expensive_instances": [],
        "missing_tags": [],
        "open_ingress_rules": [],
        "raw_blocks": [],
    }

    for tf_path in tf_files:
        try:
            content = Path(tf_path).read_text(encoding="utf-8")
            _extract_resources(content, tf_path, results)
        except Exception as e:
            logger.error(f"Failed to parse {tf_path}: {e}")

    return results

def _extract_resources(content: str, file_path: str, results: dict):
    resource_pattern = re.compile(
        r'resource\s+"([^"]+)"\s+"([^"]+)"\s+\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
        re.DOTALL,
    )

    for match in resource_pattern.finditer(content):
        resource_type = match.group(1)
        resource_name = match.group(2)
        resource_body = match.group(3)

        resource = {
            "type": resource_type,
            "name": resource_name,
            "file": file_path,
            "body": resource_body,
        }
        results["resources"].append(resource)

        instance_match = re.search(r'instance_type\s*=\s*"([^"]+)"', resource_body)
        if instance_match:
            instance_type = instance_match.group(1)
            for prefix in EXPENSIVE_INSTANCES.get("aws", []):
                if instance_type.startswith(prefix):
                    results["expensive_instances"].append({
                        "resource": f"{resource_type}.{resource_name}",
                        "instance_type": instance_type,
                        "file": file_path,
                    })

        missing = []
        for tag in MISSING_TAGS:
            if tag not in resource_body:
                missing.append(tag)
        if missing:
            results["missing_tags"].append({
                "resource": f"{resource_type}.{resource_name}",
                "missing_tags": missing,
                "file": file_path,
            })

        if "aws_security_group" in resource_type:
            if "0.0.0.0/0" in resource_body or "::/0" in resource_body:
                results["open_ingress_rules"].append({
                    "resource": f"{resource_type}.{resource_name}",
                    "file": file_path,
                })