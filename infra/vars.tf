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

variable "feed_api_image_version" {
  type        = string
  description = "Docker image version"
}

variable "deployer_service_account" {
  type        = string
  description = "Service account used to deploy resources using impersonation"
}

variable "oauth2_client_id" {
  type        = string
  description = "OAuth2 Client id"
}

variable "oauth2_client_secret" {
  type        = string
  description = "OAuth2 Client secret"
}

variable "global_rate_limit_req_per_minute" {
  type        = string
  description = "Global load balancer rate limit"
}

variable "artifact_repo_name" {
  type = string
  description = "Name of the artifact repository"
}

variable "validator_endpoint" {
  type = string
  description = "URL of the validator endpoint"
}

variable "transitland_api_key" {
  type = string
}

variable "operations_oauth2_client_id" {
  type = string
  description = "value of the OAuth2 client id for the Operations API"
}

variable "tdg_api_token" {
    type        = string
    description = "TDG API key"
}