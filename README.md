# T4U Backend - Test Automation for You

> **AI-Powered Autonomous Test Automation**  
> Create and execute web tests using natural language. AI agents understand your testing goals and generate stable, reliable test automation using Playwright locators.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Latest-red.svg)](https://playwright.dev/)

**[Quick Start](QUICK_START.md)** • **[Deployment Guide](DEPLOYMENT.md)** • **[E2B Template Setup](E2B_TEMPLATE_SETUP.md)** • **[Contributing](CONTRIBUTING.md)**

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Links](#quick-links)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Technology Stack](#technology-stack)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Development](#development)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## 🔗 Quick Links

- **[5-Minute Quick Start](QUICK_START.md)** - Get running immediately
- **[Deployment Guide](DEPLOYMENT.md)** - Deploy to Cloud Run, Docker, or VPS
- **[E2B Template Setup](E2B_TEMPLATE_SETUP.md)** - 6x faster sandbox startup
- **[Environment Variables](ENVIRONMENT.md)** - All configuration options
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute
- **[Open Source Checklist](OPEN_SOURCE_CHECKLIST.md)** - Pre-commit verification

---

## 🎯 Overview

**T4U (Test for You)** is an AI-powered test automation platform that uses autonomous agents to create and execute web tests. Simply describe what you want to test in natural language, and T4U's AI agents will:

1. **Understand** your testing goal using Claude 3.5 Sonnet
2. **Execute** tests in isolated E2B sandboxes with Playwright
3. **Generate** stable test scripts using semantic locators
4. **Replay** tests deterministically for regression testing

**No more brittle selectors. No more manual test maintenance.**

### Key Features

#### 🎯 Stable Test Automation
- **Semantic Locators** - Uses `by_role='button'`, `by_placeholder='Email'` instead of brittle element indices
- **Smart Exact Matching** - Intelligently disambiguates when multiple elements match
- **Works Across Updates** - Tests survive page structure changes

#### 🤖 AI-Powered Intelligence
- **Natural Language** - Write tests in plain English: "Login and validate dashboard"
- **Autonomous Agents** - Claude 3.5 Sonnet understands complex testing tasks
- **Self-Validating** - AI includes assertions automatically

#### ⚡ Performance & Scalability
- **6x Faster Startup** - Custom E2B templates with pre-installed Playwright (10s vs 60s)
- **Parallel Execution** - Run multiple test cases simultaneously
- **Async Operations** - 3x faster overall execution

#### 🎥 Real-Time Visibility
- **Live VNC Streaming** - Watch tests execute in real-time browser
- **Step-by-Step Updates** - Firestore real-time sync to frontend
- **Debug Logging** - Detailed execution traces

#### 🔄 Deterministic Replay
- **Proven Steps** - Record once, replay infinitely
- **No AI Costs** - Replay without LLM inference
- **Built-in Validations** - Assert element visibility, URL changes, counts

#### 🏗️ Developer Friendly
- **REST API + SSE** - Easy integration with any frontend
- **Comprehensive Docs** - Architecture, API reference, deployment guides
- **Open Source** - MIT License, contributions welcome

---

## 🏗️ Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │ Test Cases │  │ Test Runs  │  │ Live VNC Viewer     │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API / SSE
┌──────────────────────────▼──────────────────────────────────┐
│              FastAPI Server (api_server.py)                 │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐  │
│  │ /agent/    │  │ /api/runs/ │  │ Session Management  │  │
│  │  start     │  │  execute   │  │ (pause/resume/stop) │  │
│  └────────────┘  └────────────┘  └─────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Agent Layer                               │
│  ┌────────────────────────────────────────────────────┐    │
│  │         E2BTestOpsAI (Main Agent)                  │    │
│  │  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │ToolCallAgent │  │  BaseAgent   │              │    │
│  │  │  (ReAct)     │  │  (State Mgr) │              │    │
│  │  └──────────────┘  └──────────────┘              │    │
│  └─────────────────────┬──────────────────────────────┘    │
│                        │                                     │
│  ┌─────────────────────▼──────────────────────────────┐    │
│  │              Tool Collection                       │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │    │
│  │  │ Planning │ │ Browser  │ │ Sub-Agent        │  │    │
│  │  │ Tool     │ │ Tool     │ │ Tool             │  │    │
│  │  └──────────┘ └──────────┘ └──────────────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │    │
│  │  │ Vision   │ │ AI Steps │ │ Terminate        │  │    │
│  │  │ Tool     │ │ Tool     │ │ Tool             │  │    │
│  │  └──────────┘ └──────────┘ └──────────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 Sandbox & LLM Layer                         │
│  ┌────────────────────┐         ┌──────────────────────┐   │
│  │  E2B Sandbox       │         │   LLM Provider       │   │
│  │  ┌──────────────┐  │         │  ┌────────────────┐  │   │
│  │  │ Playwright   │  │         │  │ Claude 3.5     │  │   │
│  │  │ Browser      │  │◄────────┤  │ Sonnet         │  │   │
│  │  └──────────────┘  │         │  └────────────────┘  │   │
│  │  ┌──────────────┐  │         │  ┌────────────────┐  │   │
│  │  │ Desktop (VNC)│  │         │  │ Google Gemini  │  │   │
│  │  └──────────────┘  │         │  │ (Optional)     │  │   │
│  │  ┌──────────────┐  │         │  └────────────────┘  │   │
│  │  │ Screenshots  │  │         └──────────────────────┘   │
│  │  └──────────────┘  │                                     │
│  └────────────────────┘                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Data Storage Layer                       │
│  ┌────────────────────┐         ┌──────────────────────┐   │
│  │ Firebase Firestore │         │ Firebase Storage     │   │
│  │  ┌──────────────┐  │         │  ┌────────────────┐  │   │
│  │  │ Sessions     │  │         │  │ Screenshots    │  │   │
│  │  │ Test Cases   │  │         │  │ Artifacts      │  │   │
│  │  │ Steps        │  │         │  └────────────────┘  │   │
│  │  │ Runs         │  │         └──────────────────────┘   │
│  │  └──────────────┘  │                                     │
│  └────────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

### Architecture Principles

1. **Agent-Based**: Autonomous agents make decisions using LLM reasoning
2. **Tool-Based Abstraction**: Actions abstracted into reusable tools
3. **Sandbox Isolation**: Each session runs in isolated E2B sandbox
4. **ReAct Pattern**: Think → Act cycle for decision making
5. **Hierarchical Delegation**: Main agent delegates to sub-agents
6. **Real-time Sync**: Firestore provides live updates to frontend

---

## 📦 Core Entities

### 1. **Agent Session**
A single execution of the AI agent from start to completion.

**Key Attributes:**
- `session_id`: Unique identifier
- `user_id`: User who initiated the session
- `tenant_id`: Organization/tenant ID
- `test_case_id`: Associated test case (optional)
- `sandbox_id`: E2B sandbox identifier
- `vnc_url`: WebSocket URL for live browser viewing
- `status`: Session state (`initializing`, `running`, `paused`, `completed`, `failed`)
- `artifacts`: Files created during session
- `proven_steps`: Successful actions for replay
- `total_tokens`, `total_cost`: LLM usage tracking

**Firestore Collection:** `agent_sessions`

---

### 2. **Agent Step**
A single action taken by the agent (think + act cycle).

**Key Attributes:**
- `step_number`: Sequential step counter
- `timestamp`: When step occurred
- `thinking`: LLM's reasoning about what to do
- `tool_calls`: List of tools executed
- `tool_results`: Results from tool execution
- `status`: Step status (`thinking`, `executing`, `success`, `error`)
- `screenshot_urls`: Screenshots taken during step

**Firestore Collection:** `agent_steps`

---

### 3. **Test Case**
A validated sequence of actions that can be replayed.

**Key Attributes:**
- `test_case_id`: Unique identifier
- `session_id`: Original session that created this test case
- `proven_steps`: Validated action sequence
- `execution_history_raw`: Full execution log for AI analysis
- `summary`: Human-readable description
- `status`: Test case status

**Firestore Collection:** `test_cases`

**Proven Step Structure:**
```python
{
  "step_number": 1,
  "action": {
    "tool_name": "e2b_browser",
    "arguments": {
      "action": "navigate_to",
      "url": "https://example.com"
    }
  },
  "validation": {
    "type": "assert_element_visible",
    "description": "Login button is visible",
    "search_text": "Sign In"
  }
}
```

---

### 4. **Test Run**
Execution of multiple test cases (regression suite).

**Key Attributes:**
- `run_id`: Unique identifier
- `tenant_id`: Organization ID
- `project_id`: Project this run belongs to
- `test_case_ids`: List of test cases to execute
- `status`: Run status (`pending`, `running`, `completed`, `failed`)
- `results`: Per-test-case results
- `started_at`, `completed_at`: Timing information
- `current_test_case_index`: Progress tracking

**Firestore Collection:** `runs`

**Result Structure:**
```python
results: {
  "test_case_1": {
    "status": "passed",
    "vnc_url": "wss://...",
    "current_step": 8,
    "total_steps": 8,
    "passed_steps": 8,
    "failed_steps": 0,
    "started_at": "2025-10-27T...",
    "completed_at": "2025-10-27T..."
  }
}
```

---

### 5. **E2B Sandbox**
Isolated cloud environment for test execution.

**Key Features:**
- Ubuntu-based container (4 vCPUs, 4GB RAM)
- Playwright + Chromium pre-installed
- Desktop environment (Xvfb + Fluxbox + VNC)
- Full internet access
- File system isolation
- Auto-cleanup after session

**Access:**
- VNC WebSocket: `wss://<host>:6080/websockify`
- HTTP Endpoint: `https://<sandbox-id>.e2b.dev`

---

### 6. **Plan**
High-level task breakdown created by the planning tool.

**Structure:**
```python
{
  "plan_id": "task_login_001",
  "title": "Login and validate dashboard",
  "steps": [
    "Navigate to login page",
    "Complete login process",  # Delegated to sub-agent
    "Validate dashboard elements"
  ],
  "step_statuses": ["completed", "in_progress", "not_started"]
}
```

**States:** `not_started`, `in_progress`, `completed`, `blocked`

---

## 🔄 Main Logic Flow

### 1. **Agent Execution Flow** (`/agent/start`)

```
User Request
    │
    ▼
┌─────────────────────────────────┐
│ 1. Create Agent Session         │
│    - Generate session_id        │
│    - Save to Firestore          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 2. Initialize E2B Sandbox       │
│    - Create sandbox (~30s)      │
│    - Start Playwright browser   │
│    - Start VNC desktop          │
│    - Get VNC WebSocket URL      │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 3. Initialize Agent Tools       │
│    - Planning Tool              │
│    - Browser Tool (Playwright)  │
│    - Vision Tool (screenshots)  │
│    - Sub-Agent Tool             │
│    - AI Proven Steps Tool       │
│    - Terminate Tool             │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 4. ReAct Loop (max_steps: 20)  │
│    ┌────────────────────────┐   │
│    │ Think Phase            │   │
│    │  - Send messages to LLM│   │
│    │  - LLM returns thinking│   │
│    │    + tool calls        │   │
│    └───────┬────────────────┘   │
│            │                     │
│            ▼                     │
│    ┌────────────────────────┐   │
│    │ Act Phase              │   │
│    │  - Execute tools       │   │
│    │  - Save results        │   │
│    │  - Update Firestore    │   │
│    └───────┬────────────────┘   │
│            │                     │
│            │ Next Step           │
│            └─────────────────────┤
│                                  │
│    Exit Conditions:              │
│     - terminate() called         │
│     - max_steps reached          │
│     - error state                │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 5. Session Completion           │
│    - Mark incomplete steps      │
│    - Save proven steps          │
│    - Update session status      │
│    - Cleanup sandbox            │
└────────────┬────────────────────┘
             │
             ▼
         Complete
```

---

### 2. **Think-Act (ReAct) Pattern**

Each step follows the ReAct pattern:

```python
async def step() -> str:
    """Execute single step"""
    should_act = await self.think()  # Decide what to do
    if not should_act:
        return "Thinking complete"
    return await self.act()  # Execute decision
```

**Think Phase:**
1. Build message history (system prompt + conversation)
2. Send to LLM with available tools
3. LLM returns:
   - `content`: Reasoning about next action
   - `tool_calls`: List of tools to execute
4. Store thinking and tool calls in memory

**Act Phase:**
1. Execute each tool call sequentially
2. Capture tool results
3. Add tool results to message history
4. Save step to Firestore
5. Update session metadata

---

### 3. **Sub-Agent Delegation Flow**

Main agent delegates complex tasks to sub-agents:

```
Main Agent (Step 5)
    │
    │ "Login to the application"
    ▼
┌─────────────────────────────────┐
│ e2b_sub_agent(                  │
│   task="Login with credentials",│
│   context="On login page",      │
│   max_attempts=20               │
│ )                               │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ Sub-Agent Execution             │
│  - Creates isolated agent       │
│  - Shares sandbox & tools       │
│  - Independent LLM context      │
│  - Tries multiple approaches    │
│  - Returns only summary         │
└────────────┬────────────────────┘
             │
             │ Summary Result
             ▼
Main Agent (Step 5 complete)
"✅ Login successful, now on dashboard"
```

**Benefits:**
- Main agent context stays clean (1 step vs 10+ steps)
- Sub-agent can retry without bloating main conversation
- Failures isolated to sub-agent
- Main agent only sees success/failure summary

---

### 4. **Test Run Execution Flow** (`/api/runs/execute`)

```
POST /api/runs/execute
    │
    ▼
┌─────────────────────────────────┐
│ 1. Validate Run                 │
│    - Check run exists           │
│    - Get test_case_ids          │
│    - Reset results              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 2. Start Background Execution   │
│    - Return immediately         │
│    - Execute async              │
└────────────┬────────────────────┘
             │
             ▼
    ┌────────┴────────┐
    │                 │
    │ Sequential      │  Parallel
    │ Execution       │  Execution
    ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ For each TC: │  │ All TCs at   │
│              │  │ once with    │
│ 1. Create    │  │ asyncio      │
│    sandbox   │  │ .gather()    │
│ 2. Execute   │  └──────────────┘
│    steps     │
│ 3. Update    │
│    Firestore │
│ 4. Cleanup   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────┐
│ 3. Per Test Case Execution      │
│    For each proven_step:        │
│    ┌────────────────────────┐   │
│    │ - Get tool + arguments │   │
│    │ - Execute tool.execute │   │
│    │ - Check success        │   │
│    │ - Run validation       │   │
│    │ - Update Firestore     │   │
│    │ - Handle errors        │   │
│    └────────────────────────┘   │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ 4. Aggregate Results            │
│    - Count passed/failed        │
│    - Update run status          │
│    - Set completed_at           │
└────────────┬────────────────────┘
             │
             ▼
         Complete
```

**Firestore Updates (Real-time):**
- `results.{test_case_id}.status`: `pending` → `running` → `passed`/`failed`
- `results.{test_case_id}.current_step`: Progress counter
- `results.{test_case_id}.vnc_url`: Live browser URL
- `current_test_case_index`: Which test is running

Frontend listens to these updates for live progress display.

---

## 🛠️ Technology Stack

### Backend
- **Python 3.13**
- **FastAPI** - REST API + Server-Sent Events (SSE)
- **Pydantic** - Data validation and schemas
- **asyncio** - Asynchronous execution

### AI & LLM
- **Claude 3.5 Sonnet (Anthropic)** - Primary LLM
- **Google Gemini** - Alternative LLM (optional)
- **OpenAI SDK** - LLM client interface

### Browser Automation
- **Playwright** - Browser control
- **Chromium** - Headless browser
- **E2B SDK** - Sandbox management

### Data Storage
- **Firebase Firestore** - Real-time database
- **Firebase Storage** - Screenshot & artifact storage
- **Firebase Admin SDK** - Server-side Firebase access

### Infrastructure
- **E2B (v2.2.0)** - Serverless sandbox environments
- **Docker** - E2B sandbox base image
- **VNC + noVNC** - Remote desktop viewing

### Development
- **pytest** - Testing framework
- **uvicorn** - ASGI server
- **loguru** - Structured logging

---

## 🚀 Quick Start

**Get running in 5 minutes!** See **[QUICK_START.md](QUICK_START.md)** for detailed instructions.

### TL;DR

```bash
# 1. Clone & Install
git clone https://github.com/t4u-automation/t4u-backend.git
cd t4u-backend
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (copy example and add your API keys)
cp config/config.example-model-anthropic.toml config/config.toml
nano config/config.toml  # Add: Anthropic key, E2B key, Firebase bucket

# 3. Add Firebase credentials
# Download from Firebase Console and save as:
# config/firebase-service-account.json

# 4. Run
python api_server.py
# Server: http://localhost:8000
# Docs: http://localhost:8000/docs
```

For detailed setup, production deployment, and E2B template configuration, see:
- **[QUICK_START.md](QUICK_START.md)** - Step-by-step setup guide
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Cloud Run, Docker, VPS deployment  
- **[E2B_TEMPLATE_SETUP.md](E2B_TEMPLATE_SETUP.md)** - Custom template for 6x faster startup
- **[ENVIRONMENT.md](ENVIRONMENT.md)** - All configuration options

---

## 📡 API Reference

### Agent Endpoints

#### `POST /agent/start`
Start a new agent session with SSE streaming.

**Request:**
```json
{
  "prompt": "Login to https://example.com and verify the dashboard",
  "user_id": "user123",
  "tenant_id": "org456",
  "test_case_id": "tc789",
  "max_steps": 20
}
```

**Response:** Server-Sent Events (SSE) stream

**Events:**
- `session_created` - Session initialized
- `initializing` - Creating sandbox
- `sandbox_ready` - Sandbox ready with sandbox_id and VNC URL
- `vnc_url` - VNC WebSocket URL
- `step_start` - Step beginning (thinking + planned tools)
- `step_complete` - Step finished (tool results)
- `completed` - Session finished
- `error` - Error occurred

**Example Event:**
```json
{
  "type": "step_complete",
  "data": {
    "step_number": 3,
    "thinking": "I need to click the Sign In button",
    "tool_calls": [
      {
        "tool_name": "e2b_browser",
        "arguments": {
          "action": "click",
          "by_text": "Sign In"
        }
      }
    ],
    "tool_results": [
      {
        "tool_name": "e2b_browser",
        "success": true,
        "output": "Clicked button. URL changed to /dashboard"
      }
    ]
  }
}
```

---

#### `POST /agent/terminate/{session_id}`
Stop a running agent session.

**Response:**
```json
{
  "status": "terminated",
  "session_id": "20250127_123456_a1b2c3d4",
  "message": "Agent session terminated successfully"
}
```

---

#### `POST /agent/cancel/{session_id}`
Cancel a running agent session and properly close all records.

**Response:**
```json
{
  "status": "cancelled",
  "session_id": "20250127_123456_a1b2c3d4",
  "message": "Agent session cancelled successfully and all records closed"
}
```

**Note:** Unlike terminate, cancel marks the session as "cancelled" (not "terminated"), sets the `completed_at` timestamp, and saves a cancellation event to the agent_steps collection for proper session closure tracking.

---

#### `POST /agent/pause/{session_id}`
Pause agent execution (preserves state).

---

#### `POST /agent/resume/{session_id}`
Resume paused agent execution.

---

#### `POST /agent/intervene/{session_id}`
Inject guidance message and auto-resume.

**Request:**
```json
{
  "message": "Stop testing and use terminate tool"
}
```

---

#### `GET /agent/sessions`
List all active agent sessions.

**Response:**
```json
{
  "active_sessions": 2,
  "sessions": [
    {
      "session_id": "20250127_123456_a1b2c3d4",
      "status": "running",
      "sandbox_id": "sandbox_abc123"
    }
  ]
}
```

---

### Test Run Endpoints

#### `POST /api/runs/execute`
Execute a test run (multiple test cases).

**Request:**
```json
{
  "run_id": "run_xyz789",
  "tenant_id": "org456",
  "parallel": false
}
```

**Response:**
```json
{
  "success": true,
  "run_id": "run_xyz789",
  "message": "Run execution started with 3 test cases",
  "test_case_count": 3
}
```

**Note:** Execution happens in background. Frontend watches Firestore for live updates.

---

#### `POST /agent/replay/{tenant_id}/{test_case_id}`
Replay proven steps from a test case (SSE stream).

**Events:**
- `replay_start` - Execution starting
- `steps_loaded` - Proven steps loaded
- `sandbox_ready` - Sandbox created with VNC URL
- `step_start` - Step starting
- `tool_result` - Tool executed
- `replay_complete` - Execution finished
- `cleanup_complete` - Sandbox cleaned up

---

### Utility Endpoints

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "E2B Agent API",
  "active_sessions": 2
}
```

---

## 🤖 Agent System

### Agent Hierarchy

```
BaseAgent (Abstract)
    │
    ├─ ToolCallAgent (ReAct Pattern)
    │      │
    │      └─ E2BTestOpsAI (Web Automation)
    │             │
    │             └─ E2BTestOpsAISubAgent (Delegation)
