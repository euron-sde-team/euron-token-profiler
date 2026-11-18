variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
  default     = "tokenprofiler-dev"
}

variable "hostname" {
  description = "Public host name: the dashboard is served at / and the API under /api/v1 on this one host."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone for the host name: the certificate is validated and the DNS record created for you. Null: bring an issued certificate_arn and point the host name at the load balancer yourself."
  type        = string
  default     = null
}

variable "certificate_arn" {
  description = "Existing, issued ACM certificate for the host name. Required without route53_zone_id."
  type        = string
  default     = null
}

variable "product_name" {
  description = "Name shown in the dashboard."
  type        = string
  default     = "Euron TokenProfiler"
}

variable "image_tag" {
  description = "Image tag to deploy (make aws-deploy passes the git commit)."
  type        = string
  default     = "latest"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.medium"
}

variable "cache_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t4g.small"
}

variable "alarm_email" {
  description = "Address that receives alarm notifications."
  type        = string
  default     = null
}

variable "default_retention_days" {
  description = "How long a new project keeps traces (each project can change it)."
  type        = number
  default     = 30
}

variable "api_cpu" {
  description = "API task CPU units."
  type        = number
  default     = 4096
}

variable "api_memory" {
  description = "API task memory (MiB)."
  type        = number
  default     = 8192
}
