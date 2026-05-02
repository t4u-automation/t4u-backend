# Run Logic

## Two Execution Modes

### 1. AI Agent Execution (`/agent/start`)

The agent uses an LLM to autonomously navigate and test a web application:

```
User prompt → E2B sandbox + Playwright browser
  → ReAct loop (max 20 steps):
      Think: LLM decides next action
      Act: Execute Playwright commands via tools
      Observe: Take screenshot, check results
  → Extract proven steps
  → Save to Firestore
```

Each step is streamed via SSE and saved to Firestore in real-time.

### 2. Deterministic Replay (`/api/runs/execute`)

Replays previously-extracted proven steps without any LLM involvement:

```
Fetch test case from Firestore
  → Create E2B sandbox
  → For each proven step:
      Execute action (tool.execute directly)
      Execute validation (if present)
      Update Firestore progress
      Stop on assertion failure
  → Mark result: passed or failed
  → Close sandbox
```

**Key benefit:** Zero AI cost for regression testing.

## Proven Steps

After a successful AI session, the `AIProvenSteps` tool analyzes the full execution history and extracts a deterministic sequence:

```json
{
  "step_number": 1,
  "action": {
    "tool_name": "e2b_browser",
    "arguments": {
      "action": "navigate_to",
      "url": "https://app.example.com/login"
    }
  },
  "validation": {
    "type": "assert_url_contains",
    "description": "Verify we reached the login page"
  }
}
```

Each step has:
- **Action** — the Playwright command to execute
- **Validation** (optional) — an assertion to verify the action worked

## Test Runs (Multiple Test Cases)

The `/api/runs/execute` endpoint handles batched execution:

1. Validate the run exists in Firestore
2. Set run status to "running"
3. For each test case (sequential by default, parallel optional):
   - Create an E2B sandbox
   - Execute each proven step
   - Record pass/fail per step
   - Aggregate results
4. Mark the run as "completed" or "failed"
5. Update Firestore with final results

## Shared Test Cases

Before main execution, shared test cases can run first (e.g., login flows that multiple test cases need). This avoids duplicating common setup steps.

## Session Lifecycle

```
initializing → running → completed
                 ↓          ↑
               paused ──resume──┘
                 ↓
              cancelled
                 ↓
               failed
```

Sessions support pause/resume and can be cancelled or have guidance injected mid-execution via `/agent/intervene`.

## Related
- [[Agent System]] - How the AI agent works
- [[Tool System]] - Tools used during execution
- [[API Endpoints]] - Endpoint reference
- [[Firestore Schema]] - Data structures for runs and test cases
