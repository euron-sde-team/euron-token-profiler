data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  account_root = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
}

data "aws_iam_policy_document" "key" {
  #checkov:skip=CKV_AWS_109:Key policies always use Resource "*" (the key itself); root access delegates to IAM.
  #checkov:skip=CKV_AWS_111:As above; usage is constrained by per-role IAM policies and kms:ViaService conditions.
  #checkov:skip=CKV_AWS_356:As above.
  # The account root keeps control so the key can never become unmanageable.
  # Usage is then granted per role by IAM policies (the API and worker task roles), scoped
  # to the operations, the services and the encryption context each role needs.
  statement {
    sid       = "AccountRoot"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = [local.account_root]
    }
  }

  # CloudWatch Logs encrypts this deployment's log groups with the key, and only those:
  # the encryption context names a log group in this account and region.
  statement {
    sid       = "CloudWatchLogs"
    actions   = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.region}.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:*"]
    }
  }

  # CloudWatch alarms publish to an SNS topic encrypted with this key. An AWS-managed key
  # cannot be used for that (its policy cannot name CloudWatch), so the alarm topic uses
  # this one, and only alarms of this account and region may use it.
  statement {
    sid       = "CloudWatchAlarms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey*"]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${data.aws_partition.current.partition}:cloudwatch:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:alarm:*"]
    }
  }

  dynamic "statement" {
    for_each = length(var.admin_principal_arns) > 0 ? [1] : []
    content {
      sid = "KeyAdministrators"
      actions = [
        "kms:Create*", "kms:Describe*", "kms:Enable*", "kms:List*", "kms:Put*", "kms:Update*",
        "kms:Revoke*", "kms:Disable*", "kms:Get*", "kms:Delete*", "kms:TagResource",
        "kms:UntagResource", "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
      ]
      resources = ["*"]
      principals {
        type        = "AWS"
        identifiers = var.admin_principal_arns
      }
    }
  }
}

# One customer-managed key. Used at rest, through AWS services: the S3 archive bucket,
# RDS storage, the Valkey cache, Secrets Manager, ECR, CloudWatch logs and the alarm topic
# (kms:ViaService conditions in the deployment module), and directly by the API and worker
# roles to write and read archived traces with SSE-KMS.
resource "aws_kms_key" "this" {
  description             = "${var.name_prefix}: trace archive, database, cache, registries, logs and alarms"
  enable_key_rotation     = true
  rotation_period_in_days = var.rotation_period_in_days
  deletion_window_in_days = var.deletion_window_in_days
  policy                  = data.aws_iam_policy_document.key.json
}

resource "aws_kms_alias" "this" {
  name          = "alias/${var.name_prefix}"
  target_key_id = aws_kms_key.this.key_id
}
