# Development environment configuration for RAG application infrastructure
project_name    = "rag-application"
environment     = "dev"
cloud_provider  = "aws"
region          = "us-east-1"
vpc_cidr        = "10.0.0.0/16"

# MongoDB configuration
mongodb_version       = "6.0"
mongodb_instance_type = "db.t3.medium"

# Container images
rag_app_image           = "rag-application:latest"
document_processor_image = "document-processor:latest"

# MinIO / Object Storage configuration
minio_storage_size = 50

# Kafka configuration
kafka_instance_type = "kafka.t3.small"
kafka_broker_count  = 2
kafka_version       = "3.4.0"