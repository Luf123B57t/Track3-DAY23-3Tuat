"""CLI for the lab.

Mô-đun giao diện dòng lệnh (Command Line Interface - CLI) xây dựng bằng Typer.
Cung cấp các lệnh:
- `run-scenarios`: Chạy toàn bộ các kịch bản kiểm thử, xuất dữ liệu chỉ số (metrics JSON) và báo cáo.
- `validate-metrics`: Kiểm tra tính hợp lệ của schema file metrics JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from .graph import build_graph
from .metrics import MetricsReport, metric_from_state, summarize_metrics, write_metrics
from .persistence import build_checkpointer
from .report import write_report
from .scenarios import load_scenarios
from .state import initial_state

# Khởi tạo Typer CLI app
app = typer.Typer(no_args_is_help=True)


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Chạy tất cả kịch bản kiểm thử (grading scenarios) và ghi dữ liệu metrics ra file JSON."""
    # Nạp cấu hình từ file YAML
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    scenarios = load_scenarios(cfg["scenarios_path"])
    # Khởi tạo checkpointer theo cấu hình (memory/sqlite/none)
    checkpointer = build_checkpointer(cfg.get("checkpointer", "memory"), cfg.get("database_url"))
    # Xây dựng đồ thị workflow LangGraph
    graph = build_graph(checkpointer=checkpointer)
    metrics = []

    # Duyệt và thực thi từng kịch bản kiểm thử
    for scenario in scenarios:
        state = initial_state(scenario)
        run_config = {"configurable": {"thread_id": state["thread_id"]}}
        final_state = graph.invoke(state, config=run_config)
        metric = metric_from_state(
            final_state, scenario.expected_route.value, scenario.requires_approval
        )
        metrics.append(metric)

    # Tổng hợp chỉ số và ghi file đầu ra
    report = summarize_metrics(metrics)
    write_metrics(report, output)
    if cfg.get("report_path"):
        write_report(report, cfg["report_path"])
    typer.echo(f"Wrote metrics to {output}")


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    """Kiểm tra và xác thực schema file JSON metrics phục vụ chấm điểm."""
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


if __name__ == "__main__":
    app()

