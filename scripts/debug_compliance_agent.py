# scripts/debug_compliance_agent.py

import asyncio
from auditmind.ingestion.github_client import clone_repo
from auditmind.ingestion.file_parser import list_files_by_type
from auditmind.orchestrator.state import RepoContext
from auditmind.agents.compliance_agent import ComplianceAgent, ComplianceChecker

async def main():
    import tempfile
    local_path = tempfile.mkdtemp(prefix="auditmind_")

    repo_url = "https://github.com/Prakeerth1212/Drift-Pipeline"
    clone_repo(repo_url, local_path)
    files = list_files_by_type(local_path)

    repo_context = RepoContext(
        repo_url=repo_url,
        repo_name="Drift-Pipeline",
        local_path=local_path,
        **files,
    )

    # test LLM call directly
    agent = ComplianceAgent()
    checker = ComplianceChecker(repo_context)
    results = checker.run_all_checks()
    failed = [r for r in results if not r["passed"]]

    summary = agent._build_summary(failed, [r for r in results if r["passed"]])
    print("=== PROMPT BEING SENT TO GEMINI ===")
    print(summary)
    print()

    print("=== LLM RESPONSE ===")
    try:
        response = agent._ask_llm(
            agent.__class__.__dict__['__module__'],  
            summary
        )
        print(response)
    except Exception as e:
        print(f"LLM ERROR: {e}")

    # test full agent run with verbose errors
    print("\n=== FULL AGENT RUN ===")
    try:
        findings = agent._analyse(repo_context)
        print(f"Findings returned: {len(findings)}")
        for f in findings:
            print(f"  [{f.severity.value}] {f.title}")
    except Exception as e:
        import traceback
        print(f"AGENT ERROR: {e}")
        traceback.print_exc()

asyncio.run(main())