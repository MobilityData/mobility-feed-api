terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.34.0"
    }
  }
}
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

locals {
  x_number_of_concurrent_instance = 4
  deployment_timestamp = formatdate("YYYYMMDDhhmmss", timestamp())
  function_tokens_config = jsondecode(file("${path.module}../../../functions-python/tokens/function_config.json"))
  function_tokens_zip    = "${path.module}/../../functions-python/tokens/.dist/tokens.zip"

  #  DEV and QA use the vpc connector
  vpc_connector_name = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id

  # This is as a constant due to the existent of two independent infra modules
  batchfunctions_sa_email = "batchfunctions-service-account@${var.project_id}.iam.gserviceaccount.com"

  function_process_validation_report_config = jsondecode(file("${path.module}/../../functions-python/process_validation_report/function_config.json"))
  function_process_validation_report_zip = "${path.module}/../../functions-python/process_validation_report/.dist/process_validation_report.zip"
  public_hosted_datasets_url = lower(var.environment) == "prod" ? "https://${var.public_hosted_datasets_dns}" : "https://${var.environment}-${var.public_hosted_datasets_dns}"

  function_update_validation_report_config = jsondecode(file("${path.module}/../../functions-python/update_validation_report/function_config.json"))
  function_update_validation_report_zip = "${path.module}/../../functions-python/update_validation_report/.dist/update_validation_report.zip"

  function_gbfs_validation_report_config = jsondecode(file("${path.module}/../../functions-python/gbfs_validator/function_config.json"))
  function_gbfs_validation_report_zip = "${path.module}/../../functions-python/gbfs_validator/.dist/gbfs_validator.zip"

  function_reverse_geolocation_populate_config = jsondecode(file("${path.module}/../../functions-python/reverse_geolocation_populate/function_config.json"))
  function_reverse_geolocation_populate_zip = "${path.module}/../../functions-python/reverse_geolocation_populate/.dist/reverse_geolocation_populate.zip"

  function_feed_sync_dispatcher_transitland_config = jsondecode(file("${path.module}/../../functions-python/feed_sync_dispatcher_transitland/function_config.json"))
  function_feed_sync_dispatcher_transitland_zip = "${path.module}/../../functions-python/feed_sync_dispatcher_transitland/.dist/feed_sync_dispatcher_transitland.zip"

  function_feed_sync_process_transitland_config = jsondecode(file("${path.module}/../../functions-python/feed_sync_process_transitland/function_config.json"))
  function_feed_sync_process_transitland_zip = "${path.module}/../../functions-python/feed_sync_process_transitland/.dist/feed_sync_process_transitland.zip"

  function_operations_api_config = jsondecode(file("${path.module}/../../functions-python/operations_api/function_config.json"))
  function_operations_api_zip = "${path.module}/../../functions-python/operations_api/.dist/operations_api.zip"

  function_backfill_dataset_service_date_range_config = jsondecode(file("${path.module}/../../functions-python/backfill_dataset_service_date_range/function_config.json"))
  function_backfill_dataset_service_date_range_zip = "${path.module}/../../functions-python/backfill_dataset_service_date_range/.dist/backfill_dataset_service_date_range.zip"

  function_reverse_geolocation_config = jsondecode(file("${path.module}/../../functions-python/reverse_geolocation/function_config.json"))
  function_reverse_geolocation_zip = "${path.module}/../../functions-python/reverse_geolocation/.dist/reverse_geolocation.zip"

  function_update_feed_status_config = jsondecode(file("${path.module}/../../functions-python/update_feed_status/function_config.json"))
  function_update_feed_status_zip = "${path.module}/../../functions-python/update_feed_status/.dist/update_feed_status.zip"

  function_export_csv_config = jsondecode(file("${path.module}/../../functions-python/export_csv/function_config.json"))
  function_export_csv_zip = "${path.module}/../../functions-python/export_csv/.dist/export_csv.zip"

  function_tasks_executor_config = jsondecode(file("${path.module}/../../functions-python/tasks_executor/function_config.json"))
  function_tasks_executor_zip = "${path.module}/../../functions-python/tasks_executor/.dist/tasks_executor.zip"

  function_pmtiles_builder_config = jsondecode(file("${path.module}/../../functions-python/pmtiles_builder/function_config.json"))
  function_pmtiles_builder_zip = "${path.module}/../../functions-python/pmtiles_builder/.dist/pmtiles_builder.zip"
}

locals {
  all_secret_dicts = concat(
    local.function_tokens_config.secret_environment_variables,
    local.function_process_validation_report_config.secret_environment_variables,
    local.function_gbfs_validation_report_config.secret_environment_variables,
    local.function_update_validation_report_config.secret_environment_variables,
    local.function_backfill_dataset_service_date_range_config.secret_environment_variables,
    local.function_update_feed_status_config.secret_environment_variables,
    local.function_export_csv_config.secret_environment_variables,
    local.function_tasks_executor_config.secret_environment_variables,
    local.function_pmtiles_builder_config.secret_environment_variables
  )

  # Remove duplicates by key, keeping the first occurrence
  unique_secret_dicts = [
    for i, s in local.all_secret_dicts :
    s if index([
      for j in local.all_secret_dicts : j.key
    ], s.key) == i
  ]

  # Convert to a map for for_each
  unique_secret_dict_map = {
    for s in local.unique_secret_dicts : s.key => s
  }
}


data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

data "google_pubsub_topic" "datasets_batch_topic" {
  name = "datasets-batch-topic-${var.environment}"
}

