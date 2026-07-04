# Remote state in S3 with native locking (Terraform >= 1.10; no DynamoDB table
# needed). The bucket must already exist — run ./bootstrap-state.sh once first.
#
# Backend blocks cannot use variables, so these values are literals. Credentials
# come from the environment (AWS_PROFILE / SSO via your .envrc), so no profile is
# hardcoded here — make sure your profile is active before running terraform.
terraform {
  backend "s3" {
    bucket       = "auctioneye-tfstate-dmtroyer"
    key          = "auctioneye/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
}
