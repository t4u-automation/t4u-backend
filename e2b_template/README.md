# E2B Custom Template

This template has all dependencies pre-installed so sandboxes start instantly without installation delays.

## What's Included

- ✅ tmux (session management)
- ✅ Xvfb (virtual display)
- ✅ x11vnc (VNC server)
- ✅ Fluxbox (window manager)
- ✅ Python 3 + pip
- ✅ Playwright + Chromium browser
- ✅ Desktop auto-starts on container launch

## How to Build and Use

### 1. Install E2B CLI

```bash
npm install -g @e2b/cli
```

### 2. Login to E2B

```bash
e2b login
```

### 3. Build Template

```bash
cd e2b_template
e2b template build
```

This will build and push your template to E2B. You'll get a template ID like `your-template-id`.

### 4. Update Config

Edit `config/config.toml`:

```toml
[e2b]
e2b_api_key = "your-key"
template = "your-template-id"  # Use your custom template
timeout = 300
cwd = "/home/user"
```

### 5. Run

```bash
python e2b_main.py --prompt "Your task"
```

Now sandboxes will start **instantly** with everything pre-installed!

## Benefits

- ⚡ **Instant startup** - No 60-90 second install wait
- ✅ **Desktop pre-configured** - VNC and X11 ready immediately
- ✅ **Playwright ready** - Browser already installed
- 💰 **Cost effective** - Installation time doesn't count against usage

## Alternative: Use Existing E2B Templates

E2B also offers pre-built templates:

- `base` - Minimal Debian (current, requires install)
- `python` - Python environment pre-installed
- `node` - Node.js environment
- `code-interpreter` - Jupyter + data science libs

Check available templates:

```bash
e2b template list
```
