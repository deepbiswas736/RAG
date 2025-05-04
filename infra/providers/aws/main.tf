/**
 * AWS provider configuration for RAG application infrastructure.
 * This file sets up the AWS provider with appropriate region and credentials.
 */

# AWS Provider configuration
provider "aws" {
  region = var.region
  
  default_tags {
    tags = var.tags
  }
}

# Define required variables
variable "region" {
  description = "AWS region to deploy resources to"
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

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Configure AWS-specific settings
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}