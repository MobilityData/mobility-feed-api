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

# This script is part of the main terraform execution.
# Resources added here are shared across multiple modules.
# Module output:
#   vpc_connector_id: Name of the VPC connector in the form of projects/{{project}}/locations/{{region}}/connectors/{{name}}
#   vpc_connector_network: Network the VPC connector

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

locals {
#  DEV and QA use the same network for internal communication
  network = lower(var.environment) == "dev" ? "projects/mobility-feeds-qa/global/networks/default" : "default"
}

resource "google_vpc_access_connector" "vpc_connector" {
  name          = "vpc-connector-${lower(var.environment)}"
  region        = var.gcp_region
  network       = local.network
  ip_cidr_range = var.vpc_ip_cidr_range
  machine_type = var.vpc_machine_type
  min_instances = var.vpc_min_instances
  max_instances = var.vpc_max_instances
}

output "vpc_connector_id" {
  value       = google_vpc_access_connector.vpc_connector.id
  description = "Name of the VPC connector in the form of projects/{{project}}/locations/{{region}}/connectors/{{name}}"
}

output "vpc_connector_network" {
  value       = google_vpc_access_connector.vpc_connector.network
  description = "Network the VPC connector"
}