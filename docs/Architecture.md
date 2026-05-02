# Architecture

## System Layers

```
┌─────────────────────────────────────────────────────────┐
│ Frontend (React) — Test Cases, Runs, Live VNC Viewer    │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API / SSE
┌─────────────────────▼───────────────────────────────────┐
│ FastAPI Server (api_server.py)                          │
│  • /agent/start — SSE stream for agent execution        │
│  • /agent/terminate, pause, resume, cancel              │
│  • /api/runs/execute — Run multiple test cases          │
│  • /agent/replay/{tenant_id}/{test_case_id}             │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│ Agent Layer (E2BTestOpsAI)                              │
│  • ReAct pattern (Think → Act → Observe)                │
│  • Sub-agent delegation                                 │
│  • Execution history & proven steps                     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│ Tool System                                             │
│  1. PlanningTool — task breakdown & tracking             │
│  2. E2BBrowserTool — Playwright automation               │
│  3. E2BVisionTool — screenshot OCR                       │
│  4. E2BSubAgentTool — isolated subtask delegation        │
│  5. AIProvenSteps — extract reproducible steps           │
│  6. Terminate — end session                              │
│  + web_search, crawl4ai, shell, files                    │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│ E2B Sandbox + LLM                                       │
│  • Playwright browser (persistent session)               │
│  • Xvfb + Fluxbox + x11vnc desktop                       │
│  • Full internet access                                  │
│  • LLM API calls (Claude / Kimi / Gemini)                │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│ Firebase                                                │
│  • Firestore: sessions, steps, test_cases, runs          │
│  • Storage: screenshots, artifacts                       │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
testopsai-be/
├── api_server.py           # FastAPI main server (76KB)
├── selenium_server.py      # Selenium support server
├── requirements.txt        # Python dependencies
├── config/
│   ├── config.toml         # Main configuration
│   └── firebase-service-account.json
├── app/
│   ├── agent/              # AI agent implementations
│   │   ├── base.py         # BaseAgent (state machine)
│   │   ├── toolcall.py     # ToolCallAgent (ReAct + LLM)
│   │   └── e2b_agent.py    # E2BTestOpsAI (web automation)
│   ├── tool/               # Tool implementations
│   │   ├── base.py         # BaseTool abstract class
│   │   ├── planning.py     # PlanningTool
│   │   ├── ai_proven_steps.py
│   │   ├── terminate.py
│   │   └── e2b/            # E2B sandbox tools
│   │       ├── browser.py  # E2BBrowserTool (136KB)
│   │       ├── vision.py   # E2BVisionTool
│   │       ├── sub_agent.py
│   │       ├── web_search.py
│   │       ├── crawl4ai.py
│   │       ├── shell.py
│   │       └── files.py
│   ├── prompt/             # LLM prompt templates
│   │   ├── testopsai.py    # Main agent system prompt
│   │   └── toolcall.py     # ToolCall agent prompts
│   ├── e2b/                # E2B sandbox utilities
│   ├── config.py           # Configuration management
│   ├── llm.py              # LLM client wrapper
│   ├── firestore.py        # Firebase integration
│   ├── schema.py           # Pydantic models
│   └── logger.py           # Logging (loguru + structlog)
├── e2b_template/           # Custom E2B sandbox template
├── e2b_custom/             # E2B customization
├── app/deployment_google/  # Cloud Run deployment
└── logs/                   # Execution logs
```

## Execution Flow: /agent/start

```
User Request → Generate session_id
  → Save to Firestore (status: initializing)
  → Create E2B Sandbox (~30s standard / instant with custom template)
  → Start Playwright browser
  → Start desktop + VNC
  → Initialize tools
  → Return VNC URL via SSE
  → Enter ReAct Loop (max 20 steps):
      ├─ Think: LLM decides next action
      ├─ Act: Execute tool(s)
      ├─ Save: Update Firestore
      └─ Repeat until done
  → Cleanup sandbox
  → Save proven steps
  → Mark session complete
```

## Related
- [[Agent System]] - Agent hierarchy and implementation
- [[Tool System]] - Available tools
- [[API Endpoints]] - Full endpoint reference
