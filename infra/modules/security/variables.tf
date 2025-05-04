/**
 * Variables for the security module.
 * These variables define the inputs required by the security module.
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
  description = "ID of the VPC where security resources will be deployed"
  type        = string
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