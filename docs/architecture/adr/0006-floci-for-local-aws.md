# 0006: Floci emulates AWS locally, provisioned by the production Terraform

Status: accepted

## Context

The AWS services the app calls (S3 for the trace archive, KMS for encryption, Secrets Manager)
must work on a laptop with no account and no paid key, and the infrastructure code must be the
same code that builds AWS, not a parallel set of scripts.

## Decision

`make up` starts the Floci emulator (`floci/floci:2.3.0`, MIT) on the compose network and runs a
one-shot Terraform container that applies `infra/terraform/envs/local-floci` against it. That
environment uses the same `kms`, `storage` and `secrets` modules as `aws-dev` and `aws-prod`, with
only the provider endpoints and a few safety switches (no TLS enforcement, no versioning)
different. The API and worker start after it succeeds and archive to S3 with SSE-KMS exactly as on
AWS. PostgreSQL and Valkey are plain containers locally and RDS and ElastiCache on AWS.

## Consequences

- The archive is written, encrypted and read back through the real code path locally and in tests
  (the integration suite runs the S3 archive against Floci).
- Terraform changes are exercised by `make up`, not only by a plan on someone's account.
- The first `make up` is slower (provider download, 3 to 5 minutes); providers are cached in a
  Docker volume.
- The emulator is not AWS: behaviours it does not model (IAM enforcement, some bucket policies)
  are verified by `terraform validate`, tflint and checkov, not by running locally.
