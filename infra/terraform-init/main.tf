#
# MobilityData 2023
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

# This script prepares the GCP project by adding a deployer service account, binding permissions, and creates a GCP bucket for terraform state.
# The script is not intended to guide a deployment outside MobilityData environments, as there are multiple ways this can be achieved using Terraform.
# You can skip this script on your personal or organizational GCP environment if you follow a different state management mechanism and deployment credentials.
# In any case, the roles assigned to the service account created by this script guide the permissions required to deploy the Feeds API on your GCP environment.
#

provider "google" {
  project = var.project_id
  region  = var.gcp_region
}

locals {
  services = [
    "storage.googleapis.com"
  ]
}

# Configure the backend section to match your configuration.
terraform {
  backend "gcs" {
  }
}

# Enabling google cloud services.
resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

resource "google_service_account" "ci_service_account" {
  account_id   = "ci-service-account"
  project      = var.project_id
  display_name = "Service account to use as CI deployer"
}

resource "google_project_iam_binding" "ci_binding_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_service_usage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_kms" {
  project = var.project_id
  role    = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_artifactory" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_iam" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_run" {
  project = var.project_id
  role    = "roles/run.admin"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_project_iam_binding" "ci_binding_account" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  members = [
    "serviceAccount:${google_service_account.ci_service_account.email}"
  ]
}

resource "google_storage_bucket" "tf_state_bucket" {
  name          = "${var.terraform_state_bucket_name_prefix}-${var.environment}"
  force_destroy = false
  location      = "US"
  storage_class = "STANDARD"
  versioning {
    enabled = true
  }
}

output "ci_service_account_id" {
  value       = google_service_account.ci_service_account.id
  description = "CI service account ID"
}

output "ci_service_account_name" {
  value       = google_service_account.ci_service_account.name
  description = "CI service account name"
}

output "ci_service_account_email" {
  value       = google_service_account.ci_service_account.email
  description = "CI service account email"
}

output "tf_state_bucket_name" {
  value = google_storage_bucket.tf_state_bucket.name
}
