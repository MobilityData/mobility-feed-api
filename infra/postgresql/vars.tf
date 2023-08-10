# Configure the backend section to match your configuration.
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

variable "environment" {
  type        = string
  description = "API environment. Possible values: prod, staging and dev"
}

variable "deployer_service_account" {
  type        = string
  description = "Service account used to deploy resources using impersonation"
}

variable "postgresql_instance_name" {
  type        = string
  description = "The name of the PostgreSQL instance"
}

variable "postgresql_database_name" {
  type        = string
  description = "The name of the PostgreSQL database"
}

variable "postgresql_user_name" {
  type        = string
  description = "The name of the PostgreSQL user"
}

variable "postgresql_user_password" {
  type        = string
  description = "The password for the PostgreSQL user"
}

variable "postgresql_db_instance" {
  type        = string
  description = "The db instance tier for the PostgreSQL"
}