```

### BaseAgent

**Responsibilities:**
- State management (`IDLE`, `RUNNING`, `FINISHED`, `ERROR`)
- Message memory management
- Step execution loop
- Max steps enforcement

**Key Methods:**
- `async def run(request)` - Main execution loop
- `async def step()` - Single step execution (abstract)
- `update_memory()` - Add messages to conversation

---

### ToolCallAgent

**Responsibilities:**
- LLM communication
- Tool call handling
- ReAct pattern implementation
- Firestore integration
- Message history management

**Key Methods:**
- `async def think()` - LLM decision making
- `async def act()` - Tool execution
- `async def execute_tool()` - Single tool execution
- `async def cleanup()` - Resource cleanup

**Features:**
- Parallel tool calls (multiple tools per turn)
- Automatic message truncation (keeps last 50 messages)
- Proven steps tracking
- Execution history for AI analysis
- Sub-agent result integration

---

### E2BTestOpsAI

**Responsibilities:**
- E2B sandbox initialization
- Browser tool setup
- Vision tool setup
- Sub-agent tool setup
- Desktop/VNC setup

**Available Tools:**
- `planning` - Task breakdown and progress tracking
- `e2b_browser` - Playwright browser automation
- `e2b_vision` - Screenshot viewing (OCR)
- `e2b_sub_agent` - Delegate complex subtasks
- `ai_proven_steps` - Analyze and save proven steps
- `terminate` - Complete the session

**Configuration:**
- `max_steps`: 20 (default)
- `max_observe`: 10000 (result truncation)
- `system_prompt`: Detailed instructions for web automation
- `next_step_prompt`: Per-step guidance

---

## 🔧 Tool System

### Tool Architecture

All tools inherit from `BaseTool`:

```python
class BaseTool(ABC, BaseModel):
    name: str
    description: str
    parameters: Optional[dict] = None
    
    async def execute(self, **kwargs) -> Any:
        """Tool implementation"""
