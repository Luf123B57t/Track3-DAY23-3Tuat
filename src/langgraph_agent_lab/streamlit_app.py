"""Streamlit UI for running the agent and reviewing risky actions."""

from __future__ import annotations

import os
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import AgentState, Route, Scenario, initial_state


def _get_interrupt(result: dict) -> object | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    interrupt = interrupts[0]
    return getattr(interrupt, "value", interrupt)


def _invoke(command: object, thread_id: str) -> dict:
    graph = st.session_state.graph
    return graph.invoke(
        command,
        config={"configurable": {"thread_id": thread_id}},
    )


def _show_state(state: AgentState | dict) -> None:
    if state.get("final_answer"):
        st.subheader("Response")
        st.write(state["final_answer"])
    if state.get("pending_question"):
        st.info(state["pending_question"])
    if state.get("errors"):
        st.warning("\n".join(state["errors"]))


st.set_page_config(page_title="Agent Approval Console", page_icon="✅", layout="wide")
st.title("Agent Approval Console")
st.caption("Run a support request and approve or reject risky actions before execution.")

load_dotenv()
# The UI owns the human-in-the-loop decision, regardless of the shell's batch setting.
os.environ["LANGGRAPH_INTERRUPT"] = "true"

if "graph" not in st.session_state:
    st.session_state.graph = build_graph(checkpointer=build_checkpointer("memory"))
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "ui-" + uuid4().hex
if "result" not in st.session_state:
    st.session_state.result = None

with st.form("request_form"):
    query = st.text_area(
        "Support request",
        placeholder="For example: Refund this customer and send a confirmation email",
        height=120,
    )
    submitted = st.form_submit_button("Run request", type="primary")

if submitted:
    if not query.strip():
        st.error("Enter a support request first.")
    else:
        scenario = Scenario(
            id=uuid4().hex,
            query=query,
            expected_route=Route.SIMPLE,
        )
        st.session_state.thread_id = "ui-" + scenario.id
        st.session_state.result = _invoke(initial_state(scenario), st.session_state.thread_id)

result = st.session_state.result
if result:
    interrupt = _get_interrupt(result)
    if interrupt is not None:
        payload = interrupt if isinstance(interrupt, dict) else {"message": str(interrupt)}
        st.warning("Human approval required")
        st.write(payload.get("message", "Review the proposed action."))
        st.code(payload.get("proposed_action", "No action description provided."))

        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Approve", type="primary", use_container_width=True):
                st.session_state.result = _invoke(
                    Command(
                        resume={
                            "approved": True,
                            "reviewer": "streamlit-reviewer",
                            "comment": "Approved in Streamlit.",
                        }
                    ),
                    st.session_state.thread_id,
                )
                st.rerun()
        with col_reject:
            if st.button("Reject", use_container_width=True):
                st.session_state.result = _invoke(
                    Command(
                        resume={
                            "approved": False,
                            "reviewer": "streamlit-reviewer",
                            "comment": "Rejected in Streamlit.",
                        }
                    ),
                    st.session_state.thread_id,
                )
                st.rerun()
    else:
        _show_state(result)

    with st.expander("Workflow state"):
        display_result = dict(result)
        if "__interrupt__" in display_result:
            display_result["__interrupt__"] = str(display_result["__interrupt__"])
        st.json(display_result)
