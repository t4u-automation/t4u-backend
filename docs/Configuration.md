# Configuration

## Priority Order

1. **Environment variables** (highest priority)
2. **`config/config.toml`** file
3. **`.env`** file (development)

Configuration is managed by `app/config.py`.

## LLM Settings

### Claude 3.5 Sonnet (Recommended)

```toml
[llm]
model = "claude-3-5-sonnet-20241022"
base_url = "https://api.anthropic.com/v1"
api_key = "sk-ant-..."
max_tokens = 4096
temperature = 1.0
api_type = "openai"

max_input_tokens = 1000000

[llm.pricing]
input_price_low = 3.0
input_price_high = 6.0
output_price_low = 15.0
output_price_high = 22.5
tier_threshold = 200000
```

### Kimi K2 Thinking

```toml
[llm]
model = "kimi-k2-thinking"
base_url = "https://api.moonshot.ai/v1/"
api_key = "sk-..."
max_tokens = 8192
temperature = 0.0
```

### Google Gemini

```toml
[llm]
model = "gemini-2.5-flash"
base_url = "https://generativelanguage.googleapis.com/v1beta/"
api_key = "..."
```

## E2B Sandbox

```toml
[e2b]
e2b_api_key = "e2b_..."
template = "base"          # or custom template ID for 6x faster startup
timeout = 300              # sandbox timeout in seconds
cwd = "/home/user"         # working directory inside sandbox
```

## Firebase

```toml
[firestore]
enabled = true
service_account_path = "config/firebase-service-account.json"
collection = "agent_steps"
storage_bucket = "your-project.firebasestorage.app"
```

## Related
- [[Tech Stack]] - What each component does
- [[LLM Integration]] - LLM-specific details
- [[Deployment]] - Production configuration
