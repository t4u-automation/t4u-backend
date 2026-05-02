# Tool System

All tools extend `BaseTool` (`app/tool/base.py`) which provides:
- Pydantic model validation for inputs
- Standard `ToolResult` output format
- Async `execute()` pattern

## Core Tools

### PlanningTool (`app/tool/planning.py`)

High-level task breakdown and progress tracking:
- Creates plans with numbered steps
- States per step: `not_started`, `in_progress`, `completed`, `blocked`
- Agent updates plan progress as it works

### AIProvenSteps (`app/tool/ai_proven_steps.py`)

Analyzes the full execution history to extract reproducible steps:
- Calls the LLM to distill actions into a deterministic sequence
- Each proven step includes an **action** (tool call) and optional **validation** (assertion)
- Saved to the test case in Firestore for future replay

### Terminate (`app/tool/terminate.py`)

Ends the agent session:
- Accepts a success/failure status
- Triggers proven step extraction
- Cleans up the sandbox

## E2B Tools (`app/tool/e2b/`)

### E2BBrowserTool (`app/tool/e2b/browser.py`)

The largest module (~136KB). Full Playwright automation with **stable locators**.

**Actions:**
| Action | Description |
|---|---|
| `navigate_to` | Go to a URL |
| `click` | Click an element |
| `fill` | Fill a text input |
| `send_keys` | Type keys (including special keys) |
| `wait` | Wait for element/condition |
| `scroll` | Scroll page or element |
| `select_option` | Select from dropdown |
| `hover` | Hover over element |
| `drag_and_drop` | Drag element to target |
| `get_element_text` | Extract text content |
| `get_attribute` | Get element attribute value |
| `discover_elements` | Find and list elements |

**Locator Types:**
| Locator | Example |
|---|---|
| `by_text` | `by_text("Submit")` |
| `by_placeholder` | `by_placeholder("Email")` |
| `by_role` | `by_role("button", name="Login")` |
| `by_id` | `by_id("username")` |
| `by_label` | `by_label("Password")` |

**Assertions:**
| Assertion | Purpose |
|---|---|
| `assert_element_visible` | Element is visible on page |
| `assert_url_contains` | URL includes substring |
| `assert_text_contains` | Element contains text |
| `assert_count_equals` | N matching elements found |

### E2BVisionTool (`app/tool/e2b/vision.py`)

View saved screenshots with OCR capabilities. Used when the agent needs to "see" the current page state.

### E2BSubAgentTool (`app/tool/e2b/sub_agent.py`, ~22KB)

Delegates complex subtasks to an isolated sub-agent:
- Sub-agent gets its own LLM conversation context
- Shares the parent's sandbox and Playwright session
- Only a summary result returns to the parent
- Keeps the parent's context clean (1 step vs 10+)

### E2BWebSearchTool (`app/tool/e2b/web_search.py`)

Web search within the sandbox.

### E2BCrawl4AITool (`app/tool/e2b/crawl4ai.py`)

Web content extraction and crawling.

### E2BShellTool (`app/tool/e2b/shell.py`)

Execute shell commands inside the E2B sandbox.

### E2BFilesTool (`app/tool/e2b/files.py`)

File operations (read/write) inside the E2B sandbox.

## Tool Exposure to LLMs

All tools are registered in OpenAI function-calling format. The LLM sees:
- Tool name
- JSON schema for parameters
- Description

Multiple tools can be called per turn (parallel execution).

## Related
- [[Agent System]] - Agents that use these tools
- [[Design Decisions]] - Why stable locators over indices
