# Prompt System

## Location

Prompt templates live in `app/prompt/`:
- `testopsai.py` — Main agent system prompt
- `toolcall.py` — ToolCall agent prompts

## Main Agent Prompt (`testopsai.py`)

The system prompt defines the agent's behavior and constraints. Key sections:

### Stable Locator Rules
- **MUST** use stable locators (`by_text`, `by_role`, `by_placeholder`, `by_id`, `by_label`)
- **NEVER** use DOM index-based selectors
- Locators are self-documenting and auto-wait for elements

### Planning Workflow
1. Create a plan using PlanningTool
2. Delegate complex subtasks to sub-agents
3. Update plan progress as work completes
4. Call terminate when done

### Tool Usage Patterns
- Describes each tool's purpose and when to use it
- Provides examples for common actions (navigate, click, fill, assert)
- Specifies validation/assertion requirements

### Sub-Agent Delegation Strategy
- Delegate when a subtask would take 5+ steps
- Sub-agent inherits sandbox but gets fresh LLM context
- Only summary returns to parent — keeps context clean

### Restrictions & Best Practices
- Don't use indices for element selection
- Always validate after important actions
- Take screenshots when debugging
- Handle popups, modals, and overlays explicitly

## ToolCall Agent Prompt (`toolcall.py`)

Lower-level prompt for the ToolCallAgent base class:
- Defines the ReAct loop behavior
- Instructs the model on how to format tool calls
- Handles edge cases (no tool calls, errors, retries)

## Related
- [[Agent System]] - Agents that use these prompts
- [[Tool System]] - Tools referenced in prompts
- [[Design Decisions]] - Why these rules exist
