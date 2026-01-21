data "google_project" "project" {}

locals {
  services = [
    "sqladmin.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "networkmanagement.googleapis.com",
    "servicenetworking.googleapis.com"
  ]
  retained_backups = lower(var.environment) == "prod" ? 31 : 1
  # Prod instances are regional meaning high availability with logs distributed across the region, non-prod instances are zonal with logs distributed across the zone
  availability_type = lower(var.environment) == "prod" ? "REGIONAL" : "ZONAL"
  transaction_log_retention_days = lower(var.environment) == "prod" ? 7 : 1
}

resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

provider "google" {
  project         = var.project_id
  access_token    = data.google_service_account_access_token.default.access_token
  request_timeout = "60s"
}

provider "google-beta" {
  project         = var.project_id
  access_token    = data.google_service_account_access_token.default.access_token
  request_timeout = "60s"
}

# This need to be created before the database instance
resource "google_compute_global_address" "private_ip_address" {
  name          = "google-managed-services-default"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = "projects/${var.project_id}/global/networks/default"
}

# This need to be created before the database instance
resource "google_service_networking_connection" "private_vpc_connection" {
  network       = "projects/${var.project_id}/global/networks/default"
  service       = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
  depends_on = [google_compute_global_address.private_ip_address]
}

resource "google_sql_database_instance" "db" {
  name             = var.postgresql_instance_name
  database_version = "POSTGRES_14"
  region           = var.gcp_region
  # This property protects the DB from deletion only for terraform commands
  # settings.deletion_protection_enabled protects the DB from deletion in the GCP console and GCP API
  deletion_protection = true

  settings {
    tier = var.postgresql_db_instance
    # This property protects the DB from deletion in the GCP console and GCP API
    deletion_protection_enabled = true
    database_flags {
      name  = "max_connections"
      value = var.max_db_connections
    }
    ip_configuration {
      ipv4_enabled = false
      private_network = "projects/${var.project_id}/global/networks/default"
    }
    availability_type = local.availability_type
    backup_configuration {
      enabled    = true
      start_time = "00:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = local.transaction_log_retention_days
      backup_retention_settings {
        retained_backups = local.retained_backups
      }
    }
  }
  depends_on = [google_service_networking_connection.private_vpc_connection]
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

resource "google_secret_manager_secret" "secret_db_url" {
  project   = var.project_id
  secret_id = "${upper(var.environment)}_FEEDS_DATABASE_URL"
  replication {
     auto {}
  }
}

resource "google_secret_manager_secret_version" "secret_version" {
  secret = google_secret_manager_secret.secret_db_url.id
  secret_data = "postgresql+psycopg2://${var.postgresql_user_name}:${var.postgresql_user_password}@${google_sql_database_instance.db.private_ip_address}/${var.postgresql_database_name}"
}

output "instance_address" {
  description = "The first public IPv4 address of the SQL instance"
  value       = google_sql_database_instance.db.private_ip_address
}

output "instance_connection_name" {
  description = "The connection name of the SQL instance to be used in connection strings"
  value       = google_sql_database_instance.db.connection_name
}
