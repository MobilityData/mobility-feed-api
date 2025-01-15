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
  function_tokens_config = jsondecode(file("${path.module}../../../functions-python/tokens/function_config.json"))
  function_tokens_zip    = "${path.module}/../../functions-python/tokens/.dist/tokens.zip"

  function_extract_location_config = jsondecode(file("${path.module}../../../functions-python/extract_location/function_config.json"))
  function_extract_location_zip    = "${path.module}/../../functions-python/extract_location/.dist/extract_location.zip"
  #  DEV and QA use the vpc connector
  vpc_connector_name = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id

  function_process_validation_report_config = jsondecode(file("${path.module}/../../functions-python/validation_report_processor/function_config.json"))
  function_process_validation_report_zip = "${path.module}/../../functions-python/validation_report_processor/.dist/validation_report_processor.zip"
  public_hosted_datasets_url = lower(var.environment) == "prod" ? "https://${var.public_hosted_datasets_dns}" : "https://${var.environment}-${var.public_hosted_datasets_dns}"

  function_update_validation_report_config = jsondecode(file("${path.module}/../../functions-python/update_validation_report/function_config.json"))
  function_update_validation_report_zip = "${path.module}/../../functions-python/update_validation_report/.dist/update_validation_report.zip"

  function_gbfs_validation_report_config = jsondecode(file("${path.module}/../../functions-python/gbfs_validator/function_config.json"))
  function_gbfs_validation_report_zip = "${path.module}/../../functions-python/gbfs_validator/.dist/gbfs_validator.zip"

  function_feed_sync_dispatcher_transitland_config = jsondecode(file("${path.module}/../../functions-python/feed_sync_dispatcher_transitland/function_config.json"))
  function_feed_sync_dispatcher_transitland_zip = "${path.module}/../../functions-python/feed_sync_dispatcher_transitland/.dist/feed_sync_dispatcher_transitland.zip"

  function_feed_sync_process_transitland_config = jsondecode(file("${path.module}/../../functions-python/feed_sync_process_transitland/function_config.json"))
  function_feed_sync_process_transitland_zip = "${path.module}/../../functions-python/feed_sync_process_transitland/.dist/feed_sync_process_transitland.zip"

  function_operations_api_config = jsondecode(file("${path.module}/../../functions-python/operations_api/function_config.json"))
  function_operations_api_zip = "${path.module}/../../functions-python/operations_api/.dist/operations_api.zip"

  function_export_csv_config = jsondecode(file("${path.module}/../../functions-python/export_csv/function_config.json"))
  function_export_csv_zip = "${path.module}/../../functions-python/export_csv/.dist/export_csv.zip"

}

locals {
  # To allow multiple functions to access the same secrets, we need to combine all the keys from the different functions
  # Combine all keys into a list
  all_secret_keys_list = concat(
    [for x in local.function_tokens_config.secret_environment_variables : x.key],
    [for x in local.function_extract_location_config.secret_environment_variables : x.key],
    [for x in local.function_process_validation_report_config.secret_environment_variables : x.key],
    [for x in local.function_update_validation_report_config.secret_environment_variables : x.key],
    [for x in local.function_export_csv_config.secret_environment_variables : x.key]
  )

  # Convert the list to a set to ensure uniqueness
  unique_secret_keys = toset(local.all_secret_keys_list)
}

data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

data "google_pubsub_topic" "datasets_batch_topic" {
  name = "datasets-batch-topic-${var.environment}"
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
}