data "google_storage_bucket" "datasets_bucket" {
  name = "${var.datasets_bucket_name}-${var.environment}"
}

# Service account to execute the cloud functions
resource "google_service_account" "functions_service_account" {
  account_id   = "functions-service-account"
  display_name = "Functions Service Account"
}

resource "google_storage_bucket" "functions_bucket" {
  name     = "mobility-feeds-functions-python-${var.environment}"
  location = "us"
}

resource "google_storage_bucket" "gbfs_snapshots_bucket" {
  location = var.gcp_region
  name     = "${var.gbfs_bucket_name}-${var.environment}"
  cors {
    origin = ["*"]
    method = ["GET"]
    response_header = ["*"]
  }
}

resource "google_storage_bucket_iam_member" "datasets_bucket_functions_service_account" {
  bucket = data.google_storage_bucket.datasets_bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_project_iam_member" "datasets_bucket_functions_service_account" {
  project = var.project_id
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
  role    = "roles/storage.admin"
}

# Cloud function source code zip files:
# 1. Tokens
resource "google_storage_bucket_object" "function_token_zip" {
  name   = "tokens-${substr(filebase64sha256(local.function_tokens_zip),0,10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_tokens_zip
}

# 3. Process validation report
resource "google_storage_bucket_object" "process_validation_report_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "process-validation-report-${substr(filebase64sha256(local.function_process_validation_report_zip), 0, 10)}.zip"
  source = local.function_process_validation_report_zip
}

# 4. Update validation report
resource "google_storage_bucket_object" "update_validation_report_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "update-validation-report-${substr(filebase64sha256(local.function_update_validation_report_zip), 0, 10)}.zip"
  source = local.function_update_validation_report_zip
}

# 5. GBFS validation report
resource "google_storage_bucket_object" "gbfs_validation_report_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "gbfs-validator-${substr(filebase64sha256(local.function_gbfs_validation_report_zip), 0, 10)}.zip"
  source = local.function_gbfs_validation_report_zip
}

# 6. Feed sync dispatcher transitland
resource "google_storage_bucket_object" "feed_sync_dispatcher_transitland_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "feed-sync-dispatcher-transitland-${substr(filebase64sha256(local.function_feed_sync_dispatcher_transitland_zip), 0, 10)}.zip"
  source = local.function_feed_sync_dispatcher_transitland_zip
}

# 7. Feed sync process transitland
resource "google_storage_bucket_object" "feed_sync_process_transitland_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "feed-sync-process-transitland-${substr(filebase64sha256(local.function_feed_sync_process_transitland_zip), 0, 10)}.zip"
  source = local.function_feed_sync_process_transitland_zip
}

# 8. Operations API
resource "google_storage_bucket_object" "operations_api_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "operations-api-${substr(filebase64sha256(local.function_operations_api_zip), 0, 10)}.zip"
  source = local.function_operations_api_zip
}

# 9. Backfill Gtfs Datasets Service Date Range
resource "google_storage_bucket_object" "backfill_dataset_service_date_range_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "backfill-dataset-service-date-range-${substr(filebase64sha256(local.function_backfill_dataset_service_date_range_zip), 0, 10)}.zip"
  source = local.function_backfill_dataset_service_date_range_zip
}

# 10. Export CSV
resource "google_storage_bucket_object" "export_csv_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "export-csv-${substr(filebase64sha256(local.function_export_csv_zip), 0, 10)}.zip"
  source = local.function_export_csv_zip
}

# 11. Update Feed Status
resource "google_storage_bucket_object" "update_feed_status_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "backfill-dataset-service-date-range-${substr(filebase64sha256(local.function_update_feed_status_zip), 0, 10)}.zip"
  source = local.function_update_feed_status_zip
}

# 12. Reverse geolocation populate
resource "google_storage_bucket_object" "reverse_geolocation_populate_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "reverse-geolocation-populate-${substr(filebase64sha256(local.function_reverse_geolocation_populate_zip), 0, 10)}.zip"
  source = local.function_reverse_geolocation_populate_zip
}

# 13. Reverse geolocation
resource "google_storage_bucket_object" "reverse_geolocation_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "reverse-geolocation-${substr(filebase64sha256(local.function_reverse_geolocation_zip), 0, 10)}.zip"
  source = local.function_reverse_geolocation_zip
}

# 14. Task Executor
resource "google_storage_bucket_object" "tasks_executor_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "task-executor-${substr(filebase64sha256(local.function_tasks_executor_zip), 0, 10)}.zip"
  source = local.function_tasks_executor_zip
}

# 15. PMTiles Builder
resource "google_storage_bucket_object" "pmtiles_builder_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "pmtiles-${substr(filebase64sha256(local.function_pmtiles_builder_zip), 0, 10)}.zip"
  source = local.function_pmtiles_builder_zip
}

