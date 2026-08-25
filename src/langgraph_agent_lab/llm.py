"""LLM factory helper.

Hàm hỗ trợ khởi tạo LLM client (LLM Factory Helper) dùng cho các nút xử lý trong LangGraph workflow.
Tự động phát hiện và sử dụng nhà cung cấp mô hình phù hợp dựa trên API key cấu hình trong môi trường.

Cách dùng trong các nút:
    from .llm import get_llm
    llm = get_llm()
    response = llm.invoke("Hello")
"""

from __future__ import annotations

import os
from typing import Any

# Nạp các biến môi trường từ file .env nếu thư viện python-dotenv có sẵn
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def get_llm(model: str | None = None, temperature: float = 0.0) -> Any:  # noqa: ANN401
    """Tạo đối tượng LLM client dựa trên cấu hình môi trường (.env).

    Thứ tự ưu tiên kiểm tra API key:
    1. GEMINI_API_KEY    → Khởi tạo ChatGoogleGenerativeAI
    2. OPENAI_API_KEY    → Khởi tạo ChatOpenAI
    3. ANTHROPIC_API_KEY → Khởi tạo ChatAnthropic

    Tên model có thể ghi đè qua tham số `model` hoặc biến môi trường `LLM_MODEL`.
    """
    # 1. Kiểm tra Gemini API Key
    if os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-google-genai") from exc
        return ChatGoogleGenerativeAI(
            model=model or os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temperature,
        )

    # 2. Kiểm tra OpenAI API Key
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        return ChatOpenAI(
            model=model or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=temperature,
        )

    # 3. Kiểm tra Anthropic API Key
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        return ChatAnthropic(
            model=model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            temperature=temperature,
        )

    # Nếu không tìm thấy bất kỳ API key nào
    raise RuntimeError(
        "No LLM API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env\n"
        "See .env.example for configuration."
    )

