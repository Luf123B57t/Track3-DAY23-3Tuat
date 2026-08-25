"""Routing functions for conditional edges.

Các hàm rẽ nhánh điều kiện (Conditional Routing Functions) trong LangGraph workflow.
Mỗi hàm nhận đầu vào là AgentState hiện tại và trả về tên nút (string) tiếp theo.
Tên nút trả về PHẢI khớp chính xác với tên nút đã đăng ký trong graph.py.
"""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Điều hướng đồ thị sau khi thực hiện phân loại ý định (Classification).

    Mapping quy định nút tiếp theo dựa trên loại tuyến (`route`):
    - "simple"       → "answer"       (Trả lời ngay bằng LLM)
    - "tool"         → "tool"         (Gọi tool thực thi / tra cứu)
    - "missing_info" → "clarify"      (Hỏi người dùng để làm rõ)
    - "risky"        → "risky_action" (Chuẩn bị hành động rủi ro cần phê duyệt)
    - "error"        → "retry"        (Chuyển sang nút thử lại/lỗi)
    - Mặc định        → "answer"
    """
    route_str = state.get("route", "")
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }
    return mapping.get(route_str, "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Đánh giá kết quả chạy tool có đạt yêu cầu hay cần thử lại (Retry Loop Gate).

    Đây là vòng lặp kiểm tra rẽ nhánh:
    - Nếu evaluation_result == "needs_retry" → Chuyển sang nút "retry"
    - Ngược lại                            → Chuyển sang nút "answer" để tổng hợp câu trả lời
    """
    eval_result = state.get("evaluation_result", "")
    if eval_result == "needs_retry":
        return "retry"
    return "answer"


def route_after_retry(state: AgentState) -> str:
    """Quyết định thử lại chạy tool hay chuyển sang Dead Letter Queue khi vượt quá giới hạn.

    Giới hạn vòng lặp thử lại (Bounded Retry Loop):
    - Nếu số lần thử hiện tại < max_attempts → Quay lại "tool" để thử lại
    - Nếu số lần thử hiện tại >= max_attempts → Chuyển sang "dead_letter" (hàng chờ xử lý thất bại)
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    if attempt < max_attempts:
        return "tool"
    return "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Điều hướng luồng dựa trên kết quả phê duyệt của con người (Human Approval Decision).

    - Nếu được phê duyệt (approved=True) → Chuyển sang nút "tool" để thực thi hành động rủi ro
    - Nếu từ chối (approved=False)     → Chuyển sang nút "clarify" để thông báo / phản hồi người dùng
    """
    approval = state.get("approval", {})
    if isinstance(approval, dict) and approval.get("approved", False):
        return "tool"
    return "clarify"