```

### Core Tools

#### 1. **Planning Tool** (`planning`)

Manages high-level task plans.

**Commands:**
- `create(plan_id, title, steps)` - Create new plan
- `get(plan_id)` - View plan status
- `mark_step(plan_id, step_index, step_status, step_notes)` - Update step status

**Step States:**
- `not_started` - Not yet begun
- `in_progress` - Currently executing (ONLY ONE allowed at a time)
- `completed` - Successfully finished
- `blocked` - Cannot complete due to error

**Example:**
```python
# Create plan
await planning.execute(
    command="create",
    plan_id="login_test",
    title="Login and validate dashboard",
    steps=[
        "Navigate to login page",
        "Complete login process",
        "Validate dashboard elements"
    ]
)

# Mark step as in progress
await planning.execute(
    command="mark_step",
    plan_id="login_test",
    step_index=0,
    step_status="in_progress"
)
```

---

#### 2. **Browser Tool** (`e2b_browser`)

Playwright-based browser automation with stable locators.

**Key Actions:**

**Navigation:**
- `navigate_to(url)` - Go to URL (must include `https://`)
- `go_back()` - Browser back button
- `wait(seconds)` - Pause execution

**Interactions (Stable Locators):**
- `click(by_text='Sign In')` - Click by visible text
- `click(by_role='button', has_text='Submit')` - Click by ARIA role + text
- `fill(by_placeholder='Email', text='user@example.com')` - Fill input by placeholder
- `fill(by_label='Password', text='secret')` - Fill input by label
- `fill(by_id='username', text='user')` - Fill by ID attribute
- `send_keys(keys='Enter')` - Send keyboard keys

