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

variable "docker_repository_name" {
  type        = string
  description = "GCP docker repository name"
}

variable "feed_api_service" {
  type        = string
  description = "Cloud run service name for Feed API"
}

variable "feed_api_image_version" {
  type        = string
  description = "Docker image version"
}

variable "S2S_JWT_SECRET" {
  type        = string
  description = "Server to server JWT secret"
}