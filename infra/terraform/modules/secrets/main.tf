# Application secrets, generated once and stored in Secrets Manager. ECS injects each
# JSON key into the API, worker and CLI containers as an environment variable; the values
# never appear in a task definition, a Terraform plan or a log.
#
# The three are distinct on purpose (production refuses to boot if any are equal):
# rotating the session secret signs everyone out, rotating the pepper invalidates every
# API key, rotating the encryption key needs the stored upstream credentials re-entered,
# and an operator can do each without the others.
resource "random_password" "this" {
  for_each = toset(["SESSION_SECRET", "API_KEY_PEPPER", "ENCRYPTION_KEY"])
  length   = 64
  special  = false
}

resource "aws_secretsmanager_secret" "app" {
  #checkov:skip=CKV2_AWS_57:These are HMAC keys; rotation is an operator procedure (docs/guides/operations.md), not a Lambda.
  name                    = coalesce(var.secret_name, "${var.name_prefix}/app")
  description             = "TokenProfiler session signing secret, API key pepper and upstream credential encryption key"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id     = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({ for k, v in random_password.this : k => v.result })

  # Rotation happens out of band (put a new version by hand or by pipeline). Without
  # this, the next `terraform apply` would quietly roll every secret back.
  lifecycle {
    ignore_changes = [secret_string]
  }
}
