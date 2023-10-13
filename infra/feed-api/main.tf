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
    "POSTGRES_DB" = {
      secret_id   = "${var.environment}_POSTGRES_DB",
      secret_data = var.feed_api_postgres_db
    },
    "POSTGRES_HOST" = {
      secret_id   = "${var.environment}_POSTGRES_HOST",
      secret_data = var.feed_api_postgres_host
    },
    "POSTGRES_PASSWORD" = {
      secret_id   = "${var.environment}_POSTGRES_PASSWORD"
      secret_data = var.feed_api_postgres_password
    },
    "POSTGRES_PORT" = {
      secret_id   = "${var.environment}_POSTGRES_PORT"
      secret_data = var.feed_api_postgres_port
    }
    "POSTGRES_USER" = {
      secret_id   = "${var.environment}_POSTGRES_USER"
      secret_data = var.feed_api_postgres_user
    }
  }
}

resource "google_secret_manager_secret" "secret" {
  for_each = local.env

  project   = var.project_id
  secret_id = each.value.secret_id
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "secret_version" {
  for_each = local.env

  secret = google_secret_manager_secret.secret[each.key].id
  secret_data = each.value.secret_data
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
        name = "POSTGRES_DB"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.secret["POSTGRES_DB"].id
            version = "latest"
          }
        }
      }
      env {
        name = "POSTGRES_HOST"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.secret["POSTGRES_HOST"].id
            version = "latest"
          }
        }
      }
      env {
        name = "POSTGRES_PASSWORD"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.secret["POSTGRES_PASSWORD"].id
            version = "latest"
          }
        }
      }
      env {
        name = "POSTGRES_PORT"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.secret["POSTGRES_PORT"].id
            version = "latest"
          }
        }
      }
      env {
        name = "POSTGRES_USER"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.secret["POSTGRES_USER"].id
            version = "latest"
          }
        }
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

data "google_iam_policy" "secret_access" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.containers_service_account.email}"
    ]
  }
}

resource "google_secret_manager_secret_iam_policy" "policy" {
  for_each = local.env

  project = var.project_id
  secret_id = google_secret_manager_secret.secret[each.key].id
  policy_data = data.google_iam_policy.secret_access.policy_data
}

output "feed_api_uri" {
  value       = google_cloud_run_v2_service.mobility-feed-api.uri
  description = "Main URI of the Feed API"
}

output "feed_api_name" {
  value       = google_cloud_run_v2_service.mobility-feed-api.name
  description = "Main URI of the Feed API"
}