# Secrets access
resource "google_secret_manager_secret_iam_member" "secret_iam_member" {
  for_each = local.unique_secret_dict_map

  project    = var.project_id
  # The secret_id is the current item in the set. Since these are unique keys, we use each.value to access it.
  secret_id  = lookup(each.value, "secret", "${upper(var.environment)}_${each.value["key"]}")
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Cloud function definitions
# 1. functions-python/tokens cloud function
resource "google_cloudfunctions2_function" "tokens" {
  name        = local.function_tokens_config.name
  description = local.function_tokens_config.description
  location    = var.gcp_region
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_tokens_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.function_token_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_tokens_config.memory
    timeout_seconds = local.function_tokens_config.timeout
    available_cpu = local.function_tokens_config.available_cpu
    max_instance_request_concurrency = local.function_tokens_config.max_instance_request_concurrency
    max_instance_count = local.function_tokens_config.max_instance_count
    min_instance_count = local.function_tokens_config.min_instance_count
    dynamic "secret_environment_variables" {
      for_each = local.function_tokens_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_tokens_config.ingress_settings
  }
}

# 3. functions/validation_report_processor
# 3.1 functions/validation_report_processor cloud function
# Create a queue for the cloud tasks
# The 2X rate is defined as 4*2 concurrent dispatches and 1 dispatch per second
# The name of the queue need to be dynamic due to GCP limitations
# references:
#   - https://cloud.google.com/tasks/docs/deleting-appengine-queues-and-tasks#deleting_queues
#   - https://issuetracker.google.com/issues/263947953
resource "google_cloud_tasks_queue" "cloud_tasks_2x_rate_queue" {
  name     = "cloud-tasks-2x-rate-queue-${var.environment}-${local.deployment_timestamp}"
  location = var.gcp_region

  rate_limits {
    max_concurrent_dispatches = local.x_number_of_concurrent_instance * 2
    max_dispatches_per_second = 1
  }

  retry_config {
    # This will make the cloud task retry for ~two hours
    max_attempts  = 120
    min_backoff   = "20s"
    max_backoff   = "60s"
    max_doublings = 2
  }
}

output "processing_report_cloud_task_name" {
  value = google_cloud_tasks_queue.cloud_tasks_2x_rate_queue.name
}

resource "google_cloudfunctions2_function" "process_validation_report" {
  name        = local.function_process_validation_report_config.name
  description = local.function_process_validation_report_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
  project = var.project_id
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_process_validation_report_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.process_validation_report_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_process_validation_report_config.memory
    available_cpu    = local.function_process_validation_report_config.available_cpu
    timeout_seconds  = local.function_process_validation_report_config.timeout
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      ENV = var.environment
      PROJECT_ID = var.project_id
      GCP_REGION = var.gcp_region
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email      
      FILES_ENDPOINT    = local.public_hosted_datasets_url
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_process_validation_report_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_process_validation_report_config.max_instance_request_concurrency
    max_instance_count               = local.function_process_validation_report_config.max_instance_count
    min_instance_count               = local.function_process_validation_report_config.min_instance_count
  }
}

# 3.2 functions/compute_validation_report_counters cloud function
resource "google_cloudfunctions2_function" "compute_validation_report_counters" {
  name        = "compute-validation-report-counters"
  description = "Cloud function to compute counters for validation reports"
  location    = var.gcp_region
  depends_on  = [google_secret_manager_secret_iam_member.secret_iam_member]
  project     = var.project_id

  build_config {
    runtime     = var.python_runtime
    entry_point = "compute_validation_report_counters"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.process_validation_report_zip.name
      }
    }
  }

  service_config {
    available_memory = "512Mi"
    available_cpu    = "1"
    timeout_seconds  = 300
    vpc_connector    = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      ENV = var.environment
      PYTHONNODEBUGRANGES = 0
    }

    dynamic "secret_environment_variables" {
      for_each = local.function_process_validation_report_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }

    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = 1
    max_instance_count               = 1
    min_instance_count               = 0
  }
}

# 4. functions/update_validation_report cloud function
resource "google_cloudfunctions2_function" "update_validation_report" {
  location = var.gcp_region
  name     = local.function_update_validation_report_config.name
  description = local.function_update_validation_report_config.description
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
  project = var.project_id
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_update_validation_report_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.update_validation_report_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_update_validation_report_config.memory
    available_cpu    = local.function_update_validation_report_config.available_cpu
    timeout_seconds  = local.function_update_validation_report_config.timeout
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      ENV = var.environment
      MAX_RETRY = 10
      BATCH_SIZE = 5
      WEB_VALIDATOR_URL = var.validator_endpoint
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_update_validation_report_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_update_validation_report_config.max_instance_request_concurrency
    max_instance_count               = local.function_update_validation_report_config.max_instance_count
    min_instance_count               = local.function_update_validation_report_config.min_instance_count
  }
}

# 5. functions/gbfs_validator cloud function
# 5.1 Create Pub/Sub topic
resource "google_pubsub_topic" "validate_gbfs_feed" {
  name = "validate-gbfs-feed"
}

# 5.2 Create batch function that publishes to the Pub/Sub topic
resource "google_cloudfunctions2_function" "gbfs_validator_batch" {
  name        = "${local.function_gbfs_validation_report_config.name}-batch"
  description = local.function_gbfs_validation_report_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_gbfs_validation_report_config.entry_point}_batch"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.gbfs_validation_report_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      PUBSUB_TOPIC_NAME = google_pubsub_topic.validate_gbfs_feed.name
      PYTHONNODEBUGRANGES = 0
    }
    available_memory = "1Gi"
    timeout_seconds = local.function_gbfs_validation_report_config.timeout
    available_cpu = local.function_gbfs_validation_report_config.available_cpu
    max_instance_request_concurrency = local.function_gbfs_validation_report_config.max_instance_request_concurrency
    max_instance_count = local.function_gbfs_validation_report_config.max_instance_count
    min_instance_count = local.function_gbfs_validation_report_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_gbfs_validation_report_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# Schedule the batch function to run
