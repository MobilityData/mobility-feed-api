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

variable "vpc_ip_cidr_range" {
  type        = string
  description = "VPC network name. Defaulted to Montreal region default range"
  default = "10.9.0.0/28"
}

variable "vpc_machine_type" {
  type        = string
  description = "Machine type for the VPC access connector. Defaulted to f1-micro"
  default = "f1-micro"
}

variable "vpc_min_instances" {
    type        = number
    description = "Minimum number of instances for the VPC access connector. Defaulted to 2"
    default = 2
}

variable "vpc_max_instances" {
    type        = number
    description = "Maximum number of instances for the VPC access connector. Defaulted to 3"
    default = 3
}