terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.34.0"
    }
  }
}
#
# MobilityData 2026
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

# This script deploys the Garage API cloud function and the resources only it uses: its own service
# account and the private bucket holding users' datasets.
# The function sits behind the load balancer at /v1/garage (see infra/load-balancer).
# Module output:
#   function_garage_api_name: Name of the Garage API cloud function

locals {
  function_garage_api_config = jsondecode(file("${path.module}/../../functions-python/garage_api/function_config.json"))
  function_garage_api_zip    = "${path.module}/../../functions-python/garage_api/.dist/garage_api.zip"

  #  DEV and QA use the vpc connector
  vpc_connector_name    = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id

  garage_web_origins = [for origin in split(",", var.garage_web_origins) : trimspace(origin) if trimspace(origin) != ""]

  service_account_roles = [
    # Cloud Logging: allows writing logs to GCP
    "roles/logging.logWriter",
    # Serverless VPC Access: required to reach the users database through the VPC connector
    "roles/vpcaccess.user"
  ]
}

data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

# Service account the Garage API runs as. It is kept separate from the other functions' account so
# it can sign URLs, and read and write objects, for the Garage bucket only.
resource "google_service_account" "garage_service_account" {
  account_id   = "garage-service-account"
  display_name = "Garage API Service Account"
}

resource "google_project_iam_member" "garage_service_account_roles" {
  for_each = toset(local.service_account_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.garage_service_account.email}"
}

# Signed URLs are signed through the IAM signBlob API as the account itself, so no key is needed.
# The grant is on the account itself only: it cannot sign as any other account.
resource "google_service_account_iam_member" "garage_service_account_self_token_creator" {
  service_account_id = google_service_account.garage_service_account.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.garage_service_account.email}"
}

resource "google_secret_manager_secret_iam_member" "garage_secret_access" {
  for_each = { for secret in local.function_garage_api_config.secret_environment_variables : secret.key => secret }

  project   = var.project_id
  secret_id = "${upper(var.environment)}_${each.key}"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.garage_service_account.email}"
}

# Private bucket holding users' uploaded files and their Parquet conversions.
# Nothing in it is public: uploads and reads go through URLs signed by the Garage API.
resource "google_storage_bucket" "garage_bucket" {
  name                        = "mobilitydatabase-garage-${var.environment}"
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # The web app uploads to and reads from signed URLs directly from the browser.
  cors {
    origin          = local.garage_web_origins
    method          = ["GET", "HEAD", "PUT"]
    response_header = ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag"]
    max_age_seconds = 3600
  }

  # Drop multipart uploads that were started and never finished.
  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }

  # Uploaded source files are only needed until they are converted. Anything left under uploads/
  # after a week belongs to an upload that was never completed, or was not cleaned up after conversion.
  lifecycle_rule {
    condition {
      age            = 7
      matches_prefix = ["uploads/"]
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "garage_bucket_garage_service_account" {
  bucket = google_storage_bucket.garage_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.garage_service_account.email}"
}

resource "google_storage_bucket_object" "garage_api_zip" {
  bucket = var.functions_bucket_name
  name   = "garage-api-${substr(filebase64sha256(local.function_garage_api_zip), 0, 10)}.zip"
  source = local.function_garage_api_zip
}

resource "google_cloudfunctions2_function" "garage_api" {
  name        = local.function_garage_api_config.name
  description = local.function_garage_api_config.description
  location    = var.gcp_region
  depends_on  = [google_secret_manager_secret_iam_member.garage_secret_access]

  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_garage_api_config.entry_point
    source {
      storage_source {
        bucket = var.functions_bucket_name
        object = google_storage_bucket_object.garage_api_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      ENVIRONMENT          = var.environment
      PROJECT_ID           = var.project_id
      GCP_REGION           = var.gcp_region
      PYTHONNODEBUGRANGES  = 0
      CORS_ALLOWED_ORIGINS = join(",", local.garage_web_origins)
      GARAGE_BUCKET_NAME   = google_storage_bucket.garage_bucket.name
    }
    available_memory                 = local.function_garage_api_config.memory
    timeout_seconds                  = local.function_garage_api_config.timeout
    available_cpu                    = local.function_garage_api_config.available_cpu
    max_instance_request_concurrency = local.function_garage_api_config.max_instance_request_concurrency
    max_instance_count               = local.function_garage_api_config.max_instance_count
    min_instance_count               = local.function_garage_api_config.min_instance_count
    service_account_email            = google_service_account.garage_service_account.email
    ingress_settings                 = local.function_garage_api_config.ingress_settings
    vpc_connector                    = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings    = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_garage_api_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# The function only accepts traffic from the load balancer (ingress ALLOW_INTERNAL_AND_GCLB), where IAP
# checks the MDB token. The function then checks the token's user holds the user datasets feature flag.
resource "google_cloudfunctions2_function_iam_member" "garage_api_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.garage_api.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

resource "google_cloud_run_service_iam_member" "garage_api_cloud_run_invoker" {
  project  = var.project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.garage_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "function_garage_api_name" {
  value       = google_cloudfunctions2_function.garage_api.name
  description = "Name of the Garage API cloud function"
}

output "garage_bucket_name" {
  value       = google_storage_bucket.garage_bucket.name
  description = "Name of the private bucket holding users' Garage datasets"
}
