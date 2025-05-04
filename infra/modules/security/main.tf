/**
 * Security module for the RAG application infrastructure.
 * This module sets up security groups, IAM roles, and other security-related resources.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  name_prefix = "${var.project_name}-${var.environment}"
}

# AWS-specific security resources
resource "aws_security_group" "application" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-app-sg"
  description = "Security group for the RAG application"
  vpc_id      = var.vpc_id
  
  # Allow HTTPS traffic from anywhere
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }
  
  # Allow HTTP traffic for development environments
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.environment == "prod" ? [] : ["0.0.0.0/0"]
    description = "HTTP (non-prod only)"
  }
  
  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-app-sg"
  })
}

resource "aws_security_group" "database" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-db-sg"
  description = "Security group for MongoDB"
  vpc_id      = var.vpc_id
  
  # Allow MongoDB access from the application security group
  ingress {
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.application[0].id]
    description     = "MongoDB access from application"
  }
  
  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-db-sg"
  })
}

resource "aws_security_group" "storage" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-storage-sg"
  description = "Security group for MinIO/object storage"
  vpc_id      = var.vpc_id
  
  # Allow MinIO ports from the application security group
  ingress {
    from_port       = 9000
    to_port         = 9001
    protocol        = "tcp"
    security_groups = [aws_security_group.application[0].id]
    description     = "MinIO access from application"
  }
  
  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-storage-sg"
  })
}

resource "aws_security_group" "messaging" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-messaging-sg"
  description = "Security group for Kafka/messaging"
  vpc_id      = var.vpc_id
  
  # Allow Kafka ports from the application security group
  ingress {
    from_port       = 9092
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [aws_security_group.application[0].id]
    description     = "Kafka access from application"
  }
  
  # Allow ZooKeeper ports from the application security group
  ingress {
    from_port       = 2181
    to_port         = 2181
    protocol        = "tcp"
    security_groups = [aws_security_group.application[0].id]
    description     = "ZooKeeper access from application"
  }
  
  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-messaging-sg"
  })
}

# IAM role for the RAG application
resource "aws_iam_role" "application" {
  count = local.is_aws ? 1 : 0
  name  = "${local.name_prefix}-app-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

# Azure-specific security resources
# For example:
# resource "azurerm_network_security_group" "app" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${local.name_prefix}-app-nsg"
#   location            = var.region
#   resource_group_name = var.resource_group_name
#   
#   security_rule {
#     name                       = "HTTPS"
#     priority                   = 100
#     direction                  = "Inbound"
#     access                     = "Allow"
#     protocol                   = "Tcp"
#     source_port_range          = "*"
#     destination_port_range     = "443"
#     source_address_prefix      = "*"
#     destination_address_prefix = "*"
#   }
#   
#   tags = var.tags
# }

# GCP-specific security resources
# For example:
# resource "google_compute_firewall" "app" {
#   count   = local.is_gcp ? 1 : 0
#   name    = "${local.name_prefix}-app-firewall"
#   network = var.vpc_id
#   
#   allow {
#     protocol = "tcp"
#     ports    = ["443"]
#   }
#   
#   source_ranges = ["0.0.0.0/0"]
#   target_tags   = ["rag-application"]
# }