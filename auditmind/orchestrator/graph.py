from langgraph.graph import StateGraph, END
from auditmind.orchestrator.state import AuditState, AgentStatus
from auditmind.orchestrator.supervisor import (
    ingest_repo,
    run_security_agent,
    run_cost_agent,
    run_performance_agent,
    run_compliance_agent,
    synthesise_findings,
    generate_report,
)

def build_graph() -> StateGraph:
    graph = StateGraph(AuditState)
    graph.add_node("ingest", ingest_repo)
    graph.add_node("security", run_security_agent)
    graph.add_node("cost", run_cost_agent)
    graph.add_node("performance", run_performance_agent)
    graph.add_node("compliance", run_compliance_agent)
    graph.add_node("synthesise", synthesise_findings)
    graph.add_node("report", generate_report)
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "security")
    graph.add_edge("security", "cost")
    graph.add_edge("cost", "performance")
    graph.add_edge("performance", "compliance")
    graph.add_edge("compliance", "synthesise")
    graph.add_edge("synthesise", "report")
    graph.add_edge("report", END)
    return graph.compile()

audit_graph = build_graph()