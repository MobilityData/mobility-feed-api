#!/bin/bash

# Ensure the script exits if any command fails
set -e

# relative path
SCRIPT_PATH="$(dirname -- "${BASH_SOURCE[0]}")"
FUNCTIONS_PATH="$SCRIPT_PATH/../functions-python"

# Function to display usage
usage() {
  echo "Usage: $0 <function-name> [--build] [--help]"
  echo "  <function-name>  Name of the function to deploy"
  echo "  --build          Optional flag to build the function before deploying"
  echo "  --help           Display this help message"
  exit 1
}

# defaults
FUNCTION_NAME=""
BUILD_FUNCTION=false
LOCAL_ENV_FILE=".env.local"

# Parse parameters
while [[ $# -gt 0 ]]; do
  case $1 in
    --help)
      usage
      ;;
    --build)
      BUILD_FUNCTION=true
      shift
      ;;
    *)
      if [ -z "$FUNCTION_NAME" ]; then
        FUNCTION_NAME=$1
      else
        echo "Unknown parameter: $1"
        usage
      fi
      shift
      ;;
  esac
done

# Check if function name is provided
if [ -z "$FUNCTION_NAME" ]; then
  usage
fi

# Read configuration from function_config.json
CONFIG_FILE="$FUNCTIONS_PATH/$FUNCTION_NAME/function_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Configuration file $CONFIG_FILE not found!"
  exit 1
fi

RUNTIME=python311
SOURCE=$FUNCTIONS_PATH/$FUNCTION_NAME/.dist/build
ENVIRONMENT=dev
PROJECT=mobility-feeds-$ENVIRONMENT
SERVICE_ACCOUNT=functions-service-account@mobility-feeds-$ENVIRONMENT.iam.gserviceaccount.com
ENVIRONMENT_UPPER=$(echo "$ENVIRONMENT" | tr '[:lower:]' '[:upper:]')

if [ ! -d "$SOURCE" ]; then
  echo "Function distribution folder found in $SOURCE. Building function..."
  BUILD_FUNCTION=true
fi

ENTRY_POINT=$(jq -r '.entry_point // empty' "$CONFIG_FILE")
TIMEOUT=$(jq -r '.timeout // empty' "$CONFIG_FILE")
MEMORY=$(jq -r '.memory // empty' "$CONFIG_FILE")
TRIGGER_HTTP=$(jq -r '.trigger_http // empty' "$CONFIG_FILE")
SECRET_ENV_VARS=$(jq -r '.secret_environment_variables | map("--set-secrets \(.key)=projects/'$PROJECT'/secrets/'$ENVIRONMENT_UPPER'_\(.key)/versions/latest") | join(" ") // empty' "$CONFIG_FILE")
INGRESS_SETTINGS=$(jq -r '.ingress_settings // empty' "$CONFIG_FILE")
MAX_CONCURRENCY=$(jq -r '.max_instance_request_concurrency // empty' "$CONFIG_FILE")
MAX_INSTANCES=$(jq -r '.max_instance_count // empty' "$CONFIG_FILE")
MIN_INSTANCES=$(jq -r '.min_instance_count // empty' "$CONFIG_FILE")
AVAILABLE_CPU=$(jq -r '.available_cpu // empty' "$CONFIG_FILE")

if [ -z "$RUNTIME" ] || [ -z "$ENTRY_POINT" ]; then
  echo "Invalid configuration in $CONFIG_FILE"
  exit 1
fi

# Function to read environment variables from LOCAL_ENV_FILE
read_env_vars() {
  if [ -f "$FUNCTIONS_PATH/$FUNCTION_NAME/$LOCAL_ENV_FILE" ]; then
    export $(grep -v '^#' "$FUNCTIONS_PATH/$FUNCTION_NAME/$LOCAL_ENV_FILE" | xargs)
  fi
}

# Read environment variables from LOCAL_ENV_FILE
read_env_vars

# Grant the Cloud Function's service account access to each secret
SECRETS=$(jq -r '.secret_environment_variables[].key' "$CONFIG_FILE")

for SECRET_NAME in $SECRETS; do
  gcloud secrets add-iam-policy-binding ${ENVIRONMENT_UPPER}_$SECRET_NAME \
    --project 978785769226 \
    --member "serviceAccount:$SERVICE_ACCOUNT" \
    --role "roles/secretmanager.secretAccessor"
done

# Run the build script if the --build flag is provided
if [ "$BUILD_FUNCTION" = true ]; then
  $SCRIPT_PATH/function-python-build.sh --function_name $FUNCTION_NAME
fi

# Prepare environment variables from function_config.json
ENV_VARS=""
printf "Environment variables\n"
while IFS= read -r line; do
  KEY=$(echo $line | jq -r '.key')
  ENV_VAR_NAME=$(echo "$line" | jq -r '.[keys[0]]')
  ENV_VAR_VALUE=$(printenv "$ENV_VAR_NAME")
  printf "  $KEY=$ENV_VAR_VALUE\n"
  if [ -n "$ENV_VAR_VALUE" ]; then
    ENV_VARS="$ENV_VARS --set-env-vars $KEY=$ENV_VAR_VALUE"
  fi
done < <(jq -c '.environment_variables[]' "$CONFIG_FILE")

# Deploy the function
DEPLOY_CMD="gcloud functions deploy $FUNCTION_NAME --gen2 --project $PROJECT --region northamerica-northeast1 --runtime $RUNTIME --entry-point $ENTRY_POINT --source $SOURCE --service-account $SERVICE_ACCOUNT"

[ -n "$TIMEOUT" ] && DEPLOY_CMD="$DEPLOY_CMD --timeout $TIMEOUT"
[ -n "$MEMORY" ] && DEPLOY_CMD="$DEPLOY_CMD --memory $MEMORY"
[ -n "$INGRESS_SETTINGS" ] && DEPLOY_CMD="$DEPLOY_CMD --ingress-settings $INGRESS_SETTINGS"
[ -n "$MAX_INSTANCES" ] && DEPLOY_CMD="$DEPLOY_CMD --max-instances $MAX_INSTANCES"
[ -n "$MIN_INSTANCES" ] && DEPLOY_CMD="$DEPLOY_CMD --min-instances $MIN_INSTANCES"
[ -n "$MAX_CONCURRENCY" ] && DEPLOY_CMD="$DEPLOY_CMD --concurrency $MAX_CONCURRENCY"
[ -n "$AVAILABLE_CPU" ] && DEPLOY_CMD="$DEPLOY_CMD --cpu $AVAILABLE_CPU"
[ -n "$SECRET_ENV_VARS" ] && DEPLOY_CMD="$DEPLOY_CMD $SECRET_ENV_VARS"
[ -n "$ENV_VARS" ] && DEPLOY_CMD="$DEPLOY_CMD $ENV_VARS"

if [ "$TRIGGER_HTTP" = true ]; then
  DEPLOY_CMD="$DEPLOY_CMD --trigger-http --allow-unauthenticated"
else
  echo "HTTP trigger not supported for $FUNCTION_NAME"
fi

# Execute the deploy command
eval $DEPLOY_CMD

echo "Deployment of $FUNCTION_NAME complete."