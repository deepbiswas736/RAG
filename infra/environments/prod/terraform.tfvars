# Production environment configuration for RAG application infrastructure
project_name    = "rag-application"
environment     = "prod"
cloud_provider  = "aws"
region          = "us-east-1"
vpc_cidr        = "10.0.0.0/16"

# MongoDB configuration
mongodb_version       = "6.0"
mongodb_instance_type = "db.r5.xlarge"
mongodb_instance_count = 3

# Container images
rag_app_image           = "rag-application:stable"
document_processor_image = "document-processor:stable"

# Compute resource sizing
rag_app_cpu                    = 2048
rag_app_memory                 = 4096
rag_app_desired_count          = 3
document_processor_cpu         = 2048
document_processor_memory      = 4096
document_processor_desired_count = 3

# MinIO / Object Storage configuration
minio_storage_size = 1000
enable_versioning  = true

# Kafka configuration
kafka_instance_type = "kafka.m5.large"
kafka_broker_count  = 3
kafka_version       = "3.4.0"
kafka_volume_size   = 200