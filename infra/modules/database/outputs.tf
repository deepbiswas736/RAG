/**
 * Output definitions for the database module.
 * These outputs will be used by other modules to reference the database resources.
 */

output "connection_string" {
  description = "MongoDB connection string"
  value       = local.is_aws ? "mongodb://${aws_docdb_cluster.main[0].master_username}:${aws_docdb_cluster.main[0].master_password}@${aws_docdb_cluster.main[0].endpoint}:${aws_docdb_cluster.main[0].port}/?retryWrites=false" : ""
  sensitive   = true
}

output "endpoint" {
  description = "MongoDB endpoint"
  value       = local.is_aws ? aws_docdb_cluster.main[0].endpoint : ""
}

output "port" {
  description = "MongoDB port"
  value       = local.is_aws ? aws_docdb_cluster.main[0].port : ""
}

output "username" {
  description = "MongoDB admin username"
  value       = local.is_aws ? aws_docdb_cluster.main[0].master_username : ""
}

# We don't output the password directly for security reasons

output "cluster_id" {
  description = "ID of the MongoDB cluster"
  value       = local.is_aws ? aws_docdb_cluster.main[0].id : ""
}

output "instance_ids" {
  description = "IDs of the MongoDB instances"
  value       = local.is_aws ? aws_docdb_cluster_instance.main[*].id : []
}