**Element Discovery:**
- `get_by_role(role='button')` - Find all buttons/links/inputs
- `get_headings()` - Get page headings structure
- `get_elements()` - List all interactive elements

**Assertions (for Validation):**
- `assert_element_visible(search_text='News', assertion_description='...')`
- `assert_element_hidden(search_text='Loading', assertion_description='...')`
- `assert_url_contains(expected_text='/dashboard', assertion_description='...')`
- `assert_text_contains(search_text='Welcome', expected_text='John', assertion_description='...')`
- `assert_count_equals(search_text='article', expected_count=5, locator_type='role', assertion_description='...')`
- `assert_has_value(index=0, expected_value='test@example.com', assertion_description='...')`

**Why Stable Locators?**
- ✅ Text/placeholders rarely change
- ✅ Works across page updates
- ✅ Playwright auto-waits for elements
- ❌ Indices break when DOM structure changes

**Example:**
```python
# Modern approach (stable)
await browser.execute(action="navigate_to", url="https://example.com")
await browser.execute(action="click", by_text="Sign In")
await browser.execute(action="fill", by_placeholder="Email", text="user@example.com")
await browser.execute(action="fill", by_placeholder="Password", text="secret")
await browser.execute(action="click", by_role="button", has_text="Submit")
await browser.execute(action="assert_url_contains", expected_text="/dashboard", 
                      assertion_description="Login successful")

# DEPRECATED approach (unstable - indices change!)
await browser.execute(action="get_elements")  # Returns: [0] button, [1] input...
await browser.execute(action="click_element", index=0)  # ❌ Don't use!
await browser.execute(action="input_text", index=1, text="user@example.com")  # ❌ Don't use!
```

