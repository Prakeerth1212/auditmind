from typing import TypedDict, Annotated, Sequence
from dataclasses import dataclass, field
from enum import Enum
import operator

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Finding:
    agent: str                  # "security" | "cost" | "performance" | "compliance"
    title: str
    description: str
    severity: Severity
    file_path: str | None = None
    line_number: int | None = None
    recommendation: str | None = None
    raw_output: dict = field(default_factory=dict)

@dataclass
class RepoContext:
    repo_url: str
    repo_name: str
    local_path: str             # temp clone path
    python_files: list[str] = field(default_factory=list)
    yaml_files: list[str] = field(default_factory=list)
    terraform_files: list[str] = field(default_factory=list)
    docker_files: list[str] = field(default_factory=list)
    total_lines: int = 0

class AuditState(TypedDict):
    audit_id: str
    repo_url: str
    repo_context: RepoContext | None
    security_status: AgentStatus
    cost_status: AgentStatus
    performance_status: AgentStatus
    compliance_status: AgentStatus
    findings: Annotated[list[Finding], operator.add]
    deduplicated_findings: list[Finding]
    severity_counts: dict[str, int]
    executive_summary: str
    report_path: str | None
    error: str | None