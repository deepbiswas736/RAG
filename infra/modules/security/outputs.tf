/**
 * Output definitions for the security module.
 * These outputs will be used by other modules to reference the security resources.
 */

output "application_security_group_id" {
  description = "ID of the security group for the application"
  value       = local.is_aws ? aws_security_group.application[0].id : ""
}

output "database_security_group_id" {
  description = "ID of the security group for the database services"
  value       = local.is_aws ? aws_security_group.database[0].id : ""
}

output "storage_security_group_id" {
  description = "ID of the security group for the storage services"
  value       = local.is_aws ? aws_security_group.storage[0].id : ""
}

output "messaging_security_group_id" {
  description = "ID of the security group for the messaging services"
  value       = local.is_aws ? aws_security_group.messaging[0].id : ""
}

output "application_role_arn" {
  description = "ARN of the IAM role for the application (AWS only)"
  value       = local.is_aws ? aws_iam_role.application[0].arn : ""
}

# Additional outputs for Azure or GCP would be added here