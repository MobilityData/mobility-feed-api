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
  name            = "${var.source_code_path}/${filesha256(var.source_code_zip_file)}.zip"
  bucket          = google_storage_bucket.bucket.name
  source          = var.source_code_zip_file
  metadata        = {
    content_hash  = filebase64sha256(var.source_code_zip_file)
  }
}

resource "google_cloudfunctions2_function" "http_function" {
  name                    = var.http_function_name
  description             = "Python function"
  location                = "us-central1"
  build_config {
    runtime               = var.runtime
    entry_point           = var.http_entry_point
    source {
      storage_source {
        bucket            = google_storage_bucket.bucket.name
        object            = google_storage_bucket_object.object.name
      }
    }
  }
  service_config {
    available_memory      = var.available_memory
    available_cpu         = "583m"
    timeout_seconds       = var.http_timeout_seconds
    environment_variables = var.function_env_variables
    service_account_email = data.google_service_account.ci_impersonator_service_account.email
  }
}

resource "google_pubsub_topic" "pubsub_topic" {
  count = var.create_pubsub_function ? 1 : 0
  name = var.pubsub_topic_name
}

resource "google_cloudfunctions2_function" "pubsub_function" {
  name                    = var.pubsub_function_name
  description             = "Batch processing function"
  location                = "us-central1"
  count = var.create_pubsub_function ? 1 : 0
  build_config {
    runtime               = var.runtime
    entry_point           = var.pubsub_entry_point
    source {
      storage_source {
        bucket            = google_storage_bucket.bucket.name
        object            = google_storage_bucket_object.object.name
      }
    }
  }
  service_config {
    available_memory      = var.available_memory
    timeout_seconds       = var.pubsub_timeout_seconds
    environment_variables = var.function_env_variables
    service_account_email = data.google_service_account.ci_impersonator_service_account.email
    max_instance_count    = var.max_instance_count
  }
  event_trigger {
    trigger_region        = "us-central1"
    service_account_email = data.google_service_account.ci_impersonator_service_account.email
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.pubsub_topic[0].id
    retry_policy          = "RETRY_POLICY_RETRY"
  }
}

resource "google_cloud_scheduler_job" "job" {
  name                     = var.job_name
  description              = var.job_description
  schedule                 = var.job_schedule
  time_zone                = "Etc/UTC"
  attempt_deadline         = var.job_attempt_deadline

  http_target {
    http_method            = var.http_method
    uri                    = google_cloudfunctions2_function.http_function.service_config[0].uri
    oidc_token {
      service_account_email = var.deployer_service_account
    }
  }
}
