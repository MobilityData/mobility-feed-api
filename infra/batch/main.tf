terraform {
  backend "gcs" {
  }
}

data "google_project" "project" {}

provider "google" {
  project         = var.project_id
  access_token    = data.google_service_account_access_token.default.access_token
  request_timeout = "60s"
  region          = var.gcp_region
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

  function_batch_datasets_config = jsondecode(file("${path.module}/../../functions-python/batch_datasets/function_config.json"))
  function_batch_datasets_zip    = "${path.module}/../../functions-python/batch_datasets/.dist/batch_datasets.zip"

  function_batch_process_dataset_config = jsondecode(file("${path.module}/../../functions-python/batch_process_dataset/function_config.json"))
  function_batch_process_dataset_zip    = "${path.module}/../../functions-python/batch_process_dataset/.dist/batch_process_dataset.zip"
}

resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

# Service account to execute the cloud functions
resource "google_service_account" "functions_service_account" {
  account_id   = "batchfunctions-service-account"
  display_name = "Batch Functions Service Account"
}

# Cloud storage bucket to store the datasets
resource "google_storage_bucket" "datasets_bucket" {
  name     = var.datasets_bucket_name
  location = "us-central1"
  uniform_bucket_level_access = false
}

# Grant permissions to the service account to access the datasets bucket
resource "google_storage_bucket_iam_member" "datasets_bucket_functions_service_account" {
  bucket = google_storage_bucket.datasets_bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_project_iam_member" "datasets_bucket_functions_service_account" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
  role    = "roles/storage.admin"
}

resource "google_storage_bucket" "functions_bucket" {
  name     = "mobility-feeds-bacth-python-${var.environment}"
  location = "us"
}

# Function's zip files with sile sha256 as part of the name to force redeploy
resource "google_storage_bucket_object" "batch_datasets_zip" {
  name   = "batch_datasets-${substr(filebase64sha256(local.function_batch_datasets_zip), 0, 10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_batch_datasets_zip
}

# Function's zip files with sile sha256 as part of the name to force redeploy
resource "google_storage_bucket_object" "batch_process_dataset_zip" {
  name   = "batch_process_dataset-${substr(filebase64sha256(local.function_batch_process_dataset_zip), 0, 10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_batch_process_dataset_zip
}

data "google_iam_policy" "secret_access_function_batch_datasets" {
  binding {
    role = "roles/secretmanager.secretAccessor"
    members = [
      "serviceAccount:${google_service_account.functions_service_account.email}"
    ]
  }
}

# Grant permissions to the service account to access the secrets based on the function config
resource "google_secret_manager_secret_iam_policy" "policy_function_batch_datasets" {
  for_each = { for x in local.function_batch_process_dataset_config.secret_environment_variables : x.key => x }

  project     = var.project_id
  secret_id   = lookup(each.value, "secret", "${upper(var.environment)}_${each.value["key"]}")
  policy_data = data.google_iam_policy.secret_access_function_batch_datasets.policy_data
}

# Grant permissions to the service account to publish to the pubsub topic
resource "google_pubsub_topic_iam_binding" "functions_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  topic   = google_pubsub_topic.pubsub_topic.name
  members = ["serviceAccount:${google_service_account.functions_service_account.email}"]
}

# Grant permissions to the service account to subscribe to the pubsub topic
resource "google_pubsub_topic_iam_binding" "functions_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  topic   = google_pubsub_topic.pubsub_topic.name
  members = ["serviceAccount:${google_service_account.functions_service_account.email}"]
}

# Batch datasets function
resource "google_cloudfunctions2_function" "batch_datasets" {
  name        = "${local.function_batch_datasets_config.name}-${var.environment}"
  description = local.function_batch_datasets_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_policy.policy_function_batch_datasets]
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_batch_datasets_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.batch_datasets_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_batch_datasets_config.memory
    available_cpu    = local.function_batch_datasets_config.available_cpu
    timeout_seconds  = local.function_batch_datasets_config.timeout

    environment_variables = {
      PUBSUB_TOPIC_NAME = google_pubsub_topic.pubsub_topic.name
      PROJECT_ID        = var.project_id
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
      ENVIRONMENT         = var.environment
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_batch_datasets_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_batch_datasets_config.max_instance_request_concurrency
    max_instance_count               = local.function_batch_datasets_config.max_instance_count
    min_instance_count               = local.function_batch_datasets_config.min_instance_count
  }
}

