/**
 * Input variables for the RAG application infrastructure.
 * These variables can be set through terraform.tfvars files in each environment directory.
 */

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "rag-application"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cloud_provider" {
  description = "Cloud provider to deploy to (aws, azure, gcp)"
  type        = string
  default     = "aws"
  
  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud_provider)
    error_message = "Valid values for cloud_provider are: aws, azure, gcp."
  }
}

variable "region" {
  description = "Region to deploy resources to"
  type        = string
  default     = "us-east-1"  # This default is for AWS, will be overridden for Azure and GCP
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# MongoDB configuration
variable "mongodb_version" {
  description = "Version of MongoDB to deploy"
  type        = string
  default     = "6.0"
}

variable "mongodb_instance_type" {
  description = "Instance type for MongoDB (cloud provider specific)"
  type        = string
  default     = "db.t3.medium"  # AWS default, will be overridden for Azure and GCP
}

# Container images
variable "rag_app_image" {
  description = "Docker image for the main RAG application"
  type        = string
  default     = "rag-application:latest"
}

variable "document_processor_image" {
  description = "Docker image for the document processor service"
  type        = string
  default     = "document-processor:latest"
}

# MinIO / Object Storage configuration
variable "minio_storage_size" {
  description = "Size of storage allocated for MinIO (in GB)"
  type        = number
  default     = 100
}

# Kafka configuration
variable "kafka_instance_type" {
  description = "Instance type for Kafka brokers (cloud provider specific)"
  type        = string
  default     = "kafka.t3.small"  # AWS MSK default, will be overridden for Azure and GCP
}

variable "kafka_broker_count" {
  description = "Number of Kafka broker nodes"
  type        = number
  default     = 2
}

variable "kafka_version" {
  description = "Kafka version to deploy"
  type        = string
  default     = "3.4.0"
}