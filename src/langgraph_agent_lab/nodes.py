"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel

from .llm import get_llm
from .state import AgentState, ApprovalDecision, make_event


class ClassificationResult(BaseModel):
    route: Literal["simple", "tool", "missing_info", "risky", "error"]


class EvaluationResult(BaseModel):
    result: Literal["needs_retry", "success"]


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }



def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.

    *** MUST use a real LLM call — keyword-only heuristics will lose points. ***

    Use .with_structured_output() or equivalent to get reliable enum classification.
    The LLM should classify into one of: simple, tool, missing_info, risky, error.

    Hints:
    - See llm.py for the get_llm() helper
    - Use Pydantic model or TypedDict with .with_structured_output()
    - Set risk_level to "high" for risky routes, "low" otherwise
    - Priority guide: risky > tool > missing_info > error > simple

    Return: {"route": str, "risk_level": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    prompt = f"""Classify this user query into exactly one route: simple, tool, missing_info, risky, or error.

    Route definitions:
    - risky: an action with side effects, such as refunds, deletions, cancellations, or sending messages
    - tool: an information lookup or search requiring an external tool
    - missing_info: vague or incomplete requests lacking actionable context
    - error: a system failure, timeout, crash, or unavailable service
    - simple: a general question answerable without tools or side effects

    Apply this priority when multiple categories fit: risky > tool > missing_info > error > simple.

    User query: {query}
    """
    result = get_llm().with_structured_output(ClassificationResult).invoke(prompt)
    route = result.route
    risk_level = "high" if route == "risky" else "low"
    return {
        "route": route,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"query classified as {route}",
                route=route,
                risk_level=risk_level,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.

    Requirements:
    - Read current attempt count from state
    - If route is "error" and attempt < 2: return error result (string containing "ERROR")
    - Otherwise: return a mock success result string
    - Append result to tool_results list

    Return: {"tool_results": [result_string], "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0)
    route = state.get("route", "")
    query = state.get("query", "").strip()

    if route == "error" and attempt < 2:
        result = f"ERROR: transient tool failure on attempt {attempt}"
        event_type = "failed"
        message = "transient tool failure"
    else:
        result = f"SUCCESS: mock tool completed for query: {query}"
        event_type = "completed"
        message = "mock tool completed"

    return {
        "tool_results": [result],
        "events": [
            make_event(
                "tool",
                event_type,
                message,
                attempt=attempt,
                route=route,
            )
        ],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.

    SHOULD use LLM-as-judge for bonus points. Heuristic (e.g., check for "ERROR" substring)
    is acceptable for base score.

    Requirements:
    - Read the latest entry from tool_results
    - Set evaluation_result to "needs_retry" or "success"
    - This field drives route_after_evaluate conditional edge

    Note: You may need to add 'evaluation_result' to AgentState if not present.

    Return: {"evaluation_result": str, "events": [make_event(...)]}
    """
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else "No tool result was produced."
    prompt = f"""Act as a tool-result judge. Decide whether the latest tool result is satisfactory.

    Return needs_retry when the result reports an error, failure, timeout, or is missing.
    Return success only when the result clearly indicates the tool completed successfully.

    Latest tool result:
    {latest_result}
    """
    judgment = get_llm().with_structured_output(EvaluationResult).invoke(prompt)
    evaluation_result = judgment.result
    return {
        "evaluation_result": evaluation_result,
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"tool result evaluated as {evaluation_result}",
                evaluation_result=evaluation_result,
            )
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.

    *** MUST use a real LLM call — hardcoded strings will lose points. ***

    The LLM should generate a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - original query

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    proposed_action = state.get("proposed_action")
    prompt = f"""Answer the user's request helpfully and concisely.

    Use only the context below. Do not invent tool results, approval decisions, or completed actions.
    If the context contains an error or a rejected approval, explain that clearly and suggest the next step.

    User query:
    {query}

    Tool results:
    {tool_results or "None"}

    Proposed action:
    {proposed_action or "None"}

    Approval decision:
    {approval or "None"}
    """
    response = get_llm().invoke(prompt)
    final_answer = response.content if hasattr(response, "content") else str(response)
    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "answer",
                "completed",
                "grounded answer generated",
                has_tool_results=bool(tool_results),
                has_approval=approval is not None,
            )
        ],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.

    Note: You may need to add 'pending_question' to AgentState if not present.

    Return: {"pending_question": str, "final_answer": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    prompt = f"""Generate one specific clarification question for this incomplete user request.

    Ask only for the missing information needed to proceed. Do not answer the request,
    assume details, or include multiple questions. Return only the question.

    User request:
    {query}
    """
    response = get_llm().invoke(prompt)
    question = response.content if hasattr(response, "content") else str(response)
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [
            make_event(
                "clarify",
                "completed",
                "clarification question generated",
            )
        ],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.

    Note: You may need to add 'proposed_action' to AgentState if not present.

    Return: {"proposed_action": str, "events": [make_event(...)]}
    """
    query = state.get("query", "").strip()
    prompt = f"""Describe the risky action requested by the user for human approval.

    State exactly what would be done and why it requires explicit approval because it may
    change data, move money, send a message, or otherwise create an external side effect.
    Do not claim the action has been performed. Return a concise approval summary.

    User request:
    {query}
    """
    response = get_llm().invoke(prompt)
    proposed_action = response.content if hasattr(response, "content") else str(response)
    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "completed",
                "risky action prepared for approval",
            )
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use langgraph.types.interrupt() for real HITL.

    Return: {"approval": {"approved": bool, "reviewer": str, "comment": str}, "events": [make_event(...)]}
    """
    proposed_action = state.get("proposed_action", "")
    use_interrupt = os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true"

    if use_interrupt:
        from langgraph.types import interrupt

        decision = interrupt(
            {
                "message": "Approve this risky action?",
                "proposed_action": proposed_action,
            }
        )
        if isinstance(decision, dict):
            approval = ApprovalDecision.model_validate(decision)
        else:
            approval = ApprovalDecision(
                approved=bool(decision),
                comment="Decision received from human reviewer.",
            )
    else:
        approval = ApprovalDecision(
            approved=True,
            comment="Automatically approved by mock reviewer.",
        )

    approval_data = approval.model_dump()
    event_type = "approved" if approval.approved else "rejected"
    return {
        "approval": approval_data,
        "events": [
            make_event(
                "approval",
                event_type,
                f"risky action {event_type}",
                reviewer=approval.reviewer,
            )
        ],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.

    Requirements:
    - Read current attempt from state, increment by 1
    - Add an error message to errors list
    - Return updated attempt count

    Return: {"attempt": int, "errors": [str], "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0) + 1
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else "No tool result was produced."
    error_message = f"Retry attempt {attempt}: {latest_result}"

    return {
        "attempt": attempt,
        "errors": [error_message],
        "events": [
            make_event(
                "retry",
                "scheduled",
                "retry attempt recorded",
                attempt=attempt,
            )
        ],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.

    Return: {"final_answer": str, "events": [make_event(...)]}
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 0)
    final_answer = (
        "I couldn't complete this request after "
        f"{attempt} attempt(s); the maximum of {max_attempts} retries was reached."
    )
    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "dead_letter",
                "completed",
                "request moved to dead letter after retry limit",
                attempt=attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.

    Return: {"events": [make_event("finalize", "completed", "workflow finished")]}
    """
    return {
        "events": [make_event("finalize", "completed", "workflow finished")],
    }
