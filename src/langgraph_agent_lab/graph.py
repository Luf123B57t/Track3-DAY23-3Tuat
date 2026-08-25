"""Graph construction.

Mô-đun xây dựng và biên dịch đồ thị luồng công việc LangGraph (StateGraph).
Mô-đun này được thiết kế an toàn khi import (import-safe). Việc import LangGraph
chỉ diễn ra bên trong hàm `build_graph` để đảm bảo unit test vẫn có thể chạy kiểm tra schema/metrics
ngay cả khi chưa cài đặt đầy đủ các thư viện phụ thuộc.
"""

from __future__ import annotations

from typing import Any

from .state import AgentState


def build_graph(checkpointer: Any | None = None) -> Any:  # noqa: ANN401
    """Xây dựng và biên dịch workflow StateGraph trong LangGraph.

    Kiến trúc đồ thị (Architecture):

    START → intake → classify → [conditional: route_after_classify]
      simple       → answer → finalize → END
      tool         → tool → evaluate → [conditional: route_after_evaluate]
                                          success → answer → finalize → END
                                          needs_retry → retry → [conditional: route_after_retry]
                                                                  tool (retry)
                                                                  dead_letter → finalize → END
      missing_info → clarify → finalize → END
      risky        → risky_action → approval → [conditional: route_after_approval]
                                                  approved → tool → evaluate → ...
                                                  rejected → clarify → finalize → END
      error        → retry → [conditional: route_after_retry] → ...
    """
    from langgraph.graph import END, START, StateGraph

    from .nodes import (
        answer_node,
        approval_node,
        ask_clarification_node,
        classify_node,
        dead_letter_node,
        evaluate_node,
        finalize_node,
        intake_node,
        retry_or_fallback_node,
        risky_action_node,
        tool_node,
    )
    from .routing import (
        route_after_approval,
        route_after_classify,
        route_after_evaluate,
        route_after_retry,
    )

    # Khởi tạo đồ thị StateGraph với schema trạng thái AgentState
    builder = StateGraph(AgentState)

    # 1. Đăng ký toàn bộ 11 nút (Nodes) xử lý vào đồ thị
    builder.add_node("intake", intake_node)
    builder.add_node("classify", classify_node)
    builder.add_node("tool", tool_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("answer", answer_node)
    builder.add_node("clarify", ask_clarification_node)
    builder.add_node("risky_action", risky_action_node)
    builder.add_node("approval", approval_node)
    builder.add_node("retry", retry_or_fallback_node)
    builder.add_node("dead_letter", dead_letter_node)
    builder.add_node("finalize", finalize_node)

    # 2. Thêm các cạnh cố định (Fixed Edges) kết nối các nút tuyến tính
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "classify")
    builder.add_edge("tool", "evaluate")
    builder.add_edge("risky_action", "approval")
    builder.add_edge("answer", "finalize")
    builder.add_edge("clarify", "finalize")
    builder.add_edge("dead_letter", "finalize")
    builder.add_edge("finalize", END)

    # 3. Thêm các cạnh rẽ nhánh điều kiện (Conditional Edges)
    # 3.1 Rẽ nhánh sau khi phân loại ý định ở nút classify
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "tool": "tool",
            "clarify": "clarify",
            "risky_action": "risky_action",
            "retry": "retry",
        },
    )
    # 3.2 Rẽ nhánh sau khi đánh giá kết quả công cụ ở nút evaluate
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "answer": "answer",
            "retry": "retry",
        },
    )
    # 3.3 Rẽ nhánh sau khi thực hiện ghi nhận lỗi/thử lại ở nút retry
    builder.add_conditional_edges(
        "retry",
        route_after_retry,
        {
            "tool": "tool",
            "dead_letter": "dead_letter",
        },
    )
    # 3.4 Rẽ nhánh sau bước phê duyệt người dùng ở nút approval
    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "tool": "tool",
            "clarify": "clarify",
        },
    )

    # Biên dịch đồ thị đi kèm cơ chế checkpointer (nếu có)
    return builder.compile(checkpointer=checkpointer)

