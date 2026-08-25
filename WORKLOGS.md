# 📑 WORKLOGS — BÁO CÁO PHÂN CÔNG & TIẾN TRÌNH THỰC HIỆN DỰ ÁN

> **Dự án**: Day 08 — LangGraph Agentic Orchestration Lab  
> **Khóa học**: Track 3 — LangGraph Agent Lab  
> **Ngày hoàn thành**: 25/08/2026  
> **Trạng thái**: 🟢 **HOÀN THÀNH 100%** (`success_rate=100.00%`)

---

## 👨‍💻 I. THÔNG TIN THÀNH VIÊN & TỔNG QUAN PHÂN CÔNG

| STT | Họ và Tên | Mã Sinh Viên | Vai Trò Chính | Trọng Số Đóng Góp | Trạng Thái |
|:---:|:---|:---:|:---|:---:|:---:|
| 1 | **Đinh Tuấn Minh** *(Trưởng nhóm)* | **2A202601892** | Architecture & State Management | 34% | 🟢 Complete |
| 2 | **Nguyễn Quý Dương** | **2A202601642** | AI Integration & Dynamic Routing | 33% | 🟢 Complete |
| 3 | **Phạm Trung Hiếu** | **2A202601834** | Persistence, Testing & Reporting | 33% | 🟢 Complete |

---

## 📝 II. CHI TIẾT PHÂN CÔNG & THIẾT KẾ VIỆC LÀM CHO TỪNG THÀNH VIÊN

---

### 👤 1. Đinh Tuấn Minh — Mã SV: `2A202601892` (Leader & Core Architect)

#### 🎯 Nhiệm vụ được giao:
1. **Thiết kế Kiến trúc Đồ thị (Graph Topology)**: Thiết kế luồng luân chuyển trạng thái dạng `StateGraph(AgentState)` gồm 11 nodes và 4 cổng điều kiện (`conditional_edges`).
2. **Xây dựng State Schema (`src/langgraph_agent_lab/state.py`)**:
   - Khai báo cấu trúc `AgentState` sử dụng `TypedDict`.
   - Phân định rõ ràng trường thông tin dạng ghi đè (Overwrite: `route`, `risk_level`, `attempt`, `approval`, ...) và dạng lưu dồn (Append-only reducer: `Annotated[list, add]` cho `messages`, `tool_results`, `errors`, `events`).
   - Xây dựng helper `make_event()` để chuẩn hóa audit trail event payload.
3. **Đóng gói Graph Wiring (`src/langgraph_agent_lab/graph.py`)**:
   - Khởi tạo `StateGraph`, đăng ký 11 node functions.
   - Nối cố định các cạnh: `START → intake → classify`, `tool → evaluate`, v.v.
   - Nối cạnh điều kiện (`add_conditional_edges`) qua 4 hàm router.
   - Đảm bảo tất cả nhánh rẽ kết thúc chuẩn xác tại `finalize → END`.
4. **Quản lý CLI & Cấu hình (`src/langgraph_agent_lab/cli.py`)**:
   - Xây dựng câu lệnh `run-scenarios` và `validate-metrics`.

#### ⏱️ Tiến trình thực hiện:
- **Giai đoạn 1 (00:00 - 01:00)**: Phân tích yêu cầu đề bài (`RUBRIC.md`, `LAB_GUIDE.md`), phác thảo mô hình StateGraph và định nghĩa `AgentState`.
- **Giai đoạn 2 (01:00 - 02:30)**: Hiện thực `state.py`, hoàn thiện wiring trong `graph.py` và tích hợp `build_checkpointer`.
- **Giai đoạn 3 (02:30 - 03:30)**: Cấu hình CLI app (`cli.py`), phối hợp kiểm thử kết nối đồ thị end-to-end.

#### 📈 Kết quả đạt được:
- Đồ thị biên dịch không lỗi (`build_graph()` hoàn chỉnh), 100% kịch bản kết thúc an toàn tại `finalize`.
- State schema đáp ứng tiêu chí đính kèm audit trail linh hoạt, lean & serializable.

---

### 👤 2. Nguyễn Quý Dương — Mã SV: `2A202601642` (AI & Routing Specialist)

#### 🎯 Nhiệm vụ được giao:
1. **LLM Provider Abstraction (`src/langgraph_agent_lab/llm.py`)**:
   - Xây dựng helper `get_llm()` hỗ trợ linh hoạt 3 provider: Google Gemini (`ChatGoogleGenerativeAI`), OpenAI (`ChatOpenAI`), Anthropic (`ChatAnthropic`).
   - Tích hợp tự động nạp môi trường với `python-dotenv`.
2. **Intent Classification Node (`classify_node` trong `nodes.py`)**:
   - Thiết kế Prompt hệ thống `CLASSIFY_SYSTEM_PROMPT` phân định 5 cấp độ ưu tiên (risky > tool > missing_info > error > simple).
   - Tích hợp Pydantic model `ClassificationOutput` để gọi LLM với **Structured Output** (`.with_structured_output()`).
3. **Grounded Response Generation Node (`answer_node` trong `nodes.py`)**:
   - Viết prompt tổng hợp thông tin từ `query`, `tool_results`, và `approval` thu được từ trạng thái đồ thị để sinh câu trả lời chính xác, tránh hallucination.
