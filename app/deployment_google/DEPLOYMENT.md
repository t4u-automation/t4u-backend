# Deployment Guide

This guide covers deploying T4U Backend to various environments.

## 🎯 Deployment Options

1. **Google Cloud Run** (Recommended for production)
2. **Docker** (Any cloud provider)
3. **Local/VPS** (Development/testing)

---

## ☁️ Google Cloud Run Deployment

### Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Firebase project** set up
4. **API Keys:**
   - Anthropic API key
   - E2B API key
   - Firebase service account

### Quick Deploy

```bash
# 1. Set your project
gcloud config set project YOUR_PROJECT_ID

# 2. Deploy (uses cloudbuild.yaml)
bash deploy.sh
```

### Manual Deploy Steps

#### 1. Prepare Configuration

```bash
# Copy example config
cp config/config.example-model-anthropic.toml config/config.toml

# Edit config.toml with your values:
# - API keys
# - E2B template ID
# - Firebase settings
```

#### 2. Add Firebase Service Account

```bash
# Download from Firebase Console:
# Project Settings → Service Accounts → Generate New Private Key

# Save as:
cp ~/Downloads/your-project-firebase-adminsdk.json config/firebase-service-account.json
```

#### 3. Deploy to Cloud Run

```bash
# Using Cloud Build (recommended)
gcloud builds submit --config cloudbuild.yaml

# Direct deploy (alternative)
gcloud run deploy testopsai-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 10
```

#### 4. Set Environment Variables (if not in config.toml)

```bash
gcloud run services update testopsai-api \
  --set-env-vars="E2B_API_KEY=e2b_xxx" \
  --set-env-vars="ANTHROPIC_API_KEY=sk-ant-xxx"
```

### Cloud Build Configuration

The `cloudbuild.yaml` handles:
- Building Docker image with dependencies
- Installing Playwright browsers
- Deploying to Cloud Run
- Setting up environment

**Build Time:** ~5-8 minutes

### Post-Deployment

#### 1. Get Service URL

```bash
gcloud run services describe testopsai-api --region us-central1 --format='value(status.url)'
```

#### 2. Test Health Endpoint

```bash
curl https://YOUR-SERVICE-URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "E2B Agent API"
}
```

#### 3. Update Frontend

Update your frontend to point to the new Cloud Run URL.

---

## 🐳 Docker Deployment

### Build Image

```bash
docker build -f Dockerfile.api -t t4u-backend:latest .
```

### Run Container

```bash
docker run -d \
  -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-xxx \
  -e E2B_API_KEY=e2b_xxx \
  -v $(pwd)/config:/app/config \
  --name t4u-backend \
  t4u-backend:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - E2B_API_KEY=${E2B_API_KEY}
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

---

## 🖥️ Local/VPS Deployment

### System Requirements

- **Ubuntu 20.04+** or similar Linux distribution
- **Python 3.13+**
- **4GB RAM** minimum
- **Port 8000** available

### Installation

```bash
# 1. Clone repository
git clone https://github.com/t4u-automation/t4u-backend.git
cd t4u-backend

# 2. Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp config/config.example-model-anthropic.toml config/config.toml
# Edit config.toml with your API keys

# 5. Add Firebase credentials
# Download and save to config/firebase-service-account.json

# 6. Run with systemd (production)
sudo cp deployment/t4u-backend.service /etc/systemd/system/
sudo systemctl enable t4u-backend
sudo systemctl start t4u-backend

# Or run directly (development)
python api_server.py
```

### systemd Service File

Create `/etc/systemd/system/t4u-backend.service`:

```ini
[Unit]
Description=T4U Backend API Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/t4u-backend
Environment="PATH=/home/ubuntu/t4u-backend/venv/bin"
ExecStart=/home/ubuntu/t4u-backend/venv/bin/python api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # SSE support
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
```

---

## 🔧 E2B Template Setup

### Building Custom Template

The E2B template includes pre-installed Playwright and desktop environment for faster startup.

```bash
# 1. Navigate to template directory
cd e2b_template

# 2. Build template (takes ~10 minutes)
e2b template build

