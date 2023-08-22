data "google_project" "project" {}

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
  name   = "batch_processing/datasets.zip" # TODO this should be a variable
  bucket = google_storage_bucket.bucket.name
  source = "datasets.zip" # TODO this should be a variable
}

resource "google_cloudfunctions_function" "function" {
  name        = "dataset-batch-function" # TODO this should be a variable
  description = "Python function"
  runtime     = "python39" # TODO this should be a variable

  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.bucket.name
  source_archive_object = google_storage_bucket_object.object.name
  entry_point           = "batch_dataset" # TODO this should be a variable
  trigger_http          = true
  triggers = {
    source_code_hash = filebase64sha256(google_storage_bucket_object.object.source)
  }
}

resource "google_cloud_scheduler_job" "job" {
  name             = "dataset-batch-job" # TODO this should be a variable
  description      = "Run python function daily" # TODO this should be a variable
  schedule         = "*/1 * * * *" # TODO this is once a day and should be a variable
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  region           = var.gcp_region

  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.function.https_trigger_url
    oidc_token {
      service_account_email = var.deployer_service_account
    }
  }
}


