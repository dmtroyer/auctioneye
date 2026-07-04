variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Named AWS profile (e.g. an SSO profile) for the provider to use. Leave null to fall back to AWS_PROFILE / the default credential chain."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Name prefix for all resources."
  type        = string
  default     = "auctioneye"
}

# --- Schedule ---

variable "schedule_expression" {
  description = "EventBridge Scheduler expression. Default: daily at 22:00 (10pm) local."
  type        = string
  default     = "cron(0 22 * * ? *)"
}

variable "schedule_timezone" {
  description = "IANA timezone for the schedule so 10pm is local, not UTC."
  type        = string
  default     = "America/New_York"
}

# --- Lambda sizing ---

variable "lambda_timeout" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 120
}

variable "lambda_memory_size" {
  description = "Lambda memory in MB."
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the Lambda."
  type        = number
  default     = 30
}

# --- Application config (maps to env vars) ---

variable "base_url" {
  description = "Auction site base URL (BASE_URL)."
  type        = string
}

variable "browse_path" {
  description = "Listing path (BROWSE_PATH)."
  type        = string
  default     = "/Browse"
}

variable "max_pages" {
  description = "Max pages to scrape (MAX_PAGES)."
  type        = number
  default     = 20
}

variable "user_agent" {
  description = "Scraper User-Agent (USER_AGENT)."
  type        = string
  default     = "swap-watcher/1.0 (+personal script; contact owner of this account)"
}

variable "request_timeout" {
  description = "Outbound HTTP timeout in seconds (REQUEST_TIMEOUT)."
  type        = number
  default     = 20
}

variable "log_level" {
  description = "Log level (LOG_LEVEL)."
  type        = string
  default     = "INFO"
}

# --- Email / SMTP ---

variable "smtp_host" {
  description = "SMTP host (SMTP_HOST)."
  type        = string
  default     = "smtp.gmail.com"
}

variable "smtp_port" {
  description = "SMTP port (SMTP_PORT)."
  type        = number
  default     = 587
}

variable "smtp_user" {
  description = "SMTP username / login (SMTP_USER)."
  type        = string
}

# NOTE: there is no smtp_pass variable. The SMTP password is stored in SSM
# out-of-band (see ssm.tf) and never passes through Terraform / its state.

variable "email_from" {
  description = "From address (EMAIL_FROM). Defaults to smtp_user if empty."
  type        = string
  default     = ""
}

variable "email_to" {
  description = "To address (EMAIL_TO). Defaults to smtp_user if empty."
  type        = string
  default     = ""
}
