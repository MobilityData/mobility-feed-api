locals {
  function_process_validation_report_config = jsondecode(file("${path.module}/../../functions-python/validation_report_processor/function_config.json"))
  function_process_validation_report_zip = "${path.module}/../../functions-python/validation_report_processor/.dist/validation_report_processor.zip"

  # TODO: do not add the following line to the final code
  vpc_connector_name = lower(var.environment) == "dev" ? "vpc-connector-qa" : "vpc-connector-${lower(var.environment)}"
  vpc_connector_project = lower(var.environment) == "dev" ? "mobility-feeds-qa" : var.project_id

  public_hosted_datasets_url = lower(var.environment) == "prod" ? "https://${var.public_hosted_datasets_dns}" : "https://${var.environment}-${var.public_hosted_datasets_dns}"
}

# TODO: do not add the following line to the final code
data "google_vpc_access_connector" "vpc_connector" {
  name    = local.vpc_connector_name
  region  = var.gcp_region
  project = local.vpc_connector_project
}

# TODO: do not add the following line to the final code
data "google_service_account" "functions_service_account" {
  account_id = "functions-service-account"
  project    = var.project_id
}

# TODO: do not add the following line to the final code
data "google_storage_bucket" "functions_bucket" {
  name     = "mobility-feeds-functions-python-${var.environment}"
}

# Process validation report (zip)
resource "google_storage_bucket_object" "process_validation_report_zip" {
  bucket = data.google_storage_bucket.functions_bucket.name
  name   = "process-validation-report-${substr(filebase64sha256(local.function_process_validation_report_zip), 0, 10)}.zip"
  source = local.function_process_validation_report_zip
}

# Secrets access for process validation report
# TODO: this should be moved to concat of secret_environment_variables
#resource "google_secret_manager_secret_iam_member" "secret_iam_member" {
#  for_each = {
#    for x in concat(local.function_process_validation_report_config.secret_environment_variables) :
#    x.key => x
#  }
#
#  project    = var.project_id
#  secret_id  = lookup(each.value, "secret", "${upper(var.environment)}_${each.key}")
#  role       = "roles/secretmanager.secretAccessor"
#  member     = "serviceAccount:${data.google_service_account.functions_service_account.email}"
#}

# Process validation report function
resource "google_cloudfunctions2_function" "process_validation_report" {
  name        = local.function_process_validation_report_config.name
  description = local.function_process_validation_report_config.description
  location    = var.gcp_region
#  TODO: uncomment the following line
#  depends_on = [google_secret_manager_secret_iam_member.secret_iam_member]
  project = var.project_id
  build_config {
    runtime     = var.python_runtime
    entry_point = local.function_process_validation_report_config.entry_point
    source {
      storage_source {
        bucket = data.google_storage_bucket.functions_bucket.name
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
      # TODO: validate if the following line is necessary
      PROJECT_ID        = var.project_id
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
    service_account_email            = data.google_service_account.functions_service_account.email
    max_instance_request_concurrency = local.function_process_validation_report_config.max_instance_request_concurrency
    max_instance_count               = local.function_process_validation_report_config.max_instance_count
    min_instance_count               = local.function_process_validation_report_config.min_instance_count
  }
}