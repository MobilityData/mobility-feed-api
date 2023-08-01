data "google_project" "project" {}

locals {
  services = [
    "sqladmin.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ]
}

resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

provider "google" {
  project = var.project_id
  region  = var.gcp_region
}

resource "google_sql_database_instance" "db" {
  name             = var.postgresql_instance_name
  database_version = "POSTGRES_12"
  region           = var.gcp_region

  settings {
    tier = "db-f1-micro"
  }
}

resource "google_sql_database" "default" {
  name       = var.postgresql_database_name
  instance   = google_sql_database_instance.db.name
  collation  = "en_US.UTF8"
}

resource "google_sql_user" "users" {
  name     = var.postgresql_user_name
  instance = google_sql_database_instance.db.name
  password = var.postgresql_user_password
}

output "instance_address" {
  description = "The first public IPv4 address of the SQL instance"
  value       = google_sql_database_instance.db.ip_address[0]
}

output "instance_connection_name" {
  description = "The connection name of the SQL instance to be used in connection strings"
  value       = google_sql_database_instance.db.connection_name
}
