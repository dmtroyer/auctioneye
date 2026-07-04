# SMTP password stored as a SecureString. The Lambda fetches this at runtime
# (via SMTP_PASS_SSM_PARAM) so the secret is never set as a Lambda env var.
#
# NOTE: the value is passed through Terraform state — treat state as sensitive
# (use a remote backend with encryption). To keep the secret out of state
# entirely, create the parameter out-of-band (AWS CLI) and replace this resource
# with a `data "aws_ssm_parameter"` lookup.
resource "aws_ssm_parameter" "smtp_pass" {
  name        = "/${local.name}/smtp_pass"
  description = "SMTP password for ${local.name} watcher"
  type        = "SecureString"
  value       = var.smtp_pass

  tags = {
    Project = local.name
  }
}
