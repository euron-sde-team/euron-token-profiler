variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
}

variable "kms_key_arn" {
  description = "CMK that encrypts the alarm topic. Its key policy must let CloudWatch use it (the kms module does)."
  type        = string
}

variable "alarm_email" {
  description = "Address subscribed to alarm notifications (confirm the e-mail AWS sends). Null: subscribe something else to the topic."
  type        = string
  default     = null
}

variable "alb_arn_suffix" {
  description = "Load balancer ARN suffix."
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name."
  type        = string
}

variable "services" {
  description = "Every ECS service to watch for CPU and memory: { api = <service name>, worker = ..., web = ... }."
  type        = map(string)
}

variable "target_groups" {
  description = "Target group ARN suffix per web-facing service, for 5xx, health and latency alarms."
  type        = map(string)
}

variable "latency_p95_threshold_seconds" {
  description = "Alarm when a target group's p95 response time stays above this. Completions stream for as long as the answer takes, so keep headroom above your longest expected generation."
  type        = number
  default     = 5
}

variable "db_instance_identifier" {
  description = "RDS instance identifier."
  type        = string
}

variable "db_max_connections" {
  description = "Connection ceiling the alarm measures against."
  type        = number
  default     = 200
}

variable "cache_replication_group_id" {
  description = "ElastiCache replication group id; its nodes are <id>-001, <id>-002 and so on."
  type        = string
}

variable "cache_node_count" {
  description = "Nodes in the replication group (the primary plus the replicas)."
  type        = number
  default     = 1
}
