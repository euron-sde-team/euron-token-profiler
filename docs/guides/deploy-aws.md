# Deploy to AWS

One Terraform deployment module builds everything; `aws-dev` and `aws-prod` only choose sizes and
safety switches.

| Resource         | aws-dev                                                       | aws-prod                                                 |
| ---------------- | ------------------------------------------------------------- | -------------------------------------------------------- |
| Network          | 2 zones, one NAT gateway                                      | 3 zones, NAT per zone, KMS and Secrets Manager endpoints |
| Database         | RDS PostgreSQL 16, single zone, 3 days of backups             | Multi-AZ, 14 days, deletion protection                   |
| Cache            | ElastiCache for Valkey, no replica                            | one replica, automatic failover                          |
| Trace archive    | S3 bucket, SSE-KMS, TLS only, versioned                       | same                                                     |
| Compute          | ECS Fargate: api, worker, web                                 | larger tasks, more of them, autoscaling                  |
| Edge             | ALB with HTTPS                                                | ALB with HTTPS and a WAF                                 |
| Keys and secrets | one KMS key (rotation on), generated app secrets in Secrets Manager | same, longer recovery windows                      |
| Observability    | CloudWatch logs, alarms to SNS, a dashboard                   | same, one year of logs                                   |

One host name serves the dashboard (`/`), the control plane (`/api/v1`), the docs, and ingest
(`/v1`), so the session cookie is first-party and SDKs and exporters use the same URL. `/metrics`
is not routed.

## Sizing

Ingest is CPU and database bound, not memory bound. Start with the defaults, watch the API's CPU
and the `tokenprofiler_ingest_duration_seconds` histogram, and raise `api_min_count` or
`api_cpu` before the database. The worker is light: extra workers are standbys because each loop
holds a Valkey lock.

## Prerequisites

Terraform 1.10 or newer, Docker with buildx, the AWS CLI, credentials for the target account, and a
host name (a Route 53 zone, or an issued ACM certificate you validate yourself).

## Deploy

```bash
cp infra/terraform/envs/aws-dev/terraform.tfvars.example infra/terraform/envs/aws-dev/terraform.tfvars
# edit: hostname, route53_zone_id (or certificate_arn), alarm_email
make aws-plan   ENV=aws-dev        # optional: review the plan
make aws-deploy ENV=aws-dev        # registries, arm64 images, infrastructure, rollout
```

`aws-deploy` applies the registries first, builds and pushes the images, applies everything else
with the image tag (the git commit) and waits for the services to become stable. Migrations run
when the first API task starts, under an advisory lock.

## First sign-in

Create the administrator before sharing the URL, as a one-off ECS task:

```bash
make aws-cli ENV=aws-dev ARGS="user create --email you@example.com --name 'You' --role admin --password 'a-long-passphrase'"
```

Sign in, create a project key and point your SDK or OTLP exporter at `https://<hostname>` (the
exporter endpoint is `https://<hostname>/v1/otlp`).

## Operations

- Retention runs in the worker; turn on "Archive before delete" per project to keep expired traces
  in the S3 bucket (`archive/<project>/<date>/...ndjson.gz`).
- Alert webhooks leave from the worker tasks: allow outbound HTTPS to their hosts.
- Backups are RDS snapshots; the archive bucket is versioned.

## State and teardown

Copy `backend.tf.example` to `backend.tf` for remote state in a private, versioned S3 bucket (state
contains the generated secrets). `terraform destroy` in the environment removes everything except
what you protect (prod keeps its database snapshot and the archive bucket).
