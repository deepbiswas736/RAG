/**
 * Variables for the compute module.
 * These variables define the inputs required by the compute module.
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
  description = "ID of the VPC where the compute resources will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs where the compute resources will be deployed"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs where load balancers will be deployed"
  type        = list(string)
}

variable "security_group_id" {
  description = "ID of the security group for the compute resources"
  type        = string
}

# Database connection information
variable "mongodb_connection_string" {
  description = "MongoDB connection string"
  type        = string
  sensitive   = true
}

# Storage connection information
variable "storage_endpoint" {
  description = "Endpoint for the storage service"
  type        = string
}

variable "storage_access_key" {
  description = "Access key for the storage service"
  type        = string
  sensitive   = true
}

variable "storage_secret_key" {
  description = "Secret key for the storage service"
  type        = string
  sensitive   = true
}

variable "storage_secret_key_arn" {
  description = "ARN of the secret containing the storage secret key"
  type        = string
  default     = ""
}

# Messaging connection information
variable "kafka_brokers" {
  description = "List of Kafka broker connection strings"
  type        = list(string)
}

# Container image information
variable "rag_app_image" {
  description = "Docker image for the main RAG application"
  type        = string
}

variable "document_processor_image" {
  description = "Docker image for the document processor service"
  type        = string
}

# Compute resource sizing
variable "rag_app_cpu" {
  description = "CPU units for the RAG application (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "rag_app_memory" {
  description = "Memory for the RAG application (in MB)"
  type        = number
  default     = 2048
}

variable "document_processor_cpu" {
  description = "CPU units for the document processor (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "document_processor_memory" {
  description = "Memory for the document processor (in MB)"
  type        = number
  default     = 2048
}

variable "rag_app_desired_count" {
  description = "Desired number of RAG application container instances"
  type        = number
  default     = 2
}

variable "document_processor_desired_count" {
  description = "Desired number of document processor container instances"
  type        = number
  default     = 2
}

# Additional AWS-specific variables
variable "execution_role_arn" {
  description = "ARN of the IAM role for ECS task execution (AWS only)"
  type        = string
  default     = ""
}

variable "task_role_arn" {
  description = "ARN of the IAM role for ECS tasks (AWS only)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS (AWS only)"
  type        = string
  default     = ""
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