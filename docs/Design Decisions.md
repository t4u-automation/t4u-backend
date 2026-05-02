# Design Decisions

## 1. Stable Locators over DOM Indices

**Decision:** Always use `by_text`, `by_placeholder`, `by_role`, `by_id`, `by_label` — never numeric DOM indices.

**Why:** Index-based locators break when the DOM structure changes (reordering, adding/removing elements). Stable locators are self-documenting, auto-wait for elements, and survive UI refactors.

**Impact:** Tests are more resilient and readable. The system prompt explicitly forbids index-based locators.

## 2. Sub-Agent Delegation

**Decision:** Complex subtasks are delegated to isolated sub-agents rather than handled inline.

**Why:** Each sub-agent gets a fresh LLM context. This prevents the parent agent's context from being polluted with low-level details. A 10-step subtask becomes 1 step from the parent's perspective.

**Impact:** Better context management, cleaner execution history, more reliable proven step extraction.

## 3. Immediate Firestore Saves

**Decision:** Save thinking + tool calls to Firestore BEFORE the act phase. Update results AFTER.

**Why:** The frontend needs real-time progress updates. If the agent crashes mid-step, we still have the thinking record.

**Impact:** Live progress tracking in the UI. Forensic debugging of failed sessions.

## 4. Proven Steps with Validations

**Decision:** Extract both actions AND assertions from execution history.

**Why:** Actions alone can "pass" silently even when the app is broken. Assertions catch regressions. Replay without AI is only useful if it can detect failures.

**Impact:** Deterministic replay catches real bugs, not just "the steps ran without crashing."

## 5. E2B Sandboxes for Isolation

**Decision:** Every session runs in an isolated E2B cloud container.

**Why:** No cross-session contamination. Automatic cleanup prevents resource leaks. Full internet access for testing real applications. VNC provides live observation.

**Impact:** Horizontally scalable. Safe for multi-tenant use. No local browser management.

## 6. OpenAI SDK as Universal Client

**Decision:** Use the OpenAI SDK to communicate with all LLM providers (Anthropic, Moonshot, Google).

**Why:** All three providers expose OpenAI-compatible APIs. One client simplifies the codebase and makes swapping models a config change.

**Impact:** Adding a new LLM provider only requires updating `config.toml`.

## 7. Custom E2B Template for Fast Startup

**Decision:** Pre-build a custom E2B template with all dependencies installed.

**Why:** Standard sandbox provisioning takes 60-90 seconds. The custom template reduces this to near-instant by having Python, Playwright, Chrome, and the desktop environment pre-installed.

**Impact:** 6x faster startup. Better user experience.

## 8. 50-Message Rolling Window

**Decision:** Keep only the last 50 messages in LLM context, truncating older ones.

**Why:** Prevents context window overflow on long sessions. Most recent context is the most relevant for next-step decisions.

**Impact:** Sessions can run longer without context exhaustion, at the cost of losing early-session details.

## Related
- [[Architecture]] - How these decisions shape the system
- [[Agent System]] - Agent implementation details
- [[Tool System]] - Tool design rationale
