from auditmind.orchestrator.state import Finding
from auditmind.logger import get_logger

logger = get_logger(__name__)

def deduplicate(findings: list[Finding]) -> list[Finding]:
    """
    Removes duplicate findings across agents.
    Two findings are duplicates if they share the same:
      - file_path + line_number (exact same location)
      - OR title similarity > 80% (same issue, different agent wording)

    Keeps the higher severity finding when deduplicating.
    """
    if not findings:
        return []

    seen: list[Finding] = []

    for candidate in findings:
        duplicate_of = _find_duplicate(candidate, seen)

        if duplicate_of is None:
            seen.append(candidate)
        else:
            # keep whichever has higher severity
            if _severity_rank(candidate.severity) > _severity_rank(duplicate_of.severity):
                seen.remove(duplicate_of)
                seen.append(candidate)
            logger.debug(
                f"Deduped: [{candidate.agent}] '{candidate.title}' "
                f"→ duplicate of [{duplicate_of.agent}] '{duplicate_of.title}'"
            )

    logger.info(f"Deduplication: {len(findings)} → {len(seen)} findings")
    return seen

def _find_duplicate(candidate: Finding, seen: list[Finding]) -> Finding | None:
    for existing in seen:
        if (
            candidate.file_path
            and existing.file_path
            and candidate.file_path == existing.file_path
            and candidate.line_number is not None
            and existing.line_number is not None
            and abs(candidate.line_number - existing.line_number) <= 2
        ):
            return existing
        if _title_similarity(candidate.title, existing.title) > 0.80:
            return existing

    return None

def _title_similarity(a: str, b: str) -> float:
    """
    Simple token overlap similarity — no external deps needed.
    Jaccard similarity on word sets.
    """
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return len(intersection) / len(union)

def _severity_rank(severity) -> int:
    from auditmind.orchestrator.state import Severity
    ranks = {
        Severity.CRITICAL: 5,
        Severity.HIGH: 4,
        Severity.MEDIUM: 3,
        Severity.LOW: 2,
        Severity.INFO: 1,
    }
    return ranks.get(severity, 0)