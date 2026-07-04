# Hash of everything that affects the package contents. Changing source or deps
# reruns the build and produces a new zip, triggering a Lambda update.
locals {
  source_hash = sha1(join("", [
    for f in fileset(local.src_dir, "**") : filesha1("${local.src_dir}/${f}")
  ]))
  build_hash = sha1("${local.source_hash}${filesha1(local.requirements)}")
}

resource "null_resource" "build" {
  triggers = {
    build_hash = local.build_hash
  }

  provisioner "local-exec" {
    command     = "bash ${path.module}/build.sh"
    interpreter = ["bash", "-c"]
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${local.build_dir}/package"
  output_path = local.package_zip

  depends_on = [null_resource.build]
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}-watcher"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "watcher" {
  function_name = "${local.name}-watcher"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "src.lambda_handler.handler"

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size

  environment {
    variables = {
      DYNAMODB_TABLE      = aws_dynamodb_table.seen_items.name
      SMTP_PASS_SSM_PARAM = aws_ssm_parameter.smtp_pass.name

      BASE_URL        = var.base_url
      BROWSE_PATH     = var.browse_path
      MAX_PAGES       = tostring(var.max_pages)
      USER_AGENT      = var.user_agent
      REQUEST_TIMEOUT = tostring(var.request_timeout)
      LOG_LEVEL       = var.log_level

      SMTP_HOST  = var.smtp_host
      SMTP_PORT  = tostring(var.smtp_port)
      SMTP_USER  = var.smtp_user
      EMAIL_FROM = local.email_from
      EMAIL_TO   = local.email_to
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_cloudwatch_log_group.lambda,
  ]

  tags = {
    Project = local.name
  }
}