resource "google_cloud_scheduler_job" "gbfs_validator_batch_scheduler" {
  name = "gbfs-validator-batch-scheduler-${var.environment}"
  description = "Schedule the gbfs-validator-batch function"
  time_zone = "Etc/UTC"
  schedule = var.gbfs_scheduler_schedule
  region = var.gcp_region
  paused = var.environment == "prod" ? false : true
  depends_on = [google_cloudfunctions2_function.gbfs_validator_batch, google_cloudfunctions2_function_iam_member.gbfs_validator_batch_invoker]
  http_target {
    http_method = "POST"
    uri = google_cloudfunctions2_function.gbfs_validator_batch.url
    oidc_token {
      service_account_email = google_service_account.functions_service_account.email
    }
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode("{}")
  }
  attempt_deadline = "320s"
}

resource "google_cloud_scheduler_job" "transit_land_scraping_scheduler" {
  name = "transitland-scraping-scheduler-${var.environment}"
  description = "Schedule the transitland scraping function"
  time_zone = "Etc/UTC"
  schedule = var.transitland_scraping_schedule
  region = var.gcp_region
  paused = var.environment == "prod" ? false : true
  depends_on = [google_cloudfunctions2_function.feed_sync_dispatcher_transitland, google_cloudfunctions2_function_iam_member.transitland_feeds_dispatcher_invoker]
  http_target {
    http_method = "POST"
    uri = google_cloudfunctions2_function.feed_sync_dispatcher_transitland.url
    oidc_token {
      service_account_email = google_service_account.functions_service_account.email
    }
    headers = {
      "Content-Type" = "application/json"
    }
  }
  attempt_deadline = "320s"
}

# 5.3 Create function that subscribes to the Pub/Sub topic
resource "google_cloudfunctions2_function" "gbfs_validator_pubsub" {
  name        = "${local.function_gbfs_validation_report_config.name}-pubsub"
  description = local.function_gbfs_validation_report_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]
  event_trigger {
    trigger_region        = var.gcp_region
    service_account_email = google_service_account.functions_service_account.email
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.validate_gbfs_feed.id
    retry_policy          = "RETRY_POLICY_RETRY"
  }
  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_gbfs_validation_report_config.entry_point}_pubsub"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.gbfs_validation_report_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_gbfs_validation_report_config.memory
    timeout_seconds = local.function_gbfs_validation_report_config.timeout
    available_cpu = local.function_gbfs_validation_report_config.available_cpu
    max_instance_request_concurrency = local.function_gbfs_validation_report_config.max_instance_request_concurrency
    max_instance_count = local.function_gbfs_validation_report_config.max_instance_count
    min_instance_count = local.function_gbfs_validation_report_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    environment_variables = {
      ENV = var.environment
      BUCKET_NAME = google_storage_bucket.gbfs_snapshots_bucket.name
      PROJECT_ID = var.project_id
      GCP_REGION = var.gcp_region
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email
      QUEUE_NAME = google_cloud_tasks_queue.reverse_geolocation_task_queue_processor.name
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_gbfs_validation_report_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 6. functions/feed_sync_dispatcher_transitland cloud function
# 6.1 Create Pub/Sub topic
resource "google_pubsub_topic" "transitland_feeds_dispatch" {
  name = "transitland-feeds-dispatch"
}
# 6.2 Create batch function that publishes to the Pub/Sub topic
resource "google_cloudfunctions2_function" "feed_sync_dispatcher_transitland" {
  name        = "${local.function_feed_sync_dispatcher_transitland_config.name}-batch"
  description = local.function_feed_sync_dispatcher_transitland_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_feed_sync_dispatcher_transitland_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.feed_sync_dispatcher_transitland_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      PYTHONNODEBUGRANGES = 0
      PUBSUB_TOPIC_NAME = google_pubsub_topic.transitland_feeds_dispatch.name
      TRANSITLAND_API_KEY=var.transitland_api_key
      TRANSITLAND_OPERATOR_URL="https://transit.land/api/v2/rest/operators"
      TRANSITLAND_FEED_URL="https://transit.land/api/v2/rest/feeds"
    }
    available_memory = local.function_feed_sync_dispatcher_transitland_config.available_memory
    timeout_seconds = local.function_feed_sync_dispatcher_transitland_config.timeout
    available_cpu = local.function_feed_sync_dispatcher_transitland_config.available_cpu
    max_instance_request_concurrency = local.function_feed_sync_dispatcher_transitland_config.max_instance_request_concurrency
    max_instance_count = local.function_feed_sync_dispatcher_transitland_config.max_instance_count
    min_instance_count = local.function_feed_sync_dispatcher_transitland_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_feed_sync_dispatcher_transitland_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_feed_sync_dispatcher_transitland_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 7. functions/operations_api cloud function
resource "google_cloudfunctions2_function" "operations_api" {
  name        = "${local.function_operations_api_config.name}"
  description = local.function_operations_api_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_operations_api_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.operations_api_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      PYTHONNODEBUGRANGES = 0
      GOOGLE_CLIENT_ID = var.operations_oauth2_client_id
    }
    available_memory = local.function_operations_api_config.memory
    timeout_seconds = local.function_operations_api_config.timeout
    available_cpu = local.function_operations_api_config.available_cpu
    max_instance_request_concurrency = local.function_operations_api_config.max_instance_request_concurrency
    max_instance_count = local.function_operations_api_config.max_instance_count
    min_instance_count = local.function_operations_api_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_operations_api_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_operations_api_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}
