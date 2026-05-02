# Firestore Schema

## Collections

### agent_sessions

Tracks each agent execution session.

```json
{
  "session_id": "20260502_143022_abc123",
  "user_id": "user_123",
  "tenant_id": "tenant_abc",
  "test_case_id": "tc_456",
  "sandbox_id": "sbx_789",
  "vnc_url": "wss://sandbox.e2b.dev/vnc/...",
  "status": "initializing | running | paused | completed | failed | cancelled",
  "created_at": "2026-05-02T04:30:22Z",
  "started_at": "2026-05-02T04:30:52Z",
  "completed_at": "2026-05-02T04:35:10Z",
  "current_step": 5,
  "total_steps": 12,
  "total_tokens": 45000,
  "total_cost": 0.23,
  "last_output": "Successfully logged in and verified dashboard",
  "error": null,
  "artifacts": ["screenshot_1.png", "screenshot_2.png"],
  "proven_steps": [...]
}
```

### agent_steps

Individual step records within a session.

```json
{
  "session_id": "20260502_143022_abc123",
  "step_number": 3,
  "timestamp": "2026-05-02T04:31:45Z",
  "thinking": "I need to click the login button...",
  "tool_calls": [
    {
      "tool_name": "e2b_browser",
      "arguments": {"action": "click", "locator": "by_text('Login')"}
    }
  ],
  "tool_results": [
    {
      "tool_name": "e2b_browser",
      "success": true,
      "output": "Clicked element successfully",
      "error": null
    }
  ],
  "status": "thinking | executing | success | error",
  "screenshot_urls": ["gs://bucket/screenshots/step3.png"]
}
```

### test_cases

Test case definitions with extracted proven steps.

```json
{
  "test_case_id": "tc_456",
  "session_id": "20260502_143022_abc123",
  "proven_steps": [
    {
      "step_number": 1,
      "action": {
        "tool_name": "e2b_browser",
        "arguments": {"action": "navigate_to", "url": "https://app.example.com"}
      },
      "validation": {
        "type": "assert_url_contains",
        "description": "Verify navigation to app"
      }
    }
  ],
  "summary": "Login flow with dashboard validation",
  "status": "active",
  "execution_history_raw": [...]
}
```

### runs

Test run aggregations (multiple test cases).

```json
{
  "run_id": "run_789",
  "tenant_id": "tenant_abc",
  "project_id": "proj_001",
  "test_case_ids": ["tc_456", "tc_457", "tc_458"],
  "status": "pending | running | completed | failed",
  "created_at": "2026-05-02T05:00:00Z",
  "started_at": "2026-05-02T05:00:05Z",
  "completed_at": "2026-05-02T05:10:30Z",
  "current_test_case_index": 2,
  "results": {
    "tc_456": {
      "status": "passed",
      "vnc_url": "wss://...",
      "current_step": 8,
      "total_steps": 8,
      "passed_steps": 8,
      "failed_steps": 0,
      "started_at": "...",
      "completed_at": "...",
      "error": null
    }
  }
}
```

### agent_sessions_executions

Replay execution tracking — stores step-by-step execution details and results for replayed test cases.

## Related
- [[API Endpoints]] - Endpoints that read/write these collections
- [[Agent System]] - How agents populate session and step data
- [[Run Logic]] - How runs and test cases interact
