# Overview

## What is TestOpsAI?

**T4U (Test for You)** is an AI-powered autonomous test automation platform. Users write tests in plain English (e.g. "Login and validate dashboard"), and AI agents generate, execute, and validate web tests using Playwright inside isolated cloud sandboxes.

## Value Proposition

| Capability | Description |
|---|---|
| Natural language tests | Write tests as plain English prompts |
| Stable locators | Uses `by_text`, `by_role`, `by_placeholder` — never fragile DOM indices |
| Sub-agent delegation | Complex tasks split into isolated sub-agents to keep context clean |
| Isolated sandboxes | Full E2B sandbox with internet, VNC desktop, and automatic cleanup |
| Multi-LLM support | Claude 3.5 Sonnet, Kimi K2 Thinking, Google Gemini |
| Deterministic replay | Proven steps replay without AI — zero cost reruns |
| Real-time streaming | Live VNC viewing + SSE progress updates via Firebase |
| 6x faster startup | Pre-built E2B templates for instant sandbox provisioning |

## How It Works

1. User submits a natural language test prompt
2. An E2B sandbox spins up with a Playwright browser and VNC desktop
3. The AI agent enters a **ReAct loop** (Think → Act → Observe, max 20 steps)
4. Each step is saved to Firestore in real-time for live frontend updates
5. On completion, the agent extracts **proven steps** — deterministic action sequences with validations
6. Proven steps can be replayed without AI, catching regressions at zero cost

## Related
- [[Architecture]] - System design details
- [[Agent System]] - How the AI agents work
- [[Run Logic]] - Execution and replay flows
