/**
 * Output definitions for the compute module.
 * These outputs provide information about the deployed compute resources.
 */

output "api_endpoint" {
  description = "The endpoint URL for accessing the RAG application API"
  value       = local.is_aws ? "https://${aws_lb.main[0].dns_name}" : "api-endpoint-placeholder"
}

output "cluster_id" {
  description = "ID of the container orchestration cluster"
  value       = local.is_aws ? aws_ecs_cluster.main[0].id : (
    local.is_azure ? "azure-aks-cluster-id" : "gcp-gke-cluster-id"
  )
}

output "load_balancer_id" {
  description = "ID of the load balancer"
  value       = local.is_aws ? aws_lb.main[0].id : "lb-id-placeholder"
}

output "rag_app_task_definition" {
  description = "ARN of the RAG application task definition (AWS only)"
  value       = local.is_aws ? aws_ecs_task_definition.rag_app[0].arn : ""
}

output "document_processor_task_definition" {
  description = "ARN of the document processor task definition (AWS only)"
  value       = local.is_aws ? aws_ecs_task_definition.document_processor[0].arn : ""
}