# 8. functions/feed_sync_process_transitland cloud function
resource "google_cloudfunctions2_function" "feed_sync_process_transitland" {
  name        = "${local.function_feed_sync_process_transitland_config.name}-pubsub"
  description = local.function_feed_sync_process_transitland_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]
  event_trigger {
    trigger_region        = var.gcp_region
    service_account_email = google_service_account.functions_service_account.email
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.transitland_feeds_dispatch.id
    retry_policy          = "RETRY_POLICY_RETRY"
  }
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_feed_sync_process_transitland_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.feed_sync_process_transitland_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_feed_sync_process_transitland_config.memory
    timeout_seconds = local.function_feed_sync_process_transitland_config.timeout
    available_cpu = local.function_feed_sync_process_transitland_config.available_cpu
    max_instance_request_concurrency = local.function_feed_sync_process_transitland_config.max_instance_request_concurrency
    max_instance_count = local.function_feed_sync_process_transitland_config.max_instance_count
    min_instance_count = local.function_feed_sync_process_transitland_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = var.environment == "dev" ? "ALLOW_ALL" : local.function_feed_sync_process_transitland_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    environment_variables = {
      PYTHONNODEBUGRANGES = 0
      DB_REUSE_SESSION = "True"
      PROJECT_ID = var.project_id
      PUBSUB_TOPIC_NAME = google_pubsub_topic.transitland_feeds_dispatch.name
      DATASET_BATCH_TOPIC_NAME = data.google_pubsub_topic.datasets_batch_topic.name
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_feed_sync_process_transitland_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 9. functions/backfill_dataset_service_date_range cloud function
# Fills all the NULL values for service date range in the gtfs datasets table
resource "google_cloudfunctions2_function" "backfill_dataset_service_date_range" {
  name        = local.function_backfill_dataset_service_date_range_config.name
  description = local.function_backfill_dataset_service_date_range_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
  project = var.project_id
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_backfill_dataset_service_date_range_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.backfill_dataset_service_date_range_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_backfill_dataset_service_date_range_config.memory
    available_cpu    = local.function_backfill_dataset_service_date_range_config.available_cpu
    timeout_seconds  = local.function_backfill_dataset_service_date_range_config.timeout
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      # prevents multiline logs from being truncated on GCP console
      ENV = var.environment
      PYTHONNODEBUGRANGES = 0
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_backfill_dataset_service_date_range_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_backfill_dataset_service_date_range_config.max_instance_request_concurrency
    max_instance_count               = local.function_backfill_dataset_service_date_range_config.max_instance_count
    min_instance_count               = local.function_backfill_dataset_service_date_range_config.min_instance_count
  }
}

# 10. functions/export_csv cloud function
resource "google_cloudfunctions2_function" "export_csv" {
  name        = "${local.function_export_csv_config.name}"
  project     = var.project_id
  description = local.function_export_csv_config.description
  location    = var.gcp_region
  depends_on  = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_export_csv_config.entry_point}"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.export_csv_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      DATASETS_BUCKET_NAME = data.google_storage_bucket.datasets_bucket.name
      PROJECT_ID  = var.project_id
      ENVIRONMENT = var.environment
    }
    available_memory                 = local.function_export_csv_config.memory
    timeout_seconds                  = local.function_export_csv_config.timeout
    available_cpu                    = local.function_export_csv_config.available_cpu
    max_instance_request_concurrency = local.function_export_csv_config.max_instance_request_concurrency
    max_instance_count               = local.function_export_csv_config.max_instance_count
    min_instance_count               = local.function_export_csv_config.min_instance_count
    service_account_email            = google_service_account.functions_service_account.email
    ingress_settings                 = "ALLOW_ALL"
    vpc_connector                    = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings    = "PRIVATE_RANGES_ONLY"

    dynamic "secret_environment_variables" {
      for_each = local.function_export_csv_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 11. functions/update_feed_status cloud function
# Updates the Feed statuses based on latest dataset service date range

resource "google_cloudfunctions2_function" "update_feed_status" {
  name        = local.function_update_feed_status_config.name
  description = local.function_update_feed_status_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
  project = var.project_id
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_update_feed_status_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.update_feed_status_zip.name
      }
    }
  }
  service_config {
    available_memory = local.function_update_feed_status_config.memory
    available_cpu    = local.function_update_feed_status_config.available_cpu
    timeout_seconds  = local.function_update_feed_status_config.timeout
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
    }
    dynamic "secret_environment_variables" {
      for_each = local.function_update_feed_status_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
    service_account_email            = google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_update_feed_status_config.max_instance_request_concurrency
    max_instance_count               = local.function_update_feed_status_config.max_instance_count
    min_instance_count               = local.function_update_feed_status_config.min_instance_count
  }
}


resource "google_cloud_scheduler_job" "export_csv_scheduler" {
  name = "export-csv-scheduler-${var.environment}"
  description = "Schedule the export_csv function"
  time_zone = "Etc/UTC"
  schedule = var.export_csv_schedule
  region = var.gcp_region
  paused = var.environment == "prod" ? false : true
  depends_on = [google_cloudfunctions2_function.export_csv, google_cloudfunctions2_function_iam_member.export_csv_invoker]
  http_target {
    http_method = "POST"
    uri = google_cloudfunctions2_function.export_csv.url
    oidc_token {
      service_account_email = google_service_account.functions_service_account.email
    }
    headers = {
      "Content-Type" = "application/json"
    }
  }
  # Export CSV can take several minutes to run (5?) so we need to give it a longer deadline
  attempt_deadline = "600s"
}

