# ESPv2 Deployment Guide

## Prerequisites

Enable the following APIs for your project in the Google Cloud Endpoints page in the API Manager. Ignore any prompt to create credentials.

- [Cloud Endpoints API](https://console.cloud.google.com/apis/api/endpoints.googleapis.com/overview)
- [Cloud Service Management API](https://console.cloud.google.com/apis/api/servicemanagement.googleapis.com/overview)
- [Cloud Service Control API](https://console.cloud.google.com/apis/api/servicecontrol.googleapis.com/overview)
- [Artifact Registry API](https://console.cloud.google.com/apis/api/artifactregistry.googleapis.com/overview) (required for building custom ESPv2 images)

## Initial ESPv2 Deployment

Deploy the ESPv2 runtime as a Cloud Run service:

```bash
gcloud run deploy "t4u-api-esp" \
  --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \
  --allow-unauthenticated \
  --platform managed \
  --region us-central1 \
  --project="testopsai"
```

After deployment, Cloud Run will provide a service URL (e.g., `https://t4u-api-esp-1077634808665.us-central1.run.app`). **Save this URL** - you'll need it to update the `host` field in `espv2-run.yaml` in the next step.

**Optional:** You can add resource specifications if needed:
```bash
gcloud run deploy "t4u-api-esp" \
  --image="gcr.io/endpoints-release/endpoints-runtime-serverless:2" \
  --allow-unauthenticated \
  --platform managed \
  --region us-central1 \
  --project="testopsai" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600
```

## Deploy Service Configuration

After ESP was deployed, update the `espv2-run.yaml` file to include the updated ESP endpoint. **Note:** Every time you update the config, you need to deploy a new version.

```bash
gcloud endpoints services deploy espv2-run.yaml --project "testopsai"
```

## Enable Service

The service is automatically enabled during deployment. If you need to manually enable it:

```bash
gcloud services enable t4u-api-esp-1077634808665.us-central1.run.app
```

## Delete Service

To delete a service:

```bash
gcloud endpoints services delete t4u-api-esp-1077634808665.us-central1.run.app
```

## Configuration Variables

After deploying the service configuration, save these values from your deployment:

```bash
ENDPOINTS_SERVICE_CONFIG_ID=2025-10-30r0
ENDPOINTS_SERVICE_NAME=t4u-api-esp-1077634808665.us-central1.run.app
```

## Create Artifact Registry Repository

Before building the custom image, create an Artifact Registry repository to store the ESPv2 images:

```bash
gcloud artifacts repositories create esp2builds \
  --repository-format=docker \
  --location=us-central1 \
  --project=testopsai \
  --description="ESPv2 custom images with embedded service config"
```

**Note:** If the repository already exists, you can skip this step.

## Build Custom Image with Service Config

Build the image and embed the service config. The image will be pushed to Artifact Registry:

```bash
chmod +x gcloud_build_image_espv2.sh
./gcloud_build_image_espv2.sh \
  -s "${ENDPOINTS_SERVICE_NAME}" \
  -c "${ENDPOINTS_SERVICE_CONFIG_ID}" \
  -p "testopsai" \
  -g "us-central1-docker.pkg.dev/testopsai/esp2builds"
```

### Saved Image Reference

After building, save the image reference (replace with actual image name from build output):

```bash
IMAGE=us-central1-docker.pkg.dev/testopsai/esp2builds/endpoints-runtime-serverless:<ESP_VERSION>-${ENDPOINTS_SERVICE_NAME}-${ENDPOINTS_SERVICE_CONFIG_ID}
```

## Redeploy with Updated Config

Redeploy the ESPv2 service with the updated image containing the embedded config:

```bash
gcloud run deploy "t4u-api-esp" \
  --image="${IMAGE}" \
  --allow-unauthenticated \
  --platform managed \
  --region us-central1 \
  --project="testopsai"
```