---

#### 3. **Sub-Agent Tool** (`e2b_sub_agent`)

Delegates complex subtasks to specialized agent with isolated context.

**Parameters:**
- `task` (required) - Specific instruction (e.g., "Login with provided credentials")
- `context` (optional) - Current browser state (e.g., "Already on login page")
- `max_attempts` (optional) - Max steps for sub-agent (default: 20)

**Benefits:**
- Isolated LLM context (doesn't bloat main agent conversation)
- Can retry multiple approaches
- Returns only success/failure summary
- Main agent sees 1 step instead of 10+

**Example:**
```python
# Instead of this (bloats main agent context):
# Step 5: Click Sign In button
# Step 6: Fill email field
# Step 7: Fill password field
# Step 8: Click submit
# Step 9: Verify login
# Step 10: Check dashboard URL
# ... 6 steps in main agent!

# Do this (clean main agent context):
result = await sub_agent.execute(
    task="Login to the application with email user@example.com and password secret. Verify login was successful by checking URL change.",
    context="Currently on homepage at https://example.com",
    max_attempts=20
)
# Result: "✅ Login successful, now on dashboard"
# Only 1 step in main agent!
```

---

#### 4. **Vision Tool** (`e2b_vision`)

View screenshots saved in the sandbox (OCR-enabled).

**Actions:**
- `see_image(file_path)` - View screenshot with OCR text extraction

**Use Cases:**
- Last resort when browser locators fail
- Verify visual elements
- Extract text from images

**Example:**
```python
# Browser already saves screenshots automatically
# Use vision to view the saved screenshot
result = await vision.execute(
    action="see_image",
    file_path="screenshot.png"
)
# Returns: Screenshot with extracted text
```

---

#### 5. **AI Proven Steps Tool** (`ai_proven_steps`)

Analyzes execution history and generates proven steps for replay.

**Parameters:**
- `summary` - Brief task summary (e.g., "Login and validate dashboard")

**Process:**
1. Extracts execution history from agent
2. Identifies ACTION tools (navigate, click, fill)
3. Extracts VALIDATIONS (assertions)
4. Combines into step format:
```python
{
  "step_number": 1,
  "action": {"tool_name": "e2b_browser", "arguments": {...}},
  "validation": {"type": "assert_element_visible", "description": "..."}
}
```
5. Saves to Firestore test_case

**Example:**
```python
# At end of session
await ai_proven_steps.execute(
    summary="Login to example.com and validate news section"
)
```

---

#### 6. **Terminate Tool** (`terminate`)

Ends the agent session.

**Parameters:**
- `status` - `success` or `failed`
- `message` - Completion message

**Example:**
```python
await terminate.execute(
    status="success",
    message="All validations passed, task complete"
)
```

---

## 📊 Data Flow

### 1. **Session Creation Flow**

```
User Request
    │
    ▼
FastAPI (api_server.py)
    │
    ├─ Generate session_id
    ├─ Save to Firestore (agent_sessions)
    │
    ▼
E2BTestOpsAI.create()
    │
    ├─ Create E2B sandbox (~30s)
    ├─ Start Playwright browser
    ├─ Start desktop + VNC
    ├─ Initialize tools
    │
    ▼
Update Firestore
    ├─ sandbox_id
    ├─ vnc_url
    ├─ status: "running"
    │
    ▼
Start ReAct Loop
```

---

### 2. **Step Execution Data Flow**

```
Think Phase
    │
    ├─ LLM receives messages
    ├─ Returns thinking + tool_calls
    │
    ▼
Save to Firestore (IMMEDIATE)
    ├─ agent_steps/{doc_id}
    ├─ thinking: "I need to click Sign In"
    ├─ tool_calls: [{"tool_name": "e2b_browser", ...}]
    ├─ status: "executing"
    │
    ▼
Act Phase
    │
    ├─ Execute tool.execute()
    ├─ Get result
    │
    ▼
Update Firestore (IMMEDIATE)
    ├─ agent_steps/{doc_id}
    ├─ tool_results: [{"success": true, ...}]
    ├─ status: "success"
    │
    ▼
Update Session Metadata
    ├─ agent_sessions/{session_id}
    ├─ last_output: "Clicked Sign In button"
    ├─ total_tokens: 12450
    ├─ total_cost: 0.18
```

---

### 3. **Proven Steps Replay Data Flow**

```
POST /agent/replay/{tenant_id}/{test_case_id}
    │
    ▼
Get test_case from Firestore
    ├─ proven_steps: [...]
    │
    ▼
Create E2B sandbox
    │
    ▼
For each proven_step:
    │
    ├─ Extract: {action, validation}
    │
    ├─ Execute action (tool.execute)
    │   ├─ navigate_to(url)
    │   ├─ click(by_text="Sign In")
    │   ├─ fill(by_placeholder="Email", ...)
    │   └─ ...
    │
    ├─ Execute validation (if present)
    │   ├─ assert_element_visible(...)
    │   ├─ assert_url_contains(...)
    │   └─ ...
    │
    ├─ Save execution_step to Firestore
    │   ├─ execution_id
    │   ├─ step_index
    │   ├─ success: true/false
    │
    ├─ Update run result
    │   ├─ current_step: N
    │   ├─ passed_steps: X
    │   ├─ failed_steps: Y
    │
    │ If validation fails:
    │   └─ Break (stop execution)
    │
    ▼
Cleanup sandbox
    │
    ▼
Update run status
    ├─ status: "passed" / "failed"
    ├─ completed_at: timestamp
```

---

## ⚙️ Configuration

### LLM Configuration

```toml
[llm]
model = "claude-3-5-sonnet-20241022"
base_url = "https://api.anthropic.com/v1"
api_key = "sk-ant-..."
max_tokens = 4096
temperature = 1.0
api_type = "openai"
api_version = ""

# Optional: Token limits
max_input_tokens = 1000000  # Max tokens to use across session

# Optional: Pricing (for cost tracking)
[llm.pricing]
input_price_low = 3.0   # $ per million tokens (≤200K context)
input_price_high = 6.0  # $ per million tokens (>200K context)
output_price_low = 15.0
output_price_high = 22.5
tier_threshold = 200000
```

### E2B Configuration

```toml
[e2b]
e2b_api_key = "e2b_..."
template = "base"  # or custom template ID
timeout = 300
cwd = "/home/user"
```

**Custom Template:**
To use a pre-built template with Playwright pre-installed:
1. Build template: `cd e2b_template && e2b template build`
2. Note template ID: `e2b-xxxxxxxxxxxx`
3. Update config: `template = "e2b-xxxxxxxxxxxx"`

### Firestore Configuration

```toml
[firestore]
enabled = true
service_account_path = "config/firebase-service-account.json"
collection = "agent_steps"
storage_bucket = "your-project.appspot.com"
```

**Firestore Collections:**
- `agent_sessions` - Active and completed sessions
- `agent_steps` - Step-by-step execution logs
- `test_cases` - Validated test cases with proven steps
- `runs` - Test run executions
- `agent_sessions_executions` - Replay execution tracking
- `agent_sessions_executions_steps` - Replay step details

**Firebase Storage Buckets:**
- `screenshots/{user_id}/{session_id}/` - Screenshots
- `artifacts/{user_id}/{session_id}/` - Generated files (HTML, JSON, etc.)

---

## 🧪 Development

### Running Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Run server (development mode)
python api_server.py

# Server starts on http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Testing

```bash
# Run tests
pytest

# Run specific test
pytest tests/test_agent.py::test_browser_navigation

# Run with coverage
pytest --cov=app --cov-report=html
```

### Debugging

**Enable Debug Logging:**
```python
# In app/logger.py
logger.add("debug.log", level="DEBUG")
```

**View Sandbox Logs:**
```python
# Inside E2B sandbox
result = sandbox.exec("cat /tmp/browser.log")
print(result.stdout)
```

**Connect to VNC:**
Use the VNC URL from session to view live browser:
```
wss://<sandbox-id>.e2b.dev:6080/websockify
```

### Project Structure

```
testopsai-be/
├── app/
│   ├── agent/
│   │   ├── base.py              # BaseAgent
│   │   ├── toolcall.py          # ToolCallAgent (ReAct)
│   │   └── e2b_agent.py         # E2BTestOpsAI
│   ├── tool/
│   │   ├── base.py              # BaseTool
│   │   ├── planning.py          # PlanningTool
│   │   ├── ai_proven_steps.py   # AI Proven Steps
│   │   ├── terminate.py         # Terminate
│   │   ├── tool_collection.py   # Tool management
│   │   └── e2b/
│   │       ├── e2b_browser_tool.py   # Browser automation
│   │       ├── e2b_vision_tool.py    # Screenshots + OCR
│   │       └── e2b_sub_agent_tool.py # Sub-agent delegation
│   ├── e2b/
│   │   ├── sandbox.py           # E2B sandbox wrapper
│   │   └── tool_base.py         # E2B tool base class
│   ├── prompt/
│   │   ├── testopsai.py         # Agent prompts
│   │   └── toolcall.py          # ToolCall agent prompts
│   ├── config.py                # Configuration management
│   ├── firestore.py             # Firestore client
│   ├── llm.py                   # LLM client wrapper
│   ├── schema.py                # Pydantic schemas
│   ├── webhook.py               # Step execution schema
│   └── logger.py                # Logging setup
├── config/
│   ├── config.toml              # Main configuration
│   └── firebase-service-account.json  # Firebase credentials
├── e2b_template/
│   ├── e2b.Dockerfile           # E2B template definition
│   └── start_desktop.sh         # Desktop startup script
├── api_server.py                # FastAPI server
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## 🎯 Key Design Decisions

### 1. **Stable Locators over Indices**

**Problem:** Element indices change when page structure updates.

**Solution:** Use text-based, role-based, and attribute-based locators:
- `by_text="Sign In"` - Visible text (buttons, links)
- `by_placeholder="Email"` - Input placeholder
- `by_role="button"` - ARIA role
- `by_id="username"` - HTML ID attribute

**Benefits:**
- ✅ Works across page updates
- ✅ Self-documenting (clear what's being clicked)
- ✅ Playwright auto-waits for elements

---

### 2. **Sub-Agent Delegation**

**Problem:** Complex tasks bloat main agent's LLM context.

**Solution:** Delegate to sub-agents with isolated context.

**Example:**
```
Main Agent Context:
- Step 1: Navigate to site
- Step 2: Sub-agent: Login [1 step]
- Step 3: Sub-agent: Extract data [1 step]
Total: 3 steps

Without Sub-Agents:
- Step 1-10: Navigate + try 5 different login approaches
- Step 11-20: Try 3 different extraction methods
Total: 20 steps (context bloated!)
```

---

### 3. **Immediate Firestore Saves**

**Problem:** Frontend needs real-time updates during long-running sessions.

**Solution:** Save to Firestore IMMEDIATELY after each step.

**Implementation:**
1. Think phase: Save thinking + planned tools (status: "executing")
2. Act phase: Update with tool results (status: "success")
3. Frontend listens to Firestore changes for live updates

---

### 4. **Proven Steps with Validations**

**Problem:** AI-generated tests need validations to catch regressions.

**Solution:** Extract both ACTIONS and ASSERTIONS from execution history.

**Structure:**
```python
{
  "action": {"tool_name": "e2b_browser", "arguments": {...}},
  "validation": {"type": "assert_element_visible", "description": "..."}
}
```

**Replay Logic:**
1. Execute action
2. If action succeeds, run validation
3. If validation fails, mark test as failed
4. Continue to next step only if both pass

---

### 5. **E2B Sandboxes for Isolation**

**Problem:** Running browsers on server is resource-intensive and insecure.

**Solution:** Each session runs in isolated E2B sandbox.

**Benefits:**
- ✅ Full isolation (no cross-session contamination)
- ✅ Automatic cleanup (no resource leaks)
- ✅ Scalable (E2B handles infrastructure)
- ✅ Full internet access (no firewall restrictions)
- ✅ VNC for live viewing

---

## 📝 Best Practices

### For Users

1. **Write Clear Prompts:**
   - ✅ "Login to https://example.com with user@test.com, then validate the news section is visible"
   - ❌ "Test the login feature"

2. **Include URLs with Protocol:**
   - ✅ `https://example.com`
   - ❌ `example.com` (will fail)

3. **Use Specific Validation Instructions:**
   - ✅ "Validate that the News section is visible on the page"
   - ❌ "Check the page" (too vague)

4. **Watch VNC During Execution:**
   - Use VNC URL to see what's happening in real-time
   - Intervene if agent is stuck (`/agent/intervene`)

---

### For Developers

1. **Always Use Stable Locators:**
```python
# ✅ Good
await browser.execute(action="click", by_text="Sign In")
await browser.execute(action="fill", by_placeholder="Email", text="...")

# ❌ Bad
await browser.execute(action="click_element", index=0)
```

2. **Add Assertions to Proven Steps:**
```python
# After action, add validation
await browser.execute(action="click", by_text="Sign In")
await browser.execute(action="assert_url_contains", 
                      expected_text="/dashboard",
                      assertion_description="Login successful")
```

3. **Use Sub-Agents for Complex Tasks:**
```python
# If task involves 5+ browser actions, delegate to sub-agent
result = await sub_agent.execute(
    task="Complete the multi-step checkout process",
    context="Items already in cart"
)
```

4. **Handle Errors Gracefully:**
```python
try:
    result = await tool.execute(**args)
    if hasattr(result, 'error') and result.error:
        # Handle tool error
        await planning.execute(command="mark_step", 
                               step_status="blocked",
                               step_notes=str(result.error))
except Exception as e:
    # Handle exception
    logger.error(f"Tool execution failed: {e}")
```

---

## 🔮 Future Enhancements

- **Parallel Test Execution** - Run multiple test cases simultaneously
- **Screenshot Comparison** - Visual regression testing
- **Test Scheduling** - Cron-based test runs
- **Email Notifications** - Alert on test failures
- **Custom Assertions** - User-defined validation logic
- **Test Retry Logic** - Auto-retry flaky tests
- **Performance Metrics** - Track test execution times
- **Test Dependencies** - Run tests in specific order

---

## 📚 Documentation

### User Guides
- **[Quick Start](QUICK_START.md)** - Get running in 5 minutes
- **[Environment Variables](ENVIRONMENT.md)** - All configuration options
- **[API Reference](#api-reference)** - Complete API documentation (this file)

### Deployment
- **[Deployment Guide](DEPLOYMENT.md)** - Cloud Run, Docker, VPS, systemd
- **[E2B Template Setup](E2B_TEMPLATE_SETUP.md)** - Build custom template for faster startup
- **[Architecture](#architecture)** - System architecture and design (this file)

### Contributing
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute code
- **[Open Source Checklist](OPEN_SOURCE_CHECKLIST.md)** - Pre-commit verification
- **[Project Structure](#project-structure)** - Codebase organization (this file)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 T4U Automation

---

## 🤝 Contributing

We welcome contributions! See **[CONTRIBUTING.md](CONTRIBUTING.md)** for:
- Development workflow
- Coding standards
- Pull request process
- Testing guidelines

**Key principles:**
- ✅ Use stable locators (by_role, by_text, by_placeholder)
- ❌ Never use indices for click/fill actions
- ✅ Include assertions for validation
- ✅ Follow existing code style

---

## 📞 Support

- **Documentation:** See [Quick Links](#quick-links) above
- **Issues:** [GitHub Issues](https://github.com/t4u-automation/t4u-backend/issues)
- **Discussions:** [GitHub Discussions](https://github.com/t4u-automation/t4u-backend/discussions)

### Common Issues

See **[DEPLOYMENT.md](DEPLOYMENT.md#common-issues)** for troubleshooting:
- E2B sandbox timeout
- Firebase permission denied
- LLM API errors
- Locator timeouts

---

## 🌟 Show Your Support

If you find T4U useful, please:
- ⭐ Star the repository
- 🐛 Report bugs via [GitHub Issues](https://github.com/t4u-automation/t4u-backend/issues)
- 💡 Suggest features via [Discussions](https://github.com/t4u-automation/t4u-backend/discussions)
- 🤝 Contribute via [Pull Requests](CONTRIBUTING.md)

---

**Built with ❤️ for the test automation community**

[![GitHub](https://img.shields.io/github/stars/t4u-automation/t4u-backend?style=social)](https://github.com/t4u-automation/t4u-backend)

