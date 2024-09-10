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

variable "web_validator_url" {
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
    description = "Schedule for the GBFS scheduler job"
    default     = "0 0 1 * *" # every month on the first day at 00:00
}
