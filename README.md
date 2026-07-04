# AuctionEye

Watches an auction site for new listings and emails a notification. Runs as an
AWS Lambda on a daily schedule; seen listings are tracked in DynamoDB.

- **Compute:** AWS Lambda (`python3.12`, handler `src.lambda_handler.handler`)
- **Storage:** DynamoDB table of seen item IDs
- **Schedule:** EventBridge Scheduler — daily at 10pm (`schedule_timezone`)
- **Email:** Gmail SMTP; password read at runtime from SSM Parameter Store
- **Infra:** Terraform in [`infra/`](infra/) — see [infra/README.md](infra/README.md) to deploy

## Running it manually

The Lambda runs one full pass per invocation (scrape → diff against DynamoDB →
email → record). To trigger a pass on demand, invoke it directly. Run from the
`infra/` directory so `terraform output` can resolve the resource names:

```bash
cd infra
aws lambda invoke --function-name "$(terraform output -raw lambda_function_name)" /dev/stdout
```

The response prints the handler's return value, e.g.:

```json
{"new_items": 3, "total_items": 42}
```

followed by invocation metadata. (Authentication comes from your AWS profile —
via `.envrc`/direnv, `AWS_PROFILE`, or `--profile <name>`. Log in first with
`aws sso login --profile <name>` if using SSO.)

### Watch logs

```bash
aws logs tail "$(terraform output -raw log_group_name)" --follow
```

If an invoke fails, `aws lambda invoke` writes a response with a `FunctionError`
field; the traceback shows up in these logs.

### Inspect recorded items

```bash
aws dynamodb scan --table-name "$(terraform output -raw dynamodb_table_name)"
```

## Behavior notes

- The **first** run sees an empty table, so every current listing counts as new:
  it records them all and the email lists them.
- Later runs report only genuinely new items, and still send a "no new items"
  heartbeat email when nothing changed — so a successful run always produces an email.
- The event payload is ignored, so `--payload` is unnecessary when invoking.

## Local development

Install dev dependencies and run the tests:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

You can also run the watcher locally with `python -m src`, which uses the same
code path as the Lambda. It requires `DYNAMODB_TABLE`, `BASE_URL`, `SMTP_USER`,
and either `SMTP_PASS` or `SMTP_PASS_SSM_PARAM` in the environment (a local
`.env` works), plus AWS credentials with access to the table.

## Deployment

See [infra/README.md](infra/README.md) for authentication, `terraform apply`,
and configuration details.
