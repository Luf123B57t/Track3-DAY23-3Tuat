"""State and Scenario unit tests.

Kiểm tra khởi tạo trạng thái ban đầu (initial_state) và nạp kịch bản kiểm thử (load_scenarios).
"""

from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Route, Scenario, initial_state


def test_scenario_validation():
    """Kiểm tra khởi tạo scenario và định dạng thread_id chuẩn."""
    scenario = Scenario(id="x", query="hello", expected_route=Route.SIMPLE)
    state = initial_state(scenario)
    assert state["thread_id"] == "thread-x"
    assert state["attempt"] == 0
    assert state["events"] == []


def test_initial_state_has_required_fields():
    """Verify initial_state includes all fields needed by the graph."""
    scenario = Scenario(id="test", query="test query", expected_route=Route.SIMPLE)
    state = initial_state(scenario)
    assert "query" in state
    assert "route" in state
    assert "attempt" in state
    assert "max_attempts" in state
    assert "messages" in state
    assert "tool_results" in state
    assert "errors" in state
    assert "events" in state


def test_load_scenarios():
    """Kiểm tra đọc danh sách scenarios từ file JSONL."""
    scenarios = load_scenarios("data/sample/scenarios.jsonl")
    assert len(scenarios) >= 6
    assert {item.expected_route for item in scenarios} >= {Route.SIMPLE, Route.TOOL, Route.RISKY}

