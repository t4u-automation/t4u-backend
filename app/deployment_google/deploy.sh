#!/bin/bash
# Deploy TestOpsAI API to Google Cloud Run using Cloud Build

set -e

echo "============================================================"
echo "🚀 Deploying TestOpsAI API to Google Cloud Run"
echo "============================================================"
echo ""

# Configuration
PROJECT_ID="testopsai"
REGION="us-central1"
SERVICE_NAME="testopsai-api"
E2B_API_KEY="your-e2b-api-key-here"  # Get from https://e2b.dev
ANTHROPIC_API_KEY="your-anthropic-api-key-here"  # Get from https://console.anthropic.com/

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Not logged in to gcloud. Run: gcloud auth login"
    exit 1
fi

# Set project
echo "📦 Setting project: ${PROJECT_ID}"
gcloud config set project ${PROJECT_ID}

# Submit build to Cloud Build (builds in Google Cloud, no local Docker needed!)
echo ""
echo "🔨 Submitting build to Cloud Build..."
echo "   (Building in Google Cloud - no local Docker required)"
# Get the script's directory and go to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}/../.."
gcloud builds submit \
  --config app/deployment_google/cloudbuild.yaml \
  --substitutions _E2B_API_KEY="${E2B_API_KEY}",_ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo "============================================================"
echo "✅ Deployment Complete!"
echo "============================================================"
echo ""
echo "📡 API URL: ${SERVICE_URL}"
echo "📖 Docs: ${SERVICE_URL}/docs"
echo ""
echo "Test with:"
echo "  curl -N -X POST ${SERVICE_URL}/agent/start \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"prompt\":\"Navigate to example.com\", \"user_id\":\"test_user\"}'"
echo ""
echo "Replay a session:"
echo "  curl -N -X POST ${SERVICE_URL}/agent/replay/SESSION_ID"
echo ""
echo "============================================================"

