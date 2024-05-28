locals {
  function_config = jsondecode(file("${path.module}/../../functions-python/feat375/function_config.json"))
  function_zip    = "${path.module}/../../functions-python/feat375/.dist/feat375.zip"
}

# 1. Get functions service account
data "google_service_account" "functions_service_account" {
  account_id = "functions-service-account"
  project    = var.project_id
}

# 2. Create the source code zip in bucket
data "google_storage_bucket" "functions_bucket" {
  name = "mobility-feeds-functions-python-${var.environment}"
}
resource "google_storage_bucket_object" "function_zip" {
  name   = "feat375-${substr(filebase64sha256(local.function_zip),0,10)}.zip"
  bucket = data.google_storage_bucket.functions_bucket.name
  source = local.function_zip
}

# 3. Create the cloud http function
resource "google_cloudfunctions2_function" "feat375_function" {
  name        = "${local.function_config.name}-${var.environment}"
  description = local.function_config.description
  location    = var.gcp_region
  project     = var.project_id
  build_config {
    runtime     = "python310"
    entry_point = local.function_config.entry_point
    source {
      storage_source {
        bucket = data.google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_config.memory
    available_cpu    = local.function_config.available_cpu
    timeout_seconds  = local.function_config.timeout

    environment_variables = {
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
      ENVIRONMENT         = var.environment
    }
    service_account_email            = data.google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_config.max_instance_request_concurrency
    max_instance_count               = local.function_config.max_instance_count
    min_instance_count               = local.function_config.min_instance_count
  }
}

# 4. Create the Cloud Scheduler job to trigger the function daily at noon
resource "google_cloud_scheduler_job" "feat375_job" {
  name        = "feat375-scheduler-job-${var.environment}"
  project     = var.project_id
  region      = var.gcp_region
  description = "Trigger feat375 function daily at noon"
  schedule    = "0 12 * * *"  # Every day at noon
  time_zone   = "Etc/UTC"
  depends_on = [google_cloudfunctions2_function.feat375_function]

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.feat375_function.service_config[0].uri
    oidc_token {
      service_account_email = data.google_service_account.functions_service_account.email
    }
  }

  retry_config {
    retry_count = 3
  }

  attempt_deadline = "1800s"
}