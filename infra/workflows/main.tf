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

locals {
  function_reverse_geolocation_populate_config = jsondecode(file("${path.module}/../../functions-python/reverse_geolocation_populate/function_config.json"))
}

# Service account to execute the workflow
resource "google_service_account" "workflows_service_account" {
  account_id   = "workflows-service-account"
  display_name = "Workflows Service Account"
  project = var.project_id
}

# Grant permissions to the service account
resource "google_storage_bucket_iam_member" "object_user" {
  bucket  = "${var.datasets_bucket_name}-${var.environment}"
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_storage_bucket_iam_member" "object_getter" {
  bucket  = var.reports_bucket_name
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

# This permission is added to allow the workflow to act as the service account and generate tokens.
# This is required for the workflow to call a cloud tasks that generates a token to call the a cloud run service or function.
resource "google_project_iam_member" "service_account_workflow_act_as_binding" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser" #iam.serviceAccounts.actAs
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "service_account_workflow_cloudtasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

resource "google_project_iam_member" "service_account_workflow_cloudtasks_viewer" {
  project = var.project_id
  role    = "roles/cloudtasks.viewer"
  member  = "serviceAccount:${google_service_account.workflows_service_account.email}"
}

# Workflow to execute the GTFS Validator
resource "google_workflows_workflow" "gtfs_validator_execution" {
  name                    = "gtfs_validator_execution"
  region                  = var.gcp_region
  project                 = var.project_id
  description             = "Execute GTFS Validator"
  service_account         = google_service_account.workflows_service_account.id
  user_env_vars = {
    datasets_bucket_name  = "${var.datasets_bucket_name}-${var.environment}"
    reports_bucket_name   = lower(var.environment) == "prod" ? var.reports_bucket_name : "stg-${var.reports_bucket_name}"
    validator_endpoint    = var.validator_endpoint
    environment           = lower(var.environment)
    processing_report_cloud_task_name       = var.processing_report_cloud_task_name
  }
  source_contents         = file("${path.module}../../../workflows/gtfs_validator_execution.yml")
}

# Trigger to execute the GTFS Validator
# Trigger 1: Trigger the workflow when a new GTFS dataset is uploaded to the datasets bucket
resource "google_eventarc_trigger" "gtfs_validator_trigger" {
  name     = "gtfsvalidatortrigger"
  project  = var.project_id
  location = google_workflows_workflow.gtfs_validator_execution.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.audit.log.v1.written"
  }
  matching_criteria {
    attribute = "methodName"
    value = "storage.objects.create"
  }
  matching_criteria {
    attribute = "serviceName"
    value = "storage.googleapis.com"
  }
  matching_criteria {
    attribute = "resourceName"
    value     = "projects/_/buckets/${var.datasets_bucket_name}-${var.environment}/objects/*/*/*.zip"
    operator = "match-path-pattern"
  }

  # Send events to Workflows
  destination {
    workflow = google_workflows_workflow.gtfs_validator_execution.id
  }

  service_account = google_service_account.workflows_service_account.email

}


# Workflow to populate the db with all countries for reverse geocoding
resource "google_workflows_workflow" "reverse_geocoding_population" {
  name                    = "reverse_geolocation_populate"
  region                  = var.gcp_region
  project                 = var.project_id
  description             = "Populate the database with all countries for reverse geocoding"
  service_account         = google_service_account.workflows_service_account.id
  user_env_vars = {
    reverse_geolocation_populate_url  = "https://${var.gcp_region}-${var.project_id}.cloudfunctions.net/${local.function_reverse_geolocation_populate_config.name}"
    batch_size                        = 5
  }
  source_contents         = file("${path.module}../../../workflows/reverse_geolocation_populate.yml")
}


