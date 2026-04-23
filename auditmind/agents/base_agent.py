from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from auditmind.orchestrator.state import Finding, RepoContext, Severity
from auditmind.logger import get_logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from auditmind.config import settings
import time

logger = get_logger(__name__)

class BaseAgent(ABC):
    agent_name: str = "base"

    def __init__(self):
        self.llm = self._build_llm()

    def _build_llm(self) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.1,
            max_output_tokens=2048,
        )
    
    def run(self, repo_context: RepoContext) -> list[Finding]:
        start = time.time()
        logger.info(f"[{self.agent_name}] starting on {repo_context.repo_name}")
        try:
            findings = self._analyse(repo_context)
            elapsed = round(time.time() - start, 2)
            logger.info(f"[{self.agent_name}] done — {len(findings)} findings in {elapsed}s")
            return findings
        except Exception as e:
            import traceback
            logger.error(f"[{self.agent_name}] failed: {e}")
            logger.error(traceback.format_exc())
            return []

    @abstractmethod
    def _analyse(self, repo_context: RepoContext) -> list[Finding]:
        ...

    def _ask_llm(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = self.llm.invoke(messages)
        return response.content

    def _make_finding(
        self,
        title: str,
        description: str,
        severity: Severity,
        file_path: str | None = None,
        line_number: int | None = None,
        recommendation: str | None = None,
        raw_output: dict = None,
    ) -> Finding:
        return Finding(
            agent=self.agent_name,
            title=title,
            description=description,
            severity=severity,
            file_path=file_path,
            line_number=line_number,
            recommendation=recommendation,
            raw_output=raw_output or {},
        )