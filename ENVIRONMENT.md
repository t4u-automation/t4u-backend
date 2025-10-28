# Environment Variables

This document lists all required and optional environment variables for T4U Backend.

## 📋 Required Variables

### LLM Configuration

```bash
# Anthropic Claude API Key (Primary LLM)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
# Get from: https://console.anthropic.com/
```

### E2B Sandbox Configuration

```bash
# E2B API Key for sandbox management
E2B_API_KEY=e2b_your-api-key-here
# Get from: https://e2b.dev/docs/getting-started/api-key
```

### Firebase Configuration

```bash
# Path to Firebase service account JSON
FIREBASE_SERVICE_ACCOUNT_PATH=config/firebase-service-account.json
# Download from Firebase Console → Project Settings → Service Accounts

# Firebase Storage bucket for screenshots/artifacts
FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
# Find in Firebase Console → Storage
```

---

## 🔧 Optional Variables

### Alternative LLM

```bash
# Google Gemini API Key (optional alternative to Claude)
GOOGLE_API_KEY=your-google-api-key-here
# Get from: https://makersuite.google.com/app/apikey
```

### E2B Template

```bash
# Custom E2B template ID (optional - uses base if not set)
E2B_TEMPLATE_ID=97h12m86c734x32etx23
# Build with: cd e2b_template && e2b template build
```

### Server Configuration

```bash
# Server port (default: 8000)
PORT=8000

# Server host (default: 0.0.0.0)
HOST=0.0.0.0

# Environment name
ENVIRONMENT=development
# Options: development, staging, production
```

### Logging

```bash
# Log level
LOG_LEVEL=INFO
# Options: DEBUG, INFO, WARNING, ERROR

# Log file path (optional)
LOG_FILE=logs/app.log
```

### Session Limits

```bash
# Maximum concurrent agent sessions
MAX_CONCURRENT_SESSIONS=10

# Maximum steps per agent session
MAX_STEPS_PER_SESSION=50

# Session timeout in seconds
SESSION_TIMEOUT=3600
```

---

## ⚙️ Configuration Methods

T4U Backend supports multiple configuration methods (in priority order):

### 1. Environment Variables (Highest Priority)

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
export E2B_API_KEY=e2b_xxx
python api_server.py
```

### 2. config/config.toml File

```toml
[llm]
api_key = "sk-ant-xxx"
model = "claude-3-5-sonnet-20241022"

[e2b]
e2b_api_key = "e2b_xxx"
template = "base"

[firestore]
service_account_path = "config/firebase-service-account.json"
storage_bucket = "your-project.firebasestorage.app"
```

### 3. .env File (For Development)

Create `.env` in project root:
```bash
ANTHROPIC_API_KEY=sk-ant-xxx
E2B_API_KEY=e2b_xxx
FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
```

Load with python-dotenv:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 🔒 Security Notes

### DO NOT Commit

Never commit these files:
- `config/config.toml` (has API keys)
- `config/firebase-service-account.json` (credentials)
- `.env` or `.env.local` (secrets)
- Any `*.key` or `*.pem` files

### Safe to Commit

These example files are safe:
- `config/config.example-model-anthropic.toml` ✅
- `config/config.example-model-google.toml` ✅
- This documentation file ✅

### Google Cloud Run Secrets

For production, use Google Cloud Secret Manager:

```bash
# Create secret
echo -n "sk-ant-xxx" | gcloud secrets create anthropic-api-key --data-file=-

# Grant access to Cloud Run
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member=serviceAccount:PROJECT-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# Deploy with secret
gcloud run deploy testopsai-api \
  --set-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest
```

---

## 📝 Configuration File Examples

### config.toml (Development)

```toml
[llm]
model = "claude-3-5-sonnet-20241022"
base_url = "https://api.anthropic.com/v1"
api_key = "sk-ant-api03-xxx"
max_tokens = 4096
temperature = 1.0
api_type = "openai"

[e2b]
e2b_api_key = "e2b_xxx"
template = "97h12m86c734x32etx23"  # Or "base"
timeout = 300
cwd = "/home/user"

[firestore]
enabled = true
service_account_path = "config/firebase-service-account.json"
collection = "agent_steps"
storage_bucket = "testopsai.firebasestorage.app"
```

### config.toml (Production)

```toml
[llm]
model = "claude-3-5-sonnet-20241022"
base_url = "https://api.anthropic.com/v1"
# API key from environment variable
max_tokens = 4096
temperature = 0.7  # Lower for production consistency
api_type = "openai"

[llm.pricing]
input_price_low = 3.0
input_price_high = 6.0
output_price_low = 15.0
output_price_high = 22.5
tier_threshold = 200000

[e2b]
# API key from environment variable
template = "97h12m86c734x32etx23"  # Pre-built template
timeout = 600
cwd = "/home/user"

[firestore]
enabled = true
service_account_path = "config/firebase-service-account.json"
collection = "agent_steps"
storage_bucket = "your-project.firebasestorage.app"
```

---

## ✅ Validation Checklist

Before deploying:

- [ ] All API keys configured
- [ ] Firebase service account added
- [ ] Firebase Storage bucket exists
- [ ] E2B template built (or using base)
- [ ] config.toml has correct values
- [ ] .gitignore excludes secrets
- [ ] Tested locally
- [ ] Health endpoint responds

---

## 📞 Support

For configuration issues:
- Check logs: `gcloud run services logs read testopsai-api`
- Verify secrets: Ensure API keys are valid
- Test locally first: `python api_server.py`
- Open issue: https://github.com/t4u-automation/t4u-backend/issues

---

**Configuration complete!** 🎉

