# Alarms (to an SNS topic, optionally e-mailed) and one dashboard for a deployment:
# load balancer errors, health and latency for the web-facing services, CPU and memory for
# every service, the database and the cache.
data "aws_region" "current" {}

# A customer-managed key, not alias/aws/sns: alarms cannot publish to a topic encrypted with
# the AWS-managed key, so notifications would be dropped silently.
resource "aws_sns_topic" "alarms" {
  name              = "${var.name_prefix}-alarms"
  kms_master_key_id = var.kms_key_arn
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == null ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  region = data.aws_region.current.region

  lb_alarms = merge([
    for name, tg in var.target_groups : {
      "${name}-5xx" = {
        description = "${name}: 5xx responses from the tasks"
        namespace   = "AWS/ApplicationELB"
        metric      = "HTTPCode_Target_5XX_Count"
        stat        = "Sum"
        threshold   = 25
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { LoadBalancer = var.alb_arn_suffix, TargetGroup = tg }
      }
      "${name}-unhealthy" = {
        description = "${name}: tasks failing load balancer health checks"
        namespace   = "AWS/ApplicationELB"
        metric      = "UnHealthyHostCount"
        stat        = "Maximum"
        threshold   = 0
        period      = 60
        comparison  = "GreaterThanThreshold"
        dimensions  = { LoadBalancer = var.alb_arn_suffix, TargetGroup = tg }
      }
      "${name}-latency-p95" = {
        description = "${name}: p95 response time above ${var.latency_p95_threshold_seconds} seconds"
        namespace   = "AWS/ApplicationELB"
        metric      = "TargetResponseTime"
        stat        = "p95"
        threshold   = var.latency_p95_threshold_seconds
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { LoadBalancer = var.alb_arn_suffix, TargetGroup = tg }
      }
    }
  ]...)

  ecs_alarms = merge([
    for name, service in var.services : {
      "${name}-cpu" = {
        description = "${name}: CPU sustained above 85%"
        namespace   = "AWS/ECS"
        metric      = "CPUUtilization"
        stat        = "Average"
        threshold   = 85
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { ClusterName = var.ecs_cluster_name, ServiceName = service }
      }
      "${name}-memory" = {
        description = "${name}: memory sustained above 85%"
        namespace   = "AWS/ECS"
        metric      = "MemoryUtilization"
        stat        = "Average"
        threshold   = 85
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { ClusterName = var.ecs_cluster_name, ServiceName = service }
      }
    }
  ]...)

  db_alarms = {
    db-cpu = {
      description = "Database CPU sustained above 80%"
      namespace   = "AWS/RDS"
      metric      = "CPUUtilization"
      stat        = "Average"
      threshold   = 80
      period      = 300
      comparison  = "GreaterThanThreshold"
      dimensions  = { DBInstanceIdentifier = var.db_instance_identifier }
    }
    db-storage = {
      description = "Database free storage below 5 GiB"
      namespace   = "AWS/RDS"
      metric      = "FreeStorageSpace"
      stat        = "Minimum"
      threshold   = 5 * 1024 * 1024 * 1024
      period      = 300
      comparison  = "LessThanThreshold"
      dimensions  = { DBInstanceIdentifier = var.db_instance_identifier }
    }
    db-connections = {
      description = "Database connections above 80% of the configured ceiling"
      namespace   = "AWS/RDS"
      metric      = "DatabaseConnections"
      stat        = "Maximum"
      threshold   = var.db_max_connections * 0.8
      period      = 300
      comparison  = "GreaterThanThreshold"
      dimensions  = { DBInstanceIdentifier = var.db_instance_identifier }
    }
  }

  # The cache never evicts (signed-out session markers must not be forgotten early), so a
  # full cache refuses writes: the memory alarm fires with room to spare.
  cache_alarms = merge([
    for i in range(var.cache_node_count) : {
      "cache-${format("%03d", i + 1)}-memory" = {
        description = "Valkey node ${format("%03d", i + 1)}: memory above 75% (the cache never evicts, so a full cache refuses writes)"
        namespace   = "AWS/ElastiCache"
        metric      = "DatabaseMemoryUsagePercentage"
        stat        = "Maximum"
        threshold   = 75
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { CacheClusterId = "${var.cache_replication_group_id}-${format("%03d", i + 1)}" }
      }
      "cache-${format("%03d", i + 1)}-cpu" = {
        description = "Valkey node ${format("%03d", i + 1)}: engine CPU sustained above 80%"
        namespace   = "AWS/ElastiCache"
        metric      = "EngineCPUUtilization"
        stat        = "Average"
        threshold   = 80
        period      = 300
        comparison  = "GreaterThanThreshold"
        dimensions  = { CacheClusterId = "${var.cache_replication_group_id}-${format("%03d", i + 1)}" }
      }
    }
  ]...)

  alarms = merge(local.lb_alarms, local.ecs_alarms, local.db_alarms, local.cache_alarms)
}

