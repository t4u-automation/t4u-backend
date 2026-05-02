# LLM Integration

## Client Architecture (`app/llm.py`)

Uses the **OpenAI SDK** as a universal client. All LLM providers expose OpenAI-compatible APIs, so one client handles everything.

## Supported Models

### Claude 3.5 Sonnet (Default)
- Provider: Anthropic
- Base URL: `https://api.anthropic.com/v1`
- Best for: General test automation, balanced reasoning
- Max tokens: 4096
- Temperature: 1.0

### Kimi K2 Thinking
- Provider: Moonshot AI
- Base URL: `https://api.moonshot.ai/v1/`
- Best for: Advanced reasoning, complex multi-step tasks
- Supports 200-300 tool calls per session
- Trillion-parameter Mixture of Experts architecture
- Max tokens: 8192
- Temperature: 0.0 (deterministic)

### Google Gemini
- Provider: Google
- Base URL: `https://generativelanguage.googleapis.com/v1beta/`
- Alternative option

## Token Counting & Cost Tracking

Per-message token counting covers both text and images. Pricing uses a **tiered model**:

| Metric | Below 200K tokens | Above 200K tokens |
|---|---|---|
| Input price | `input_price_low` | `input_price_high` |
| Output price | `output_price_low` | `output_price_high` |

Costs are aggregated at the session level and saved to Firestore.

## Reasoning Model Handling

Special behavior for models like `o1`, `o3-mini`, `kimi-k2-thinking`:
- Uses `max_completion_tokens` instead of `max_tokens`
- Temperature forced to `0.0`
- No system prompt (model uses built-in reasoning)

## Message History

- Maintains a rolling window of the last **50 messages**
- Roles: SYSTEM, USER, ASSISTANT, TOOL
- Supports base64 image content for vision
- Old messages are automatically truncated

## Retry Logic

Uses **Tenacity** for exponential backoff:
- Retries on rate limits and transient API errors
- Configurable retry count and delays

## Related
- [[Agent System]] - How agents use the LLM client
- [[Configuration]] - LLM config options
- [[Tech Stack]] - Provider details
