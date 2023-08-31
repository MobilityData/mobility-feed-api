data "google_project" "project" {}

provider "google" {
 region = var.gcp_region
}

locals {
  services = [
    "cloudscheduler.googleapis.com",
    "cloudfunctions.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "networkmanagement.googleapis.com",
    "cloudbuild.googleapis.com"
  ]
}

data "google_service_account" "ci_impersonator_service_account" {
  account_id = "ci-impersonator"
  project    = var.project_id
}

resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

resource "google_storage_bucket" "bucket" {
  name     = var.bucket_name
  location = var.gcp_region
}

resource "google_storage_bucket_object" "object" {
#  Workaround to force source code update of cloud function when the zip file hash is updated
  name            = "datasets/${filesha256("datasets.zip")}.zip" # TODO this should be a variable
  bucket          = google_storage_bucket.bucket.name
  source          = "datasets.zip" # TODO this should be a variable
  metadata        = {
    content_hash  = filebase64sha256("datasets.zip") # TODO this should be a variable
  }
}

resource "google_cloudfunctions2_function" "function" {
  name                    = "dataset-batch-function-v2" # TODO this should be a variable
  description             = "Python function"
  location                = "us-central1"
  build_config {
    runtime               = "python310" # TODO this should be a variable
    entry_point           = "batch_dataset" # TODO this should be a variable
    source {
      storage_source {
        bucket            = google_storage_bucket.bucket.name
        object            = google_storage_bucket_object.object.name
      }
    }
  }
  service_config {
    available_memory      = "512Mi"
    timeout_seconds       = 3600
    environment_variables = var.function_env_variables
    service_account_email =data.google_service_account.ci_impersonator_service_account.email
  }
}

resource "google_pubsub_topic" "default" {
  name = "functions2-topic"
}


resource "google_cloudfunctions2_function" "function2" {
  name                    = "dataset-function" # TODO this should be a variable
  description             = "Python function"
  location                = "us-central1"
  build_config {
    runtime               = "python310" # TODO this should be a variable
    entry_point           = "process_dataset" # TODO this should be a variable
    source {
      storage_source {
        bucket            = google_storage_bucket.bucket.name
        object            = google_storage_bucket_object.object.name
      }
    }
  }
  service_config {
    available_memory      = "512Mi"
    timeout_seconds       = 540
    environment_variables = var.function_env_variables
    service_account_email = data.google_service_account.ci_impersonator_service_account.email
  }
  event_trigger {
    trigger_region = "us-central1"
    service_account_email = data.google_service_account.ci_impersonator_service_account.email
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.default.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}

resource "google_cloud_scheduler_job" "job" {
  name                      = "dataset-batch-job" # TODO this should be a variable
  description               = "Run python function daily" # TODO this should be a variable
  schedule                  = "*/1 * * * *" # TODO this is once a day and should be a variable
  time_zone                 = "Etc/UTC"
  attempt_deadline          = "320s"

  http_target {
    http_method             = "GET"
    uri                     = google_cloudfunctions2_function.function.service_config[0].uri
    oidc_token {
      service_account_email = var.deployer_service_account
    }
  }
}