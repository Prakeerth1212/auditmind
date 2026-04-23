import os
import subprocess
import shutil
from pathlib import Path
from auditmind.config import settings
from auditmind.logger import get_logger

logger = get_logger(__name__)
def clone_repo(repo_url: str, target_path: str) -> str:
    """
    Clones a GitHub repo into target_path.
    Supports both public repos and private repos via GITHUB_TOKEN.
    Returns the local path on success, raises on failure.
    """
    if settings.github_token and "github.com" in repo_url:
        # transform https://github.com/user/repo
        #        → https://token@github.com/user/repo
        authenticated_url = repo_url.replace(
            "https://",
            f"https://{settings.github_token}@",
        )
    else:
        authenticated_url = repo_url

    logger.info(f"Cloning {repo_url} → {target_path}")

    try:
        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",        # shallow clone — we only need current state
                "--single-branch",
                authenticated_url,
                target_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"git clone failed: {result.stderr.strip()}"
            )

        logger.info(f"Clone successful: {target_path}")
        return target_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("git clone timed out after 120s — repo may be too large")
    except FileNotFoundError:
        raise RuntimeError("git not found — ensure git is installed in the container")


def cleanup_repo(local_path: str) -> None:
    """
    Removes the cloned repo from disk after audit completes.
    Always call this in a finally block.
    """
    try:
        if os.path.exists(local_path):
            shutil.rmtree(local_path)
            logger.info(f"Cleaned up {local_path}")
    except Exception as e:
        logger.warning(f"Cleanup failed for {local_path}: {e}")

def get_repo_name(repo_url: str) -> str:
    """Extracts repo name from URL. github.com/user/my-repo → my-repo"""
    return repo_url.rstrip("/").split("/")[-1].replace(".git", "")

def get_recent_commits(local_path: str, n: int = 10) -> list[dict]:
    """
    Returns the last n commits as a list of dicts.
    Used for the compliance agent to check commit hygiene.
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", local_path,
                "log", f"-{n}",
                "--pretty=format:%H|%an|%ae|%s|%ci",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "message": parts[3],
                    "date": parts[4],
                })
        return commits
    except Exception as e:
        logger.warning(f"Could not fetch commits: {e}")
        return []