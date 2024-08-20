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
    # BigQuery data ingestion function config
    function_big_query_ingest_config = jsondecode(file("${path.module}/../../functions-python/big_query_ingestion/function_config.json"))
    function_big_query_ingest_zip = "${path.module}/../../functions-python/big_query_ingestion/.dist/big_query_ingestion.zip"

    #  DEV and QA use the vpc connector
    vpc_connector_name = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
    vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id
}

locals {
  # To allow multiple functions to access the same secrets, we need to combine all the keys from the different functions
  # Combine all keys into a list
  all_secret_keys_list = concat(
    [for x in local.function_big_query_ingest_config.secret_environment_variables : x.key],
  )

  # Convert the list to a set to ensure uniqueness
  unique_secret_keys = toset(local.all_secret_keys_list)
}

# Service account for the metrics
resource "google_service_account" "metrics_service_account" {
    account_id   = "metrics-service-account"
    display_name = "Metrics Service Account"
    project = var.project_id
}

# Secrets access
resource "google_secret_manager_secret_iam_member" "secret_iam_member" {
  for_each = local.unique_secret_keys

  project    = var.project_id
  # The secret_id is the current item in the set. Since these are unique keys, we use each.value to access it.
  secret_id  = "${upper(var.environment)}_${each.value}"
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.metrics_service_account.email}"
}

data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

resource "google_storage_bucket" "functions_bucket" {
  name     = "mobility-feeds-metrics-source-${var.environment}"
  location = "us"
  project = var.project_id
}

# GTFS - Big Query data ingestion function
# 1. Source code storage
resource "google_storage_bucket_object" "gtfs_big_query_ingest_function" {
  name   = "gtfs-big-query-ingest-${substr(filebase64sha256(local.function_big_query_ingest_zip),0,10)}.zip"
  bucket = google_storage_bucket.functions_bucket.name
  source = local.function_big_query_ingest_zip
}

# 2. Cloud Function
# 2.1. GTFS - Big Query data ingestion function
resource "google_cloudfunctions2_function" "gtfs_big_query_ingest" {
  name        = "${local.function_big_query_ingest_config.name}-gtfs"
  project     = var.project_id
  description = local.function_big_query_ingest_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_big_query_ingest_config.entry_point}_gtfs"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.gtfs_big_query_ingest_function.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      BUCKET_NAME = data.google_storage_bucket.gtfs_datasets_bucket.name
      DATASET_ID = var.dataset_id
      TABLE_ID = var.gtfs_table_id
      BQ_DATASET_LOCATION = var.gcp_region
      PYTHONNODEBUGRANGES = 0
    }
    available_memory = local.function_big_query_ingest_config.memory
    timeout_seconds = local.function_big_query_ingest_config.timeout
    available_cpu = local.function_big_query_ingest_config.available_cpu
    max_instance_request_concurrency = local.function_big_query_ingest_config.max_instance_request_concurrency
    max_instance_count = local.function_big_query_ingest_config.max_instance_count
    min_instance_count = local.function_big_query_ingest_config.min_instance_count
    service_account_email = google_service_account.metrics_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_big_query_ingest_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }

}

# 2.2. GBFS - Big Query data ingestion function
resource "google_cloudfunctions2_function" "gbfs_big_query_ingest" {
  name        = "${local.function_big_query_ingest_config.name}-gbfs"
  project     = var.project_id
  description = local.function_big_query_ingest_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]

  build_config {
    runtime     = var.python_runtime
    entry_point = "${local.function_big_query_ingest_config.entry_point}_gbfs"
    source {
      storage_source {
        bucket = google_storage_bucket.functions_bucket.name
        object = google_storage_bucket_object.gtfs_big_query_ingest_function.name
      }
    }
  }
  service_config {
    environment_variables = {
      PROJECT_ID = var.project_id
      BUCKET_NAME = data.google_storage_bucket.gbfs_snapshots_bucket.name
      DATASET_ID = var.dataset_id
      TABLE_ID = var.gbfs_table_id
      BQ_DATASET_LOCATION = var.gcp_region
      PYTHONNODEBUGRANGES = 0
    }
    available_memory = local.function_big_query_ingest_config.memory
    timeout_seconds = local.function_big_query_ingest_config.timeout
    available_cpu = local.function_big_query_ingest_config.available_cpu
    max_instance_request_concurrency = local.function_big_query_ingest_config.max_instance_request_concurrency
    max_instance_count = local.function_big_query_ingest_config.max_instance_count
    min_instance_count = local.function_big_query_ingest_config.min_instance_count
    service_account_email = google_service_account.metrics_service_account.email
    ingress_settings = "ALLOW_ALL"
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
    dynamic "secret_environment_variables" {
      for_each = local.function_big_query_ingest_config.secret_environment_variables
      content {
        key        = secret_environment_variables.value["key"]
        project_id = var.project_id
        secret     = "${upper(var.environment)}_${secret_environment_variables.value["key"]}"
        version    = "latest"
      }
    }
  }

}


# Grant permissions to the service account
# 1. BigQuery roles
resource "google_project_iam_member" "big_query_data_editor_permissions" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.metrics_service_account.email}"
}
resource "google_project_iam_member" "big_query_job_user_permissions" {
  member  = "serviceAccount:${google_service_account.metrics_service_account.email}"
  project = var.project_id
  role    = "roles/bigquery.jobUser"
}

# 2. Storage roles
resource "google_project_iam_member" "storage_object_creator_permissions" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.metrics_service_account.email}"
}
data "google_storage_bucket" "gtfs_datasets_bucket" {
  name = "${var.gtfs_datasets_storage_bucket}-${var.environment}"
}
data "google_storage_bucket" "gbfs_snapshots_bucket" {
  name = "${var.gbfs_snapshots_storage_bucket}-${var.environment}"
}

resource "google_storage_bucket_iam_member" "datasets_bucket_functions_service_account" {
  bucket = data.google_storage_bucket.gtfs_datasets_bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.metrics_service_account.email}"
}

resource "google_storage_bucket_iam_member" "snapshots_bucket_functions_service_account" {
  bucket = data.google_storage_bucket.gbfs_snapshots_bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.metrics_service_account.email}"
}

