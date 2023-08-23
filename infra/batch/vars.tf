variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "gcp_region" {
  type        = string
  description = "GCP region"
}

variable "bucket_name" {
  type        = string
  description = "GCS bucket name where the Python code is stored"
}

variable "deployer_service_account" {
  type        = string
  description = "Service account used to deploy resources using impersonation"
}

variable "function_env_variables" {
  description = "Environment variables for the cloud function"
  type        = map(string)
  default     = {}
}

