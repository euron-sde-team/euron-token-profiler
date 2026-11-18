output "secret_arn" {
  description = "ARN of the JSON secret holding SESSION_SECRET, API_KEY_PEPPER and ENCRYPTION_KEY."
  value       = aws_secretsmanager_secret.app.arn
}

output "secret_name" {
  description = "Name of the secret."
  value       = aws_secretsmanager_secret.app.name
}

output "keys" {
  description = "JSON keys inside the secret, for ECS `secrets` valueFrom references."
  value       = sort(keys(random_password.this))
}
