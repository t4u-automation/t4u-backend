# E2B Sandbox Integration for TestOpsAI

E2B provides cloud-based sandboxes with **full unrestricted internet access** - a perfect alternative to Daytona's tier-restricted sandboxes.

## ✨ Key Benefits

- ✅ **Full Internet Access** - No tier restrictions, access any website
- ✅ **Fast Startup** - Firecracker VMs start in seconds
- ✅ **Browser Support** - Built-in Playwright for web automation
- ✅ **Cost Effective** - Generous free tier, then $0.05/hour
- ✅ **Easy to Use** - Similar API to Daytona

## 🚀 Quick Start

### 1. Get E2B API Key

Sign up and get your API key from: https://e2b.dev/docs

### 2. Configure TestOpsAI

Add to `config/config.toml`:

```toml
[e2b]
e2b_api_key = "e2b_your_api_key_here"
template = "base"
timeout = 300
cwd = "/home/user"
```

### 3. Test E2B

```bash
# Quick test
export E2B_API_KEY="your-api-key"
python e2b_simple_demo.py

# Full test
python e2b_test.py
```

### 4. Run E2B Agent

```bash
python e2b_main.py --prompt "Open yourhddev.web.app and login with test-dev-empl@incendi.io"
```

## 📚 Available Tools

### E2BShellTool (`e2b_shell`)

Execute shell commands with full internet access:

```python
{
    "action": "e2b_shell",
    "command": "curl https://example.com"
}
```

### E2BFilesTool (`e2b_files`)

File operations in sandbox:

```python
{
    "action": "e2b_files",
    "action": "write",
    "path": "/home/user/test.txt",
    "content": "Hello!"
}
```

### E2BBrowserTool (`e2b_browser`)

Browser automation with Playwright and **automatic screenshot capture**:

```python
{
    "action": "e2b_browser",
    "action": "navigate",
    "url": "https://example.com"
}
```

**✨ Screenshot & Highlighting Features:**

- 📸 **Auto-screenshots** before/after every action
- 🔴 **Red highlighting** of clicked elements
- 💾 **Dual storage**: E2B sandbox + local workspace
- 🖼️ **Live viewer** available at `e2b_viewer.py`

See `E2B_SCREENSHOT_GUIDE.md` for details.

## 🔄 Comparison: E2B vs Daytona

| Feature          | E2B                 | Daytona          |
| ---------------- | ------------------- | ---------------- |
| Internet Access  | ✅ Full (all tiers) | ⚠️ Tier 3+ only  |
| Startup Speed    | ⚡ 2-5 seconds      | 🐌 25-30 seconds |
| Browser Support  | ✅ Playwright       | ✅ Custom API    |
| VNC Access       | ❌ No               | ✅ Yes           |
| Cost (Free Tier) | ✅ Generous         | ✅ Limited       |
| Monthly Price    | $20 (100hrs)        | $10 (Tier 3)     |

## 📖 Learn More

- [E2B Documentation](https://e2b.dev/docs)
- [E2B Python SDK](https://github.com/e2b-dev/e2b)
- [E2B Pricing](https://e2b.dev/pricing)
