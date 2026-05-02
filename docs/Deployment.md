# Deployment

## Docker

**Dockerfile.api** builds the API server for Google Cloud Run:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY api_server.py .
COPY config/ config/
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn api_server:app --host 0.0.0.0 --port $PORT
```

## Google Cloud Run

The production deployment uses:
- **Cloud Run** for serverless API hosting
- **ESPv2** for API gateway (optional)
- **Cloud Build** for CI/CD (`app/deployment_google/cloudbuild.yaml`)
- **Cloud Secret Manager** for API keys
- **Cloud Firestore** for database
- **Cloud Storage** for screenshots/artifacts

### Deploy Scripts

| Script | Purpose |
|---|---|
| `app/deployment_google/deploy.sh` | Production deployment |
| `app/deployment_google/deploy.local.sh` | Local testing |
| `app/deployment_google/cloudbuild.yaml` | CI/CD pipeline |

## E2B Custom Template

Located in `e2b_template/`. Provides **6x faster sandbox startup** by pre-installing:
- Python 3 + Playwright + Chromium
- Xvfb + Fluxbox + x11vnc (virtual desktop)
- Supervisor for process management
- All required Python packages

Standard sandbox startup: ~60-90s. Custom template: near-instant.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp config/config.example.toml config/config.toml
# Edit config.toml with your API keys

# Run
uvicorn api_server:app --reload --port 8000
```

## Related
- [[Configuration]] - Environment and config setup
- [[Architecture]] - System overview