resource "google_cloud_scheduler_job" "update_feed_status_scheduler" {
  name = "update-feed-status-${var.environment}"
  description = "Schedule the update_feed_status function daily"
  time_zone = "Etc/UTC"
  schedule = var.update_feed_status_schedule
  region = var.gcp_region
  paused = var.environment == "prod" ? false : true
  depends_on = [google_cloudfunctions2_function.update_feed_status, google_cloudfunctions2_function_iam_member.update_feed_status_invoker]
  http_target {
    http_method = "POST"
    uri = google_cloudfunctions2_function.update_feed_status.url
    oidc_token {
      service_account_email = google_service_account.functions_service_account.email
    }
    headers = {
      "Content-Type" = "application/json"
    }
  }
  attempt_deadline = "600s"
}


# IAM entry for all users to invoke the function
# 12. functions/reverse_geolocation_populate cloud function
resource "google_cloudfunctions2_function" "reverse_geolocation_populate" {
  name        = local.function_reverse_geolocation_populate_config.name
  description = local.function_reverse_geolocation_populate_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_reverse_geolocation_populate_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.reverse_geolocation_populate_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PYTHONNODEBUGRANGES = 0
      DB_REUSE_SESSION = "True"
    }
    available_memory = local.function_reverse_geolocation_populate_config.available_memory
    timeout_seconds = local.function_reverse_geolocation_populate_config.timeout
    available_cpu = local.function_reverse_geolocation_populate_config.available_cpu
    max_instance_request_concurrency = local.function_reverse_geolocation_populate_config.max_instance_request_concurrency
    max_instance_count = local.function_reverse_geolocation_populate_config.max_instance_count
    min_instance_count = local.function_reverse_geolocation_populate_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_reverse_geolocation_populate_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_reverse_geolocation_populate_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 13.1 functions/reverse_geolocation - processor cloud function
resource "google_cloudfunctions2_function" "reverse_geolocation_processor" {
  name        = "${local.function_reverse_geolocation_config.name}-processor"
  description = local.function_reverse_geolocation_config.description
  location    = var.gcp_region
  depends_on = [
    google_project_iam_member.event-receiving,
    google_secret_manager_secret_iam_member.secret_iam_member,
  ]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_reverse_geolocation_config.entry_point}_processor"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.reverse_geolocation_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PYTHONNODEBUGRANGES = 0
      PROJECT_ID = var.project_id
      GCP_REGION = var.gcp_region
      ENVIRONMENT = var.environment
      MATERIALIZED_VIEW_QUEUE = google_cloud_tasks_queue.refresh_materialized_view_task_queue.name
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email
      DATASETS_BUCKET_NAME_GTFS = "${var.datasets_bucket_name}-${var.environment}"
      DATASETS_BUCKET_NAME_GBFS = "${var.gbfs_bucket_name}-${var.environment}"
    }
    available_memory = local.function_reverse_geolocation_config.available_memory
    timeout_seconds = 1700
    available_cpu = local.function_reverse_geolocation_config.available_cpu
    max_instance_request_concurrency = local.function_reverse_geolocation_config.max_instance_request_concurrency
    max_instance_count = 10
    min_instance_count = local.function_reverse_geolocation_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_reverse_geolocation_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_reverse_geolocation_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 13.2 reverse_geolocation task queue
resource "google_cloud_tasks_queue" "reverse_geolocation_task_queue_processor" {
  location = var.gcp_region
  name     = "reverse-geolocation-processor-task-queue"
  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 1
  }
  retry_config {
      max_attempts  = 10
      min_backoff   = "20s"
      max_backoff   = "60s"
  }
}

# Grant execution permission to bathcfunctions service account to the reverse_geolocation_processor function
resource "google_cloudfunctions2_function_iam_member" "reverse_geolocation_processor_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.reverse_geolocation_processor.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${local.batchfunctions_sa_email}"
}

# Grant execution permission to batchfunctions service account to the pmtiles_builder function
resource "google_cloudfunctions2_function_iam_member" "pmtiles_builder_invoker_batch_sa" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.pmtiles_builder.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${local.batchfunctions_sa_email}"
}

# Grant execution permission to the service account to the pmtiles_builder function
resource "google_cloudfunctions2_function_iam_member" "pmtiles_builder_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.pmtiles_builder.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# 13.3 functions/reverse_geolocation - batch cloud function
resource "google_cloudfunctions2_function" "reverse_geolocation_batch" {
  name        = "${local.function_reverse_geolocation_config.name}-batch"
  description = local.function_reverse_geolocation_config.description
  location    = var.gcp_region
  depends_on = [
    google_project_iam_member.event-receiving,
    google_secret_manager_secret_iam_member.secret_iam_member
  ]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_reverse_geolocation_config.entry_point}_batch"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.reverse_geolocation_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PYTHONNODEBUGRANGES = 0
      PROJECT_ID = var.project_id
      DATASETS_BUCKET_NAME = "${var.datasets_bucket_name}-${var.environment}"
      QUEUE_NAME = google_cloud_tasks_queue.reverse_geolocation_task_queue_processor.name
      GCP_REGION = var.gcp_region
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email
    }
    available_memory = local.function_reverse_geolocation_config.available_memory
    timeout_seconds = local.function_reverse_geolocation_config.timeout
    available_cpu = local.function_reverse_geolocation_config.available_cpu
    max_instance_request_concurrency = local.function_reverse_geolocation_config.max_instance_request_concurrency
    max_instance_count = local.function_reverse_geolocation_config.max_instance_count
    min_instance_count = local.function_reverse_geolocation_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_reverse_geolocation_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_reverse_geolocation_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# Task queue to invoke pmtiles_builder function
