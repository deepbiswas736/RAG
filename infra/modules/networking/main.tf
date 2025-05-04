/**
 * Networking module for RAG application infrastructure.
 * This module creates the VPC, subnets, route tables, and other networking components.
 * It's designed to work across different cloud providers by using conditional logic.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  # Calculate subnet CIDRs based on the VPC CIDR
  public_subnet_cidrs  = [cidrsubnet(var.vpc_cidr, 4, 0), cidrsubnet(var.vpc_cidr, 4, 1)]
  private_subnet_cidrs = [cidrsubnet(var.vpc_cidr, 4, 2), cidrsubnet(var.vpc_cidr, 4, 3)]
  
  # Set availability zones based on the region
  availability_zones = local.is_aws ? ["${var.region}a", "${var.region}b"] : ["1", "2"]
}

# AWS-specific networking resources
resource "aws_vpc" "main" {
  count      = local.is_aws ? 1 : 0
  cidr_block = var.vpc_cidr
  
  enable_dns_support   = true
  enable_dns_hostnames = true
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-vpc"
  })
}

resource "aws_subnet" "public" {
  count             = local.is_aws ? length(local.public_subnet_cidrs) : 0
  vpc_id            = aws_vpc.main[0].id
  cidr_block        = local.public_subnet_cidrs[count.index]
  availability_zone = local.availability_zones[count.index]
  
  map_public_ip_on_launch = true
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-public-subnet-${count.index}"
    Type = "Public"
  })
}

resource "aws_subnet" "private" {
  count             = local.is_aws ? length(local.private_subnet_cidrs) : 0
  vpc_id            = aws_vpc.main[0].id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = local.availability_zones[count.index]
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-private-subnet-${count.index}"
    Type = "Private"
  })
}

resource "aws_internet_gateway" "main" {
  count  = local.is_aws ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-igw"
  })
}

resource "aws_route_table" "public" {
  count  = local.is_aws ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = local.is_aws ? length(local.public_subnet_cidrs) : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_eip" "nat" {
  count  = local.is_aws ? 1 : 0
  domain = "vpc"
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-nat-eip"
  })
}

resource "aws_nat_gateway" "main" {
  count         = local.is_aws ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-nat-gateway"
  })
}

resource "aws_route_table" "private" {
  count  = local.is_aws ? 1 : 0
  vpc_id = aws_vpc.main[0].id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id
  }
  
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-private-rt"
  })
}

resource "aws_route_table_association" "private" {
  count          = local.is_aws ? length(local.private_subnet_cidrs) : 0
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}

# Azure-specific networking resources would go here
# For example:
# resource "azurerm_virtual_network" "main" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${var.project_name}-${var.environment}-vnet"
#   address_space       = [var.vpc_cidr]
#   location            = var.region
#   resource_group_name = var.resource_group_name
#   tags                = var.tags
# }

# GCP-specific networking resources would go here
# For example:
# resource "google_compute_network" "main" {
#   count                   = local.is_gcp ? 1 : 0
#   name                    = "${var.project_name}-${var.environment}-vpc"
#   auto_create_subnetworks = false
# }