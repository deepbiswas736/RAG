/**
 * Variables for the database module.
 * These variables define the inputs required by the database module.
 */

variable "cloud_provider" {
  description = "Cloud provider to deploy to (aws, azure, gcp)"
  type        = string
  
  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud_provider)
    error_message = "Valid values for cloud_provider are: aws, azure, gcp."
  }
}

variable "region" {
  description = "Region to deploy resources to"
  type        = string
}

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where the database will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs where the database will be deployed"
  type        = list(string)
}

variable "security_group_id" {
  description = "ID of the security group for the database"
  type        = string
}

variable "mongodb_version" {
  description = "Version of MongoDB to deploy"
  type        = string
  default     = "6.0"
}

variable "mongodb_instance_type" {
  description = "Instance type for MongoDB (cloud provider specific)"
  type        = string
  default     = "db.t3.medium"  # AWS default
}

variable "mongodb_instance_count" {
  description = "Number of MongoDB instances to deploy"
  type        = number
  default     = 1
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Azure-specific variables
variable "resource_group_name" {
  description = "Azure resource group name (only used when cloud_provider is 'azure')"
  type        = string
  default     = ""
}

# GCP-specific variables
variable "project_id" {
  description = "GCP project ID (only used when cloud_provider is 'gcp')"
  type        = string
  default     = ""
}