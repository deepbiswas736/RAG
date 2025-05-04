/**
 * Messaging module for the RAG application infrastructure.
 * This module sets up Kafka and ZooKeeper services on the selected cloud provider.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  name_prefix = "${var.project_name}-${var.environment}"
}

# AWS-specific Kafka resources using MSK (Managed Streaming for Kafka)
resource "aws_msk_cluster" "main" {
  count         = local.is_aws ? 1 : 0
  cluster_name  = "${local.name_prefix}-kafka-cluster"
  kafka_version = var.kafka_version
  number_of_broker_nodes = var.kafka_broker_count
  
  broker_node_group_info {
    instance_type = var.kafka_instance_type
    client_subnets = var.subnet_ids
    security_groups = [var.security_group_id]
    
    storage_info {
      ebs_storage_info {
        volume_size = var.kafka_volume_size
      }
    }
  }
  
  encryption_info {
    encryption_in_transit {
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
    }
  }
  
  configuration_info {
    arn      = aws_msk_configuration.main[0].arn
    revision = aws_msk_configuration.main[0].latest_revision
  }
  
  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }
  
  tags = var.tags
}

resource "aws_msk_configuration" "main" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-kafka-config"
  description = "Kafka configuration for ${local.name_prefix}"
  
  kafka_versions = [var.kafka_version]
  
  server_properties = <<EOF
auto.create.topics.enable=true
delete.topic.enable=true
EOF
}

# Azure-specific Kafka resources using Event Hubs
# For example:
# resource "azurerm_eventhub_namespace" "main" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${local.name_prefix}-eventhub-namespace"
#   location            = var.region
#   resource_group_name = var.resource_group_name
#   sku                 = "Standard"
#   capacity            = var.kafka_broker_count
#   
#   tags = var.tags
# }
# 
# resource "azurerm_eventhub" "main" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${local.name_prefix}-events"
#   namespace_name      = azurerm_eventhub_namespace.main[0].name
#   resource_group_name = var.resource_group_name
#   partition_count     = 4
#   message_retention   = 7
# }

# GCP-specific Kafka resources using Pub/Sub
# For example:
# resource "google_pubsub_topic" "main" {
#   count   = local.is_gcp ? 1 : 0
#   name    = "${local.name_prefix}-pubsub-topic"
#   project = var.project_id
#   
#   message_retention_duration = "86600s"
# }