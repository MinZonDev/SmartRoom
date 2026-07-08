output "billing_queue_url" {
  value       = aws_sqs_queue.billing.url
  description = "Gán vào env SQS_BILLING_QUEUE_URL"
}

output "billing_dlq_url" {
  value = aws_sqs_queue.billing_dlq.url
}

output "invoice_bucket" {
  value       = aws_s3_bucket.invoices.bucket
  description = "Gán vào env S3_INVOICE_BUCKET"
}

output "ses_sender" {
  value = aws_ses_email_identity.sender.email
}
