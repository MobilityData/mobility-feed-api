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


# This script deploys the the Artifactory Registry.
# The Artifactory repository is created with name: feeds-${var.environment}.
# Module output:
#   feed_repository_name: Name of the created artifact registry repository.

locals {
  services = [
    "cloudresourcemanager.googleapis.com",
    "artifactregistry.googleapis.com"
  ]
}

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

# Enabling google cloud services.
resource "google_project_service" "services" {
  for_each                   = toset(local.services)
  service                    = each.value
  project                    = var.project_id
  disable_dependent_services = true
}

resource "google_artifact_registry_repository" "feed_repository" {
  repository_id = "feeds-${var.environment}"
  location      = var.gcp_region
  project       = var.project_id
  format        = "DOCKER"
}

output "feed_repository_name" {
  value       = google_artifact_registry_repository.feed_repository.name
  description = "Name of the created artifact registry repository."
}
