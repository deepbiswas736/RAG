/**
 * Compute module for the RAG application infrastructure.
 * This module deploys the containerized RAG application services using the appropriate
 * container orchestration service for the selected cloud provider.
 */

locals {
  is_aws   = var.cloud_provider == "aws"
  is_azure = var.cloud_provider == "azure"
  is_gcp   = var.cloud_provider == "gcp"
  
  name_prefix = "${var.project_name}-${var.environment}"
}

# AWS-specific compute resources using ECS
resource "aws_ecs_cluster" "main" {
  count = local.is_aws ? 1 : 0
  name  = "${local.name_prefix}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "ecs_logs" {
  count = local.is_aws ? 1 : 0
  name  = "/ecs/${local.name_prefix}"
  
  retention_in_days = 30
  
  tags = var.tags
}

# Create a task definition for the main RAG application
resource "aws_ecs_task_definition" "rag_app" {
  count                    = local.is_aws ? 1 : 0
  family                   = "${local.name_prefix}-rag-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.rag_app_cpu
  memory                   = var.rag_app_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  
  container_definitions = jsonencode([
    {
      name         = "rag-app"
      image        = var.rag_app_image
      essential    = true
      
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "MONGODB_URI"
          value = var.mongodb_connection_string
        },
        {
          name  = "MINIO_ENDPOINT"
          value = var.storage_endpoint
        },
        {
          name  = "MINIO_ACCESS_KEY"
          value = var.storage_access_key
        },
        {
          name  = "KAFKA_BROKERS"
          value = join(",", var.kafka_brokers)
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]
      
      secrets = [
        {
          name      = "MINIO_SECRET_KEY"
          valueFrom = var.storage_secret_key_arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs[0].name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "rag-app"
        }
      }
    }
  ])
  
  tags = var.tags
}

# Create a task definition for the document processor service
resource "aws_ecs_task_definition" "document_processor" {
  count                    = local.is_aws ? 1 : 0
  family                   = "${local.name_prefix}-doc-processor"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.document_processor_cpu
  memory                   = var.document_processor_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  
  container_definitions = jsonencode([
    {
      name         = "document-processor"
      image        = var.document_processor_image
      essential    = true
      
      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "MONGODB_URI"
          value = var.mongodb_connection_string
        },
        {
          name  = "MINIO_ENDPOINT"
          value = var.storage_endpoint
        },
        {
          name  = "MINIO_ACCESS_KEY"
          value = var.storage_access_key
        },
        {
          name  = "KAFKA_BROKERS"
          value = join(",", var.kafka_brokers)
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        }
      ]
      
      secrets = [
        {
          name      = "MINIO_SECRET_KEY"
          valueFrom = var.storage_secret_key_arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs[0].name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "doc-processor"
        }
      }
    }
  ])
  
  tags = var.tags
}

# Create services to run the task definitions
resource "aws_ecs_service" "rag_app" {
  count           = local.is_aws ? 1 : 0
  name            = "${local.name_prefix}-rag-app"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.rag_app[0].arn
  desired_count   = var.rag_app_desired_count
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets         = var.subnet_ids
    security_groups = [var.security_group_id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.rag_app[0].arn
    container_name   = "rag-app"
    container_port   = 8000
  }
  
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  
  tags = var.tags
}

resource "aws_ecs_service" "document_processor" {
  count           = local.is_aws ? 1 : 0
  name            = "${local.name_prefix}-doc-processor"
  cluster         = aws_ecs_cluster.main[0].id
  task_definition = aws_ecs_task_definition.document_processor[0].arn
  desired_count   = var.document_processor_desired_count
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets         = var.subnet_ids
    security_groups = [var.security_group_id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.document_processor[0].arn
    container_name   = "document-processor"
    container_port   = 8080
  }
  
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  
  tags = var.tags
}

# Create Application Load Balancer resources
resource "aws_lb" "main" {
  count              = local.is_aws ? 1 : 0
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets            = var.public_subnet_ids
  
  enable_deletion_protection = var.environment == "prod"
  
  tags = var.tags
}

resource "aws_lb_target_group" "rag_app" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-rag-app-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  
  health_check {
    enabled             = true
    interval            = 30
    path                = "/health"
    port                = "traffic-port"
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
  
  tags = var.tags
}

resource "aws_lb_target_group" "document_processor" {
  count       = local.is_aws ? 1 : 0
  name        = "${local.name_prefix}-doc-proc-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  
  health_check {
    enabled             = true
    interval            = 30
    path                = "/health"
    port                = "traffic-port"
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
  
  tags = var.tags
}

resource "aws_lb_listener" "https" {
  count             = local.is_aws ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.rag_app[0].arn
  }
  
  tags = var.tags
}

resource "aws_lb_listener" "http" {
  count             = local.is_aws ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port              = 80
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
  
  tags = var.tags
}

resource "aws_lb_listener_rule" "document_processor" {
  count        = local.is_aws ? 1 : 0
  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.document_processor[0].arn
  }
  
  condition {
    path_pattern {
      values = ["/api/documents/*", "/api/process/*"]
    }
  }
  
  tags = var.tags
}

# Azure-specific compute resources using AKS
# For example:
# resource "azurerm_kubernetes_cluster" "main" {
#   count               = local.is_azure ? 1 : 0
#   name                = "${local.name_prefix}-aks"
#   location            = var.region
#   resource_group_name = var.resource_group_name
#   dns_prefix          = "${var.project_name}-${var.environment}"
#   
#   default_node_pool {
#     name            = "default"
#     node_count      = 2
#     vm_size         = "Standard_D2s_v3"
#     os_disk_size_gb = 30
#     vnet_subnet_id  = var.subnet_ids[0]
#   }
#   
#   identity {
#     type = "SystemAssigned"
#   }
#   
#   tags = var.tags
# }

# GCP-specific compute resources using GKE
# For example:
# resource "google_container_cluster" "main" {
#   count     = local.is_gcp ? 1 : 0
#   name      = "${local.name_prefix}-gke"
#   location  = var.region
#   project   = var.project_id
#   
#   network    = var.vpc_id
#   subnetwork = var.subnet_ids[0]
#   
#   remove_default_node_pool = true
#   initial_node_count       = 1
# }
# 
# resource "google_container_node_pool" "main" {
#   count      = local.is_gcp ? 1 : 0
#   name       = "${local.name_prefix}-node-pool"
#   location   = var.region
#   cluster    = google_container_cluster.main[0].name
#   project    = var.project_id
#   node_count = 2
#   
#   node_config {
#     machine_type = "e2-standard-2"
#     disk_size_gb = 100
#   }
# }