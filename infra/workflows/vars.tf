#
# MobilityData 2024
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

variable "datasets_bucket_name" {
  type        = string
  description = "Name of the bucket where the datasets are stored"
  default     = "mobilitydata-datasets"
}

variable "reports_bucket_name" {
  type        = string
  description = "Name of the bucket where the validation reports are stored"
  default     = "gtfs-validator-results"
}

variable "reports_project_id" {
  type        = string
  description = "GCP project ID where the validation reports are stored"
  default     = "web-based-gtfs-validator"
}

variable "validator_endpoint" {
  type = string
  description = "URL of the validator endpoint"
}

variable "processing_report_cloud_task_name" {
  type = string
  description = "The cloud task name to call the process report task"
}