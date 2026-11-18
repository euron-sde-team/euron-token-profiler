output "bucket_name" {
  description = "Archive bucket name (S3_BUCKET)."
  value       = aws_s3_bucket.archive.bucket
}

output "bucket_arn" {
  description = "Archive bucket ARN, for IAM policies."
  value       = aws_s3_bucket.archive.arn
}
