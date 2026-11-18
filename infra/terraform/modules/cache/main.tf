# Valkey (ElastiCache) for what TokenProfiler keeps hot: rate-limit windows, node heartbeats, reconcile events,
# dashboard aggregates, signed-out session markers and the housekeeping lock. Everything in it can be rebuilt
# except the session markers, which matter for security. It is encrypted at rest with the
# deployment key and in transit with TLS, requires an auth token, and that token reaches
# the tasks only inside REDIS_URL in Secrets Manager.
resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-cache"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "cache" {
  name        = "${var.name_prefix}-cache"
  description = "Valkey; ingress only from application tasks"
  vpc_id      = var.vpc_id
  tags        = { Name = "${var.name_prefix}-cache" }
}

# A signed-out session is remembered as a key with a TTL. The default policy
# (volatile-lru) would evict such keys first under memory pressure and silently sign a
# revoked token back in; noeviction makes the write fail instead, which the API reports as
# an error and the memory alarm warns about long before it happens.
resource "aws_elasticache_parameter_group" "this" {
  name        = "${var.name_prefix}-valkey${split(".", var.engine_version)[0]}"
  family      = "valkey${split(".", var.engine_version)[0]}"
  description = "TokenProfiler: never evict signed-out session markers"

  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }
}

resource "random_password" "auth" {
  length  = 48
  special = false
}

resource "aws_elasticache_replication_group" "this" {
  #checkov:skip=CKV2_AWS_50:Failover needs a replica. aws-prod runs one (cache_replicas = 1), which turns on automatic failover and Multi-AZ below; aws-dev keeps a single node to save cost.
  replication_group_id       = "${var.name_prefix}-cache"
  description                = "Key and view caches, rate limits, the worker lease and signed-out sessions"
  engine                     = "valkey"
  engine_version             = var.engine_version
  node_type                  = var.node_type
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.this.name
  num_cache_clusters         = var.replicas + 1
  automatic_failover_enabled = var.replicas > 0
  multi_az_enabled           = var.replicas > 0
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.cache.id]
  at_rest_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  transit_encryption_enabled = true
  auth_token                 = random_password.auth.result
  snapshot_retention_limit   = var.snapshot_retention_days
  auto_minor_version_upgrade = true
  apply_immediately          = var.apply_immediately
}

resource "aws_secretsmanager_secret" "url" {
  #checkov:skip=CKV2_AWS_57:The auth token belongs to the replication group; rotate it by replacing the token (docs/guides/operations.md).
  name                    = "${var.name_prefix}/cache"
  description             = "REDIS_URL for the API and the worker, including the Valkey auth token"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "url" {
  secret_id = aws_secretsmanager_secret.url.id
  secret_string = jsonencode({
    REDIS_URL = "rediss://:${random_password.auth.result}@${aws_elasticache_replication_group.this.primary_endpoint_address}:6379/0"
  })
}
