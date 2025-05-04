/**
 * Storage module for the RAG application infrastructure.
 * This module creates object storage resources (similar to MinIO) on the selected cloud provider.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  name_prefix = "${var.project_name}-${var.environment}"
}

# AWS S3 as the storage service
resource "aws_s3_bucket" "data" {
  count  = local.is_aws ? 1 : 0
  bucket = "${local.name_prefix}-data-bucket"
  
  tags = merge(var.tags, {
    Name = "${local.name_prefix}-data-bucket"
  })
}

resource "aws_s3_bucket_versioning" "data" {
  count  = local.is_aws ? 1 : 0
  bucket = aws_s3_bucket.data[0].id
  
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_ownership_controls" "data" {
  count  = local.is_aws ? 1 : 0
  bucket = aws_s3_bucket.data[0].id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "data" {
  count  = local.is_aws ? 1 : 0
  depends_on = [aws_s3_bucket_ownership_controls.data]
  
  bucket = aws_s3_bucket.data[0].id
  acl    = "private"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  count  = local.is_aws ? 1 : 0
  bucket = aws_s3_bucket.data[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  count  = local.is_aws ? 1 : 0
  bucket = aws_s3_bucket.data[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Create IAM user and access keys for application access
resource "aws_iam_user" "storage_user" {
  count = local.is_aws ? 1 : 0
  name  = "${local.name_prefix}-storage-user"
  
  tags = var.tags
}

resource "aws_iam_access_key" "storage_user" {
  count = local.is_aws ? 1 : 0
  user  = aws_iam_user.storage_user[0].name
}

resource "aws_iam_user_policy" "storage_user" {
  count  = local.is_aws ? 1 : 0
  name   = "${local.name_prefix}-storage-user-policy"
  user   = aws_iam_user.storage_user[0].name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          "${aws_s3_bucket.data[0].arn}",
          "${aws_s3_bucket.data[0].arn}/*"
        ]
      }
    ]
  })
}

# Azure-specific storage resources using Blob Storage
# For example:
# resource "azurerm_storage_account" "main" {
#   count                    = local.is_azure ? 1 : 0
#   name                     = "${replace(local.name_prefix, "-", "")}storage"
#   resource_group_name      = var.resource_group_name
#   location                 = var.region
#   account_tier             = "Standard"
#   account_replication_type = "LRS"
#   account_kind             = "StorageV2"
#   is_hns_enabled           = false
#   
#   tags = var.tags
# }
# 
# resource "azurerm_storage_container" "data" {
#   count                 = local.is_azure ? 1 : 0
#   name                  = "data"
#   storage_account_name  = azurerm_storage_account.main[0].name
#   container_access_type = "private"
# }

# GCP-specific storage resources using Google Cloud Storage
# For example:
# resource "google_storage_bucket" "data" {
#   count         = local.is_gcp ? 1 : 0
#   name          = "${local.name_prefix}-data-bucket"
#   location      = var.region
#   force_destroy = var.environment != "prod"
#   
#   uniform_bucket_level_access = true
#   
#   versioning {
#     enabled = var.enable_versioning
#   }
# }