# Cloud function source code zip files:
# 1. Tokens
resource "google_storage_bucket_object" "function_token_zip" {
  name   = "tokens-${substr(filebase64sha256(local.function_tokens_zip),0,10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_tokens_zip
}
# 2. Extract location
resource "google_storage_bucket_object" "function_extract_location_zip_object" {
  name   = "bucket-extract-bb-${substr(filebase64sha256(local.function_extract_location_zip),0,10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_extract_location_zip
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

# 9. Export CSV
resource "google_storage_bucket_object" "export_csv_zip" {
  bucket = google_storage_bucket.functions_bucket.name
  name   = "export-csv-${substr(filebase64sha256(local.function_export_csv_zip), 0, 10)}.zip"
  source = local.function_export_csv_zip
}

# Secrets access
resource "google_secret_manager_secret_iam_member" "secret_iam_member" {
  for_each = local.unique_secret_keys

  project    = var.project_id
  # The secret_id is the current item in the set. Since these are unique keys, we use each.value to access it.
  secret_id  = "${upper(var.environment)}_${each.value}"
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

# 2.1 functions/extract_location cloud function
resource "google_cloudfunctions2_function" "extract_location" {
  name        = local.function_extract_location_config.name
  description = local.function_extract_location_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]
  event_trigger {
    event_type = "google.cloud.audit.log.v1.written"
    service_account_email = google_service_account.functions_service_account.email
    event_filters {
      attribute = "serviceName"
      value = "storage.googleapis.com"
    }
    event_filters {
      attribute = "methodName"
      value = "storage.objects.create"
    }
    event_filters {
      attribute = "resourceName"
      value     = "projects/_/buckets/mobilitydata-datasets-${var.environment}/objects/*/*/*.zip"
      operator = "match-path-pattern"
    }
  }
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_extract_location_config.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.function_extract_location_zip_object.name
      }
    }
  }
  service_config {
    available_memory = local.function_extract_location_config.memory
    timeout_seconds = local.function_extract_location_config.timeout
    available_cpu = local.function_extract_location_config.available_cpu
    max_instance_request_concurrency = local.function_extract_location_config.max_instance_request_concurrency
    max_instance_count = local.function_extract_location_config.max_instance_count
    min_instance_count = local.function_extract_location_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = local.function_extract_location_config.ingress_settings
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_extract_location_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 2.2 functions/extract_location cloud function pub/sub triggered
resource "google_pubsub_topic" "dataset_updates" {
  name = "dataset-updates"
}
resource "google_cloudfunctions2_function" "extract_location_pubsub" {
  name        = "${local.function_extract_location_config.name}-pubsub"
  description = local.function_extract_location_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]
  event_trigger {
    trigger_region        = var.gcp_region
    service_account_email = google_service_account.functions_service_account.email
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.dataset_updates.id
    retry_policy          = "RETRY_POLICY_RETRY"
  }
  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_extract_location_config.entry_point}_pubsub"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.function_extract_location_zip_object.name
      }
    }
  }
  service_config {
    available_memory = local.function_extract_location_config.memory
    timeout_seconds = local.function_extract_location_config.timeout
    available_cpu = local.function_extract_location_config.available_cpu
    max_instance_request_concurrency = local.function_extract_location_config.max_instance_request_concurrency
    max_instance_count = local.function_extract_location_config.max_instance_count
    min_instance_count = local.function_extract_location_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_extract_location_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 2.3 functions/extract_location cloud function batch
resource "google_cloudfunctions2_function" "extract_location_batch" {
  name        = "${local.function_extract_location_config.name}-batch"
  description = local.function_extract_location_config.description
  location    = var.gcp_region
  depends_on = [google_project_iam_member.event-receiving, google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_extract_location_config.entry_point}_batch"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.function_extract_location_zip_object.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      PUBSUB_TOPIC_NAME = google_pubsub_topic.dataset_updates.name
      PYTHONNODEBUGRANGES = 0
    }
    available_memory = "1Gi"
    timeout_seconds = local.function_extract_location_config.timeout
    available_cpu = local.function_extract_location_config.available_cpu
    max_instance_request_concurrency = local.function_extract_location_config.max_instance_request_concurrency
    max_instance_count = local.function_extract_location_config.max_instance_count
    min_instance_count = local.function_extract_location_config.min_instance_count
    service_account_email = google_service_account.functions_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_extract_location_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }
}

# 3. functions/validation_report_processor cloud function
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

# 6. functions/export_csv cloud function
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
      DATASETS_BUCKET_NANE = var.datasets_bucket_name
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
      for_each    = local.function_export_csv_config.secret_environment_variables
      PROJECT_ID  = var.project_id
      ENVIRONMENT = var.environment
    }
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
      for_each = local.function_extract_location_config.secret_environment_variables
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
  bucket = "${var.datasets_bucket_name}-${var.environment}"
  role   = "roles/storage.objectViewer"
  members = [
    "serviceAccount:${google_service_account.functions_service_account.email}"
  ]
}

# Grant write access to the gbfs bucket for the service account
resource "google_storage_bucket_iam_binding" "gbfs_bucket_object_creator" {
  bucket = google_storage_bucket.gbfs_snapshots_bucket.name
  role   = "roles/storage.objectCreator"
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

output "function_tokens_name" {
  value = google_cloudfunctions2_function.tokens.name
}

resource "google_cloudfunctions2_function_iam_member" "extract_location_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  cloud_function = google_cloudfunctions2_function.extract_location.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_cloud_run_service_iam_member" "extract_location_cloud_run_invoker" {
  project        = var.project_id
  location       = var.gcp_region
  service        = google_cloudfunctions2_function.extract_location.name
  role           = "roles/run.invoker"
  member         = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# Task queue to invoke update_validation_report function
resource "google_cloud_tasks_queue" "update_validation_report_task_queue" {
  project  = var.project_id
  location = var.gcp_region
  name     = "update-validation-report-task-queue"
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
    dataset_updates = google_pubsub_topic.dataset_updates.name
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
    dataset_updates = google_pubsub_topic.dataset_updates.name
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