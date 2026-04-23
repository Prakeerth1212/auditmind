import subprocess
import json
from auditmind.logger import get_logger
logger = get_logger(__name__)

def run_bandit(path: str) -> dict:
    try:
        result = subprocess.run(
            [
                "bandit",
                "-r", path,           # recursive
                "-f", "json",         # JSON output
                "-ll",                # only medium+ severity
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            return json.loads(result.stdout)
        return {}
    except subprocess.TimeoutExpired:
        logger.error("Bandit timed out")
        return {}
    except Exception as e:
        logger.error(f"Bandit failed: {e}")
        return {}