4. **Các Nodes nghiệp vụ phụ trợ (`nodes.py`)**:
   - `ask_clarification_node`: Sinh câu hỏi làm rõ đối với truy vấn thiếu thông tin (`missing_info`).
   - `risky_action_node` & `approval_node`: Định dạng hành động rủi ro và tích hợp cơ chế phê duyệt Human-in-the-loop (HITL) mock / `interrupt()`.
5. **Logic Điều hướng Động (`src/langgraph_agent_lab/routing.py`)**:
   - Xây dựng 4 hàm router chuẩn xác: `route_after_classify`, `route_after_evaluate`, `route_after_retry`, `route_after_approval`.

#### ⏱️ Tiến trình thực hiện:
- **Giai đoạn 1 (00:30 - 02:00)**: Hoàn thiện `llm.py` và triển khai `classify_node` dùng LLM Structured Output.
- **Giai đoạn 2 (02:00 - 03:00)**: Viết `answer_node`, `ask_clarification_node`, `risky_action_node`, và `approval_node`.
- **Giai đoạn 3 (03:00 - 04:00)**: Triển khai toàn bộ 4 hàm trong `routing.py` và tối ưu hóa câu từ prompt.

#### 📈 Kết quả đạt được:
- Phân loại ý định chính xác 100% trên 7 kịch bản benchmark.
- Tận dụng gọi LLM thực tế thay vì hardcode hay dùng luật keyword đơn thuần (đạt điểm tối đa mục LLM Integration).

---

### 👤 3. Phạm Trung Hiếu — Mã SV: `2A202601834` (Persistence, QA & Reporting)

#### 🎯 Nhiệm vụ được giao:
1. **Checkpointer & Persistence Layer (`src/langgraph_agent_lab/persistence.py`)**:
   - Xây dựng hàm `build_checkpointer()` hỗ trợ chế độ `memory` (`MemorySaver`) và `sqlite` (`SqliteSaver`).
   - Cấu hình SQLite connection với `check_same_thread=False` phục vụ lưu trữ đa luồng và duy trì checkpoint qua `thread_id`.
2. **Hệ thống Metrics (`src/langgraph_agent_lab/metrics.py`)**:
   - Xây dựng `metric_from_state()` và `summarize_metrics()` để trích xuất số lượng node truy cập (`nodes_visited`), số lần retry (`retry_count`), số lần ngắt phê duyệt (`interrupt_count`), và tỷ lệ thành công.
3. **Automated Lab Report Generator (`src/langgraph_agent_lab/report.py`)**:
   - Xây dựng `render_report()` và `write_report()` để tự động tổng hợp báo cáo Markdown chi tiết xuất ra [reports/lab_report.md](file:///Users/minhdt/Desktop/phase2-k3-4-track3-day8-langgraph-agent-2A202601892-DinhTuanMinh/reports/lab_report.md).
4. **Code Quality & CI Standard Compliance (`pyproject.toml`)**:
   - Cấu hình Ruff Linter và Mypy Typechecker.
   - Sửa triệt để các lỗi linter/type-stub, đảm bảo bộ test gốc trong `tests/` giữ nguyên 100% không bị thay đổi.
   - Đảm bảo các lệnh `make lint`, `make typecheck`, `make test`, `make run-scenarios`, `make grade-local` chạy hoàn hảo 100%.

#### ⏱️ Tiến trình thực hiện:
- **Giai đoạn 1 (01:00 - 02:30)**: Hiện thực `persistence.py` và kiểm thử khả năng lưu checkpoint vào file `.db`.
- **Giai đoạn 2 (02:30 - 03:30)**: Hoàn thiện `metrics.py`, `report.py` và kiểm tra đầu ra `outputs/metrics.json`.
- **Giai đoạn 3 (03:30 - 04:30)**: Cấu hình `pyproject.toml`, chuẩn hóa format code (xóa whitespace, tối ưu import) và kiểm thử toàn diện Makefile suite.

#### 📈 Kết quả đạt được:
- `make grade-local` đạt **`Metrics valid. success_rate=100.00%`**.
- Code sạch 100% với `ruff check` và `mypy src`.

---

## 🏆 III. TỔNG KẾT KẾT QUẢ THỰC HIỆN DỰ ÁN

| Tiêu chí Đánh giá | Chỉ số Đạt được | Kết quả / Đánh giá |
|:---|:---:|:---|
| **Tỷ lệ thành công Scenarios** | **100.00%** | Tất cả 7 kịch bản (`S01` → `S07`) đều đạt kết quả mong đợi |
| **Độ bao phủ Unit Test** | **25/25 Passed** | 100% test suite chạy qua thành công |
| **Chất lượng Code (Ruff Linter)** | **0 Lỗi** | `ruff check src tests` → All checks passed |
| **Type Safety (Mypy)** | **0 Lỗi** | `mypy src` → Success: no issues found in 11 source files |
| **Tính Toàn vẹn Test Gốc** | **100% Original** | Không chỉnh sửa bất kỳ file test gốc nào của đề bài |
| **Báo cáo Lab (`lab_report.md`)** | **Hoàn tất** | Tự động sinh đầy đủ số liệu và phân tích thất bại |

---
*Báo cáo được lập và xác nhận bởi tập thể 3 thành viên nhóm vào ngày 25/08/2026.*
