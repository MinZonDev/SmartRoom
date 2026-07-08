#!/bin/bash
# Chạy tự động khi LocalStack sẵn sàng (/etc/localstack/init/ready.d/)
# Tạo: DLQ -> queue billing (redrive sau 3 lần fail) -> bucket hóa đơn
set -e

# PHẢI khớp AWS_REGION trong backend/.env — SQS scope theo region,
# lệch region là app báo QueueDoesNotExist
export AWS_DEFAULT_REGION=ap-southeast-1

awslocal sqs create-queue --queue-name smartroom-billing-dlq

dlq_arn=$(awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/smartroom-billing-dlq \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

awslocal sqs create-queue --queue-name smartroom-billing \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${dlq_arn}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"}"

awslocal s3 mb s3://smartroom-invoices || true

# SES: verify địa chỉ gửi để test notification email local
awslocal ses verify-email-identity --email-address no-reply@smartroom.demo

echo "[smartroom] LocalStack init xong: queue billing + DLQ + bucket + SES sender"
