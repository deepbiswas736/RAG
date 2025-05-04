/**
 * Output definitions for the networking module.
 * These outputs will be used by other modules to reference the networking resources.
 */

output "vpc_id" {
  description = "ID of the VPC"
  value       = local.is_aws ? aws_vpc.main[0].id : (local.is_azure ? "azure-vnet-id" : "gcp-vpc-id")
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = local.is_aws ? aws_subnet.public[*].id : []
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = local.is_aws ? aws_subnet.private[*].id : []
}

output "nat_gateway_id" {
  description = "ID of the NAT Gateway (AWS only)"
  value       = local.is_aws ? aws_nat_gateway.main[0].id : null
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway (AWS only)"
  value       = local.is_aws ? aws_internet_gateway.main[0].id : null
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = var.vpc_cidr
}

# Additional outputs specific to Azure or GCP would be added here