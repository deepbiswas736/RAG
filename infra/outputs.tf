/**
 * Outputs for the RAG application infrastructure.
 * These outputs provide important information after the infrastructure is deployed.
 */

output "api_endpoint" {
  description = "The endpoint URL for accessing the RAG application API"
  value       = module.compute.api_endpoint
}

output "mongodb_connection_string" {
  description = "MongoDB connection string (sensitive)"
  value       = module.database.connection_string
  sensitive   = true
}

output "storage_endpoint" {
  description = "Object storage service endpoint"
  value       = module.storage.endpoint
}

output "storage_access_key" {
  description = "Object storage access key (sensitive)"
  value       = module.storage.access_key
  sensitive   = true
}

output "storage_secret_key" {
  description = "Object storage secret key (sensitive)"
  value       = module.storage.secret_key
  sensitive   = true
}

output "kafka_brokers" {
  description = "Kafka broker connection strings"
  value       = module.messaging.kafka_brokers
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "cloud_provider" {
  description = "The cloud provider used for deployment"
  value       = var.cloud_provider
}

output "environment" {
  description = "The deployment environment"
  value       = var.environment
}

output "region" {
  description = "The region where resources are deployed"
  value       = var.region
}