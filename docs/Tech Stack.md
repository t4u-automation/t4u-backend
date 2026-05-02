# Tech Stack

## Core

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.13+ |
| Framework | FastAPI | 0.115+ |
| Server | Uvicorn | ASGI |
| Validation | Pydantic | 2.10+ |

## AI & LLM

| Provider | Model | Use Case |
|---|---|---|
| Anthropic | Claude 3.5 Sonnet | Default reasoning (recommended) |
| Moonshot AI | Kimi K2 Thinking | Advanced reasoning, 200-300 tool calls/session |
| Google | Gemini 2.5 Flash | Alternative LLM |
| Client SDK | OpenAI SDK | Universal LLM client (OpenAI-compatible API) |

## Browser Automation

| Tool | Purpose |
|---|---|
| Playwright 1.51+ | Browser control and test execution |
| Chromium | Headless browser engine |
| E2B SDK v2.2.0 | Sandbox management and provisioning |

## Data & Storage

| Service | Purpose |
|---|---|
| Firebase Firestore | Real-time NoSQL database (sessions, steps, test cases, runs) |
| Firebase Storage | Screenshot and artifact storage |
| Firebase Admin SDK | Server-side access |

## Infrastructure

| Component | Purpose |
|---|---|
| E2B Sandboxes | Isolated cloud containers with VNC |
| Docker | Containerization |
| Google Cloud Run | Serverless deployment |
| VNC + noVNC | Remote desktop viewing |
| Xvfb + Fluxbox | Virtual desktop in E2B sandbox |

## Dev & Observability

| Tool | Purpose |
|---|---|
| Pytest 8.3+ | Testing framework |
| pytest-asyncio 0.25+ | Async test support |
| Loguru 0.7+ | Structured logging |
| Structlog 25.4 | Log aggregation |
| Tenacity 9.0+ | Retry logic with exponential backoff |

## Key Libraries

| Library | Purpose |
|---|---|
| html2text | HTML to Markdown conversion |
| browser-use 0.1.40 | Browser automation utilities |
| google-generativeai | Gemini support |
| crawl4ai | Web content extraction |

## Related
- [[Configuration]] - How to configure each component
- [[LLM Integration]] - Multi-model support details
- [[Deployment]] - Docker and Cloud Run setup
