import os
from pathlib import Path
from auditmind.logger import get_logger

logger = get_logger(__name__)

EXTENSION_MAP = {
    ".py": "python_files",
    ".yaml": "yaml_files",
    ".yml": "yaml_files",
    ".tf": "terraform_files",
    ".dockerfile": "docker_files",
}

DOCKER_FILENAMES = {"dockerfile", "dockerfile.dev", "dockerfile.prod"}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".mypy_cache", ".pytest_cache",
    "migrations", ".terraform",
}

# max file size to analyse (skip huge generated files)
MAX_FILE_SIZE_KB = 500

def list_files_by_type(root_path: str) -> dict:
    """
    Walks the cloned repo and categorises every file by type.
    Returns a dict ready to unpack into RepoContext fields:
      {
        python_files: [...],
        yaml_files: [...],
        terraform_files: [...],
        docker_files: [...],
        total_lines: int,
      }
    """
    result = {
        "python_files": [],
        "yaml_files": [],
        "terraform_files": [],
        "docker_files": [],
        "total_lines": 0,
    }

    for dirpath, dirnames, filenames in os.walk(root_path):
        # prune skip dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in SKIP_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)

            # skip oversized files
            try:
                size_kb = os.path.getsize(full_path) / 1024
                if size_kb > MAX_FILE_SIZE_KB:
                    logger.debug(f"Skipping large file: {full_path} ({size_kb:.0f}KB)")
                    continue
            except OSError:
                continue

            category = _categorise_file(filename)
            if category:
                result[category].append(full_path)
                result["total_lines"] += _count_lines(full_path)

    logger.info(
        f"File scan complete: "
        f"{len(result['python_files'])} Python, "
        f"{len(result['yaml_files'])} YAML, "
        f"{len(result['terraform_files'])} Terraform, "
        f"{len(result['docker_files'])} Docker | "
        f"{result['total_lines']} total lines"
    )
    return result

def _categorise_file(filename: str) -> str | None:
    """Returns the category key or None if the file should be ignored."""
    name_lower = filename.lower()

    # dockerfile by name
    if name_lower in DOCKER_FILENAMES or name_lower.startswith("dockerfile"):
        return "docker_files"

    # by extension
    suffix = Path(filename).suffix.lower()
    return EXTENSION_MAP.get(suffix)

def _count_lines(file_path: str) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def read_file_safe(file_path: str) -> str:
    """
    Safe file reader with encoding fallback.
    Used by agents that need raw file content.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return ""