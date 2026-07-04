# AuctionEye infrastructure (Terraform)

Provisions the watcher on AWS:

- **Lambda** (`python3.12`, handler `src.lambda_handler.handler`) — runs one
  watcher pass per invocation. Packaged as a zip built by `build.sh`.
- **DynamoDB** table (`<project>-seen-items`, PAY_PER_REQUEST) — stores seen item IDs.
- **SSM Parameter Store** SecureString (`/<project>/smtp_pass`) — the SMTP password,
  fetched at runtime.
- **EventBridge Scheduler** — invokes the Lambda daily at 10pm (`schedule_timezone`).
- IAM roles + CloudWatch log group.

## Authentication (AWS IAM Identity Center / SSO)

Credentials come from an IAM Identity Center profile (no static keys on disk).
Terraform reads the profile from `var.aws_profile` (set `aws_profile` in
`terraform.tfvars`), so `terraform` commands don't need `AWS_PROFILE` set. You
still log in before running it, and re-login when the session expires:

```bash
aws sso login --profile personal
aws sts get-caller-identity --profile personal   # verify
```

Replace `personal` with your profile name throughout. Raw `aws` CLI commands
(the test section below) still need the profile — either `--profile personal`,
`export AWS_PROFILE=personal`, or a `.envrc` (direnv) in the repo root.

First-time CLI setup, if the profile doesn't exist yet: `aws configure sso`
(needs `awscli` v2). Point it at your Identity Center start URL and the
`AdministratorAccess` role, and set the CLI default region to match `var.region`.

## Usage

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # then edit (incl. aws_profile)

terraform init
terraform validate
terraform plan
terraform apply
```

The build runs automatically via a `local-exec` provisioner (needs `bash`,
`python3`, and `pip` on PATH). It reinstalls deps and re-zips whenever files
under `../src` or `requirements.txt` change.

If Terraform errors with an expired-token / credentials message mid-run, your
SSO session lapsed — run `aws sso login --profile personal` again and re-run.

## Test a deployed invoke

```bash
aws lambda invoke --function-name "$(terraform output -raw lambda_function_name)" /dev/stdout
aws dynamodb scan --table-name "$(terraform output -raw dynamodb_table_name)"
aws logs tail "$(terraform output -raw log_group_name)" --follow
```

## Secret handling note

`smtp_pass` is written to Terraform state, so state must be treated as sensitive.
It is kept in an encrypted, versioned S3 bucket (see Remote state below). To keep
the secret out of state entirely instead, create the SSM parameter out-of-band and
swap `ssm.tf`'s `resource` for a `data "aws_ssm_parameter"` lookup.

## Remote state (S3)

State lives in an encrypted, versioned S3 bucket with native locking
(`backend.tf`). The bucket must exist before `terraform init`, so it's a one-time
bootstrap:

```bash
# 1. Create the state bucket (versioning + encryption + public access blocked).
#    Args default to the bucket/region already in backend.tf.
./bootstrap-state.sh

# 2. Point Terraform at it, migrating the existing local state up to S3.
terraform init -migrate-state    # answer "yes" to copy state

# 3. Once confirmed, the local terraform.tfstate* files are just backups
#    and can be deleted.
```

The bucket name (`auctioneye-tfstate-dmtroyer`) and region in `backend.tf` must
match what `bootstrap-state.sh` creates; change both together if you rename it.
Backend blocks can't read variables, so credentials come from the environment —
have your profile active (`.envrc` / `AWS_PROFILE` / `aws sso login`) first.
