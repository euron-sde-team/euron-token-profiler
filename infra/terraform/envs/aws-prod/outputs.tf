output "urls" {
  description = "Public URLs: the dashboard, the API base and the interactive API reference."
  value       = module.tokenprofiler.urls
}

output "ecr_repository_urls" {
  description = "Image repositories."
  value       = module.tokenprofiler.ecr_repository_urls
}

output "cluster_name" {
  description = "ECS cluster."
  value       = module.tokenprofiler.cluster_name
}

output "service_names" {
  description = "ECS services."
  value       = module.tokenprofiler.service_names
}

output "cli_task_definition" {
  description = "Task definition for one-off CLI tasks."
  value       = module.tokenprofiler.cli_task_definition
}

output "cli_security_group_id" {
  description = "Security group for one-off CLI tasks."
  value       = module.tokenprofiler.cli_security_group_id
}

output "private_subnet_ids" {
  description = "Private subnets for one-off tasks."
  value       = module.tokenprofiler.private_subnet_ids
}

output "load_balancer_dns_name" {
  description = "Point the host name here (a CNAME) when the zone is not in Route53."
  value       = module.tokenprofiler.load_balancer_dns_name
}

output "certificate_validation_records" {
  description = "DNS records to publish when the zone is not in Route53."
  value       = module.tokenprofiler.certificate_validation_records
}
