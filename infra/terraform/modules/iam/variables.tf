variable "env" {
  description = "Environment name."
  type        = string
}

variable "backups_bucket_arn" {
  description = "ARN of the pg_dump backup bucket; null disables the backups policy."
  type        = string
  default     = null
}

variable "ghcr_credential_param_arn" {
  description = "SSM Parameter Store ARN holding the GHCR PAT (read by cloud-init)."
  type        = string
  default     = null
}
