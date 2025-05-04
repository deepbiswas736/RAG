/**
 * Variables for the messaging module.
 * These variables define the inputs required by the messaging module.
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
  description = "ID of the VPC where the messaging services will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs where the messaging services will be deployed"
  type        = list(string)
}

variable "security_group_id" {
  description = "ID of the security group for the messaging services"
  type        = string
}

variable "kafka_version" {
  description = "Kafka version to deploy"
  type        = string
  default     = "3.4.0"
}

variable "kafka_instance_type" {
  description = "Instance type for Kafka brokers (cloud provider specific)"
  type        = string
  default     = "kafka.t3.small"  # AWS MSK default
}

variable "kafka_broker_count" {
  description = "Number of Kafka broker nodes"
  type        = number
  default     = 2
}

variable "kafka_volume_size" {
  description = "EBS volume size for Kafka brokers in GB"
  type        = number
  default     = 100
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