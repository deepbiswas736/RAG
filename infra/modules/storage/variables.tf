/**
 * Variables for the storage module.
 * These variables define the inputs required by the storage module.
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
  description = "ID of the VPC where the storage services will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs where the storage services will be deployed"
  type        = list(string)
}

variable "security_group_id" {
  description = "ID of the security group for the storage services"
  type        = string
}

variable "enable_versioning" {
  description = "Whether to enable versioning for the storage bucket"
  type        = bool
  default     = true
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