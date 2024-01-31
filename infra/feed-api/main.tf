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

# This script deploys the Feed API cloud run service.
# The cloud run service is created with name: mobility-feed-api-${var.environment}
# Module output:
#   feed_api_uri: Main URI of the Feed API

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

locals {
  env = {
    "FEEDS_DATABASE_URL" = {
      secret_id = "${var.environment}_FEEDS_DATABASE_URL"
    }
  }
}

# Service account to execute the cloud run service
resource "google_service_account" "containers_service_account" {
  account_id   = "containers-service-account"
  display_name = "Containers Service Account"
}

# Mobility Feed API cloud run service instance.
resource "google_cloud_run_v2_service" "mobility-feed-api" {
  name     = "mobility-feed-api-${var.environment}"
  location = var.gcp_region
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.containers_service_account.email
    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_name}/${var.feed_api_service}:${var.feed_api_image_version}"
      env {
        name = "FEEDS_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret = "${upper(var.environment)}_FEEDS_DATABASE_URL"
            version = "latest"
          }
        }
      }
      env {
        name = "SHOULD_CLOSE_DB_SESSION"
        value = "false"
      }
    }
  }
}

# Remove authentication from API endpoints
data "google_iam_policy" "noauth" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location = google_cloud_run_v2_service.mobility-feed-api.location
  project  = google_cloud_run_v2_service.mobility-feed-api.project
  service  = google_cloud_run_v2_service.mobility-feed-api.name

  policy_data = data.google_iam_policy.noauth.policy_data
}

resource "google_secret_manager_secret_iam_member" "policy" {
  for_each = local.env

  project = var.project_id
  secret_id = "${upper(var.environment)}_${each.key}"
  role = "roles/secretmanager.secretAccessor"
  member =  "serviceAccount:${google_service_account.containers_service_account.email}"
}

resource "github_actions_secret" "feeds_auth_token" {
  repository       = "mobility-feed-api"
  secret_name      = "FEEDS_AUTH_TOKEN"
  plaintext_value  = "your-auth-token"
}

output "feed_api_uri" {
  value       = google_cloud_run_v2_service.mobility-feed-api.uri
  description = "Main URI of the Feed API"
}

output "feed_api_name" {
  value       = google_cloud_run_v2_service.mobility-feed-api.name
  description = "Main URI of the Feed API"
}