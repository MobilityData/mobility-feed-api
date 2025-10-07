terraform {
  backend "gcs" {
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.34.0"
    }
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
  #  DEV and QA use the vpc connector
  vpc_connector_name = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id
#  Files DNS name
  public_hosted_datasets_url = lower(var.environment) == "prod" ? "https://${var.public_hosted_datasets_dns}" : "https://${var.environment}-${var.public_hosted_datasets_dns}"
  # 1day=86400, 7days=604800, 31days=2678400
  retention_duration_seconds = lower(var.environment) == "prod" ? 2678400 : 604800

  deployment_timestamp = formatdate("YYYYMMDDhhmmss", timestamp())

  function_pmtiles_builder_config = jsondecode(file("${path.module}/../../functions-python/pmtiles_builder/function_config.json"))
}

data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

# This resource maps an already created SSL certificate to a terraform state resource.
# The SSL setup is done outside terraform for security reasons.
data "google_compute_ssl_certificate" "files_ssl_cert" {
  name = "files-${var.environment}-mobilitydatabase"
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
  location = var.gcp_region
  uniform_bucket_level_access = false
  autoclass {
    enabled = true
  }
  soft_delete_policy {
    retention_duration_seconds = local.retention_duration_seconds
  }
  cors {
    origin = ["*"]
    method = ["GET"]
    response_header = ["*"]
  }
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
  name     = "mobility-feeds-batch-python-${var.environment}"
  location = var.gcp_region
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

# Grant permissions to the service account to access the secrets based on the function config
resource "google_secret_manager_secret_iam_member" "secret_iam_member" {
  for_each = {
    for x in local.function_batch_process_dataset_config.secret_environment_variables : x.key => x
  }

  project    = var.project_id
  secret_id  = lookup(each.value, "secret", "${upper(var.environment)}_${each.value["key"]}")
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.functions_service_account.email}"
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
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
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
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

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

# Grant the batch functions service account permission to enqueue Cloud Tasks
resource "google_project_iam_member" "queue_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

# This permission is added to allow the function to act as the service account and generate tokens.
resource "google_project_iam_member" "service_account_workflow_act_as_binding" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser" #iam.serviceAccounts.actAs
  member  = "serviceAccount:${google_service_account.functions_service_account.email}"
}

resource "google_pubsub_topic" "pubsub_topic" {
  name = "datasets-batch-topic-${var.environment}"
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


# Batch process dataset function
resource "google_cloudfunctions2_function" "pubsub_function" {
  name        = "${local.function_batch_process_dataset_config.name}-${var.environment}"
  description = local.function_batch_process_dataset_config.description
  location    = var.gcp_region
  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]

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
    vpc_connector = data.google_vpc_access_connector.vpc_connector.id
    vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

    environment_variables = {
      DATASETS_BUCKET_NAME = google_storage_bucket.datasets_bucket.name
      # prevents multiline logs from being truncated on GCP console
      PYTHONNODEBUGRANGES = 0
      DB_REUSE_SESSION    = "True"
      ENVIRONMENT         = var.environment
      PUBLIC_HOSTED_DATASETS_URL = local.public_hosted_datasets_url
      PROJECT_ID = var.project_id
      GCP_REGION = var.gcp_region
      SERVICE_ACCOUNT_EMAIL = google_service_account.functions_service_account.email
      MATERIALIZED_VIEW_QUEUE = google_cloud_tasks_queue.refresh_materialized_view_task_queue.name
      PMTILES_BUILDER_QUEUE = google_cloud_tasks_queue.pmtiles_builder_task_queue.name
      REVERSE_GEOLOCATION_QUEUE = "reverse-geolocation-processor-task-queue"
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

# Task queue to invoke refresh_materialized_view 
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

resource "google_compute_backend_bucket" "files_backend" {
  name       = "datasets-backend-${var.environment}"
  bucket_name = google_storage_bucket.datasets_bucket.name
  enable_cdn  = false
}

resource "google_compute_url_map" "files_url_map" {
  name            = "files-url-map-${var.environment}"
  default_service = google_compute_backend_bucket.files_backend.id
  host_rule {
    hosts        = ["*"]
    path_matcher = "allpaths"

  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_bucket.files_backend.id
  }
}

resource "google_compute_target_https_proxy" "files_https_proxy" {
  name             = "files-proxy-${var.environment}"
  url_map          = google_compute_url_map.files_url_map.id
  ssl_certificates = [data.google_compute_ssl_certificate.files_ssl_cert.id]
}

data "google_compute_global_address" "files_http_lb_ipv4" {
  name         = "files-http-lb-ipv4-static-${var.environment}"
}

data "google_compute_global_address" "files_http_lb_ipv6" {
  name         = "files-http-lb-ipv6-static-${var.environment}"
}

resource "google_compute_global_forwarding_rule" "files_http_lb_rule" {
  name                  = "files-http-lb-rule-${var.environment}"
  target                = google_compute_target_https_proxy.files_https_proxy.self_link
  port_range            = "443"
  ip_address            = data.google_compute_global_address.files_http_lb_ipv6.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "files_http_lb_rule_ipv4" {
  name                  = "files-http-lb-rule-v4-${var.environment}"
  target                = google_compute_target_https_proxy.files_https_proxy.self_link
  port_range            = "443"
  ip_address            = data.google_compute_global_address.files_http_lb_ipv4.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_cloud_run_service_iam_member" "pmtiles_builder_invoker" {
  project  = var.project_id
  location = var.gcp_region
  service  = "${local.function_pmtiles_builder_config.name}-${var.environment}"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions_service_account.email}"
}