#
# MobilityData 2024
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

# This script deploys the MCP Server cloud run service.
# The cloud run service is created with name: mcp-server-${var.environment}
# Module output:
#   mcp_server_uri: URI of the MCP Server Cloud Run service

data "google_project" "project" {}

locals {
  vpc_connector_name    = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id

  service_account_roles = [
    # Cloud Logging: allows writing logs to GCP
    "roles/logging.logWriter",
    # Cloud Trace: allows writing trace and span data
    "roles/cloudtrace.agent",
    # Cloud Monitoring: allows publishing custom metrics
    "roles/monitoring.metricWriter",
    # Serverless VPC Access: required to use a VPC connector
    "roles/vpcaccess.user",
  ]

  service_account_role_bindings = {
    for role in local.service_account_roles :
    "${role}" => {
      role    = role
      project = var.project_id
    }
  }
}

data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

resource "google_service_account" "mcp_service_account" {
  account_id   = "mcp-service-account"
  display_name = "MCP Server Service Account"
}

resource "google_cloud_run_v2_service" "mcp_server" {
  name     = "mcp-server-${var.environment}"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.mcp_service_account.email

    # Use annotations for max instances on older provider(<6.0.0)
    annotations = {
      "run.googleapis.com/max-instances" = "10"
    }

    vpc_access {
      connector = data.google_vpc_access_connector.vpc_connector.id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.project_id}/${var.docker_repository_name}/mcp-server:${var.mcp_image_version}"

      env {
        name = "FEEDS_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = "${upper(var.environment)}_FEEDS_DATABASE_URL"
            version = "latest"
          }
        }
      }

      env {
        name  = "DATASETS_BUCKET_URL"
        value = "https://storage.googleapis.com/mobilitydata-datasets-${lower(var.environment)}"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

data "google_iam_policy" "noauth" {
  binding {
    role    = "roles/run.invoker"
    members = ["allUsers"]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location    = google_cloud_run_v2_service.mcp_server.location
  project     = google_cloud_run_v2_service.mcp_server.project
  service     = google_cloud_run_v2_service.mcp_server.name
  policy_data = data.google_iam_policy.noauth.policy_data
}

resource "google_secret_manager_secret_iam_member" "feeds_db_url_access" {
  project   = var.project_id
  secret_id = "${upper(var.environment)}_FEEDS_DATABASE_URL"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp_service_account.email}"
}

resource "google_project_iam_member" "mcp_service_account_roles" {
  for_each = local.service_account_role_bindings

  project = each.value.project
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.mcp_service_account.email}"
}

output "mcp_server_uri" {
  value       = google_cloud_run_v2_service.mcp_server.uri
  description = "URI of the MCP Server Cloud Run service"
}

output "mcp_server_name" {
  value       = google_cloud_run_v2_service.mcp_server.name
  description = "Name of the MCP Server Cloud Run service"
}
