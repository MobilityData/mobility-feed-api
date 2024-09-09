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

variable "python_runtime" {
  type = string
  description = "Python runtime version"
  default = "python310"
}

variable "gtfs_datasets_storage_bucket" {
  type        = string
  description = "Name of the bucket where the GTFS datasets are stored"
  default     = "mobilitydata-datasets"
}

variable "gbfs_snapshots_storage_bucket" {
  type        = string
  description = "Name of the bucket where the GBFS snapshots are stored"
  default     = "mobilitydata-gbfs-snapshots"
}

variable "dataset_id" {
    type        = string
    description = "ID of the BigQuery dataset"
    default     = "data_analytics"
}

variable "gtfs_table_id" {
    type        = string
    description = "ID of the BigQuery table for GTFS data"
    default     = "gtfs_validation_reports"
}

variable "gbfs_table_id" {
    type        = string
    description = "ID of the BigQuery table for GBFS data"
    default     = "gbfs_validation_reports"
}

variable gtfs_data_schedule {
    type        = string
    description = "Schedule for GTFS data ingestion"
    default     = "0 0 2 * *"  # Midnight on the 2nd of every month
}

variable gbfs_data_schedule {
    type        = string
    description = "Schedule for GBFS data ingestion"
    default     = "0 0 2 * *"  # Midnight on the 2nd of every month
}

variable "gtfs_data_preprocessor_schedule" {
    type        = string
    description = "Schedule for GTFS data preprocessor"
    default     = "0 0 2 * *"  # Midnight on the 2nd of every month
}

variable "gbfs_data_preprocessor_schedule" {
    type        = string
    description = "Schedule for GBFS data preprocessor"
    default     = "0 0 2 * *"  # Midnight on the 2nd of every month
}