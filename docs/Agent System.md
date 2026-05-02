# Agent System

## Agent Hierarchy

```
BaseAgent (Abstract base class)
  └─ ToolCallAgent (ReAct pattern — LLM communication)
      └─ E2BTestOpsAI (Web automation agent)
          └─ E2BTestOpsAISubAgent (Isolated delegation)
```

## BaseAgent (`app/agent/base.py`)

Abstract foundation for all agents. Manages:
- **State machine**: IDLE → RUNNING → FINISHED | ERROR
- **Memory management**: message history
- **Step execution loop**: abstract framework
- **Max steps enforcement**: prevents runaway loops

## ToolCallAgent (`app/agent/toolcall.py`)

Implements the **ReAct pattern** (Reason + Act) on top of BaseAgent:

- Communicates with LLMs using the OpenAI SDK
- Manages token counting and cost tracking
- Parses tool calls from LLM responses and executes them
- Maintains message history (keeps last **50 messages**, truncates older ones)
- Saves each step to Firestore immediately (thinking + tool results)
- Tracks execution history for proven step extraction

### ReAct Loop

```
For each step (max 20):
  1. THINK — Send message history to LLM → get reasoning + tool_calls
     → Save to Firestore (status: "executing")
  
  2. ACT — Execute each tool call sequentially
     → Capture results
     → Add to message history
     → Update Firestore (status: "success" or "error")
     → Update session metadata (tokens, cost)
  
  3. EXIT CONDITIONS:
     - terminate() tool called
     - max_steps reached
     - unrecoverable error
```

## E2BTestOpsAI (`app/agent/e2b_agent.py`)

The main web automation agent. On initialization:

1. Creates an E2B sandbox (~10-30s standard, instant with custom template)
2. Starts Playwright browser with Chromium
3. Starts Xvfb + Fluxbox + x11vnc desktop environment
4. Initializes all tools: planning, browser, vision, sub-agent, proven steps, terminate
5. Returns VNC URL for live viewing

**Configuration:**
- Max **20 steps** per session
- System prompt from `app/prompt/testopsai.py`
- Next-step guidance injected per iteration

## E2BTestOpsAISubAgent

Isolated agent for delegated subtasks:
- Gets its own LLM context (no pollution of parent context)
- Shares the parent's E2B sandbox and Playwright session
- Only a summary result returns to the parent agent
- Turns 10+ steps into 1 step from the parent's perspective

## State Management

```
IDLE ──start()──→ RUNNING ──complete()──→ FINISHED
                     │
                     ├──pause()──→ PAUSED ──resume()──→ RUNNING
                     │
                     └──error()──→ ERROR
```

Sessions can also be **cancelled** via the `/agent/cancel` endpoint, which sets status to "cancelled" and closes all Firestore records.

## Related
- [[Tool System]] - Tools available to agents
- [[LLM Integration]] - How agents communicate with LLMs
- [[Prompt System]] - System prompts that guide agent behavior
- [[Run Logic]] - How agents execute test runs
