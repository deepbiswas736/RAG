/**
 * Output definitions for the storage module.
 * These outputs provide access information for the object storage services.
 */

output "endpoint" {
  description = "Endpoint for the storage service"
  value       = local.is_aws ? "s3.${var.region}.amazonaws.com" : "storage-endpoint-placeholder"
}

output "bucket_name" {
  description = "Name of the storage bucket"
  value       = local.is_aws ? aws_s3_bucket.data[0].bucket : "bucket-name-placeholder"
}

output "access_key" {
  description = "Access key for storage service"
  value       = local.is_aws ? aws_iam_access_key.storage_user[0].id : "access-key-placeholder"
  sensitive   = true
}

output "secret_key" {
  description = "Secret key for storage service"
  value       = local.is_aws ? aws_iam_access_key.storage_user[0].secret : "secret-key-placeholder"
  sensitive   = true
}

output "bucket_arn" {
  description = "ARN of the storage bucket (AWS only)"
  value       = local.is_aws ? aws_s3_bucket.data[0].arn : ""
}