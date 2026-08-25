"""Graph smoke tests.

Các bài test tích hợp End-to-End (Smoke Tests) cho LangGraph workflow.
Kiểm tra khả năng thực thi và rẽ nhánh của đồ thị qua các kịch bản thực tế.
"""

import importlib.util
import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        importlib.util.find_spec("langgraph") is None,
        reason="langgraph not installed",
    ),
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured (set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)",
    ),
]

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("How do I reset my password?", Route.SIMPLE.value),
        ("Please lookup order status for order 123", Route.TOOL.value),
        ("Refund this customer", Route.RISKY.value),
        ("Can you fix it?", Route.MISSING_INFO.value),
        ("Timeout failure while processing", Route.ERROR.value),
    ],
)
def test_graph_runs_and_routes_correctly(query, expected_route):
    """Kiểm tra đồ thị thực thi và rẽ nhánh chính xác theo từng loại câu hỏi query."""
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    scenario = Scenario(id="smoke", query=query, expected_route=Route(expected_route))
    state = initial_state(scenario)
    result = graph.invoke(state, config={"configurable": {"thread_id": state["thread_id"]}})
    assert result["route"] == expected_route
    assert result.get("final_answer") or result.get("pending_question")


def test_graph_terminates_all_routes():
    """Kiểm tra tất cả các tuyến (routes) đều kết thúc tại nút finalize."""
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    queries = [
        ("simple query about help", Route.SIMPLE),
        ("lookup order status 999", Route.TOOL),
        ("fix it", Route.MISSING_INFO),
        ("delete user account now", Route.RISKY),
        ("timeout error in system", Route.ERROR),
    ]
    for query, route in queries:
        scenario = Scenario(id=f"term-{route.value}", query=query, expected_route=route)
        state = initial_state(scenario)
        result = graph.invoke(state, config={"configurable": {"thread_id": state["thread_id"]}})
        events = result.get("events", [])
        finalize_events = [e for e in events if e.get("node") == "finalize"]
        assert finalize_events, f"Route {route.value} did not reach finalize node"

