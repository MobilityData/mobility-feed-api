variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "gcp_region" {
  type        = string
  description = "GCP region"
}

variable "environment" {
  type        = string
  description = "API environment. Possible values: prod, staging and dev"
}

variable "deployer_service_account" {
  type        = string
  description = "Service account used to deploy resources using impersonation"
}

variable "datasets_bucket_name" {
  type        = string
  description = "Name of the bucket where the datasets are stored"
}

variable "job_schedule" {
  type        = string
  description = "Schedule for the scheduler job"
  # default every week on monday at 00:00
  default = "0 0 * * 1"
}

variable "job_name" {
  type        = string
  description = "Name of the job"
  default = "dataset-batch-job"
}

variable "job_attempt_deadline" {
  type        = string
  description = "Attempt deadline for the scheduler job"
  default = "320s"
}

variable "python_runtime" {
  type = string
  description = "Python runtime version"
  default = "python311"
}

variable "public_hosted_datasets_dns" {
  type = string
  description = "Public hosted DNS for datasets"
  default = "files.mobilitydatabase.org"
}