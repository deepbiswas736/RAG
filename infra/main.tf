/**
 * Main Terraform configuration file for the RAG application infrastructure.
 * This file sets up the providers and includes the necessary modules based on
 * the selected cloud provider.
 */

# Define local variables for the deployment
locals {
  project_name    = var.project_name
  environment     = var.environment
  cloud_provider  = var.cloud_provider
  region          = var.region
  tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "Terraform"
  }
}

# Include the selected cloud provider configuration based on the var.cloud_provider value
module "provider_config" {
  source = "./providers/${local.cloud_provider}"
  
  region          = local.region
  project_name    = local.project_name
  environment     = local.environment
  tags            = local.tags
}

# Set up networking infrastructure (VPC, subnets, etc.)
module "networking" {
  source = "./modules/networking"
  
  cloud_provider  = local.cloud_provider
  region          = local.region
  project_name    = local.project_name
  environment     = local.environment
  vpc_cidr        = var.vpc_cidr
  tags            = local.tags
}

# Set up security (IAM, Security Groups, etc.)
module "security" {
  source = "./modules/security"
  
  cloud_provider  = local.cloud_provider
  project_name    = local.project_name
  environment     = local.environment
  vpc_id          = module.networking.vpc_id
  tags            = local.tags
}

# Set up the database resources (MongoDB)
module "database" {
  source = "./modules/database"
  
  cloud_provider  = local.cloud_provider
  project_name    = local.project_name
  environment     = local.environment
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  security_group_id = module.security.database_security_group_id
  mongodb_version = var.mongodb_version
  mongodb_instance_type = var.mongodb_instance_type
  tags            = local.tags
}

# Set up object storage resources (MinIO)
module "storage" {
  source = "./modules/storage"
  
  cloud_provider  = local.cloud_provider
  project_name    = local.project_name
  environment     = local.environment
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  security_group_id = module.security.storage_security_group_id
  tags            = local.tags
}

# Set up messaging resources (Kafka)
module "messaging" {
  source = "./modules/messaging"
  
  cloud_provider  = local.cloud_provider
  project_name    = local.project_name
  environment     = local.environment
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  security_group_id = module.security.messaging_security_group_id
  tags            = local.tags
}

# Set up compute resources (ECS, AKS, GKE depending on provider)
module "compute" {
  source = "./modules/compute"
  
  cloud_provider  = local.cloud_provider
  project_name    = local.project_name
  environment     = local.environment
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.private_subnet_ids
  public_subnet_ids = module.networking.public_subnet_ids
  security_group_id = module.security.application_security_group_id
  
  # Database connection information
  mongodb_connection_string = module.database.connection_string
  
  # Storage connection information
  storage_endpoint = module.storage.endpoint
  storage_access_key = module.storage.access_key
  storage_secret_key = module.storage.secret_key
  
  # Messaging connection information
  kafka_brokers = module.messaging.kafka_brokers
  
  # Container image information
  rag_app_image = var.rag_app_image
  document_processor_image = var.document_processor_image
  
  tags          = local.tags
}