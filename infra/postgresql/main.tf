resource "google_sql_database_instance" "db" {
  name             = var.instance_name
  database_version = "POSTGRES_12"
  region           = var.region

  settings {
    tier = "db-f1-micro"
  }
}

resource "google_sql_database" "default" {
  name       = var.database_name
  instance   = google_sql_database_instance.db.name
  collation  = "en_US.UTF8"
}

resource "google_sql_user" "users" {
  name     = var.user_name
  instance = google_sql_database_instance.db.name
  password = var.user_password
}
