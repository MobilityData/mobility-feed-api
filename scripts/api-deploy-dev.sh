
# This script used the docker-build-push.sh to deploy the API the a developers DEV environment 
# This needs a configuration file named .deploy-env-dev
# 
# Usage:
#   api-deploy-dev.sh <name-suffix>
# parameters:
#   name-suffix: [optional] prefix of the cloud run function to be created. The full name will be: developer-feed-api-<name-prefix>
# The cloud run created in dev will be named:
#   - developer-feed-api-<<name-suffix>>
# If name-suffix is not passed then the default name applies: 
#   - developer-feed-api-dev

# Relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"

# Load config file
CONFIG_FILE="$SCRIPT_PATH/.deploy-env-dev"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
else
  echo "Configuration file $CONFIG_FILE not found."
  exit 1
fi

DOCKER_IMAGE_VERSION=local-developper-$(date +%s)
SERVICE_NAME_SUFFIX=${1:-dev}
CLOUD_RUN_SERVICE_NAME=developer-feed-api-$SERVICE_NAME_SUFFIX
ARTIFACT_REGISTRY_URL=$REGION-docker.pkg.dev/$PROJECT_ID
ARTIFACT_REPO=feeds-dev

# Build and push the image
"$SCRIPT_PATH/docker-build-push.sh" -project_id "$PROJECT_ID" -repo_name "$ARTIFACT_REPO" -service "$CLOUD_RUN_SERVICE_NAME" -region "$REGION" -version "$DOCKER_IMAGE_VERSION"

# Deploy the container to Cloud Run
gcloud run deploy "$CLOUD_RUN_SERVICE_NAME" \
  --image "$ARTIFACT_REGISTRY_URL/$ARTIFACT_REPO/$CLOUD_RUN_SERVICE_NAME:$DOCKER_IMAGE_VERSION" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --project "$PROJECT_ID" \
  --service-account "$SERVICE_ACCOUNT_EMAIL" \
  --update-secrets "$SECRETS" \
  --vpc-connector "$VPC_CONNECTOR" \
  --vpc-egress "all"
