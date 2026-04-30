variable "region" {
  description = "AWS region for the state bucket + lock table."
  type        = string
  default     = "ap-south-1"
}

variable "state_bucket_name" {
  description = "Globally-unique S3 bucket name for terraform remote state."
  type        = string
  default     = "vestrs-tfstate"
}

variable "lock_table_name" {
  description = "DynamoDB table name for terraform state locks."
  type        = string
  default     = "vestrs-tfstate-lock"
}
