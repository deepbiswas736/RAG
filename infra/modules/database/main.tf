/**
 * Database module for the RAG application infrastructure.
 * This module sets up MongoDB resources based on the selected cloud provider.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  name_prefix = "${var.project_name}-${var.environment}"
}

# AWS-specific MongoDB resources using DocumentDB (AWS's MongoDB-compatible database)
resource "aws_docdb_subnet_group" "main" {
  count      = local.is_aws ? 1 : 0
  name       = "${local.name_prefix}-docdb-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-docdb-subnet-group"
  })
}

resource "aws_docdb_cluster_parameter_group" "main" {
  count       = local.is_aws ? 1 : 0
  family      = "docdb4.0"
  name        = "${local.name_prefix}-docdb-param-group"
  description = "DocDB parameter group for ${local.name_prefix}"

  parameter {
    name  = "tls"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-docdb-param-group"
  })
}

resource "random_password" "mongodb" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_docdb_cluster" "main" {
  count                   = local.is_aws ? 1 : 0
  cluster_identifier      = "${local.name_prefix}-docdb-cluster"
  engine                  = "docdb"
  master_username         = "mongodb_admin"
  master_password         = random_password.mongodb.result
  db_subnet_group_name    = aws_docdb_subnet_group.main[0].name
  vpc_security_group_ids  = [var.security_group_id]
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.main[0].name
  
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"
  apply_immediately       = var.environment != "prod"
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-docdb-cluster"
  })
}

resource "aws_docdb_cluster_instance" "main" {
  count                      = local.is_aws ? var.mongodb_instance_count : 0
  identifier                 = "${local.name_prefix}-docdb-instance-${count.index}"
  cluster_identifier         = aws_docdb_cluster.main[0].id
  instance_class             = var.mongodb_instance_type
  apply_immediately          = var.environment != "prod"
  auto_minor_version_upgrade = true
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-docdb-instance-${count.index}"
  })
}

# Azure-specific MongoDB resources using CosmosDB
# For example:
# resource "azurerm_cosmosdb_account" "main" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${replace(local.name_prefix, "-", "")}mongodb"
#   location            = var.region
#   resource_group_name = var.resource_group_name
#   offer_type          = "Standard"
#   kind                = "MongoDB"
#
#   capabilities {
#     name = "EnableMongo"
#   }
#
#   consistency_policy {
#     consistency_level = "Session"
#   }
#
#   geo_location {
#     location          = var.region
#     failover_priority = 0
#   }
#
#   tags = var.tags
# }

# GCP-specific MongoDB resources
# For example:
# resource "google_compute_global_address" "private_ip_address" {
#   count         = local.is_gcp ? 1 : 0
#   name          = "${local.name_prefix}-mongodb-private-ip"
#   purpose       = "VPC_PEERING"
#   address_type  = "INTERNAL"
#   prefix_length = 16
#   network       = var.network_id
# }