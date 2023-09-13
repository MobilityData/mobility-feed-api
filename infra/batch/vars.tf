terraform {
  backend "gcs" {
  }
}

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

variable "source_code_path" {
  type        = string
  description = "Path for the source code zip file"
}

variable "source_code_zip_file" {
  type        = string
  description = "Name of the source code zip file"
}

variable "http_function_name" {
  type        = string
  description = "Name for the batch http function"
}

variable "pubsub_function_name" {
  type        = string
  description = "Name for the batch pubsub function"
}

variable "runtime" {
  type        = string
  description = "Runtime version of Python for functions"
}

variable "http_entry_point" {
  type        = string
  description = "Entry point for the batch http function"
}

variable "pubsub_entry_point" {
  type        = string
  description = "Entry point for the pubsub function"
}

variable "available_memory" {
  type        = string
  description = "Available memory for functions"
}

variable "available_cpu" {
  type        = string
  description = "Available CPU for functions"
}

variable "pubsub_timeout_seconds" {
  type        = number
  description = "Timeout seconds for the pubsub function"
}

variable "http_timeout_seconds" {
  type        = number
  description = "Timeout seconds for the http function"
}

variable "max_instance_count" {
  type        = number
  description = "Maximum instance count for the PubSub function"
}

variable "job_name" {
  type        = string
  description = "Name for the scheduler job"
}

variable "job_description" {
  type        = string
  description = "Description for the scheduler job"
}

variable "job_schedule" {
  type        = string
  description = "Schedule for the scheduler job"
}

variable "job_attempt_deadline" {
  type        = string
  description = "Attempt deadline for the scheduler job"
}

variable "http_method" {
  type        = string
  description = "HTTP method for the scheduler job"
}

variable "pubsub_topic_name" {
  type        = string
  description = "PubSub topic name used by the PubSub function"
}

variable "create_pubsub_function" {
  type        = bool
  default     = true
  description = "Flag to control the creation of the resource"
}