# 3. Note the template ID
# Output: Built template 97h12m86c734x32etx23

# 4. Update config.toml
[e2b]
template = "97h12m86c734x32etx23"
```

### Template Contents

- **Base:** Ubuntu 22.04
- **Playwright:** Pre-installed with Chromium
- **Desktop:** Xvfb + Fluxbox + noVNC
- **VNC:** Port 6080
- **Browser:** Headless Chromium

### Updating Template

```bash
# Edit e2b_template/e2b.Dockerfile
# Add your dependencies

# Rebuild
cd e2b_template
e2b template build

# Use new template ID in config
```

---

## 🔍 Monitoring & Debugging

### Cloud Run Logs

```bash
# View recent logs
gcloud run services logs read testopsai-api --limit 50

# Stream logs
gcloud run services logs tail testopsai-api

# Filter by severity
gcloud run services logs read testopsai-api --log-filter="severity>=ERROR"
```

### Common Issues

#### 1. E2B Sandbox Timeout

**Symptom:** "Timeout creating E2B sandbox"

**Solutions:**
- Check E2B API key is valid
- Verify E2B account has available quota
- Check template exists and is built

#### 2. Firebase Permission Denied

**Symptom:** "Permission denied" when saving to Firestore

**Solutions:**
- Verify service account has Firestore permissions
- Check service account JSON is correct
- Ensure Firebase project ID matches

#### 3. LLM API Errors

**Symptom:** "API key invalid" or rate limit errors

**Solutions:**
- Verify Anthropic API key
- Check account balance/quota
- Reduce concurrent sessions

#### 4. Browser Locator Timeout

**Symptom:** "Locator timeout 10s exceeded"

**Solutions:**
- Element might not exist - check VNC
- Use more specific locator (by_id instead of by_text)
- Add wait before action if page loads slowly

---

## 📊 Performance Optimization

### Cloud Run Settings

For production workloads:

```bash
gcloud run services update testopsai-api \
  --memory 4Gi \
  --cpu 4 \
  --concurrency 10 \
  --max-instances 50 \
  --min-instances 1  # Keep warm
```

### Cost Optimization

- **E2B:** Sandboxes auto-cleanup after session (~$0.01-0.05 per session)
- **LLM:** Main cost - optimize prompts, use sub-agents
- **Cloud Run:** Scales to zero when idle
- **Firestore:** Read/write costs - batch updates when possible

---

## 🔄 Rolling Updates

### Zero-Downtime Deployment

Cloud Run handles this automatically:
1. New revision deployed
2. Traffic gradually shifted
3. Old revision kept for rollback

### Rollback

```bash
# List revisions
gcloud run revisions list --service testopsai-api

# Rollback to previous
gcloud run services update-traffic testopsai-api \
  --to-revisions=testopsai-api-00042-abc=100
```

---

## 📈 Scaling

### Horizontal Scaling

Cloud Run auto-scales based on:
- Concurrent requests
- CPU utilization
- Memory usage

Configure:
```bash
gcloud run services update testopsai-api \
  --min-instances 2 \
  --max-instances 100 \
  --concurrency 20
```

### Rate Limiting

Implement in `api_server.py`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/agent/start")
@limiter.limit("10/minute")  # 10 sessions per minute per IP
async def start_agent(...):
    ...
```

---

## 🔐 Security Best Practices

### API Security

1. **Authentication** - Add API key authentication
2. **Rate Limiting** - Prevent abuse
3. **Input Validation** - Sanitize all inputs
4. **CORS** - Configure allowed origins

### Secrets Management

**Google Cloud Secret Manager:**

```bash
# Store secrets
echo -n "sk-ant-xxx" | gcloud secrets create anthropic-api-key --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# Use in Cloud Run
gcloud run services update testopsai-api \
  --set-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest
```

---

## 📞 Support

For deployment issues:
- **GitHub Issues** - https://github.com/t4u-automation/t4u-backend/issues
- **Documentation** - Check README.md and this file
- **Logs** - Always include relevant logs when reporting issues

---

**Happy deploying!** 🚀

