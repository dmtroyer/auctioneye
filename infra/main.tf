locals {
  name       = var.project_name
  email_from = var.email_from != "" ? var.email_from : var.smtp_user
  email_to   = var.email_to != "" ? var.email_to : var.smtp_user

  # Source that, when changed, should trigger a rebuild + redeploy.
  src_dir      = "${path.module}/../src"
  requirements = "${path.module}/../requirements.txt"
  build_dir    = "${path.module}/build"
  package_zip  = "${path.module}/build/lambda.zip"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