resource "google_cloud_tasks_queue" "pmtiles_builder_task_queue" {
  project  = var.project_id
  location = var.gcp_region
  name     = "pmtiles-builder-queue-${var.environment}-${local.deployment_timestamp}"

  rate_limits {
    max_concurrent_dispatches = 20
    max_dispatches_per_second = 1
  }

  retry_config {
    # This will make the cloud task retry for ~1 hour
    max_attempts  = 31
    min_backoff   = "120s"
    max_backoff   = "120s"
    max_doublings = 2
  }
}


# 14. functions/tasks_executor cloud function
resource "google_cloudfunctions2_function" "tasks_executor" {
  name        = "${local.function_tasks_executor_config.name}-${var.environment}"
  project     = var.project_id
  description = local.function_tasks_executor_config.description
  location    = var.gcp_region
  depends_on  = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_tasks_executor_config.entry_point}"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.tasks_executor_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID  = var.project_id
      ENVIRONMENT = var.environment
      BOUNDING_BOXES_PUBSUB_TOPIC_NAME = google_pubsub_topic.rebuild_missing_bounding_boxes.name
      DATASET_PROCESSING_TOPIC_NAME = "datasets-batch-topic-${var.environment}"
      MATERIALIZED_VIEW_QUEUE = google_cloud_tasks_queue.refresh_materialized_view_task_queue.name
      DATASETS_BUCKET_NAME = "${var.datasets_bucket_name}-${var.environment}"
      GBFS_SNAPSHOTS_BUCKET_NAME = google_storage_bucket.gbfs_snapshots_bucket.name
      PMTILES_BUILDER_QUEUE = google_cloud_tasks_queue.pmtiles_builder_task_queue.name
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email
      GCP_REGION = var.gcp_region
    }
    available_memory                 = local.function_tasks_executor_config.memory
    timeout_seconds                  = local.function_tasks_executor_config.timeout
    available_cpu                    = local.function_tasks_executor_config.available_cpu
    max_instance_request_concurrency = local.function_tasks_executor_config.max_instance_request_concurrency
    max_instance_count               = local.function_tasks_executor_config.max_instance_count
    min_instance_count               = local.function_tasks_executor_config.min_instance_count
    service_account_email            = google_service_account.functions_service_account.email
    ingress_settings                 = "ALLOW_ALL"
    vpc_connector                    = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings    = "PRIVATE_RANGES_ONLY"

    dynamic "secret_environment_variables" {
      for_each = local.function_tasks_executor_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
  }
}

# Grant execution permission to bathcfunctions service account to the tasks_executor function
resource "google_cloudfunctions2_function_iam_member" "tasks_executor_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.tasks_executor.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${local.batchfunctions_sa_email}"
}

# 15. functions/pmtiles_builder cloud function
resource "google_cloudfunctions2_function" "pmtiles_builder" {
  name        = "${local.function_pmtiles_builder_config.name}-${var.environment}"
  project     = var.project_id
  description = local.function_pmtiles_builder_config.description
  location    = var.gcp_region
  depends_on  = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_pmtiles_builder_config.entry_point}"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.pmtiles_builder_zip.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID  = var.project_id
      ENV = var.environment
      PUBSUB_TOPIC_NAME = "rebuild-bounding-boxes-topic"
      MATERIALIZED_VIEW_QUEUE = google_cloud_tasks_queue.refresh_materialized_view_task_queue.name
      DATASETS_BUCKET_NAME = "${var.datasets_bucket_name}-${var.environment}"
    }
    available_memory                 = local.function_pmtiles_builder_config.memory
    timeout_seconds                  = local.function_pmtiles_builder_config.timeout
    available_cpu                    = local.function_pmtiles_builder_config.available_cpu
    max_instance_request_concurrency = local.function_pmtiles_builder_config.max_instance_request_concurrency
    max_instance_count               = local.function_pmtiles_builder_config.max_instance_count
    min_instance_count               = local.function_pmtiles_builder_config.min_instance_count
    service_account_email            = google_service_account.functions_service_account.email
    ingress_settings                 = "ALLOW_ALL"
    vpc_connector                    = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings    = "PRIVATE_RANGES_ONLY"

    dynamic "secret_environment_variables" {
      for_each = local.function_pmtiles_builder_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = lookup(secret_environment_variables.value, "secret", "${upper(var.environment)}_${secret_environment_variables.value["key"]}")
        version    = "latest"
      }
    }
  }
}

# Create the Pub/Sub topic used for publishing messages about rebuilding missing bounding boxes
resource "google_pubsub_topic" "rebuild_missing_bounding_boxes" {
  name = "rebuild-bounding-boxes-topic"
}

# Grant the Cloud Functions service account permission to publish messages to the rebuild-bounding-boxes-topic Pub/Sub topic
resource "google_pubsub_topic_iam_member" "rebuild_missing_bounding_boxes_publisher" {
  topic  = google_pubsub_topic.rebuild_missing_bounding_boxes.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# IAM entry for all users to invoke the function
resource "google_cloudfunctions2_function_iam_member" "tokens_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.tokens.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

resource "google_cloud_run_service_iam_member" "tokens_cloud_run_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  service        = google_cloudfunctions2_function.tokens.name
  role           = "roles/run.invoker"
  member         = "allUsers"
}

