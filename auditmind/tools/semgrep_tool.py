import subprocess
import json
from auditmind.logger import get_logger

logger = get_logger(__name__)
RULESETS = [
    "p/owasp-top-ten",
    "p/secrets",
    "p/python",
]

def run_semgrep(path: str) -> dict:
    try:
        result = subprocess.run(
            [
                "semgrep",
                "--config", "p/owasp-top-ten",
                "--config", "p/secrets",
                "--config", "p/python",
                "--json",
                "--quiet",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.stdout:
            return json.loads(result.stdout)
        return {}
    except subprocess.TimeoutExpired:
        logger.error("Semgrep timed out")
        return {}
    except Exception as e:
        logger.error(f"Semgrep failed: {e}")
        return {}