/**
 * Output definitions for the messaging module.
 * These outputs will be used by other modules to reference the messaging resources.
 */

output "kafka_brokers" {
  description = "List of Kafka broker connection strings"
  value       = local.is_aws ? aws_msk_cluster.main[0].bootstrap_brokers_tls : []
}

output "zookeeper_connect_string" {
  description = "Zookeeper connection string"
  value       = local.is_aws ? aws_msk_cluster.main[0].zookeeper_connect_string : ""
}

output "cluster_name" {
  description = "Name of the Kafka cluster"
  value       = local.is_aws ? aws_msk_cluster.main[0].cluster_name : ""
}

output "cluster_arn" {
  description = "ARN of the Kafka cluster"
  value       = local.is_aws ? aws_msk_cluster.main[0].arn : ""
}