#
# MobilityData 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Configure the backend section to match your configuration.
terraform {
  backend "gcs" {
  }
}

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

# All Google services should be placed at root level script.
# This is to avoid circular dependencies when updating and removing resources and services.
# If a particular Google API(service) should be removed, consider update the environments in multiple phases rather a single one as follow,
# - remove associated resources to the Google API from the TF script
# - apply changes
# - remove the the Google API from the service list
# Make sure all environments are updated in that order, this method should be applied in at least two independent PRs.
#
locals {
  services = [
    "sqladmin.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "apigateway.googleapis.com", # remove this service in the future after all envs remove api gw resources
    "servicemanagement.googleapis.com",
    "servicecontrol.googleapis.com",
    "compute.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "vpcaccess.googleapis.com",
    "workflows.googleapis.com",
    "cloudtasks.googleapis.com",
  ]
}

# Enabling google cloud services.
resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

provider "google" {
  project         = var.project_id
  access_token    = data.google_service_account_access_token.default.access_token
  request_timeout = "60s"
}

provider "google-beta" {
  project         = var.project_id
  access_token    = data.google_service_account_access_token.default.access_token
  request_timeout = "60s"
}

provider "external" {}

module "global" {
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment

  source = "./global"
}

module "feed-api" {
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment

  docker_repository_name = "${var.artifact_repo_name}-${var.environment}"
  feed_api_service       = "feed-api"
  feed_api_image_version = var.feed_api_image_version

  source = "./feed-api"
}


module "functions-python" {
  source = "./functions-python"
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment
  
  transitland_api_key = var.transitland_api_key
  operations_oauth2_client_id = var.operations_oauth2_client_id
  validator_endpoint = var.validator_endpoint
  tdg_api_token = var.tdg_api_token
}

module "workflows" {
  source = "./workflows"
  project_id         = var.project_id
  gcp_region         = var.gcp_region
  environment        = var.environment
  validator_endpoint = var.validator_endpoint
  processing_report_cloud_task_name = module.functions-python.processing_report_cloud_task_name
}

module "feed-api-load-balancer" {
  depends_on  = [module.feed-api, module.functions-python]
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment

  feed_api_name                    = module.feed-api.feed_api_name
  oauth2_client_id                 = var.oauth2_client_id
  oauth2_client_secret             = var.oauth2_client_secret
  global_rate_limit_req_per_minute = var.global_rate_limit_req_per_minute

  function_tokens_name = module.functions-python.function_tokens_name

  source = "./load-balancer"
}

module "metrics" {
  source = "./metrics"
  depends_on = [module.functions-python]
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment
}