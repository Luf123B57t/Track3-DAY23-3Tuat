"""Report generation helper.

(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    (student): Generate a report that includes:
    1. Metrics summary table (total scenarios, success rate, retries, interrupts)
    2. Per-scenario results table
    3. Architecture explanation (your graph design, state schema, reducers)
    4. Failure analysis (at least two failure modes you considered)
    5. Improvement plan

    Use reports/lab_report_template.md as your guide.

    Return: formatted markdown string
    """
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Day 08 Lab Report",
        "",
        "## 1. Team / student",
        "",
        "- Name: Not provided",
        "- Repo/commit: Not provided",
        "- Date: Generated from the current metrics report",
        "",
        "## 2. Architecture",
        "",
        "The workflow is a stateful LangGraph graph. `intake` normalizes the query, "
        "`classify` selects a route, and conditional edges send execution to answering, "
        "tool use, clarification, risky-action approval, or bounded retry handling. "
        "All terminal paths pass through `finalize` before `END`.",
        "",
        "```text",
        "START -> intake -> classify -> answer -> finalize -> END",
        "                         |-> tool -> evaluate -> answer/retry",
        "                         |-> clarify -> finalize",
        "                         |-> risky_action -> approval -> tool/clarify",
        "                         |-> retry -> tool/dead_letter -> finalize",
        "```",
        "",
        "## 3. State schema",
        "",
        "| Field | Reducer | Why |",
        "|---|---|---|",
        "| `messages` | append | Preserve workflow messages |",
        "| `tool_results` | append | Preserve each tool attempt |",
        "| `errors` | append | Preserve retry and failure history |",
        "| `events` | append | Maintain the audit trail |",
        "| `route` | overwrite | Store the current route |",
        "| `attempt` | overwrite | Track the current retry count |",
        "| `evaluation_result` | overwrite | Control the retry loop |",
        "| `approval` | overwrite | Store the latest approval decision |",
        "| `final_answer` | overwrite | Store the final response |",
        "",
        "## 4. Scenario results",
        "",
        f"- Total scenarios: {metrics.total_scenarios}",
        f"- Success rate: {metrics.success_rate:.2%}",
        f"- Average nodes visited: {metrics.avg_nodes_visited:.2f}",
        f"- Total retries: {metrics.total_retries}",
        f"- Total interrupts: {metrics.total_interrupts}",
        f"- Resume success: {metrics.resume_success}",
        "",
        "| Scenario | Expected route | Actual route | Success | Retries | Interrupts |",
        "|---|---|---|---:|---:|---:|",
    ]
    for item in metrics.scenario_metrics:
        lines.append(
            "| "
            + " | ".join(
                [
                    cell(item.scenario_id),
                    cell(item.expected_route),
                    cell(item.actual_route or "—"),
                    cell(item.success),
                    cell(item.retry_count),
                    cell(item.interrupt_count),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 5. Failure analysis",
            "",
            "1. **Retry or tool failure:** transient tool errors are recorded, evaluated, "
            "and retried only while the configured attempt limit allows. Exhausted attempts "
            "are moved to the dead-letter path.",
            "2. **Risky action without approval:** risky requests are routed through the "
            "approval node before tool execution; rejected requests go to clarification.",
            "3. **Missing information:** vague requests are clarified instead of answered "
            "with invented assumptions.",
            "",
            "## 6. Persistence / recovery evidence",
            "",
            "The graph accepts a checkpointer and uses a stable `thread_id` per scenario. "
            "Memory persistence is available for local runs, while the SQLite extension "
            "stores checkpoints in a WAL-enabled database for state history and recovery.",
            "",
            "## 7. Extension work",
            "",
            "SQLite checkpoint persistence was implemented using `SqliteSaver`, with "
            "support for configurable database paths and `sqlite:///` URLs.",
            "",
            "## 8. Improvement plan",
            "",
            "Productionize durable storage and crash-resume tests first, then add structured "
            "observability for LLM latency, token usage, routing confidence, and approval outcomes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
