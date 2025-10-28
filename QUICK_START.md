# T4U Backend - Quick Start Guide

Get up and running in 5 minutes!

---

## ⚡ Quick Setup

### 1. Clone & Install (2 min)

```bash
# Clone repository
git clone https://github.com/t4u-automation/t4u-backend.git
cd t4u-backend

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Get API Keys (5 min)

You need 3 API keys:

**Anthropic (Claude 3.5 Sonnet):**
- Sign up: https://console.anthropic.com/
- Get API key: https://console.anthropic.com/settings/keys
- Copy: `sk-ant-api03-...`

**E2B (Sandbox Platform):**
- Sign up: https://e2b.dev/
- Get API key: https://e2b.dev/docs/getting-started/api-key
- Copy: `e2b_...`

**Firebase (Database & Storage):**
- Create project: https://console.firebase.google.com/
- Enable Firestore Database
- Enable Storage
- Download service account:
  - Project Settings → Service Accounts → Generate New Private Key
  - Save as `config/firebase-service-account.json`

### 3. Configure (1 min)

```bash
# Copy example config
cp config/config.example-model-anthropic.toml config/config.toml

# Edit with your keys
nano config/config.toml
```

Update these values:
```toml
[llm]
api_key = "sk-ant-YOUR-KEY-HERE"

[e2b]
e2b_api_key = "e2b_YOUR-KEY-HERE"

[firestore]
storage_bucket = "your-project.firebasestorage.app"
```

### 4. Run (30 sec)

```bash
python api_server.py
```

Expected output:
```
✅ Firestore + Storage connected
🚀 TESTOPSAI API SERVER
📡 API: http://localhost:8000
📖 Docs: http://localhost:8000/docs
```

### 5. Test (1 min)

Open browser: http://localhost:8000/docs

Try the `/agent/start` endpoint with:
```json
{
  "prompt": "Navigate to https://example.com and verify the page title",
  "user_id": "test_user",
  "tenant_id": "test_tenant"
}
```

Watch the SSE stream for live updates!

---

## 🎯 Next Steps

### Build E2B Template (Optional but Recommended)

Reduces sandbox startup from 60s → 10s:

```bash
cd e2b_template
e2b template build

# Note the template ID (e.g., 97h12m86c734x32etx23)
# Update config.toml:
[e2b]
template = "97h12m86c734x32etx23"
```

See **E2B_TEMPLATE_SETUP.md** for details.

### Deploy to Production

```bash
# Deploy to Google Cloud Run
bash deploy.sh
```

See **DEPLOYMENT.md** for Cloud Run, Docker, and VPS options.

### Explore Features

**Test Creation:**
```bash
# Create a test by natural language
POST /agent/start
{
  "prompt": "Login to https://app.com with user@test.com and password secret123, then validate the dashboard is visible"
}
```

**Test Replay:**
```bash
# Replay saved test
POST /agent/replay/{tenant_id}/{test_case_id}
```

**Batch Testing:**
```bash
# Run multiple tests
POST /api/runs/execute
{
  "run_id": "run_123",
  "tenant_id": "org_456",
  "parallel": true
}
```

---

## 📚 Documentation

- **README.md** - Complete architecture and API reference
- **DEPLOYMENT.md** - Production deployment guide
- **E2B_TEMPLATE_SETUP.md** - Custom template setup
- **ENVIRONMENT.md** - All configuration options
- **CONTRIBUTING.md** - How to contribute

---

## 🆘 Troubleshooting

### "E2B sandbox timeout"

- Check E2B API key is valid
- Verify account has available quota
- Try using base template instead of custom

### "Firebase permission denied"

- Verify service account JSON is correct
- Check Firestore is enabled
- Ensure Storage bucket exists

### "LLM API error"

- Verify Anthropic API key
- Check account balance
- Reduce max_tokens if rate limited

### "Locator timeout"

- Element might not exist - use VNC to verify
- Try different locator (by_id instead of by_text)
- Check if page fully loaded

---

## 💡 Tips

### 1. Use Stable Locators

```python
# ✅ Good - stable across updates
click(by_role='button', has_text='Submit')
fill(by_placeholder='Email', text='...')

# ❌ Bad - breaks on DOM changes
click_element(index=0)
input_text(index=1, text='...')
```

### 2. Watch VNC During Development

Use the VNC URL to see exactly what the browser is doing.

### 3. Use Sub-Agents for Complex Tasks

```python
# Delegate login to sub-agent
e2b_sub_agent(
    task="Login with provided credentials and verify success",
    context="Currently on homepage"
)
```

### 4. Include Assertions

```python
# After actions, validate
assert_url_contains(expected_text='/dashboard')
assert_element_visible(search_text='News')
```

---

## 🎉 You're Ready!

Start building AI-powered tests:

```bash
python api_server.py
# Open http://localhost:8000/docs
```

**Questions?** Check the docs or open an issue!

---

**Happy testing!** 🚀