# Percentile statistics are an "extended statistic" in CloudWatch; the others are plain.
resource "aws_cloudwatch_metric_alarm" "this" {
  for_each            = local.alarms
  alarm_name          = "${var.name_prefix}-${each.key}"
  alarm_description   = each.value.description
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  statistic           = startswith(each.value.stat, "p") ? null : each.value.stat
  extended_statistic  = startswith(each.value.stat, "p") ? each.value.stat : null
  dimensions          = each.value.dimensions
  period              = each.value.period
  evaluation_periods  = 2
  threshold           = each.value.threshold
  comparison_operator = each.value.comparison
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name_prefix
  dashboard_body = jsonencode({
    widgets = concat(
      [
        {
          type = "metric", x = 0, y = 0, width = 12, height = 6
          properties = {
            title = "Requests and errors", region = local.region, stat = "Sum", period = 60
            metrics = [
              ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix],
              [".", "HTTPCode_Target_4XX_Count", ".", "."],
              [".", "HTTPCode_Target_5XX_Count", ".", "."],
            ]
          }
        },
        {
          type = "metric", x = 12, y = 0, width = 12, height = 6
          properties = {
            title = "Latency p50 / p95 / p99", region = local.region, period = 60
            metrics = [
              ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p50" }],
              ["...", { stat = "p95" }],
              ["...", { stat = "p99" }],
            ]
          }
        },
        {
          type = "metric", x = 0, y = 12, width = 12, height = 6
          properties = {
            title = "Requests and errors", region = local.region, stat = "Sum", period = 60
            metrics = [
              ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix],
              [".", "HTTPCode_Target_5XX_Count", ".", "."],
              [".", "HTTPCode_ELB_5XX_Count", ".", "."],
            ]
          }
        },
        {
          type = "metric", x = 12, y = 12, width = 12, height = 6
          properties = {
            title = "Database", region = local.region, stat = "Average", period = 60
            metrics = [
              ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_instance_identifier],
              [".", "DatabaseConnections", ".", "."],
              [".", "ReadLatency", ".", "."],
              [".", "WriteLatency", ".", "."],
            ]
          }
        },
        {
          type = "metric", x = 0, y = 18, width = 12, height = 6
          properties = {
            title = "Valkey (primary)", region = local.region, stat = "Average", period = 60
            metrics = [
              ["AWS/ElastiCache", "EngineCPUUtilization", "CacheClusterId", "${var.cache_replication_group_id}-001"],
              [".", "DatabaseMemoryUsagePercentage", ".", "."],
              [".", "CurrConnections", ".", "."],
            ]
          }
        },
        {
          type = "alarm", x = 12, y = 18, width = 12, height = 6
          properties = {
            title  = "Alarms"
            alarms = [for alarm in aws_cloudwatch_metric_alarm.this : alarm.arn]
          }
        },
      ],
      [
        for i, name in sort(keys(var.services)) : {
          type = "metric", x = (i % 3) * 8, y = 6, width = 8, height = 6
          properties = {
            title = "${name}: CPU / memory", region = local.region, stat = "Average", period = 60
            metrics = [
              ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.services[name]],
              [".", "MemoryUtilization", ".", ".", ".", "."],
            ]
          }
        }
      ],
    )
  })
}
