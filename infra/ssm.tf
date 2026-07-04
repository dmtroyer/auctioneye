# The SMTP password lives in SSM Parameter Store but is intentionally NOT managed
# by Terraform, so the secret value never enters Terraform state. The Lambda reads
# it at runtime (SMTP_PASS_SSM_PARAM); Terraform only needs the parameter's name
# and ARN, which we CONSTRUCT here rather than read. (Reading it via a
# `data "aws_ssm_parameter"` source would pull the value back into state.)
#
# Create / rotate the value out-of-band:
#   aws ssm put-parameter --name /auctioneye/smtp_pass --type SecureString \
#       --value '<gmail app password>' --overwrite
#
# It must exist before the Lambda runs (Terraform apply does not create it).

locals {
  smtp_pass_param_name = "/${local.name}/smtp_pass"
  smtp_pass_param_arn = format(
    "arn:%s:ssm:%s:%s:parameter%s",
    data.aws_partition.current.partition,
    data.aws_region.current.name,
    data.aws_caller_identity.current.account_id,
    local.smtp_pass_param_name,
  )
}

# Migration: forget the previously Terraform-managed parameter WITHOUT destroying
# it (the real SSM parameter, with its value, stays in place). Safe to delete this
# block after one `terraform apply` has removed it from state.
removed {
  from = aws_ssm_parameter.smtp_pass

  lifecycle {
    destroy = false
  }
}
