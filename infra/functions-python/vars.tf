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

variable "python_runtime" {
  type = string
  description = "Python runtime version"
  default = "python311"
}

variable "datasets_bucket_name" {
  type        = string
  description = "Name of the bucket where the datasets are stored"
  default = "mobilitydata-datasets"
}

variable "public_hosted_datasets_dns" {
  type = string
  description = "Public hosted DNS for datasets"
  default = "files.mobilitydatabase.org"
}

variable "validator_endpoint" {
  type = string
  description = "URL of the web validator"
  default = "https://stg-gtfs-validator-web-mbzoxaljzq-ue.a.run.app"
}

variable "gbfs_bucket_name" {
    type        = string
    description = "Name of the bucket where the GBFS feeds are stored"
    default     = "mobilitydata-gbfs-snapshots"
}

variable "gbfs_scheduler_schedule" {
    type        = string
    description = "Schedule for the GBFS validator daily job (version extraction and validation, Mon–Sat only)"
    default     = "0 0 * * 1-6" # At 00:00 Mon–Sat (Sunday is handled by the weekly geolocation job)
}

variable "gbfs_geolocation_scheduler_schedule" {
    type        = string
    description = "Schedule for the GBFS geolocation extraction weekly job"
    default     = "0 0 * * 0" # At 00:00 every Sunday
}


variable "jbda_scheduler_schedule" {
    type        = string
    description = "Schedule for the JBDA scheduler job"
    default     = "0 0 3 * *" # At 00:00 on the 3rd day of every month
}

variable "tdg_api_token" {
    type        = string
    description = "TDG API key"
}

variable "web_app_revalidate_url" {
    type        = string
    description = "URL of the web app's revalidation endpoint for cache invalidation"
    default     = ""
}

variable "web_app_revalidate_secret" {
    type        = string
    description = "Secret token used to authenticate requests to the web app's revalidation endpoint"
    sensitive   = true
    default     = ""
}

variable "transitland_scraping_schedule" {
    type        = string
    description = "Schedule Transitland scraping job"
    default = "0 15 3 * *" # Runs at 00:00 JST on the 3rd day of every month
}

variable "transitland_api_key" {
    type        = string
    description = "Transitland API key"
}

variable "operations_oauth2_client_id" {
  type = string
  description = "value of the OAuth2 client id for the Operations API"
}

variable "export_csv_schedule" {
    type        = string
    description = "Schedule the export_csv function"
    default = "0 4 * * 2,5" # At 4am every Tuesday and Friday.
}

variable "update_feed_status_schedule" {
    type        = string
    description = "Schedule the update_feed_status function"
    default     = "0 4 * * *" # At 4am every day.
}