variable "env" { type = string }
variable "region" { type = string }
variable "aws_account_id" { type = string }
variable "github_oidc_provider_arn" {
  description = "ARN of the account-wide OIDC provider (output of the bootstrap stack)."
  type        = string
}

variable "github_repository" {
  description = "owner/name (e.g. lamba-manish/vestrs)."
  type        = string
}
