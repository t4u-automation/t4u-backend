# API Endpoints

All endpoints are defined in `api_server.py`.

## Agent Execution

### POST /agent/start

Start a new AI agent session. Returns an SSE stream.

**Payload:**
```json
{
  "prompt": "Login and validate dashboard",
  "user_id": "user_123",
  "tenant_id": "tenant_abc",
  "test_case_id": "tc_456",
  "max_steps": 20
}
```

**SSE Events:**
| Event | Description |
|---|---|
| `session_created` | Session ID assigned |
| `initializing` | Sandbox starting up |
| `sandbox_ready` | Sandbox provisioned |
| `vnc_url` | VNC URL for live viewing |
| `step_start` | Agent beginning a new step |
| `step_complete` | Step finished (with results) |
| `completed` | Session finished successfully |
| `error` | Session failed |

### POST /agent/terminate/{session_id}

Force-stop a running session.

### POST /agent/cancel/{session_id}

Cancel a session. Marks status as "cancelled" and closes all Firestore records.

### POST /agent/pause/{session_id}

Pause execution while preserving state.

### POST /agent/resume/{session_id}

Resume a paused session.

### POST /agent/intervene/{session_id}

Inject guidance into a running session.

**Payload:**
```json
{
  "message": "Try clicking the hamburger menu first"
}
```

Auto-resumes the session after injecting the message.

### GET /agent/sessions

List all active sessions.

## Test Runs & Replay

### POST /api/runs/execute

Execute a test run (multiple test cases).

**Payload:**
```json
{
  "run_id": "run_789",
  "tenant_id": "tenant_abc",
  "parallel": false
}
```

Executes test cases sequentially (default) or in parallel. Updates Firestore in real-time.

### POST /agent/replay/{tenant_id}/{test_case_id}

Replay proven steps without AI. Returns an SSE stream with progress updates. Zero LLM cost.

## Utility

### GET /health

Health check endpoint.

## Related
- [[Architecture]] - Where endpoints fit in the system
- [[Firestore Schema]] - Data structures used by endpoints
- [[Run Logic]] - Execution flow details
