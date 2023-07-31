variable "instance_name" {
  description = "The name of the Cloud SQL instance"
  type        = string
}

variable "database_name" {
  description = "The name of the database to create"
  type        = string
}

variable "user_name" {
  description = "The name of the default user"
  type        = string
}

variable "user_password" {
  description = "The password for the default user. If not set, a random one will be generated and available in the generated_user_password output variable."
  type        = string
}

variable "region" {
  description = "The region of the Cloud SQL resources"
  type        = string
}
