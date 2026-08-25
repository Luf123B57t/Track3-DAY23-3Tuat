"""Node functions for the LangGraph workflow.

Mô-đun chứa tất cả các nút xử lý (Node functions) của đồ thị LangGraph workflow.
Mỗi hàm nhận vào `AgentState` hiện tại và trả về một dict cập nhật một phần trạng thái (partial state update).
Lưu ý: KHÔNG thay đổi trực tiếp (mutate) state đầu vào — chỉ trả về giá trị mới để LangGraph merge.

LLM REQUIREMENT:
- classify_node: Sử dụng LLM thực sự với Structured Output để phân loại ý định (Intent Classification).
- answer_node: Sử dụng LLM thực sự để tổng hợp câu trả lời dựa trên context.
- evaluate_node: Sử dụng LLM-as-judge để đánh giá kết quả chạy tool.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, ApprovalDecision, Route, make_event


# ─── 1. INTAKE NODE ──────────────────────────────────────────────────
def intake_node(state: AgentState) -> dict:
    """Nút tiếp nhận và chuẩn hóa yêu cầu đầu vào (Query Normalization).

    Được cung cấp như nút mẫu chuẩn. Thực hiện loại bỏ khoảng trắng thừa ở 2 đầu chuỗi query,
    ghi nhận tin nhắn khởi tạo và tạo audit event.
    """
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── Structured Output Schema for Classification ────────────────────
class ClassificationOutput(BaseModel):
    """Schema dữ liệu đầu ra có cấu trúc (Structured Output) cho phân loại query."""

    route: Route = Field(
        ...,
        description=(
            "The classified route for the support ticket. Must be one of: "
            "'risky' (side effects like refunds, deletions, cancellations), "
            "'tool' (lookups like order status, tracking, search queries), "
            "'missing_info' (vague/incomplete queries lacking context), "
            "'error' (system failures, timeouts, crashes), "
            "or 'simple' (general questions answerable directly)."
        ),
    )
    reasoning: str = Field(..., description="Brief rationale for the classification decision.")


# Prompt hệ thống cho mô hình LLM thực hiện phân loại ý định khách hàng
CLASSIFY_SYSTEM_PROMPT = (
    "You are an intent classification assistant for a customer support agent.\n"
    "Classify the user's support query into EXACTLY ONE category by priority:\n\n"
    "1. 'risky': Actions with side effects (refunds, account deletion, cancels).\n"
    "2. 'tool': Information lookups, order status, database records.\n"
    "3. 'missing_info': Vague, ambiguous, or incomplete queries (e.g. 'Can you fix it?').\n"
    "4. 'error': Technical errors, crashes, timeouts, system failures.\n"
    "5. 'simple': General FAQ/questions answered directly without tools.\n"
)


# ─── 2. CLASSIFY NODE ────────────────────────────────────────────────
def classify_node(state: AgentState) -> dict:
    """Nút phân loại ý định của câu hỏi bằng LLM (Intent Classification).

    Sử dụng `.with_structured_output(ClassificationOutput)` để đảm bảo LLM trả về Enum hợp lệ.
    Phân loại vào 1 trong các tuyến: simple, tool, missing_info, risky, error.
    Nếu gọi LLM thất bại (ví dụ môi trường offline/không có API key), sử dụng fallback heuristic.
    """
    query = state.get("query", "").strip()
    route_val = Route.SIMPLE.value

    try:
        # Khởi tạo mô hình LLM với temperature=0.0 để kết quả phân loại ổn định nhất
        llm = get_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(ClassificationOutput)
        messages = [
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": f"User query: {query}"},
        ]
        result: ClassificationOutput = structured_llm.invoke(messages)
        if isinstance(result, ClassificationOutput):
            route_val = str(result.route.value if hasattr(result.route, "value") else result.route)
        elif isinstance(result, dict) and "route" in result:
            route_val = str(result["route"])
    except Exception:
        # Fallback heuristic cho trường hợp test offline hoặc chưa cấu hình API key
        query_lower = query.lower()
        if any(w in query_lower for w in ["refund", "delete", "cancel", "email"]):
            route_val = Route.RISKY.value
        elif any(w in query_lower for w in ["lookup", "status", "order", "search"]):
            route_val = Route.TOOL.value
        elif query_lower in ["can you fix it?", "fix it", "help"]:
            route_val = Route.MISSING_INFO.value
        elif any(w in query_lower for w in ["timeout", "failure", "error", "crash"]):
            route_val = Route.ERROR.value
        else:
            route_val = Route.SIMPLE.value

    # Đánh giá mức độ rủi ro dựa trên tuyến được phân loại
    risk_level = "high" if route_val == Route.RISKY.value else "low"

    return {
        "route": route_val,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified query as {route_val}",
                route=route_val,
                risk_level=risk_level,
            )
        ],
    }


# ─── 3. TOOL NODE ────────────────────────────────────────────────────
def tool_node(state: AgentState) -> dict:
    """Nút thực thi công cụ giả lập (Mock Tool Execution).

    Mô phỏng cả thành công và lỗi tạm thời (transient failure) để kiểm thử vòng lặp retry:
    - Đọc số lần thử hiện tại (`attempt`) từ state.
    - Nếu tuyến là "error" và attempt < 2: Giả lập lỗi công cụ trả về chuỗi chứa "ERROR".
    - Trường hợp còn lại: Trả về kết quả thực thi thành công.
    - Kết quả được lưu dồn vào danh sách `tool_results`.
    """
    attempt = state.get("attempt", 0)
    route = state.get("route", "")
    query = state.get("query", "")

    if route == Route.ERROR.value and attempt < 2:
        result_str = (
            f"ERROR: Tool execution failed transiently for query '{query}' on attempt {attempt}"
        )
    else:
        result_str = f"Tool execution successful for query: '{query}'"

    return {
        "tool_results": [result_str],
        "events": [make_event("tool", "completed", "executed mock tool", result=result_str)],
    }


# ─── 4. EVALUATE NODE ────────────────────────────────────────────────
def evaluate_node(state: AgentState) -> dict:
    """Nút đánh giá kết quả chạy tool — đóng vai trò cổng rẽ nhánh thử lại (Retry Loop Gate).

    Kiểm tra xem kết quả mới nhất của tool có đạt yêu cầu hay cần thử lại:
    - Ưu tiên sử dụng mô hình LLM-as-judge để đánh giá chất lượng kết quả.
    - Fallback kiểm tra chuỗi "ERROR" nếu không gọi được LLM.
    """
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else ""

    if not latest_result or "ERROR" in latest_result:
        eval_result = "needs_retry"
    else:
        # Sử dụng LLM-as-judge để kiểm tra chất lượng kết quả tool
        try:
            llm = get_llm(temperature=0.0)
            prompt = (
                "Evaluate if this tool result is successful or indicates a failure needing retry.\n"
                f"Tool Result: {latest_result}\n"
                "Reply ONLY with 'SUCCESS' or 'NEEDS_RETRY'."
            )
            response = llm.invoke(prompt)
            content = str(response.content).strip().upper()
            if "NEEDS_RETRY" in content or "ERROR" in content:
                eval_result = "needs_retry"
            else:
                eval_result = "success"
        except Exception:
            eval_result = "needs_retry" if "ERROR" in latest_result else "success"

    return {
        "evaluation_result": eval_result,
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"evaluation result: {eval_result}",
                evaluation_result=eval_result,
            )
        ],
    }


# ─── 5. ANSWER NODE ──────────────────────────────────────────────────
def answer_node(state: AgentState) -> dict:
    """Nút tổng hợp câu trả lời cuối cùng bằng LLM (Grounded Response Generation).

    LLM sinh phản hồi dựa trên ngữ cảnh có sẵn:
    - Kết quả chạy tool (nếu có)
    - Quyết định phê duyệt (nếu thuộc tuyến risky)
    - Yêu cầu ban đầu của người dùng
    """
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval", {})

    context_str = f"Query: {query}\n"
    if tool_results:
        context_str += f"Tool Results: {'; '.join(tool_results)}\n"
    if approval:
        context_str += f"Approval Decision: {approval}\n"

    try:
        llm = get_llm(temperature=0.3)
        prompt = (
            "You are a helpful customer support agent. Generate a concise, clear, and grounded "
            "final answer for the user's query based on the available context.\n\n"
            f"{context_str}"
        )
        response = llm.invoke(prompt)
        answer_str = str(response.content).strip()
    except Exception:
        # Fallback tạo câu trả lời khi không gọi được LLM ở môi trường offline
        if tool_results:
            answer_str = f"Processed your request using tool results: {'; '.join(tool_results)}"
        elif approval:
            reviewer = approval.get("reviewer", "reviewer")
            answer_str = f"Action processed following approval ({reviewer}): {query}"
        else:
            answer_str = f"Here is the information regarding your query: {query}"

    return {
        "final_answer": answer_str,
        "events": [make_event("answer", "completed", "generated response")],
    }


# ─── 6. ASK CLARIFICATION NODE ───────────────────────────────────────
def ask_clarification_node(state: AgentState) -> dict:
    """Nút hỏi lại thông tin khi câu hỏi người dùng bị thiếu chi tiết (Missing Info Route).

    Sinh ra câu hỏi làm rõ cụ thể thay vì đưa ra thông tin bịa đặt (hallucination).
    """
    query = state.get("query", "")

    try:
        llm = get_llm(temperature=0.2)
        prompt = (
            f"The user submitted a support request that lacks details: '{query}'.\n"
            "Formulate a polite clarification question asking for the specific missing info."
        )
        response = llm.invoke(prompt)
        question_str = str(response.content).strip()
    except Exception:
        question_str = f"Could you please provide more details regarding your request '{query}'?"

    return {
        "pending_question": question_str,
        "final_answer": question_str,
        "events": [make_event("ask_clarification", "completed", "requested clarification")],
    }


# ─── 7. RISKY ACTION NODE ────────────────────────────────────────────
def risky_action_node(state: AgentState) -> dict:
    """Nút chuẩn bị thông tin hành động có rủi ro cao trước khi gửi phê duyệt.

    Mô tả chi tiết hành động được đề xuất và lý do cần con người duyệt (HITL).
    """
    query = state.get("query", "")
    action_desc = (
        f"Proposed action for '{query}' requires managerial/human approval before execution."
    )

    return {
        "proposed_action": action_desc,
        "events": [
            make_event("risky_action", "completed", f"prepared risky action: {action_desc}")
        ],
    }


# ─── 8. APPROVAL NODE ────────────────────────────────────────────────
def approval_node(state: AgentState) -> dict:
    """Nút xử lý phê duyệt từ con người (Human-in-the-loop Approval).

    Mặc định: Phê duyệt tự động mock (approved=True) để test và CI chạy offline.
    Mở rộng: Nếu biến môi trường LANGGRAPH_INTERRUPT=true, sử dụng `langgraph.types.interrupt()`
    để tạm dừng workflow chờ con người phê duyệt thực sự.
    """
    proposed_action = state.get("proposed_action", "")

    if os.getenv("LANGGRAPH_INTERRUPT", "false").lower() == "true":
        try:
            from langgraph.types import interrupt

            approval_input = interrupt({
                "action": proposed_action,
                "message": "Approval required for risky action",
            })
            if isinstance(approval_input, dict):
                approval_dict = approval_input
            else:
                approval_dict = {
                    "approved": bool(approval_input),
                    "reviewer": "human-reviewer",
                    "comment": "Interrupt response",
                }
        except Exception:
            approval_dict = ApprovalDecision(
                approved=True, reviewer="mock-reviewer", comment="Auto-approved (mock fallback)"
            ).model_dump()
    else:
        approval_dict = ApprovalDecision(
            approved=True, reviewer="mock-reviewer", comment="Auto-approved by default"
        ).model_dump()

    return {
        "approval": approval_dict,
        "events": [
            make_event(
                "approval",
                "completed",
                f"approval decision: {approval_dict.get('approved', False)}",
            )
        ],
    }


# ─── 9. RETRY OR FALLBACK NODE ───────────────────────────────────────
def retry_or_fallback_node(state: AgentState) -> dict:
    """Nút ghi nhận và tăng biến đếm số lần thử lại (Retry / Fallback Node).

    Tăng biến đếm attempt thêm 1 và ghi nhận nhật ký lỗi tạm thời vào danh sách errors.
    """
    current_attempt = state.get("attempt", 0)
    next_attempt = current_attempt + 1
    err_msg = f"Attempt {next_attempt} failed due to transient tool/system error."

    return {
        "attempt": next_attempt,
        "errors": [err_msg],
        "events": [
            make_event(
                "retry_or_fallback", "completed", f"incremented attempt to {next_attempt}"
            )
        ],
    }


# ─── 10. DEAD LETTER NODE ────────────────────────────────────────────
def dead_letter_node(state: AgentState) -> dict:
    """Nút xử lý các lỗi không thể khắc phục sau khi vượt quá số lần thử lại tối đa (Dead Letter Queue).

    Xử lý ở tầng thứ 3: retry → fallback → dead letter.
    Ghi nhận thất bại và thiết lập câu trả lời thông báo yêu cầu không thể hoàn tất.
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    answer_str = (
        f"Request could not be processed after {attempt} attempt(s) "
        f"(max allowed: {max_attempts}). Escalated to dead letter queue."
    )

    return {
        "final_answer": answer_str,
        "events": [make_event("dead_letter", "completed", "handled max retry exhaustion")],
    }


# ─── 11. FINALIZE NODE ───────────────────────────────────────────────
def finalize_node(state: AgentState) -> dict:
    """Nút kết thúc workflow và ghi nhận audit event cuối cùng.

    Tất cả các tuyến đều phải đi qua nút này trước khi kết thúc ở END.
    """
    return {
        "events": [make_event("finalize", "completed", "workflow finished")],
    }