resource "google_cloudfunctions2_function_iam_member" "batch_datasets_function_invoker" {
  cloud_function = google_cloudfunctions2_function.batch_datasets.name
  project        = var.project_id
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_cloud_run_service_iam_member" "batch_datasets_cloud_run_invoker" {
  project  = google_cloudfunctions2_function.batch_datasets.project
  location = google_cloudfunctions2_function.batch_datasets.location
  service  = google_cloudfunctions2_function.batch_datasets.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions_service_account.email}"
}


resource "google_datastore_index" "dataset_processing_index_execution_id_stable_id_status" {
  project = var.project_id
  kind    = "historical_dataset_batch"
  properties {
    name      = "execution_id"
    direction = "ASCENDING"
  }
  properties {
    name      = "stable_id"
    direction = "ASCENDING"
  }
}

resource "google_datastore_index" "dataset_processing_index_execution_id_timestamp" {
  project = var.project_id
  kind    = "historical_dataset_batch"
  properties {
    name      = "execution_id"
    direction = "ASCENDING"
  }
  properties {
    name      = "timestamp"
    direction = "ASCENDING"
  }
}

resource "google_datastore_index" "batch_execution_index_execution_id_timestamp" {
  project = var.project_id
  kind    = "batch_execution"
  properties {
    name      = "execution_id"
    direction = "ASCENDING"
  }
  properties {
    name      = "timestamp"
    direction = "ASCENDING"
  }
}


resource "google_project_iam_member" "datastore_owner" {
  project = var.project_id
  role    = "roles/datastore.owner"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_pubsub_topic" "pubsub_topic" {
  name = "datasets-batch-topic-${var.environment}"
}

# Batch process dataset function
resource "google_cloudfunctions2_function" "pubsub_function" {
  name        = "${local.function_batch_process_dataset_config.name}-${var.environment}"
  description = local.function_batch_process_dataset_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_policy.policy_function_batch_datasets]
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_batch_process_dataset_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.batch_process_dataset_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_batch_process_dataset_config.memory
    available_cpu    = local.function_batch_process_dataset_config.available_cpu
    timeout_seconds  = local.function_batch_process_dataset_config.timeout

    environment_variables = {
      DATASETS_BUCKET_NANE = google_storage_bucket.datasets_bucket.name
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
      DB_REUSE_SESSION    = "True"
      ENVIRONMENT         = var.environment
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_batch_process_dataset_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_batch_process_dataset_config.max_instance_request_concurrency
    max_instance_count               = local.function_batch_process_dataset_config.max_instance_count
    min_instance_count               = local.function_batch_process_dataset_config.min_instance_count
  }
  event_trigger {
    trigger_region        = var.gcp_region
    service_account_email = google_service_account.functions_service_account.email
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.pubsub_topic.id
    retry_policy          = "RETRY_POLICY_RETRY"
  }
}

resource "google_cloudfunctions2_function_iam_member" "pubsub_function_invoker" {
  cloud_function = google_cloudfunctions2_function.pubsub_function.name
  project        = var.project_id
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_cloud_run_service_iam_member" "cloud_run_invoker" {
  project  = google_cloudfunctions2_function.pubsub_function.project
  location = google_cloudfunctions2_function.pubsub_function.location
  service  = google_cloudfunctions2_function.pubsub_function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Scheduler job to trigger the batch job only on Mondays
# Paused for non-prod environments
resource "google_cloud_scheduler_job" "job" {
  name             = "${var.job_name}-${var.environment}"
  description      = "Batch job to process datasets"
  schedule         = var.job_schedule
  time_zone        = "Etc/UTC"
  attempt_deadline = var.job_attempt_deadline
  paused           = var.environment == "prod" ? false : true
  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.batch_datasets.url
    oidc_token {
      service_account_email = google_service_account.functions_service_account.email
    }
    body = base64encode("{}")
    headers = {
      "Content-Type" = "application/json"
    }
  }
}
