"""Routing function tests.

Các bài unit test kiểm tra logic chuyển hướng (Routing) dựa trên trạng thái state.
"""

import pytest

from langgraph_agent_lab.routing import (
    route_after_approval,
    route_after_classify,
    route_after_evaluate,
    route_after_retry,
)
from langgraph_agent_lab.state import Route


def test_route_after_classify_simple():
    """Kiểm tra điều hướng tuyến simple sang nút answer."""
    assert route_after_classify({"route": Route.SIMPLE.value}) == "answer"


def test_route_after_classify_tool():
    """Kiểm tra điều hướng tuyến tool sang nút tool."""
    assert route_after_classify({"route": Route.TOOL.value}) == "tool"


def test_route_after_classify_risky():
    """Kiểm tra điều hướng tuyến risky sang nút risky_action."""
    assert route_after_classify({"route": Route.RISKY.value}) == "risky_action"


def test_route_after_classify_missing():
    """Kiểm tra điều hướng tuyến missing_info sang nút clarify."""
    assert route_after_classify({"route": Route.MISSING_INFO.value}) == "clarify"


def test_route_after_classify_error():
    """Kiểm tra điều hướng tuyến error sang nút retry."""
    assert route_after_classify({"route": Route.ERROR.value}) == "retry"


def test_route_after_classify_unknown_defaults():
    """Kiểm tra đường tuyến không xác định mặc định chuyển sang nút answer."""
    assert route_after_classify({"route": "unknown_route"}) == "answer"


def test_route_after_approval_approved():
    """Kiểm tra khi con người đồng ý (approved=True) chuyển sang nút tool."""
    assert route_after_approval({"approval": {"approved": True}}) == "tool"


def test_route_after_approval_rejected():
    """Kiểm tra khi con người từ chối (approved=False) chuyển sang nút clarify."""
    assert route_after_approval({"approval": {"approved": False}}) == "clarify"


def test_route_after_retry_within_limit():
    """Kiểm tra khi số lần thử lại chưa vượt quá giới hạn max_attempts thì tiếp tục chuyển sang tool."""
    assert route_after_retry({"attempt": 0, "max_attempts": 3}) == "tool"
    assert route_after_retry({"attempt": 1, "max_attempts": 3}) == "tool"
    assert route_after_retry({"attempt": 2, "max_attempts": 3}) == "tool"


def test_route_after_retry_at_limit():
    """Kiểm tra khi số lần thử đạt giới hạn max_attempts thì chuyển sang dead_letter."""
    assert route_after_retry({"attempt": 3, "max_attempts": 3}) == "dead_letter"


def test_route_after_retry_over_limit():
    """Kiểm tra khi số lần thử vượt quá giới hạn max_attempts thì chuyển sang dead_letter."""
    assert route_after_retry({"attempt": 5, "max_attempts": 3}) == "dead_letter"


def test_route_after_evaluate_success():
    """Kiểm tra đánh giá tool thành công (success) chuyển sang nút answer."""
    assert route_after_evaluate({"evaluation_result": "success"}) == "answer"


def test_route_after_evaluate_retry():
    """Kiểm tra đánh giá tool cần thử lại (needs_retry) chuyển sang nút retry."""
    assert route_after_evaluate({"evaluation_result": "needs_retry"}) == "retry"

