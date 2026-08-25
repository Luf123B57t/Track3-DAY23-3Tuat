"""State schema for the Day 08 LangGraph lab.

Định nghĩa cấu trúc dữ liệu trạng thái (State Schema) cho Agent Workflow.
Bao gồm:
- Enum Route: Danh sách các đường hướng phân loại yêu cầu.
- LabEvent & ApprovalDecision: Các Pydantic model ghi log audit event và quyết định duyệt HITL.
- AgentState: State chính kiểu TypedDict được LangGraph quản lý xuyên suốt workflow.
- Scenario: Cấu hình kịch bản kiểm thử cho agent.
- initial_state & make_event: Hàm khởi tạo trạng thái ban đầu và tạo event log.
"""

from __future__ import annotations

from enum import StrEnum
from operator import add
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field, field_validator


class Route(StrEnum):
    """Enum quy định các tuyến (route) xử lý trong workflow."""

    SIMPLE = "simple"          # Yêu cầu đơn giản, trả lời trực tiếp không cần tool
    TOOL = "tool"              # Cần tra cứu dữ liệu / gọi tool thực thi
    MISSING_INFO = "missing_info"  # Yêu cầu thiếu thông tin, cần hỏi lại người dùng
    RISKY = "risky"            # Thao tác có rủi ro cao (hoàn tiền, xóa tk), cần phê duyệt
    ERROR = "error"            # Lỗi hệ thống/tạm thời, cần xử lý retry
    DEAD_LETTER = "dead_letter"  # Vượt quá số lần thử lại max, đẩy vào hàng chờ xử lý lỗi
    DONE = "done"              # Hoàn tất workflow


class LabEvent(BaseModel):
    """Model lưu vết sự kiện (Audit Event) dạng append-only phục vụ chấm điểm và debug."""

    node: str
    event_type: str
    message: str
    latency_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    """Quyết định phê duyệt từ con người (Human-in-the-loop)."""

    approved: bool = False
    reviewer: str = "mock-reviewer"
    comment: str = ""


class AgentState(TypedDict, total=False):
    """LangGraph state schema cho tác vụ điều phối support-ticket agent.

    Các trường dạng danh sách tích lũy (Append-only) sử dụng Annotated[list, add]
    để tự động nối dữ liệu qua các bước node.
    """

    thread_id: str             # ID định danh phiên làm việc (thread)
    scenario_id: str           # ID kịch bản kiểm thử
    query: str                 # Câu hỏi / yêu cầu từ người dùng
    route: str                 # Danh mục tuyến xử lý được classify chọn
    risk_level: str            # Mức độ rủi ro ('high' hoặc 'low')
    attempt: int               # Số lần đã thử lại (retry counter)
    max_attempts: int          # Số lần thử lại tối đa cho phép
    final_answer: str | None   # Câu trả lời cuối cùng dành cho người dùng
    evaluation_result: str     # Kết quả đánh giá tool ('success' hoặc 'needs_retry')
    pending_question: str      # Câu hỏi làm rõ thông tin khi thông tin bị thiếu
    proposed_action: str       # Mô tả hành động rủi ro chờ phê duyệt
    approval: dict[str, Any]   # Thông tin chi tiết quyết định phê duyệt (HITL)

    # Danh sách dữ liệu dạng tích lũy (Append-only)
    messages: Annotated[list[str], add]             # Nhật ký tin nhắn workflow
    tool_results: Annotated[list[str], add]         # Lịch sử kết quả thực thi các tool
    errors: Annotated[list[str], add]               # Nhật ký các lỗi phát sinh
    events: Annotated[list[dict[str, Any]], add]    # Nhật ký toàn bộ các audit event


class Scenario(BaseModel):
    """Cấu hình chi tiết một kịch bản test dành cho agent."""

    id: str
    query: str
    expected_route: Route
    requires_approval: bool = False
    should_retry: bool = False
    max_attempts: int = 3
    tags: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        """Kiểm tra đảm bảo query không được để trống."""
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


def initial_state(scenario: Scenario) -> AgentState:
    """Tạo trạng thái khởi tạo (initial state) có thể serialize từ thông tin kịch bản."""
    return {
        "thread_id": f"thread-{scenario.id}",
        "scenario_id": scenario.id,
        "query": scenario.query,
        "route": "",
        "risk_level": "unknown",
        "attempt": 0,
        "max_attempts": scenario.max_attempts,
        "final_answer": None,
        "evaluation_result": "",
        "pending_question": "",
        "proposed_action": "",
        "approval": {},
        "messages": [],
        "tool_results": [],
        "errors": [],
        "events": [],
    }


def make_event(
    node: str, event_type: str, message: str, **metadata: Any  # noqa: ANN401
) -> dict[str, Any]:
    """Hàm tiện ích giúp tạo payload event chuẩn hóa theo dạng dictionary."""
    return LabEvent(
        node=node, event_type=event_type, message=message, metadata=metadata
    ).model_dump()

