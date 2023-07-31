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

locals {
  services = [
    "cloudresourcemanager.googleapis.com"
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
 project 		= var.project_id
 access_token	= data.google_service_account_access_token.default.access_token
 request_timeout 	= "60s"
}

module "artifact-registry" {
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment

  source = "./artifact-registry"
}

module "feed-api" {
  depends_on  = [module.artifact-registry]
  project_id  = var.project_id
  gcp_region  = var.gcp_region
  environment = var.environment

  docker_repository_name = module.artifact-registry.feed_repository_name
  feed_api_service = "feed-api"
  feed_api_image_version = var.feed_api_image_version

  source = "./feed-api"
}

module "postgresql" {
  source          = "./postgresql"
  instance_name   = var.postgresql_instance_name
  database_name   = var.postgresql_database_name
  user_name       = var.postgresql_user_name
  user_password   = var.postgresql_user_password
  region          = var.gcp_region
}