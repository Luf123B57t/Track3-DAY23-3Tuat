"""Report generation helper.

Mô-đun hỗ trợ tự động tạo báo cáo kết quả bài lab dưới dạng định dạng Markdown (lab report)
dựa trên dữ liệu chỉ số thu thập từ MetricsReport.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Tạo chuỗi nội dung báo cáo dạng Markdown từ dữ liệu đối tượng `MetricsReport`."""
    lines = [
        "# Day 08 Lab Report — LangGraph Agentic Orchestration",
        "",
        "## 1. Team / student",
        "",
        "- **Name**: Student",
        "- **Repo/commit**: day08-langgraph-agent-lab",
        "- **Date**: 2026-08-25",
        "",
        "## 2. Architecture",
        "",
        (
            "The support-ticket agent is built as a LangGraph `StateGraph(AgentState)` "
            "with 11 registered node functions and 4 conditional routing gates:"
        ),
        "",
        "```",
        "START → intake → classify → [route_after_classify]",
        "  simple       → answer → finalize → END",
        "  tool         → tool → evaluate → [route_after_evaluate]",
        "                                      success → answer → finalize → END",
        "                                      needs_retry → retry → [route_after_retry]",
        "                                                              tool (retry)",
        (
            "                                                             "
            " dead_letter → finalize → END"
        ),
        "  missing_info → clarify → finalize → END",
        "  risky        → risky_action → approval → [route_after_approval]",
        "                                              approved → tool → evaluate → ...",
        "                                              rejected → clarify → finalize → END",
        "  error        → retry → [route_after_retry] → ...",
        "```",
        "",
        "## 3. State schema",
        "",
        (
            "The state is managed using `AgentState` (`TypedDict`). Specific fields use "
            "append-only list reducers (`Annotated[list, add]`) for auditability, while "
            "state flags are updated via overwrites."
        ),
        "",
        "| Field | Reducer / Type | Mode | Description / Why |",
        "|---|---|---|---|",
        "| `thread_id` | `str` | Overwrite | Unique thread identifier per session |",
        "| `scenario_id` | `str` | Overwrite | ID of scenario being executed |",
        "| `query` | `str` | Overwrite | Original support ticket query text |",
        "| `route` | `str` | Overwrite | Current route category assigned by `classify_node` |",
        "| `risk_level` | `str` | Overwrite | Risk assessment (`'high'` for risky, else `'low'`) |",
        (
            "| `attempt` | `int` | Overwrite | Retry counter incremented by"
            " `retry_or_fallback_node` |"
        ),
        "| `max_attempts` | `int` | Overwrite | Bounded retry threshold |",
        "| `final_answer` | `str | None` | Overwrite | Final response text generated for user |",
        (
            "| `evaluation_result` | `str` | Overwrite | Gate flag (`'success'` / `'needs_retry'`)"
            " for tool evaluation |"
        ),
        (
            "| `pending_question` | `str` | Overwrite | Generated clarification question for"
            " missing info |"
        ),
        (
            "| `proposed_action` | `str` | Overwrite | Description of risky action requiring HITL"
            " review |"
        ),
        "| `approval` | `dict` | Overwrite | HITL approval decision dictionary |",
        (
            "| `messages` | `Annotated[list[str], add]` | Append-only | Audit log of workflow"
            " messages |"
        ),
        (
            "| `tool_results` | `Annotated[list[str], add]` | Append-only | History of tool call"
            " outputs |"
        ),
        (
            "| `errors` | `Annotated[list[str], add]` | Append-only | Accumulated error log for"
            " retry tracking |"
        ),
        (
            "| `events` | `Annotated[list[dict], add]` | Append-only | Complete structured audit"
            " trail of graph events |"
        ),
        "",
        "## 4. Scenario results",
        "",
        f"- **Total Scenarios**: {metrics.total_scenarios}",
        f"- **Success Rate**: {metrics.success_rate * 100:.1f}%",
        f"- **Avg Nodes Visited**: {metrics.avg_nodes_visited:.2f}",
        f"- **Total Retries**: {metrics.total_retries}",
        f"- **Total Interrupts**: {metrics.total_interrupts}",
        "",
        (
            "| Scenario ID | Expected Route | Actual Route | Success | Retries | Interrupts |"
            " Nodes Visited |"
        ),
        "|---|---|---|---:|---:|---:|---:|",
    ]

    for item in metrics.scenario_metrics:
        lines.append(
            f"| {item.scenario_id} | {item.expected_route} | {item.actual_route} | "
            f"{item.success} | {item.retry_count} | {item.interrupt_count} | "
            f"{item.nodes_visited} |"
        )

    lines.extend([
        "",
        "## 5. Failure analysis",
        "",
        (
            "1. **Transient Tool Failure & Bounded Retries**: For scenario `S05_error`,"
            " initial tool calls return transient errors. The graph routes through `evaluate`"
            " (`needs_retry`) -> `retry` (attempt count 1 -> 2) -> `tool`. Once attempt count"
            " reaches 2, tool succeeds and proceeds to `answer`. For `S07_dead_letter` where"
            " `max_attempts=1`, the loop exhausts immediately and routes to `dead_letter`,"
            " preventing infinite retry loops."
        ),
        (
            "2. **Risky Action Approval Gate**: For high-risk operations (e.g. `S04_risky` refund,"
            " `S06_delete` account deletion), `classify_node` assigns route `'risky'`. The graph"
            " routes through `risky_action_node` to format `proposed_action`, then to"
            " `approval_node`. If approved, execution proceeds to `tool`; if rejected, execution"
            " redirects to `clarify` node to seek safe alternatives."
        ),
        "",
        "## 6. Persistence / recovery evidence",
        "",
        (
            "- **SQLite Checkpointer**: Configured via `SqliteSaver(conn=sqlite3.connect(...))`"
            " in `persistence.py` supporting persistent `.db` files."
        ),
        (
            "- **Thread Isolation**: `thread_id` parameters uniquely scope state checkpoints,"
            " allowing multiple independent support conversations simultaneously."
        ),
        (
            "- **State History & Crash Resume**: `graph.get_state_history(config)` returns state"
            " history snapshots across node transitions. Re-opening a connection to a SQLite"
            " database file recovers graph state seamlessly across process restarts."
        ),
        "",
        "## 7. Extension work",
        "",
        (
            "- **SQLite Checkpointer Extension**: Implemented `SqliteSaver` integration in"
            " `persistence.py` with multi-thread support."
        ),
        (
            "- **LLM Structured Output**: Integrated `ChatOpenAI`/`ChatGoogleGenerativeAI` with"
            " `.with_structured_output(ClassificationOutput)` for intent classification."
        ),
        (
            "- **LLM-as-Judge Evaluation**: Implemented LLM quality evaluation in `evaluate_node`"
            " for tool results with fallback error handling."
        ),
        "",
        "## 8. Improvement plan",
        "",
        "If given an additional day, the top productionization priorities would be:",
        (
            "1. **Streamlit / Web Approval UI**: Build a visual dashboard for human reviewers"
            " to inspect `proposed_action` and approve/reject pending interrupts."
        ),
        (
            "2. **Parallel Tool Fan-out**: Use LangGraph `Send()` API to execute multiple tools"
            " in parallel for complex multi-part queries."
        ),
        (
            "3. **OpenTelemetry / LangSmith Tracing**: Add end-to-end tracing for LLM latency,"
            " token usage, and graph node transitions."
        ),
    ])

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Ghi nội dung báo cáo đã render ra file Markdown theo đường dẫn `output_path`."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")

