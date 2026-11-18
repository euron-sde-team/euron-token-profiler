output "archive_bucket" {
  description = "S3_BUCKET for the local stack."
  value       = module.storage.bucket_name
}

output "kms_key_alias" {
  description = "S3_KMS_KEY_ID for the local stack."
  value       = module.kms.alias_name
}

output "kms_key_id" {
  description = "Id of the key behind the alias."
  value       = module.kms.key_id
}

output "app_secret_arn" {
  description = "Secret holding the generated application secrets (not read locally)."
  value       = module.secrets.secret_arn
}