# Allow Operations API function to be called by all users
resource "google_cloudfunctions2_function_iam_member" "operations_api_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.operations_api.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

resource "google_cloud_run_service_iam_member" "operastions_cloud_run_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  service        = google_cloudfunctions2_function.operations_api.name
  role           = "roles/run.invoker"
  member         = "allUsers"
}

# Permissions on the service account used by the function and Eventarc trigger
resource "google_project_iam_member" "invoking" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_project_iam_member" "event-receiving" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
  depends_on = [google_project_iam_member.invoking]
}

# Grant read access to the datasets bucket for the service account
resource "google_storage_bucket_iam_binding" "bucket_object_viewer" {
  for_each = {
    datasets_bucket = "${var.datasets_bucket_name}-${var.environment}"
  }
  bucket = each.value
  depends_on = []
  role   = "roles/storage.objectViewer"
  members = [
    "serviceAccount:${google_service_account.functions_service_account.email}"
  ]
}

# Grant write access to the bucket for the service account - objects
resource "google_storage_bucket_iam_binding" "bucket_object_creator" {
  for_each = {
    gbfs_snapshots_bucket = google_storage_bucket.gbfs_snapshots_bucket.name
  }
  depends_on = [google_storage_bucket.gbfs_snapshots_bucket]
  bucket = each.value
  role   = "roles/storage.objectCreator"
  members = [
    "serviceAccount:${google_service_account.functions_service_account.email}"
  ]
}

# Grant access to the bucket for the service account - bucket
resource "google_storage_bucket_iam_binding" "storage_admin" {
  for_each = {
    datasets_bucket = "${var.datasets_bucket_name}-${var.environment}"
  }
  depends_on = [google_storage_bucket.gbfs_snapshots_bucket]
  bucket = each.value
  role   = "roles/storage.admin"
  members = [
    "serviceAccount:${google_service_account.functions_service_account.email}"
  ]
}

# Grant the service account the ability to invoke the workflows
resource "google_project_iam_member" "workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_project_iam_audit_config" "all-services" {
  project = var.project_id
  service = "allServices"
  audit_log_config {
    log_type = "ADMIN_READ"
  }
  audit_log_config {
    log_type = "DATA_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

# Grant the service account the ability to enqueue tasks
resource "google_project_iam_member" "queue_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}


output "function_tokens_name" {
  value = google_cloudfunctions2_function.tokens.name
}


# Task queue to invoke update_validation_report function
resource "google_cloud_tasks_queue" "update_validation_report_task_queue" {
  project  = var.project_id
  location = var.gcp_region
  name     = "update-validation-report-task-queue"

  rate_limits {
    max_concurrent_dispatches = 1
    max_dispatches_per_second = 1
  }

  retry_config {
    # This will make the cloud task retry for ~1 hour
    max_attempts  = 31
    min_backoff   = "120s"
    max_backoff   = "120s"
    max_doublings = 2
  }
}

# Task queue to invoke refresh_materialized_view function
resource "google_cloud_tasks_queue" "refresh_materialized_view_task_queue" {
  project  = var.project_id
  location = var.gcp_region
  name     = "refresh-materialized-view-task-queue-${var.environment}-${local.deployment_timestamp}"

  rate_limits {
    max_concurrent_dispatches = 1
    max_dispatches_per_second = 0.5
  }

  retry_config {
    # ~22 minutes total: 120 + 240 + 480 + 480 = 1320s (initial attempt + 4 retries)
    max_attempts  = 5
    min_backoff   = "120s"
    max_backoff   = "480s"
    max_doublings = 2
  }
}

# Task queue to invoke gbfs_validator_batch function for the scheduler
resource "google_cloudfunctions2_function_iam_member" "gbfs_validator_batch_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.gbfs_validator_batch.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_cloudfunctions2_function_iam_member" "transitland_feeds_dispatcher_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.feed_sync_dispatcher_transitland.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Grant permissions to the service account to publish to the pubsub topic
resource "google_pubsub_topic_iam_member" "functions_publisher" {
  for_each = {
    validate_gbfs_feed = google_pubsub_topic.validate_gbfs_feed.name
    feed_sync_dispatcher_transitland = google_pubsub_topic.transitland_feeds_dispatch.name
    dataset_batch = data.google_pubsub_topic.datasets_batch_topic.name
  }

  project = var.project_id
  role    = "roles/pubsub.publisher"
  topic   = each.value
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Grant permissions to the service account to subscribe to the pubsub topic
resource "google_pubsub_topic_iam_member" "functions_subscriber" {
  for_each = {
    validate_gbfs_feed = google_pubsub_topic.validate_gbfs_feed.name
    feed_sync_dispatcher_transitland = google_pubsub_topic.transitland_feeds_dispatch.name
  }

  project = var.project_id
  role    = "roles/pubsub.subscriber"
  topic   = each.value
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Grant permissions to the service account to write/read in datastore
resource "google_project_iam_member" "datastore_owner" {
  project = var.project_id
  role    = "roles/datastore.owner"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

#TODO: Check this
resource "google_cloudfunctions2_function_iam_member" "export_csv_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.export_csv.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_cloudfunctions2_function_iam_member" "update_feed_status_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.update_feed_status.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Grant permissions to the service account to create bigquery jobs
resource "google_project_iam_member" "bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# This permission is added to allow the function to act as the service account and generate tokens.
resource "google_project_iam_member" "service_account_workflow_act_as_binding" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser" #iam.serviceAccounts.actAs
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}