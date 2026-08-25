"""Metrics schema and helpers.

Mô-đun định nghĩa Pydantic schema và hàm tiện ích thu thập chỉ số đánh giá (Metrics):
- ScenarioMetric: Chỉ số đánh giá của từng kịch bản đơn lẻ.
- MetricsReport: Báo cáo tổng hợp toàn bộ các kịch bản.
- metric_from_state: Trích xuất chỉ số metric từ trạng thái AgentState sau khi hoàn thành.
- summarize_metrics: Tính toán chỉ số trung bình và tỷ lệ thành công.
- write_metrics: Ghi báo cáo metrics ra file JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field


class ScenarioMetric(BaseModel):
    """Model lưu trữ chỉ số đo lường hiệu năng của từng kịch bản (Scenario)."""

    scenario_id: str
    success: bool
    expected_route: str
    actual_route: str | None = None
    nodes_visited: int = 0
    retry_count: int = 0
    interrupt_count: int = 0
    approval_required: bool = False
    approval_observed: bool = False
    latency_ms: int = 0
    errors: list[str] = Field(default_factory=list)


class MetricsReport(BaseModel):
    """Model tổng hợp báo cáo chỉ số của toàn bộ kịch bản kiểm thử."""

    total_scenarios: int
    success_rate: float
    avg_nodes_visited: float
    total_retries: int
    total_interrupts: int
    resume_success: bool = False
    scenario_metrics: list[ScenarioMetric]


def metric_from_state(
    state: dict[str, Any], expected_route: str, approval_required: bool
) -> ScenarioMetric:
    """Trích xuất và tính toán thông số `ScenarioMetric` từ `AgentState` kết thúc."""
    events = state.get("events", []) or []
    errors = state.get("errors", []) or []
    actual_route = state.get("route")
    approval = state.get("approval")
    nodes = [event.get("node", "unknown") for event in events]
    retry_count = sum(1 for node in nodes if node == "retry")
    interrupt_count = sum(1 for node in nodes if node == "approval")
    has_answer = bool(state.get("final_answer") or state.get("pending_question"))
    success = actual_route == expected_route and has_answer
    if approval_required:
        success = success and approval is not None
    return ScenarioMetric(
        scenario_id=str(state.get("scenario_id", "unknown")),
        success=success,
        expected_route=expected_route,
        actual_route=actual_route,
        nodes_visited=len(nodes),
        retry_count=retry_count,
        interrupt_count=interrupt_count,
        approval_required=approval_required,
        approval_observed=approval is not None,
        errors=list(errors),
    )


def summarize_metrics(items: list[ScenarioMetric]) -> MetricsReport:
    """Tổng hợp danh sách các `ScenarioMetric` thành một `MetricsReport` tổng quan."""
    if not items:
        raise ValueError("No scenario metrics to summarize")
    return MetricsReport(
        total_scenarios=len(items),
        success_rate=sum(1 for item in items if item.success) / len(items),
        avg_nodes_visited=mean(item.nodes_visited for item in items),
        total_retries=sum(item.retry_count for item in items),
        total_interrupts=sum(item.interrupt_count for item in items),
        resume_success=False,
        scenario_metrics=items,
    )


def write_metrics(report: MetricsReport, output_path: str | Path) -> None:
    """Ghi dữ liệu `MetricsReport` ra file dưới định dạng JSON formatted."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

