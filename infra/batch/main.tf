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

provider "google" {
  project = var.project_id
  region  = var.gcp_region
}

resource "google_storage_bucket" "bucket" {
  name = var.bucket_name
  location = var.gcp_region
}

resource "google_storage_bucket_object" "entry_point" {
  name   = "datasets/main.py"
  bucket = google_storage_bucket.bucket.name
  source = "datasets/main.py"
}

resource "google_storage_bucket_object" "python_requirements" {
  name   = "datasets/requirements.txt"
  bucket = google_storage_bucket.bucket.name
  source = "datasets/requirements.txt"
}

resource "google_cloudfunctions_function" "function" {
  name        = "my-function"
  description = "Python function"
  runtime     = "python311"

  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.bucket.name
  source_archive_object = google_storage_bucket_object.entry_point.name

  entry_point = "batch_dataset"

  trigger_http = true
}

resource "google_cloud_scheduler_job" "job" {
  name             = "daily-job"
  description      = "Run python function daily"
  schedule         = "*/1 * * * *"
  time_zone        = "UTC"
  attempt_deadline = "320s"

  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.function.https_trigger_url
  }
}
