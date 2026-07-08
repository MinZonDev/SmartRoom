# SmartRoom — hạ tầng messaging & storage
# Dev local : terraform apply -var use_localstack=true  (LocalStack :4566)
# Production: terraform apply                            (AWS thật, cần credentials)

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # LocalStack: credentials giả + trỏ mọi service về :4566
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  # LocalStack không resolve được virtual-hosted style (bucket.localhost)
  s3_use_path_style = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      sqs = var.localstack_endpoint
      s3  = var.localstack_endpoint
      ses = var.localstack_endpoint
    }
  }
}

# ---------------------------------------------------------------- SQS billing

resource "aws_sqs_queue" "billing_dlq" {
  name                      = "${var.name_prefix}-billing-dlq"
  message_retention_seconds = 1209600 # 14 ngày — đủ thời gian điều tra message hỏng
}

resource "aws_sqs_queue" "billing" {
  name                       = "${var.name_prefix}-billing"
  visibility_timeout_seconds = 120 # > thời gian xử lý 1 job chốt tháng
  receive_wait_time_seconds  = 20  # long polling — khớp worker

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.billing_dlq.arn
    maxReceiveCount     = 3
  })
}

# ------------------------------------------------------------------ S3 bucket

resource "aws_s3_bucket" "invoices" {
  bucket = "${var.name_prefix}-invoices"
}

# Không bao giờ public — truy cập qua presigned URL
resource "aws_s3_bucket_public_access_block" "invoices" {
  bucket                  = aws_s3_bucket.invoices.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "invoices" {
  bucket = aws_s3_bucket.invoices.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ----------------------------------------------------------------- SES sender

resource "aws_ses_email_identity" "sender" {
  email = var.ses_sender_email
}
