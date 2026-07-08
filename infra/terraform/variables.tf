variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "name_prefix" {
  type        = string
  default     = "smartroom"
  description = "Prefix cho tên resources"
}

variable "use_localstack" {
  type        = bool
  default     = false
  description = "true = trỏ provider về LocalStack (dev local)"
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

variable "ses_sender_email" {
  type        = string
  default     = "no-reply@smartroom.demo"
  description = "Địa chỉ gửi email hệ thống (phải verify với SES)"
}
