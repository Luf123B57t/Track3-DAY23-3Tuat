# Day 08 Lab Report

## 1. Team / student

- Name: Not provided
- Repo/commit: Not provided
- Date: Generated from the current metrics report

## 2. Architecture

The workflow is a stateful LangGraph graph. `intake` normalizes the query, `classify` selects a route, and conditional edges send execution to answering, tool use, clarification, risky-action approval, or bounded retry handling. All terminal paths pass through `finalize` before `END`.

```text
START -> intake -> classify -> answer -> finalize -> END
                         |-> tool -> evaluate -> answer/retry
                         |-> clarify -> finalize
                         |-> risky_action -> approval -> tool/clarify
                         |-> retry -> tool/dead_letter -> finalize
```

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `messages` | append | Preserve workflow messages |
| `tool_results` | append | Preserve each tool attempt |
| `errors` | append | Preserve retry and failure history |
| `events` | append | Maintain the audit trail |
| `route` | overwrite | Store the current route |
| `attempt` | overwrite | Track the current retry count |
| `evaluation_result` | overwrite | Control the retry loop |
| `approval` | overwrite | Store the latest approval decision |
| `final_answer` | overwrite | Store the final response |

## 4. Scenario results

- Total scenarios: 7
- Success rate: 100.00%
- Average nodes visited: 6.57
- Total retries: 4
- Total interrupts: 2
- Resume success: False

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | True | 0 | 0 |
| S02_tool | tool | tool | True | 0 | 0 |
| S03_missing | missing_info | missing_info | True | 0 | 0 |
| S04_risky | risky | risky | True | 0 | 1 |
| S05_error | error | error | True | 3 | 0 |
| S06_delete | risky | risky | True | 0 | 1 |
| S07_dead_letter | error | error | True | 1 | 0 |

## 5. Failure analysis

1. **Retry or tool failure:** transient tool errors are recorded, evaluated, and retried only while the configured attempt limit allows. Exhausted attempts are moved to the dead-letter path.
2. **Risky action without approval:** risky requests are routed through the approval node before tool execution; rejected requests go to clarification.
3. **Missing information:** vague requests are clarified instead of answered with invented assumptions.

## 6. Persistence / recovery evidence

The graph accepts a checkpointer and uses a stable `thread_id` per scenario. Memory persistence is available for local runs, while the SQLite extension stores checkpoints in a WAL-enabled database for state history and recovery.

## 7. Extension work

SQLite checkpoint persistence was implemented using `SqliteSaver`, with support for configurable database paths and `sqlite:///` URLs.

## 8. Improvement plan

Productionize durable storage and crash-resume tests first, then add structured observability for LLM latency, token usage, routing confidence, and approval outcomes.
